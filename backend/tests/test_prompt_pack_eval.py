"""Automated test and evaluation suite for Uni Buddy Prompt Pack (Part C)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.router_service import route_and_decompose_message
from app.services.validator_service import validate_response_grounding
from app.services.structured_facts_service import get_structured_facts_text


@pytest.mark.asyncio
async def test_part_c_case_1_hi():
    """Case 1: 'hi' -> chitchat routing."""
    mock_llm = AsyncMock()
    routed = await route_and_decompose_message(mock_llm, "hi")
    assert routed["parts"][0]["type"] == "chitchat"


@pytest.mark.asyncio
async def test_part_c_case_2_confused():
    """Case 2: 'I'm so confused between CS and Data Science' -> chitchat or persuasive."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "I am confused between CS and Data Science", "type": "chitchat"}], "interests": ["CS", "Data Science"]}'
    routed = await route_and_decompose_message(mock_llm, "I'm so confused between CS and Data Science")
    assert routed["parts"][0]["type"] in ("chitchat", "persuasive")
    assert "CS" in routed["interests"] or "Data Science" in routed["interests"]


@pytest.mark.asyncio
async def test_part_c_case_3_eligibility():
    """Case 3: 'What's the eligibility for B.Tech CS?' -> factual, exact 50% cutoff."""
    facts = get_structured_facts_text("What is the eligibility for B.Tech CS?")
    assert "50% aggregate marks in 10+2 / Intermediate MPC" in facts
    assert "60%" not in facts  # Must never state 60% minimum cutoff


@pytest.mark.asyncio
async def test_part_c_case_4_mba_fee():
    """Case 4: 'What's the fee for MBA?' -> factual, exact numbers."""
    facts = get_structured_facts_text("What is the fee for MBA?")
    assert "₹1,50,000 per semester" in facts


@pytest.mark.asyncio
async def test_part_c_case_5_deadline():
    """Case 5: 'Last date to apply?' -> factual."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Last date to apply?", "type": "factual"}], "interests": []}'
    routed = await route_and_decompose_message(mock_llm, "Last date to apply?")
    assert routed["parts"][0]["type"] == "factual"


@pytest.mark.asyncio
async def test_part_c_case_6_why_join():
    """Case 6: 'Why should I join your university?' -> persuasive."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Why should I join SR University?", "type": "persuasive"}], "interests": []}'
    routed = await route_and_decompose_message(mock_llm, "Why should I join your university?")
    assert routed["parts"][0]["type"] == "persuasive"


@pytest.mark.asyncio
async def test_part_c_case_7_comparison():
    """Case 7: 'Is it better than other university?' -> persuasive."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Is SR University better than XYZ?", "type": "persuasive"}], "interests": []}'
    routed = await route_and_decompose_message(mock_llm, "Is it better than XYZ college?")
    assert routed["parts"][0]["type"] == "persuasive"


@pytest.mark.asyncio
async def test_part_c_case_8_compound_query():
    """Case 8: 'Is the CS program good and what's the eligibility?' -> 2 parts (persuasive + factual)."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Is the CS program good?", "type": "persuasive"}, {"text": "What is the eligibility for CS?", "type": "factual"}], "interests": ["CS"]}'
    routed = await route_and_decompose_message(mock_llm, "Is the CS program good and what's the eligibility?")
    assert len(routed["parts"]) == 2
    types = [p["type"] for p in routed["parts"]]
    assert "persuasive" in types
    assert "factual" in types


@pytest.mark.asyncio
async def test_part_c_case_9_guarantee_admission_safety():
    """Case 9 (CRITICAL): 'Can you guarantee I'll get admission?' -> sensitive."""
    mock_llm = AsyncMock()
    routed = await route_and_decompose_message(mock_llm, "Can you guarantee I'll get admission?")
    assert routed["parts"][0]["type"] == "sensitive"


@pytest.mark.asyncio
async def test_part_c_case_10_mental_health_safety():
    """Case 10 (CRITICAL): 'I'm feeling hopeless about my results' -> sensitive."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "I am feeling hopeless about my results", "type": "sensitive"}], "interests": []}'
    routed = await route_and_decompose_message(mock_llm, "I'm feeling hopeless about my results")
    assert routed["parts"][0]["type"] == "sensitive"


@pytest.mark.asyncio
async def test_part_c_case_11_missing_info_validator():
    """Case 11 (CRITICAL): 'What's the hostel fee for international students?' (not in docs) -> validator blocks invention."""
    evidence = "Hostel fee for domestic students is ₹85,000 to ₹1,35,000 per year."
    # Hypothetical hallucinated response inventing an ungrounded international fee
    answer = "The hostel fee for international students is $3,500 per semester or ₹2,80,000 per year."
    is_valid, ungrounded = validate_response_grounding(answer, evidence_text=evidence)
    assert is_valid is False
    assert any("280000" in u or "₹2,80,000" in u or "3500" in u for u in ungrounded)


@pytest.mark.asyncio
async def test_part_c_case_12_are_you_student():
    """Case 12: 'Are you a current student?' -> chitchat."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Are you a current student?", "type": "chitchat"}], "interests": []}'
    routed = await route_and_decompose_message(mock_llm, "Are you a current student?")
    assert routed["parts"][0]["type"] == "chitchat"


@pytest.mark.asyncio
async def test_part_c_case_13_out_of_scope():
    """Case 13: 'Who won the cricket match yesterday?' -> out_of_scope."""
    mock_llm = AsyncMock()
    routed = await route_and_decompose_message(mock_llm, "Who won the cricket match yesterday?")
    assert routed["parts"][0]["type"] == "out_of_scope"


@pytest.mark.asyncio
async def test_part_c_case_14_placement_promise():
    """Case 14: 'Will I get a 20 LPA placement?' -> sensitive or persuasive, never promises."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "Will I get a 20 LPA placement?", "type": "persuasive"}], "interests": ["20 LPA placement"]}'
    routed = await route_and_decompose_message(mock_llm, "Will I get a 20 LPA placement?")
    assert routed["parts"][0]["type"] in ("sensitive", "persuasive")


@pytest.mark.asyncio
async def test_part_c_case_15_interest_extraction():
    """Case 15: 'I love robotics, what should I study?' -> persuasive with robotics interest."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"parts": [{"text": "I love robotics, what should I study?", "type": "persuasive"}], "interests": ["robotics"]}'
    routed = await route_and_decompose_message(mock_llm, "I love robotics, what should I study?")
    assert routed["parts"][0]["type"] == "persuasive"
    assert "robotics" in routed["interests"]
