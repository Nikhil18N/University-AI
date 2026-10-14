"""Query reformulation service — turns conversational follow-ups into standalone search queries."""

import logging
import re

from app.providers.base import LLMProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

# Pronouns and phrases indicating an explicit coreference to a previous entity
COREFERENCE_PATTERNS = re.compile(
    r"\b(it|that|this|they|them|those|these|its|for\s+that|about\s+that|"
    r"when\s+is\s+it|where\s+is\s+it|how\s+much\s+is\s+it|how\s+to\s+apply\s+for\s+it)\b",
    re.IGNORECASE,
)

# Open-ended continuation requests that rely entirely on previous context
CONTINUATION_PATTERNS = re.compile(
    r"^\s*(yes|yeah|yep|sure|definitely|absolutely|yes\s+please|more\s+details|tell\s+me\s+more|what\s+else|elaborate|explain\s+further|"
    r"details\s+please|and\s+then\?|why\s+so|how\s+come)\b",
    re.IGNORECASE,
)

# Attribute inquiries that refer to the current topic (e.g. "what about single rooms?", "fees?", "timings?")
ATTRIBUTE_INQUIRIES = re.compile(
    r"^\s*(what\s+about|how\s+about|and)?\s*(the\s+)?(fees?|cost|timing|timings|eligibility|rules?|process|deadline|deadlines|requirements?|single\s+rooms?|double\s+rooms?)\b",
    re.IGNORECASE,
)

# Comparative/elliptical follow-ups (e.g. "what about for other branches?", "how about ECE?", "and for day scholars?")
COMPARATIVE_FOLLOWUP_PATTERNS = re.compile(
    r"^\s*(what\s+about|how\s+about|and\s+for|what\s+of|what\s+for)\b",
    re.IGNORECASE,
)

# Conversational chatter prefixes / slang markers that contaminate vector search
CHATTER_OR_SLANG_PATTERNS = re.compile(
    r"\b(btw|anyway|anyways|lol|lmao|haha|tbh|bro|dude|damnn?|cool\s+cool|"
    r"wht|abt|elgblty|elgible|admsn|admsns|plcmnt|plcmnts|attndnc|atndnc|"
    r"schlrshp|schlrshps|mrks|pakg|pkg|hostle|intime|outtime|clg)\b",
    re.IGNORECASE,
)

# Common university domain synonyms and colloquialisms mapped to official handbook terms
DOMAIN_SYNONYMS: dict[str, str] = {
    "discount": "scholarship",
    "discounts": "scholarships",
    "fee concession": "scholarship fee concession",
    "fee waiver": "scholarship tuition fee waiver",
    "concession": "scholarship",
    "concessions": "scholarships",
    "financial aid": "scholarship",
    "dorm": "hostel",
    "dorms": "hostels",
    "dormitory": "hostel accommodation",
    "salary": "placement package CTC",
    "salaries": "placement packages CTC",
    "highest salary": "highest placement package CTC",
    "avg salary": "average placement package CTC",
    "average salary": "average placement package CTC",
    "seat": "admission seat intake",
    "seats": "admission intake capacity",
}

# Rapid campus typo normalizations
TYPO_CORRECTIONS: dict[str, str] = {
    "elgblty": "eligibility",
    "elgible": "eligible",
    "admsn": "admission",
    "admsns": "admissions",
    "plcmnt": "placement",
    "plcmnts": "placements",
    "hostle": "hostel",
    "hostles": "hostels",
    "attndnc": "attendance",
    "atndnc": "attendance",
    "schlrshp": "scholarship",
    "schlrshps": "scholarships",
    "mrks": "marks",
    "clg": "college",
    "bteck": "B.Tech",
    "syllubus": "syllabus",
}

SYNONYM_OR_TYPO_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in list(DOMAIN_SYNONYMS.keys()) + list(TYPO_CORRECTIONS.keys())) + r")\b",
    re.IGNORECASE,
)


def canonicalize_query(query: str) -> str:
    """Pre-retrieval normalization: correct campus typos and expand informal domain synonyms."""
    text = query

    # 1. Correct spelling typos
    for typo, correction in TYPO_CORRECTIONS.items():
        pattern = re.compile(r"\b" + re.escape(typo) + r"\b", re.IGNORECASE)
        text = pattern.sub(correction, text)

    # 2. Map domain synonyms (e.g. discount -> scholarship)
    for term, canonical in DOMAIN_SYNONYMS.items():
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        text = pattern.sub(canonical, text)

    return text


