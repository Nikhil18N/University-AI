"""v4.17.1: Reply to a specific message / fee card, and Edit the latest typed message (through /agent/stream).

* every turn has message ids known to the browser (done.message_id / done.user_message_id) and saved with them;
* a reply gives the model the referenced message and its fee estimate (flagged as earlier when a newer exists),
  and is refused for a message outside the student's conversation;
* editing the latest typed message restores the state from before it, archives the replaced pair (never deletes
  it), recalculates from the corrected text and is refused for any other message or after an external action.
"""
import asyncio
import json
import uuid

import pytest
from google.genai import types

import app.main  # noqa: F401  (wires the turn logger, conversation resolver and history loader)
from app.sru_agent import agent, memory
from app.sru_agent import router as agent_router


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class Recorder:
    def __init__(self):
        self.prompts = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.prompts.append(str(config.system_instruction))
        return _text("Here is the answer about it.")


# All on one event loop, with no pooled database connection left from another test's loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
async def _fresh_db_connections():
    from app.db.session import engine
    await engine.dispose(close=False)
    yield
    await engine.dispose(close=False)


@pytest.fixture
def model(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(agent, "get_client", lambda *a, **k: rec)
    monkeypatch.setattr(agent.config, "GEMINI_API_KEYS", [], raising=False)
    monkeypatch.setattr(agent._ring, "next_key", lambda: None)
    return rec


async def _turn(sid, msg, conv=None, **kw):
    req = agent_router.AgentRequest(session_id=sid, message=msg, conversation_id=conv, **kw)
    resp = await agent_router.agent_stream(req, None)
    events = []
    async for chunk in resp.body_iterator:
        for line in str(chunk).splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    for _ in range(200):                                  # the turn is saved in the background
        if not agent_router._turn_queues:
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.2)
    return events


async def _student():
    sid = f"v4171re-{uuid.uuid4().hex}"
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    return sid


async def _saved(sid, conv):
    from app.db.session import async_session_factory
    from app.services import conversation_service
    async with async_session_factory() as db:
        return await conversation_service.get_conversation(db, uuid.UUID(conv), sid)


@pytest.mark.asyncio
async def test_turns_have_ids_and_a_reply_is_about_the_referenced_estimate(model):
    sid = await _student()
    first = await _turn(sid, "Just show the B.Tech CSE fee", source="button")
    done = first[-1]
    assert done["type"] == "done" and done["message_id"] and done["user_message_id"]
    conv = done["conversation_id"]
    saved = await _saved(sid, conv)
    ids = [str(m.id) for m in saved.messages]
    assert done["message_id"] in ids and done["user_message_id"] in ids       # saved with the browser's ids
    reply = await _turn(sid, "What does this amount include?", conv, reply_to=done["message_id"])
    assert reply[-1]["type"] == "done"
    prompt = model.prompts[-1]
    assert "REPLYING TO THIS EARLIER MESSAGE" in prompt and "fee estimate shown with that message" in prompt
    saved = await _saved(sid, conv)
    asked = next(m for m in saved.messages if m.content == "What does this amount include?")
    assert asked.reply_to == done["message_id"]


@pytest.mark.asyncio
async def test_a_reply_to_a_message_of_another_conversation_is_refused(model):
    sid, other = await _student(), await _student()
    theirs = (await _turn(other, "Just show the B.Tech CSE fee", source="button"))[-1]
    mine = (await _turn(sid, "Just show the MBA fee", source="button"))[-1]
    ev = await _turn(sid, "and this?", mine["conversation_id"], reply_to=theirs["message_id"])
    assert ev[-1]["type"] == "error" and "not in this conversation" in ev[-1]["detail"]


@pytest.mark.asyncio
async def test_editing_the_latest_message_recalculates_from_the_corrected_text(model):
    sid = await _student()
    t1 = (await _turn(sid, "Just show the B.Tech CSE fee", source="button"))[-1]
    conv = t1["conversation_id"]
    t2 = (await _turn(sid, "my marks are 870 out of 1000", conv))[-1]
    assert (await memory.get_profile(sid)).get("percent") == 87.0
    edited = await _turn(sid, "my marks are 950 out of 1000", conv, edit_of=t2["user_message_id"])
    assert edited[-1]["type"] == "done", edited[-1]
    assert (await memory.get_profile(sid)).get("percent") == 95.0             # the corrected marks
    saved = await _saved(sid, conv)
    texts = [m.content for m in saved.messages if m.role == "user"]
    assert "my marks are 870 out of 1000" not in texts                        # replaced (archived, not shown)
    new = next(m for m in saved.messages if m.content == "my marks are 950 out of 1000")
    assert new.edited is True
    history = [h["text"] for h in await memory.get_history(sid, conv)]
    assert "my marks are 870 out of 1000" not in history                      # the agent forgot the old text


