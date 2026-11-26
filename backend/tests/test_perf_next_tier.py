"""Unit tests for next-tier performance optimizations: embedding cache, Redis MGET, parallel retrieval."""
from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest

from app import main as app_main
from app.sru_agent import agent, memory, tools


class _FakeMgetRedis:
    def __init__(self):
        self.kv: dict[str, str] = {}
        self.mget_calls = 0

    async def get(self, key: str):
        return self.kv.get(key)

    async def set(self, key: str, val: str, ex: int | None = None):
        self.kv[key] = val

    async def mget(self, keys: list[str]):
        self.mget_calls += 1
        return [self.kv.get(k) for k in keys]


@pytest.mark.asyncio
async def test_cached_embed_query_avoids_duplicate_provider_calls(monkeypatch):
    app_main._EMB_LOCAL_CACHE.clear()
    fake_redis = _FakeMgetRedis()
    monkeypatch.setattr(memory, "_shared_redis", fake_redis)

    calls = 0

    class _FakeEmbedder:
        async def embed_single(self, text: str):
            nonlocal calls
            calls += 1
            return [0.1, 0.2, 0.3]

    from app.api.v1 import deps
    monkeypatch.setattr(deps, "get_embedding_provider", lambda: _FakeEmbedder())

    q = f"hostel curfew timings {uuid.uuid4().hex[:6]}"
    v1 = await app_main._cached_embed_query(q)
    # Clear local cache to verify Redis cache hit on second worker
    app_main._EMB_LOCAL_CACHE.clear()
    v2 = await app_main._cached_embed_query(q.upper() + "  ")
    assert v1 == v2 == [0.1, 0.2, 0.3]
    assert calls == 1


@pytest.mark.asyncio
async def test_warm_turn_keys_uses_single_mget(monkeypatch):
    fake_redis = _FakeMgetRedis()
    sid = f"mget-{uuid.uuid4().hex[:8]}"
    cid = "conv-1"
    fake_redis.kv[memory._profile_key(sid)] = json.dumps({"name": "Asha"})
    fake_redis.kv[memory._history_key(sid, cid)] = json.dumps([{"role": "user", "text": "hi"}])
    fake_redis.kv[memory._state_key(sid, cid)] = json.dumps({"active_program": "btech_cse"})

    monkeypatch.setattr(memory, "_shared_redis", fake_redis)
    memory._hot.clear()
    memory._local.clear()

    await memory.warm_turn_keys(sid, cid)
    assert fake_redis.mget_calls == 1
    assert (await memory.get_profile(sid))["name"] == "Asha"
    assert (await memory.get_conversation_state(sid, cid))["active_program"] == "btech_cse"


@pytest.mark.asyncio
async def test_hybrid_handbook_context_fans_out_subquestions_concurrently(monkeypatch):
    timings = []

    async def slow_search(q: str):
        t0 = time.perf_counter()
        await asyncio.sleep(0.06)
        timings.append((t0, time.perf_counter()))
        return [{"title": f"Doc for {q}", "text": f"Verified answer for {q}", "source": "Admin.pdf"}]

    monkeypatch.setattr(tools, "_knowledge_search", slow_search)
    t_start = time.perf_counter()
    ctx = await agent._hybrid_handbook_context("what are the hostel fees and what are the placements?")
    elapsed = time.perf_counter() - t_start

    assert "Verified answer" in ctx
    assert len(timings) >= 2
    # Concurrent fan-out: overlaps instead of running sequentially
    assert elapsed < len(timings) * 0.055


@pytest.mark.asyncio
async def test_incremental_sensitive_detail_streaming_releases_verified_lines():
    from google.genai import types

    class _StreamingVerifiedFake:
        def __init__(self):
            self.aio = self
            self.models = self

        async def generate_content_stream(self, model, contents, config):
            async def _gen():
                yield types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
                    role="model", parts=[types.Part.from_text(text="B.Tech CSE tuition is ₹3,40,000 per year.\n")]))])
                yield types.GenerateContentResponse(
                    candidates=[types.Candidate(
                        content=types.Content(role="model", parts=[types.Part.from_text(text="Hostel is optional.")]),
                        finish_reason="STOP")],
                    usage_metadata=types.GenerateContentResponseUsageMetadata(
                        prompt_token_count=100, candidates_token_count=20, thoughts_token_count=0, cached_content_token_count=0
                    ),
                )
            return _gen()

    sid = f"inc-{uuid.uuid4().hex[:8]}"
    await memory.update_profile(sid, name="Asha", phone="9876543210", welcome_actions_shown=True)
    events = [ev async for ev in agent.run_agent("what is the B.Tech CSE tuition fee?", sid, client=_StreamingVerifiedFake(), source="typed")]
    token_deltas = [ev["delta"] for ev in events if ev["type"] == "token"]
    # The verified ₹3,40,000 line is released incrementally before the stream ends
    assert any("₹3,40,000" in d for d in token_deltas)
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_explicit_prompt_cache_reuse_and_apply():
    from types import SimpleNamespace
    from google.genai import types
    from app.sru_agent import llm_loop

    llm_loop.invalidate_prompt_cache()
    created_calls = 0

    class _FakeCaches:
        async def create(self, model, config):
            nonlocal created_calls
            created_calls += 1
            return SimpleNamespace(name=f"cachedContents/test-{created_calls}")

    fake_client = SimpleNamespace(aio=SimpleNamespace(caches=_FakeCaches()))
    c1 = await llm_loop.get_or_create_prompt_cache(fake_client, "gemini-3.5-flash-lite", "STATIC PREFIX", cache_key_tag="t1")
    c2 = await llm_loop.get_or_create_prompt_cache(fake_client, "gemini-3.5-flash-lite", "STATIC PREFIX", cache_key_tag="t1")
    assert c1 == c2 == "cachedContents/test-1"
    assert created_calls == 1

    cfg = types.GenerateContentConfig(system_instruction="FULL", tools=[])
    updated = llm_loop._apply_explicit_cache(cfg, {"dynamic_suffix": "DYNAMIC"}, c1)
    assert updated.cached_content == c1
    assert updated.system_instruction == "DYNAMIC"
    assert updated.tools is None


@pytest.mark.asyncio
async def test_speculative_one_round_fee_execution():
    from google.genai import types

    class _OneRoundModel:
        def __init__(self):
            self.calls = 0
            self.configs = []
            self.aio = self
            self.models = self

        async def generate_content(self, model, contents, config):
            self.calls += 1
            self.configs.append(config)
            return types.GenerateContentResponse(
                candidates=[types.Candidate(content=types.Content(
                    role="model", parts=[types.Part.from_text(text="For B.Tech CSE with 92%, you get a 30% scholarship.")]))],
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=100, candidates_token_count=20, thoughts_token_count=0, cached_content_token_count=0
                ),
            )

    sid = f"spec-{uuid.uuid4().hex[:8]}"
    await memory.update_profile(sid, name="Asha", phone="9876543210", welcome_actions_shown=True)
    m = _OneRoundModel()
    events = [ev async for ev in agent.run_agent("what is B.Tech CSE fee with 92%?", sid, client=m, source="typed")]
    done = events[-1]
    assert done["type"] == "done"
    assert m.calls == 1
    assert m.configs[0].tool_config.function_calling_config.mode == "NONE"
    assert any(c.get("type") == "calculate_fee" for c in done["cards"])
