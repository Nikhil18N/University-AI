"""Tests for query reformulation service."""

import pytest
from app.providers.base import LLMProvider
from app.services.reformulation_service import (
    needs_reformulation,
    reformulate_query,
)


class MockLLM(LLMProvider):
    async def generate(self, messages, temperature=0.7, max_tokens=None):
        # Returns a mock reformulated standalone query
        return "What are the hostel curfew hours and late entry penalties?"

    async def stream(self, messages, temperature=0.7, max_tokens=None):
        yield "mock"


def test_needs_reformulation_no_context():
    assert needs_reformulation("When does it close?", "") is False


def test_needs_reformulation_with_pronouns():
    context = "user: Tell me about hostel regulations\nassistant: Hostels have rules."
    assert needs_reformulation("When does it close?", context) is True
    assert needs_reformulation("How much is that?", context) is True
    assert needs_reformulation("What about single rooms?", context) is True


def test_no_reformulation_needed_for_standalone():
    context = "user: Tell me about labs\nassistant: SR University has modern engineering labs."
    # Long standalone query without coreferences
    query = "What is the tuition fee structure for undergraduate engineering programs?"
    assert needs_reformulation(query, context) is False
    # Short standalone topic queries must NOT be reformulated with previous context
    assert needs_reformulation("about placements?", context) is False
    assert needs_reformulation("placements?", context) is False
    assert needs_reformulation("hostel fees?", context) is False
    assert needs_reformulation("bus routes?", context) is False


def test_needs_reformulation_for_continuation():
    context = "user: Tell me about admissions\nassistant: Admissions are open."
    assert needs_reformulation("tell me more", context) is True
    assert needs_reformulation("more details", context) is True
    assert needs_reformulation("details please", context) is True


@pytest.mark.asyncio
async def test_reformulate_query():
    context = "user: Tell me about hostel regulations\nassistant: Hostels have rules."
    mock_llm = MockLLM()
    reformulated = await reformulate_query(
        "When does it close?",
        conversation_context=context,
        llm_provider=mock_llm,
    )
    assert reformulated == "What are the hostel curfew hours and late entry penalties?"
