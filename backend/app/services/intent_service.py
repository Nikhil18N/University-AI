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
        re.compile(
            r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)(\s+(there|buddy|friend|assistant|bot|sru|all))?[!.,\s]*$",
            re.IGNORECASE,
        ),
        "GREETING",
    ),
    (
        re.compile(
            r"^\s*(bye|goodbye|see\s+you|farewell|take\s+care|cya)(\s+(later|bro|all|buddy|soon))?[.!?\s]*$",
            re.IGNORECASE,
        ),
        "GOODBYE",
    ),
    (
        re.compile(
            r"^\s*(thanks|thank\s+you|thx|much\s+appreciated|appreciate\s+it|many\s+thanks)(\s+(a\s+lot|so\s+much|bro|sir|buddy|assistant|bot))?[.!?\s]*$",
            re.IGNORECASE,
        ),
        "THANKS",
    ),
    (
        re.compile(r"^\s*(how\s+are\s+you|how's\s+it\s+going|how\s+do\s+you\s+do|what's\s+up)[?!.,\s]*$", re.IGNORECASE),
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
        re.compile(r"^\s*(help|what\s+can\s+you\s+do|how\s+can\s+you\s+help|commands)[?!.,\s]*$", re.IGNORECASE),
        "HELP",
    ),
]

# Direct requests for personal student records lookup (e.g. "what is my attendance", "check my GPA")
STUDENT_SPECIFIC_PATTERN = re.compile(
    r"(\b(what\s+is\s+my|what\s+are\s+my|tell\s+me\s+my|show\s+my|check\s+my|view\s+my|get\s+my|fetch\s+my|can\s+you\s+check\s+my)\s+(attendance|grades?|gpa|cgpa|marks|results?|timetable|schedule|fee\s+dues|dues)\b|"
    r"^\s*(my\s+(attendance|grades?|gpa|marks|results?|timetable|fee\s+dues|dues))\s*[?!.,]?\s*$|"
    r"\bpay\s+my\s+fee\b)",
    re.IGNORECASE,
)

# Negations, disclaimers, or corrections mentioning attributes (e.g., "i never mentioned my marks", "didn't say my score")
STUDENT_NEGATION_PATTERN = re.compile(
    r"\b(never|didn't|did\s+not|not|haven't|don't|why)\s+(mention|mentioned|say|said|give|given|share|shared|tell|told|state|stated|ask|asking)\b",
    re.IGNORECASE,
)

UNIVERSITY_KEYWORDS = {
    "exam", "exams", "examination", "examinations", "fee", "fees", "hostel", "hostels",
    "attendance", "semester", "semesters", "course", "courses", "syllabus", "department",
    "departments", "faculty", "scholarship", "scholarships", "transport", "bus", "library",
    "timetable", "result", "results", "grade", "grades", "marks", "regulation", "regulations",
    "calendar", "admission", "admissions", "registration", "register", "certificate", "certificates",
    "document", "documents", "documentation", "marksheet", "marksheets", "memo", "memos",
    "requirement", "requirements", "eligibility", "criteria", "qualification", "qualifications",
    "apply", "applying", "application", "enroll", "enrollment", "procedure", "process",
    "convocation", "placement", "placements", "internship", "internships", "laboratory",
    "lab", "labs", "campus", "notice", "notices", "circular", "deadline", "deadlines",
    "university", "college", "curfew", "mess", "warden", "hall ticket", "admit card",
    "tuition", "refund", "re-evaluation", "penalty", "penalties", "late fee", "late registration",
    "fine", "fines", "due", "dues", "rule", "rules", "policy", "policies",
    "srix", "club", "clubs", "event", "events", "canteen", "cafeteria", "sports", "gym",
    "accommodation", "program", "programs", "btech", "mtech", "mba", "phd",
    "chancellor", "ranking", "rankings", "nirf", "accreditation",
    "warangal", "visit", "places", "tourist", "tourism", "temple", "ramappa", "laknavaram", "fort",
    # Common shortcuts, slang, and typo variants
    "admsn", "admsns", "adm", "admision", "elgblty", "elgible", "eligiblity",
    "plcmnt", "plcmnts", "placmnt", "placmnts", "pakg", "pkg", "ctc", "lpa",
    "schlrshp", "schlrshps", "scholrshp", "scholrshps",
    "attndnc", "atndnc", "attendence",
    "hostle", "hostles", "intime", "outtime",
    "sem", "sems",
    "cgpa", "sgpa",
    "cse", "ece", "eee", "mech", "civil", "aiml",
    "prof", "hod", "vc",
    "mrks",
    "clg", "collge", "cllg", "univ", "varsity", "sru",
}


