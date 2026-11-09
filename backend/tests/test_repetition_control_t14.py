from unittest.mock import AsyncMock
import pytest
from app.services.session_state_service import (
    extract_opener_pattern,
    is_opener_repeating,
    record_opener,
    get_recent_openers,
    record_told_claims,
    get_told_claims,
)
from app.services.router_service import route_and_decompose_message
from pathlib import Path

def test_extract_opener_pattern():
    text = "It can feel a bit overwhelming when choosing a college."
    pattern = extract_opener_pattern(text)
    assert pattern == "it can feel a bit"

    short = "Hello there!"
    assert extract_opener_pattern(short) == "hello there"

    empty = ""
    assert extract_opener_pattern(empty) == ""


def test_is_opener_repeating():
    recent = ["it can feel a bit", "welcome to our campus today"]
    assert is_opener_repeating("It can feel a bit stressful", recent) is True
    assert is_opener_repeating("Welcome to our campus today friend", recent) is True
    assert is_opener_repeating("Here are the direct details for you", recent) is False
    assert is_opener_repeating("", recent) is False
    assert is_opener_repeating("Any text here", []) is False


@pytest.mark.asyncio
async def test_record_and_get_recent_openers():
    session_id = "test-session-opener-123"
    await record_opener(session_id, "Hello, nice to meet you!")
    await record_opener(session_id, "Let me explain the fees structure")

    openers = await get_recent_openers(session_id)
    assert len(openers) >= 2
    assert "hello nice to meet you" in openers
    assert "let me explain the fees" in openers


@pytest.mark.asyncio
async def test_record_and_get_told_claims():
    session_id = "test-session-claims-123"
    await record_told_claims(session_id, ["HL_CAMPUS_SPORTS", "HL_PLACEMENTS_STATS"])
    told = await get_told_claims(session_id)
    assert "HL_CAMPUS_SPORTS" in told
    assert "HL_PLACEMENTS_STATS" in told

    # Adding duplicate should not cause duplicates
    await record_told_claims(session_id, ["HL_CAMPUS_SPORTS", "HL_INNOVATION_SRIX"])
    told2 = await get_told_claims(session_id)
    assert "HL_INNOVATION_SRIX" in told2
    assert len(told2) == 3


@pytest.mark.asyncio
async def test_router_emotion_classification():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "confused between CSE and AI", "type": "persuasive"}], "interests": [], "emotion": "mild"}'

    # Distress message (fast-path sensitive)
    res_distress = await route_and_decompose_message(mock_llm, "I don't want to live anymore")
    assert res_distress is not None
    assert res_distress.get("emotion") == "strong"

    # Factual message (fast-path or general)
    mock_llm.generate.return_value = '{"parts": [{"text": "What is the fee for B.Tech CSE?", "type": "factual"}], "interests": [], "emotion": "none"}'
    res_factual = await route_and_decompose_message(mock_llm, "What is the fee for B.Tech CSE?")
    assert res_factual is not None
    assert res_factual.get("emotion") == "none"

    # Mild confusion message
    mock_llm.generate.return_value = '{"parts": [{"text": "confused", "type": "persuasive"}], "interests": [], "emotion": "mild"}'
    res_mild = await route_and_decompose_message(mock_llm, "I am a bit confused between CSE and AI branches")
    assert res_mild is not None
    assert res_mild.get("emotion") == "mild"


def test_persona_prompt_no_overwhelming_stock_phrase():
    persona_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "persona.md"
    content = persona_path.read_text()
    # Ensure it's forbidden as a stock opening phrase
    assert "Never open plain factual or eligibility questions with boilerplate sympathy" in content
    assert "Emotion gating" in content
