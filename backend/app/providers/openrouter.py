"""OpenRouter LLM provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.providers.base import LLMProvider

import re

logger = logging.getLogger(__name__)


def _clean_reasoning(text: str) -> str:
    """Strip internal chain-of-thought traces (e.g. <think> or Thinking Process:)."""
    if not text:
        return ""
    # Strip <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # If the response contains Thinking Process followed by Final Version or Answer
    if "Thinking Process:" in text:
        match = re.search(
            r"(?:Final\s+(?:Version|Answer|Draft)|Response):\s*[\"']?(.*)",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if match:
            text = match.group(1).rstrip("\"'")
        else:
            # Drop thinking headers/lines if uncompleted
            lines = [
                line
                for line in text.splitlines()
                if not line.strip().startswith(("Thinking Process:", "1.", "2.", "3.", "4.", "5.", "6.", "*", "-"))
            ]
            text = "\n".join(lines)
    return text.strip()


class OpenRouterProvider(LLMProvider):
    """LLM provider that communicates with OpenRouter API."""

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        if not api_key:
            raise ValueError("OpenRouter API key is required.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "University AI Companion",
            },
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send messages to OpenRouter and return full response."""
        effective_max_tokens = max_tokens or 1024
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
            "reasoning": {"enabled": False},
        }

        response = await self._client.post("/chat/completions", json=payload)
        if response.status_code == 404 and ":free" in self.model:
            logger.warning(
                "OpenRouter model '%s' returned 404. Retrying without ':free' suffix.",
                self.model,
            )
            self.model = self.model.replace(":free", "")
            payload["model"] = self.model
            response = await self._client.post("/chat/completions", json=payload)
        elif response.status_code == 429 and ":free" in self.model:
            fallback_model = "deepseek/deepseek-chat"
            logger.warning(
                "OpenRouter free-tier rate limit reached on '%s'. Falling back to '%s'.",
                self.model,
                fallback_model,
            )
            payload["model"] = fallback_model
            response = await self._client.post("/chat/completions", json=payload)

        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return ""

        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
        return _clean_reasoning(content)

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from OpenRouter."""
        effective_max_tokens = max_tokens or 1024
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": effective_max_tokens,
            "reasoning": {"enabled": False},
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[len("data: ") :]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