_QUESTION_STARTERS = {"what", "when", "where", "why", "who", "which", "can", "could", "is", "are", "do", "does", "recommend", "tell"}


def _is_greeting_without_question(text: str) -> bool:
    """Return True if message is a greeting or courtesy, but not a substantive question."""
    if not re.match(r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)\b", text, re.IGNORECASE):
        return False
    # Courtesy check: "how are you" or "how is it going" is part of greeting
    if re.search(r"\bhow\s+(are\s+you|is\s+it\s+going)\b", text, re.IGNORECASE):
        return True
    # If it contains substantive question words, it's an inquiry, not a pure greeting
    words = [w.lower() for w in re.findall(r"\w+", text)]
    for w in words:
        if w in _QUESTION_STARTERS:
            return False
    return True


# Direct score, percentage, or number answers to bot questions (e.g. "93%", "93", "85% in PCM")
SCORE_REPLY_PATTERN = re.compile(
    r"^\s*(?:i\s+(?:got|scored|have|achieved)\s+)?\d{1,3}(?:\.\d+)?\s*%?(?:\s*(?:marks?|out\s+of\s+\d+)?(?:\s*in\s+(?:12th|pcm|intermediate|boards?))?)?\s*$",
    re.I,
)

# Explicit personal record lookup expressions
PERSONAL_RECORD_LOOKUP = re.compile(
    r"(\b(my\s+(attendance|grades?|gpa|cgpa|marks|results?|timetable|fee\s+dues|dues|schedule)|pay\s+my\s+fee)\b|"
    r"\b(what\s+is\s+my|what\s+are\s+my|tell\s+me\s+my|show\s+my|check\s+my|view\s+my|get\s+my|fetch\s+my)\b)",
    re.I,
)


def fast_classify(message: str, conversation_context: str = "") -> IntentType | None:
    """Check fast regex patterns and keyword indicators."""
    text = message.strip()

    # 1. Corrections, clarifications, and negations (e.g. "i never mentioned my marks", "didn't say my score")
    if STUDENT_NEGATION_PATTERN.search(text):
        return "GENERAL"

    # 2. Direct score or percentage answer to ongoing dialogue (e.g. "93%", "93", "85% in 12th")
    if SCORE_REPLY_PATTERN.match(text):
        if conversation_context.strip():
            return "UNIVERSITY"
        return "GENERAL_CONVERSATION"

    # 3. Student-specific individual record lookup requests
    if STUDENT_SPECIFIC_PATTERN.search(text):
        return "STUDENT_SPECIFIC"

    # 4. University keyword check — even if query starts with a greeting
    #    (e.g., "Hi, how to apply for admission?")
    words = set(re.findall(r"\w+", text.lower()))
    if words & UNIVERSITY_KEYWORDS:
        return "UNIVERSITY"

    # 5. Check for greetings that do not contain substantive questions
    if _is_greeting_without_question(text):
        return "GREETING"

    # 6. Other conversational patterns (thanks, goodbyes, acknowledgments, help)
    for pattern, intent in FAST_PATTERNS:
        if intent != "GREETING" and pattern.search(text):
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
    fast_result = fast_classify(message, conversation_context=conversation_context)
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
            # Guard against small LLMs falsely classifying short answers as STUDENT_SPECIFIC
            if intent == "STUDENT_SPECIFIC" and not PERSONAL_RECORD_LOOKUP.search(message):
                logger.info(
                    "Guardrail: Overriding false STUDENT_SPECIFIC classification for '%s'",
                    message[:40],
                )
                intent = "UNIVERSITY" if conversation_context.strip() else "GENERAL_CONVERSATION"

            return intent, confidence  # type: ignore

    except Exception as e:
        logger.warning("LLM classification failed for '%s': %s", message[:40], e)

    return "GENERAL_CONVERSATION", 0.5
