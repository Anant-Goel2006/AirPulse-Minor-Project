from datetime import datetime
import time
from flask import Blueprint, jsonify, request
api_bp = Blueprint("api_bp", __name__)

from backend.app.config import WAQI_TOKEN, LIVE_HISTORY_RETENTION_HOURS
from backend.app.utils import normalize_query_text, _to_float_or_none
from backend.app.services.waqi import (
    LIVE_STATE_LOCK, LIVE_CITY_HISTORY, LIVE_GLOBAL_HISTORY
)
from backend.app.services.core_live import (
    get_live_snapshot_rows, fetch_live_city_row, update_live_histories,
    select_live_row_for_city, _history_entry_from_row, 
    _is_true_query_flag, _city_key_match, _mean_live, _safe_row_timestamp_label,
    _build_heatmap_from_entries, build_historical_payload_from_entries,
    build_current_aqi_response_from_row
)


def generate_lstm_forecast_inlined(city, current_aqi, current_pm25, current_temp):
    """Simple pure-math LSTM simulation to avoid dependencies."""
    import math, random, time
    from backend.app.utils import get_category
    forecast = []
    base_time = int(time.time())
    volatility, trend, current_val = 0.15, (-0.02 if current_aqi > 150 else 0.01), float(current_aqi)
    for day in range(1, 8):
        cell_memory = math.sin(day * math.pi / 4) * (current_val * 0.1)
        noise = random.gauss(0, current_val * volatility)
        next_val = max(10.0, min(500.0, current_val * (1 + trend) + cell_memory + noise))
        forecast_ts = base_time + (day * 86400)
        dt_obj = datetime.fromtimestamp(forecast_ts)
        cat = get_category(int(round(next_val)))
        forecast.append({
            "day_epoch": forecast_ts, "date": dt_obj.strftime("%Y-%m-%d"),
            "day_name": dt_obj.strftime("%A"), "predicted_aqi": int(round(next_val)),
            "level": cat["level"], "color": cat["color"]
        })
        current_val = next_val
    return forecast


@api_bp.route("/predict/7day", methods=["GET"])
def predict_7day():
    city = str(request.args.get("city", "")).strip()
    aqi = request.args.get("aqi", 50, type=float)
    if not city: return jsonify({"error": "City parameter is required"}), 400
    predictions = generate_lstm_forecast_inlined(city, aqi, 0, 0)
    return jsonify({"city": city, "model": "LSTM_Sim_Inlined", "forecast": predictions}), 200


@api_bp.route("/current-aqi")
def current_aqi():
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        raw_city = normalize_query_text(request.args.get("city"))
        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        row = None

        if raw_city:
            row = fetch_live_city_row(raw_city, allow_cached_payload=not force_fresh)
            if row:
                update_live_histories([row])
            if row is None:
                probe_rows = get_live_snapshot_rows(force=force_fresh, city_queries=[raw_city])
                row = select_live_row_for_city(probe_rows, raw_city)
        else:
            rows = get_live_snapshot_rows(force=force_fresh)
            if rows:
                row = max(rows, key=lambda r: float(r.get("timestamp_epoch") or 0.0))

        if row is None:
            msg = f"No live AQI data found for '{raw_city}'" if raw_city else "No live AQI data available right now"
            return jsonify({"error": msg}), 404

        payload = build_current_aqi_response_from_row(row)
        if not isinstance(payload, dict):
            return jsonify({"error": "Failed to build live AQI response"}), 500
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/heatmap")
def heatmap():
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        city = normalize_query_text(request.args.get("city"))
        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        raw_hours = request.args.get("hours", LIVE_HISTORY_RETENTION_HOURS)
        try: hours = int(float(raw_hours))
        except: hours = LIVE_HISTORY_RETENTION_HOURS
        hours = max(1, min(hours, max(1, LIVE_HISTORY_RETENTION_HOURS)))
        cutoff_epoch = time.time() - (hours * 3600)

        rows = get_live_snapshot_rows(force=force_fresh)
        city_row = None
        if city:
            city_row = fetch_live_city_row(city, allow_cached_payload=not force_fresh)
            if city_row:
                update_live_histories([city_row])

        with LIVE_STATE_LOCK:
            if city:
                entries = []
                requested_key = normalize_query_text(city).lower().strip()
                for city_key, history in LIVE_CITY_HISTORY.items():
                    if _city_key_match(requested_key, city_key):
                        entries.extend(list(history))
            else:
                entries = list(LIVE_GLOBAL_HISTORY)
                
        entries = [
            entry for entry in entries
            if float(entry.get("timestamp_epoch") or 0.0) >= cutoff_epoch
        ]

        if not entries:
            if city:
                if city_row:
                    entries = [_history_entry_from_row(city_row)]
                else:
                    row = select_live_row_for_city(rows, city)
                    if row:
                        entries = [_history_entry_from_row(row)]
            else:
                aqi_vals = [_to_float_or_none(r.get("aqi")) for r in rows]
                aqi_vals = [v for v in aqi_vals if v is not None]
                if aqi_vals:
                    entries = [{
                        "timestamp_epoch": time.time(),
                        "aqi": float(sum(aqi_vals) / len(aqi_vals)),
                        "pollutants": {},
                        "weather": {},
                    }]

        if not entries:
            msg = f"No live heatmap data for '{city}'" if city else "No valid AQI values for heatmap"
            return jsonify({"error": msg}), 404

        # Notice: _ensure_min_history_points cloning logic has been removed here to fix duplication bug
        return jsonify(_build_heatmap_from_entries(entries))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/historical")
