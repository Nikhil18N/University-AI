"""Phase 1 tests: usage_metadata extraction, all-path telemetry, guardrail slabs, and hostel curfew."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from google.genai import types

from app.providers.gemini import GeminiProvider
from app.services.guardrail_service import KNOWN_POLICY_PERCENTAGES
from app.sru_agent import agent, memory, observability


class _UsageFakeModel:
    def __init__(self, streaming: bool = False):
        self.streaming = streaming
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(
                role="model", parts=[types.Part.from_text(text="SR University offers B.Tech CSE.")]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=120,
                candidates_token_count=35,
                thoughts_token_count=10,
                cached_content_token_count=40,
            ),
        )

    async def generate_content_stream(self, model, contents, config):
        async def _gen():
            yield types.GenerateContentResponse(
                candidates=[types.Candidate(content=types.Content(
                    role="model", parts=[types.Part.from_text(text="SR University ")]))]
            )
            yield types.GenerateContentResponse(
                candidates=[types.Candidate(
                    content=types.Content(role="model", parts=[types.Part.from_text(text="offers B.Tech CSE.")]),
                    finish_reason="STOP")],
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=200,
                    candidates_token_count=45,
                    thoughts_token_count=5,
                    cached_content_token_count=80,
                ),
            )
        return _gen()


def test_guardrail_known_policy_percentages():
    for slab in ("10%", "15%", "20%", "25%", "30%", "40%", "50%", "55%", "75%", "100%"):
        assert slab in KNOWN_POLICY_PERCENTAGES
    assert "60%" not in KNOWN_POLICY_PERCENTAGES
    assert "65%" not in KNOWN_POLICY_PERCENTAGES


def test_handbook_first_year_curfew_is_830_pm():
    doc = Path(__file__).resolve().parent.parent / "data" / "handbook" / "04_hostels_rules_and_discipline_code.md"
    text = doc.read_text(encoding="utf-8")
    assert "8:30 PM" in text


def test_gemini_provider_extract_usage():
    usage = GeminiProvider._extract_usage({
        "usageMetadata": {
            "promptTokenCount": 150,
            "candidatesTokenCount": 42,
            "thoughtsTokenCount": 8,
            "cachedContentTokenCount": 50,
        }
    })
    assert usage == {
        "prompt_token_count": 150,
        "candidates_token_count": 42,
        "thoughts_token_count": 8,
        "cached_content_token_count": 50,
    }


@pytest.mark.asyncio
async def test_telemetry_captured_on_llm_and_deterministic_turns(monkeypatch):
    observability.clear_telemetry()
    sid = f"obs-{uuid.uuid4().hex[:10]}"
    await memory.update_profile(sid, name="Asha", phone="9876543210", welcome_actions_shown=True)

    # 1. Deterministic _say() turn (button / structured)
    [det_done] = [
        ev async for ev in agent.run_agent("Calculate my scholarship", sid, source="button")
        if ev["type"] == "done"
    ]
    recent = observability.get_recent_telemetry(limit=5)
    assert len(recent) >= 1
    assert recent[-1]["response_mode"] == "deterministic"
    assert recent[-1]["llm_rounds"] == 0
    assert det_done.get("telemetry") is not None

    # 2. LLM turn (non-streaming generate_content)
    m_sync = _UsageFakeModel()
    delattr(_UsageFakeModel, "generate_content_stream")
    try:
        [llm_done] = [
            ev async for ev in agent.run_agent("Tell me about SRU library", sid, client=m_sync, source="typed")
            if ev["type"] == "done"
        ]
    finally:
        # Restore generate_content_stream for next assertion
        _UsageFakeModel.generate_content_stream = _UsageFakeModel.__dict__.get("generate_content_stream") or (
            lambda self, model, contents, config: None
        )
    t_llm = llm_done["telemetry"]
    assert t_llm["llm_rounds"] == 1
    assert t_llm["prompt_tokens"] == 120
    assert t_llm["candidates_tokens"] == 35
    assert t_llm["thoughts_tokens"] == 10
    assert t_llm["cached_tokens"] == 40
    assert len(t_llm["round_latencies_ms"]) == 1