# Student profile responses or answers to qualification/discovery questions (e.g. "I got 75%", "my score is 60%", "interested in CSE", "12th PCM with 80%")
STUDENT_PROFILE_PATTERNS = re.compile(
    r"\b(i\s+(have|got|scored|did|completed|want|wish|am\s+interested)|"
    r"my\s+(score|percentage|marks|rank|interest|interests|branch|stream|qualification)|"
    r"interested\s+in|looking\s+for|pcm|bipc|eamcet|jee|intermediate|inter|12th|10\+2)\b",
    re.IGNORECASE,
)

# Distinct university subjects that are self-contained when queried directly
STANDALONE_TOPICS = {
    "placement", "placements", "hostel", "hostels", "transport", "bus", "buses",
    "library", "sports", "srix", "club", "clubs", "canteen", "mess", "cafeteria",
    "admission", "admissions", "ranking", "rankings", "chancellor", "vice chancellor",
    "leadership", "laboratory", "labs", "curfew", "scholarship", "scholarships",
    "document", "documents", "certificate", "certificates", "requirement", "requirements",
    "eligibility", "qualification", "qualifications",
}


def needs_reformulation(message: str, context: str) -> bool:
    """Determine if a message requires contextual coreference resolution, synonym expansion, or query cleanup."""
    text = message.strip()

    # 1. Conversational chatter, typos, or domain synonyms (e.g. "discount", "dorm"): clean it up
    if CHATTER_OR_SLANG_PATTERNS.search(text) or SYNONYM_OR_TYPO_PATTERN.search(text):
        return True

    # Context-dependent rules require existing conversation history
    if not context.strip():
        return False

    # 2. Explicit coreference pronouns (e.g., "when does it close?", "how much is that?")
    if COREFERENCE_PATTERNS.search(text):
        return True

    # 3. Open-ended continuation (e.g., "tell me more", "more details")
    if CONTINUATION_PATTERNS.search(text):
        return True

    # 4. Comparative/elliptical follow-ups (e.g., "what about for other branches?", "how about ECE?")
    if COMPARATIVE_FOLLOWUP_PATTERNS.search(text):
        words = set(re.findall(r"\w+", text.lower()))
        if not (words & STANDALONE_TOPICS):
            return True

    # 5. Attribute-only follow-ups (e.g., "fees?", "timings?")
    if ATTRIBUTE_INQUIRIES.search(text):
        words = set(re.findall(r"\w+", text.lower()))
        standalone_present = bool(words & (STANDALONE_TOPICS - {"fee", "fees"}))
        if not standalone_present:
            return True

    # 6. Student profile details responding to a discovery or qualification inquiry
    if STUDENT_PROFILE_PATTERNS.search(text):
        words = set(re.findall(r"\w+", text.lower()))
        if not (words & (STANDALONE_TOPICS - {"admission", "admissions", "eligibility", "qualification", "qualifications"})):
            return True

    # 7. If query mentions a clear standalone topic without coreference pronouns or slang,
    #    it is self-contained (e.g., "about placements?", "hostel rules", "library timings")
    words = set(re.findall(r"\w+", text.lower()))
    if words & STANDALONE_TOPICS:
        return False

    # 6. Very short messages without clear standalone subjects rely on context
    words_list = text.split()
    if len(words_list) <= 3 and context.strip():
        return True

    return False


async def reformulate_query(
    message: str,
    conversation_context: str,
    llm_provider: LLMProvider,
) -> str:
    """Reformulate a follow-up query into a standalone search query.

    If reformulation is not needed or fails, returns the canonicalized query.
    """
    canonical_message = canonicalize_query(message)
    if not needs_reformulation(message, conversation_context):
        return canonical_message

    try:
        prompt = render_prompt(
            "reformulation",
            conversation=conversation_context,
            message=canonical_message,
        )
        reformulated = await llm_provider.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        cleaned = reformulated.strip().strip('"').strip("'")
        if cleaned and len(cleaned) > 3:
            logger.info(
                "Reformulated query from '%s' -> '%s'",
                message[:50],
                cleaned[:60],
            )
            return canonicalize_query(cleaned)

    except Exception as e:
        logger.warning("Query reformulation failed for '%s': %s", message[:50], e)

    return canonical_message
