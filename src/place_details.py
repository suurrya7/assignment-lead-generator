import os, requests


def fetch_place_details(place_id: str) -> dict:
    """Fetch full place details for a given Google Place ID.

    Uses the Google Places Details API with the API key provided via the
    ``GOOGLE_API_KEY`` environment variable. Returns a dictionary containing
    the subset of fields required by the lead generation pipeline.

    The result may be empty (``{}``) if the request fails or the API returns an
    error – the caller is responsible for handling that case.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        # Without an API key we cannot query the service; caller will treat
        # this as a missing detail.
        return {}

    url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': place_id,
        'key': api_key,
        'language': 'en',
        # Request only the fields we actually need to minimise quota usage.
        'fields': ','.join([
            'place_id',
            'name',
            'formatted_phone_number',
            'website',
            'rating',
            'user_ratings_total',
            'address_component',
            'formatted_address',
            'utc_offset_minutes'
        ])
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if data.get('status') != 'OK':
            return {}
        result = data.get('result', {})
        # Normalise keys for the rest of the pipeline.
        return {
            'place_id': result.get('place_id'),
            'name': result.get('name'),
            'formatted_phone_number': result.get('formatted_phone_number'),
            'website': result.get('website'),
            'rating': result.get('rating'),
            'user_ratings_total': result.get('user_ratings_total'),
            'address': result.get('formatted_address'),
        }
    except Exception:
        # Network issues or unexpected payload – treat as no data.
        return {}
