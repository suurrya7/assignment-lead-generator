import os, json, re, time, datetime
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

keywords = cfg["keywords"]
all_cities = [c for cities in cfg["countries"].values() for c in cities]

# Environment-controlled limits (safe for free tier)
DAILY_DETAILS_BUDGET = int(os.getenv('DAILY_PLACE_DETAILS_BUDGET', '300'))
MAX_RESULTS_PER_CITY = int(os.getenv('MAX_RESULTS_PER_CITY', '30'))
MAX_NEW_LEADS_PER_RUN = int(os.getenv('MAX_NEW_LEADS_PER_RUN', '250'))

# ----------------------------------------------------------------------
# Google Sheet connection
# ----------------------------------------------------------------------
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
if not service_account_json:
    raise RuntimeError('Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable')
if os.path.isfile(service_account_json):
    creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_json, scope)
else:
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
spreadsheet = client.open_by_key(os.getenv('GOOGLE_SHEET_ID'))
sheet = spreadsheet.sheet1  # leads go here


# ----------------------------------------------------------------------
# Fetch existing IDs at the START so we can skip them immediately
# ----------------------------------------------------------------------
print("[main] Fetching existing identifiers from sheet...")
existing_ids, existing_emails = get_existing_identifiers(sheet)
print(f"[main] Found {len(existing_ids)} existing Place IDs.")


# ----------------------------------------------------------------------
# State management — stored in a "State" tab inside the same Google Sheet
# ----------------------------------------------------------------------
def get_or_create_state_sheet(spreadsheet):
    """Get or create a 'State' worksheet to persist progress."""
    try:
        return spreadsheet.worksheet('State')
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title='State', rows=5, cols=2)
        # Using update_acell to be 100% immune to gspread version differences
        ws.update_acell('A1', 'keyword_index')
        ws.update_acell('B1', '0')
        ws.update_acell('A2', 'city_index')
        ws.update_acell('B2', '0')
        ws.update_acell('A3', 'details_used_today')
        ws.update_acell('B3', '0')
        ws.update_acell('A4', 'last_run_date')
        ws.update_acell('B4', '')
        print("[state] Created 'State' tab in Google Sheet")
        return ws


def load_state(state_ws):
    """Load state from the State worksheet."""
    data = state_ws.get_all_values()
    state = {}
    for row in data:
        if len(row) >= 2:
            state[row[0]] = row[1]
    return {
        'keyword_index': int(state.get('keyword_index', 0) or 0),
        'city_index': int(state.get('city_index', 0) or 0),
        'details_used_today': int(state.get('details_used_today', 0) or 0),
        'last_run_date': state.get('last_run_date', ''),
    }


def save_state(state_ws, state):
    """Save state back to the State worksheet."""
    state_ws.update_acell('B1', str(state['keyword_index']))
    state_ws.update_acell('B2', str(state['city_index']))
    state_ws.update_acell('B3', str(state['details_used_today']))
    state_ws.update_acell('B4', state['last_run_date'])
    print(f"[state] Saved: keyword={state['keyword_index']}, city={state['city_index']}, details_used={state['details_used_today']}")


state_ws = get_or_create_state_sheet(spreadsheet)
state = load_state(state_ws)

# Reset daily details counter if a new UTC day started
today = datetime.datetime.utcnow().date().isoformat()
if state['last_run_date'] != today:
    state['details_used_today'] = 0
    state['last_run_date'] = today

# Prepare indices
keyword_idx = state['keyword_index']
city_idx = state['city_index']
details_used = state['details_used_today']
current_keyword = keywords[keyword_idx % len(keywords)]

print(f"\n{'='*60}")
print(f"  Starting run: keyword='{current_keyword}' ({keyword_idx+1}/{len(keywords)})")
print(f"  Starting city index: {city_idx} ({all_cities[city_idx % len(all_cities)]})")
print(f"  Details budget: {details_used}/{DAILY_DETAILS_BUDGET}")
print(f"{'='*60}")

new_leads = []
processed_cities = 0
budget_hit = False

while details_used < DAILY_DETAILS_BUDGET and processed_cities < len(all_cities):
    city = all_cities[city_idx % len(all_cities)]
    print(f"\n--- Processing city: {city} | keyword: {current_keyword} ---")
    
    # 1️⃣ Get place IDs for this city+keyword (free unlimited call)
    place_ids = fetch_place_ids(current_keyword, city, limit=MAX_RESULTS_PER_CITY)
    print(f"[main] Got {len(place_ids)} place IDs for '{city}'")
    
    if not place_ids:
        print(f"[main] No place IDs found, skipping city")
        city_idx += 1
        processed_cities += 1
        continue
        
    # 2️⃣ For each ID, fetch full details (costly call, counts against quota)
    for pid in place_ids:
        if details_used >= DAILY_DETAILS_BUDGET:
            budget_hit = True
            break
            
        if pid in existing_ids:
            # Skip instantly without using any quota!
            continue
            
        details = fetch_place_details(pid)
        if not details:
            print(f"[main] No details for place_id={pid}")
            continue
            
        lead = {
            "name": details.get('name'),
            "phone": details.get('formatted_phone_number'),
            "phone_intl": details.get('international_phone_number'),
            "website": details.get('website'),
            "address": details.get('address'),
            "rating": details.get('rating'),
            "user_ratings_total": details.get('user_ratings_total'),
            "place_id": details.get('place_id'),
            "search_keyword": current_keyword,
            "search_city": city,
        }
        # Generate WhatsApp number: country code + number, digits only, no + sign
        intl = details.get('international_phone_number') or ''
        whatsapp = re.sub(r'[^0-9]', '', intl)
        lead['whatsapp'] = whatsapp
        
        # Optional email enrichment (does NOT use Google quota)
        if os.getenv('ENABLE_EMAIL_ENRICH', 'true').lower() == 'true':
            lead = enrich_email_if_needed(lead)

        lead = validate_lead(lead)
        print(f"[main] Lead: {lead.get('name')} | score={lead.get('quality_score')} | valid={lead.get('is_valid')}")
        
        if lead.get('is_valid'):
            new_leads.append(lead)
            existing_ids.add(pid) # Add locally so we don't fetch again today
            
        details_used += 1

    if budget_hit:
        print("\n[main] Daily budget reached mid-city! Halting further queries.")
        # DO NOT increment city_idx! Next run will resume exactly at this city!
        break
    else:
        # Finished all IDs in this city
        city_idx += 1
        processed_cities += 1

# When all cities are done for this keyword, move to next keyword
# Only advance if we actually finished the list and didn't just break from budget
if city_idx >= len(all_cities) and not budget_hit:
    keyword_idx = (keyword_idx + 1) % len(keywords)
    city_idx = 0
    print(f"\n[main] All cities done for '{current_keyword}'. Next keyword: '{keywords[keyword_idx]}'")

# ----------------------------------------------------------------------
# Deduplicate again just in case (email duplicates, etc.)
# ----------------------------------------------------------------------
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
            lead.get('whatsapp', ''),
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
# Persist updated state to Google Sheet (survives across CI runs)
# ----------------------------------------------------------------------
state['keyword_index'] = keyword_idx
state['city_index'] = city_idx
state['details_used_today'] = details_used
save_state(state_ws, state)
