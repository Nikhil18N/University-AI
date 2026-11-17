"""Tests for conversation persistence, title backfilling, and agent stream conversation resolution."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.conversation import Conversation
from app.models.message import Message
from app.services import conversation_service
from app.sru_agent import router


@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_with_title():
    """Verify get_or_create_conversation sets the title when creating a new conversation."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()

    session_id = "test-session-123"
    custom_title = "What are the fees for B.Tech CSE?"

    conv = await conversation_service.get_or_create_conversation(
        mock_db, session_id, conversation_id=None, title=custom_title
    )

    assert conv.session_id == session_id
    assert conv.title == custom_title
    mock_db.add.assert_called_once_with(conv)
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_conversation_updates_default_title():
    """Verify that an existing conversation with 'New conversation' title gets updated if a custom title is provided."""
    mock_db = MagicMock()
    conv_id = uuid.uuid4()
    existing_conv = Conversation(
        id=conv_id, session_id="test-session-123", title="New conversation"
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_conv
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()

    updated = await conversation_service.get_or_create_conversation(
        mock_db, "test-session-123", conversation_id=conv_id, title="Hostel Curfew Rules"
    )

    assert updated.id == conv_id
    assert updated.title == "Hostel Curfew Rules"
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_conversation_preserves_existing_custom_title():
    """Verify that an existing conversation with an already customized title is not overwritten."""
    mock_db = MagicMock()
    conv_id = uuid.uuid4()
    existing_conv = Conversation(
        id=conv_id, session_id="test-session-123", title="Already Customized Title"
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_conv
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.flush = AsyncMock()

    result = await conversation_service.get_or_create_conversation(
        mock_db, "test-session-123", conversation_id=conv_id, title="Different Second Question"
    )

    assert result.title == "Already Customized Title"


@pytest.mark.asyncio
async def test_list_conversations_filters_empty_and_backfills_titles():
    """Verify list_conversations skips empty chats (0 messages) and backfills 'New conversation' titles."""
    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    c1 = Conversation(id=uuid.uuid4(), session_id="sess-1", title="New conversation")
    c1.messages = []  # Empty ghost conversation -> should be filtered out

    c2 = Conversation(id=uuid.uuid4(), session_id="sess-1", title="New conversation")
    m2 = Message(conversation_id=c2.id, role="user", content="How much is the CSE tuition fee?")
    c2.messages = [m2]  # Has messages, title stuck -> should be backfilled

    c3 = Conversation(id=uuid.uuid4(), session_id="sess-1", title="Existing Good Title")
    m3 = Message(conversation_id=c3.id, role="user", content="Tell me about hostel")
    c3.messages = [m3]  # Already has good title -> kept intact

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [c1, c2, c3]
    mock_db.execute = AsyncMock(return_value=mock_result)

    summaries = await conversation_service.list_conversations(mock_db, "sess-1")

    # Empty conversation c1 must be filtered out
    assert len(summaries) == 2
    assert summaries[0].id == c2.id
    assert summaries[0].title == "How much is the CSE tuition fee?"
    assert summaries[1].id == c3.id
    assert summaries[1].title == "Existing Good Title"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_conversation_resolver_end_to_end():
    """Verify agent_conversation_resolver creates and returns a valid UUID string and reuses it
    (the database path, used when background writes are switched off)."""
    from app.main import agent_conversation_resolver
    from app.sru_agent import config as agent_config

    mock_conv = Conversation(
        id=uuid.uuid4(), session_id="sess-end-to-end", title="What is the NIRF rank of SRU?"
    )

    with patch("app.db.session.async_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_factory.return_value = mock_session

        with patch("app.services.conversation_service.get_or_create_conversation", return_value=mock_conv) as mock_get_or_create, \
                patch.object(agent_config, "AGENT_BACKGROUND_WRITES", False):
            resolved_id = await agent_conversation_resolver(
                "sess-end-to-end", None, "What is the NIRF rank of SRU?"
            )

            assert resolved_id == str(mock_conv.id)
            mock_get_or_create.assert_awaited_once()
            mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_stream_invokes_conversation_resolver_and_propagates_conv_id():
    """Verify router.agent_stream calls _conversation_resolver and passes resolved ID to run_agent."""
    from app.sru_agent.router import AgentRequest, agent_stream, set_conversation_resolver, set_turn_logger

    resolved_conv_id = "test-uuid-resolved-456"

    async def fake_resolver(session_id, conversation_id, message):
        return resolved_conv_id

    recorded_turns = []
    async def fake_logger(session_id, conversation_id, user_text, answer, tools_used):
        recorded_turns.append((session_id, conversation_id, user_text, answer))

    set_conversation_resolver(fake_resolver)
    set_turn_logger(fake_logger)

    async def fake_run_agent(message, session_id, conversation_id=None):
        yield {"type": "start", "conversation_id": conversation_id}
        yield {"type": "token", "delta": "Answer text"}
        yield {"type": "done", "conversation_id": conversation_id, "answer": "Answer text", "tools_used": []}

    with patch("app.sru_agent.router.memory.allow_request", return_value=True):
        with patch("app.sru_agent.router.run_agent", side_effect=fake_run_agent):
            req = AgentRequest(
                session_id="session-persist-1",
                message="Tell me about admissions",
                conversation_id=None,
            )

            stream_resp = await agent_stream(req)
            events = []
            async for chunk in stream_resp.body_iterator:
                events.append(chunk)
            from app.sru_agent import memory as agent_memory
            await agent_memory.flush()  # the turn is saved in the background, after the answer

            # Check that turn logger was called with resolved_conv_id
            assert len(recorded_turns) == 1
            assert recorded_turns[0][1] == resolved_conv_id

            # Check that the SSE stream contains start and done with resolved_conv_id
            all_chunks = "".join(events)
            assert f'"conversation_id": "{resolved_conv_id}"' in all_chunks
