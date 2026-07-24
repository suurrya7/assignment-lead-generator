import gspread

def get_existing_identifiers(sheet):
    # Column K (index 11) = place_id, Column E (index 5) = email (may be blank)
    place_ids = set(sheet.col_values(11)[1:])  # skip header
    emails = set(sheet.col_values(5)[1:])
    return place_ids, emails

def filter_new_leads(leads, existing_ids, existing_emails):
    new = []
    for lead in leads:
        pid_dup = lead.get('place_id') in existing_ids
        email_dup = lead.get('email') and lead['email'] in existing_emails
        if not pid_dup and not email_dup:
            new.append(lead)
    print(f"Deduplication: {len(leads)} raw → {len(new)} new unique leads")
    return new
