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
    assert fast_classify("hi") == "GREETING"
    assert fast_classify("goodbye") == "GOODBYE"
    assert fast_classify("thanks") == "THANKS"
    assert fast_classify("thank you") == "THANKS"
    assert fast_classify("how are you") == "HOW_ARE_YOU"
    assert fast_classify("what can you do") == "HELP"
    assert fast_classify("my attendance") == "STUDENT_SPECIFIC"
    assert fast_classify("exam schedule") == "UNIVERSITY"
    # Acknowledgment tests
    assert fast_classify("ok") == "ACKNOWLEDGMENT"
    assert fast_classify("okay") == "ACKNOWLEDGMENT"
    assert fast_classify("got it") == "ACKNOWLEDGMENT"
    assert fast_classify("cool") == "ACKNOWLEDGMENT"
    assert fast_classify("great") == "ACKNOWLEDGMENT"
    # Mixed greeting + university question should be UNIVERSITY
    assert fast_classify("how to apply for admission?") == "UNIVERSITY"
    assert fast_classify("Hi, how to apply for admission?") == "UNIVERSITY"
    assert fast_classify("Hello, tell me about placements") == "UNIVERSITY"
    assert fast_classify("about placements?") == "UNIVERSITY"
    # Document and requirement queries must be UNIVERSITY (not STUDENT_SPECIFIC)
    assert fast_classify("what are the required documents?") == "UNIVERSITY"
    assert fast_classify("required documents") == "UNIVERSITY"
    assert fast_classify("what documents do i need?") == "UNIVERSITY"
    # Clarifications and negations should be GENERAL (not STUDENT_SPECIFIC)
    assert fast_classify("i never mentioned my marks") == "GENERAL"
    assert fast_classify("i didn't share my marks") == "GENERAL"


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


def test_score_replies_classified_as_university_with_context():
    context = "assistant: What score did you get in your 12th exams?"
    assert fast_classify("93%", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("93", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("85% in PCM", conversation_context=context) == "UNIVERSITY"
    assert fast_classify("I scored 78%", conversation_context=context) == "UNIVERSITY"


@pytest.mark.asyncio
async def test_student_specific_guardrail_override():
    # If LLM hallucinates STUDENT_SPECIFIC on a simple number/answer, guardrail should override it
    mock_llm = MockLLM('{"intent": "STUDENT_SPECIFIC", "confidence": 0.95}')
    context = "assistant: What score did you achieve?"
    intent, _ = await classify_intent(
        "93%",
        conversation_context=context,
        llm_provider=mock_llm,
    )
    assert intent == "UNIVERSITY"

