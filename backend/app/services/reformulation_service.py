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
    r"^\s*(more\s+details|tell\s+me\s+more|what\s+else|elaborate|explain\s+further|"
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
    """Determine if a message requires contextual coreference resolution or query cleanup."""
    text = message.strip()

    # 1. Conversational chatter or slang contaminates vector retrieval: clean it up
    if CHATTER_OR_SLANG_PATTERNS.search(text):
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

    # 5. If query mentions a clear standalone topic without coreference pronouns or slang,
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

    If reformulation is not needed or fails, returns the original query.
    """
    if not needs_reformulation(message, conversation_context):
        return message

    try:
        prompt = render_prompt(
            "reformulation",
            conversation=conversation_context,
            message=message,
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

    return message
