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
    cards = generate_cards(
        user_message="How much is the fee for B.Tech?",
        answer="The tuition fee is 1,40,000 per year.",
    )
    assert len(cards) >= 1
    assert cards[0]["type"] == "fee_breakdown"
    assert len(cards[0]["items"]) >= 3


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


def test_time_aware_greeting():
    greeting = get_conversational_response("GREETING", has_context=False)
    assert "SRU Buddy" in greeting or "SR University" in greeting
