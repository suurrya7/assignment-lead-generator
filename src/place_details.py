import os, requests


def fetch_place_details(place_id: str) -> dict:
    """Fetch full place details for a given Google Place ID.

    Uses the Places API (New) v1 endpoint with a limited field mask
    to stay within the "Place Details Essentials" SKU (10,000 free/month).

    Falls back to the legacy Place Details endpoint if the new API fails.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return {}

    # --- New Places API (v1) – Place Details ---
    url = f'https://places.googleapis.com/v1/places/{place_id}'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': ','.join([
            'id',
            'displayName',
            'nationalPhoneNumber',
            'internationalPhoneNumber',
            'websiteUri',
            'rating',
            'userRatingCount',
            'formattedAddress',
        ]),
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            r = resp.json()
            return {
                'place_id': r.get('id'),
                'name': r.get('displayName', {}).get('text', ''),
                'formatted_phone_number': r.get('nationalPhoneNumber') or r.get('internationalPhoneNumber'),
                'international_phone_number': r.get('internationalPhoneNumber'),
                'website': r.get('websiteUri'),
                'rating': r.get('rating'),
                'user_ratings_total': r.get('userRatingCount'),
                'address': r.get('formattedAddress'),
            }
        else:
            print(f"[place_details] New API error ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[place_details] New API exception: {e}")

    # --- Fallback: Legacy Place Details ---
    legacy_url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': place_id,
        'key': api_key,
        'language': 'en',
        'fields': ','.join([
            'place_id',
            'name',
            'formatted_phone_number',
            'international_phone_number',
            'website',
            'rating',
            'user_ratings_total',
            'formatted_address',
        ]),
    }
    try:
        resp = requests.get(legacy_url, params=params, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if data.get('status') != 'OK':
            return {}
        result = data.get('result', {})
        return {
            'place_id': result.get('place_id'),
            'name': result.get('name'),
            'formatted_phone_number': result.get('formatted_phone_number'),
            'international_phone_number': result.get('international_phone_number'),
            'website': result.get('website'),
            'rating': result.get('rating'),
            'user_ratings_total': result.get('user_ratings_total'),
            'address': result.get('formatted_address'),
        }
    except Exception:
        return {}
