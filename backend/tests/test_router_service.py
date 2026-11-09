"""Tests for query router service and decomposition."""

import json
import pytest
from unittest.mock import AsyncMock

from app.services.router_service import (
    route_and_decompose_message,
    _clean_json_output,
)


def test_clean_json_output():
    raw_md = "```json\n{\"parts\": [{\"text\": \"Hi\", \"type\": \"chitchat\"}], \"interests\": []}\n```"
    cleaned = _clean_json_output(raw_md)
    data = json.loads(cleaned)
    assert data["parts"][0]["type"] == "chitchat"


@pytest.mark.asyncio
async def test_fast_router_patterns():
    mock_llm = AsyncMock()

    # Fast chitchat
    res = await route_and_decompose_message(mock_llm, "Hi there!")
    assert res["parts"][0]["type"] == "chitchat"
    assert mock_llm.generate.call_count == 0

    # Fast sensitive
    res_sens = await route_and_decompose_message(mock_llm, "I don't want to live anymore")
    assert res_sens["parts"][0]["type"] == "sensitive"
    assert mock_llm.generate.call_count == 0

    # Fast out of scope
    res_oos = await route_and_decompose_message(mock_llm, "Who won the cricket match yesterday?")
    assert res_oos["parts"][0]["type"] == "out_of_scope"
    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_llm_decomposition():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = json.dumps({
        "parts": [
            {"text": "Is the CSE program good?", "type": "persuasive"},
            {"text": "What is the fee for B.Tech CSE?", "type": "factual"},
        ],
        "interests": ["Computer Science", "CSE"],
    })

    res = await route_and_decompose_message(
        mock_llm,
        "Is the CSE program good and what are its fees?",
        conversation_context="User: Hello\nAssistant: Welcome to SR University!",
    )
    assert len(res["parts"]) == 2
    assert res["parts"][0]["type"] == "persuasive"
    assert res["parts"][1]["type"] == "factual"
    assert "Computer Science" in res["interests"]


@pytest.mark.asyncio
async def test_router_fallback_on_invalid_json():
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "Not valid JSON at all!"

    res = await route_and_decompose_message(mock_llm, "Tell me about CSE eligibility")
    assert len(res["parts"]) == 1
    assert res["parts"][0]["type"] == "factual"
    assert res["parts"][0]["text"] == "Tell me about CSE eligibility"


@pytest.mark.parametrize(
    "phrase, language_flavor",
    [
        ("I feel like ending it all", "English"),
        ("suicide feels like my only option", "English"),
        ("I am feeling hopeless about my future", "English"),
        ("lost all hope and don't want to live", "English"),
        ("jeevitham meeda asha poindi", "Telugu-English"),
        ("inka nenu chasthe bagunnu", "Telugu-English"),
        ("pranam theesukunta", "Telugu-English"),
        ("jeevitham meeda virakthi vachindi", "Telugu-English"),
        ("bathakali ani ledu inka", "Telugu-English"),
        ("koi umeed nahi bachi mere paas", "Hinglish"),
        ("marne ka mann kar raha hai", "Hinglish"),
        ("sab khatam ho gaya sab khatam karna chahta hu", "Hinglish"),
        ("zindagi se tang aa gaya hu", "Hinglish"),
    ],
)
@pytest.mark.asyncio
async def test_multilingual_distress_fast_path_zero_llm_calls(phrase, language_flavor):
    """10+ multilingual distress phrases must route to sensitive in pure regex with 0 LLM calls (T8)."""
    mock_llm = AsyncMock()
    res = await route_and_decompose_message(mock_llm, phrase)

    assert len(res["parts"]) == 1
    assert res["parts"][0]["type"] == "sensitive", f"Failed for {language_flavor}: {phrase}"
    assert mock_llm.generate.call_count == 0, f"LLM was called unexpectedly for fast-path {phrase}"


@pytest.mark.asyncio
async def test_router_fallback_detects_distress_on_broken_json():
    """If LLM router returns broken JSON, fallback must check distress regex rather than blind factual default."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "Garbage router response {broken"

    res = await route_and_decompose_message(mock_llm, "sab khatam ho gaya")
    assert len(res["parts"]) == 1
    assert res["parts"][0]["type"] == "sensitive"


@pytest.mark.asyncio
async def test_combined_query_sensitive_takeover_no_fees():
    """A combined query like 'fees for CSE and I feel like ending it all' must yield ONLY sensitive assistance."""
    from app.services.chat_service import execute_prompt_pack_pipeline

    mock_llm = AsyncMock()
    # Mock LLM generating compassionate distress reply without marketing
    mock_llm.generate.return_value = (
        "I hear how much pain you are in right now. Please talk to someone who can help. "
        "National Student Support Helplines: Tele-MANAS (14416 / 1800-891-4416), AASRA (+91-9820466726)."
    )

    combined_msg = "What is the fees for B.Tech CSE and I feel like ending it all"
    ans, sources = await execute_prompt_pack_pipeline(
        message=combined_msg,
        conversation_context="",
        profile={},
        llm=mock_llm,
        rag_service=None,
    )

    assert sources == []
    assert "Tele-MANAS" in ans or "14416" in ans
    assert "₹" not in ans
    assert "1,25,000" not in ans
    assert "per year" not in ans.lower()


