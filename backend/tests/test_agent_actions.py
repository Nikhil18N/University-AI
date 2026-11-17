"""Tests for the agent's real-world actions and its honesty about them.

Covers the blockers found in the 16 Nov 2026 live test:
  * "I have cancelled the callback" was said without anything being cancelled
  * a callback was dropped when the name / number arrived in a later message
  * a campus-visit request with a past date and a phone number got a blank reply
  * a generic fee table was shown under a personalised fee answer
  * one busy Gemini key failed most students when 20 asked at once

A fake model is used everywhere, so no API key or internet is needed.
"""
from datetime import date, timedelta

import pytest
from google.genai import types

from app.sru_agent import agent, config, intents, memory, tools
from app.sru_agent.agent import run_agent


def _call(tool_name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=tool_name, args=args)]))])


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class ScriptedClient:
    """Returns scripted model responses and counts how often the model was asked."""

    def __init__(self, script=()):
        self.script, self.requests = list(script), []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _run(message, session, client=None, conversation_id=None):
    events = [e async for e in run_agent(message, session, conversation_id, client=client or ScriptedClient())]
    return events, events[-1]


def _next_weekday(days_ahead=3):
    d = date.today() + timedelta(days=days_ahead)
    return d + timedelta(days=1) if d.weekday() == 6 else d


@pytest.fixture
def leads():
    """In-memory stand-ins for the leads table: what was saved, what was cancelled."""
    store = {"saved": [], "cancelled": []}

    async def saver(lead):
        store["saved"].append(lead)
        return {"id": f"lead{len(store['saved']):04d}-aaaa-bbbb"}

    async def canceller(lead_id, reason=""):
        store["cancelled"].append(lead_id)
        return True

    tools.set_lead_saver(saver)
    tools.set_lead_canceller(canceller)
    yield store
    tools.set_lead_saver(None)
    tools.set_lead_canceller(None)


# ------------------------------------------------------------------ cancel ----
@pytest.mark.asyncio
async def test_cancel_with_nothing_saved_never_claims_cancelled(leads):
    client = ScriptedClient()
    events, done = await _run("please don't call me", "act-cancel-none", client)
    assert done["type"] == "done"
    assert client.requests == []  # settled without the model
    assert done["tools_used"] == [{"name": "cancel_contact_request", "status": "nothing_to_cancel", "is_action": True}]
    assert "nothing to cancel" in done["answer"]
    assert "have cancelled" not in done["answer"].lower()
    assert leads["cancelled"] == []


@pytest.mark.asyncio
async def test_callback_saved_when_details_arrive_in_a_later_message(leads):
    sid = "act-callback-later"
    # Turn 1: the student asks for a call; the model asks for details.
    client = ScriptedClient([_text("Sure! Please share your full name and 10-digit mobile number.")])
    _, done = await _run("ok ask someone to call me", sid, client)
    assert leads["saved"] == []
    assert (await memory.get_conversation_state(sid))["pending_action"] == "callback"

    # Turn 2: name and number arrive. The agent saves the lead itself; the model is not needed.
    client = ScriptedClient()
    events, done = await _run("Ravi Kumar 9876543210, tomorrow evening", sid, client)
    assert client.requests == []
    assert len(leads["saved"]) == 1
    lead = leads["saved"][0]
    assert (lead["name"], lead["phone"]) == ("Ravi Kumar", "9876543210")
    assert lead["metadata"]["request_type"] == "callback" and lead["metadata"]["consent"] is True
    assert lead["metadata"]["preferred_time"] == "tomorrow evening"
    assert done["tools_used"] == [{"name": "request_counsellor_callback", "status": "saved", "is_action": True}]
    assert "lead0001" in done["answer"] and "3210" in done["answer"]
    assert any(c["type"] == "request_counsellor_callback" for c in done["cards"])
    assert not (await memory.get_conversation_state(sid)).get("pending_action")


