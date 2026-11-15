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


@pytest.mark.asyncio
async def test_create_feedback_does_not_auto_promote_exemplar(mock_embedding_provider):
    """Verify that user thumbs up (rating=1) does NOT automatically register exemplars."""
    from unittest.mock import patch
    from app.services.conversation_service import create_feedback
    from app.schemas.chat import FeedbackRequest

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    async def mock_flush():
        feedback_obj = mock_db.add.call_args[0][0]
        feedback_obj.id = uuid.uuid4()
    mock_db.flush = AsyncMock(side_effect=mock_flush)

    request = FeedbackRequest(
        session_id="test-session",
        conversation_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        rating=1,
        comment="Great answer!",
    )

    with patch("app.services.exemplar_service.ExemplarService.register_exemplar") as mock_register:
        response = await create_feedback(mock_db, request, embeddings=mock_embedding_provider)
        assert response.status == "received"
        # register_exemplar should NOT have been called
        mock_register.assert_not_called()
