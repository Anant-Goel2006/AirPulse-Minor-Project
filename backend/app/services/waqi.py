import os
import time
import json
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from collections import deque
import requests

from backend.app.config import (
    WAQI_TOKEN, WAQI_BASE_URL,
    LIVE_FETCH_WORKERS, LIVE_CACHE_TTL_SEC, LIVE_HISTORY_MAX_POINTS
)
from backend.app.utils import (
    normalize_live_query, normalize_query_text, encode_feed_query,
    haversine_km, compute_bounds_for_radius, parse_aqi_value, _extract_iaqi_value
)

# Shared Memory State
LIVE_FEED_CACHE = {}
LIVE_STATE_LOCK = Lock()
LIVE_CITY_HISTORY = {}
LIVE_GLOBAL_HISTORY = deque(maxlen=LIVE_HISTORY_MAX_POINTS)
LIVE_ROWS_CACHE = {"ts": 0.0, "rows": []}

def encode_feed_query(query):
    return quote(query, safe="")

def waqi_get_json(path, params=None, timeout=8, log_label="WAQI"):
    if not WAQI_TOKEN:
        return {"status": "error", "data": "WAQI token missing"}
    
    url = f"{WAQI_BASE_URL}{path}"
    p = params or {}
    if "token" not in p:
        p["token"] = WAQI_TOKEN

    try:
        resp = requests.get(url, params=p, timeout=timeout)
        if resp.status_code == 403:
            return {"status": "error", "data": "Invalid WAQI token (HTTP 403)"}
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "data": str(e)}

def fetch_feed(query, timeout=8):
    if not query:
        return {"status": "error", "data": "Empty query"}
    
    encoded = encode_feed_query(str(query).strip())
    path = f"/feed/{encoded}/" if not str(query).startswith("@") else f"/feed/{query}/"
    return waqi_get_json(path, timeout=timeout, log_label=f"feed({query[:20]})")

def fetch_search(keyword, timeout=6):
    return waqi_get_json("/search/", {"keyword": keyword}, timeout=timeout, log_label=f"search({keyword[:20]})")

def fetch_map_bounds(lat1, lng1, lat2, lng2, timeout=8):
    bounds = f"{lat1},{lng1},{lat2},{lng2}"
    return waqi_get_json("/map/bounds/", {"latlng": bounds}, timeout=timeout, log_label="bounds")

def _live_cache_key(raw_query):
    return normalize_live_query(raw_query)

def get_live_cache(query_keys):
    now = time.time()
    for q in query_keys:
        key = _live_cache_key(q)
        if not key:
             continue
        with LIVE_STATE_LOCK:
            hit = LIVE_FEED_CACHE.get(key)
        if hit and (now - hit["ts"] < LIVE_CACHE_TTL_SEC):
            return hit["payload"]
    return None

def remember_live_cache(query_keys, payload):
    now = time.time()
    with LIVE_STATE_LOCK:
        for q in query_keys:
            key = _live_cache_key(q)
            if key:
                LIVE_FEED_CACHE[key] = {"ts": now, "payload": payload}

def normalize_feed_payload(payload):
    # Strip fallback logic that drifts from WAQI raw value
    # Only rely on the officially broadcast `aqi` value
    if not isinstance(payload, dict) or str(payload.get("status", "")).lower() != "ok":
        return payload
        
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload
        
    aqi_val = parse_aqi_value(data.get("aqi"))
    if aqi_val is not None:
         # Raw data intact. No interpolation needed.
         return payload
         
    # We DO NOT fallback to an interpolated value anymore if standard AQI is completely missing.
    # The record should explicitly be handled as an empty record by the UI.
    return payload

def is_valid_feed_payload(payload):
    if not isinstance(payload, dict): return False
    if str(payload.get("status", "")).lower() != "ok": return False
    data = payload.get("data")
    if not isinstance(data, dict): return False
    
    # Needs valid geolocation to map correctly
    city = data.get("city")
    if not isinstance(city, dict) or not city.get("geo"):
         return False
         
    return True
