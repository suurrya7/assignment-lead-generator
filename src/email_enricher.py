import re, requests

def enrich_email_if_needed(lead: dict) -> dict:
    """If the lead has a website, attempt to extract an email by scraping the homepage.
    Returns the lead dict with an added 'email' key if any email is found.
    """
    website = lead.get('website') or lead.get('url')
    if not website:
        return lead
        
    try:
        # Fetch the homepage
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(website, headers=headers, timeout=5, allow_redirects=True)
        if resp.status_code != 200:
            return lead
            
        # Regex to find emails (simple but effective for public pages)
        # Looks for mailto: links or standard email patterns
        text = resp.text
        
        # 1. Try mailto: links first (highest quality)
        mailto_matches = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
        if mailto_matches:
            lead['email'] = mailto_matches[0].lower()
            return lead
            
        # 2. Try general text search if no mailto is found
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        
        # Filter out common false positives (image extensions, wix domains, etc.)
        valid_emails = []
        for e in emails:
            e = e.lower()
            if any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']):
                continue
            if 'sentry.io' in e or 'wixpress' in e or 'example.com' in e:
                continue
            valid_emails.append(e)
            
        if valid_emails:
            # Prefer 'info', 'contact', 'support', 'hello' if available
            prioritized = sorted(valid_emails, key=lambda x: 0 if any(p in x for p in ['info@', 'contact@', 'support@', 'hello@', 'admin@']) else 1)
            lead['email'] = prioritized[0]
            
    except Exception:
        pass
        
    return lead
