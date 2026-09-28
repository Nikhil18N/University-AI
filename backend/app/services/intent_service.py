"""Intent classification service — hybrid fast pattern matching + LLM classifier."""

import json
import logging
import re
from typing import Literal

from app.providers.base import LLMProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

IntentType = Literal[
    "GREETING",
    "GOODBYE",
    "THANKS",
    "HOW_ARE_YOU",
    "ACKNOWLEDGMENT",
    "HELP",
    "STUDENT_SPECIFIC",
    "UNIVERSITY",
    "GENERAL_CONVERSATION",
    "UNKNOWN",
]

# Fast regex patterns for instantaneous classification without LLM latency
FAST_PATTERNS: list[tuple[re.Pattern, IntentType]] = [
    (
        re.compile(r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)\b", re.IGNORECASE),
        "GREETING",
    ),
    (
        re.compile(r"^\s*(bye|goodbye|see\s+you|farewell|take\s+care|cya)\b", re.IGNORECASE),
        "GOODBYE",
    ),
    (
        re.compile(r"\b(thanks|thank\s+you|thx|much\s+appreciated|appreciate\s+it|many\s+thanks)\b", re.IGNORECASE),
        "THANKS",
    ),
    (
        re.compile(r"^\s*(how\s+are\s+you|how's\s+it\s+going|how\s+do\s+you\s+do|what's\s+up)\b", re.IGNORECASE),
        "HOW_ARE_YOU",
    ),
    (
        re.compile(
            r"^\s*(ok|okay|k|got\s+it|understood|cool|great|awesome|nice|alright|sure|fine|noted|perfect|yep|yeah|sounds\s+good)[.!?\s]*$",
            re.IGNORECASE,
        ),
        "ACKNOWLEDGMENT",
    ),
    (
        re.compile(r"^\s*(help|what\s+can\s+you\s+do|how\s+can\s+you\s+help|commands)\b", re.IGNORECASE),
        "HELP",
    ),
]

STUDENT_SPECIFIC_PATTERN = re.compile(
    r"\b(my\s+(attendance|grades?|gpa|marks|results?|timetable|schedule|fees?|dues?|application)|pay\s+my\s+fee)\b",
    re.IGNORECASE,
)

UNIVERSITY_KEYWORDS = {
    "exam", "exams", "examination", "examinations", "fee", "fees", "hostel", "hostels",
    "attendance", "semester", "semesters", "course", "courses", "syllabus", "department",
    "departments", "faculty", "scholarship", "scholarships", "transport", "bus", "library",
    "timetable", "result", "results", "grade", "grades", "marks", "regulation", "regulations",
    "calendar", "admission", "admissions", "registration", "register", "certificate",
    "convocation", "placement", "placements", "internship", "internships", "laboratory",
    "lab", "labs", "campus", "notice", "notices", "circular", "deadline", "deadlines",
    "university", "college", "curfew", "mess", "warden", "hall ticket", "admit card",
    "tuition", "refund", "re-evaluation", "penalty", "penalties", "late fee", "late registration",
    "fine", "fines", "due", "dues", "rule", "rules", "policy", "policies",
    "srix", "club", "clubs", "event", "events", "canteen", "cafeteria", "sports", "gym",
    "accommodation", "program", "programs", "btech", "mtech", "mba", "phd",
    "chancellor", "ranking", "rankings", "nirf", "accreditation", "eligibility",
}


def fast_classify(message: str) -> IntentType | None:
    """Check fast regex patterns and keyword indicators."""
    text = message.strip()

    # 1. Student-specific auth check takes precedence
    if STUDENT_SPECIFIC_PATTERN.search(text):
        return "STUDENT_SPECIFIC"

    # 2. University keyword check — even if query starts with a greeting
    #    (e.g., "Hi, how to apply for admission?")
    words = set(re.findall(r"\w+", text.lower()))
    if words & UNIVERSITY_KEYWORDS:
        return "UNIVERSITY"

    # 3. Conversational patterns (pure greetings, thanks, goodbyes, acknowledgments, help)
    for pattern, intent in FAST_PATTERNS:
        if pattern.search(text):
            return intent

    return None


async def classify_intent(
    message: str,
    conversation_context: str = "",
    llm_provider: LLMProvider | None = None,
) -> tuple[IntentType, float]:
    """Classify the user query intent using fast filter with LLM fallback.

    Returns (intent, confidence).
    """
    # 1. Try fast classifier first (0ms latency)
    fast_result = fast_classify(message)
    if fast_result is not None:
        logger.debug("Fast classified '%s' as %s", message[:40], fast_result)
        return fast_result, 0.95

    # If no LLM provider provided, default to GENERAL_CONVERSATION
    if llm_provider is None:
        return "GENERAL_CONVERSATION", 0.5

    # 2. LLM classifier for nuanced or conversational queries
    try:
        prompt = render_prompt(
            "classifier",
            context=conversation_context or "No previous conversation.",
            message=message,
        )
        response = await llm_provider.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        # Parse JSON from response
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        intent = data.get("intent", "GENERAL_CONVERSATION").upper()
        confidence = float(data.get("confidence", 0.8))

        valid_intents: set[IntentType] = {
            "GREETING",
            "GOODBYE",
            "THANKS",
            "HOW_ARE_YOU",
            "ACKNOWLEDGMENT",
            "HELP",
            "STUDENT_SPECIFIC",
            "UNIVERSITY",
            "GENERAL_CONVERSATION",
            "UNKNOWN",
        }
        if intent in valid_intents:
            return intent, confidence  # type: ignore

    except Exception as e:
        logger.warning("LLM classification failed for '%s': %s", message[:40], e)

    return "GENERAL_CONVERSATION", 0.5
