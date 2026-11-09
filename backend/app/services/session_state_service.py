"""Session state management service — tracks pending offers, slot filling, and distress cooldowns (T13)."""

import json
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Affirmative tokens for pending offer resolution
AFFIRMATIVE_REGEX = re.compile(
    r"^\s*(yes|yeah|yep|sure|ok|okay|k|haan|ha|avunu|sare|definitely|please\s+do|please|walk\s+me\s+through|tell\s+me|proceed)[!.,\s]*$",
    re.IGNORECASE,
)

# In-memory session state fallback dictionary
_IN_MEMORY_SESSION_STATE: dict[str, dict[str, Any]] = {}


def _default_session_state() -> dict[str, Any]:
    return {
        "pending_offer": None,           # {"type": str, "topic": str, "program": str, "text": str, "age": int}
        "offered_topics": [],            # list of topic names already offered
        "completed_topics": [],          # list of topic names completed
        "distress_cooldown_turns": 0,    # turns remaining in post-distress cooldown
        "last_openers": [],              # list of first-5-words openers used
        "told_claims": [],               # list of highlight IDs already presented
        "slots": {},                     # {"exam_board": str, "program": str, "category": str}
    }


async def get_session_state(session_id: str, redis_client=None) -> dict[str, Any]:
    """Retrieve the current session state object."""
    if not session_id:
        return _default_session_state()

    state = _default_session_state()

    # In-memory layer
    if session_id in _IN_MEMORY_SESSION_STATE:
        state.update(_IN_MEMORY_SESSION_STATE[session_id])

    # Redis layer
    if redis_client:
        try:
            key = f"sru:session:{session_id}:state"
            raw = await redis_client.get(key)
            if raw:
                data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else str(raw))
                if isinstance(data, dict):
                    state.update(data)
        except Exception as exc:
            logger.warning("Failed to get session state from Redis: %s", exc)

    return state


async def update_session_state(session_id: str, updates: dict[str, Any], redis_client=None) -> dict[str, Any]:
    """Update fields in the session state object."""
    if not session_id:
        return _default_session_state()

    state = await get_session_state(session_id, redis_client=redis_client)
    state.update(updates)

    _IN_MEMORY_SESSION_STATE[session_id] = state

    if redis_client:
        try:
            key = f"sru:session:{session_id}:state"
            await redis_client.setex(key, 86400, json.dumps(state))
        except Exception as exc:
            logger.warning("Failed to save session state to Redis: %s", exc)

    return state


async def set_pending_offer(session_id: str, offer_type: str, topic: str, program: str = "", text: str = "", redis_client=None) -> None:
    """Store a pending offer that can be accepted with a short affirmative ('yes')."""
    state = await get_session_state(session_id, redis_client=redis_client)
    offer = {
        "type": offer_type,
        "topic": topic,
        "program": program,
        "text": text,
        "age": 0,
    }
    offered = list(state.get("offered_topics", []))
    if topic and topic not in offered:
        offered.append(topic)

    await update_session_state(
        session_id,
        {"pending_offer": offer, "offered_topics": offered},
        redis_client=redis_client,
    )


