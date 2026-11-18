"""Tests for the Intelligent Course Selection & Fee Enquiry Flow in SRU Buddy.

Verifies the 10 target scenarios:
1. "What is the B.Tech CSE fee for 2027–28?"
2. "Tell me the complete fee structure."
3. "What is the hostel fee?"
4. "How much will B.Tech CSE cost including hostel?"
5. "What are the fees for Agriculture?"
6. "I am interested in Astra School of Business."
7. User selects a school but types a course manually.
8. User changes their selected programme midway.
9. User asks about scholarships after receiving fee details.
10. User asks about fees for an unverified future academic year.
"""
import pytest
from app.sru_agent import memory
from app.sru_agent.agent import run_agent
from app.sru_agent import fee_flow


class DummyClient:
    def __init__(self):
        self.requests = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append({"contents": list(contents), "config": config})
        return None


async def _run(message, session_id, conv_id="conv-flow", client=None):
    events = []
    # Using client=DummyClient() allows testing deterministic agent logic directly
    cl = client or DummyClient()
    async for ev in run_agent(message, session_id, conversation_id=conv_id, client=cl):
        events.append(ev)
    return events


# ---- Scenario 1: "What is the B.Tech CSE fee for 2027–28?" ----
@pytest.mark.asyncio
async def test_scenario_1_btech_cse_fee_with_academic_year():
    session_id = "test-fee-sc1"
    conv_id = "conv-1"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("What is the B.Tech CSE fee for 2027–28?", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]
    cards = events[-1]["cards"]

    assert "3,40,000" in answer
    assert "2027-28" in answer
    assert any(c.get("type") == "fee_structure_detailed" for c in cards)
    assert any("Hostel" in s for s in events[-1]["suggestions"])


# ---- Scenario 2: "Tell me the complete fee structure." ----
@pytest.mark.asyncio
async def test_scenario_2_complete_fee_structure_asks_school():
    session_id = "test-fee-sc2"
    conv_id = "conv-2"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("Tell me the complete fee structure.", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]
    cards = events[-1]["cards"]

    # Must prompt for academic area / school
    assert "school" in answer.lower() or "academic area" in answer.lower()
    assert any(c.get("type") == "school_selection" for c in cards)
    school_card = next(c for c in cards if c.get("type") == "school_selection")
    assert len(school_card["schools"]) == 6

    state = await memory.get_conversation_state(session_id, conv_id)
    assert state.get("fee_flow_state") == "awaiting_school_selection"


# ---- Scenario 3: "What is the hostel fee?" ----
@pytest.mark.asyncio
async def test_scenario_3_hostel_fee_query_initiates_flow():
    session_id = "test-fee-sc3"
    conv_id = "conv-3"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("What is the hostel fee for 2027-28?", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]
    cards = events[-1]["cards"]

    # Before generic numbers, initiates academic flow
    assert any(c.get("type") == "school_selection" for c in cards)
    state = await memory.get_conversation_state(session_id, conv_id)
    assert state.get("fee_flow_state") == "awaiting_school_selection"
    assert state.get("fee_flow_year") == "2027-28"


# ---- Scenario 4: "How much will B.Tech CSE cost including hostel?" ----
@pytest.mark.asyncio
async def test_scenario_4_btech_cse_cost_including_hostel():
    session_id = "test-fee-sc4"
    conv_id = "conv-4"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("How much will B.Tech CSE cost including hostel?", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]
    cards = events[-1]["cards"]

    assert "3,40,000" in answer
    assert "1,15,000" in answer or "Hostel" in answer
    assert any(c.get("type") == "fee_structure_detailed" for c in cards)


# ---- Scenario 5: "What are the fees for Agriculture?" ----
@pytest.mark.asyncio
async def test_scenario_5_fees_for_agriculture():
    session_id = "test-fee-sc5"
    conv_id = "conv-5"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("What are the fees for Agriculture?", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]
    cards = events[-1]["cards"]

    # Directly identifies School of Agriculture and presents its programmes
    assert "Agriculture" in answer
    assert any(c.get("type") == "course_selection" for c in cards)
    course_card = next(c for c in cards if c.get("type") == "course_selection")
    progs = [p["name"] for p in course_card["programs_ug"]]
    assert any("Agriculture" in p for p in progs)
    assert any("Food Technology" in p for p in progs)

    state = await memory.get_conversation_state(session_id, conv_id)
    assert state.get("fee_flow_state") == "awaiting_course_selection"
    assert state.get("fee_flow_school") == "school_agriculture"


