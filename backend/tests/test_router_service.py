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