@pytest.mark.asyncio
async def test_cancel_after_save_marks_the_lead_and_says_so(leads):
    sid = "act-cancel-saved"
    await _run("please call me, my name is Sita Devi, 9123456780", sid)
    assert len(leads["saved"]) == 1

    events, done = await _run("actually don't call me", sid)
    assert leads["cancelled"] == ["lead0001-aaaa-bbbb"]
    assert done["tools_used"][0]["status"] == "cancelled"
    assert "cancelled your callback request" in done["answer"] and "lead0001" in done["answer"]
    assert "last_lead_id" not in await memory.get_profile(sid)

    # A second cancel has nothing left to cancel, and says exactly that.
    _, done = await _run("cancel the callback", sid)
    assert done["tools_used"][0]["status"] == "nothing_to_cancel"
    assert len(leads["cancelled"]) == 1


@pytest.mark.asyncio
async def test_cancel_is_honest_when_cancelling_is_not_possible(leads):
    sid = "act-cancel-unwired"
    await _run("call me please, I am Arjun Reddy 9988776655", sid)
    tools.set_lead_canceller(None)
    _, done = await _run("cancel my callback", sid)
    assert done["tools_used"][0]["status"] == "not_available"
    assert "could not cancel" in done["answer"] and config.ADMISSIONS_PHONE in done["answer"]
    assert "have cancelled" not in done["answer"].lower()


@pytest.mark.asyncio
async def test_model_claiming_a_cancellation_is_corrected(leads):
    """The model says 'cancelled' without calling the tool: the agent runs the tool and reports the truth."""
    sid = "act-cancel-claim"
    client = ScriptedClient([_text("No problem, I have cancelled your callback request. Our team will not call you.")])
    # Telugu-English phrasing the keyword check does not know, so the message reaches the model.
    _, done = await _run("naku callback vaddu, remove chey", sid, client)
    assert len(client.requests) == 1
    assert any(t["name"] == "cancel_contact_request" for t in done["tools_used"])
    assert "nothing to cancel" in done["answer"]
    assert "have cancelled" not in done["answer"].lower()


@pytest.mark.asyncio
async def test_model_claiming_a_saved_request_is_corrected(leads):
    sid = "act-saved-claim"
    client = ScriptedClient([_text("Done! I have requested a callback and a counsellor will call you soon.")])
    _, done = await _run("i need more guidance about admission", sid, client)
    assert leads["saved"] == []
    assert done["answer"].startswith("I have not saved anything yet")
    assert "10-digit mobile number" in done["answer"]
    assert (await memory.get_conversation_state(sid))["pending_action"] == "callback"


@pytest.mark.asyncio
async def test_refund_question_is_not_mistaken_for_a_cancellation(leads):
    client = ScriptedClient([_text("If an admission is cancelled, refunds follow the UGC refund guidelines.")])
    _, done = await _run("if i cancel my admission will i get the fee refund?", "act-refund", client)
    assert done["tools_used"] == []
    assert "UGC refund guidelines" in done["answer"]


# ---------------------------------------------------------- callback details ----
@pytest.mark.asyncio
async def test_number_without_name_asks_for_the_name_then_saves(leads):
    sid = "act-name-later"
    _, done = await _run("call me on 9876501234", sid)
    assert leads["saved"] == [] and "full name" in done["answer"]

    _, done = await _run("Mahesh Babu", sid)
    assert len(leads["saved"]) == 1
    assert (leads["saved"][0]["name"], leads["saved"][0]["phone"]) == ("Mahesh Babu", "9876501234")
    assert done["tools_used"][0]["status"] == "saved"


@pytest.mark.asyncio
async def test_invalid_number_is_refused_and_nothing_is_saved(leads):
    client = ScriptedClient()
    _, done = await _run("call me on 12345", "act-bad-phone", client)
    assert client.requests == [] and leads["saved"] == []
    assert "does not look like a valid 10-digit mobile number" in done["answer"]


@pytest.mark.asyncio
async def test_details_given_after_the_agent_asked_for_the_number(leads):
    """The agent offered a callback and asked for the number; the student's reply completes it."""
    sid = "act-offered"
    await memory.append_history(sid, "is the hostel safe?",
                                "Yes. Would you like a counsellor to call you? Please share your name and mobile number.")
    _, done = await _run("Lakshmi Narayana, 9000012345", sid)
    assert len(leads["saved"]) == 1 and leads["saved"][0]["name"] == "Lakshmi Narayana"
    assert done["tools_used"][0] == {"name": "request_counsellor_callback", "status": "saved", "is_action": True}


