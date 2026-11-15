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
    r"(?:https?://[^\s)\]]+|portal\.[a-z0-9.-]+\.[a-z]{2,}|(?:www\.)?[a-z0-9-]+\.(?:edu|edu\.in|ac\.in|com|org)(?:/[^\s)\]]*)?)",
    re.I,
)

OFFICIAL_ALLOWED_DOMAINS = ("sru.edu.in", "apply.sru.edu.in", "wa.me", "maps.google.com")


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
    unsupported = []
    for url in found_urls:
        url_lower = url.lower()
        if any(domain in url_lower for domain in OFFICIAL_ALLOWED_DOMAINS):
            continue
        if url_lower not in evidence_lower:
            unsupported.append(url)

    return len(unsupported) == 0, unsupported


def sanitize_hallucinated_urls(answer: str, unsupported_urls: list[str]) -> str:
    """Replace unsupported portal links and fabricated URLs with official admissions contact instructions."""
    sanitized = answer
    for url in unsupported_urls:
        # If preceded by at/via/on/visit/portal, replace gracefully
        prep_pattern = re.compile(rf"\b(?:at|on|via|through|visit|portal)\s+{re.escape(url)}", re.I)
        if prep_pattern.search(sanitized):
            sanitized = prep_pattern.sub("the Admissions Office (0870-2818333 / info@sru.edu.in)", sanitized)
        else:
            sanitized = re.sub(
                re.escape(url),
                "the Admissions Office (0870-2818333 / info@sru.edu.in)",
                sanitized,
                flags=re.I,
            )
    sanitized = re.sub(r"\blogin (?:at|to) (?:the )?", "contact the ", sanitized, flags=re.I)
    sanitized = re.sub(r"\bvisit (?:at|to) (?:the )?", "contact the ", sanitized, flags=re.I)
    return sanitized


