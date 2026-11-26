"""Tests for observability endpoint/summary, multi-query diversity, model tiering, structured flows, and parallel post-processing."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.sru_agent import (
    agent,
    config,
    fee_coordinator,
    llm_loop,
    observability,
    postprocess,
    semantic_router,
    structured_flows,
)


def test_observability_summary_and_row_builder():
    records = [
        {
            "detected_intent": "FEE_QUERY",
            "model": "gemini-3.1-flash-lite",
            "response_mode": "model",
            "total_latency_ms": 120.0,
            "generation_latency_ms": 95.0,
            "first_token_ms": 40.0,
            "llm_rounds": 1,
            "prompt_tokens": 500,
            "candidates_tokens": 120,
            "thoughts_tokens": 10,
            "cached_tokens": 300,
            "fallback_decision": False,
        },
        {
            "detected_intent": "FAQ_CACHE",
            "model": None,
            "response_mode": "cache",
            "total_latency_ms": 12.0,
            "generation_latency_ms": 0.0,
            "first_token_ms": 10.0,
            "llm_rounds": 0,
            "prompt_tokens": 0,
            "candidates_tokens": 0,
            "thoughts_tokens": 0,
            "cached_tokens": 0,
            "fallback_decision": False,
        },
        {
            "detected_intent": "GENERAL",
            "model": "gemini-3.5-flash-lite",
            "response_mode": "fallback",
            "total_latency_ms": 300.0,
            "generation_latency_ms": 250.0,
            "first_token_ms": None,
            "llm_rounds": 2,
            "prompt_tokens": 700,
            "candidates_tokens": 150,
            "thoughts_tokens": 0,
            "cached_tokens": 0,
            "fallback_decision": True,
        },
    ]
    summary = observability.compute_telemetry_summary(records)
    assert summary["total_turns"] == 3
    assert summary["p50_total_latency_ms"] == 120.0
    assert summary["p95_total_latency_ms"] == 300.0
    assert summary["total_prompt_tokens"] == 1200
    assert summary["total_cached_tokens"] == 300
    assert summary["cache_hit_rate"] == round(2 / 3, 4)
    assert summary["fallback_rate"] == round(1 / 3, 4)
    assert summary["by_mode"]["cache"] == 1

    row = observability.build_turn_telemetry_row(records[0])
    assert row.detected_intent == "FEE_QUERY"
    assert row.prompt_tokens == 500
    assert row.cached_tokens == 300
    assert row.first_token_ms == 40.0


def test_record_telemetry_persist_db_false_skips_db_write(monkeypatch):
    observability.clear_telemetry()
    called = []
    monkeypatch.setattr(
        observability,
        "_persist_telemetry_to_db",
        lambda t: called.append(t),
    )
    t = observability.PolicyTurnTelemetry(
        session_id="s1", conversation_id="c1", message="hi", detected_intent="GREETING"
    )
    observability.record_policy_telemetry(t, persist=True, persist_db=False)
    assert len(observability.get_recent_telemetry(10)) == 1
    assert called == []


@pytest.mark.asyncio
async def test_admin_telemetry_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.v1.admin import verify_admin_key

    observability.clear_telemetry()
    observability.record_policy_telemetry(
        observability.PolicyTurnTelemetry(
            session_id="sess-test-1",
            conversation_id="conv-1",
            message="What are CSE fees?",
            detected_intent="FEE_QUERY",
            response_mode="model",
            total_latency_ms=85.0,
            prompt_tokens=400,
            candidates_tokens=90,
        ),
        persist=False,
    )
    app.dependency_overrides[verify_admin_key] = lambda: "test-admin"
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/admin/telemetry?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_turns"] >= 1
        assert len(body["recent"]) >= 1
    finally:
        app.dependency_overrides.pop(verify_admin_key, None)


def test_multi_query_decomposition_and_diversity(monkeypatch):
    sub_qs = semantic_router.decompose_multi_questions(
        "1. What are B.Tech CSE fees? 2. What are the hostel curfew timings?"
    )
    assert len(sub_qs) == 2

    # Ensure _hybrid_handbook_context preserves top hits from every sub-question
    async def fake_knowledge_search(q: str):
        ql = q.lower()
        if "hostel" in ql or "curfew" in ql:
            return [{"title": "Hostel Rules", "text": "Hostel curfew is 9:30 PM.", "source": "04_hostel.md"}]
        if "fee" in ql or "cse" in ql:
            return [{"title": "CSE Fees", "text": "B.Tech CSE tuition fee is 1,35,000 per semester.", "source": "fee.json"}]
        # Global query returns 4 unrelated high-ranked items
        return [
            {"title": f"Generic {i}", "text": f"Generic info chunk {i}", "source": "doc.md"}
            for i in range(4)
        ]

    monkeypatch.setattr(agent.tools, "_knowledge_search", fake_knowledge_search)
    monkeypatch.setattr(agent.knowledge, "search", lambda *a, **kw: [])
    ctx = asyncio.run(
        agent._hybrid_handbook_context("What are B.Tech CSE fees? And what are the hostel curfew timings?")
    )
    assert "Hostel curfew" in ctx
    assert "B.Tech CSE tuition fee" in ctx


def test_model_tiering_by_complexity(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODEL_TIERING", True)
    monkeypatch.setattr(config, "AGENT_LITE_MODEL", "gemini-3.1-flash-lite")
    monkeypatch.setattr(config, "AGENT_MODEL", "gemini-3.5-flash-lite")

    lite_models, lite_think, lite_tier = llm_loop.select_model_tier(
        "What is SRU NAAC grade?",
        fallback_models=("gemini-3.5-flash",),
        has_tools=False,
    )
    assert lite_tier == "lite"
    assert lite_think == "MINIMAL"
    assert lite_models[0] == "gemini-3.1-flash-lite"

    std_models, _, std_tier = llm_loop.select_model_tier(
        "Compare B.Tech CSE vs AIML fees and also explain hostel curfew and placements",
        fallback_models=("gemini-3.5-flash",),
        has_tools=True,
        is_compound=True,
        is_compare=True,
    )
    assert std_tier == "standard"
    assert std_models[0] == "gemini-3.5-flash-lite"


def test_structured_flows_and_fee_coordinator():
    flags = fee_coordinator.classify_fee_turn("Calculate my B.Tech CSE scholarship", "GENERAL", is_multi_q=False)
    assert flags["is_scholarship_calc_q"] is True
    assert flags["is_other_fee_inquiry"] is False

    assert fee_coordinator.intake_open({"fee_intake": {"waiting_for": "marks"}}, "92%") is True
    assert fee_coordinator.intake_open({"fee_intake": {"waiting_for": "done"}}, "What is hostel fee?") is False


@pytest.mark.asyncio
async def test_parallel_postprocess_and_batched_commit():
    async def c_coro():
        await asyncio.sleep(0.01)
        return [{"type": "video_recommendations"}]

    async def s_coro():
        await asyncio.sleep(0.01)
        return ["Calculate my fee", "Hostel details"]

    cards, sugg = await postprocess.parallel_cards_and_suggestions(
        cards_coro=c_coro(),
        suggestions_coro=s_coro(),
    )
    assert cards == [{"type": "video_recommendations"}]
    assert sugg == ["Calculate my fee", "Hostel details"]

    # Verify agent_turn_logger batches TurnTelemetry into the same session.commit()
    from app import main as app_main

    added = []
    committed = []

    class FakeSession:
        def add(self, obj):
            added.append(obj)

        async def commit(self):
            committed.append(True)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    fake_conv = SimpleNamespace(id="11111111-1111-1111-1111-111111111111", title="Chat")
    with (
        patch("app.db.session.async_session_factory", return_value=FakeSession()),
        patch("app.services.conversation_service.get_or_create_conversation", AsyncMock(return_value=fake_conv)),
        patch("app.services.conversation_service.add_message", AsyncMock()),
    ):
        await app_main.agent_turn_logger(
            "sess-1234567890123456",
            str(fake_conv.id),
            "What is the CSE fee?",
            "B.Tech CSE fee is ...",
            [],
            telemetry={
                "session_id": "sess-1234567890123456",
                "detected_intent": "FEE_QUERY",
                "response_mode": "model",
                "prompt_tokens": 350,
            },
        )
    assert len(committed) == 1
    assert len(added) == 1
    assert added[0].detected_intent == "FEE_QUERY"
