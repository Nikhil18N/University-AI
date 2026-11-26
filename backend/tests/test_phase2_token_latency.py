"""Phase 2 tests: deterministic fast-path, intent-scoped tool pruning, prompt prefix caching, and parallel tools."""
from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest
from google.genai import types

from app.sru_agent import agent, memory, prompt, tools


class _CountingClient:
    def __init__(self, script=()):
        self.calls = 0
        self.configs = []
        self.script = list(script)
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.calls += 1
        self.configs.append(config)
        if self.script:
            return self.script.pop(0)
        return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
            role="model", parts=[types.Part.from_text(text="SRU Buddy answer.")]))])


@pytest.mark.asyncio
@pytest.mark.parametrize("msg", [
    "hi",
    "hello",
    "thanks!",
    "bye",
    "what is your NAAC grade?",
    "how do I apply?",
    "admissions contact number",
])
async def test_zero_llm_calls_on_small_talk_quick_facts_and_contact_links(msg):
    sid = f"p2-fast-{uuid.uuid4().hex[:8]}"
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    client = _CountingClient()
    events = [ev async for ev in agent.run_agent(msg, sid, client=client, source="typed")]
    assert events[-1]["type"] == "done"
    assert client.calls == 0, f"Expected 0 LLM calls for '{msg}', got {client.calls}"
    assert events[-1]["telemetry"]["llm_rounds"] == 0


def test_intent_scoped_tool_pruning_reduces_schema_tokens():
    full_decl = agent._tool_declarations()
    full_chars = len(json.dumps(full_decl.model_dump(mode="json")))

    queries = [
        "what is the B.Tech CSE fee with 92%?",
        "who is the HOD of CSE?",
        "tell me about hostel facilities",
        "can I join MBA with 55%?",
        "compare CSE vs ECE fees",
    ]
    pruned_chars = []
    for q in queries:
        selected = tools.select_tools_for_message(q)
        assert 1 <= len(selected) <= 4
        decl = agent._tool_declarations(selected)
        pruned_chars.append(len(json.dumps(decl.model_dump(mode="json"))))

    avg_pruned = sum(pruned_chars) / len(pruned_chars)
    reduction_pct = (1.0 - avg_pruned / full_chars) * 100.0
    # Tool schema tokens drop by >=70%, driving >40% total round-1 input token reduction
    assert reduction_pct >= 70.0, f"Expected >=70% tool schema reduction, got {reduction_pct:.1f}%"


def test_system_prompt_has_stable_static_prefix():
    p1 = prompt.build_system_prompt(
        profile={"name": "Asha", "percent": 90},
        variant_id=1,
        used_openings=["Hi Asha!"],
        handbook_passages="Passage A",
        conversation_note="Discussing CSE",
    )
    p2 = prompt.build_system_prompt(
        profile={"name": "Ravi", "percent": 82},
        variant_id=4,
        used_openings=["Hello Ravi!", "Here is the breakdown."],
        handbook_passages="Passage B with different length",
        conversation_note="Discussing MBA",
    )
    # The static prefix up to CURRENT TURN CONTEXT must be byte-for-byte identical
    marker = "CURRENT TURN CONTEXT"
    assert marker in p1 and marker in p2
    assert p1.split(marker)[0] == p2.split(marker)[0]


@pytest.mark.asyncio
async def test_parallel_tool_execution(monkeypatch):
    call_times = []

    async def slow_tool_a(args, ctx):
        t0 = time.perf_counter()
        await asyncio.sleep(0.08)
        call_times.append(("a", t0, time.perf_counter()))
        return {"status": "ok", "info": "A"}

    async def slow_tool_b(args, ctx):
        t0 = time.perf_counter()
        await asyncio.sleep(0.08)
        call_times.append(("b", t0, time.perf_counter()))
        return {"status": "ok", "info": "B"}

    monkeypatch.setitem(tools.TOOLS, "get_program_info", (slow_tool_a, "A", tools.TOOLS["get_program_info"][2]))
    monkeypatch.setitem(tools.TOOLS, "calculate_fee", (slow_tool_b, "B", tools.TOOLS["calculate_fee"][2]))

    fc1 = types.FunctionCall(name="get_program_info", args={"program": "btech_cse"})
    fc2 = types.FunctionCall(name="calculate_fee", args={"program": "btech_cse"})
    resp1 = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part(function_call=fc1), types.Part(function_call=fc2)]))])
    resp2 = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text="Both tools completed.")]))])

    sid = f"p2-par-{uuid.uuid4().hex[:8]}"
    await memory.update_profile(sid, name="Ravi", phone="9876543210", welcome_actions_shown=True)
    client = _CountingClient([resp1, resp2])
    t_start = time.perf_counter()
    events = [ev async for ev in agent.run_agent("CSE program info and fee", sid, client=client, source="typed")]
    elapsed = time.perf_counter() - t_start

    assert events[-1]["type"] == "done"
    assert len(call_times) == 2
    # Overlapping execution: both started before either finished, total time < 0.16s (or close to 0.08s)
    assert elapsed < 0.15 or (max(t[1] for t in call_times) < min(t[2] for t in call_times))