def historical():
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        city = normalize_query_text(request.args.get("city"))
        raw_hours = request.args.get("hours", 24)
        try: hours = int(float(raw_hours))
        except: hours = 24
        hours = max(1, min(hours, max(1, LIVE_HISTORY_RETENTION_HOURS)))
        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        cutoff_epoch = time.time() - (hours * 3600)

        city_row = None
        if city:
            city_row = fetch_live_city_row(city, allow_cached_payload=not force_fresh)
            if city_row:
                update_live_histories([city_row])
        else:
            get_live_snapshot_rows(force=force_fresh)

        entries = []
        with LIVE_STATE_LOCK:
            if city:
                requested_key = normalize_query_text(city).lower().strip()
                for city_key, history in LIVE_CITY_HISTORY.items():
                    if _city_key_match(requested_key, city_key):
                        entries.extend(list(history))
            else:
                entries = list(LIVE_GLOBAL_HISTORY)

        entries = [
            entry for entry in entries
            if float(entry.get("timestamp_epoch") or 0.0) >= cutoff_epoch
        ]

        if not entries:
            if city:
                if city_row:
                    entries = [_history_entry_from_row(city_row)]
                else:
                    snapshot_rows = get_live_snapshot_rows(force=False, city_queries=[city])
                    row = select_live_row_for_city(snapshot_rows, city)
                    if row:
                        entries = [_history_entry_from_row(row)]
            else:
                rows = get_live_snapshot_rows(force=False)
                if rows:
                    update_live_histories(rows)
                    with LIVE_STATE_LOCK:
                        entries = list(LIVE_GLOBAL_HISTORY)
                    entries = [
                        entry for entry in entries
                        if float(entry.get("timestamp_epoch") or 0.0) >= cutoff_epoch
                    ]

        if not entries:
            return jsonify({"error": "No live historical data available yet"}), 404

        return jsonify(build_historical_payload_from_entries(entries))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/statistics")
def statistics():
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        rows = get_live_snapshot_rows(force=force_fresh)
        if not rows:
            return jsonify({"error": "No live data"}), 404

        aqi_vals = [_to_float_or_none(r.get("aqi")) for r in rows]
        aqi_vals = [v for v in aqi_vals if v is not None]
        if not aqi_vals:
            return jsonify({"error": "No valid AQI values in live data"}), 404

        with LIVE_STATE_LOCK:
            total_readings = int(sum(len(hist) for hist in LIVE_CITY_HISTORY.values()))
        if total_readings <= 0:
            total_readings = len(rows)

        avg_pm25 = _mean_live((r.get("pollutants") or {}).get("pm25") for r in rows)
        avg_pm10 = _mean_live((r.get("pollutants") or {}).get("pm10") for r in rows)
        avg_temperature = _mean_live((r.get("weather") or {}).get("temperature") for r in rows)
        avg_humidity = _mean_live((r.get("weather") or {}).get("humidity") for r in rows)

        return jsonify({
            "total_readings": int(total_readings),
            "avg_aqi": round(float(sum(aqi_vals) / len(aqi_vals)), 1),
            "max_aqi": int(round(max(aqi_vals))),
            "min_aqi": int(round(min(aqi_vals))),
            "cities_monitored": int(len(rows)),
            "avg_pm25": round(float(avg_pm25), 1) if avg_pm25 is not None else 0.0,
            "avg_pm10": round(float(avg_pm10), 1) if avg_pm10 is not None else 0.0,
            "avg_temperature": round(float(avg_temperature), 1) if avg_temperature is not None else 0.0,
            "avg_humidity": round(float(avg_humidity), 1) if avg_humidity is not None else 0.0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/city-ranking")
def city_ranking():
    from backend.app.utils import get_category
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        latest = get_live_snapshot_rows(force=force_fresh)
        if not latest:
            return jsonify({"error": "No live data"}), 404

        latest = sorted(
            latest,
            key=lambda r: float(r.get("aqi") or float("-inf")),
            reverse=True,
        )
        rows = []
        for r in latest:
            aqi_val = _to_float_or_none(r.get("aqi"))
            if aqi_val is None:
                continue
            cat = get_category(int(max(0, round(aqi_val))))
            rows.append({
                "city": str(r.get("city") or "").strip(),
                "country": str(r.get("country") or "").strip(),
                "aqi": float(aqi_val),
                "level": cat["level"], "color": cat["color"],
                "pm25": round(float(_to_float_or_none((r.get("pollutants") or {}).get("pm25")) or 0.0), 1),
                "timestamp": _safe_row_timestamp_label(r),
            })
        return jsonify({"cities": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/city-locations")
def city_locations():
    from backend.app.utils import get_category
    try:
        if not WAQI_TOKEN:
            return jsonify({"error": "WAQI token not configured on server"}), 503

        force_fresh = _is_true_query_flag(request.args.get("fresh"))
        latest = get_live_snapshot_rows(force=force_fresh)
        if not latest:
            return jsonify({"error": "No live data"}), 404

        locations = []
        for row in latest:
            lat = _to_float_or_none(row.get("latitude"))
            lng = _to_float_or_none(row.get("longitude"))
            aqi_val = _to_float_or_none(row.get("aqi"))
            if lat is None or lng is None or aqi_val is None:
                continue
            cat = get_category(int(max(0, round(aqi_val))))
            locations.append({
                "city": row.get("city"),
                "country": row.get("country"),
                "lat": float(lat),
                "lng": float(lng),
                "aqi": float(aqi_val),
                "color": cat["color"], "category": cat["level"],
            })
        locations.sort(key=lambda item: str(item.get("city") or "").lower())
        return jsonify({"locations": locations})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
