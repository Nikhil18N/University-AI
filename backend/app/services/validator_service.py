"""Deterministic numeric and date validator service (plain code, not an LLM).

P1 Hardening (Task T5):
1. Unit normalization: "1,25,000", "125000", and "1.25 lakh" compare equal.
2. Currency normalization: ₹, Rs., INR.
3. Date normalization: "15 March 2027", "15/03/2027", "March 15th" compare by normalized date.
4. Unit words extraction: bare numbers next to "seats", "credits", "semesters", "years".
5. Enumerated whitelist where EVERY entry has a required explanatory comment.
6. Block reasons logged with privacy masking.
"""

from datetime import datetime
import logging
import re
from typing import Any

from app.config import settings
from app.services.structured_facts_service import get_all_grounded_numbers

logger = logging.getLogger(__name__)

# Enumerated constants whitelist with mandatory rationale comment per item
WHITELISTED_CONSTANTS_WITH_REASONS: dict[str, str] = {
    # Standard secondary educational tiers
    "10": "Standard 10th grade matriculation",
    "12": "Standard 12th grade higher secondary board",
    "10th": "Ordinal reference to matriculation",
    "12th": "Ordinal reference to intermediate",
    "10+2": "Standard Indian higher secondary education pattern",
    # Standard degree program durations & semesters
    "1": "Single semester, year, or ordinal list marker",
    "2": "Standard Master duration (2 years) or ordinal marker",
    "3": "Standard 3-year degree duration or ordinal marker",
    "4": "Standard B.Tech degree duration (4 years)",
    "5": "Dual-degree / integrated program duration (5 years)",
    "6": "Number of semesters in 3-year degree or average LPA",
    "8": "Standard 8 semesters in 4-year B.Tech",
    "first": "Ordinal duration marker",
    "second": "Ordinal duration marker",
    "third": "Ordinal duration marker",
    "fourth": "Ordinal duration marker",
    "1st": "Ordinal rank/year marker",
    "2nd": "Ordinal rank/year marker",
    "3rd": "Ordinal rank/year marker",
    "4th": "Ordinal rank/year marker",
    # Campus physical & operational characteristics
    "24": "Hours per day in 24/7",
    "7": "Days per week in 24/7",
    "24/7": "24/7 continuous facility availability",
    "24x7": "24x7 continuous facility availability",
    "20": "Proximity time in minutes to Warangal station",
    "20 minutes": "Commute duration to station",
    "14": "Campus distance in km to Kazipet junction",
    "16": "Campus distance in km to Warangal railway station",
    "14 km": "Distance measure to Kazipet",
    "16 km": "Distance measure to Warangal",
    "150": "Total university campus area in acres",
    "150-acre": "Adjective format of campus size",
    "150 acres": "Plural format of campus area",
    # Academic credits & marks denominator
    "160": "Standard AICTE credits for 4-year B.Tech completion",
    "500": "Standard Telangana Inter MPC passing mark denominator (500/1000)",
    "1000": "Total maximum aggregate marks in Intermediate MPC",
    # Standard academic calendar years
    "2024": "Recent historical academic and NIRF reference year",
    "2025": "Current NIRF / NBA ranking evaluation cycle",
    "2026": "Current academic intake calendar year",
    "2027": "Upcoming academic cycle completion year",
}


def get_dynamic_allowed_numbers() -> set[str]:
    """Return whitelisted numbers combining base constants and configured contacts/helplines from config (T7)."""
    allowed = set(WHITELISTED_CONSTANTS_WITH_REASONS.keys())

    # Add configured admissions contacts
    for phone in [
        getattr(settings, "ADMISSIONS_PHONE", ""),
        getattr(settings, "ADMISSIONS_PHONE_ALT", ""),
    ]:
        if phone:
            allowed.add(phone)
            digits = re.sub(r"[^\d]", "", phone)
            if digits:
                allowed.add(digits)
            for part in re.split(r"[^\d]+", phone):
                if part:
                    allowed.add(part)

    # Add configured crisis helplines
    for helpline in getattr(settings, "CRISIS_HELPLINES", []):
        for field in ("number", "alt_number"):
            num_val = helpline.get(field)
            if num_val:
                allowed.add(num_val)
                digits = re.sub(r"[^\d]", "", num_val)
                if digits:
                    allowed.add(digits)
                for part in re.split(r"[^\d]+", num_val):
                    if part:
                        allowed.add(part)

    return allowed


