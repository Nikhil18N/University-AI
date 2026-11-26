"""Phase 3 tests: hybrid RRF retrieval, handbook sync, policy-safe FAQ cache, and profile store."""
from __future__ import annotations

import uuid

import pytest
from google.genai import types

from app.main import _merge_evidence
from app.services import agent_profile_store
from app.sru_agent import agent, memory, tools
from scripts import ingest_handbook_docs


class _FakeCollection:
    def __init__(self, docs):
        self._docs = dict(docs)
        self.deleted = []

    def get(self, include=None, where=None):
        return {"ids": list(self._docs.keys()), "documents": list(self._docs.values())}

    def delete(self, ids):
        self.deleted.extend(ids)
        for cid in ids:
            self._docs.pop(cid, None)


class _CacheableFakeModel:
    enable_faq_cache = True

    def __init__(self):
        self.calls = 0
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.calls += 1
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(
                role="model", parts=[types.Part.from_text(text="SR University has a 170-acre campus in Warangal.")]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100, candidates_token_count=20, thoughts_token_count=0, cached_content_token_count=0
            ),
        )


def test_handbook_docs_include_13_14_15():
    files = {d["file"] for d in ingest_handbook_docs.HANDBOOK_DOCS}
    assert "13_laboratories_and_research_centers.md" in files
    assert "14_university_overview_and_institutional_profile.md" in files
    assert "15_events_clubs_and_student_life_nov2026.md" in files


def test_purge_stale_handbook_chunks():
    col = _FakeCollection({
        "c1": "Fee structure for 2025-26 academic year",
        "c2": "2026-27 merit scholarship bands",
        "c3": "SRU has a 150-acre campus",
        "c4": "SR University is located on a 170-acre campus for 2027-28",
    })
    removed = ingest_handbook_docs.purge_stale_handbook_chunks(col)
    assert removed == 3
    assert set(col.deleted) == {"c1", "c2", "c3"}


def test_rrf_merge_preserves_admin_uploaded_docs():
    semantic = [
        {"title": "Admin Circular 2027.pdf", "text": "Special shuttle bus from Hanamkonda starts at 7:30 AM.", "retrieval": "semantic"},
        {"title": "Handbook", "text": "SRU campus has modern classrooms.", "retrieval": "semantic"},
    ]
    lexical = [
        {"title": "Handbook", "text": "SRU campus has modern classrooms.", "retrieval": "keyword"},
        {"title": "Handbook Transport", "text": "University buses cover Warangal and Kazipet.", "retrieval": "keyword"},
    ]
    merged = _merge_evidence(semantic, lexical, limit=4)
    titles = [m["title"] for m in merged]
    assert "Admin Circular 2027.pdf" in titles
    # Overlapping item in both semantic + lexical ranks highest under RRF
    assert merged[0]["title"] == "Handbook"
    assert "rrf_score" in merged[0]


@pytest.mark.asyncio
async def test_hybrid_handbook_context_includes_admin_docs(monkeypatch):
    async def fake_search(query):
        return [{"title": "Admin_Policy_2027.pdf", "text": "Admin uploaded: Hostel laundry token is issued monthly.", "source": "Admin_Policy_2027.pdf"}]

    monkeypatch.setattr(tools, "_knowledge_search", fake_search)
    ctx = await agent._hybrid_handbook_context("hostel laundry token")
    assert "Admin_Policy_2027.pdf" in ctx
    assert "Hostel laundry token" in ctx


def test_faq_cache_key_excludes_pii_and_active_flows():
    # PII excluded
    assert memory.faq_cache_key("call me on 9876543210") is None
    assert memory.faq_cache_key("my email is test@example.com") is None
    # Active multi-step flows excluded
    assert memory.faq_cache_key("what is the campus size?", conv_state={"pending_action": "callback"}) is None
    assert memory.faq_cache_key("what is the campus size?", conv_state={"fee_eval": {"active": True}}) is None
    # Key ignores PII profile fields (name, phone)
    k1 = memory.faq_cache_key("what is the campus size?", profile={"name": "Asha", "phone": "9876543210", "program_interest": "btech_cse"})
    k2 = memory.faq_cache_key("what is the campus size?", profile={"name": "Ravi", "phone": "9123456789", "program_interest": "btech_cse"})
    assert k1 is not None and k1 == k2


@pytest.mark.asyncio
async def test_repeated_faq_hits_cache_at_zero_llm_tokens():
    client = _CacheableFakeModel()
    s1 = f"p3-c1-{uuid.uuid4().hex[:8]}"
    s2 = f"p3-c2-{uuid.uuid4().hex[:8]}"
    q = f"tell me about the innovation ecosystem and startups at SRU {uuid.uuid4().hex[:6]}"

    ev1 = [e async for e in agent.run_agent(q, s1, client=client, source="typed")]
    assert ev1[-1]["type"] == "done"
    assert client.calls == 1

    ev2 = [e async for e in agent.run_agent(q, s2, client=client, source="typed")]
    assert ev2[-1]["type"] == "done"
    assert client.calls == 1  # 2nd call hit cache at 0 LLM calls!
    assert ev2[-1]["telemetry"]["llm_rounds"] == 0
    assert ev2[-1]["telemetry"]["response_mode"] == "cache"


def test_agent_profile_store_allows_values_over_255_chars():
    long_val = "x" * 400
    durable = agent_profile_store._durable({"saved_academic": long_val})
    assert "saved_academic" in durable
    assert len(durable["saved_academic"]) > 255
