import re
import math
from datetime import datetime
from backend.app.config import CATS, STATE_HINTS, AREA_STOPWORDS

def safe_float(raw, default=0.0):
    try:
        return float(raw)
    except (ValueError, TypeError):
        return float(default)

def _to_float_or_none(val):
    try:
        if val is None:
            return None
        out = float(val)
        if math.isnan(out):
            return None
        return out
    except Exception:
        return None

def _json_clone(payload):
    import json
    try:
        return json.loads(json.dumps(payload))
    except Exception:
        return None

def haversine_km(lat1, lon1, lat2, lon2):
    try:
        r = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        return r * 2 * math.asin(math.sqrt(a))
    except Exception:
        return float("inf")

def compute_bounds_for_radius(lat, lng, radius_km):
    try:
        lat, lng = float(lat), float(lng)
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
        return {
            "lat_min": lat - lat_delta,
            "lat_max": lat + lat_delta,
            "lng_min": lng - lng_delta,
            "lng_max": lng + lng_delta
        }
    except Exception:
        return None

def normalize_query_text(raw):
    return str(raw or "").lower().strip()

def get_category(aqi_value):
    try:
        val = int(aqi_value)
    except (ValueError, TypeError):
        return CATS[-1]
    for c in CATS:
        if c.get("min", 0) <= val <= c.get("max", 0):
            return c
    return CATS[-1]

def normalize_station_text(text):
    text = str(text or "").lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\b(?:at|in|near)\b', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_aqi_value(raw):
    txt = str(raw or "").strip()
    if txt in {"", "-", "--", "n/a", "N/A"}:
        return None
    try:
        return float(txt)
    except Exception:
        return None

def _extract_iaqi_value(iaqi, key):
    if not isinstance(iaqi, dict):
        return None
    node = iaqi.get(key)
    if isinstance(node, dict):
        return parse_aqi_value(node.get("v"))
    return parse_aqi_value(node)

def normalize_live_query(raw):
    txt = normalize_query_text(raw)
    from backend.app.config import LIVE_QUERY_ALIASES
    if txt in LIVE_QUERY_ALIASES:
        return LIVE_QUERY_ALIASES[txt]
    if " " in txt and txt.replace(" ", "") in LIVE_QUERY_ALIASES:
        return LIVE_QUERY_ALIASES[txt.replace(" ", "")]
    return txt

def get_time_phase_from_iso(time_iso):
    try:
        if not time_iso:
            return "day"
        stripped = time_iso[:19].replace("Z", "")
        dt = datetime.fromisoformat(stripped)
        h = dt.hour
        if 5 <= h < 18: return "day"
        if 18 <= h <= 21: return "evening"
        return "night"
    except Exception:
        return "day"

def clean_place_token(raw):
    t = str(raw or "").lower().strip()
    t = re.sub(r'\s*\(.*?\)', '', t)
    t = re.sub(r'\s*[-|]\s*(imd|monitor|station|waqi)\b.*$', '', t)
    t = re.sub(r'[^a-z0-9\s.\'-]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def location_from_station_name(raw_name, fallback=""):
    """Robust heuristic parsing of a WAQI standard station string into Area + City fields"""
    original = str(raw_name or "").strip()
    if not (fallback and fallback.strip()):
        fallback = "Unknown"
    if not original:
        return {"area": "", "city": fallback}

    parts = [clean_place_token(p) for p in original.split(",")]
    parts = [p for p in parts if p]
    if not parts:
         return {"area": "", "city": fallback}
         
    fallback_norm = normalize_query_text(fallback)
         
    if len(parts) == 1:
        # e.g "Beijing" or "Connaught Place"
        if fallback_norm and fallback_norm in parts[0]:
            return {"area": "", "city": fallback}
        if any(hint in parts[0] for hint in AREA_STOPWORDS):
            return {"area": parts[0].title(), "city": fallback}
        return {"area": "", "city": parts[0].title()}

    if len(parts) >= 3:
        # e.g ["RK Puram", "New Delhi", "India"] -> ["RK Puram", "New Delhi"]
        return {"area": parts[-3].title(), "city": parts[-2].title()}
        
    # Standard 2-part name ["Area/Station", "City"] or ["City", "Country"] or ["Area", "Country"]
    first = parts[0]
    second = parts[1]
    
    # If the second part looks like a state/country hint or is definitely not a city:
    if second in STATE_HINTS or second in {"india", "us", "usa", "china", "uk", "france", "japan"}:
        if fallback_norm and fallback_norm in first:
            return {"area": "", "city": fallback}
        if any(hint in first for hint in AREA_STOPWORDS):
             return {"area": first.title(), "city": fallback}
        return {"area": "", "city": first.title()}

    # Check if first part explicitly matches the fallback
    if fallback_norm and (fallback_norm == first or fallback_norm in first):
        return {"area": "", "city": fallback}
        
    return {"area": first.title(), "city": second.title()}
