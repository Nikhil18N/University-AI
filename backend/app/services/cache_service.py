"""Response cache service — Redis-backed cache for repeated RAG queries.

Caches grounded university answers to avoid redundant Gemini API + ChromaDB
round-trips for common repeated questions (e.g., 'What is minimum attendance?').

Cache policy:
- Only UNIVERSITY intent answers are cached (never STUDENT_SPECIFIC).
- Cache key: SHA-256 of the canonicalized query string.
- TTL: 3600 seconds (1 hour) — university facts change infrequently.
- Maximum cached answer length: 4000 characters (very long answers skipped).
- Cache is bypassed on error (graceful degradation, never raises).
"""

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600  # 1 hour
_MAX_ANSWER_LEN = 4000     # don't cache abnormally long answers
_KEY_PREFIX = "sru:rag:v1:"


def make_cache_key(canonical_query: str) -> str:
    """Return a Redis key for the given canonical query string."""
    digest = hashlib.sha256(canonical_query.lower().strip().encode("utf-8")).hexdigest()[:24]
    return f"{_KEY_PREFIX}{digest}"


async def get_cached_answer(
    redis_client: Any,
    canonical_query: str,
) -> tuple[str, list[dict]] | None:
    """Return (answer, sources) from cache, or None on miss or error."""
    if redis_client is None:
        return None
    try:
        key = make_cache_key(canonical_query)
        raw = await redis_client.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        logger.info("Cache HIT for query: %.60s", canonical_query)
        return data["answer"], data.get("sources", [])
    except Exception as exc:
        logger.warning("Cache get error (degrading gracefully): %s", exc)
        return None


async def set_cached_answer(
    redis_client: Any,
    canonical_query: str,
    answer: str,
    sources: list[dict],
) -> None:
    """Store (answer, sources) in Redis with TTL. Silently skips on error."""
    if redis_client is None:
        return
    if len(answer) > _MAX_ANSWER_LEN:
        logger.debug("Answer too long (%d chars) — skipping cache write", len(answer))
        return
    try:
        key = make_cache_key(canonical_query)
        payload = json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False)
        await redis_client.set(key, payload, ex=_CACHE_TTL_SECONDS)
        logger.info("Cache SET for query: %.60s (TTL=%ds)", canonical_query, _CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Cache set error (degrading gracefully): %s", exc)


async def invalidate_cache(redis_client: Any, canonical_query: str) -> None:
    """Delete a cached answer for a specific query."""
    if redis_client is None:
        return
    try:
        key = make_cache_key(canonical_query)
        await redis_client.delete(key)
    except Exception as exc:
        logger.warning("Cache invalidate error: %s", exc)
