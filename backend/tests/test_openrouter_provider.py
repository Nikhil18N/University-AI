"""Unit tests for OpenRouterProvider and factory."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.openrouter import OpenRouterProvider
from app.providers.factory import create_llm_provider


def test_openrouter_provider_requires_api_key():
    with pytest.raises(ValueError, match="OpenRouter API key is required"):
        OpenRouterProvider(api_key="")


@pytest.mark.asyncio
async def test_openrouter_generate_success():
    provider = OpenRouterProvider(api_key="sk-or-test-key", model="meta-llama/llama-3.3-70b-instruct:free")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello from OpenRouter!",
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await provider.generate([{"role": "user", "content": "Hi"}])

        assert result == "Hello from OpenRouter!"
        mock_post.assert_called_once()


def test_factory_openrouter_missing_key():
    with patch("app.config.settings.LLM_PROVIDER", "openrouter"):
        with patch("app.config.settings.OPENROUTER_API_KEY", ""):
            with patch("app.config.settings.LLM_API_KEY", ""):
                with pytest.raises(ValueError, match="OPENROUTER_API_KEY or LLM_API_KEY is required"):
                    create_llm_provider()


def test_factory_openrouter_success():
    with patch("app.config.settings.LLM_PROVIDER", "openrouter"):
        with patch("app.config.settings.OPENROUTER_API_KEY", "sk-or-test-key"):
            with patch("app.config.settings.LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free"):
                p = create_llm_provider()
                assert isinstance(p, OpenRouterProvider)
                assert p.model == "meta-llama/llama-3.3-70b-instruct:free"
                assert p.api_key == "sk-or-test-key"
