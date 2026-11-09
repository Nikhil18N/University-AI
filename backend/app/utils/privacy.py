"""Privacy utilities for DPDP compliance: masking PII (phones, emails) in logs and evaluation records."""

import re


EMAIL_REGEX = re.compile(
    r"\b([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b",
    re.IGNORECASE,
)

# Matches 10-digit Indian mobile numbers with optional country code (+91, 91, 0) and separators
PHONE_REGEX = re.compile(
    r"(?:\+?91[\s-]?)?(?:0)?([6-9]\d{4})[\s-]?(\d{5})\b"
)


def mask_email(text: str) -> str:
    """Mask email addresses, replacing local part with first letter and asterisks.

    Example: 'student.name@sru.edu.in' -> 's***@sru.edu.in'
    """
    if not text:
        return text

    def _replace_email(match: re.Match) -> str:
        local_part = match.group(1)
        domain = match.group(2)
        if len(local_part) <= 1:
            masked_local = f"{local_part}***"
        else:
            masked_local = f"{local_part[0]}***"
        return f"{masked_local}@{domain}"

    return EMAIL_REGEX.sub(_replace_email, text)


def mask_phone(text: str) -> str:
    """Mask phone numbers, keeping prefix and obscuring the last 5 digits.

    Example: '9876543210' -> '98765*****'
             '+91 9876543210' -> '+91 98765*****'
             '+91-98765-43210' -> '+91-98765-*****'
    """
    if not text:
        return text

    def _replace_phone(match: re.Match) -> str:
        full_match = match.group(0)
        prefix_digits = match.group(1)  # first 5 digits of mobile
        # Retain everything up to the second group and mask the 5 digits with asterisks
        idx = full_match.rfind(match.group(2))
        if idx != -1:
            return full_match[:idx] + "*****"
        return f"{prefix_digits}*****"

    return PHONE_REGEX.sub(_replace_phone, text)


def mask_pii(text: str) -> str:
    """Mask both emails and phone numbers in any text."""
    if not text:
        return text
    return mask_phone(mask_email(text))
