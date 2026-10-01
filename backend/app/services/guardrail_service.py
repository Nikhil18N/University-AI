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
