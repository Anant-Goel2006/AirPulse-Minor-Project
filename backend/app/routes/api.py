from datetime import datetime
import time
from flask import Blueprint, jsonify, request

from backend.app.config import WAQI_TOKEN, LIVE_HISTORY_RETENTION_HOURS
from backend.app.utils import normalize_query_text, _to_float_or_none, get_category
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
from backend.app.services.email_service import send_email, send_aqi_alert_email

api_bp = Blueprint("api_bp", __name__)


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


# ── Email Alert APIs ──────────────────────────────────────────
@api_bp.route("/email/send-aqi-alert", methods=["POST"])
def send_aqi_alert():
    """
    Send AQI alert email with professional HTML formatting.
    
    Request JSON:
    {
        "to_email": "user@example.com",
        "city": "Delhi",
        "aqi": 285,
        "aqi_category": "Severe",
        "pollutants": {
            "PM2.5": 245.5,
            "PM10": 380.2,
            "NO2": 89.1
        },
        "recommendation": "Avoid all outdoor activities..."
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400
        
        to_email = str(data.get("to_email", "")).strip()
        city = str(data.get("city", "Unknown")).strip()
        aqi_value = int(data.get("aqi", 0))
        aqi_category = str(data.get("aqi_category", "Unknown")).strip()
        pollutants = data.get("pollutants", {})
        recommendation = str(data.get("recommendation", "")).strip()
        
        # Validate email
        if not to_email or "@" not in to_email:
            return jsonify({"error": "Invalid email address"}), 400
        
        # Send alert email
        result = send_aqi_alert_email(
            to_email=to_email,
            city=city,
            aqi_value=aqi_value,
            aqi_category=aqi_category,
            pollutants=pollutants if pollutants else None,
            recommendation=recommendation if recommendation else None
        )
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "message_id": result['message_id']
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result['error'],
                "message": result['message']
            }), 500
    
    except Exception as e:
        return jsonify({"error": f"Exception: {str(e)}"}), 500


@api_bp.route("/email/send", methods=["POST"])
def send_custom_email():
    """
    Send a custom email with HTML and/or plain text body.
    
    Request JSON:
    {
        "to_email": "user@example.com",
        "subject": "Test Email",
        "html_body": "<h1>Hello</h1>",
        "text_body": "Hello",
        "cc_emails": ["cc@example.com"],
        "bcc_emails": ["bcc@example.com"],
        "reply_to": "noreply@example.com"
    }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No JSON payload provided"}), 400
        
        to_email = str(data.get("to_email", "")).strip()
        subject = str(data.get("subject", "")).strip()
        html_body = data.get("html_body")
        text_body = data.get("text_body")
        cc_emails = data.get("cc_emails")
        bcc_emails = data.get("bcc_emails")
        reply_to = data.get("reply_to")
        
        # Validate inputs
        if not to_email or "@" not in to_email:
            return jsonify({"error": "Invalid recipient email address"}), 400
        
        if not subject:
            return jsonify({"error": "Subject line cannot be empty"}), 400
        
        if not html_body and not text_body:
            return jsonify({"error": "Either html_body or text_body is required"}), 400
        
        # Send email
        result = send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            reply_to=reply_to
        )
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "message_id": result['message_id']
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result['error'],
                "message": result['message']
            }), 500
    
    except Exception as e:
        return jsonify({"error": f"Exception: {str(e)}"}), 500


@api_bp.route("/email/test", methods=["POST"])
def test_email():
    """
    Send a test email to verify SMTP configuration.
    
    Request JSON:
    {
        "to_email": "your-email@example.com"
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        to_email = str(data.get("to_email", "")).strip()
        
        if not to_email or "@" not in to_email:
            return jsonify({"error": "Valid email address required"}), 400
        
        result = send_email(
            to_email=to_email,
            subject="🧪 AirPulse Email Service Test",
            html_body="""
            <html>
                <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center;">
                        <h1>✅ Email Service Working!</h1>
                    </div>
                    <div style="padding: 20px; background: #f5f5f5;">
                        <p>Your SMTP configuration is correctly set up.</p>
                        <p><strong>Email Service Details:</strong></p>
                        <ul>
                            <li>✅ SMTP Connection: Successful</li>
                            <li>✅ Authentication: Successful</li>
                            <li>✅ Message Delivery: Successful</li>
                        </ul>
                        <p style="margin-top: 20px; color: #666; font-size: 12px;">
                            This is an automated test email from AirPulse Air Quality Monitor.
                        </p>
                    </div>
                </body>
            </html>
            """,
            text_body="AirPulse Email Service Test - If you received this, your SMTP is configured correctly!"
        )
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": f"Test email sent to {to_email}",
                "message_id": result['message_id']
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": result['error'],
                "message": "Failed to send test email"
            }), 500
    
    except Exception as e:
        return jsonify({"error": f"Exception: {str(e)}"}), 500

