"""Ollama LLM provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider that talks to a local Ollama instance."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send messages to Ollama and return the full response."""
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama."""
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with self._client.stream(
            "POST", "/api/chat", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
