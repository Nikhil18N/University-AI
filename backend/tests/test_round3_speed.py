"""Round 3 (v3.0.0): the speed changes.

The live server spent 3-5 seconds per message on Redis / database trips before Gemini was even
asked, and saved the chat before the cards were sent. These tests pin down the fixes:
answers stream while Gemini writes them, the thinking setting is dropped if a model refuses it,
saving happens after the answer (in order), and a new chat starts without a database trip.
"""
import asyncio
import time
import uuid
from unittest.mock import patch

import pytest
from google.genai import types

from app.sru_agent import agent, config, memory
from app.sru_agent.agent import run_agent


def test_agent_memory_reuses_application_redis_client():
    shared = object()
    memory.set_redis_client(shared)
    try:
        assert memory._client() is shared
    finally:
        memory.set_redis_client(None)


@pytest.mark.asyncio
async def test_legacy_chat_route_rejects_rate_limited_session(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1 import chat as chat_api
    from app.schemas.chat import ChatRequest

    async def deny_request(*args, **kwargs):
        return False

    monkeypatch.setattr(memory, "allow_request", deny_request)

    with pytest.raises(HTTPException) as error:
        await chat_api.send_message(
            ChatRequest(session_id="rate-limited-session", message="hello"),
            db=None,
            llm=None,
            rag=None,
            redis=None,
        )

    assert error.value.status_code == 429


def _text_chunk(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


def _call_chunk(name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=name, args=args)]))])


class StreamingClient:
    """A fake Gemini client that answers in pieces, like the real streaming API."""

    def __init__(self, rounds, fail_first_with=None):
        self.rounds, self.requests, self.configs = list(rounds), [], []
        self.fail_first_with = fail_first_with
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):  # not used when streaming works
        raise AssertionError("the agent should have streamed")

    async def generate_content_stream(self, model, contents, config):
        self.requests.append(list(contents))
        self.configs.append(config)
        if self.fail_first_with:
            exc, self.fail_first_with = self.fail_first_with, None
            raise exc
        chunks = self.rounds.pop(0)

        async def _gen():
            for c in chunks:
                await asyncio.sleep(0)
                yield c
        return _gen()


async def _events(client, message, session):
    return [e async for e in run_agent(message, session, client=client)]


@pytest.mark.asyncio
async def test_answer_streams_while_the_model_writes_it():
    client = StreamingClient([[_text_chunk("SR University has "), _text_chunk("a 150-acre campus.")]])
    events = await _events(client, "tell me about the campus size", f"stream-{uuid.uuid4()}")
    tokens = [e["delta"] for e in events if e["type"] == "token"]
    assert tokens[:2] == ["SR University has ", "a 150-acre campus."]  # the model's own pieces
    done = events[-1]
    assert done["type"] == "done" and done["answer"] == "SR University has a 150-acre campus."
    # the words are not sent a second time after streaming
    assert "".join(tokens) == done["answer"]


@pytest.mark.asyncio
async def test_streamed_tool_call_still_runs_the_tool():
    client = StreamingClient([
        [_call_chunk("calculate_fee", program="cse", percent=92)],
        [_text_chunk("With 92% you get a 30% scholarship.")],
    ])
    events = await _events(client, "what will the cse fee be for me with 92%, state board, no entrance exam",
                           f"stream-tool-{uuid.uuid4()}")
    done_tools = [e for e in events if e["type"] == "tool" and e["status"] == "done"]
    assert done_tools and done_tools[0]["result"]["scholarship_percent"] == 30
    sent_back = client.requests[1][-1].parts[0].function_response
    assert sent_back.name == "calculate_fee"
    assert events[-1]["answer"] == "With 92% you get a 30% scholarship."


@pytest.mark.asyncio
async def test_minimal_thinking_is_asked_for_and_dropped_if_refused():
    refused = Exception("400 INVALID_ARGUMENT: thinking_level MINIMAL is not supported for this model")
    client = StreamingClient([[_text_chunk("Hello from SR University.")]], fail_first_with=refused)
    events = await _events(client, "what is sru known for", f"think-{uuid.uuid4()}")
    assert events[-1]["answer"] == "Hello from SR University."
    assert client.configs[0].thinking_config is not None          # first try: least thinking
    assert client.configs[1].thinking_config is None              # retried without the setting