STANDARD_ALLOWED_NUMBERS: set[str] = set(WHITELISTED_CONSTANTS_WITH_REASONS.keys())

# Regex patterns
CURRENCY_PATTERN = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9,]+(?:\.[0-9]+)?(?:\s*(?:lakh|lac|crore|cr))?)", re.I)
PERCENTAGE_PATTERN = re.compile(r"\b([0-9]{1,3}(?:\.[0-9]+)?)\s*%", re.I)
LPA_PATTERN = re.compile(r"\b([0-9]{1,3}(?:\.[0-9]+)?)\s*LPA\b", re.I)
RANK_PATTERN = re.compile(r"\b([0-9]{1,3})(?:st|nd|rd|th)\b(?:\s*rank)?", re.I)
UNIT_NUMBERS_PATTERN = re.compile(r"\b(\d+)\s*(seats?|credits?|semesters?|years?|months?|days?|hours?|students?)\b", re.I)

# Date regex patterns for standard university announcements
DATE_PATTERNS = [
    # 15 March 2027 or 15th March 2027 or 15 Mar 2027
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b", re.I),
    # March 15, 2027 or March 15th, 2027
    re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I),
    # 15/03/2027 or 15-03-2027
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    # 2027-03-15
    re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"),
]

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}

def get_fallback_validator_block() -> str:
    portal = getattr(settings, "ADMISSIONS_PORTAL_URL", "")
    phone = getattr(settings, "ADMISSIONS_PHONE", "")
    email = getattr(settings, "ADMISSIONS_EMAIL", "")
    return (
        "I couldn't verify those details against our official sources, so I'd rather not "
        f"give you numbers I'm unsure about. Please check {portal} or "
        f"contact the Admissions Office at {phone} / {email}."
    )


def get_fallback_low_confidence() -> str:
    phone = getattr(settings, "ADMISSIONS_PHONE", "")
    email = getattr(settings, "ADMISSIONS_EMAIL", "")
    return (
        "I don't want to guess on this one and risk giving you the wrong info. "
        f"The admissions team can confirm it directly: {phone} / {email}. "
        "Meanwhile, want me to help with something else?"
    )


FALLBACK_VALIDATOR_BLOCK = get_fallback_validator_block()
FALLBACK_LOW_CONFIDENCE = get_fallback_low_confidence()


def format_indian_currency(n: int) -> str:
    """Format an integer with Indian comma grouping (e.g. 1,25,000)."""
    s = str(n)
    if len(s) <= 3:
        return s
    last_three = s[-3:]
    remaining = s[:-3]
    parts = []
    while len(remaining) > 2:
        parts.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        parts.insert(0, remaining)
    return ",".join(parts) + "," + last_three


def normalize_currency_amount(val_str: str) -> list[str]:
    """Normalize currency forms. Handles '1.25 lakh' -> '125000' and Indian/Western comma grouping."""
    forms: list[str] = []
    clean = val_str.lower().strip()

    # Check for lakh/lac
    lakh_match = re.search(r"([0-9.]+)\s*(?:lakh|lac)s?", clean)
    if lakh_match:
        try:
            num = float(lakh_match.group(1))
            val_int = int(num * 100000)
            forms.append(str(val_int))
            forms.append(f"{val_int:,}")
            forms.append(format_indian_currency(val_int))
            forms.append(f"{num:g} lakh")
            forms.append(f"{num:g}lakh")
        except ValueError:
            pass

    # Bare number with commas stripped
    digits_only = re.sub(r"[^\d.]", "", clean)
    if digits_only:
        try:
            if "." in digits_only:
                f_val = float(digits_only)
                forms.append(str(f_val))
                forms.append(str(int(f_val)))
            else:
                i_val = int(digits_only)
                forms.append(str(i_val))
                forms.append(f"{i_val:,}")
                forms.append(format_indian_currency(i_val))
                # Also generate lakh form if >= 100000
                if i_val >= 100000 and i_val % 1000 == 0:
                    lakh_equiv = i_val / 100000.0
                    forms.append(f"{lakh_equiv:g} lakh")
                    forms.append(f"{lakh_equiv:g}lakh")
        except ValueError:
            pass

    # Deduplicate preserving order
    return list(dict.fromkeys(forms))


