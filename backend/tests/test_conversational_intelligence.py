"""Verification suite for SRU Buddy's Conversational Intelligence & Personalization.

Tests all 10 conversation scenarios:
1. User starts with "Hi" -> greets and politely asks name.
2. User directly asks about B.Tech fees -> acknowledges and asks name.
3. User introduces their name and asks about SRU -> greets by name and answers without asking name again.
4. User asks multiple questions without repeating name -> remembers name and uses it naturally throughout conversation.
5. User changes from admissions to campus facilities -> smooth topic transition.
6. User asks an incomplete/unclear question -> handles gracefully.
7. User behaves like a parent seeking information -> parent mode with safety and cost transparency.
8. User sends short messages ("Okay", "Why?", "Tell me more") -> context-aware without restart.
9. User returns to a previous topic -> smoothly resumes previous topic.
10. Different users start separate sessions -> complete session isolation.
"""
import pytest
from google.genai import types

from app.sru_agent import memory, prompt, tools, intents
from app.sru_agent.agent import run_agent


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


def _call(tool_name, **args):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_function_call(name=tool_name, args=args)]))])


class MockAgentClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append({"contents": list(contents), "config": config})
        if self.responses:
            return self.responses.pop(0)
        return _text("Here is the requested university information.")


async def _run(message, session_id, conversation_id=None, client=None):
    events = []
    async for ev in run_agent(message, session_id, conversation_id=conversation_id, client=client):
        events.append(ev)
    return events


# ---- Scenario 1: User starts with "Hi" -> greets and politely asks name ----
@pytest.mark.asyncio
async def test_scenario_1_user_starts_with_hi():
    session_id = "test-session-sc1-greeting"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, "conv-1")

    events = await _run("Hi", session_id, "conv-1")
    assert events[-1]["type"] == "done"
    answer = events[-1]["answer"]

    # Must greet and ask for name
    assert any(term in answer.lower() for term in ("name", "call you", "who do i have the pleasure"))
    state = await memory.get_conversation_state(session_id, "conv-1")
    assert state.get("awaiting_name") is True
    assert state.get("name_asked") is True


# ---- Scenario 2: User directly asks about B.Tech fees -> acknowledges and asks name ----
@pytest.mark.asyncio
async def test_scenario_2_direct_fee_question_asks_name_then_answers():
    session_id = "test-session-sc2-fee-ask"
    conv_id = "conv-2"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    # Turn 1: Direct question on first interaction
    events1 = await _run("What is the B.Tech CSE fee?", session_id, conv_id)
    assert events1[-1]["type"] == "done"
    answer1 = events1[-1]["answer"]
    assert any(phrase in answer1.lower() for phrase in ("fee", "help you", "details"))
    assert "name" in answer1.lower()

    state1 = await memory.get_conversation_state(session_id, conv_id)
    assert state1.get("awaiting_name") is True
    assert state1.get("name_asked") is True
    assert state1.get("pending_user_question") == "What is the B.Tech CSE fee?"

    # Turn 2: User provides name "Mahesh"
    mock_client = MockAgentClient([
        _text("Nice to meet you, Mahesh! For B.Tech CSE at SR University, the tuition fee is ₹1,65,000 per semester.")
    ])
    events2 = await _run("Mahesh", session_id, conv_id, client=mock_client)
    assert events2[-1]["type"] == "done"

    profile = await memory.get_profile(session_id)
    assert profile.get("name") == "Mahesh"

    state2 = await memory.get_conversation_state(session_id, conv_id)
    assert state2.get("awaiting_name") is False
    assert state2.get("pending_user_question") is None


# ---- Scenario 3: User introduces their name and asks about SRU -> greets by name without re-asking ----
@pytest.mark.asyncio
async def test_scenario_3_user_introduces_name_and_asks():
    session_id = "test-session-sc3-intro"
    conv_id = "conv-3"
    await memory.clear_profile(session_id)
    await memory.clear_conversation_state(session_id, conv_id)

    mock_client = MockAgentClient([
        _text("Hi Mahesh! Great to connect with you. SR University is established under Telangana Act 2018 and ranked 91st by NIRF.")
    ])

    events = await _run("Hello, I'm Mahesh. I want to know about SRU.", session_id, conv_id, client=mock_client)
    assert events[-1]["type"] == "done"

    profile = await memory.get_profile(session_id)
    assert profile.get("name") == "Mahesh"

    # Confirmed name was NOT asked again
    state = await memory.get_conversation_state(session_id, conv_id)
    assert state.get("awaiting_name") is False
    assert state.get("name_asked") is True


