"""Runtime hallucination detection and response verification service."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Patterns for extracting numeric claims: percentages, scores, currency
PERCENT_PATTERN = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\s*%", re.I)
SCORE_FRACTION_PATTERN = re.compile(r"\b(\d{2,4})\s*(?:out\s+of|/)\s*(\d{2,4})\b", re.I)


def verify_numeric_faithfulness(
    answer: str,
    evidence_text: str,
    conversation_context: str,
    question: str,
) -> tuple[bool, list[str]]:
    """Check if percentage and score numbers in the answer are grounded in evidence or user context.

    Returns (is_faithful, list_of_unsupported_numbers).
    """
    answer_percents = {m.group(0).lower().replace(" ", "") for m in PERCENT_PATTERN.finditer(answer)}
    if not answer_percents:
        return True, []

    # Combined allowed corpus: evidence + conversation context + user's question
    allowed_corpus = (evidence_text + " " + conversation_context + " " + question).lower().replace(" ", "")

    unsupported = []
    for pct in answer_percents:
        raw_num = pct.replace("%", "").strip()
        # Check if the percentage or raw number exists in the allowed corpus
        if pct not in allowed_corpus and raw_num not in allowed_corpus:
            unsupported.append(pct)

    if unsupported:
        logger.warning(
            "Runtime guardrail detected unsupported numeric claims: %s", unsupported
        )
        return False, unsupported

    return True, []


def verify_retrieval_confidence(
    retrieved_chunks: list[dict[str, Any]],
    confidence_threshold: float = 0.5,
) -> bool:
    """Check if at least one chunk has strong semantic similarity to the query.

    ChromaDB cosine distance: lower is closer (0.0 = identical, 1.0 = orthogonal).
    Returns True if confidence is sufficient, False otherwise.
    """
    if not retrieved_chunks:
        return False

    distances = [
        c["distance"] for c in retrieved_chunks if c.get("distance") is not None
    ]
    if not distances:
        # Distance metric not available, default to accepting retrieved documents
        return True

    best_distance = min(distances)
    return best_distance <= confidence_threshold


URL_PATTERN = re.compile(
    r"(?:https?://[^\s)\]]+|portal\.[a-z0-9.-]+|(?:www\.)?[a-z0-9-]+\.(?:edu|edu\.in|com|org)/[^\s)\]]*)",
    re.I,
)


def verify_url_faithfulness(
    answer: str,
    evidence_text: str,
) -> tuple[bool, list[str]]:
    """Check if URLs or portal mentions in the answer are grounded in the evidence.

    Returns (is_faithful, list_of_unsupported_urls).
    """
    found_urls = [m.group(0).rstrip(".,;!?:") for m in URL_PATTERN.finditer(answer)]
    if not found_urls:
        return True, []

    evidence_lower = evidence_text.lower()
    unsupported = [
        url for url in found_urls if url.lower() not in evidence_lower
    ]
    return len(unsupported) == 0, unsupported


def sanitize_hallucinated_urls(answer: str, unsupported_urls: list[str]) -> str:
    """Replace unsupported portal links and fabricated URLs with offline contact instructions."""
    sanitized = answer
    for url in unsupported_urls:
        sanitized = re.sub(
            re.escape(url),
            "the academic coordinator or admissions office",
            sanitized,
            flags=re.I,
        )
    # Also clean up phrases like "visit portal.university.edu" or "login at..."
    sanitized = re.sub(r"\blogin (?:at|to) (?:the )?", "contact the ", sanitized, flags=re.I)
    sanitized = re.sub(r"\bvisit (?:at|to) (?:the )?", "contact the ", sanitized, flags=re.I)
    return sanitized


# Forbidden outcome-implying and admission-guaranteeing phrases (T13)
FORBIDDEN_OUTCOME_PATTERNS = [
    re.compile(r"\b(you're\s+in\s+a\s+great\s+spot|you\s+are\s+in\s+a\s+great\s+spot)\b", re.I),
    re.compile(r"\b(you've\s+got\s+this|you\s+have\s+got\s+this)\b", re.I),
    re.compile(r"\b(you\s+will\s+(easily\s+)?get\s+admission|admission\s+is\s+guaranteed)\b", re.I),
    re.compile(r"\b(guaranteed\s+(seat|admission|placement|job))\b", re.I),
    re.compile(r"\b(your\s+seat\s+is\s+confirmed|sure\s+shot\s+admission)\b", re.I),
]


def verify_outcome_language(text: str) -> tuple[bool, list[str]]:
    """Verify that reply contains zero outcome-implying or admission-guaranteeing language (T13)."""
    detected = []
    for pattern in FORBIDDEN_OUTCOME_PATTERNS:
        match = pattern.search(text)
        if match:
            detected.append(match.group(0))
    if detected:
        logger.warning("Guardrail blocked forbidden outcome language: %s", detected)
        return False, detected
    return True, []


