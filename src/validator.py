import re, requests


def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 7


def is_website_reachable(url: str, timeout: int = 5) -> bool:
    if not url:
        return False
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_lead(lead: dict) -> dict:
    score = 0
    if lead.get('name'):
        score += 20
    if lead.get('phone') and is_valid_phone(lead['phone']):
        score += 25
    if lead.get('website'):
        score += 20   # count website presence (skip reachability check to save time)
    if lead.get('email') and is_valid_email(lead['email']):
        score += 20
    if lead.get('rating') and float(lead['rating']) >= 3.5:
        score += 10
    if lead.get('address'):
        score += 5
    lead['quality_score'] = score
    # A lead with name + phone OR name + website is valid (score >= 40)
    lead['is_valid'] = score >= 40
    return lead
