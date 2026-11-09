"""Unit tests for response caching service (P0 Hardening T1)."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.config import settings
from app.services.cache_service import (
    CACHE_SCHEMA_VERSION,
    REDIS_KEY_INDEX_VERSION,
    REDIS_KEY_FACTS_VERSION,
    bump_facts_version,
    bump_index_version,
    get_cached_answer,
    get_cached_part,
    get_facts_version,
    get_index_version,
    invalidate_cache,
    is_cacheable,
    make_cache_key,
    make_scoped_cache_key,
    normalize_relevant_profile,
    set_cached_answer,
    set_cached_part,
)


def test_make_cache_key_deterministic():
    key1 = make_cache_key("What is the hostel fee?")
    key2 = make_cache_key("what is the hostel fee?  ")
    assert key1 == key2
    assert key1.startswith(f"sru:rag:{CACHE_SCHEMA_VERSION}:")


def test_make_cache_key_different_for_different_queries():
    key1 = make_cache_key("What is the hostel fee?")
    key2 = make_cache_key("What are the placement packages?")
    assert key1 != key2


def test_resolved_pronouns_collision_prevention():
    """Two sessions sending identical raw string 'what about its fees?' produce different keys
    after router pronoun resolution."""
    raw_query = "what about its fees?"
    resolved_q_cse = "what are the fees for b.tech cse?"
    resolved_q_mba = "what are the fees for mba?"

    key_cse = make_scoped_cache_key("factual", resolved_q_cse, {"degree": "b.tech", "branch": "cse"})
    key_mba = make_scoped_cache_key("factual", resolved_q_mba, {"degree": "mba"})

    assert key_cse != key_mba


def test_profile_degree_change_changes_factual_cache_key():
    """Changing student profile program/branch alters the factual cache key."""
    q = "what are the fees?"
    key_btech = make_scoped_cache_key("factual", q, {"branch": "cse"})
    key_mech = make_scoped_cache_key("factual", q, {"branch": "mechanical"})
    assert key_btech != key_mech


def test_profile_interests_do_not_alter_factual_cache_key():
    """Student profile interests are excluded from factual cache keys."""
    q = "what is the minimum attendance?"
    key1 = make_scoped_cache_key("factual", q, {"interests": ["robotics", "ai"]})
    key2 = make_scoped_cache_key("factual", q, {"interests": ["sports", "music"]})
    assert key1 == key2


def test_mode_gating_is_cacheable():
    """Only factual mode is cacheable. Persuasive, chitchat, sensitive, out_of_scope are never cached."""
    assert is_cacheable("factual", "The annual fee is ₹1,00,000.", part_count=1) is True
    assert is_cacheable("persuasive", "SRU offers top labs and great opportunities.", part_count=1) is False
    assert is_cacheable("chitchat", "Hey there! How can I help you?", part_count=1) is False
    assert is_cacheable("sensitive", "Please reach out to Tele-MANAS at 14416.", part_count=1) is False
    assert is_cacheable("out_of_scope", "I can only help with SR University questions.", part_count=1) is False


def test_multi_part_replies_never_cached():
    """Merged multi-part answers (part_count > 1) are never cached."""
    assert is_cacheable("factual", "The fee is ₹1,00,000.", part_count=2) is False


def test_clarifying_question_to_student_never_cached():
    """Answers that ask a clarifying question back to the student are never cached."""
    ans_with_question = "Which program are you interested in so I can provide the fee?"
    assert is_cacheable("factual", ans_with_question, part_count=1) is False
    assert is_cacheable("factual", "Could you specify if you want AC or non-AC hostel?", part_count=1) is False


def test_validator_fallback_block_never_cached():
    """Answers containing the validator block or ungrounded warning are never cached."""
    blocked = "I couldn't verify those details against our official sources, so I'd rather not guess."
    assert is_cacheable("factual", blocked, part_count=1) is False


def test_version_bump_invalidates_cache_key():
    """Bumping index_version or facts_version produces completely different keys."""
    q = "what is the highest package?"
    key_v1 = make_scoped_cache_key("factual", q, index_version="1", facts_version="1")
    key_idx_bump = make_scoped_cache_key("factual", q, index_version="2", facts_version="1")
    key_facts_bump = make_scoped_cache_key("factual", q, index_version="1", facts_version="2")

    assert key_v1 != key_idx_bump
    assert key_v1 != key_facts_bump
    assert key_idx_bump != key_facts_bump


@pytest.mark.asyncio
async def test_get_cached_answer_none_client():
    res = await get_cached_answer(None, "sample query")
    assert res is None


@pytest.mark.asyncio
async def test_set_cached_answer_none_client():
    await set_cached_answer(None, "sample query", "sample answer", [])


@pytest.mark.asyncio
async def test_get_cached_part_hit():
    mock_redis = MagicMock()
    stored = {"answer": "Tuition is 1.4L per year.", "sources": [{"title": "Fee Doc"}]}
    mock_redis.get = AsyncMock(return_value=json.dumps(stored))

    result = await get_cached_part(mock_redis, mode="factual", resolved_question="what is the tuition fee?")
    assert result is not None
    answer, sources = result
    assert answer == "Tuition is 1.4L per year."
    assert len(sources) == 1
    assert sources[0]["title"] == "Fee Doc"


@pytest.mark.asyncio
async def test_get_cached_part_miss():
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)

    result = await get_cached_part(mock_redis, mode="factual", resolved_question="unknown query")
    assert result is None


@pytest.mark.asyncio
async def test_get_cached_part_persuasive_skipped():
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"answer": "test"}))

    # Should immediately return None without calling redis.get
    result = await get_cached_part(mock_redis, mode="persuasive", resolved_question="why join sru?")
    assert result is None
    mock_redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_bump_index_and_facts_version():
    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(side_effect=[2, 3])

    new_idx = await bump_index_version(mock_redis)
    new_facts = await bump_facts_version(mock_redis)

    assert new_idx == 2
    assert new_facts == 3
    assert mock_redis.incr.call_count == 2


@pytest.mark.asyncio
async def test_cache_disabled_setting(monkeypatch):
    monkeypatch.setattr(settings, "RESPONSE_CACHE_ENABLED", False)
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"answer": "abc"}))

    res = await get_cached_part(mock_redis, mode="factual", resolved_question="any query")
    assert res is None
    mock_redis.get.assert_not_called()
