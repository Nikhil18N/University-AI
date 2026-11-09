"""Deterministic numeric and date validator service (plain code, not an LLM)."""

import logging
import re
from typing import Any

from app.services.structured_facts_service import get_all_grounded_numbers

logger = logging.getLogger(__name__)

# Common universal allowed numbers (standard grades, durations, hours)
STANDARD_ALLOWED_NUMBERS: set[str] = {
    # Educational standards
    "10", "12", "10th", "12th", "10+2", "160", "4", "8", "1", "2", "3", "5",
    "4 years", "8 semesters", "first", "second", "third", "fourth",
    "1st", "2nd", "3rd", "4th",
    # Operational constants
    "24", "7", "24/7", "24x7", "20", "20 minutes", "14", "16", "14 km", "16 km",
    "150", "150-acre", "150 acres", "1000", "500",
    # Standard phone extensions
    "0870", "2818333", "2818311", "1800", "599", "0019",
}

# Regex patterns for numeric claims
CURRENCY_PATTERN = re.compile(r"₹\s*([0-9,]+(?:\.[0-9]+)?)", re.I)
PERCENTAGE_PATTERN = re.compile(r"\b([0-9]{1,3}(?:\.[0-9]+)?)\s*%", re.I)
LPA_PATTERN = re.compile(r"\b([0-9]{1,3}(?:\.[0-9]+)?)\s*LPA\b", re.I)
RANK_PATTERN = re.compile(r"\b([0-9]{1,3})(?:st|nd|rd|th)\b", re.I)
GENERAL_NUMBER_PATTERN = re.compile(r"\b([0-9]{2,7})\b")

FALLBACK_VALIDATOR_BLOCK = (
    "I couldn't verify those details against our official sources, so I'd rather not "
    "give you numbers I'm unsure about. Please check https://apply.sru.edu.in or "
    "contact the Admissions Office at 0870-2818333 / info@sru.edu.in."
)

FALLBACK_LOW_CONFIDENCE = (
    "I don't want to guess on this one and risk giving you the wrong info. "
    "The admissions team can confirm it directly: 0870-2818333 / info@sru.edu.in. "
    "Meanwhile, want me to help with something else?"
)


def extract_numeric_tokens(text: str) -> set[str]:
    """Extract all formatted numbers, currency amounts, percentages, and ranks from text."""
    tokens = set()
    if not text:
        return tokens

    # Currency
    for m in CURRENCY_PATTERN.finditer(text):
        tokens.add(m.group(0).replace(" ", ""))
        tokens.add(m.group(1).replace(",", ""))

    # Percentages
    for m in PERCENTAGE_PATTERN.finditer(text):
        tokens.add(f"{m.group(1)}%")
        tokens.add(m.group(1))

    # LPA
    for m in LPA_PATTERN.finditer(text):
        tokens.add(f"{m.group(1)} LPA".upper())
        tokens.add(m.group(1))

    # Ranks
    for m in RANK_PATTERN.finditer(text):
        tokens.add(m.group(0).lower())
        tokens.add(m.group(1))

    return tokens


def validate_response_grounding(
    answer: str,
    evidence_text: str = "",
    structured_data_text: str = "",
    user_message: str = "",
    student_profile_text: str = "",
) -> tuple[bool, list[str]]:
    """Validate that every currency figure, percentage, cutoff, and package in answer is grounded.

    Returns:
        (is_valid, list_of_ungrounded_claims)
    """
    if not answer:
        return True, []

    # Extract all claims from the generated answer
    answer_tokens = extract_numeric_tokens(answer)
    if not answer_tokens:
        return True, []

    # Build the full allowed corpus
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
    whitelist.update(STANDARD_ALLOWED_NUMBERS)

    ungrounded = []
    for token in answer_tokens:
        token_clean = token.lower().strip()
        raw_digits = re.sub(r"[^\d]", "", token_clean)

        # 1. Check exact token in whitelist
        if token in whitelist or token_clean in whitelist or raw_digits in whitelist:
            continue

        # 2. Check if token or raw number appears in allowed corpus
        if token_clean in allowed_corpus or (raw_digits and raw_digits in allowed_corpus):
            continue

        ungrounded.append(token)

    if ungrounded:
        logger.warning(
            "Validator blocked ungrounded numbers in answer: %s", ungrounded
        )
        return False, ungrounded

    return True, []
