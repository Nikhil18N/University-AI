"""Tests for Task T10: Facts vs Why-Us (Highlights) Collection Separation."""

import pytest

from app.config import settings
from app.db.chroma import get_chroma_client
from app.providers.factory import create_embedding_provider, create_llm_provider
from app.services.rag_service import RAGService
from scripts.split_chroma_collections import HIGHLIGHT_TITLES


def test_sru_facts_and_highlights_collections_populated():
    """Verify that sru_facts and sru_highlights collections are populated with distinct, non-overlapping chunks."""
    client = get_chroma_client()
    facts_coll = client.get_collection(settings.CHROMA_FACTS_COLLECTION)
    high_coll = client.get_collection(settings.CHROMA_HIGHLIGHTS_COLLECTION)

    assert facts_coll.count() == 95, f"Expected 95 facts chunks, got {facts_coll.count()}"
    assert high_coll.count() == 67, f"Expected 67 highlights chunks, got {high_coll.count()}"

    # Verify metadata tagging
    facts_data = facts_coll.get(include=["metadatas"])
    for meta in facts_data["metadatas"]:
        assert meta.get("scope") == "facts"
        assert meta.get("title") not in HIGHLIGHT_TITLES

    high_data = high_coll.get(include=["metadatas"])
    for meta in high_data["metadatas"]:
        assert meta.get("scope") == "highlights"
        assert meta.get("title") in HIGHLIGHT_TITLES


@pytest.mark.asyncio
async def test_factual_retrieval_receives_zero_highlights():
    """A query scoped to 'facts' must NEVER receive any highlights or promotional chunks."""
    from unittest.mock import AsyncMock, MagicMock

    llm = MagicMock()
    embed = MagicMock()
    embed.embed_single = AsyncMock(return_value=[0.01] * 3072)
    rag = RAGService(llm_provider=llm, embedding_provider=embed)

    # Ask a query that might appeal to highlights if unpartitioned
    chunks = await rag.retrieve("Tell me about placements, rankings, and awards", top_k=5, scope="facts")

    assert len(chunks) > 0
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        title = meta.get("title", "")
        scope = meta.get("scope", "")
        assert scope == "facts", f"Expected scope='facts', got '{scope}' for title '{title}'"
        assert title not in HIGHLIGHT_TITLES, f"Highlights document '{title}' leaked into factual retrieval"


@pytest.mark.asyncio
async def test_persuasive_retrieval_receives_zero_factual_policy():
    """A query scoped to 'highlights' must NEVER receive raw regulatory or policy facts."""
    from unittest.mock import AsyncMock, MagicMock

    llm = MagicMock()
    embed = MagicMock()
    embed.embed_single = AsyncMock(return_value=[0.01] * 3072)
    rag = RAGService(llm_provider=llm, embedding_provider=embed)

    chunks = await rag.retrieve("Why choose SR University for Computer Science?", top_k=5, scope="highlights")

    assert len(chunks) > 0
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        title = meta.get("title", "")
        scope = meta.get("scope", "")
        assert scope == "highlights", f"Expected scope='highlights', got '{scope}' for title '{title}'"
        assert title in HIGHLIGHT_TITLES, f"Factual document '{title}' leaked into highlights retrieval"
