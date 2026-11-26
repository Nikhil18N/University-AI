"""Google Gemini LLM provider implementation."""

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from app.providers.base import LLMProvider
from app.providers.key_pool import APIKeyPool

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider that communicates with Google Gemini API with multi-key pool failover."""

    def __init__(
        self,
        api_key: str | list[str] = "",
        model: str = "gemini-3.1-flash-lite",
        api_keys: list[str] | str | None = None,
    ):
        raw_keys = api_keys if api_keys is not None else api_key
        if not raw_keys:
            raise ValueError("Gemini API key is required.")
        self.key_pool = APIKeyPool(raw_keys)
        # Automatically upgrade deprecated/unavailable models to high-quota Flash Lite models (15 RPM / 500 RPD)
        legacy_models = {
            "gemini-2.0-flash": "gemini-3.5-flash-lite",
            "gemini-2.0-flash-lite": "gemini-3.5-flash-lite",
            "gemini-2.5-flash": "gemini-3.5-flash-lite",
            "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
            "gemini-1.5-flash": "gemini-3.5-flash-lite",
            "gemini-1.5-flash-8b": "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
        }
        self.model = legacy_models.get(model, model)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.last_usage: dict[str, int] | None = None
        self.last_latency_ms: float | None = None
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            # Keep a small pool of persistent connections so successive Gemini calls
            # (reformulate → generate → guardrail) reuse the same TCP connection.
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    @property
    def api_key(self) -> str:
        """Current active key for backwards compatibility."""
        return self.key_pool.get_current_key()

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

    @staticmethod
    def _extract_usage(data: dict) -> dict[str, int] | None:
        raw = data.get("usageMetadata")
        if not isinstance(raw, dict):
            return None
        return {
            "prompt_token_count": int(raw.get("promptTokenCount") or 0),
            "candidates_token_count": int(raw.get("candidatesTokenCount") or 0),
            "thoughts_token_count": int(raw.get("thoughtsTokenCount") or 0),
            "cached_content_token_count": int(raw.get("cachedContentTokenCount") or 0),
        }

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send messages to Gemini and return the full response with automatic multi-key and quota fallback."""
        payload = self._format_payload(messages, temperature, max_tokens)
        self.last_usage = None
        self.last_latency_ms = None
        t0 = time.perf_counter()
        # STRICT QUOTA PROTECTION:
        # Only use high-quota Flash-Lite models (15 RPM / 500 RPD).
        # NEVER fall back to 3.6-flash or 3.8-flash (5 RPM / 20 RPD) which burn the daily 20-call cap.
        models_to_try = [self.model]
        for fallback in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        total_keys = len(self.key_pool)
        last_response = None

        for model_name in models_to_try:
            url = f"{self.base_url}/models/{model_name}:generateContent"
            keys_tried_for_model = 0

            while keys_tried_for_model < total_keys:
                active_key = self.key_pool.get_next_key(advance=True)
                keys_tried_for_model += 1

                try:
                    response = await self._client.post(
                        url,
                        json=payload,
                        headers={"x-goog-api-key": active_key},
                    )
                    last_response = response

                    if response.status_code == 200:
                        self.key_pool.mark_success(active_key)
                        self.model = model_name
                        data = response.json()
                        self.last_usage = self._extract_usage(data)
                        self.last_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                        candidates = data.get("candidates", [])
                        if not candidates:
                            return ""
                        parts = candidates[0].get("content", {}).get("parts", [])
                        return "".join(p.get("text", "") for p in parts)
                    elif response.status_code in (401, 403, 429, 500, 502):
                        logger.warning(
                            "Gemini key %s hit HTTP %d on model '%s'. Rotating key.",
                            self.key_pool.label(active_key),
                            response.status_code,
                            model_name,
                        )
                        self.key_pool.mark_rate_limited(active_key)
                        if keys_tried_for_model < total_keys:
                            continue
                        else:
                            break
                    elif response.status_code in (404, 503):
                        logger.warning(
                            "Gemini model '%s' returned status %d. Auto-falling back to next available model.",
                            model_name,
                            response.status_code,
                        )
                        break
                    else:
                        response.raise_for_status()
                except httpx.TimeoutException:
                    logger.warning(
                        "Gemini model '%s' with key %s timed out. Trying next candidate...",
                        model_name,
                        self.key_pool.label(active_key),
                    )
                    continue

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("All available Gemini models and API keys are currently exhausted or unreachable.")

    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from Gemini with automatic multi-key and quota fallback."""
        payload = self._format_payload(messages, temperature, max_tokens)
        self.last_usage = None
        self.last_latency_ms = None
        t0 = time.perf_counter()
        # STRICT QUOTA PROTECTION:
        # Only use high-quota Flash-Lite models (15 RPM / 500 RPD).
        # NEVER fall back to 3.6-flash or 3.8-flash (5 RPM / 20 RPD) which burn the daily 20-call cap.
        models_to_try = [self.model]
        for fallback in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite"):
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        total_keys = len(self.key_pool)

        for model_name in models_to_try:
            url = f"{self.base_url}/models/{model_name}:streamGenerateContent?alt=sse"
            keys_tried_for_model = 0

            while keys_tried_for_model < total_keys:
                active_key = self.key_pool.get_next_key(advance=True)
                keys_tried_for_model += 1

                try:
                    async with self._client.stream(
                        "POST",
                        url,
                        json=payload,
                        headers={"x-goog-api-key": active_key},
                    ) as response:
                        if response.status_code in (401, 403, 429, 500, 502):
                            logger.warning(
                                "Gemini stream key %s hit status %d on model '%s'. Rotating key.",
                                self.key_pool.label(active_key),
                                response.status_code,
                                model_name,
                            )
                            self.key_pool.mark_rate_limited(active_key)
                            if keys_tried_for_model < total_keys:
                                continue
                            else:
                                break
                        elif response.status_code in (404, 503):
                            logger.warning(
                                "Gemini stream '%s' returned status %d. Auto-falling back to next model.",
                                model_name,
                                response.status_code,
                            )
                            break
                        response.raise_for_status()
                        self.key_pool.mark_success(active_key)
                        self.model = model_name
                        async for line in response.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            json_str = line[len("data: ") :]
                            try:
                                data = json.loads(json_str)
                                usage = self._extract_usage(data)
                                if usage is not None:
                                    self.last_usage = usage
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for p in parts:
                                        text = p.get("text", "")
                                        if text:
                                            yield text
                            except json.JSONDecodeError:
                                continue
                        self.last_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                        return
                except httpx.TimeoutException:
                    continue

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
