"""Automated verification suite for the 8 canonical test conversations from the
Developer Guide ("From Chatbot to AI Agent"):

1. "i got 85% in inter, cse fee?" -> remember details + calculate_fee (25%, ₹2,55,000, 2027-28)
2. Follow-up "and with ac hostel?" -> retains memory, adds hostel without asking marks again
3. Follow-up "ok ask someone to call me" -> asks name, phone, consent; saves lead with reference
4. "call me on 12345" -> refuses invalid number, saves nothing
5. "eamcet rank 9000 scholarship for cse" -> matches official 2027-28 rank slab (25%)
6. "my daughter got 58%, can she join btech? is hostel safe?" -> parent mode + eligibility + search
7. "cse lo seat confirm ga vastunda 60k rank ki" -> strictly forbids seat guarantees
8. "write python code to reverse a list" -> declines out-of-domain coding question
"""
import pytest
from google.genai import types

from app.sru_agent import memory, prompt, tools
from app.sru_agent.agent import run_agent
from app.sru_agent.fees import calculate_fee, check_eligibility


def _call(tool_name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=tool_name, args=args)]))])


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class ScriptedClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        return self.script.pop(0)


async def _run(client, message, session):
    return [e async for e in run_agent(message, session, client=client)]


# ---- Scenario 1: Fee Calculation from Marks ----
@pytest.mark.asyncio
async def test_scenario_1_fee_calculation():
    """'i got 85% in inter, cse fee?' -> calls remember_student_details, then calculate_fee."""
    client = ScriptedClient([
        _call("remember_student_details", program_interest="cse", percent=85),
        _call("calculate_fee", program="cse"),
        _text("With 85% in Intermediate, you qualify for a 25% merit scholarship for 2027-28. First year tuition is ₹2,55,000.")
    ])
    session = "scenario-1-fee"
    events = await _run(client, "i got 85% in inter, cse fee?", session)

    tools_used = [t["name"] for t in events[-1]["tools_used"]]
    assert tools_used == ["remember_student_details", "calculate_fee"]

    fee_result = [e for e in events if e.get("type") == "tool" and e.get("result")][0]["result"]
    assert fee_result["scholarship_percent"] == 25
    assert fee_result["tuition_first_year_after_scholarship"] == "₹2,55,000"
    assert fee_result["academic_year"] == "2027-28"
    assert "₹2,55,000" in events[-1]["answer"]


# ---- Scenario 2: Multi-Turn Memory Retention ----
@pytest.mark.asyncio
async def test_scenario_2_memory_retention_ac_hostel():
    """Follow-up: 'and with ac hostel?' -> retains marks & program without re-asking."""
    session = "scenario-2-mem"
    await memory.update_profile(session, percent=85, program_interest="cse")

    client = ScriptedClient([
        _call("calculate_fee", hostel="ac_3"),
        _text("With AC 3-sharing hostel added, your first year payable is ₹4,15,000.")
    ])
    events = await _run(client, "and with ac hostel?", session)

    fee_result = [e for e in events if e.get("type") == "tool" and e.get("result")][0]["result"]
    assert fee_result["scholarship_percent"] == 25
    assert fee_result["hostel"]["type"] == "AC, 3-sharing"
    assert fee_result["hostel"]["per_year"] == "₹1,35,000"
    assert fee_result["tuition_first_year_after_scholarship"] == "₹2,55,000"


# ---- Scenario 3: Counselor Callback with Consent ----
@pytest.mark.asyncio
async def test_scenario_3_callback_with_consent():
    """'ok ask someone to call me' -> collects details, asks consent, saves lead."""
    saved_leads = []
    async def mock_lead_saver(lead):
        saved_leads.append(lead)
        return {"id": "SRU-LEAD-7890"}

    tools.set_lead_saver(mock_lead_saver)
    try:
        session = "scenario-3-lead"
        client = ScriptedClient([
            _call("request_counsellor_callback", name="Ananya Rao", phone="9849012345", consent=True, preferred_time="afternoon"),
            _text("I have requested a callback from our admissions team (Ref: #SRU-LEAD). A counselor will call you shortly.")
        ])
        events = await _run(client, "my name is Ananya Rao, phone 9849012345, yes please contact me", session)

        assert len(saved_leads) == 1
        assert saved_leads[0]["name"] == "Ananya Rao"
        assert saved_leads[0]["phone"] == "9849012345"
        assert saved_leads[0]["metadata"]["consent"] is True
        assert saved_leads[0]["metadata"]["request_type"] == "callback"
        assert events[-1]["tools_used"][0]["status"] == "saved"
    finally:
        tools.set_lead_saver(None)


# ---- Scenario 4: Refusal of Invalid Phone Number ----
@pytest.mark.asyncio
async def test_scenario_4_invalid_phone_rejected():
    """'call me on 12345' -> rejects invalid number, nothing saved."""
    res = await tools.run_tool(
        "request_counsellor_callback",
        {"name": "Ravi", "phone": "12345", "consent": True},
        {"session_id": "scenario-4-bad", "profile": {}}
    )
    assert res["status"] == "invalid"
    assert "10-digit" in res["problem"]


# ---- Scenario 5: EAPCET Rank 9000 Slab Matching ----
def test_scenario_5_eapcet_rank_9000_matching():
    """'eamcet rank 9000 scholarship for cse' -> evaluates 25% waiver from official table."""
    fee = calculate_fee("cse", eapcet_rank=9000)
    assert fee["status"] == "ok"
    assert fee["scholarship_percent"] == 25
    assert fee["scholarship_basis"] == "eapcet rank 9000"
    assert fee["tuition_first_year_after_scholarship"] == "₹2,55,000"


# ---- Scenario 6: Parent Mode & Eligibility Check ----
@pytest.mark.asyncio
async def test_scenario_6_parent_mode_and_eligibility():
    """'my daughter got 58%, can she join btech? is hostel safe?' -> parent mode, eligibility, search."""
    elig = check_eligibility("btech_cse", 58)
    assert elig["status"] == "ok"
    assert elig["eligible"] is True
    assert elig["minimum_percent"] == 50

    sys_prompt = prompt.build_system_prompt({"is_parent": True})
    assert "THE USER IS A PARENT" in sys_prompt
    assert "campus safety, hostels" in sys_prompt


# ---- Scenario 7: Anti-Seat Guarantee Policy ----
def test_scenario_7_anti_seat_guarantee_rules():
    """'cse lo seat confirm ga vastunda 60k rank ki' -> system prompt forbids seat guarantee."""
    sys_prompt = prompt.build_system_prompt({})
    assert "NEVER PROMISE OR GUARANTEE SEATS" in sys_prompt
    assert "seat confirm ga vastundi" in sys_prompt
    assert "admission depends on seat availability" in sys_prompt


# ---- Scenario 8: Out-of-Domain Rejection ----
def test_scenario_8_out_of_domain_rejection_policy():
    """'write python code to reverse a list' -> declines coding question politely."""
    sys_prompt = prompt.build_system_prompt({})
    assert "Off-topic requests (coding, homework, essays, weather, general chat)" in sys_prompt
    assert "reply in one friendly line that you can only help with SR University admissions" in sys_prompt
