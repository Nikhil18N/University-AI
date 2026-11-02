"""Tests for Gemini LLM and Embedding providers."""

import pytest
from app.providers.gemini import GeminiProvider
from app.providers.embedding_gemini import GeminiEmbeddingProvider


def test_gemini_provider_init_requires_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key="")


def test_gemini_embedding_provider_init_requires_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiEmbeddingProvider(api_key="")


def test_gemini_message_conversion():
    provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")
    messages = [
        {"role": "system", "content": "You are a university helper."},
        {"role": "user", "content": "What are the timings?"},
        {"role": "assistant", "content": "9am to 5pm"},
        {"role": "user", "content": "Thank you"},
    ]

    system_instruction, contents = provider._convert_messages(messages)

    assert system_instruction == {"parts": [{"text": "You are a university helper."}]}
    assert len(contents) == 3
    assert contents[0] == {"role": "user", "parts": [{"text": "What are the timings?"}]}
    assert contents[1] == {"role": "model", "parts": [{"text": "9am to 5pm"}]}
    assert contents[2] == {"role": "user", "parts": [{"text": "Thank you"}]}
