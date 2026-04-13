import os
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = str(os.getenv("PEXELS_API_KEY") or "").strip()
if not PEXELS_API_KEY:
    PEXELS_API_KEY = str(os.getenv("PPELS_API_KEY") or "").strip()

print(f"Testing Pexels API Key: {PEXELS_API_KEY[:5]}...{PEXELS_API_KEY[-5:] if len(PEXELS_API_KEY) > 10 else ''}")

if not PEXELS_API_KEY:
    print("Error: PEXELS_API_KEY not found in .env")
    exit(1)

search_query = "Delhi city skyline"
try:
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={
            "query": search_query,
            "orientation": "landscape",
            "per_page": 1,
            "size": "large",
        },
        timeout=10,
    )
    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        photos = data.get("photos", [])
        if photos:
            print("Success! Found a photo.")
            print(f"Photo URL: {photos[0].get('url')}")
            src = photos[0].get("src", {})
            print(f"Landscape URL: {src.get('landscape')}")
        else:
            print("Success but no photos found for this query.")
    elif resp.status_code == 401:
        print("Error: 401 Unauthorized. The API key is likely invalid.")
    else:
        print(f"Error: Received status code {resp.status_code}")
        print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error making request: {e}")
