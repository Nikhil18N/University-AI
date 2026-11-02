"""Unit tests for GeminiProvider and provider factory."""

import pytest
from app.providers.gemini import GeminiProvider
from app.providers.factory import create_llm_provider
from unittest.mock import AsyncMock, patch, MagicMock


def test_gemini_provider_requires_api_key():
    with pytest.raises(ValueError, match="Gemini API key is required"):
        GeminiProvider(api_key="")


def test_gemini_format_payload():
    provider = GeminiProvider(api_key="fake-test-key", model="gemini-2.0-flash")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Tell me about admissions."},
    ]
    payload = provider._format_payload(messages, temperature=0.5, max_tokens=100)

    assert "system_instruction" in payload
    assert payload["system_instruction"]["parts"][0]["text"] == "You are a helpful assistant."
    assert payload["generationConfig"]["temperature"] == 0.5
    assert payload["generationConfig"]["maxOutputTokens"] == 100
    assert len(payload["contents"]) == 3
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][1]["role"] == "model"
    assert payload["contents"][2]["role"] == "user"


@pytest.mark.asyncio
async def test_gemini_generate_success():
    provider = GeminiProvider(api_key="fake-test-key", model="gemini-2.0-flash")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Welcome to SR University!"}],
                    "role": "model",
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await provider.generate([{"role": "user", "content": "Hello"}])

        assert result == "Welcome to SR University!"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_gemini_generate_429_fallback():
    provider = GeminiProvider(api_key="fake-test-key", model="gemini-3.5-flash")

    # First call returns 429, second returns 200
    resp_429 = MagicMock()
    resp_429.status_code = 429

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Answer from fallback model"}],
                    "role": "model",
                }
            }
        ]
    }
    resp_200.raise_for_status = MagicMock()

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_429, resp_200]
        result = await provider.generate([{"role": "user", "content": "Hello"}])

        assert result == "Answer from fallback model"
        assert mock_post.call_count == 2
        assert provider.model == "gemini-3.1-flash-lite"


def test_factory_gemini_missing_key():
    with patch("app.config.settings.LLM_PROVIDER", "gemini"):
        with patch("app.config.settings.GEMINI_API_KEY", ""):
            with patch("app.config.settings.LLM_API_KEY", ""):
                with pytest.raises(ValueError, match="GEMINI_API_KEY or LLM_API_KEY is required"):
                    create_llm_provider()


def test_factory_gemini_success():
    with patch("app.config.settings.LLM_PROVIDER", "gemini"):
        with patch("app.config.settings.GEMINI_API_KEY", "test-key-123"):
            with patch("app.config.settings.LLM_MODEL", "gemini-3.5-flash"):
                p = create_llm_provider()
                assert isinstance(p, GeminiProvider)
                assert p.model == "gemini-3.5-flash"
                assert p.api_key == "test-key-123"


def test_gemini_legacy_model_upgrade():
    p = GeminiProvider(api_key="test-key-123", model="gemini-2.0-flash")
    assert p.model == "gemini-3.1-flash-lite"


@pytest.mark.asyncio
async def test_gemini_embedding_provider():
    from app.providers.embedding_gemini import GeminiEmbeddingProvider

    provider = GeminiEmbeddingProvider(api_key="fake-test-key")
    resp_batch = MagicMock()
    resp_batch.status_code = 200
    resp_batch.json.return_value = {
        "embeddings": [{"values": [0.1, 0.2, 0.3]}, {"values": [0.4, 0.5, 0.6]}]
    }
    resp_batch.raise_for_status = MagicMock()

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_batch
        res = await provider.embed(["doc1", "doc2"])
        assert len(res) == 2
        assert res[0] == [0.1, 0.2, 0.3]

    resp_single = MagicMock()
    resp_single.status_code = 200
    resp_single.json.return_value = {
        "embedding": {"values": [0.7, 0.8, 0.9]}
    }
    resp_single.raise_for_status = MagicMock()

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_single
        res_single = await provider.embed_single("query")
        assert res_single == [0.7, 0.8, 0.9]


def test_factory_gemini_embedding_provider():
    from app.providers.factory import create_embedding_provider
    from app.providers.embedding_gemini import GeminiEmbeddingProvider

    with patch("app.config.settings.EMBEDDING_PROVIDER", "gemini"):
        with patch("app.config.settings.GEMINI_API_KEY", "test-key-123"):
            emb = create_embedding_provider()
            assert isinstance(emb, GeminiEmbeddingProvider)

