"""Tests for ExemplarService self-improvement and few-shot memory."""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.exemplar_service import ExemplarService


@pytest.fixture
def mock_embedding_provider():
    mock = MagicMock()
    mock.embed_single = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return mock


@pytest.mark.asyncio
async def test_exemplar_registration_and_matching(mock_embedding_provider):
    service = ExemplarService(mock_embedding_provider)
    mock_collection = MagicMock()
    service._get_collection = MagicMock(return_value=mock_collection)

    msg_id = uuid.uuid4()
    question = "Can I join B.Tech CSE?"
    answer = "Yes, B.Tech CSE requires 60% in 10+2 PCM."

    # Test register
    success = await service.register_exemplar(msg_id, question, answer)
    assert success is True
    mock_collection.upsert.assert_called_once()

    # Test find matching exemplar
    mock_collection.query.return_value = {
        "metadatas": [[{"question": question, "answer": answer}]],
        "distances": [[0.15]],
    }
    match = await service.find_matching_exemplar("Can I join B.Tech CSE?")
    assert match is not None
    assert match["answer"] == answer
    assert match["distance"] == 0.15

    # Test distance above threshold returns None
    mock_collection.query.return_value = {
        "metadatas": [[{"question": question, "answer": answer}]],
        "distances": [[0.55]],
    }
    no_match = await service.find_matching_exemplar("Something completely different")
    assert no_match is None


@pytest.mark.asyncio
async def test_exemplar_removal(mock_embedding_provider):
    service = ExemplarService(mock_embedding_provider)
    mock_collection = MagicMock()
    service._get_collection = MagicMock(return_value=mock_collection)

    msg_id = uuid.uuid4()
    success = await service.remove_exemplar(msg_id)
    assert success is True
    mock_collection.delete.assert_called_once_with(ids=[str(msg_id)])