@pytest.mark.asyncio
async def test_same_request_is_not_saved_twice(leads):
    sid = "act-no-duplicates"
    await _run("please call me. Kiran Rao 9012345678", sid)
    _, done = await _run("please call me. Kiran Rao 9012345678", sid)
    assert len(leads["saved"]) == 1
    assert "already saved" in done["answer"]


@pytest.mark.asyncio
async def test_other_question_in_the_same_message_is_still_answered(leads):
    sid = "act-and-question"
    client = ScriptedClient([_text("Your callback is saved (reference lead0001). Yes, hostel is available for girls.")])
    _, done = await _run("please call me, Priya Sharma 9876512345. also is hostel available for girls?", sid, client)
    assert len(leads["saved"]) == 1 and len(client.requests) == 1
    assert "hostel is available" in done["answer"]
    # If the model is down, the saved request is still confirmed.
    client = ScriptedClient([RuntimeError("boom")])
    _, done = await _run("please call me, Anil Kumar 9876512399. also what about transport?", "act-and-question-2", client)
    assert done["type"] == "done" and "callback request is saved" in done["answer"]


# ------------------------------------------------------------- campus visit ----
@pytest.mark.asyncio
async def test_visit_with_all_details_in_one_message_is_booked(leads):
    visit = _next_weekday()
    client = ScriptedClient()
    _, done = await _run(f"Book a campus visit on {visit.isoformat()} for 3 people. Ravi Kumar 9876543210",
                         "act-visit-one", client)
    assert client.requests == [] and len(leads["saved"]) == 1
    meta = leads["saved"][0]["metadata"]
    assert meta["request_type"] == "campus_visit" and meta["visit_date"] == visit.isoformat() and meta["visitors"] == 3
    assert done["tools_used"] == [{"name": "book_campus_visit", "status": "saved", "is_action": True}]
    assert visit.strftime("%B %d, %Y") in done["answer"] and "lead0001" in done["answer"]


@pytest.mark.asyncio
async def test_visit_with_a_past_date_gets_a_clear_reply_not_a_blank_one(leads):
    client = ScriptedClient()
    _, done = await _run("I want to visit the campus on 2026-01-05. My name is Ravi Kumar, phone 9876543210",
                         "act-visit-past", client)
    assert done["type"] == "done" and leads["saved"] == []
    assert "has already passed" in done["answer"] and "Which other date" in done["answer"]
    assert "Ask the student" not in done["answer"]  # no instructions meant for the model leak to the student
    assert done["tools_used"][0] == {"name": "book_campus_visit", "status": "invalid", "is_action": True}


@pytest.mark.asyncio
async def test_visit_details_typed_after_confirming_the_date(leads):
    sid, conv = "act-visit-typed", "conv-visit-typed"
    visit = _next_weekday(5)
    _, done = await _run(f"I want to visit on {visit.isoformat()}", sid, conversation_id=conv)
    assert done["answer"] == f"Do you mean {visit.strftime('%B %d, %Y')}?"
    _, done = await _run("yes", sid, conversation_id=conv)
    assert any(c.get("type") == "campus_visit_form" for c in done["cards"])
    # Instead of filling the form, the student types the details in the chat.
    _, done = await _run("Sneha Reddy 9876500011", sid, conversation_id=conv)
    assert len(leads["saved"]) == 1
    assert leads["saved"][0]["metadata"]["visit_date"] == visit.isoformat()
    assert done["tools_used"][0]["status"] == "saved"


@pytest.mark.asyncio
async def test_detailed_visit_question_is_not_hijacked_by_the_canned_question():
    client = ScriptedClient([_text("Yes, parents are welcome. Visits run Monday to Saturday, 9:30 AM to 4:30 PM.")])
    _, done = await _run("can my parents also come for the campus visit and what are the timings?", "act-visit-info", client)
    assert len(client.requests) == 1
    assert "parents are welcome" in done["answer"]


def test_visit_date_is_found_inside_a_sentence():
    today = date(2026, 11, 16)  # a Monday
    r = tools.resolve_campus_visit_date
    assert r("Book a visit on 20 Nov for 3 people. Ravi 9876543210", today=today)["iso"] == "2026-11-20"
    assert r("we are 4 members coming this saturday at 10 am", today=today)["iso"] == "2026-11-21"
    assert r("visit on 25/11/26 at 11:30", today=today)["iso"] == "2026-11-25"
    past = r("I want to visit campus on 2026-11-10, my number is 9876543210", today=today)
    assert past["is_past"] is True and past["is_valid"] is False and "already passed" in past["reason"]
    # numbers that are not dates
    for text in ("9876543210", "my marks are 85%", "i got 17th rank", "call me at 5", "I sat for jee"):
        assert r(text, today=today)["date"] is None, text


