"""Relevance filter to keep only leads related to academic/assignment services."""

# Terms that indicate a RELEVANT lead (checked in name + website)
RELEVANT_TERMS = [
    # Core services
    'assignment', 'essay', 'dissertation', 'thesis', 'homework',
    'coursework', 'academic', 'writing service', 'writing help',
    'tutor', 'tutoring', 'tuition', 'coaching class',
    'education', 'learning', 'study', 'student',
    # Specific services
    'proofreading', 'editing service', 'copywriting',
    'research paper', 'term paper', 'case study',
    'exam help', 'test prep', 'online class',
    'plagiarism', 'grammar check',
    # Business types
    'academy', 'institute', 'classes', 'coaching',
    'e-learning', 'elearning', 'edtech',
    'university', 'college', 'school',
    'content writing', 'ghostwriting', 'ghost writing',
]

# Terms that indicate an IRRELEVANT lead (checked in name only)
IRRELEVANT_TERMS = [
    # Food & drink
    'restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'bakery',
    'bar', 'pub', 'bistro', 'diner', 'food', 'catering', 'kitchen',
    'sweets', 'ice cream', 'dhaba',
    # Health
    'hospital', 'clinic', 'doctor', 'dental', 'pharmacy', 'medical',
    'physiotherapy', 'ayurvedic', 'veterinary', 'pathology', 'diagnostic',
    # Real estate & construction
    'real estate', 'property', 'builder', 'construction', 'architect',
    'interior', 'plumber', 'electrician', 'contractor',
    # Auto & transport
    'garage', 'auto', 'car wash', 'taxi', 'travel', 'tour',
    'logistics', 'courier', 'cargo', 'movers', 'packers',
    # Fitness & beauty
    'gym', 'fitness', 'salon', 'spa', 'beauty', 'parlour', 'parlor',
    # Shopping & manufacturing
    'supermarket', 'grocery', 'mall', 'store', 'shop',
    'factory', 'manufacturing', 'textile', 'jewel',
    # Finance & legal (unrelated)
    'chartered accountant', 'tax consultant', 'insurance',
    # Hotel & accommodation
    'hotel', 'resort', 'lodge', 'hostel', 'guest house',
    # Others
    'temple', 'church', 'mosque', 'ngo', 'trust',
    'petrol', 'gas station', 'hardware',
    'laundry', 'dry clean', 'tailor',
    'event', 'wedding', 'photography',
    'security', 'detective', 'pest control',
]


def is_relevant_lead(lead: dict) -> bool:
    """Check if a lead is relevant to academic/assignment services.

    Returns True if the lead passes relevance checks.
    """
    name = (lead.get('name') or '').lower()
    website = (lead.get('website') or '').lower()
    combined = name + ' ' + website

    # 1. Reject if the name matches any irrelevant term
    for term in IRRELEVANT_TERMS:
        if term in name:
            return False

    # 2. Accept if the name or website matches any relevant term
    for term in RELEVANT_TERMS:
        if term in combined:
            return True

    # 3. If no match either way, reject (conservative approach)
    return False
