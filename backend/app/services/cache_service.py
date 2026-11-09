"""Response cache service — Redis-backed scoped cache for repeated factual queries.

Cache policy (P0 Hardening):
1. Keyed per resolved sub-question text (after pronoun resolution), NOT raw message.
2. Canonical tuple:
   cache_schema_version | mode | resolved_question_normalized | relevant_profile_fields | prompt_version | generation_model | index_version | facts_version
3. Strictly caches factual mode queries only. Never caches persuasive, chitchat, sensitive,
   out_of_scope, multi-part merged answers, validator-blocked outputs, low-confidence fallbacks,
   or any reply that contains a clarifying question back to the student.
4. Auto-invalidated when index_version or facts_version is bumped in Redis.
5. All logging uses key hashes (no raw student questions or PII).
"""

import hashlib
import json
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = "v2"
PROMPT_VERSION = "2026.11"
_CACHE_TTL_SECONDS = 3600  # 1 hour
_MAX_ANSWER_LEN = 4000     # Skip abnormally long answers
_KEY_PREFIX = f"sru:rag:{CACHE_SCHEMA_VERSION}:"

REDIS_KEY_INDEX_VERSION = "sru:version:index"
REDIS_KEY_FACTS_VERSION = "sru:version:facts"

# Profile fields that can change factual answers (interests are strictly excluded)
RELEVANT_PROFILE_KEYS = ("degree", "branch", "program", "category", "nationality", "exam")


def normalize_relevant_profile(profile: dict | None) -> str:
    """Extract and sort profile fields that alter factual answers. Interests are excluded."""
    if not profile:
        return "none"
    pairs = []
    for k in sorted(RELEVANT_PROFILE_KEYS):
        val = profile.get(k)
        if val is not None and str(val).strip():
            norm_val = str(val).strip().lower()
            pairs.append(f"{k}={norm_val}")
    return ",".join(pairs) if pairs else "none"


def make_scoped_cache_key(
    mode: str,
    resolved_question: str,
    relevant_profile: dict | None = None,
    prompt_version: str = PROMPT_VERSION,
    generation_model: str = "",
    index_version: str = "1",
    facts_version: str = "1",
) -> str:
    """Build a deterministic SHA-256 key from a canonical delimited tuple."""
    model_name = generation_model or getattr(settings, "LLM_MODEL", "gemini-3.5-flash-lite")
    norm_q = " ".join(resolved_question.lower().strip().split())
    norm_profile = normalize_relevant_profile(relevant_profile)
    mode_clean = mode.lower().strip()

    raw_tuple = (
        f"{CACHE_SCHEMA_VERSION}|"
        f"{mode_clean}|"
        f"{norm_q}|"
        f"{norm_profile}|"
        f"{prompt_version}|"
        f"{model_name}|"
        f"{index_version}|"
        f"{facts_version}"
    )
    digest = hashlib.sha256(raw_tuple.encode("utf-8")).hexdigest()[:32]
    return f"{_KEY_PREFIX}{digest}"


def is_cacheable(mode: str, answer: str, part_count: int = 1) -> bool:
    """Check if an answer meets strict eligibility criteria for caching."""
    if mode != "factual":
        return False
    if part_count > 1:
        # Multi-part merged answers are never cached
        return False
    if not answer or len(answer) > _MAX_ANSWER_LEN:
        return False
    # Never cache validator fallback blocks or refusal text
    if "couldn't verify those details against our official sources" in answer.lower():
        return False
    if "admissions office (0870-2818333" in answer.lower() and "verify" in answer.lower():
        return False
    # Never cache replies that ask a clarifying question back to the student
    if "?" in answer:
        return False
    clarifying_signals = (
        "which program",
        "which branch",
        "which course",
        "what degree",
        "could you clarify",
        "please specify",
    )
    lower_ans = answer.lower()
    if any(sig in lower_ans for sig in clarifying_signals):
        return False

    return True


async def get_index_version(redis_client: Any) -> str:
    """Fetch current index_version counter from Redis, defaulting to '1'."""
    if redis_client is None:
        return "1"
    try:
        ver = await redis_client.get(REDIS_KEY_INDEX_VERSION)
        return str(ver) if ver else "1"
    except Exception:
        return "1"


async def get_facts_version(redis_client: Any) -> str:
    """Fetch current facts_version counter from Redis, defaulting to '1'."""
    if redis_client is None:
        return "1"
    try:
        ver = await redis_client.get(REDIS_KEY_FACTS_VERSION)
        return str(ver) if ver else "1"
    except Exception:
        return "1"


