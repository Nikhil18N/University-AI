"""Tests for engagement features: suggestions, rich cards, guided flows, and streaming."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.schemas.chat import ChatRequest
from app.services.suggestion_service import generate_suggestions
from app.services.card_service import generate_cards
from app.services.flow_service import (
    detect_flow_trigger,
    get_wizard_step_from_history,
    execute_wizard_step,
)
from app.services.chat_service import handle_chat_stream, get_conversational_response


def test_suggestion_generation_eligibility():
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="Am I eligible with 93% in 12th?",
        answer="You are fully eligible for B.Tech CSE!",
    )
    assert any("How to Apply" in s for s in suggestions)
    assert len(suggestions) >= 3


def test_suggestion_generation_placements():
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="What are the placement statistics?",
        answer="Our highest package is 34 LPA with top recruiters.",
    )
    assert any("Recruiters" in s or "Package" in s for s in suggestions)


def test_suggestion_generation_comparison():
    suggestions = generate_suggestions(
        intent="UNIVERSITY",
        user_message="Compare CSE vs CSE AI and ML",
        answer="CSE covers broad core foundations while AI/ML specializes in data models.",
    )
    assert any("Lab Facilities" in s or "Compare" in s for s in suggestions)


def test_cards_comparison():
    cards = generate_cards(
        user_message="What is the difference between CSE and CSE AIML?",
        answer="Here is a breakdown of CSE vs AIML.",
    )
    assert len(cards) >= 1
    assert cards[0]["type"] == "comparison"
    assert len(cards[0]["columns"]) == 2


def test_cards_fee_breakdown():
    """Verify that fee breakdown cards are attached for general fee queries."""
    cards = generate_cards(
        user_message="What is the complete fee structure and merit scholarship details for B.Tech?",
        answer="The tuition fee is ₹1,47,500 per semester.",
    )
    assert len(cards) >= 1
    assert any(c.get("type") == "fee_breakdown" for c in cards)


def test_cards_curriculum():
    cards = generate_cards(
        user_message="What is the curriculum and subjects for CSE?",
        answer="The curriculum has core and elective components.",
    )
    assert len(cards) >= 1
    assert cards[0]["type"] == "curriculum"
    assert len(cards[0]["structure"]) >= 3


def test_cards_campus_tour():
    cards = generate_cards(
        user_message="Tell me about campus facilities and hostels",
        answer="SR University has a vibrant campus.",
    )
    assert any(c["type"] == "campus_tour" for c in cards)


def test_flow_trigger_detection():
    assert detect_flow_trigger("I want to start the admission wizard") == "admission_wizard"
    assert detect_flow_trigger("guided admission please") == "admission_wizard"
    assert detect_flow_trigger("random query") is None


def test_wizard_step_progression():
    # Step 1
    step1 = get_wizard_step_from_history([], "admission wizard")
    assert step1["step"] == 1
    assert "B.Tech" in step1["options"][0]

    # Step 2: after B.Tech selected
    step2 = get_wizard_step_from_history([{"role": "user", "content": "admission wizard"}], "B.Tech")
    assert step2["step"] == 2
    assert "CSE" in step2["options"][0]

    # Step 3: after branch selected
    step3 = get_wizard_step_from_history(
        [
            {"role": "user", "content": "admission wizard"},
            {"role": "user", "content": "B.Tech"},
        ],
        "CSE",
    )
    assert step3["step"] == 3

    # Step 4: after score selected (93%)
    step4 = get_wizard_step_from_history(
        [
            {"role": "user", "content": "admission wizard"},
            {"role": "user", "content": "B.Tech"},
            {"role": "user", "content": "CSE"},
        ],
        "93%",
    )
    assert step4["step"] == 4
    assert step4["is_eligible"] is True


def test_wizard_completion_prevents_loop():
    """Verify that once Step 4 is rendered, subsequent queries (like Hostel Details) exit the wizard."""
    step4_answer, _ = execute_wizard_step({
        "flow_name": "admission_wizard",
        "step": 4,
        "total_steps": 4,
        "step_title": "Eligibility Verdict & Next Steps",
        "degree": "B.Tech",
        "branch": "CSE (Core)",
        "score": "78%",
        "is_eligible": True,
        "completed": True,
    })
    history = [
        {"role": "user", "content": "admission wizard"},
        {"role": "assistant", "content": "Welcome to the SR University Admission Wizard! (Step 1 of 4)"},
        {"role": "user", "content": "B.Tech"},
        {"role": "assistant", "content": "Step 2 of 4: Select Your Branch"},
        {"role": "user", "content": "CSE"},
        {"role": "assistant", "content": "Step 3 of 4: Qualifying Percentage"},
        {"role": "user", "content": "78%"},
        {"role": "assistant", "content": step4_answer},
    ]

    # Follow-up button click or question must NOT re-trigger step 4
    next_step = get_wizard_step_from_history(history, "🏠 Hostel Details")
    assert next_step is None

    next_step_fee = get_wizard_step_from_history(history, "💰 Fee Structure")
    assert next_step_fee is None

    next_step_general = get_wizard_step_from_history(history, "What is the hostel fee?")
    assert next_step_general is None


def test_calculator_handoff_query_does_not_trigger_wizard():
    """Verify calculator handoff query does NOT falsely hijack into admission wizard."""
    calc_query = (
        "I evaluated the scholarship for B.Tech Computer Science and Engineering with 78% "
        "which qualifies for a 20% merit waiver (Payable: ₹60,000/sem). "
        "Please share details on admission verification and hostel accommodation."
    )
    assert detect_flow_trigger(calc_query) is None
    assert get_wizard_step_from_history([], calc_query) is None


def test_wizard_eligibility_50_percent_cutoff():
    """Verify 50% minimum MPC cutoff for B.Tech."""
    # 55% should be eligible (above 50% cutoff)
    step4_55 = get_wizard_step_from_history(
        [
            {"role": "user", "content": "admission wizard"},
            {"role": "user", "content": "B.Tech"},
            {"role": "user", "content": "CSE"},
        ],
        "55%",
    )
    assert step4_55["is_eligible"] is True

    # 45% should require additional guidance (below 50% cutoff)
    step4_45 = get_wizard_step_from_history(
        [
            {"role": "user", "content": "admission wizard"},
            {"role": "user", "content": "B.Tech"},
            {"role": "user", "content": "CSE"},
        ],
        "45%",
    )
    assert step4_45["is_eligible"] is False


def test_wizard_cancellation():
    """Verify that users can exit the wizard with cancel/stop keywords."""
    history = [
        {"role": "user", "content": "admission wizard"},
        {"role": "assistant", "content": "Welcome to the SR University Admission Wizard! (Step 1 of 4)"},
    ]
    assert get_wizard_step_from_history(history, "cancel") is None
    assert get_wizard_step_from_history(history, "stop") is None
    assert get_wizard_step_from_history(history, "nevermind") is None


def test_time_aware_greeting():
    greeting = get_conversational_response("GREETING", has_context=False)
    assert "SRU Buddy" in greeting or "SR University" in greeting
