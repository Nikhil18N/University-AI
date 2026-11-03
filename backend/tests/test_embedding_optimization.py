"""Tests for P0-A and P1-B embedding / exemplar optimizations.

P0-A: retrieve_with_embedding() returns the computed embedding so callers can
      reuse it in prepare_rag_request() / find_matching_exemplar(), avoiding a
      second embed_single() API round-trip.

P1-B: find_matching_exemplar() returns None immediately (without calling
      embed_single()) when the cached _exemplar_count is 0, saving 300-800ms
      per request in early production.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_EMBEDDING = [0.1, 0.2, 0.3, 0.4]


def _make_embedding_provider(embedding: list[float] = FAKE_EMBEDDING) -> MagicMock:
    provider = MagicMock()
    provider.embed_single = AsyncMock(return_value=embedding)
    return provider


def _make_chroma_collection(count: int = 0) -> MagicMock:
    col = MagicMock()
    col.count.return_value = count
    col.query.return_value = {"metadatas": [], "distances": []}
    return col


def _make_chroma_client(collection: MagicMock) -> MagicMock:
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client


# ---------------------------------------------------------------------------
# Test 1 — retrieve_with_embedding() returns (list[dict], list[float])
# ---------------------------------------------------------------------------

class TestRetrieveWithEmbedding:
    """RAGService.retrieve_with_embedding() must return (chunks, embedding)."""

    def _make_rag_service(self, embedding_provider, chroma_collection):
        """Build a RAGService with all external deps mocked."""
        from app.config import settings  # noqa: F401  — loaded for side-effects

        with patch("app.db.chroma.get_chroma_client") as mock_gc:
            chroma_client = _make_chroma_client(chroma_collection)
            mock_gc.return_value = chroma_client

            from app.services.rag_service import RAGService
            llm = MagicMock()
            service = RAGService(llm_provider=llm, embedding_provider=embedding_provider)
        return service

    def test_returns_tuple_of_chunks_and_embedding(self):
        embedding_provider = _make_embedding_provider()

        mock_collection = _make_chroma_collection()
        mock_collection.query.return_value = {
            "documents": [["Admission requires 60% in PCM."]],
            "metadatas": [[{"section": "Admissions", "title": "UG Guide"}]],
            "distances": [[0.1]],
        }

        service = self._make_rag_service(embedding_provider, mock_collection)

        result = asyncio.run(service.retrieve_with_embedding("What are admission requirements?"))

        assert isinstance(result, tuple), "Should return a tuple"
        assert len(result) == 2, "Tuple should have exactly two elements"

        chunks, embedding = result

        # chunks is a list of dicts
        assert isinstance(chunks, list)
        assert len(chunks) == 1
        assert "content" in chunks[0]

        # embedding is a non-empty list of floats
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) > 0, "Embedding list must not be empty"
        assert all(isinstance(v, float) for v in embedding), "Embedding values should be floats"

    def test_retrieve_is_consistent_with_retrieve_with_embedding(self):
        """retrieve() should return the same chunks as retrieve_with_embedding()."""
        embedding_provider = _make_embedding_provider()

        mock_collection = _make_chroma_collection()
        mock_collection.query.return_value = {
            "documents": [["Fee is Rs 50,000 per semester."]],
            "metadatas": [[{"section": "Fees", "title": "Fee Structure"}]],
            "distances": [[0.05]],
        }

        service = self._make_rag_service(embedding_provider, mock_collection)

        chunks_only = asyncio.run(service.retrieve("What is the fee?"))
        chunks_with_emb, _ = asyncio.run(service.retrieve_with_embedding("What is the fee?"))

        assert chunks_only == chunks_with_emb


# ---------------------------------------------------------------------------
# Test 2 — find_matching_exemplar() returns None without embed_single() when
#           _exemplar_count == 0
# ---------------------------------------------------------------------------

class TestExemplarCountFastPath:
    """P1-B: ExemplarService should skip the embedding call when count is 0."""

    def _make_service_with_count(self, count: int):
        mock_collection = _make_chroma_collection(count=count)
        chroma_client = _make_chroma_client(mock_collection)

        with patch("app.db.chroma.get_chroma_client", return_value=chroma_client):
            from app.services.exemplar_service import ExemplarService
            embedding_provider = _make_embedding_provider()
            service = ExemplarService(embedding_provider=embedding_provider)

        # Explicitly set the cached count (in case the mock count() was called
        # during __init__ via _refresh_exemplar_count).
        service._exemplar_count = count
        # Replace _get_collection so we control what queries return.
        service._get_collection = MagicMock(return_value=mock_collection)
        return service, embedding_provider

    def test_returns_none_without_embedding_call_when_count_zero(self):
        service, embedding_provider = self._make_service_with_count(0)

        result = asyncio.run(service.find_matching_exemplar("What is the fee?"))

        assert result is None, "Should return None immediately when collection is empty"
        embedding_provider.embed_single.assert_not_called()

    def test_calls_embedding_when_count_nonzero(self):
        service, embedding_provider = self._make_service_with_count(3)
        # Make query return a result above threshold so we get None back.
        service._get_collection.return_value.query.return_value = {
            "metadatas": [[{"question": "foo", "answer": "bar"}]],
            "distances": [[0.99]],
        }

        asyncio.run(service.find_matching_exemplar("Some question"))

        embedding_provider.embed_single.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3 — find_matching_exemplar() skips embed_single() when
#           precomputed_embedding is provided
# ---------------------------------------------------------------------------

class TestPrecomputedEmbedding:
    """P0-A: find_matching_exemplar() should accept and use precomputed_embedding."""

    def _make_service_with_exemplars(self):
        mock_collection = _make_chroma_collection(count=2)
        mock_collection.query.return_value = {
            "metadatas": [[{"question": "Can I join B.Tech CSE?", "answer": "Yes, 60% required."}]],
            "distances": [[0.10]],
        }
        chroma_client = _make_chroma_client(mock_collection)

        with patch("app.db.chroma.get_chroma_client", return_value=chroma_client):
            from app.services.exemplar_service import ExemplarService
            embedding_provider = _make_embedding_provider()
            service = ExemplarService(embedding_provider=embedding_provider)

        service._exemplar_count = 2
        service._get_collection = MagicMock(return_value=mock_collection)
        return service, embedding_provider

    def test_skips_embed_single_when_precomputed_embedding_given(self):
        service, embedding_provider = self._make_service_with_exemplars()

        precomputed = [0.9, 0.8, 0.7, 0.6]
        result = asyncio.run(
            service.find_matching_exemplar(
                "Can I join B.Tech CSE?",
                precomputed_embedding=precomputed,
            )
        )

        # embed_single should NOT have been called
        embedding_provider.embed_single.assert_not_called()
        # Should still return a match based on the mocked collection response
        assert result is not None
        assert "answer" in result

    def test_calls_embed_single_when_no_precomputed_embedding(self):
        service, embedding_provider = self._make_service_with_exemplars()

        asyncio.run(service.find_matching_exemplar("Can I join B.Tech CSE?"))

        embedding_provider.embed_single.assert_called_once_with("Can I join B.Tech CSE?")


# ---------------------------------------------------------------------------
# Test 4 — _exemplar_count increments on register_exemplar()
# ---------------------------------------------------------------------------

class TestExemplarCountIncrement:
    """P1-B: _exemplar_count should increment after a successful register_exemplar()."""

    def _make_service(self):
        mock_collection = _make_chroma_collection(count=0)
        chroma_client = _make_chroma_client(mock_collection)

        with patch("app.db.chroma.get_chroma_client", return_value=chroma_client):
            from app.services.exemplar_service import ExemplarService
            embedding_provider = _make_embedding_provider()
            service = ExemplarService(embedding_provider=embedding_provider)

        service._exemplar_count = 0
        service._get_collection = MagicMock(return_value=mock_collection)
        return service

    def test_count_increments_after_register(self):
        service = self._make_service()
        assert service._exemplar_count == 0

        msg_id = uuid.uuid4()
        asyncio.run(
            service.register_exemplar(
                msg_id,
                question="What is the fee?",
                answer="Rs 50,000 per semester.",
            )
        )

        assert service._exemplar_count == 1, "_exemplar_count should be 1 after first registration"

    def test_count_increments_multiple_times(self):
        service = self._make_service()
        assert service._exemplar_count == 0

        for i in range(3):
            asyncio.run(
                service.register_exemplar(
                    uuid.uuid4(),
                    question=f"Question {i}",
                    answer=f"Answer {i}",
                )
            )

        assert service._exemplar_count == 3

    def test_count_decrements_on_remove(self):
        service = self._make_service()
        service._exemplar_count = 2  # pretend two are stored

        msg_id = uuid.uuid4()
        asyncio.run(service.remove_exemplar(msg_id))

        assert service._exemplar_count == 1

    def test_count_does_not_go_below_zero_on_remove(self):
        service = self._make_service()
        service._exemplar_count = 0

        asyncio.run(service.remove_exemplar(uuid.uuid4()))

        assert service._exemplar_count == 0, "Count should never go below zero"
