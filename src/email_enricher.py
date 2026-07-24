import subprocess, json, re, os

def enrich_email_if_needed(lead: dict, limit: int = 10) -> dict:
    """If the lead has a website, attempt to extract the domain and run theHarvester to find emails.
    Returns the lead dict with an added 'email' key if any email is found.
    """
    website = lead.get('website') or lead.get('url')
    if not website:
        return lead
    # Extract domain from URL
    domain = re.sub(r'^https?://', '', website).split('/')[0]
    if not domain:
        return lead
    # Run theHarvester command
    cmd = ["theHarvester", "-d", domain, "-b", "all", "-l", str(limit), "-f", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return lead
        data = json.loads(result.stdout)
        emails = [e.get('email') for e in data.get('emails', []) if e.get('email')]
        if emails:
            lead['email'] = emails[0]  # take first
    except Exception:
        pass
    return lead
