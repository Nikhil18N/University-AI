"""Phase 4 tests: LLMProvider unification, modularization, multi-worker Redis state, evals, and CSP."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types

from app.providers.base import LLMProvider
from app.services import app_settings, card_service, evaluation_service
from app.sru_agent import config, fee_coordinator, llm_loop, memory, observability, postprocess, tool_runner


class _FakeRedis:
    """In-memory async Redis stand-in shared across simulated workers."""

    def __init__(self):
        self.kv: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.lists: dict[str, list[str]] = {}

    async def get(self, key: str):
        return self.kv.get(key)

    async def set(self, key: str, val: str, ex: int | None = None):
        self.kv[key] = val

    async def delete(self, key: str):
        self.kv.pop(key, None)
        self.sets.pop(key, None)
        self.lists.pop(key, None)

    async def sadd(self, key: str, val: str):
        self.sets.setdefault(key, set()).add(val)

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))

    async def expire(self, key: str, ttl: int):
        return True

    async def lpush(self, key: str, val: str):
        self.lists.setdefault(key, []).insert(0, val)

    async def ltrim(self, key: str, start: int, end: int):
        self.lists[key] = self.lists.get(key, [])[start : end + 1]

    async def lrange(self, key: str, start: int, end: int):
        return self.lists.get(key, [])[start : end + 1]


def test_sru_agent_provider_implements_llm_provider():
    provider = llm_loop.GeminiAgentProvider({"fixed": None, "models": ["gemini-3.5-flash-lite"], "model_idx": 0})
    assert isinstance(provider, LLMProvider)
    assert hasattr(provider, "generate_with_tools")
    assert hasattr(provider, "stream_with_tools")


def test_modular_packages_and_fee_coordinator():
    assert fee_coordinator.is_active_fee_step({"fee_eval": {"active": True, "final_shown": False}}) is True
    assert fee_coordinator.is_active_fee_step({"fee_eval": {"active": True, "final_shown": True}}) is False
    assert fee_coordinator.active_fee_program({"active_program": "btech_cse"}) == "btech_cse"
    assert tool_runner.tool_declarations(["calculate_fee"]) is not None
    assert "calculate_fee" in postprocess.CARD_TOOLS


@pytest.mark.asyncio
async def test_multi_worker_redis_state_consistency(monkeypatch):
    shared_redis = _FakeRedis()
    monkeypatch.setattr(memory, "_shared_redis", shared_redis)
    monkeypatch.setattr(config, "AGENT_LOCAL_CACHE", False)
    monkeypatch.setattr(config, "AGENT_BACKGROUND_WRITES", False)

    sid = f"mw-{uuid.uuid4().hex[:8]}"

    # Worker 1 writes profile, shown card, and telemetry
    await memory.update_profile(sid, name="Asha", program_interest="btech_cse")
    await card_service.record_session_card_async(sid, "fee_breakdown")
    observability.record_policy_telemetry(
        observability.PolicyTurnTelemetry(
            session_id=sid, conversation_id=None, message="hi", detected_intent="GREETING", response_mode="deterministic"
        )
    )
    await memory.shutdown_flush(timeout=2.0)

    # Simulate Worker 2: wipe process-local caches completely
    memory._hot.clear()
    memory._local.clear()
    card_service._SESSION_SHOWN_CARDS.clear()
    observability.clear_telemetry()

    # Worker 2 reads from shared Redis
    prof = await memory.get_profile(sid)
    assert prof["name"] == "Asha"
    assert prof["program_interest"] == "btech_cse"

    shown = await card_service.get_session_shown_cards_async(sid)
    assert "fee_breakdown" in shown

    recent = await observability.get_recent_telemetry_async(limit=5)
    assert any(r["session_id"] == sid for r in recent)


@pytest.mark.asyncio
async def test_evaluation_service_runs_against_sru_agent(monkeypatch, tmp_path):
    ds = tmp_path / "eval.jsonl"
    ds.write_text(json.dumps({
        "test_id": "T1",
        "category": "admissions",
        "question": "What is the campus size?",
        "expected_keywords": ["170-acre"],
        "negative_keywords": ["150-acre"],
    }) + "\n", encoding="utf-8")

    async def fake_query(question: str, test_id: str):
        return "SR University has a 170-acre campus in Warangal.", [{"document_id": "14", "title": "Profile"}]

    recorded = []

    async def fake_record(**kwargs):
        recorded.append(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(evaluation_service, "_query_sru_agent", fake_query)
    monkeypatch.setattr(evaluation_service, "record_evaluation", fake_record)

    summary = await evaluation_service.run_benchmark_suite(db=None, dataset_path=ds)
    assert summary["total_tests"] == 1
    assert summary["passed_tests"] == 1
    assert recorded[0]["actual_answer"].startswith("SR University has a 170-acre")


def test_vercel_csp_pins_exact_render_origin():
    vercel_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "vercel.json"
    data = json.loads(vercel_path.read_text(encoding="utf-8"))
    csp_header = next(
        h["value"]
        for rule in data["headers"]
        for h in rule["headers"]
        if h["key"] == "Content-Security-Policy"
    )
    assert "https://university-ai-luwe.onrender.com" in csp_header
    assert "https://*.onrender.com" not in csp_header
