from datetime import datetime
import math
import time
from collections import deque

from backend.app.config import LIVE_HISTORY_RETENTION_HOURS
from backend.app.utils import (
    normalize_query_text,
    _to_float_or_none,
    _json_clone
)
from backend.app.services.waqi import (
    LIVE_STATE_LOCK,
    LIVE_ROWS_CACHE,
    LIVE_CITY_HISTORY,
    LIVE_GLOBAL_HISTORY,
    LIVE_HISTORY_MAX_POINTS
)

def parse_live_timestamp(time_meta):
    now = datetime.now()
    if not isinstance(time_meta, dict):
        return now, now.strftime("%Y-%m-%d %H:%M:%S")

    # Time fallback precedence
    candidates = [
        time_meta.get("iso"),
        time_meta.get("s"),
        (time_meta.get("tz") or {}).get("s"),
        (time_meta.get("tz") or {}).get("iso"),
    ]

    for txt in candidates:
        if not txt or not isinstance(txt, str):
            continue
        parsed = None
        try:
            parsed = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
        except Exception:
            parsed = None
            
        if parsed is None:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    parsed = datetime.strptime(txt, fmt)
                    break
                except Exception:
                    continue
                    
        if parsed is not None:
            return parsed, txt
            
    return now, now.strftime("%Y-%m-%d %H:%M:%S")

def build_current_aqi_from_live_payload(live_payload, requested_city=None):
    from backend.app.utils import get_category, location_from_station_name

    if not isinstance(live_payload, dict):
        return None
    data = live_payload.get("data")
    if not isinstance(data, dict):
        return None
        
    aqi_raw = data.get("aqi")
    aqi_float = _to_float_or_none(aqi_raw)
    
    # Do NOT interpolate if it's explicitly None, missing data is distinct from 0.0 AQI
    if aqi_float is None:
        return None

    cat = get_category(aqi_float)
    city_dict = data.get("city") if isinstance(data.get("city"), dict) else {}
    raw_name = city_dict.get("name") or requested_city or ""
    
    loc = location_from_station_name(raw_name, fallback=requested_city)

    # Pollutants
    iaqi = data.get("iaqi") or {}
    pollutants = {}
    from backend.app.config import POLL_CFG
    for p_key in POLL_CFG:
        node = iaqi.get(p_key)
        val = None
        if isinstance(node, dict): val = _to_float_or_none(node.get("v"))
        else: val = _to_float_or_none(node)
        if val is not None:
            pollutants[p_key] = val

    # Weather (temperature from iaqi 't', humidity 'h', wind 'w')
    weather = {}
    for w_key, i_key in [("temperature", "t"), ("humidity", "h"), ("wind_speed", "w")]:
        node = iaqi.get(i_key)
        val = None
        if isinstance(node, dict): val = _to_float_or_none(node.get("v"))
        else: val = _to_float_or_none(node)
        if val is not None:
            weather[w_key] = val

    # Geo
    geo = city_dict.get("geo") or []
    lat = _to_float_or_none(geo[0]) if len(geo) > 0 else None
    lng = _to_float_or_none(geo[1]) if len(geo) > 1 else None

    # Time
    time_meta = data.get("time") if isinstance(data.get("time"), dict) else {}
    ts_dt, ts_label = parse_live_timestamp(time_meta)

    return {
        "aqi": aqi_float,
        "category": cat["level"],
        "color": cat["color"],
        "bg": cat["bg"],
        "description": cat["text"],
        "station_name": raw_name,
        "area": loc["area"],
        "city": loc["city"],
        "country": "",
        "latitude": lat,
        "longitude": lng,
        "pollutants": pollutants,
        "weather": weather,
        "timestamp": ts_label,
        "timestamp_epoch": ts_dt.timestamp()
    }

def build_live_row_from_payload(live_payload, requested_city=""):
    base = build_current_aqi_from_live_payload(live_payload, requested_city=requested_city)
    if not isinstance(base, dict):
        return None

    data = live_payload.get("data") if isinstance(live_payload, dict) else {}
    city_meta = data.get("city") if isinstance(data.get("city"), dict) else {}
    station_name = str(city_meta.get("name") or requested_city or base.get("city") or "").strip()
    time_meta = data.get("time") if isinstance(data.get("time"), dict) else {}
    ts_dt, ts_label = parse_live_timestamp(time_meta)
    city_key = normalize_query_text(base.get("city") or requested_city).lower().strip()

    return {
        "city_key": city_key,
        "city": str(base.get("city") or requested_city or "Unknown").strip(),
        "country": str(base.get("country") or "").strip(),
        "station_name": str(base.get("station_name") or station_name).strip(),
        "area": str(base.get("area") or "").strip(),
        "aqi": float(base.get("aqi")),
        "category": str(base.get("category") or "Unknown"),
        "color": str(base.get("color") or "#9ca3af"),
        "bg": str(base.get("bg") or "#f5f5f5"),
        "description": str(base.get("description") or ""),
        "latitude": _to_float_or_none(base.get("latitude")),
        "longitude": _to_float_or_none(base.get("longitude")),
        "pollutants": base.get("pollutants"),
        "weather": base.get("weather"),
        "timestamp": ts_label,
        "timestamp_iso": ts_dt.isoformat(timespec="seconds"),
        "timestamp_epoch": float(ts_dt.timestamp()),
        "source": "live",
    }

def build_current_aqi_response_from_row(row):
    if not isinstance(row, dict):
        return None
    return {
        "aqi": float(row.get("aqi", 0.0)),
        "category": row.get("category"),
        "color": row.get("color"),
        "bg": row.get("bg"),
        "description": row.get("description"),
        "station_name": row.get("station_name"),
        "area": row.get("area"),
        "city": row.get("city"),
        "country": row.get("country"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "timestamp": row.get("timestamp"),
        "pollutants": row.get("pollutants") or {},
        "weather": row.get("weather") or {},
        "source": "live",
    }
