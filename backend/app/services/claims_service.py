"""Claim-level grounding, verified highlight store, and known-gaps memory (T15)."""

import json
import logging
from pathlib import Path
import re
from typing import Any
import yaml

from app.config import settings

logger = logging.getLogger(__name__)

# Configurable facility and offering term whitelist for qualitative claim checks
FACILITY_TERMS = [
    "gym",
    "gymnasium",
    "cricket",
    "football",
    "basketball",
    "volleyball",
    "kabaddi",
    "badminton",
    "swimming",
    "tennis",
    "running track",
    "sports",
    "athletics",
    "wi-fi",
    "wifi",
    "hostel",
    "air conditioning",
    "ac hostel",
    "library",
    "modern labs",
    "laboratories",
    "specialized gear",
    "licensed software",
]

# Topic keywords for gap detection
TOPIC_GAP_PATTERNS = [
    (re.compile(r"\b(sports?|gym|athletics|cricket|football|games|playground)\b", re.I), "sports_facilities"),
    (re.compile(r"\b(international|foreign|nri)\b.*?\bhostels?\b|\bhostels?\b.*?\b(international|foreign|nri)\b", re.I), "international_hostel"),
    (re.compile(r"\b(dress\s*code|uniform)\b", re.I), "dress_code"),
    (re.compile(r"\b(transport|bus\s+routes?|bus\s+fee)\b", re.I), "transport_details"),
    (re.compile(r"\b(scholarship\s+slab|fee\s+concession)\b", re.I), "scholarship_slabs"),
]

# In-memory session gap fallback when Redis is unavailable
_IN_MEMORY_SESSION_GAPS: dict[str, set[str]] = {}


def load_verified_highlights() -> list[dict[str, Any]]:
    """Load verified highlights from backend/app/data/verified_highlights.yaml."""
    yaml_path = Path(__file__).resolve().parent.parent / "data" / "verified_highlights.yaml"
    if not yaml_path.exists():
        logger.warning("verified_highlights.yaml not found at %s", yaml_path)
        return []
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("highlights", [])
    except Exception as exc:
        logger.error("Failed to load verified_highlights.yaml: %s", exc)
        return []


