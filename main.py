import os, json, random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.places_fetcher import fetch_leads_for_keyword
from src.validator import validate_lead
from src.deduplicator import get_existing_identifiers, filter_new_leads
from src.email_enricher import enrich_email_if_needed

# Load config
config_path = os.path.join('config', 'keywords.json')
with open(config_path) as f:
    cfg = json.load(f)

# Prepare Google Sheet connection
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
creds = ServiceAccountCredentials.from_json_keyfile_name(service_account_json, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv('GOOGLE_SHEET_ID')).sheet1

# Daily sampling
FULL = cfg.get('generated_searches', [])
DAILY_COMBO_COUNT = int(os.getenv('DAILY_COMBO_COUNT', 10))

today_searches = random.sample(FULL, DAILY_COMBO_COUNT)

all_raw_leads = []
for combo in today_searches:
    leads = fetch_leads_for_keyword(combo['query'], combo['location'], limit=cfg.get('results_per_keyword', 30))
    for lead in leads:
        lead['search_keyword'] = combo['query']
        lead['search_city'] = combo['location']
        # Optional email enrichment
        if os.getenv('ENABLE_EMAIL_ENRICH', 'true').lower() == 'true':
            lead = enrich_email_if_needed(lead)
        lead = validate_lead(lead)
        if lead.get('is_valid'):
            all_raw_leads.append(lead)

# Deduplication against sheet
existing_ids, existing_emails = get_existing_identifiers(sheet)
new_leads = filter_new_leads(all_raw_leads, existing_ids, existing_emails)

# Write to sheet
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
        lead.get('category', '')
    ])
if rows:
    sheet.append_rows(rows, value_input_option='RAW')

print(f"Completed: {len(new_leads)} new leads added.")