@pytest.mark.asyncio
async def test_only_the_latest_message_can_be_edited(model):
    sid = await _student()
    t1 = (await _turn(sid, "what is the mess fee"))[-1]                       # typed, then typed again after it
    conv = t1["conversation_id"]
    await _turn(sid, "what is the hostel fee", conv)
    ev = await _turn(sid, "changed", conv, edit_of=t1["user_message_id"])
    assert ev[-1]["type"] == "error" and "latest message" in ev[-1]["detail"]
    saved = await _saved(sid, conv)
    assert [m.content for m in saved.messages if m.role == "user"] == ["what is the mess fee", "what is the hostel fee"]


@pytest.mark.asyncio
async def test_a_turn_that_completed_a_request_cannot_be_edited(model):
    sid = await _student()
    t1 = (await _turn(sid, "Just show the B.Tech CSE fee", source="button"))[-1]
    conv = t1["conversation_id"]
    t2 = (await _turn(sid, "hostel food?", conv))[-1]
    await memory.mark_turn_snapshot(sid, conv, action_done=True)               # e.g. a callback was saved
    ev = await _turn(sid, "something else", conv, edit_of=t2["user_message_id"])
    assert ev[-1]["type"] == "error" and "can't undo" in ev[-1]["detail"]


@pytest.mark.asyncio
async def test_a_button_choice_is_not_editable_and_saved_messages_say_how_they_were_sent(model):
    sid = await _student()
    t1 = (await _turn(sid, "Just show the B.Tech CSE fee", source="button"))[-1]
    conv = t1["conversation_id"]
    ev = await _turn(sid, "Just show the MBA fee", conv, edit_of=t1["user_message_id"])
    assert ev[-1]["type"] == "error" and "typed" in ev[-1]["detail"]
    t2 = (await _turn(sid, "what is the hostel fee", conv))[-1]
    saved = await _saved(sid, conv)
    by_id = {str(m.id): m for m in saved.messages}
    assert by_id[t1["user_message_id"]].source == "button"
    assert by_id[t2["user_message_id"]].source == "typed" and by_id[t2["user_message_id"]].action_done is False
    assert t2["user_metadata"]["source"] == "typed" and not t2["user_metadata"].get("action_done")


@pytest.mark.asyncio
async def test_an_edit_without_the_earlier_state_is_refused_clearly(model):
    sid = await _student()
    t1 = (await _turn(sid, "what is the hostel fee"))[-1]
    conv = t1["conversation_id"]
    key = memory._snap_key(sid, conv)                                        # e.g. expired
    memory._hot.pop(key, None)
    memory._local.pop(key, None)
    if memory._client():
        await memory._client().delete(key)
    ev = await _turn(sid, "what is the mess fee", conv, edit_of=t1["user_message_id"])
    assert ev[-1]["type"] == "error" and "no longer be edited" in ev[-1]["detail"]
    saved = await _saved(sid, conv)
    assert [m.content for m in saved.messages if m.role == "user"] == ["what is the hostel fee"]   # nothing archived


@pytest.mark.asyncio
async def test_the_latest_typed_message_can_be_edited_after_buttons_and_everything_after_it_is_replaced(model):
    sid = await _student()
    t1 = (await _turn(sid, "Just show the B.Tech CSE fee", source="button"))[-1]
    conv = t1["conversation_id"]
    t2 = (await _turn(sid, "my marks are 870 out of 1000", conv))[-1]
    t3 = (await _turn(sid, "Just show the MBA fee", conv, source="button"))[-1]     # a button after the typed one
    assert t3["type"] == "done"
    edited = await _turn(sid, "my marks are 950 out of 1000", conv, edit_of=t2["user_message_id"])
    assert edited[-1]["type"] == "done", edited[-1]
    assert (await memory.get_profile(sid)).get("percent") == 95.0
    saved = await _saved(sid, conv)
    users = [m.content for m in saved.messages if m.role == "user"]
    assert users == ["Just show the B.Tech CSE fee", "my marks are 950 out of 1000"]   # later turns archived too
    # a button turn takes no snapshot: the typed message stays the one that can be edited
    snap = await memory.get_turn_snapshot(sid, conv)
    assert snap["turn_id"] == edited[-1]["user_message_id"]
