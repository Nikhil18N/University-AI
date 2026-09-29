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
    """Determine if a message requires contextual coreference resolution."""
    if not context.strip():
        return False

    text = message.strip()

    # 1. Explicit coreference pronouns (e.g., "when does it close?", "how much is that?")
    if COREFERENCE_PATTERNS.search(text):
        return True

    # 2. Open-ended continuation (e.g., "tell me more", "more details")
    if CONTINUATION_PATTERNS.search(text):
        return True

    # 3. Attribute-only follow-ups (e.g., "what about single rooms?", "fees?", "timings?")
    if ATTRIBUTE_INQUIRIES.search(text):
        words = set(re.findall(r"\w+", text.lower()))
        standalone_present = bool(words & (STANDALONE_TOPICS - {"fee", "fees"}))
        if not standalone_present:
            return True

    # 4. If query mentions a clear standalone topic without coreference pronouns,
    #    it is self-contained (e.g., "about placements?", "hostel rules", "library timings")
    words = set(re.findall(r"\w+", text.lower()))
    if words & STANDALONE_TOPICS:
        return False

    # 5. Very short messages without clear standalone subjects rely on context
    words_list = text.split()
    if len(words_list) <= 3:
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
