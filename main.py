import os, json, time, datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.places_fetcher import fetch_place_ids
from src.place_details import fetch_place_details
from src.validator import validate_lead
from src.deduplicator import get_existing_identifiers, filter_new_leads
from src.email_enricher import enrich_email_if_needed


# Load configuration
config_path = os.path.join('config', 'keywords.json')
with open(config_path) as f:
    cfg = json.load(f)

# Load (or create) persistent state
state_path = os.path.join('config', 'state.json')
if not os.path.exists(state_path):
    state = {
        "keyword_index": 0,
        "city_index": 0,
        "details_used_today": 0,
        "last_run_date": ""
    }
    with open(state_path, "w") as sf:
        json.dump(state, sf, indent=2)
else:
    with open(state_path) as sf:
        state = json.load(sf)

# Reset daily details counter if a new UTC day started
today = datetime.datetime.utcnow().date().isoformat()
if state.get("last_run_date") != today:
    state["details_used_today"] = 0
    state["last_run_date"] = today

# Prepare indices
keyword_idx = state["keyword_index"]
city_idx = state["city_index"]
details_used = state["details_used_today"]

keywords = cfg["keywords"]
all_cities = [c for cities in cfg["countries"].values() for c in cities]
current_keyword = keywords[keyword_idx]

# Environment‑controlled limits (safe for free tier)
DAILY_DETAILS_BUDGET = int(os.getenv('DAILY_PLACE_DETAILS_BUDGET', '300'))  # max Place Details calls per run
MAX_RESULTS_PER_CITY = int(os.getenv('MAX_RESULTS_PER_CITY', '30'))        # max IDs returned per city
MAX_NEW_LEADS_PER_RUN = int(os.getenv('MAX_NEW_LEADS_PER_RUN', '250'))    # safety cap on rows written

new_leads = []
processed_cities = 0

# Google Sheet connection
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
if not service_account_json:
    raise RuntimeError('Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable')
# Try to interpret as file path; if that fails, fall back to raw JSON.
if os.path.isfile(service_account_json):
    creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_json, scope)
else:
    # Assume raw JSON string
    try:
        sa_raw = service_account_json.strip()
        if (sa_raw.startswith('"') and sa_raw.endswith('"')) or (sa_raw.startswith("'") and sa_raw.endswith("'")):
            sa_raw = sa_raw[1:-1]
        if not (sa_raw.startswith('{') and sa_raw.endswith('}')):
            sa_raw = '{' + sa_raw + '}'
        sa_info = json.loads(sa_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)
    except Exception as e:
        raise RuntimeError('Invalid GOOGLE_SERVICE_ACCOUNT_JSON') from e
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv('GOOGLE_SHEET_ID')).sheet1

while details_used < DAILY_DETAILS_BUDGET and processed_cities < len(all_cities):
    city = all_cities[city_idx]
    print(f"\n--- Processing city: {city} | keyword: {current_keyword} ---")
    # 1️⃣ Get place IDs for this city+keyword (free unlimited call)
    place_ids = fetch_place_ids(current_keyword, city, limit=MAX_RESULTS_PER_CITY)
    print(f"[main] Got {len(place_ids)} place IDs for '{city}'")
    if not place_ids:
        print(f"[main] No place IDs found, skipping city")
        city_idx = (city_idx + 1) % len(all_cities)
        processed_cities += 1
        continue
    # 2️⃣ For each ID, fetch full details (costly call, counts against quota)
    for pid in place_ids:
        if details_used >= DAILY_DETAILS_BUDGET:
            break
        details = fetch_place_details(pid)
        if not details:
            print(f"[main] No details for place_id={pid}")
            continue
        lead = {
            "name": details.get('name'),
            "phone": details.get('formatted_phone_number'),
            "website": details.get('website'),
            "address": details.get('address'),
            "rating": details.get('rating'),
            "user_ratings_total": details.get('user_ratings_total'),
            "place_id": details.get('place_id'),
            "search_keyword": current_keyword,
            "search_city": city,
        }
        # Optional email enrichment (does NOT use Google quota)
        if os.getenv('ENABLE_EMAIL_ENRICH', 'true').lower() == 'true':
            lead = enrich_email_if_needed(lead)

        lead = validate_lead(lead)
        print(f"[main] Lead: {lead.get('name')} | score={lead.get('quality_score')} | valid={lead.get('is_valid')}")
        if lead.get('is_valid'):
            new_leads.append(lead)
        details_used += 1
    # move to next city
    city_idx = (city_idx + 1) % len(all_cities)
    processed_cities += 1

# ----------------------------------------------------------------------
# Deduplicate against existing sheet entries
# ----------------------------------------------------------------------
existing_ids, existing_emails = get_existing_identifiers(sheet)
new_leads = filter_new_leads(new_leads, existing_ids, existing_emails)

# Optional safety cap on how many rows we write in one run
if len(new_leads) > MAX_NEW_LEADS_PER_RUN:
    new_leads = new_leads[:MAX_NEW_LEADS_PER_RUN]

# ----------------------------------------------------------------------
# Write new rows to Google Sheet
# ----------------------------------------------------------------------
if new_leads:
    rows = []
    for lead in new_leads:
        rows.append([
            lead.get('date_added', ''),
            lead.get('name', ''),
            lead.get('phone', ''),
            lead.get('phone_intl', ''),
            lead.get('email', ''),
            lead.get('website', ''),
            lead.get('address', ''),
            lead.get('rating', ''),
            lead.get('user_ratings_total', ''),
            lead.get('search_keyword', ''),
            lead.get('search_city', ''),
            lead.get('place_id', ''),
            lead.get('quality_score', ''),
            lead.get('category', ''),
        ])
    sheet.append_rows(rows, value_input_option='RAW')
    print(f"Completed: {len(new_leads)} new leads added for keyword '{current_keyword}'.")
else:
    print(f"No new leads for keyword '{current_keyword}'.")

# ----------------------------------------------------------------------
# Persist updated state for next run
# ----------------------------------------------------------------------
state["keyword_index"] = (keyword_idx + (city_idx == 0)) % len(keywords)
state["city_index"] = city_idx
state["details_used_today"] = details_used
with open(state_path, "w") as sf:
    json.dump(state, sf, indent=2)
