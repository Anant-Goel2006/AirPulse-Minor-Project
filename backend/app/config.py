import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
WAQI_TOKEN = os.getenv("WAQI_TOKEN", "")
if not WAQI_TOKEN:
    # Check fallback for legacy env var name if necessary, or just rely on WAQI_TOKEN
    WAQI_TOKEN = os.getenv("WAQI_API_TOKEN", "")

# Server Configuration
FLASK_PORT = int(os.getenv("FLASK_PORT", 8080))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
WAQI_BASE_URL = os.getenv("WAQI_BASE_URL", "https://api.waqi.info").strip().rstrip("/")
if WAQI_BASE_URL == "http://api.waqi.info":
    WAQI_BASE_URL = "https://api.waqi.info"

# Cache & Limits
LIVE_CACHE_TTL_SEC = int(os.getenv("LIVE_CACHE_TTL_SEC", "120"))
LIVE_ONLY_MODE = str(os.getenv("LIVE_ONLY_MODE", "true")).strip().lower() in {"1", "true", "yes", "y"}
LIVE_SNAPSHOT_TTL_SEC = int(os.getenv("LIVE_SNAPSHOT_TTL_SEC", "60"))
LIVE_HISTORY_RETENTION_HOURS = int(os.getenv("LIVE_HISTORY_RETENTION_HOURS", "48"))
LIVE_HISTORY_MAX_POINTS = int(os.getenv("LIVE_HISTORY_MAX_POINTS", "720"))
LIVE_FETCH_WORKERS = int(os.getenv("LIVE_FETCH_WORKERS", "6"))

DEFAULT_MONITOR_CITIES = [
    "delhi", "mumbai", "bengaluru", "kolkata", "hyderabad", "chennai",
    "beijing", "shanghai", "london", "new york", "tokyo", "singapore",
    "sydney", "paris"
]

def parse_monitor_cities():
    raw = os.getenv("MONITOR_CITIES", "")
    if raw.strip():
        cities = [c.strip() for c in raw.split(",") if c.strip()]
        if cities:
            return cities
    return DEFAULT_MONITOR_CITIES

LIVE_MONITOR_CITIES = parse_monitor_cities()

# UI Constants
CATS = [
    {"min":0,   "max":50,  "level":"Good",              "color":"#009966", "bg":"#e8f8f2", "text":"Air quality is satisfactory, and air pollution poses little or no risk."},
    {"min":51,  "max":100, "level":"Moderate",          "color":"#ffde33", "bg":"#fffde8", "text":"Air quality is acceptable. However, there may be a risk for some people."},
    {"min":101, "max":150, "level":"Unhealthy for Sens.","color":"#ff9933", "bg":"#fff3e0", "text":"Members of sensitive groups may experience health effects. The general public is less likely to be affected."},
    {"min":151, "max":200, "level":"Unhealthy",         "color":"#cc0033", "bg":"#fde8ed", "text":"Some members of the general public may experience health effects; sensitive groups may experience more serious effects."},
    {"min":201, "max":300, "level":"Very Unhealthy",    "color":"#660099", "bg":"#f3e8ff", "text":"Health alert: The risk of health effects is increased for everyone."},
    {"min":301, "max":999, "level":"Hazardous",         "color":"#7e0023", "bg":"#fde8e8", "text":"Dangerously high pollution levels. Life-threatening health risks. Stay indoors."},
]

LIVE_QUERY_ALIASES = {
    "uk": "united kingdom",
    "england": "united kingdom",
    "usa": "united states",
    "us": "united states",
    "u s": "united states",
    "u.s.": "united states",
}

STATE_HINTS = {
    "kerala", "tamil nadu", "karnataka", "maharashtra", "gujarat",
    "rajasthan", "punjab", "haryana", "uttar pradesh", "bihar",
    "west bengal", "odisha", "andhra pradesh", "telangana", "assam",
    "madhya pradesh", "chhattisgarh", "jharkhand", "uttarakhand",
    "himachal pradesh", "delhi", "goa", "tripura", "manipur",
    "meghalaya", "mizoram", "nagaland", "sikkim", "arunachal pradesh",
}

AREA_STOPWORDS = {
    "market", "airport", "industrial", "college", "school", "hospital", "chowk",
    "junction", "square", "zone", "park", "ward", "township", "district",
    "marg", "ave", "avenue", "boulevard", "blvd", "expressway", "highway",
}