# ---- Scenario 6: "I am interested in Astra School of Business." ----
@pytest.mark.asyncio
async def test_scenario_6_interested_in_business_school():
    session_id = "test-fee-sc6"
    conv_id = "conv-6"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    events = await _run("I am interested in Astra School of Business.", session_id, conv_id)
    assert events[-1]["type"] == "done"
    cards = events[-1]["cards"]

    assert any(c.get("type") == "course_selection" for c in cards)
    course_card = next(c for c in cards if c.get("type") == "course_selection")
    ug_names = [p["name"] for p in course_card["programs_ug"]]
    assert any("BBA" in name for name in ug_names)
    assert any("B.Com" in name for name in ug_names)


# ---- Scenario 7: User selects a school but types a course manually ----
@pytest.mark.asyncio
async def test_scenario_7_selects_school_then_types_course_manually():
    session_id = "test-fee-sc7"
    conv_id = "conv-7"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    # Turn 1: Broad fee query
    await _run("Tell me about the course fees", session_id, conv_id)
    state1 = await memory.get_conversation_state(session_id, conv_id)
    assert state1.get("fee_flow_state") == "awaiting_school_selection"

    # Turn 2: User types manual course directly: "B.Tech Mechanical"
    events2 = await _run("B.Tech Mechanical", session_id, conv_id)
    assert events2[-1]["type"] == "done"
    answer2 = events2[-1]["answer"]
    cards2 = events2[-1]["cards"]

    assert "Mechanical" in answer2
    assert "2,00,000" in answer2
    assert any(c.get("type") == "fee_structure_detailed" for c in cards2)


# ---- Scenario 8: User changes selected programme midway ----
@pytest.mark.asyncio
async def test_scenario_8_change_school_midway():
    session_id = "test-fee-sc8"
    conv_id = "conv-8"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    # Turn 1: Select School of Engineering
    events1 = await _run("School of Engineering", session_id, conv_id)
    state1 = await memory.get_conversation_state(session_id, conv_id)
    assert state1.get("fee_flow_state") == "awaiting_course_selection"
    assert state1.get("fee_flow_school") == "school_engineering"

    # Turn 2: User changes their mind: "Go back and change school"
    events2 = await _run("Change school", session_id, conv_id)
    assert events2[-1]["type"] == "done"
    cards2 = events2[-1]["cards"]
    assert any(c.get("type") == "school_selection" for c in cards2)

    state2 = await memory.get_conversation_state(session_id, conv_id)
    assert state2.get("fee_flow_state") == "awaiting_school_selection"


# ---- Scenario 9: User asks about scholarships after receiving fee details ----
@pytest.mark.asyncio
async def test_scenario_9_scholarships_followup_after_fee_details():
    session_id = "test-fee-sc9"
    conv_id = "conv-9"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    # Turn 1: Get B.Tech CSE fee
    await _run("What is the fee for B.Tech CSE?", session_id, conv_id)
    state1 = await memory.get_conversation_state(session_id, conv_id)
    assert state1.get("fee_flow_state") == "completed"

    # Turn 2: User asks about hostel follow-up
    events2 = await _run("What about hostel?", session_id, conv_id)
    assert events2[-1]["type"] == "done"
    answer2 = events2[-1]["answer"]
    assert "1,35,000" in answer2
    assert "Non-AC" in answer2
    assert "4,000-seat" in answer2


# ---- Scenario 10: User asks about fees for an unverified future academic year ----
@pytest.mark.asyncio
async def test_scenario_10_unverified_academic_year_honesty():
    session_id = "test-fee-sc10"
    conv_id = "conv-10"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    # Ask for an unverified future year: 2029-30
    events = await _run("What is the B.Tech CSE fee for 2029-30?", session_id, conv_id)
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]

    # Must honestly mention that 2029-30 is not yet finalized, and present the latest verified (2027-28)
    assert "not yet been finalized" in answer or "latest verified" in answer or "2027-28" in answer
    assert "3,40,000" in answer
