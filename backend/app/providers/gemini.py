"""Google Gemini LLM provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider that communicates with Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-lite"):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        self.api_key = api_key
        # Automatically upgrade deprecated/unavailable models
        legacy_models = {
            "gemini-2.0-flash": "gemini-3.1-flash-lite",
            "gemini-2.0-flash-lite": "gemini-3.1-flash-lite",
            "gemini-2.5-flash": "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite": "gemini-3.1-flash-lite",
            "gemini-1.5-flash": "gemini-3.1-flash-lite",
            "gemini-1.5-flash-8b": "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite": "gemini-3.1-flash-lite",
        }
        self.model = legacy_models.get(model, model)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"x-goog-api-key": self.api_key},
        )

    def _format_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict:
        """Convert standard role/content messages to Gemini API format."""
        contents = []
        system_parts = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue

            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        merged_contents = []
        for item in contents:
            if merged_contents and merged_contents[-1]["role"] == item["role"]:
                merged_contents[-1]["parts"].extend(item["parts"])
            else:
                merged_contents.append(item)

        generation_config: dict = {
            "temperature": temperature,
        }
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens

        payload: dict = {
            "contents": merged_contents,
            "generationConfig": generation_config,
        }

        if system_parts:
            payload["system_instruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }

        return payload

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send messages to Gemini and return the full response with automatic quota fallback."""
        payload = self._format_payload(messages, temperature, max_tokens)
        models_to_try = [self.model] + [
            m
            for m in [
                "gemini-3.1-flash-lite",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.5-flash-lite",
                "gemini-flash-latest",
            ]
            if m != self.model
        ]

        last_response = None
        for model_name in models_to_try:
            url = f"{self.base_url}/models/{model_name}:generateContent"
            try:
                response = await self._client.post(url, json=payload)
                last_response = response
                if response.status_code == 200:
                    self.model = model_name
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return ""
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text", "") for p in parts)
                elif response.status_code in (429, 404, 503):
                    logger.warning(
                        "Gemini model '%s' returned status %d. Auto-falling back to next available model.",
                        model_name,
                        response.status_code,
                    )
                    continue
                else:
                    response.raise_for_status()
            except httpx.TimeoutException:
                logger.warning("Gemini model '%s' timed out. Trying next candidate...", model_name)
                continue

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("All available Gemini models are currently exhausted or unreachable.")

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from Gemini with automatic quota fallback."""
        payload = self._format_payload(messages, temperature, max_tokens)
        models_to_try = [self.model] + [
            m
            for m in [
                "gemini-3.1-flash-lite",
                "gemini-3.8-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.5-flash-lite",
                "gemini-flash-latest",
            ]
            if m != self.model
        ]

        for model_name in models_to_try:
            url = f"{self.base_url}/models/{model_name}:streamGenerateContent?alt=sse"
            try:
                async with self._client.stream("POST", url, json=payload) as response:
                    if response.status_code in (429, 404, 503):
                        logger.warning(
                            "Gemini stream '%s' returned status %d. Auto-falling back to next model.",
                            model_name,
                            response.status_code,
                        )
                        continue
                    response.raise_for_status()
                    self.model = model_name
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        json_str = line[len("data: ") :]
                        try:
                            data = json.loads(json_str)
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    text = p.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue
                    return
            except httpx.TimeoutException:
                continue

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