async def resolve_pending_offer_if_affirmative(
    session_id: str,
    message: str,
    redis_client=None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Check if message is an affirmative accepting a pending offer.
    
    Returns:
        (is_resolved, resolved_query_text, offer_dict)
    """
    if not session_id or not message:
        return False, None, None

    clean_msg = message.strip()
    is_affirmative = bool(AFFIRMATIVE_REGEX.match(clean_msg))

    state = await get_session_state(session_id, redis_client=redis_client)
    pending = state.get("pending_offer")

    if not pending:
        return False, None, None

    # Check age of pending offer; clear after 2 unrelated turns
    if pending.get("age", 0) > 2:
        await update_session_state(session_id, {"pending_offer": None}, redis_client=redis_client)
        return False, None, None

    if is_affirmative:
        topic = pending.get("topic", "application")
        prog = pending.get("program", "")
        # Resolve to explicit sub-question text
        if "application" in topic or "apply" in topic or pending.get("type") == "application_steps":
            resolved_text = f"Please walk me through the step-by-step application process for {prog or 'B.Tech'} at SR University."
        elif "hostel" in topic:
            resolved_text = f"Tell me about the hostel options and accommodation facilities for {prog or 'students'} at SR University."
        elif "scholarship" in topic:
            resolved_text = f"What are the scholarship slabs and fee waivers for {prog or 'B.Tech'}?"
        else:
            resolved_text = pending.get("text") or f"Tell me more about {topic} at SR University."

        # Mark topic as completed and clear pending offer
        completed = list(state.get("completed_topics", []))
        if topic not in completed:
            completed.append(topic)

        await update_session_state(
            session_id,
            {"pending_offer": None, "completed_topics": completed},
            redis_client=redis_client,
        )
        return True, resolved_text, pending

    # Not an affirmative; increment age
    pending["age"] = pending.get("age", 0) + 1
    await update_session_state(session_id, {"pending_offer": pending}, redis_client=redis_client)
    return False, None, None


async def trigger_distress_cooldown(session_id: str, turns: int = 3, redis_client=None) -> None:
    """Set post-distress cooldown turns."""
    await update_session_state(session_id, {"distress_cooldown_turns": turns}, redis_client=redis_client)


async def step_distress_cooldown(session_id: str, redis_client=None) -> int:
    """Check and decrement distress cooldown. Returns remaining cooldown turns."""
    state = await get_session_state(session_id, redis_client=redis_client)
    current = state.get("distress_cooldown_turns", 0)
    if current > 0:
        new_val = current - 1
        await update_session_state(session_id, {"distress_cooldown_turns": new_val}, redis_client=redis_client)
        return current  # was in cooldown for this turn
    return 0


async def is_in_distress_cooldown(session_id: str, redis_client=None) -> bool:
    """Check if session is currently under distress cooldown."""
    state = await get_session_state(session_id, redis_client=redis_client)
    return state.get("distress_cooldown_turns", 0) > 0


def extract_opener_pattern(text: str) -> str:
    """Extract normalized first five words from a message."""
    words = re.findall(r"\w+", text.lower())
    return " ".join(words[:5]) if words else ""


async def record_opener(session_id: str, reply_text: str, redis_client=None) -> None:
    """Record the opener pattern of a response to avoid repetitive greetings."""
    if not session_id or not reply_text:
        return
    pattern = extract_opener_pattern(reply_text)
    if not pattern:
        return

    state = await get_session_state(session_id, redis_client=redis_client)
    openers = list(state.get("last_openers", []))
    openers.append(pattern)
    if len(openers) > 6:
        openers = openers[-6:]

    await update_session_state(session_id, {"last_openers": openers}, redis_client=redis_client)


async def get_recent_openers(session_id: str, redis_client=None) -> list[str]:
    """Retrieve recent opener patterns for this session."""
    state = await get_session_state(session_id, redis_client=redis_client)
    return list(state.get("last_openers", []))


def is_opener_repeating(reply_text: str, recent_openers: list[str]) -> bool:
    """Check if the first five words repeat any of the last two openers."""
    if not recent_openers:
        return False
    current = extract_opener_pattern(reply_text)
    if not current:
        return False
    # Check against the last two openers
    return current in recent_openers[-2:]


async def record_told_claims(session_id: str, highlight_ids: list[str], redis_client=None) -> None:
    """Record highlight IDs presented to the student to ensure variety."""
    if not session_id or not highlight_ids:
        return
    state = await get_session_state(session_id, redis_client=redis_client)
    told = list(state.get("told_claims", []))
    for hid in highlight_ids:
        if hid and hid not in told:
            told.append(hid)
    await update_session_state(session_id, {"told_claims": told}, redis_client=redis_client)


async def get_told_claims(session_id: str, redis_client=None) -> set[str]:
    """Retrieve all highlight IDs presented so far in this session."""
    state = await get_session_state(session_id, redis_client=redis_client)
    return set(state.get("told_claims", []))

