"""Query reformulation service — turns conversational follow-ups into standalone search queries.

Handles:
- Coreference resolution (pronouns, ellipsis)
- Spelling typos and shorthand (hostle, elgblty, mrks, etc.)
- Domain synonyms and colloquialisms (discount → scholarship, dorm → hostel)
- Informal / Hinglish vocabulary common among Indian students
- Fuzzy spell correction for unknown misspellings against known university vocabulary
"""

import difflib
import logging
import re

from app.providers.base import LLMProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coreference and continuation patterns
# ---------------------------------------------------------------------------

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
    r"schlrshp|schlrshps|mrks|pakg|pkg|hostle|intime|outtime|clg|"
    # Hinglish / Telugu-English informal markers
    r"yaar|kya|bhai|anna|andi|ayya|nenu|meeru|mee|oka|okka|cheppandi|"
    r"cheppu|antu|ante|konchem|kaadu|ledu|ayyindi|avutundi|undi)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Domain synonyms: informal / colloquial → official handbook term
# ---------------------------------------------------------------------------
DOMAIN_SYNONYMS: dict[str, str] = {
    # Scholarships / financial aid
    "discount": "scholarship",
    "discounts": "scholarships",
    "fee concession": "scholarship fee concession",
    "fee waiver": "scholarship tuition fee waiver",
    "concession": "scholarship",
    "concessions": "scholarships",
    "financial aid": "scholarship",
    "financial help": "scholarship",
    "money help": "scholarship",
    "fee help": "scholarship fee concession",
    "free seat": "scholarship full fee waiver",
    "free admission": "scholarship merit admission",

    # Accommodation — only expand standalone 'dorm', not 'room' (too generic mid-sentence)
    "dorm": "hostel",
    "dorms": "hostels",
    "dormitory": "hostel accommodation",
    # 'room'/'rooms'/'stay'/'quarters'/'pg'/'paying guest' removed — too noisy mid-sentence

    # Placements / salaries
    "salary": "placement package CTC",
    "salaries": "placement packages CTC",
    "highest salary": "highest placement package CTC",
    # 'avg salary' and 'average salary' removed — 'avg' is caught by typo dict, not compound
    "job package": "placement package CTC",
    "job offer": "placement offer",
    "jobs": "placement",
    "company": "placement recruiter company",
    "companies": "placement recruiters",
    "mnc": "MNC placement recruiter",
    "hire": "placement recruitment",
    "hiring": "placement recruitment",
    "campus drive": "campus placement drive",
    "off campus": "off-campus placement",

    # Admissions / seats
    "seat": "admission seat intake",
    "seats": "admission intake capacity",
    # 'join'/'joining' removed — too generic in mid-sentence (e.g. 'how to join'→'how to admission enrollment')
    "enroll": "admission enrollment",
    "enrollment": "admission enrollment procedure",
    "take admission": "admission procedure",
    "getting admission": "admission eligibility criteria",

    # Fees / costs
    "cost": "fee structure",
    "price": "fee structure",
    "charges": "fee structure",
    "amount": "fee amount",
    "fees per year": "annual fee structure",
    "yearly fee": "annual fee structure",
    "total fees": "total fee structure",
    "how much fees": "fee structure",

    # Academics / marks
    "pass marks": "minimum passing marks",
    "pass percentage": "minimum passing percentage",
    "board marks": "12th intermediate marks",
    "12 marks": "12th marks",
    "inter marks": "intermediate marks",
    "pcm score": "PCM 12th percentage",

    # Hinglish meaning mappings — ONLY expand standalone words that are clearly domain terms
    # NOTE: Generic Hinglish particles (kab, kahan, kaise, chahiye, kitna) removed — they
    #       corrupt mid-sentence context when replaced word-for-word. The LLM reformulation
    #       step handles these naturally.

    # Common informal phrases (multi-word → clear search term)
    "when to apply": "admission application deadline",
    "how to join": "admission enrollment procedure",
    "how to get in": "admission eligibility and procedure",
    "last date": "application deadline",
    "cut off": "cutoff marks",
    "cutoff marks": "admission cutoff percentage",
}

