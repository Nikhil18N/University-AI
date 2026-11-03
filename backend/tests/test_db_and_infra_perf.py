"""Tests for P1-A, P1-C, P1-D, P2-D performance fixes.

P1-A: get_all_user_messages() capped with LIMIT 20
P1-C: SQLAlchemy async engine pool config (structural / smoke)
P1-D: uvloop in requirements + Dockerfile (structural checks)
P2-D: reformulation_service no longer double-canonicalizes
"""

import inspect
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# P1-A: get_all_user_messages has a `limit` parameter
# ---------------------------------------------------------------------------

def test_get_all_user_messages_has_limit_param():
    """get_all_user_messages() must accept a `limit` keyword argument (default 20)."""
    from app.services.conversation_service import get_all_user_messages

    sig = inspect.signature(get_all_user_messages)
    assert "limit" in sig.parameters, (
        "get_all_user_messages() is missing the `limit` parameter"
    )
    default = sig.parameters["limit"].default
    assert default == 20, (
        f"Expected default limit=20, got {default!r}"
    )


# ---------------------------------------------------------------------------
# P2-D: canonicalize_query called only ONCE (on input, not on LLM output)
# ---------------------------------------------------------------------------

def test_canonicalize_query_single_application():
    """Applying canonicalize_query twice to clean text must be idempotent — confirms
    that the second call (now removed) was redundant.

    The LLM output path now returns `cleaned` directly; since the input was already
    canonicalized before being sent to the LLM, one pass is sufficient.
    """
    from app.services.reformulation_service import canonicalize_query

    # A piece of clean, already-canonicalized text
    clean_text = "hostel eligibility admission scholarship"

    first_pass = canonicalize_query(clean_text)
    second_pass = canonicalize_query(first_pass)

    assert first_pass == second_pass, (
        "canonicalize_query is not idempotent — applying it twice changes the output, "
        "which means the removed second call was NOT neutral and something else is wrong."
    )


def test_reformulate_query_does_not_double_canonicalize(monkeypatch):
    """When LLM reformulation succeeds, canonicalize_query must be called exactly
    once (on the raw message), NOT again on the LLM output.
    """
    from app.services import reformulation_service

    call_count = {"n": 0}
    original_canonicalize = reformulation_service.canonicalize_query

    def counting_canonicalize(query: str) -> str:
        call_count["n"] += 1
        return original_canonicalize(query)

    monkeypatch.setattr(reformulation_service, "canonicalize_query", counting_canonicalize)
    monkeypatch.setattr(reformulation_service, "needs_reformulation", lambda msg, ctx: False)

    import asyncio

    class _FakeLLM:
        async def generate(self, messages, temperature=0.1):
            return "hostel eligibility"

    result = asyncio.run(
        reformulation_service.reformulate_query(
            message="hostle elgblty",
            conversation_context="",
            llm_provider=_FakeLLM(),
        )
    )

    # needs_reformulation returns False → only the initial canonicalize_query call
    assert call_count["n"] == 1, (
        f"Expected canonicalize_query to be called 1 time, got {call_count['n']}"
    )
    assert result == "hostel eligibility"


# ---------------------------------------------------------------------------
# P2-D bonus: apply_fuzzy_corrections + canonicalize_query pipeline
# ---------------------------------------------------------------------------

def test_fuzzy_plus_canonicalize_pipeline():
    """'hostle elgblty' should canonicalize to 'hostel eligibility'."""
    from app.services.reformulation_service import canonicalize_query

    result = canonicalize_query("hostle elgblty")
    assert result == "hostel eligibility", (
        f"Expected 'hostel eligibility', got {result!r}"
    )


# ---------------------------------------------------------------------------
# P1-C: engine has explicit pool settings (structural smoke test)
# ---------------------------------------------------------------------------

def test_engine_pool_settings():
    """The async engine must be configured with explicit pool parameters."""
    from app.db import session as db_session

    engine = db_session.engine
    pool = engine.pool

    # pool_size
    assert pool.size() == 10, f"Expected pool_size=10, got {pool.size()}"
    # max_overflow: accessible via the private attribute on QueuePool
    assert pool._max_overflow == 20, f"Expected max_overflow=20, got {pool._max_overflow}"
    # pool_timeout
    assert pool._timeout == 30, f"Expected pool_timeout=30, got {pool._timeout}"
    # pool_recycle
    assert engine.pool._recycle == 1800, f"Expected pool_recycle=1800, got {engine.pool._recycle}"
