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

    # 4b. "I want to visit campus on 2026-11-25" / "visit campus tomorrow": a visit with a date
    #     anywhere in the sentence (the patterns above only catch "visit on ...").
    if re.search(r"\b(?:visit|come|tour)\b", msg) and not re.search(r"\b(?:timings?|hours?|rules?|allowed|can\s+parents)\b", msg):
        from .tools import resolve_campus_visit_date
        if resolve_campus_visit_date(msg).get("date"):
            return "CAMPUS_VISIT_BOOKING_WITH_DATE"

    # 5. Explicit booking request (without a specific date yet)
    if any(phrase in msg for phrase in _EXPLICIT_BOOKING_PHRASES):
        return "CAMPUS_VISIT_BOOKING"

    # 6. General campus visit inquiry
    if any(pattern in msg for pattern in _VISIT_INFO_PATTERNS):
        return "CAMPUS_VISIT_INFO"

    return "GENERAL"


# ----------------------------------------------------------------------------
# Contact requests: "ask someone to call me", "don't call me", and the name a
# student gives along with a phone number. Used by the agent to run the callback /
# cancel tools itself, so a request is never "noted" without being saved.
# ----------------------------------------------------------------------------
_CONTACT_VERB = r"(?:call|contact|phone|ring|disturb|message|whatsapp|text)(?:ing)?"
_NOT_NOW = r"(?!\s+(?:me\s+|us\s+)?(?:before|until|till|at|on|in\s+the|during|now|today|tomorrow|after|between)\b)"

_CANCEL_CONTACT_PATTERN = re.compile(
    rf"\b(?:do\s*n[o']?t|dont|never|stop|no\s+need\s+to|need\s+not|not\s+to|please\s+don'?t)\s+{_CONTACT_VERB}\b{_NOT_NOW}"
    r"|\bcancel\b.{0,30}\b(?:call\s*-?\s*back|callback|call|request|visit|booking|appointment|tour)\b"
    r"|\b(?:call\s*-?\s*back|callback|visit|booking|appointment)\b.{0,20}\bcancel\b"
    r"|\b(?:remove|delete)\s+my\s+(?:number|details|phone|contact|request|data)\b"
    r"|\b(?:i\s+)?(?:do\s*n[o']?t|dont)\s+want\s+(?:a\s+|any\s+|the\s+)?(?:call|callback|call\s*back|calls)\b"
    r"|\bcall\s+(?:cheyakandi|cheyyakandi|cheyoddu|cheyyoddu|cheyakudadhu|vaddu|oddu|mat\s+kar\w*|nahi\s+kar\w*|na\s+kar\w*)\b",
    re.IGNORECASE,
)
_CANCEL_IT_PATTERN = re.compile(r"^\s*(?:please\s+|pls\s+)?cancel(?:\s+(?:it|that|this|please|pls))?[.!\s]*$",
                                re.IGNORECASE)

_CALLBACK_REQUEST_PATTERN = re.compile(
    r"\bcall\s*-?\s*back\b"
    r"|\b(?:call|ring|phone|contact)\s+(?:me|us|him|her|my\s+(?:son|daughter|father|mother|dad|mom|"
    r"parents?|husband|wife|brother|sister|ward))\b"
    r"|\b(?:someone|somebody|anyone|counsell?or|admissions?\s+(?:team|office|officer|people)|team)\b"
    r".{0,25}\b(?:call|contact|phone|ring)\b(?!\s+(?:number|no\b|details|cent(?:re|er)|letter|it\b))"
    r"|\b(?:talk|speak)\s+(?:to|with)\s+(?:a\s+|an\s+|the\s+|your\s+|some\s+)?(?:counsell?or|admissions?|"
    r"someone|somebody|human|person|representative|agent|staff)\b"
    r"|\b(?:call|phone)\s+(?:cheyandi|cheyyandi|cheyamani|cheyinchandi|cheyagalara|cheyyagalara|"
    r"karo|kijiye|karna|kardo|kar\s+do|kar\s+dijiye)\b",
    re.IGNORECASE,
)
# "Will someone call me after I apply?" is a question about the process, not a request.
_PROCESS_QUESTION = re.compile(r"^\s*(?:will|would|does|do|did|is|are|when|why|how\s+(?:long|soon|many))\b",
                               re.IGNORECASE)

_VISIT_REQUEST_PATTERN = re.compile(
    r"\b(?:book|schedule|arrange|plan|register|reserve|fix)\b.{0,30}\b(?:visit|tour|slot)\b"
    r"|\b(?:want|wish|like|planning|plan|coming|come)\b.{0,25}\b(?:visit|see\s+the\s+campus|campus\s+tour)\b"
    r"|\bvisit\b.{0,20}\b(?:book|schedule|arrange)\b",
    re.IGNORECASE,
)


