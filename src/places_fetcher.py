import os, json, requests

def fetch_leads_for_keyword(query: str, location: str, limit: int = 30):
    """Placeholder implementation using Google Places Text Search API.
    Returns a list of lead dictionaries with minimal fields.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return []
    url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': f"{query} in {location}",
        'key': api_key,
        'language': 'en'
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for place in data.get('results', [])[:limit]:
        lead = {
            'name': place.get('name'),
            'place_id': place.get('place_id'),
            'address': place.get('formatted_address'),
            'rating': place.get('rating'),
            'user_ratings_total': place.get('user_ratings_total'),
            'url': place.get('url'),
            'website': place.get('website'),
            'phone': place.get('formatted_phone_number'),
        }
        results.append(lead)
    return results
