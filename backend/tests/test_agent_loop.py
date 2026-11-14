"""Tests the agent loop with a FAKE model, so no API key or internet is needed.
Proves: tools are run, results go back to the model, consent is enforced, leads are saved."""
import pytest
from google.genai import types

from app.sru_agent import memory, tools
from app.sru_agent.agent import run_agent


def _call(tool_name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=tool_name, args=args)]))])


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class FakeClient:
    """Returns scripted responses and records what the agent sent."""
    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        return self.script.pop(0)


async def _run(client, message, session):
    return [e async for e in run_agent(message, session, client=client)]


@pytest.mark.asyncio
async def test_fee_question_runs_tool_and_returns_numbers():
    client = FakeClient([_call("calculate_fee", program="cse", percent=92),
                         _text("With 92% you get 30%. Tuition is ₹2,38,000 for 2027-28.")])
    events = await _run(client, "92% cse fee?", "s-fee")
    tool_done = [e for e in events if e["type"] == "tool" and e["status"] == "done"][0]
    assert tool_done["result"]["tuition_first_year_after_scholarship"] == "₹2,38,000"
    # the tool result was sent back to the model on the second request
    sent_back = client.requests[1][-1].parts[0].function_response
    assert sent_back.name == "calculate_fee" and sent_back.response["scholarship_percent"] == 30
    assert events[-1]["type"] == "done" and "₹2,38,000" in events[-1]["answer"]


@pytest.mark.asyncio
async def test_two_tools_in_a_row_and_memory():
    client = FakeClient([_call("remember_student_details", program_interest="cse", percent=85),
                         _call("calculate_fee", program="cse"),
                         _text("Your fee is ready.")])
    events = await _run(client, "i got 85% and want cse", "s-mem")
    assert [t["name"] for t in events[-1]["tools_used"]] == ["remember_student_details", "calculate_fee"]
    fee = [e for e in events if e["type"] == "tool" and e.get("result")][0]["result"]
    assert fee["scholarship_percent"] == 25  # used the remembered 85%
    assert (await memory.get_profile("s-mem"))["percent"] == 85
    assert len(await memory.get_history("s-mem")) == 2


@pytest.mark.asyncio
async def test_callback_needs_consent_then_saves():
    saved = []

    async def fake_saver(lead):
        saved.append(lead)
        return {"id": "abc12345-0000"}

    tools.set_lead_saver(fake_saver)
    try:
        client = FakeClient([_call("request_counsellor_callback", name="Ravi Kumar", phone="9876543210", consent=False),
                             _text("May our team contact you?")])
        events = await _run(client, "call me", "s-lead")
        assert [e for e in events if e["type"] == "tool" and e["status"] == "done"][0]["result_status"] == "needs_consent"
        assert saved == []

        client = FakeClient([_call("request_counsellor_callback", name="Ravi Kumar", phone="+91 98765 43210",
                                   consent=True, preferred_time="evening"),
                             _text("Done. A counsellor will call you.")])
        events = await _run(client, "yes", "s-lead")
        assert events[-1]["tools_used"][0] == {"name": "request_counsellor_callback", "status": "saved", "is_action": True}
        assert saved[0]["phone"] == "9876543210" and saved[0]["source"] == "chat_inquiry"
        assert saved[0]["metadata"]["request_type"] == "callback" and saved[0]["metadata"]["consent"] is True
    finally:
        tools.set_lead_saver(None)


@pytest.mark.asyncio
async def test_bad_phone_and_past_date_are_rejected():
    r = await tools.run_tool("request_counsellor_callback", {"name": "A B", "phone": "12345", "consent": True},
                             {"session_id": "s-x", "profile": {}})
    assert r["status"] == "invalid"
    r = await tools.run_tool("book_campus_visit", {"name": "A B", "phone": "9876543210", "consent": True,
                                                   "visit_date": "2020-01-01"}, {"session_id": "s-x", "profile": {}})
    assert r["status"] == "invalid"


@pytest.mark.asyncio
async def test_model_error_gives_friendly_message():
    class Broken(FakeClient):
        async def generate_content(self, **kw):
            raise RuntimeError("boom")
    events = await _run(Broken([]), "hello", "s-err")
    assert events[-1]["type"] == "error" and "boom" not in events[-1]["detail"]


@pytest.mark.asyncio
async def test_tool_loop_is_capped():
    client = FakeClient([_call("list_programs")] * 4 + [_text("Here are the programs.")])
    events = await _run(client, "courses?", "s-cap")
    assert events[-1]["type"] == "done" and len(events[-1]["tools_used"]) == 4
    assert len(client.requests) == 5
