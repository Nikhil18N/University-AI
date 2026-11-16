"""Comprehensive tests for intent classification, date resolution, context truthfulness, and booking accuracy."""

from datetime import date, timedelta
import pytest
from unittest.mock import AsyncMock, patch

from app.sru_agent.intents import classify_agent_intent
from app.sru_agent.tools import resolve_campus_visit_date
from app.sru_agent import memory, agent
from app.services.card_service import generate_cards


def test_intent_classification_campus_visit_info_vs_booking():
    # General inquiries must be classified as CAMPUS_VISIT_INFO, NOT BOOKING
    assert classify_agent_intent("campus visit") == "CAMPUS_VISIT_INFO"
    assert classify_agent_intent("visit campus") == "CAMPUS_VISIT_INFO"
    assert classify_agent_intent("can I visit the campus") == "CAMPUS_VISIT_INFO"
    assert classify_agent_intent("tell me about campus visit") == "CAMPUS_VISIT_INFO"
    assert classify_agent_intent("visiting hours") == "CAMPUS_VISIT_INFO"

    # Explicit booking actions must be classified as CAMPUS_VISIT_BOOKING
    assert classify_agent_intent("schedule campus visit") == "CAMPUS_VISIT_BOOKING"
    assert classify_agent_intent("book campus tour") == "CAMPUS_VISIT_BOOKING"
    assert classify_agent_intent("how can i book a campus tour") == "CAMPUS_VISIT_BOOKING"
    assert classify_agent_intent("i want to schedule a visit") == "CAMPUS_VISIT_BOOKING"

    # Visiting with a date mentioned
    assert classify_agent_intent("I want to visit on 17th.") == "CAMPUS_VISIT_BOOKING_WITH_DATE"
    assert classify_agent_intent("visit on tomorrow") == "CAMPUS_VISIT_BOOKING_WITH_DATE"
    assert classify_agent_intent("visit on next Monday") == "CAMPUS_VISIT_BOOKING_WITH_DATE"

    # Date query
    assert classify_agent_intent("What is today's date?") == "DATE_QUERY"
    assert classify_agent_intent("what's today's date") == "DATE_QUERY"
    assert classify_agent_intent("today's date") == "DATE_QUERY"

    # Confusion query
    assert classify_agent_intent("What are you talking about?") == "CONFUSION_QUERY"
    assert classify_agent_intent("what do you mean") == "CONFUSION_QUERY"
    assert classify_agent_intent("huh") == "CONFUSION_QUERY"


def test_date_confirmation_intent_with_state():
    state_awaiting = {"awaiting_date_confirmation": True, "pending_visit_date": "2026-11-17"}
    assert classify_agent_intent("Yes", state=state_awaiting) == "DATE_CONFIRMATION_YES"
    assert classify_agent_intent("yeah", state=state_awaiting) == "DATE_CONFIRMATION_YES"
    assert classify_agent_intent("correct", state=state_awaiting) == "DATE_CONFIRMATION_YES"
    assert classify_agent_intent("No", state=state_awaiting) == "DATE_CONFIRMATION_NO"

    # Without awaiting state, "Yes" is just general
    assert classify_agent_intent("Yes", state={}) == "GENERAL"


def test_resolve_campus_visit_date_dynamic_and_deterministic():
    mock_today = date(2026, 11, 16)  # Monday, Nov 16, 2026

    # 17th -> Nov 17, 2026
    res17 = resolve_campus_visit_date("17th", today=mock_today)
    assert res17["is_valid"] is True
    assert res17["iso"] == "2026-11-17"
    assert res17["human"] == "November 17, 2026"
    assert res17["is_sunday"] is False

    # tomorrow -> Nov 17, 2026
    res_tmrw = resolve_campus_visit_date("tomorrow", today=mock_today)
    assert res_tmrw["is_valid"] is True
    assert res_tmrw["iso"] == "2026-11-17"

    # next Monday (from Monday Nov 16 -> Monday Nov 23)
    res_next_mon = resolve_campus_visit_date("next Monday", today=mock_today)
    assert res_next_mon["is_valid"] is True
    assert res_next_mon["iso"] == "2026-11-23"

    # Sunday handling: Nov 22, 2026 is Sunday
    res_sun = resolve_campus_visit_date("22nd Nov", today=mock_today)
    assert res_sun["is_sunday"] is True
    assert res_sun["is_valid"] is False
    assert len(res_sun["alternative_suggestions"]) == 2
    assert res_sun["alternative_suggestions"][0]["iso"] == "2026-11-21"  # Saturday
    assert res_sun["alternative_suggestions"][1]["iso"] == "2026-11-23"  # Monday

    # Outside 90 days window
    res_far = resolve_campus_visit_date("17th May 2027", today=mock_today)
    assert res_far["is_outside_window"] is True
    assert res_far["is_valid"] is False


