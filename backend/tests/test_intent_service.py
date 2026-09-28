"""Tests for intent classification service."""

import pytest
from app.providers.base import LLMProvider
from app.services.intent_service import classify_intent, fast_classify


class MockLLM(LLMProvider):
    def __init__(self, response: str):
        self.response = response

    async def generate(self, messages, temperature=0.7, max_tokens=None):
        return self.response

    async def stream(self, messages, temperature=0.7, max_tokens=None):
        yield self.response


def test_fast_classify():
    assert fast_classify("hello") == "GREETING"
    assert fast_classify("goodbye") == "GOODBYE"
    assert fast_classify("thanks") == "THANKS"
    assert fast_classify("how are you") == "HOW_ARE_YOU"
    assert fast_classify("what can you do") == "HELP"
    assert fast_classify("my attendance") == "STUDENT_SPECIFIC"
    assert fast_classify("exam schedule") == "UNIVERSITY"


@pytest.mark.asyncio
async def test_classify_intent_fast_path():
    intent, conf = await classify_intent("hello there")
    assert intent == "GREETING"
    assert conf > 0.9


@pytest.mark.asyncio
async def test_classify_intent_llm_fallback():
    mock_llm = MockLLM('{"intent": "UNIVERSITY", "confidence": 0.92, "needs_clarification": false}')
    intent, conf = await classify_intent(
        "Is there an academic break in March?",
        conversation_context="",
        llm_provider=mock_llm,
    )
    assert intent == "UNIVERSITY"
    assert conf == 0.92


@pytest.mark.asyncio
async def test_classify_intent_llm_markdown_json():
    mock_llm = MockLLM('```json\n{"intent": "GENERAL_CONVERSATION", "confidence": 0.88}\n```')
    intent, conf = await classify_intent(
        "Tell me a joke about computer science",
        conversation_context="",
        llm_provider=mock_llm,
    )
    assert intent == "GENERAL_CONVERSATION"
    assert conf == 0.88