# ---------------------------------------------------------------------------
# Rapid typo corrections (exact word-boundary substitution, no fuzzy needed)
# ---------------------------------------------------------------------------
TYPO_CORRECTIONS: dict[str, str] = {
    # Eligibility
    "elgblty": "eligibility",
    "elgible": "eligible",
    "eligiblity": "eligibility",
    "eligble": "eligible",
    "egibility": "eligibility",

    # Admission
    "admsn": "admission",
    "admsns": "admissions",
    "admision": "admission",
    "admisions": "admissions",
    "adm": "admission",

    # Placement
    "plcmnt": "placement",
    "plcmnts": "placements",
    "placmnt": "placement",
    "placmnts": "placements",

    # Hostel
    "hostle": "hostel",
    "hostles": "hostels",
    "hostal": "hostel",
    "hostall": "hostel",
    "hostels": "hostels",

    # Attendance
    "attndnc": "attendance",
    "atndnc": "attendance",
    "attendence": "attendance",
    "attedance": "attendance",

    # Scholarship
    "schlrshp": "scholarship",
    "schlrshps": "scholarships",
    "scholrshp": "scholarship",
    "scholrshps": "scholarships",
    "scolarship": "scholarship",
    "scolarships": "scholarships",

    # Misc
    "mrks": "marks",
    "clg": "college",
    "collge": "college",
    "cllg": "college",
    "bteck": "B.Tech",
    "btech": "B.Tech",
    "mtech": "M.Tech",
    "syllubus": "syllabus",
    "syllbus": "syllabus",
    "silabus": "syllabus",
    "candiature": "candidature",
    "registation": "registration",
    "regestration": "registration",
    "submision": "submission",
    "submisson": "submission",
    "accomodation": "accommodation",
    "acommodation": "accommodation",
    "semister": "semester",
    "semster": "semester",
    "libary": "library",
    "placment": "placement",
    "scholership": "scholarship",
    "scholarshp": "scholarship",
    "aplication": "application",
    "applcation": "application",
    "faculity": "faculty",
    "infomation": "information",
    "informaton": "information",
    "admiission": "admission",
    "eligiility": "eligibility",
    "hostelite": "hostel student",
}

# ---------------------------------------------------------------------------
# Fuzzy spell correction — catches unknown misspellings not in the dict above
# ---------------------------------------------------------------------------

# The vocabulary we want to correct towards — university domain terms users might misspell
_FUZZY_VOCABULARY: list[str] = [
    "eligibility", "eligible", "admission", "admissions", "placement", "placements",
    "scholarship", "scholarships", "hostel", "hostels", "attendance", "semester",
    "semesters", "syllabus", "library", "cafeteria", "laboratory", "registration",
    "certificate", "accommodation", "transportation", "application", "enrollment",
    "department", "examination", "timetable", "regulation", "internship", "internships",
    "convocation", "university", "college", "faculty", "curriculum", "accreditation",
    "qualification", "requirement", "deadline", "procedure", "tuition", "concession",
]

# Only apply fuzzy correction to words longer than this (short words have too many false positives)
_FUZZY_MIN_WORD_LEN = 6
_FUZZY_MATCH_CUTOFF = 0.80  # similarity threshold (0→1); higher = more conservative


def _fuzzy_correct_word(word: str) -> str:
    """Return the closest vocabulary word if above similarity cutoff, else the original word."""
    if len(word) < _FUZZY_MIN_WORD_LEN:
        return word
    # Skip words that are already exact vocabulary matches
    if word.lower() in _FUZZY_VOCABULARY:
        return word
    matches = difflib.get_close_matches(
        word.lower(), _FUZZY_VOCABULARY, n=1, cutoff=_FUZZY_MATCH_CUTOFF
    )
    if matches:
        corrected = matches[0]
        # Preserve original capitalisation style
        if word[0].isupper():
            corrected = corrected.capitalize()
        logger.debug("Fuzzy corrected '%s' → '%s'", word, corrected)
        return corrected
    return word


def apply_fuzzy_corrections(text: str) -> str:
    """Apply fuzzy spell correction to each word in the query."""
    # Tokenise preserving punctuation and spaces
    tokens = re.findall(r"\w+|\W+", text)
    result = []
    for token in tokens:
        if re.match(r"\w+", token):
            result.append(_fuzzy_correct_word(token))
        else:
            result.append(token)
    return "".join(result)


# ---------------------------------------------------------------------------
# Combined pattern for detecting synonyms / typos (used by needs_reformulation)
# ---------------------------------------------------------------------------
SYNONYM_OR_TYPO_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in list(DOMAIN_SYNONYMS.keys()) + list(TYPO_CORRECTIONS.keys())) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Student profile / qualification sharing patterns
# ---------------------------------------------------------------------------
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


def canonicalize_query(query: str) -> str:
    """Pre-retrieval normalization pipeline:

    1. Correct exact spelling typos (campus shorthand)
    2. Map domain synonyms / colloquialisms to official handbook terms
    3. Apply fuzzy spell correction for unknown misspellings
    """
    text = query

    # Step 1: Exact typo corrections
    for typo, correction in TYPO_CORRECTIONS.items():
        pattern = re.compile(r"\b" + re.escape(typo) + r"\b", re.IGNORECASE)
        text = pattern.sub(correction, text)

    # Step 2: Domain synonym expansion (longest phrases first to avoid partial matches)
    sorted_synonyms = sorted(DOMAIN_SYNONYMS.items(), key=lambda x: -len(x[0]))
    for term, canonical in sorted_synonyms:
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        text = pattern.sub(canonical, text)

    # Step 3: Fuzzy correction for remaining unknown misspellings
    text = apply_fuzzy_corrections(text)

    return text


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

    # 8. Very short messages without clear standalone subjects rely on context
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

    Pipeline:
    1. canonicalize_query() — fast deterministic correction (typos, synonyms, fuzzy)
    2. needs_reformulation() — decide if LLM rewrite is needed
    3. LLM reformulation — coreference resolution; returns the cleaned LLM output directly
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
            return cleaned

    except Exception as e:
        logger.warning("Query reformulation failed for '%s': %s", message[:50], e)

    return canonical_message