def test_card_service_suppresses_booking_box_on_general_campus_visit():
    # User says "campus visit" -> Must NOT trigger campus_visit_form
    cards_info = generate_cards(user_message="campus visit", answer="Here is info.")
    assert not any(c.get("type") == "campus_visit_form" for c in cards_info)

    # User says "schedule campus visit" -> DOES trigger campus_visit_form
    cards_booking = generate_cards(user_message="schedule campus visit", answer="Sure!")
    assert any(c.get("type") == "campus_visit_form" for c in cards_booking)


@pytest.mark.asyncio
async def test_end_to_end_conversation_sequence():
    """Test the exact 5-step conversation flow reported by the user."""
    session_id = "test-session-accuracy-1"
    conversation_id = "conv-accuracy-1"

    # Step 1: User says "campus visit"
    events_1 = [e async for e in agent.run_agent("campus visit", session_id, conversation_id)]
    done_1 = next(e for e in events_1 if e["type"] == "done")
    assert "Are you looking for information about visiting the SR University campus, or would you like to schedule a campus visit?" in done_1["answer"]
    assert not any(c.get("type") == "campus_visit_form" for c in done_1["cards"])

    # Step 2: User says "What are you talking about?"
    events_2 = [e async for e in agent.run_agent("What are you talking about?", session_id, conversation_id)]
    done_2 = next(e for e in events_2 if e["type"] == "done")
    assert "Sorry for the confusion! I can help you with campus visit details, directions, timings, or scheduling a visit." in done_2["answer"]
    assert "earlier" not in done_2["answer"].lower()

    # Step 3: User says "What is today's date?"
    events_3 = [e async for e in agent.run_agent("What is today's date?", session_id, conversation_id)]
    done_3 = next(e for e in events_3 if e["type"] == "done")
    expected_today = date.today().strftime("%B %d, %Y")
    assert f"Today is {expected_today}." in done_3["answer"]

    # Step 4: User says "I want to visit on 17th."
    with patch("app.sru_agent.agent.date") as mock_date:
        mock_date.today.return_value = date(2026, 11, 16)
        events_4 = [e async for e in agent.run_agent("I want to visit on 17th.", session_id, conversation_id)]
        done_4 = next(e for e in events_4 if e["type"] == "done")
        assert "Do you mean November 17, 2026?" in done_4["answer"]

    # Step 5: User says "Yes."
    events_5 = [e async for e in agent.run_agent("Yes.", session_id, conversation_id)]
    done_5 = next(e for e in events_5 if e["type"] == "done")
    assert "Great! Let me help you submit a campus visit request for November 17, 2026." in done_5["answer"]
    assert any(c.get("type") == "campus_visit_form" for c in done_5["cards"])
    visit_card = next(c for c in done_5["cards"] if c.get("type") == "campus_visit_form")
    assert visit_card.get("suggested_date") == "2026-11-17"


@pytest.mark.asyncio
async def test_memory_isolation_across_conversations():
    """Verify that conversation history from chat A never leaks into chat B."""
    session_id = "test-session-leakage"
    conv_a = "conv-a"
    conv_b = "conv-b"

    await memory.append_history(session_id, "I want to visit campus", "We can book a tour", conv_a)

    history_a = await memory.get_history(session_id, conv_a)
    history_b = await memory.get_history(session_id, conv_b)

    assert len(history_a) == 2
    assert len(history_b) == 0  # conv_b is completely fresh and unpolluted!
