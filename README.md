# Assignment Lead Generator

A GitHub‑Actions‑powered pipeline that generates daily B2B leads for academic writing services across major cities in India, the United Kingdom, the United States, Australia and Canada.

The generator combines a massive keyword × city matrix, Google Places API look‑ups, optional email enrichment via **theHarvester**, validation, de‑duplication against a master Google Sheet and writes the final leads to the sheet for downstream CRM import.

## Repository Layout
```
assignment-lead-generator/
├─ .github/workflows/daily_leads.yml
├─ config/keywords.json          # keyword & city matrix (generated once)
├─ src/
│   ├─ places_fetcher.py
│   ├─ validator.py
│   ├─ deduplicator.py
│   ├─ sheets_writer.py
│   └─ email_enricher.py
├─ main.py
├─ requirements.txt
└─ README.md
```

## Setup
1. Add the required GitHub secrets:
   - `GOOGLE_API_KEY`
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`
   - `ENABLE_EMAIL_ENRICH` (optional, true/false)
2. Run the one‑time script `generate_searches.py` (included in `src/`) to populate `config/keywords.json` with the full search matrix.
3. The workflow will run daily at 08:00 UTC, produce up to 300 leads, and append them to the Google Sheet.

## Development
Install dependencies:
```
python -m pip install -r requirements.txt
```
Run locally:
```
python main.py
```