_NUMBER_UPDATE_PATTERN = re.compile(
    r"\b(?:change|update|replace|correct|edit|modify)\b.{0,40}\b(?:number|mobile|phone|contact)\b"
    r"|\b(?:number|mobile|phone)\b.{0,25}\b(?:changed|is\s+wrong|was\s+wrong|incorrect)\b"
    r"|\b(?:my\s+)?new\s+(?:mobile\s+|phone\s+|contact\s+)?(?:number|no\b)"
    r"|\b(?:update|change|edit)\b.{0,25}\b(?:settings?|profile|my\s+details)\b",
    re.IGNORECASE,
)
_NUMBER_STATEMENT_PATTERN = re.compile(
    r"\b(?:my|this\s+is\s+my|here\s+is\s+my)\s+(?:new\s+)?(?:mobile|phone|contact|whatsapp|cell)?\s*"
    r"(?:number|no\.?|num)\b", re.IGNORECASE)


def is_number_update(message: str) -> bool:
    """'change my number', 'my new number is ...', 'update it in the settings'."""
    return bool(_NUMBER_UPDATE_PATTERN.search(message or ""))


def is_number_statement(message: str) -> bool:
    """'my mobile number is 98...' (the student is telling us their number)."""
    return bool(_NUMBER_STATEMENT_PATTERN.search(message or ""))


def is_cancel_contact(message: str, has_open_request: bool = False) -> bool:
    """True for 'don't call me', 'cancel the callback', 'cancel my visit' (and bare 'cancel' when a
    request is open or being arranged)."""
    msg = message or ""
    if _CANCEL_CONTACT_PATTERN.search(msg):
        return True
    return bool(has_open_request and _CANCEL_IT_PATTERN.match(msg))


def is_callback_request(message: str) -> bool:
    """True when the student asks to be phoned by the admissions team."""
    msg = message or ""
    if _CANCEL_CONTACT_PATTERN.search(msg) or not _CALLBACK_REQUEST_PATTERN.search(msg):
        return False
    has_digits = bool(re.search(r"\d{5,}", msg))
    return has_digits or not _PROCESS_QUESTION.match(msg)


def is_visit_request(message: str) -> bool:
    """True when the student asks to book / plan a campus visit (not just asks about visiting)."""
    return bool(_VISIT_REQUEST_PATTERN.search(message or ""))


_NOT_A_NAME = frozenset("""
a an the i im am is are was me my mine we us you your u he she they this that it its here there
yes yeah yep ok okay no not sure please pls plz thanks thank hi hello hey sir madam mam
name names number numbers phone mobile contact call calls callback back whatsapp no num ph
and or but so for of on in at to from with by as if then also too very just now still about
interested looking planning studying student parent father mother son daughter brother sister
going coming visiting calling asking thinking confused worried eligible ready waiting getting
done fine good happy want wants need needs like would will can could should may have has had
visit campus tour book booking schedule date today tomorrow morning afternoon evening night
monday tuesday wednesday thursday friday saturday sunday
january february march april june july august september october november december
cse ece eee mech civil btech mtech mba bba bca mca bsc msc engineering course fee fees hostel
scholarship admission admissions counsellor counselor team sru university inter intermediate
rank marks percent percentage eapcet eamcet jee cbse people persons members friends
bus buses route routes transport placement placements library timings timing faculty professor professors
hod dean details detail information info location address directions food mess sports ragging refund
documents document apply application loan lab labs wifi college ranking rankings nirf reach how what where
when why which who fee structure syllabus curriculum seats seat cutoff exam exams result results
""".split())
_NAME_INTRO = re.compile(
    r"(?:\bmy\s+name\s+is|\bname\s*(?:is|:|-)|\bname\s+(?=[A-Za-z])|\bmyself\b|\bnaa\s+peru\b|"
    r"\bmera\s+naam\b)\s*([A-Za-z][A-Za-z .']{0,45})", re.IGNORECASE)
# "I am ..." is usually not a name ("I am interested", "I am a parent"), so it needs more proof.
_WEAK_NAME_INTRO = re.compile(r"(?:\bi\s+am\b|\bi'm\b|\bim\b|\bthis\s+is\b)\s+([A-Za-z][A-Za-z .']{0,45})",
                              re.IGNORECASE)
_NAME_WORD = re.compile(r"[A-Za-z][A-Za-z.']*")


def _clean_name(fragment: str):
    """Leading words of `fragment` that can be a person's name (1-4 words), else None."""
    words = []
    for raw in (fragment or "").replace(",", " , ").split():
        word = raw.strip(".'")
        if not _NAME_WORD.fullmatch(raw) or word.lower() in _NOT_A_NAME or len(words) == 4:
            break
        words.append(word)
    while words and len(words[-1]) == 1 and len(words) > 3:
        words.pop()
    name = " ".join(words).strip()
    if len(name.replace(" ", "")) < 3:
        return None
    return " ".join(w if w.isupper() and len(w) <= 3 else w.capitalize() for w in name.split())