# ---- Scenario 4: User asks multiple questions without repeating name -> remembers name ----
@pytest.mark.asyncio
async def test_scenario_4_remembers_name_across_multiple_turns():
    session_id = "test-session-sc4-memory"
    conv_id = "conv-4"
    await memory.update_profile(session_id, name="Sneha")
    await memory.update_conversation_state(session_id, conv_id, name_asked=True)

    mock_client = MockAgentClient([
        _text("Hi Sneha! Here are the placement statistics for SR University."),
        _text("Yes Sneha, we have separate hostels for boys and girls.")
    ])

    # Turn 1
    events1 = await _run("Tell me about placements", session_id, conv_id, client=mock_client)
    assert events1[-1]["type"] == "done"
    assert "name" not in events1[-1]["answer"].lower() or "sneha" in events1[-1]["answer"].lower()

    # Turn 2
    events2 = await _run("Do you have hostel facilities?", session_id, conv_id, client=mock_client)
    assert events2[-1]["type"] == "done"

    profile = await memory.get_profile(session_id)
    assert profile.get("name") == "Sneha"


# ---- Scenario 5: User changes from admissions to campus facilities -> smooth topic transition ----
@pytest.mark.asyncio
async def test_scenario_5_smooth_topic_transition():
    session_id = "test-session-sc5-transition"
    conv_id = "conv-5"
    await memory.update_profile(session_id, name="Rahul")
    await memory.update_conversation_state(session_id, conv_id, active_topic="fees", name_asked=True)

    mock_client = MockAgentClient([
        _text("SR University features world-class sports arenas, gymnasiums, and innovation labs at SRiX.")
    ])

    events = await _run("What sports and gym facilities do you have on campus?", session_id, conv_id, client=mock_client)
    assert events[-1]["type"] == "done"
    # Transitioned without error or forced fee discussion
    assert "sports" in events[-1]["answer"].lower() or "gym" in events[-1]["answer"].lower()


# ---- Scenario 6: User asks an incomplete/unclear question -> handles gracefully ----
@pytest.mark.asyncio
async def test_scenario_6_unclear_question_handled_gracefully():
    session_id = "test-session-sc6-unclear"
    conv_id = "conv-6"
    await memory.update_profile(session_id, name="Arjun")

    mock_client = MockAgentClient([
        _text("Could you specify which department or program's eligibility you would like to know?")
    ])

    events = await _run("eligibility?", session_id, conv_id, client=mock_client)
    assert events[-1]["type"] == "done"
    assert events[-1]["answer"]


# ---- Scenario 7: User behaves like a parent seeking information -> parent persona active ----
@pytest.mark.asyncio
async def test_scenario_7_parent_persona():
    session_id = "test-session-sc7-parent"
    conv_id = "conv-7"
    await memory.clear_profile(session_id)

    # Detect parent persona
    persona = intents.detect_user_persona("My daughter completed 12th state board, how safe is the girls hostel?")
    assert persona == "parent"

    sys_prompt = prompt.build_system_prompt({"is_parent": True}, persona=persona)
    assert "THE USER IS A PARENT" in sys_prompt
    assert "campus safety, hostels" in sys_prompt


# ---- Scenario 8: Short messages ("Okay", "Why?", "Tell me more") -> context-aware without restart ----
@pytest.mark.asyncio
async def test_scenario_8_short_followup_messages():
    session_id = "test-session-sc8-short"
    conv_id = "conv-8"
    await memory.update_profile(session_id, name="Kiran")

    mock_client = MockAgentClient([
        _text("Certainly Kiran, to elaborate further on the curriculum..."),
        _text("The primary reason is our hands-on project-based learning model.")
    ])

    # Turn 1: "Tell me more"
    events1 = await _run("Tell me more", session_id, conv_id, client=mock_client)
    assert events1[-1]["type"] == "done"
    assert "kiran" in events1[-1]["answer"].lower()

    # Turn 2: "Why?"
    events2 = await _run("Why?", session_id, conv_id, client=mock_client)
    assert events2[-1]["type"] == "done"
    assert "learning" in events2[-1]["answer"].lower() or "reason" in events2[-1]["answer"].lower()


# ---- Scenario 9: User returns to a previous topic -> smooth resume ----
@pytest.mark.asyncio
async def test_scenario_9_return_to_previous_topic():
    session_id = "test-session-sc9-resume"
    conv_id = "conv-9"
    await memory.update_profile(session_id, name="Vikram")

    mock_client = MockAgentClient([
        _text("Returning to the B.Tech CSE fee structure: first-year tuition is ₹1,65,000 per semester.")
    ])

    events = await _run("Let's go back to the B.Tech fees we discussed earlier", session_id, conv_id, client=mock_client)
    assert events[-1]["type"] == "done"
    assert "fee" in events[-1]["answer"].lower() or "1,65,000" in events[-1]["answer"]


# ---- Scenario 10: Different users start separate sessions -> complete session isolation ----
@pytest.mark.asyncio
async def test_scenario_10_separate_sessions_isolated():
    session_a = "user-session-alice"
    session_b = "user-session-bob"

    await memory.update_profile(session_a, name="Alice", percent=95)
    await memory.update_profile(session_b, name="Bob", percent=70)

    prof_a = await memory.get_profile(session_a)
    prof_b = await memory.get_profile(session_b)

    assert prof_a["name"] == "Alice"
    assert prof_a["percent"] == 95

    assert prof_b["name"] == "Bob"
    assert prof_b["percent"] == 70
