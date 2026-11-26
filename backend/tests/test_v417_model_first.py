"""v4.17.0: typed messages are understood by the model, never routed by keywords.

* A TYPED message goes to the language model with the conversation, the saved details, verified facts and the
  tools, even when its words look like a fixed topic ("standard fee of cse", "about sru", "placement record").
* The fixed flows run only for STRUCTURED turns: a button / chip the bot offered, a submitted form, an answer to
  the step the bot is waiting on, or a phone number.
* When every AI key is resting (rate limit), a typed question gets an honest "busy" reply with buttons that work
  without the model, never a keyword-matched canned answer.
"""
import uuid

import pytest
from google.genai import types

from app.sru_agent import agent, memory
from app.sru_agent.agent import _structured_turn, run_agent
from app.sru_agent.router import AgentRequest


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class Recorder:
    """A fake model that records what it was sent and answers from a script."""

    def __init__(self, script=()):
        self.script, self.requests, self.prompts = list(script), [], []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        self.prompts.append(config.system_instruction)
        item = self.script.pop(0) if self.script else _text("(model answer)")
        if isinstance(item, Exception):
            raise item
        return item


class _ApiError(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code = code


class RateLimited(Recorder):
    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        raise _ApiError(429, "429 RESOURCE_EXHAUSTED")


def _sid():
    return f"v417-{uuid.uuid4().hex[:10]}"


async def _run(message, sid, client, source="typed", conversation_id=None):
    return [e async for e in run_agent(message, sid, conversation_id, client=client, source=source)]


# ------------------------------------------------------------------------------- the routing rule ----
def test_typed_free_text_is_not_structured():
    assert _structured_turn("typed", False, {}, "standard fee of cse", False, False) is None
    assert _structured_turn("typed", False, {}, "how is ru", False, False) is None
    assert _structured_turn("typed", False, {"fee_intake": {"waiting_for": "done"}}, "im from delhi",
                            False, False) is None


def test_structured_turns_are_facts_about_the_turn_not_the_words():
    assert _structured_turn("button", False, {}, "Calculate my scholarship", False, False) == "button"
    assert _structured_turn(None, False, {}, "anything", False, False) == "internal"
    assert _structured_turn("typed", True, {}, "Am I eligible for B.Tech CSE?", False, False) == "form"
    assert _structured_turn("typed", False, {}, "my number is 9876543210", False, False) == "phone_number"
    # no open step: a typed answer-shaped message is still a question for the model
    assert _structured_turn("typed", False, {}, "CBSE", False, False) is None


def _intake(waiting):
    return {"fee_intake": {"counsellor_mode": True, "program": "btech_cse", "waiting_for": waiting}}


@pytest.mark.parametrize("state, message", [
    (_intake("board"), "CBSE"), (_intake("board"), "Telangana Intermediate (TSBIE)"),
    (_intake("stage"), "Completed Intermediate (Passed out)"),
    (_intake("marks"), "931 out of 1000"), (_intake("marks"), "87%"), (_intake("percent"), "92"),
    (_intake("stream"), "MPC (Maths, Physics, Chemistry)"),
    ({"fee_eval": {"active": True, "awaiting": "hostel", "final_shown": False}}, "Non-AC 4-sharing"),
    ({"fee_eval": {"active": True, "awaiting": "hostel", "final_shown": False}}, "no hostel"),
    ({"pending_action": "callback"}, "Ravi Kumar"), ({"offer": "fee_chart"}, "yes"),
])
def test_a_typed_message_that_gives_what_the_step_asked_for_continues_it(state, message):
    assert (_structured_turn("typed", False, state, message, False, False) or "").startswith("answer:")


@pytest.mark.parametrize("state, message", [
    (_intake("board"), "placement record"),               # short, no question mark, answers nothing asked
    (_intake("marks"), "hostel food"),
    (_intake("stream"), "campus life"),
    ({"fee_eval": {"active": True, "awaiting": "hostel", "final_shown": False}}, "what about placements?"),
    ({"fee_eval": {"active": True, "awaiting": "concession", "final_shown": False}}, "is the campus safe"),
    ({"offer": "fee_chart"}, "how is the hostel food"),
    ({"pending_action": "callback"}, "what is the fee for MBA?"),
    ({"dialogue": {"step": "topic_aspect", "topic": "hostel"}}, "is sru good for cse compared to other colleges"),
])
def test_anything_else_typed_during_an_open_step_goes_to_the_model(state, message):
    assert _structured_turn("typed", False, state, message, False, False) is None


def test_a_closed_step_takes_nothing():
    done_eval = {"fee_eval": {"active": True, "awaiting": "hostel", "final_shown": True}}
    assert _structured_turn("typed", False, done_eval, "no hostel", False, False) is None
    assert _structured_turn("typed", False, _intake("done"), "CBSE", False, False) is None


def test_request_schema_defaults_to_typed_and_rejects_other_sources():
    req = AgentRequest(session_id="s" * 20, message="hi")
    assert req.source == "typed"
    assert AgentRequest(session_id="s" * 20, message="hi", source="button").source == "button"
    with pytest.raises(Exception):
        AgentRequest(session_id="s" * 20, message="hi", source="keyword")


# ----------------------------------------------------------------- typed questions reach the model ----
@pytest.mark.asyncio
@pytest.mark.parametrize("message", [
    "standard fee of cse", "about sru", "Placement record", "how is ru", "I can't afford fee",
    "im from bipc, can I join CSE?", "is there a fee waiver", "what is the fee structure",
    "i got 45% can i join btech", "tell me about hostel facilities",
])
async def test_typed_questions_are_answered_by_the_model(message):
    sid = _sid()
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    client = Recorder([_text("Here is the answer written for this exact question.")])
    events = await _run(message, sid, client)
    done = events[-1]
    assert done["type"] == "done"
    assert client.requests, f"'{message}' was answered without the model"
    assert client.requests[0][-1].parts[0].text.lower() == message.lower()   # the student's own words
    assert done["answer"].startswith("Here is the answer written for this exact question.")


@pytest.mark.asyncio
async def test_the_model_gets_the_conversation_and_verified_facts():
    sid = _sid()
    client = Recorder([_text("First answer."), _text("Second answer.")])
    first = await _run("what programmes are there?", sid, client)
    conv = first[-1].get("conversation_id")
    await _run("and which one has the best placements?", sid, client, conversation_id=conv)
    second_contents = client.requests[-1]
    texts = [p.text for c in second_contents for p in c.parts if getattr(p, "text", None)]
    assert "what programmes are there?" in texts and "First answer." in texts    # the history is sent
    assert "VERIFIED FACTS" in client.prompts[-1]


@pytest.mark.asyncio
async def test_a_typed_fee_question_is_not_prefetched_from_keywords():
    sid = _sid()
    client = Recorder([_text("Which programme and what marks?")])
    events = await _run("how much is the fee with 85%?", sid, client)
    assert "FEE CALCULATION ALREADY DONE" not in client.prompts[0]
    assert not any(c.get("type") == "calculate_fee" for c in events[-1]["cards"])


# ------------------------------------------------------------- buttons and steps keep their flows ----
@pytest.mark.asyncio
async def test_a_button_runs_its_fixed_flow():
    sid = _sid()
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    client = Recorder()
    events = await _run("Just show the B.Tech CSE fee", sid, client, source="button")
    done = events[-1]
    assert done["type"] == "done" and not client.requests                    # no model needed for a button
    assert any(c.get("type") == "fee_structure_detailed" for c in done["cards"])   # the engine's own fee card
    assert "₹1,95,000" in done["answer"]                                      # Semester 1 from the engine


# ---------------------------------------------------------------------------------- rate limits ----
@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["placement record", "tell me about hostel facilities",
                                     "cse fee with 85% in inter", "what is the eligibility for MBA"])