def extract_name(message: str, bare_ok: bool = False):
    """The student's name if the message states one.

    Understands 'my name is Ravi Kumar', 'I am Ravi, 98...', 'Ravi Kumar 9876543210',
    '9876543210 Ravi Kumar'. With bare_ok=True (the agent has just asked for the name) a message
    that is only a name ('Ravi Kumar') also counts.
    """
    msg = (message or "").strip()
    for m in _NAME_INTRO.finditer(msg):
        name = _clean_name(m.group(1))
        if name:
            return name
    phone = re.search(r"(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)", msg)
    for m in _WEAK_NAME_INTRO.finditer(msg):
        name = _clean_name(m.group(1))
        if name:
            typed = m.group(1).split()[:len(name.split())]
            if phone or bare_ok or all(w[:1].isupper() for w in typed):
                return name
    if phone:
        before = re.sub(r"[\s,\-(:]+$", "", msg[:phone.start()])
        before = re.split(r"[.;:!?\n,]", before)[-1].strip()
        if before and all(_NAME_WORD.fullmatch(w) for w in before.split()) and len(before.split()) <= 4:
            name = _clean_name(before)
            if name and len(name.split()) == len(before.split()):
                return name
        after = re.sub(r"^[\s,\-).]+", "", msg[phone.end():])
        after = re.split(r"[.;:!?\n,]", after)[0].strip()
        if after and all(_NAME_WORD.fullmatch(w) for w in after.split()) and len(after.split()) <= 4:
            name = _clean_name(after)
            if name and len(name.split()) == len(after.split()):
                return name
    if bare_ok and 1 <= len(msg.split()) <= 4 and all(_NAME_WORD.fullmatch(w) for w in msg.split()):
        name = _clean_name(msg)
        if name and len(name.split()) == len(msg.split()):
            return name
    return None


def extract_preferred_time(message: str):
    """'tomorrow evening', 'after 5 pm' ... as typed, or None."""
    m = re.search(r"\b((?:today|tomorrow|tonight)\s+)?(morning|afternoon|evening|night)\b"
                  r"|\b(?:after|before|at|around|by)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b"
                  r"|\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b(?:today|tomorrow)\b", message or "", re.IGNORECASE)
    return m.group(0).strip().lower() if m else None


def extract_visitors(message: str):
    m = re.search(r"\b(\d{1,2})\s*(?:people|persons?|members?|of\s+us|visitors?|guests?)\b", message or "",
                  re.IGNORECASE)
    return int(m.group(1)) if m else None


_BUDDY = r"(?:\s+(?:sru\s*_?\s*buddy|buddy|sru|there|bro|sir|mam|madam|team|dear|man|anna|akka))*"
_SMALL_TALK_PATTERNS = (
    ("greeting", re.compile(r"^(?:hi+|hello+|hey+|hlo+|helo|namaste|namaskaram|vanakkam|"
                            r"good\s+(?:morning|afternoon|evening))" + _BUDDY + r"[\s!.]*$", re.IGNORECASE)),
    ("how_are_you", re.compile(r"^(?:(?:hi+|hello+|hey+)[\s,]+)?(?:how\s+(?:are|r)\s+(?:you|u)(?:\s+doing)?|"
                               r"how\s+is\s+it\s+going|what'?s\s+up|wass?up)" + _BUDDY + r"[\s?!.]*$", re.IGNORECASE)),
    ("thanks", re.compile(r"^(?:ok(?:ay)?[\s,]+)?(?:thanks?(?:\s+a\s+lot)?|thank\s*(?:you|u)(?:\s+so\s+much|\s+very\s+much)?|"
                          r"thx|tq|ty)" + _BUDDY + r"[\s!.]*$", re.IGNORECASE)),
    ("bye", re.compile(r"^(?:ok(?:ay)?[\s,]+)?(?:bye+|good\s*bye|see\s+(?:you|u)|good\s+night)" + _BUDDY + r"[\s!.]*$",
                       re.IGNORECASE)),
    ("who_are_you", re.compile(r"^(?:who\s+(?:are|r)\s+(?:you|u)|what\s+(?:are|r)\s+(?:you|u)|"
                               r"what\s+can\s+(?:you|u)\s+do|what\s+is\s+sru\s*_?\s*buddy|"
                               r"are\s+(?:you|u)\s+(?:a\s+|an\s+)?(?:bot|human|ai|real|robot))" + r"[\s?!.]*$", re.IGNORECASE)),
)


def small_talk(message: str):
    """'greeting', 'how_are_you', 'thanks', 'bye' or 'who_are_you' when the message is ONLY that."""
    msg = (message or "").strip()
    if len(msg) > 60:
        return None
    for kind, pattern in _SMALL_TALK_PATTERNS:
        if pattern.match(msg):
            return kind
    return None