def get_relevant_highlights(query: str, profile_interests: list[str] | None = None, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieve verified highlights matching query keywords or student interests."""
    all_highlights = load_verified_highlights()
    if not all_highlights:
        return []

    query_lower = query.lower()
    interests_lower = [i.lower() for i in (profile_interests or [])]

    scored = []
    for h in all_highlights:
        score = 0
        tags = [t.lower() for t in h.get("tags", [])]
        text_lower = h.get("short_text", "").lower()

        # Match tags against query and interests
        for tag in tags:
            if tag in query_lower:
                score += 3
            for interest in interests_lower:
                if tag in interest or interest in tag:
                    score += 4

        # Word overlaps
        for word in re.findall(r"\w+", query_lower):
            if len(word) > 3 and word in text_lower:
                score += 1

        scored.append((score, h))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:limit]]


def format_highlights_for_prompt(highlights: list[dict[str, Any]]) -> str:
    """Format highlights with explicit IDs for model grounding."""
    lines = []
    for h in highlights:
        lines.append(f"[{h['id']}]: {h['short_text']} (Source: {h.get('source_name', 'SRU')})")
    return "\n\n".join(lines)


def verify_persuasive_output(output_text: str, available_ids: list[str]) -> tuple[bool, str, list[str]]:
    """Validate that persuasive output cites only highlight IDs that exist in the available set.
    
    Returns (is_valid, reply_text, used_ids).
    """
    clean_text = output_text.strip()

    # Case 1: Structured JSON output
    # Handle possible markdown json codeblock
    if "```json" in clean_text:
        match = re.search(r"```json\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
        if match:
            clean_text = match.group(1).strip()
    elif clean_text.startswith("```") and clean_text.endswith("```"):
        clean_text = clean_text.strip("`").strip()

    try:
        data = json.loads(clean_text)
        if isinstance(data, dict) and "reply_text" in data:
            reply_text = str(data["reply_text"]).strip()
            used_ids = data.get("used_highlight_ids", [])
            if not isinstance(used_ids, list):
                used_ids = []

            # Verify every used ID is in available_ids
            unsupported_ids = [uid for uid in used_ids if uid not in available_ids]
            if unsupported_ids:
                logger.warning("Persuasive output claimed unsupported highlight IDs: %s (available: %s)", unsupported_ids, available_ids)
                return False, reply_text, used_ids
            return True, reply_text, used_ids
    except (json.JSONDecodeError, ValueError):
        pass

    # Case 2: Plain text output — check for any hallucinatory ID tags or unsupported claims
    # If the model didn't return valid JSON, check if it directly contains any illegal highlight IDs
    found_ids = re.findall(r"\bHL_[A-Z0-9_]+\b", output_text)
    invalid_found = [fid for fid in found_ids if fid not in available_ids]
    if invalid_found:
        return False, output_text, invalid_found

    return True, output_text, []


def verify_qualitative_claims(reply_text: str, context_text: str) -> tuple[bool, list[str]]:
    """Deterministic check: extract facility and offering terms and require each to appear in context."""
    reply_lower = reply_text.lower()
    context_lower = context_text.lower()

    unsupported = []
    for term in FACILITY_TERMS:
        # Check if term is present in reply
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, reply_lower):
            # Must appear in context
            if term not in context_lower:
                # Check root variants for common pluralizations
                singular = term[:-1] if term.endswith("s") and len(term) > 4 else term
                if singular not in context_lower:
                    unsupported.append(term)

    if unsupported:
        logger.warning("Qualitative claim check failed. Reply mentioned unsupported terms: %s", unsupported)
        return False, unsupported

    return True, []


async def record_known_gap(session_id: str, topic_key: str, redis_client=None) -> None:
    """Store a known information gap for the session."""
    if not session_id or not topic_key:
        return

    _IN_MEMORY_SESSION_GAPS.setdefault(session_id, set()).add(topic_key)

    if redis_client:
        try:
            redis_key = f"sru:session:{session_id}:known_gaps"
            await redis_client.sadd(redis_key, topic_key)
            await redis_client.expire(redis_key, 86400)
        except Exception as exc:
            logger.warning("Failed to record known gap in Redis: %s", exc)


async def get_known_gaps(session_id: str, redis_client=None) -> set[str]:
    """Retrieve known gaps recorded for this session."""
    gaps = set(_IN_MEMORY_SESSION_GAPS.get(session_id, set()))

    if redis_client:
        try:
            redis_key = f"sru:session:{session_id}:known_gaps"
            stored = await redis_client.smembers(redis_key)
            if stored:
                for item in stored:
                    gaps.add(item.decode("utf-8") if isinstance(item, bytes) else str(item))
        except Exception as exc:
            logger.warning("Failed to retrieve known gaps from Redis: %s", exc)

    return gaps


def detect_topic_gap_from_response(user_message: str, response_text: str) -> str | None:
    """Detect if response admitted a knowledge gap on a specific topic."""
    resp_lower = response_text.lower()
    admit_gap_phrases = [
        "notes do not list",
        "notes don't list",
        "can't confirm",
        "cannot confirm",
        "don't have that detail",
        "do not have that detail",
        "no verified information",
        "check with the admissions office",
        "contact the admissions office",
    ]

    if any(phrase in resp_lower for phrase in admit_gap_phrases):
        combined = f"{user_message} {response_text}"
        for pattern, topic_key in TOPIC_GAP_PATTERNS:
            if pattern.search(combined):
                return topic_key
        return "general_gap"

    return None


def get_turn_fallback(reason: str = "general") -> str:
    """Return a specific, appropriate fallback text based on failure reason."""
    portal = getattr(settings, "ADMISSIONS_PORTAL_URL", "https://sru.edu.in")
    phone = getattr(settings, "ADMISSIONS_PHONE", "0870-2818333")
    email = getattr(settings, "ADMISSIONS_EMAIL", "info@sru.edu.in")

    if reason == "ungrounded_number":
        return (
            "I couldn't verify those details against our official sources, so I'd rather not "
            f"give you numbers I'm unsure about. Please check {portal} or "
            f"contact the Admissions Office at {phone} / {email}."
        )
    elif reason in ("unsupported_claim", "unverified_facility", "known_gap"):
        return (
            "I don't have verified notes on those specific facilities or details in my current materials, "
            f"and I'd rather not guess. Please check {portal} or reach out to Admissions at {phone} / {email}."
        )
    else:
        return (
            "I don't have that detail verified in my current records right now. "
            f"The admissions team can confirm it directly: {phone} / {email}."
        )
