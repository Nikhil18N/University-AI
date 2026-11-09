"""Unit tests for Fact-check, Comparison intents, and Scoped Statistics (T16)."""

from unittest.mock import AsyncMock
import pytest

from app.services.prompt_service import render_prompt
from app.services.router_service import route_and_decompose_message
from app.services.structured_facts_service import CANONICAL_STATISTICS, get_structured_facts_text
from app.services.validator_service import verify_statistics_scoping


@pytest.mark.asyncio
async def test_router_classifies_fact_check():
    mock_llm = AsyncMock()
    # Fast regex path or LLM fallback
    routed = await route_and_decompose_message(
        mock_llm,
        "My friend said this university is best at placements compared to other universities? fact check",
    )
    assert any(p["type"] == "fact_check" for p in routed["parts"])


@pytest.mark.asyncio
async def test_router_classifies_comparison():
    mock_llm = AsyncMock()
    routed = await route_and_decompose_message(
        mock_llm,
        "Is SR University better than other colleges in Hyderabad?",
    )
    assert any(p["type"] == "comparison" for p in routed["parts"])


@pytest.mark.asyncio
async def test_router_classifies_social_proof_doubt():
    mock_llm = AsyncMock()
    routed = await route_and_decompose_message(
        mock_llm,
        "My friend told me not to join SR University",
    )
    assert any(p["type"] == "social_proof_doubt" for p in routed["parts"])


def test_verify_statistics_scoping_average_package():
    # Pass: scoped with batch year and graduating students
    valid_text = "For the 2023–24 graduating batch university-wide, the average placement package was 6 LPA."
    is_valid, reasons = verify_statistics_scoping(valid_text)
    assert is_valid is True
    assert len(reasons) == 0

    # Fail: naked 6 LPA without scope or year
    invalid_text = "The package is 6 LPA."
    is_valid, reasons = verify_statistics_scoping(invalid_text)
    assert is_valid is False
    assert any("6 LPA" in r for r in reasons)


def test_verify_statistics_scoping_highest_package():
    # Pass: scoped with recruiter Microsoft and batch
    valid_text = "The highest package was 51 LPA from Microsoft for the 2023-24 batch."
    is_valid, reasons = verify_statistics_scoping(valid_text)
    assert is_valid is True

    # Fail: naked 51 LPA without recruiter or batch
    invalid_text = "The highest package offered is 51 LPA."
    is_valid, reasons = verify_statistics_scoping(invalid_text)
    assert is_valid is False
    assert any("51 LPA" in r for r in reasons)


def test_verify_statistics_scoping_nirf():
    # Pass: 91st with 2025
    valid_text = "SR University is ranked 91st in NIRF Engineering 2025."
    is_valid, reasons = verify_statistics_scoping(valid_text)
    assert is_valid is True

    # Fail: 91st without 2025
    invalid_text = "We are ranked 91st in NIRF."
    is_valid, reasons = verify_statistics_scoping(invalid_text)
    assert is_valid is False
    assert any("2025" in r for r in reasons)


def test_structured_facts_includes_canonical_scoping():
    facts_text = get_structured_facts_text("placement package average highest")
    assert "average_package" in facts_text
    assert "2023–24" in facts_text
    assert "university-wide" in facts_text
    assert "Microsoft" in facts_text


def test_render_fact_check_prompt():
    prompt = render_prompt(
        "fact_check",
        intent_type="fact_check",
        part_text="is it true that placements are best?",
        student_profile="Prospective student",
        retrieved_context="Average package 6 LPA, High 51 LPA",
    )
    assert "fact_check" in prompt
    assert "placements are best" in prompt
    assert "Superlatives" in prompt or "superlatives" in prompt or "Rules" in prompt

