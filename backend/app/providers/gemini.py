"""Google Gemini LLM provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """LLM provider that communicates with the Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-3.5-flash-lite"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) is required.")
        self.api_key = api_key
        # Strip 'models/' prefix if user provided it
        self.model = model.replace("models/", "")
        self._client = httpx.AsyncClient(
            base_url=GEMINI_BASE_URL,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    def _convert_messages(self, messages: list[dict[str, str]]) -> tuple[dict | None, list[dict]]:
        """Convert standard messages to Gemini contents and system instruction."""
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        # Gemini requires at least one user message
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        return system_instruction, contents

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send messages to Gemini and return the complete generated text."""
        system_instruction, contents = self._convert_messages(messages)

        payload: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        url = f"/models/{self.model}:generateContent?key={self.api_key}"
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as err:
            logger.error("Unexpected Gemini response structure: %s", data)
            raise ValueError("Invalid response format from Gemini API") from err

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens from Gemini using SSE."""
        system_instruction, contents = self._convert_messages(messages)

        payload: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        url = f"/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        data = json.loads(data_str)
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
