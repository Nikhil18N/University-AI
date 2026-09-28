"""Query reformulation service — turns conversational follow-ups into standalone search queries."""

import logging
import re

from app.providers.base import LLMProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

# Patterns indicating a contextual follow-up or coreference
FOLLOW_UP_INDICATORS = re.compile(
    r"\b(it|that|this|they|them|those|these|its|for\s+that|about\s+that|what\s+about|how\s+about|and|also|when\s+is\s+it|where\s+is\s+it)\b",
    re.IGNORECASE,
)


def needs_reformulation(message: str, context: str) -> bool:
    """Determine if a message requires contextual coreference resolution."""
    if not context.strip():
        return False

    # Check for pronoun / follow-up cues
    if FOLLOW_UP_INDICATORS.search(message):
        return True

    # Very short messages (e.g., "more details") usually rely on context.
    words = message.strip().split()
    if len(words) <= 3:
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
