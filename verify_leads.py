"""Website-based lead verification.

Reads unverified leads from the Google Sheet, visits each website,
analyses the page content for academic/assignment-related keywords,
and updates a 'Verified' status column in the sheet.
"""

import os, json, re, sys, time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------------------------------------------------------
# Keywords that confirm a website is assignment/academic related
# ---------------------------------------------------------------------------
STRONG_SIGNALS = [
    'assignment help', 'assignment writing', 'essay writing', 'essay help',
    'dissertation help', 'dissertation writing', 'thesis help', 'thesis writing',
    'homework help', 'coursework help', 'coursework writing',
    'academic writing', 'academic help', 'academic assistance',
    'research paper', 'term paper', 'case study writing',
    'write my essay', 'write my assignment', 'do my assignment',
    'do my homework', 'pay someone to write', 'custom essay',
    'custom writing', 'plagiarism free', 'plagiarism-free',
    'online tutoring', 'online tutor', 'tuition centre', 'tuition center',
    'coaching class', 'coaching institute', 'coaching centre',
    'exam preparation', 'test prep',
    'proofreading service', 'editing service',
    'ghostwriting', 'ghost writing', 'content writing service',
    'e-learning', 'elearning', 'edtech',
    'assignment expert', 'myassignment', 'assignmenthelp',
]

MEDIUM_SIGNALS = [
    'student', 'university', 'college', 'academic', 'education',
    'learning', 'study', 'tutor', 'teacher', 'professor',
    'grade', 'marks', 'exam', 'semester', 'syllabus',
    'assignment', 'essay', 'dissertation', 'thesis',
    'homework', 'coursework', 'project help',
    'writing service', 'writing help',
    'academy', 'institute', 'classes',
]

# ---------------------------------------------------------------------------
# Irrelevant signals — if page is dominated by these, it's not our niche
# ---------------------------------------------------------------------------
IRRELEVANT_SIGNALS = [
    'restaurant', 'menu', 'food delivery', 'order food',
    'hotel booking', 'book a room', 'check-in',
    'doctor appointment', 'hospital', 'clinic',
    'buy now', 'add to cart', 'shopping cart', 'e-commerce',
    'real estate', 'property for sale', 'rent apartment',
    'car rental', 'auto repair', 'garage',
    'salon', 'spa', 'beauty treatment',
    'gym membership', 'fitness class',
]


def fetch_page_text(url: str, timeout: int = 10) -> str:
    """Fetch a webpage and return its visible text content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        resp = requests.get(url, headers=headers, timeout=timeout,
                            allow_redirects=True)
        if resp.status_code >= 400:
            return ''
        # Strip HTML tags to get plain text
        text = re.sub(r'<script[^>]*>.*?</script>', ' ', resp.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).lower().strip()
        return text
    except Exception as e:
        print(f"  [verify] Error fetching {url}: {e}")
        return ''


def score_page(text: str) -> dict:
    """Score page text for relevance to academic/assignment services.

    Returns dict with score, verdict, and matched keywords.
    """
    if not text:
        return {'score': 0, 'verdict': 'NO_WEBSITE', 'matched': []}

    strong_matches = [kw for kw in STRONG_SIGNALS if kw in text]
    medium_matches = [kw for kw in MEDIUM_SIGNALS if kw in text]
    irrelevant_matches = [kw for kw in IRRELEVANT_SIGNALS if kw in text]

    # Scoring: strong signals worth 10, medium worth 3, irrelevant subtract 5
    score = len(strong_matches) * 10 + len(medium_matches) * 3 - len(irrelevant_matches) * 5

    if score >= 15:
        verdict = '✅ Verified'
    elif score >= 5:
        verdict = '🔍 Maybe Relevant'
    else:
        verdict = '❌ Not Relevant'

    return {
        'score': score,
        'verdict': verdict,
        'matched': strong_matches[:5] + medium_matches[:3],  # keep top matches for logging
    }


def connect_sheet():
    """Connect to Google Sheet using service account credentials."""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    sa_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not sa_json:
        raise RuntimeError('Missing GOOGLE_SERVICE_ACCOUNT_JSON')

    if os.path.isfile(sa_json):
        creds = ServiceAccountCredentials.from_json_keyfile_name(sa_json, scope)
    else:
        sa_raw = sa_json.strip()
        if (sa_raw.startswith('"') and sa_raw.endswith('"')) or \
           (sa_raw.startswith("'") and sa_raw.endswith("'")):
            sa_raw = sa_raw[1:-1]
        if not (sa_raw.startswith('{') and sa_raw.endswith('}')):
            sa_raw = '{' + sa_raw + '}'
        sa_info = json.loads(sa_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)

    client = gspread.authorize(creds)
    return client.open_by_key(os.getenv('GOOGLE_SHEET_ID')).sheet1


def ensure_verified_column(sheet):
    """Make sure column O (15) has a 'Verified' header."""
    headers = sheet.row_values(1)
    VERIFIED_COL = 15  # Column O
    if len(headers) < VERIFIED_COL or headers[VERIFIED_COL - 1] != 'Verified':
        sheet.update_cell(1, VERIFIED_COL, 'Verified')
    return VERIFIED_COL


def main():
    print("=" * 60)
    print("  LEAD WEBSITE VERIFICATION")
    print("=" * 60)

    sheet = connect_sheet()
    VERIFIED_COL = ensure_verified_column(sheet)

    # Get all rows
    all_rows = sheet.get_all_values()
    if len(all_rows) <= 1:
        print("No leads to verify.")
        return

    headers = all_rows[0]
    # Find the website column (column F = index 5)
    website_col_idx = 5  # 0-indexed column F
    name_col_idx = 1     # 0-indexed column B

    verified_count = 0
    maybe_count = 0
    rejected_count = 0
    skipped_count = 0

    for row_num in range(2, len(all_rows) + 1):  # 1-indexed, skip header
        row = all_rows[row_num - 1]

        # Check if already verified (column O = index 14)
        existing_status = row[VERIFIED_COL - 1] if len(row) >= VERIFIED_COL else ''
        if existing_status and existing_status != '':
            skipped_count += 1
            continue

        name = row[name_col_idx] if len(row) > name_col_idx else ''
        website = row[website_col_idx] if len(row) > website_col_idx else ''

        if not website:
            sheet.update_cell(row_num, VERIFIED_COL, '⚠️ No Website')
            skipped_count += 1
            continue

        # Ensure URL has scheme
        if not website.startswith('http'):
            website = 'https://' + website

        print(f"\n[{row_num}] Checking: {name}")
        print(f"    Website: {website}")

        text = fetch_page_text(website)
        result = score_page(text)

        print(f"    Score: {result['score']} → {result['verdict']}")
        if result['matched']:
            print(f"    Matched: {', '.join(result['matched'][:5])}")

        # Update the sheet
        sheet.update_cell(row_num, VERIFIED_COL, result['verdict'])

        if result['verdict'] == '✅ Verified':
            verified_count += 1
        elif result['verdict'] == '🔍 Maybe Relevant':
            maybe_count += 1
        else:
            rejected_count += 1

        # Rate-limit to avoid Google Sheets quota issues
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"  VERIFICATION COMPLETE")
    print(f"  ✅ Verified:       {verified_count}")
    print(f"  🔍 Maybe Relevant: {maybe_count}")
    print(f"  ❌ Not Relevant:   {rejected_count}")
    print(f"  ⏭️  Skipped:        {skipped_count}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