# -------------------------------------------------------------- understanding ----
def test_contact_intents():
    for text in ("ok ask someone to call me", "can a counsellor call me", "I want to talk to a counsellor",
                 "call me on 12345", "call cheyandi"):
        assert intents.is_callback_request(text), text
    for text in ("will someone call me after applying?", "what number can I call?", "how do you contact parents",
                 "what do they call the fest", "don't call me"):
        assert not intents.is_callback_request(text), text
    for text in ("don't call me", "please do not contact me", "cancel the callback", "cancel my visit",
                 "no need to call", "call cheyakandi", "remove my number"):
        assert intents.is_cancel_contact(text), text
    assert not intents.is_cancel_contact("don't call me before 5pm")
    assert not intents.is_cancel_contact("cancel")           # nothing open
    assert intents.is_cancel_contact("cancel", has_open_request=True)


def test_name_extraction():
    assert intents.extract_name("my name is Ananya Rao, phone 9849012345") == "Ananya Rao"
    assert intents.extract_name("Ravi Kumar 9876543210") == "Ravi Kumar"
    assert intents.extract_name("9876543210 ravi kumar") == "Ravi Kumar"
    assert intents.extract_name("i am ravi kumar, 9876543210") == "Ravi Kumar"
    assert intents.extract_name("Mahesh", bare_ok=True) == "Mahesh"
    for text in ("I am interested in CSE", "i am from hyderabad 9876543210", "call me on 9876543210",
                 "yes 9876543210", "I am telugu medium student"):
        assert intents.extract_name(text) is None, text
    assert intents.extract_name("cse fee", bare_ok=True) is None


def test_phone_helpers():
    assert tools.find_phone("my number is +91 98765 43210 ok") == "9876543210"
    assert tools.find_phone("fee is 340000 and rank 9000") is None
    assert tools.find_bad_phone("call me on 12345678") == "12345678"
    assert tools.find_bad_phone("visit on 2026-11-20") is None
    assert tools.find_bad_phone("fee 3,40,000") is None


# -------------------------------------------------------------------- cards ----
@pytest.mark.asyncio
async def test_no_generic_fee_table_under_a_personalised_answer():
    client = ScriptedClient([_call("calculate_fee", program="cse", percent=85),
                             _text("With 85% you get 25%. Tuition is ₹2,55,000 for 2027-28.")])
    _, done = await _run("What is the fee breakdown for B.Tech CSE per semester? I got 85%", "act-cards", client)
    kinds = [c.get("type") for c in done["cards"]]
    assert "calculate_fee" in kinds
    assert "fee_breakdown" not in kinds


@pytest.mark.asyncio
async def test_generic_fee_table_still_shown_when_no_fee_tool_ran():
    client = ScriptedClient([_text("B.Tech CSE tuition is listed below.")])
    _, done = await _run("What is the fee breakdown for B.Tech CSE per semester?", "act-cards-generic", client)
    assert "fee_breakdown" in [c.get("type") for c in done["cards"]]


# ----------------------------------------------------------------- new tools ----
@pytest.mark.asyncio
async def test_program_info_concessions_compare_and_share_tools():
    ctx = {"session_id": "act-tools", "profile": {}}
    info = await tools.run_tool("get_program_info", {"program": "mba"}, ctx)
    assert info["status"] == "ok" and info["tuition_per_year"] == "₹3,00,000" and "Bachelor" in info["eligibility"]

    sports = await tools.run_tool("get_special_concessions", {"category": "state level sports"}, ctx)
    assert sports["status"] == "ok"
    assert {c["category"] for c in sports["matching"]} == {
        "Sports: National level representation", "Sports: International level representation"}

    both = await tools.run_tool("compare_programs", {"program_a": "cse", "program_b": "ece", "percent": 85}, ctx)
    assert [c["tuition_first_year_after_scholarship"] for c in both["comparison"]] == ["₹2,55,000", "₹2,02,500"]

    assert (await tools.run_tool("share_fee_estimate", {}, ctx))["status"] == "no_estimate"
    await tools.run_tool("calculate_fee", {"program": "cse", "percent": 85, "hostel": "ac_4"}, ctx)
    share = await tools.run_tool("share_fee_estimate", {}, ctx)
    assert share["status"] == "ok" and share["whatsapp_share_url"].startswith("https://wa.me/?text=")
    assert "Merit scholarship: 25%" in share["share_text"] and "₹2,55,000" in share["share_text"]
    # calculate_fee remembers what the student said, so a follow-up needs no repeat
    assert (await memory.get_profile("act-tools"))["percent"] == 85