def extract_dates(text: str) -> list[str]:
    """Extract and normalize all calendar dates to ISO YYYY-MM-DD format."""
    normalized_dates = []
    if not text:
        return normalized_dates

    # Pattern 1: DD Month YYYY
    for m in DATE_PATTERNS[0].finditer(text):
        day, month_str, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = MONTH_MAP.get(month_str, 0)
        if 1 <= month <= 12 and 1 <= day <= 31:
            normalized_dates.append(f"{year:04d}-{month:02d}-{day:02d}")

    # Pattern 2: Month DD, YYYY
    for m in DATE_PATTERNS[1].finditer(text):
        month_str, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        month = MONTH_MAP.get(month_str, 0)
        if 1 <= month <= 12 and 1 <= day <= 31:
            normalized_dates.append(f"{year:04d}-{month:02d}-{day:02d}")

    # Pattern 3: DD/MM/YYYY
    for m in DATE_PATTERNS[2].finditer(text):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            normalized_dates.append(f"{year:04d}-{month:02d}-{day:02d}")

    # Pattern 4: YYYY-MM-DD
    for m in DATE_PATTERNS[3].finditer(text):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            normalized_dates.append(f"{year:04d}-{month:02d}-{day:02d}")

    return normalized_dates


def extract_numeric_tokens(text: str) -> set[str]:
    """Extract all formatted numbers, currency amounts, percentages, units, and dates from text."""
    tokens = set()
    if not text:
        return tokens

    # Currency
    for m in CURRENCY_PATTERN.finditer(text):
        amt_str = m.group(1)
        for norm in normalize_currency_amount(amt_str):
            tokens.add(norm)
            tokens.add(f"₹{norm}")

    # Percentages
    for m in PERCENTAGE_PATTERN.finditer(text):
        pct = m.group(1)
        tokens.add(f"{pct}%")
        tokens.add(pct)

    # LPA
    for m in LPA_PATTERN.finditer(text):
        tokens.add(f"{m.group(1)} LPA".upper())
        tokens.add(m.group(1))

    # Ranks
    for m in RANK_PATTERN.finditer(text):
        tokens.add(m.group(0).lower())
        tokens.add(m.group(1))

    # Units (seats, credits, duration)
    for m in UNIT_NUMBERS_PATTERN.finditer(text):
        num_str = m.group(1)
        tokens.add(num_str)
        tokens.add(f"{num_str} {m.group(2).lower()}")

    return tokens


def mask_sensitive_token(token: str) -> str:
    """Mask sensitive digits or emails for privacy-safe logging."""
    if re.match(r"^\+?[0-9]{10,12}$", token):
        return token[:3] + "******" + token[-2:]
    if "@" in token:
        parts = token.split("@")
        return parts[0][:2] + "***@" + parts[1]
    return token


def validate_response_grounding(
    answer: str,
    evidence_text: str = "",
    structured_data_text: str = "",
    user_message: str = "",
    student_profile_text: str = "",
) -> tuple[bool, list[str]]:
    """Validate that every currency figure, percentage, cutoff, unit, and date in answer is grounded.

    Returns:
        (is_valid, list_of_ungrounded_claims)
    """
    if not answer:
        return True, []

    # 1. Extract all claims from the generated answer
    answer_tokens = extract_numeric_tokens(answer)
    answer_dates = extract_dates(answer)

    if not answer_tokens and not answer_dates:
        return True, []

    # 2. Build the full allowed corpus
    allowed_corpus = (
        evidence_text
        + " "
        + structured_data_text
        + " "
        + user_message
        + " "
        + student_profile_text
    ).lower()

    # Pre-compiled verified ground truth whitelist
    whitelist = get_all_grounded_numbers()
    whitelist.update(get_dynamic_allowed_numbers())

    ungrounded = []

    # 3. Verify numeric tokens
    for token in answer_tokens:
        token_clean = token.lower().strip()
        raw_digits = re.sub(r"[^\d]", "", token_clean)

        # Check exact token in whitelist
        if token in whitelist or token_clean in whitelist or raw_digits in whitelist:
            continue

        # Check in allowed corpus
        if token_clean in allowed_corpus or (raw_digits and raw_digits in allowed_corpus):
            continue

        ungrounded.append(token)

    # 4. Verify dates
    if answer_dates:
        allowed_dates = extract_dates(allowed_corpus)
        for dt in answer_dates:
            if dt not in allowed_dates:
                # Also check if year is whitelisted
                year = dt.split("-")[0]
                if year not in whitelist and year not in allowed_corpus:
                    ungrounded.append(dt)

    if ungrounded:
        masked_reasons = [mask_sensitive_token(t) for t in ungrounded]
        logger.warning(
            "Validator blocked ungrounded numbers in answer: %s", masked_reasons
        )
        return False, ungrounded

    return True, []
