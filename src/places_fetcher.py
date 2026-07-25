import os, json, requests


def fetch_place_ids(query: str, location: str, limit: int = 30) -> list:
    """Fetch place IDs using the Places API (New) Text Search.

    Uses the free-tier "Text Search (IDs Only)" endpoint by requesting
    only the 'places.id' field mask.  This endpoint is unlimited and
    free on the Essentials plan.

    Falls back to the legacy Text Search endpoint if the new API fails.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("[places_fetcher] ERROR: GOOGLE_API_KEY not set")
        return []

    # --- New Places API (v1) – Text Search (IDs Only) – FREE ---
    url = 'https://places.googleapis.com/v1/places:searchText'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        # Requesting ONLY place id keeps it in the free "IDs Only" SKU
        'X-Goog-FieldMask': 'places.id',
    }
    body = {
        'textQuery': f"{query} in {location}",
        'maxResultCount': min(limit, 20),   # API max is 20 per request
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        print(f"[places_fetcher] POST {url}  status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            ids = [p['id'] for p in data.get('places', []) if 'id' in p]
            print(f"[places_fetcher] Found {len(ids)} place IDs for '{query}' in '{location}'")
            return ids[:limit]
        else:
            print(f"[places_fetcher] New API error: {resp.text[:300]}")
    except Exception as e:
        print(f"[places_fetcher] New API exception: {e}")

    # --- Fallback: Legacy Text Search (may incur cost) ---
    print("[places_fetcher] Falling back to legacy Text Search API")
    legacy_url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': f"{query} in {location}",
        'key': api_key,
        'language': 'en',
    }
    try:
        resp = requests.get(legacy_url, params=params, timeout=15)
        print(f"[places_fetcher] Legacy API status={resp.status_code}")
        if resp.status_code != 200:
            return []
        data = resp.json()
        print(f"[places_fetcher] Legacy API status field: {data.get('status')}")
        if data.get('status') != 'OK':
            print(f"[places_fetcher] Legacy API error_message: {data.get('error_message', 'N/A')}")
            return []
        ids = [p['place_id'] for p in data.get('results', [])[:limit] if 'place_id' in p]
        print(f"[places_fetcher] Legacy found {len(ids)} IDs")
        return ids
    except Exception as e:
        print(f"[places_fetcher] Legacy exception: {e}")
        return []