@pytest.mark.asyncio
async def test_callback_replies_are_not_streamed_before_the_honesty_check():
    client = StreamingClient([])

    async def no_stream(*a, **k):
        raise AssertionError("must not stream")
    client.generate_content_stream = no_stream

    async def plain(model, contents, config):
        return _text_chunk("Sure, please share your name and number.")
    client.generate_content = plain
    events = await _events(client, "can someone call me back about admissions", f"cb-{uuid.uuid4()}")
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_profile_saves_happen_in_the_background_and_in_order():
    saved = []

    async def slow_save(session_id, profile):
        await asyncio.sleep(0.05)
        saved.append(dict(profile))

    async def load(session_id):
        return {}

    memory.set_profile_store(load, slow_save)
    try:
        sid = f"bg-{uuid.uuid4()}"
        started = time.perf_counter()
        await memory.update_profile(sid, name="Asha")
        await memory.update_profile(sid, city="Warangal")
        await memory.update_profile(sid, percent=91)
        assert time.perf_counter() - started < 0.05      # the student did not wait for the database
        await memory.flush()
        assert saved[-1] == {"name": "Asha", "city": "Warangal", "percent": 91}  # newest copy wins
        assert len(saved) <= 2                           # writes were merged, not one per change
    finally:
        memory.set_profile_store(None, None)


@pytest.mark.asyncio
async def test_new_chat_gets_an_id_without_waiting_for_the_database():
    import app.main as main

    created = []

    async def slow_create(session_id, conv_uuid, title):
        await asyncio.sleep(0.2)
        created.append((session_id, str(conv_uuid), title))

    with patch.object(main, "_create_conversation_row", slow_create):
        started = time.perf_counter()
        conv_id = await main.agent_conversation_resolver("fast-sess-1", None, "What is the CSE fee?")
        assert time.perf_counter() - started < 0.1
        uuid.UUID(conv_id)
        # the turn logger waits for the row, so the messages land in the right chat
        assert conv_id in main._creating_conversations
        await memory.flush()
        assert created == [("fast-sess-1", conv_id, "What is the CSE fee?")]
        # a new chat has no earlier messages: no database read for its history
        assert await memory.get_history("fast-sess-1", conv_id) == []
        # the same chat again: no database check at all
        assert await main.agent_conversation_resolver("fast-sess-1", conv_id, "next") == conv_id


@pytest.mark.asyncio
async def test_done_reaches_the_browser_before_the_chat_is_saved():
    from app.sru_agent.router import AgentRequest, agent_stream, set_conversation_resolver, set_turn_logger

    logged = []

    async def slow_logger(session_id, conversation_id, user_text, answer, tools_used, **kw):
        await asyncio.sleep(0.3)
        logged.append(user_text)

    async def resolver(session_id, conversation_id, message):
        return "conv-speed-1"

    async def fake_run_agent(message, session_id, conversation_id=None):
        yield {"type": "start", "conversation_id": conversation_id}
        yield {"type": "token", "delta": "Answer"}
        yield {"type": "done", "conversation_id": conversation_id, "answer": "Answer", "tools_used": []}

    set_conversation_resolver(resolver)
    set_turn_logger(slow_logger)
    try:
        with patch("app.sru_agent.router.run_agent", side_effect=fake_run_agent):
            started = time.perf_counter()
            for text in ("first question", "second question"):
                resp = await agent_stream(AgentRequest(session_id="speed-sess", message=text))
                chunks = [c async for c in resp.body_iterator]
                assert '"type": "done"' in chunks[-1]
            assert time.perf_counter() - started < 0.3   # did not wait for the slow save
            await memory.flush()
            assert logged == ["first question", "second question"]  # saved in order
    finally:
        import app.main as main
        set_conversation_resolver(main.agent_conversation_resolver)
        set_turn_logger(main.agent_turn_logger)


def test_retry_waits_are_short_by_default():
    assert sum(config.AGENT_RETRY_DELAYS) <= 4
