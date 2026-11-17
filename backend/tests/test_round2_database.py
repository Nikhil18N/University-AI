"""Database-backed checks for the second audit round. They need PostgreSQL and are skipped
when it is not reachable (like the other database tests in this folder).

  * a reopened chat shows each question above its answer, with the same cards and suggestions
  * old chats, whose question and answer share one timestamp, are shown in the right order too
  * the student's profile survives the cache (Settings > My details stays in step)
  * a corrected mobile number is written to the saved callback request
"""
import uuid
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_chat_order_profile_and_lead_update_in_postgres():
    from sqlalchemy import text

    from app.db.session import async_session_factory, engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
            await conn.execute(text("select 1 from messages limit 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL with the app tables is not available")

    from app.main import agent_turn_logger
    from app.models.lead import ProspectiveLead
    from app.models.message import Message
    from app.services import agent_profile_store, conversation_service

    try:
        session_id = f"db-{uuid.uuid4().hex[:20]}"
        async with async_session_factory() as db:
            conv = await conversation_service.get_or_create_conversation(db, session_id, None, title="order test")
            await db.commit()
            conv_id = conv.id

        # 1. three agent turns, saved the way the live site saves them
        card = {"type": "calculate_fee", "data": {"program": "B.Tech CSE", "scholarship_percent": 25}}
        for i in range(3):
            await agent_turn_logger(session_id, str(conv_id), f"question {i}", f"answer {i}", [],
                                    cards=[card] if i == 1 else [], suggestions=["Hostel details"],
                                    started_at=datetime.now(timezone.utc))
        async with async_session_factory() as db:
            detail = await conversation_service.get_conversation(db, conv_id, session_id)
        assert [(m.role, m.content) for m in detail.messages] == [
            ("user", "question 0"), ("assistant", "answer 0"), ("user", "question 1"),
            ("assistant", "answer 1"), ("user", "question 2"), ("assistant", "answer 2")]
        assert detail.messages[3].cards == [card] and detail.messages[3].suggestions == ["Hostel details"]
        assert all(a.created_at < b.created_at for a, b in zip(detail.messages, detail.messages[1:]))

        # 2. an OLD chat: question and answer stored with the same timestamp, answer inserted first
        same = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
        async with async_session_factory() as db:
            old = await conversation_service.get_or_create_conversation(db, session_id, None, title="old chat")
            db.add(Message(conversation_id=old.id, role="assistant", content="old answer", created_at=same))
            db.add(Message(conversation_id=old.id, role="user", content="old question", created_at=same))
            await db.commit()
            old_id = old.id
        async with async_session_factory() as db:
            detail = await conversation_service.get_conversation(db, old_id, session_id)
            recent = await conversation_service.get_recent_messages(db, old_id)
        assert [m.role for m in detail.messages] == ["user", "assistant"]
        assert [m["role"] for m in recent] == ["user", "assistant"]

        # 3. the agent can read a saved chat back as context, but only for its own session
        history = await agent_profile_store.load_history(session_id, str(conv_id))
        assert history[0] == {"role": "user", "text": "question 0"} and history[-1]["role"] == "model"
        assert await agent_profile_store.load_history("someone-else", str(conv_id)) == []

        # 4. profile: saved, read back, changed, removed
        await agent_profile_store.save_profile(session_id, {"name": "Dinesh Kumar", "phone": "7075545685",
                                                           "percent": 98, "last_fee": {"big": "x" * 400}})
        agent_profile_store._last_saved.pop(session_id, None)
        assert await agent_profile_store.load_profile(session_id) == {
            "name": "Dinesh Kumar", "phone": "7075545685", "percent": 98}
        await agent_profile_store.save_profile(session_id, {"name": "Dinesh Kumar", "phone": "9876501234"})
        agent_profile_store._last_saved.pop(session_id, None)
        assert await agent_profile_store.load_profile(session_id) == {"name": "Dinesh Kumar", "phone": "9876501234"}

        # 5. a corrected number reaches the saved callback request
        async with async_session_factory() as db:
            lead = ProspectiveLead(name="Dinesh Kumar", phone="7075545685", source="chat_inquiry", status="new",
                                   metadata_={"request_type": "callback"})
            db.add(lead)
            await db.commit()
            lead_id = lead.id
        assert await agent_profile_store.update_lead_contact(str(lead_id), phone="9876501234") is True
        assert await agent_profile_store.update_lead_contact(str(uuid.uuid4()), phone="9876501234") is False
        async with async_session_factory() as db:
            lead = await db.get(ProspectiveLead, lead_id)
            assert lead.phone == "9876501234" and lead.metadata_["previous_phone"] == "7075545685"
            assert lead.metadata_["request_type"] == "callback"
    finally:
        await engine.dispose()


def test_api_security_headers_and_cors_do_not_echo_unknown_origins():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res = client.get("/api/v1/agent/fee-config", headers={"Origin": "https://evil.example.com"})
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("access-control-allow-origin") is None
    assert res.headers.get("access-control-allow-credentials") is None
    ok = client.get("/api/v1/agent/fee-config", headers={"Origin": "https://university-ai-companion.vercel.app"})
    assert ok.headers.get("access-control-allow-origin") == "https://university-ai-companion.vercel.app"


def test_small_talk_does_not_become_the_chat_title():
    from app.sru_agent import intents
    assert intents.small_talk("hi") and intents.small_talk("hi sru_buddy") and intents.small_talk("thanks")
    assert not intents.small_talk("what is the cse fee")
