"""
Regex patterns for extracting structured fields from OHS certificates.
Used as the fast, deterministic extraction layer before LLM calls.
"""

import re
from datetime import date
from dateutil import parser as date_parser


# --- Date patterns ---
# Handles common UK and international formats found on inspection certificates

DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    r'\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b',
    # DD Month YYYY  e.g. 15 March 2025
    r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
    # DD Mon YYYY  e.g. 15 Mar 2025
    r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b',
    # YYYY-MM-DD (ISO format)
    r'\b(\d{4})-(\d{2})-(\d{2})\b',
]

# --- Certificate number patterns ---
CERT_NUMBER_PATTERNS = [
    r'(?:certificate|cert|ref|no|number)[.\s#:]*([A-Z0-9\-\/]{4,20})',
    r'(?:examination|report)\s+(?:number|no|ref|#)[.\s:]*([A-Z0-9\-\/]{4,20})',
    r'(?:doc|document)\s*(?:no|number|ref)[.\s:]*([A-Z0-9\-\/]{4,20})',
]

# --- Safe Working Load patterns ---
SWL_PATTERNS = [
    r'(?:safe\s+working\s+load|swl|rated\s+capacity|wll)[.\s:]*(\d+(?:\.\d+)?)\s*(?:tonne|ton|kg|kn|t\b)',
    r'(\d+(?:\.\d+)?)\s*(?:tonne|ton|kg)\s*(?:swl|safe\s+working\s+load)',
    r'swl[:\s]*(\d+(?:\.\d+)?)\s*(?:t\b|te\b|tonne|ton|kg)',
]

# --- Working Pressure patterns ---
PRESSURE_PATTERNS = [
    r'(?:maximum\s+allowable\s+working\s+pressure|mawp|working\s+pressure|max\s+pressure)[.\s:]*(\d+(?:\.\d+)?)\s*(?:bar|barg|psi|kpa|mpa)',
    r'(\d+(?:\.\d+)?)\s*(?:bar|barg|psi)\s*(?:mawp|working\s+pressure|max)',
    r'pressure[:\s]*(\d+(?:\.\d+)?)\s*(?:bar|barg|psi)',
]

# --- Plant / equipment ID patterns ---
PLANT_ID_PATTERNS = [
    r'(?:plant\s+(?:id|no|number|ref)|equipment\s+(?:id|no|number|ref)|serial\s+(?:no|number))[.\s:]*([A-Z0-9\-\/]{2,20})',
    r'(?:asset\s+(?:no|number|id|ref))[.\s:]*([A-Z0-9\-\/]{2,20})',
    r'(?:id|s\/n|s\.n\.)[:\s]*([A-Z0-9\-\/]{4,20})',
]


def extract_dates(text: str) -> list[str]:
    """Extract all raw date strings found in the text."""
    found = []
    for pattern in DATE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # re.findall returns tuples for groups — join them back
            if isinstance(match, tuple):
                found.append(" ".join(str(m) for m in match if m))
            else:
                found.append(match)
    return found


def parse_date_string(date_str: str | None) -> date | None:
    """Parse a date string into a date object. Returns None if unparseable."""
    if not date_str:
        return None
    try:
        return date_parser.parse(str(date_str), dayfirst=True).date()
    except (ValueError, TypeError, OverflowError):
        return None


def extract_certificate_number(text: str) -> str | None:
    """Extract certificate or reference number."""
    for pattern in CERT_NUMBER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_swl(text: str) -> str | None:
    """Extract Safe Working Load value with units."""
    for pattern in SWL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_pressure(text: str) -> str | None:
    """Extract Maximum Allowable Working Pressure with units."""
    for pattern in PRESSURE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_plant_id(text: str) -> str | None:
    """Extract plant, equipment, or asset ID."""
    for pattern in PLANT_ID_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None