async def test_rate_limit_gives_an_honest_busy_reply_never_a_keyword_answer(message, monkeypatch):
    async def no_sleep(_seconds):
        return None
    monkeypatch.setattr(agent.asyncio, "sleep", no_sleep)
    sid = _sid()
    events = await _run(message, sid, RateLimited())
    done = events[-1]
    assert done["type"] == "done"
    assert done["answer"] in agent._LIMIT_REPLY_OPTIONS
    assert "₹" not in done["answer"]
    assert done["suggestions"] == list(agent._BUSY_CHIPS)
    assert not done["cards"]


def _call(name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=name, args=args)]))])


@pytest.mark.asyncio
async def test_the_model_starts_the_guided_board_first_check_instead_of_asking_for_marks():
    # v4.17.1: "i want to join for b.tech cse" -> the model hands over to the guided steps (board, stage, marks out of
    # that board's total); it never collects marks in a message
    sid = _sid()
    await memory.update_profile(sid, name="Ravi Kumar", phone="9876543210", welcome_actions_shown=True)
    client = Recorder([_call("start_guided_check", program="B.Tech CSE")])
    events = await _run("i want to join sru for b.tech cse", sid, client)
    done = events[-1]
    assert done["type"] == "done"
    assert any(c.get("type") == "counsellor_board_selection" for c in done["cards"]), done["cards"]
    assert "board" in done["answer"].lower()
    state = await memory.get_conversation_state(sid, done["conversation_id"])
    assert (state.get("fee_intake") or {}).get("waiting_for") == "board"