async def bump_index_version(redis_client: Any) -> int:
    """Increment index_version counter in Redis to invalidate all current document RAG cache entries."""
    if redis_client is None:
        return 1
    try:
        new_ver = await redis_client.incr(REDIS_KEY_INDEX_VERSION)
        logger.info("Bumped Redis index_version to %d", new_ver)
        return int(new_ver)
    except Exception as exc:
        logger.warning("Failed to bump index_version: %s", exc)
        return 1


async def bump_facts_version(redis_client: Any) -> int:
    """Increment facts_version counter in Redis to invalidate all current structured facts cache entries."""
    if redis_client is None:
        return 1
    try:
        new_ver = await redis_client.incr(REDIS_KEY_FACTS_VERSION)
        logger.info("Bumped Redis facts_version to %d", new_ver)
        return int(new_ver)
    except Exception as exc:
        logger.warning("Failed to bump facts_version: %s", exc)
        return 1


async def get_cached_part(
    redis_client: Any,
    mode: str,
    resolved_question: str,
    profile: dict | None = None,
    index_version: str | None = None,
    facts_version: str | None = None,
) -> tuple[str, list[dict]] | None:
    """Retrieve cached factual answer using scoped key. Returns None on miss or bypass."""
    if redis_client is None or not getattr(settings, "RESPONSE_CACHE_ENABLED", True):
        return None
    if mode != "factual":
        return None
    try:
        idx_ver = index_version or await get_index_version(redis_client)
        fac_ver = facts_version or await get_facts_version(redis_client)
        key = make_scoped_cache_key(
            mode=mode,
            resolved_question=resolved_question,
            relevant_profile=profile,
            index_version=idx_ver,
            facts_version=fac_ver,
        )
        raw = await redis_client.get(key)
        key_hash = key.split(":")[-1][:12]
        if raw is None:
            logger.debug("Cache MISS: key_hash=%s", key_hash)
            return None
        data = json.loads(raw)
        logger.info("Cache HIT: key_hash=%s", key_hash)
        return data["answer"], data.get("sources", [])
    except Exception as exc:
        logger.warning("Cache get error (degrading gracefully): %s", exc)
        return None


async def set_cached_part(
    redis_client: Any,
    mode: str,
    resolved_question: str,
    answer: str,
    sources: list[dict],
    profile: dict | None = None,
    part_count: int = 1,
    index_version: str | None = None,
    facts_version: str | None = None,
) -> None:
    """Store cached factual answer with TTL if criteria are satisfied."""
    if redis_client is None or not getattr(settings, "RESPONSE_CACHE_ENABLED", True):
        return
    if not is_cacheable(mode, answer, part_count=part_count):
        return
    try:
        idx_ver = index_version or await get_index_version(redis_client)
        fac_ver = facts_version or await get_facts_version(redis_client)
        key = make_scoped_cache_key(
            mode=mode,
            resolved_question=resolved_question,
            relevant_profile=profile,
            index_version=idx_ver,
            facts_version=fac_ver,
        )
        payload = json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False)
        await redis_client.set(key, payload, ex=_CACHE_TTL_SECONDS)
        key_hash = key.split(":")[-1][:12]
        logger.info("Cache SET: key_hash=%s (TTL=%ds)", key_hash, _CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Cache set error (degrading gracefully): %s", exc)


# ---------------- Backward Compatibility Wrappers ----------------

def make_cache_key(canonical_query: str) -> str:
    """Legacy wrapper for backward-compatibility with existing tests."""
    return make_scoped_cache_key("factual", canonical_query)


async def get_cached_answer(
    redis_client: Any,
    canonical_query: str,
) -> tuple[str, list[dict]] | None:
    """Legacy wrapper."""
    return await get_cached_part(redis_client, mode="factual", resolved_question=canonical_query)


async def set_cached_answer(
    redis_client: Any,
    canonical_query: str,
    answer: str,
    sources: list[dict],
) -> None:
    """Legacy wrapper."""
    await set_cached_part(
        redis_client,
        mode="factual",
        resolved_question=canonical_query,
        answer=answer,
        sources=sources,
        part_count=1,
    )


async def invalidate_cache(redis_client: Any, canonical_query: str) -> None:
    """Delete a cached answer for a specific query."""
    if redis_client is None:
        return
    try:
        key = make_cache_key(canonical_query)
        await redis_client.delete(key)
    except Exception as exc:
        logger.warning("Cache invalidate error: %s", exc)
