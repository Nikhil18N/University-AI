"""Deterministic intent classification and disambiguation for SRU Buddy."""

import re
from typing import Literal

AgentIntent = Literal[
    "DATE_QUERY",
    "CONFUSION_QUERY",
    "DATE_CONFIRMATION_YES",
    "DATE_CONFIRMATION_NO",
    "CAMPUS_VISIT_BOOKING_WITH_DATE",
    "CAMPUS_VISIT_BOOKING",
    "CAMPUS_VISIT_INFO",
    "GENERAL",
]

_DATE_QUERY_PATTERN = re.compile(
    r"^\s*(what\s+is\s+today'?s\s+date|what'?s\s+today'?s\s+date|what\s+date\s+is\s+today|"
    r"today'?s\s+date|tell\s+me\s+today'?s\s+date|current\s+date|"
    r"what\s+is\s+the\s+date\s+today|what\s+date\s+is\s+it|what\s+day\s+is\s+it\s+today)[?!.,\s]*$",
    re.IGNORECASE,
)

_CONFUSION_PATTERN = re.compile(
    r"^\s*(what\s+are\s+you\s+talking\s+about|what\s+are\s+u\s+talking\s+about|"
    r"what\s+do\s+you\s+mean|what\s+does\s+that\s+mean|"
    r"i\s+didn'?t\s+(ask|say|mention)\s+that|i\s+never\s+(asked|said|mentioned)\s+that|"
    r"huh|what\s+is\s+this|what\s+are\s+you\s+saying)[?!.,\s]*$",
    re.IGNORECASE,
)

_YES_CONFIRM_PATTERN = re.compile(
    r"^\s*(yes|yeah|yep|yup|yes\s+please|correct|sure|right|that'?s\s+right|ok|okay|confirm)[.!?\s]*$",
    re.IGNORECASE,
)

_NO_CONFIRM_PATTERN = re.compile(
    r"^\s*(no|nope|nah|not\s+that|wrong|different\s+date|cancel|neither)[.!?\s]*$",
    re.IGNORECASE,
)

# Explicit booking phrases (actions to book, schedule, or reserve a visit)
_EXPLICIT_BOOKING_PHRASES = (
    "book campus tour", "schedule campus visit", "how can i book a campus tour",
    "book a campus tour", "schedule visit", "book a visit", "book a tour",
    "schedule a tour", "schedule tour", "tour booking", "campus visit booking",
    "how to book a visit", "i want to book a visit", "i want to schedule a visit",
    "register for campus visit", "reserve a slot", "book my visit",
)

# Date mention in the context of visiting
_VISIT_WITH_DATE_PATTERN = re.compile(
    r"\b(visit\s+(on|at|for)|visit\s+this|visit\s+next|visit\s+tomorrow|visit\s+today|"
    r"come\s+(on|at|for)|coming\s+(on|at|for)|plan\s+to\s+visit\s+on|"
    r"want\s+to\s+visit\s+on|would\s+like\s+to\s+visit\s+on)\s+([a-zA-Z0-9\s/-]+)",
    re.IGNORECASE,
)

# General campus visit information inquiries
_VISIT_INFO_PATTERNS = (
    "campus visit", "visit campus", "visit sru", "visit the campus",
    "can i visit", "can we visit", "can parents visit", "visiting hours",
    "visiting timings", "visit timings", "visiting rules", "visiting guidelines",
    "what to see on campus", "campus walkthrough", "campus tour info",
    "how to visit sru", "how to visit the campus", "directions to campus",
)


def classify_agent_intent(message: str, state: dict | None = None) -> AgentIntent:
    """Classify user intent before triggering LLM or rich cards."""
    msg = (message or "").strip().lower()
    if not msg:
        return "GENERAL"

    state = state or {}

    # 1. Date query
    if _DATE_QUERY_PATTERN.match(msg):
        return "DATE_QUERY"

    # 2. Confusion query
    if _CONFUSION_PATTERN.match(msg):
        return "CONFUSION_QUERY"

    # 3. Active date confirmation in progress
    if state.get("awaiting_date_confirmation"):
        if _YES_CONFIRM_PATTERN.match(msg):
            return "DATE_CONFIRMATION_YES"
        if _NO_CONFIRM_PATTERN.match(msg):
            return "DATE_CONFIRMATION_NO"

    # 4. Check if message is asking to visit on a specific date
    # E.g. "I want to visit on 17th", "visit on tomorrow", "can I visit on next Monday"
    if _VISIT_WITH_DATE_PATTERN.search(msg) or any(k in msg for k in ("visit on", "visit tomorrow", "visit today")):
        return "CAMPUS_VISIT_BOOKING_WITH_DATE"

    # Also detect if the message is simply a date in response to a visit discussion
    if state.get("active_topic") == "campus_visit":
        from .tools import resolve_campus_visit_date
        res = resolve_campus_visit_date(msg)
        if res.get("date"):
            return "CAMPUS_VISIT_BOOKING_WITH_DATE"

    # 5. Explicit booking request (without a specific date yet)
    if any(phrase in msg for phrase in _EXPLICIT_BOOKING_PHRASES):
        return "CAMPUS_VISIT_BOOKING"

    # 6. General campus visit inquiry
    if any(pattern in msg for pattern in _VISIT_INFO_PATTERNS):
        return "CAMPUS_VISIT_INFO"

    return "GENERAL"