def test_every_tool_declaration_is_accepted_by_the_sdk():
    decl = agent._tool_declarations()
    names = {f.name for f in decl.function_declarations}
    assert {"cancel_contact_request", "get_program_info", "get_special_concessions", "compare_programs",
            "share_fee_estimate"} <= names
    assert tools.ACTION_TOOLS == {"request_counsellor_callback", "book_campus_visit", "cancel_contact_request"}


# --------------------------------------------------------------------- load ----
class _ApiError(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code = code


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(config, "AGENT_RETRY_DELAYS", (0, 0, 0))


@pytest.mark.asyncio
async def test_busy_server_is_retried(no_waiting):
    client = ScriptedClient([_ApiError(503, "503 UNAVAILABLE: the model is overloaded"),
                             _text("SR University is in Warangal.")])
    _, done = await _run("where is sru?", "act-retry", client)
    assert done["type"] == "done" and done["answer"] == "SR University is in Warangal."
    assert len(client.requests) == 2


@pytest.mark.asyncio
async def test_rate_limited_key_rotates_to_the_next_key(no_waiting, monkeypatch):
    calls = []

    class KeyClient(ScriptedClient):
        def __init__(self, key):
            super().__init__()
            self.key = key

        async def generate_content(self, model, contents, config):
            calls.append(self.key)
            if self.key == "key-A":
                raise _ApiError(429, "429 RESOURCE_EXHAUSTED: quota exceeded")
            return _text("Answered on the second key.")

    ring = agent._KeyRing()
    monkeypatch.setattr(config, "GEMINI_API_KEYS", ["key-A", "key-B"])
    monkeypatch.setattr(ring, "client", lambda key: KeyClient(key))
    monkeypatch.setattr(agent, "_ring", ring)

    events = [e async for e in run_agent("where is sru?", "act-rotate")]
    assert events[-1]["type"] == "done" and events[-1]["answer"] == "Answered on the second key."
    assert calls == ["key-A", "key-B"]
    # the next student starts on a healthy key, not the rate-limited one
    events = [e async for e in run_agent("where is sru?", "act-rotate-2")]
    assert calls[-1] == "key-B" and len(calls) == 3


@pytest.mark.asyncio
async def test_fee_question_is_still_answered_when_the_model_is_unreachable(no_waiting):
    class Down(ScriptedClient):
        async def generate_content(self, model, contents, config):
            raise _ApiError(429, "429 RESOURCE_EXHAUSTED")

    _, done = await _run("cse fee with 85% in inter", "act-offline", Down())
    assert done["type"] == "done"
    assert "₹2,55,000" in done["answer"] and "25% merit scholarship" in done["answer"]
    assert done["cards"][0]["type"] == "calculate_fee"
    # a non-fee question still reports the problem, so the website can fall back
    events, last = await _run("tell me about placements", "act-offline-2", Down())
    assert last["type"] == "error"


@pytest.mark.asyncio
async def test_empty_model_reply_is_retried_and_never_blank():
    client = ScriptedClient([_text(""), _text("Here is the answer.")])
    _, done = await _run("how is campus life?", "act-empty", client)
    assert done["answer"] == "Here is the answer."
    client = ScriptedClient([_text(""), _text("")])
    _, done = await _run("how is campus life?", "act-empty-2", client)
    assert done["answer"].strip() != ""


def test_prompt_is_compact_and_has_no_fee_numbers():
    from app.sru_agent.prompt import build_system_prompt
    text = build_system_prompt({"name": "Ravi", "last_lead_id": "secret-id"}, pending_action="callback")
    assert len(text) < 9000, "the prompt is sent with every model call; keep it small"
    for number in ("3,40,000", "2,42,500", "1,15,000", "₹550"):
        assert number not in text
    assert "PENDING ACTION" in text and "secret-id" not in text


@pytest.mark.asyncio
async def test_twenty_students_at_once_are_all_answered(monkeypatch):
    """The 16 Nov load blocker (20 at once -> 5 answered). Three keys, each allowing only a few
    calls per moment, 20 students at the same instant: every one must get an answer."""
    import asyncio
    import time

    monkeypatch.setattr(config, "AGENT_RETRY_DELAYS", (0.05, 0.1, 0.2))
    monkeypatch.setattr(config, "AGENT_KEY_COOLDOWN_SECONDS", 0.15)
    monkeypatch.setattr(config, "AGENT_MAX_CONCURRENCY", 6)
    monkeypatch.setattr(config, "GEMINI_API_KEYS", ["key-A", "key-B", "key-C"])
    window, allowed = 0.15, 5          # each key: 5 calls per 0.15 s, like a per-minute quota in miniature
    used_at = {"key-A": [], "key-B": [], "key-C": []}
    running = {"now": 0, "peak": 0}

    class QuotaClient(ScriptedClient):
        def __init__(self, key):
            super().__init__()
            self.key = key

        async def generate_content(self, model, contents, config):
            now = time.monotonic()
            recent = [t for t in used_at[self.key] if now - t < window]
            if len(recent) >= allowed:
                raise _ApiError(429, "429 RESOURCE_EXHAUSTED")
            used_at[self.key] = recent + [now]
            running["now"] += 1
            running["peak"] = max(running["peak"], running["now"])
            await asyncio.sleep(0.01)
            running["now"] -= 1
            # first call of a message asks for a tool, the second writes the answer
            if contents[-1].parts[0].function_response is None:
                return _call("list_programs")
            return _text("Here are the programs SR University offers.")

    ring = agent._KeyRing()
    monkeypatch.setattr(ring, "client", lambda key: QuotaClient(key))
    monkeypatch.setattr(agent, "_ring", ring)
    monkeypatch.setattr(agent, "_gates", {})  # a fresh concurrency gate with the limit set above

    async def one_student(i):
        events = [e async for e in run_agent("which courses are there?", f"act-load-{i}")]
        return events[-1]["type"]

    results = await asyncio.gather(*(one_student(i) for i in range(20)))
    assert results.count("done") == 20, results
    assert running["peak"] <= 6                      # never more than AGENT_MAX_CONCURRENCY at once
    assert all(len(calls) > 0 for calls in used_at.values())  # the load was spread over every key


@pytest.mark.asyncio
async def test_name_first_then_number(leads):
    sid = "act-name-first"
    client = ScriptedClient([_text("Sure. Please share your full name and 10-digit mobile number.")])
    await _run("can a counsellor call me?", sid, client)
    _, done = await _run("Divya Teja", sid)
    assert leads["saved"] == [] and "10-digit mobile number" in done["answer"] and "Divya" in done["answer"]
    _, done = await _run("9812345670", sid)
    assert (leads["saved"][0]["name"], leads["saved"][0]["phone"]) == ("Divya Teja", "9812345670")
    assert done["tools_used"][0]["status"] == "saved"


@pytest.mark.asyncio
async def test_unrelated_short_message_is_not_taken_as_a_name(leads):
    sid = "act-not-a-name"
    client = ScriptedClient([_text("Sure. Please share your mobile number.")])   # did not ask for a name
    await _run("ask someone to call me", sid, client)
    client = ScriptedClient([_text("Buses run from Warangal, Hanamkonda and Kazipet.")])
    _, done = await _run("bus routes", sid, client)
    assert len(client.requests) == 1 and "Buses run" in done["answer"]
    assert not (await memory.get_conversation_state(sid)).get("pending_name")


@pytest.mark.asyncio
async def test_number_alone_after_the_agent_asked_for_it(leads):
    sid = "act-number-alone"
    await memory.update_profile(sid, name="Harika Rao")
    await memory.append_history(sid, "yes please", "Great. What is your 10-digit mobile number?")
    _, done = await _run("9700012345", sid)
    assert len(leads["saved"]) == 1 and leads["saved"][0]["name"] == "Harika Rao"
