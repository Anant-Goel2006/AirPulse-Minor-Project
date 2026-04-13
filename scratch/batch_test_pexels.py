import os
import requests
import re
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = str(os.getenv("PEXELS_API_KEY") or "").strip()

def build_city_image_queries(seed_text):
    cleaned = re.sub(r"[^a-z0-9 ]", "", str(seed_text or "").strip().lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return []

    parts = cleaned.split()
    tail = " ".join(parts[-2:]) if len(parts) >= 2 else cleaned
    broad = parts[-1] if parts else cleaned
    
    # Updated matching the new broader queries in app.py
    queries = [
        f"{cleaned} city skyline",
        f"{cleaned} urban",
        f"{tail} city",
        f"{broad} skyline",
        f"{broad} city",
        cleaned,
        broad
    ]

    seen = set()
    ordered = []
    for query in queries:
        normalized = re.sub(r"\s+", " ", str(query or "").strip().lower()).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered

test_cities = [
    "Delhi",
    "Mumbai",
    "London",
    "IHBAS, Dilshad Garden, Delhi", # Specific station
    "Bawana, Delhi",
    "Sonia Vihar",
    "Anand Vihar",
    "Aundh, Pune",
    "HSR Layout, Bangalore"
]

for city in test_cities:
    print(f"\n--- Testing City: {city} ---")
    queries = build_city_image_queries(city)
    found = False
    for q in queries:
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": q, "per_page": 1},
                timeout=5
            )
            data = resp.json()
            photos = data.get("photos", [])
            print(f"  Query: '{q}' -> Status: {resp.status_code}, Photos Found: {len(photos)}")
            if photos:
                found = True
                break
        except Exception as e:
            print(f"  Query: '{q}' -> Error: {e}")
    if not found:
        print(f"  !! No photos found for '{city}' with current queries !!")
