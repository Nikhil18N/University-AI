"""Google Gemini embedding provider implementation."""

import asyncio
import logging
import httpx

from app.providers.embedding_base import EmbeddingProvider
from app.providers.key_pool import APIKeyPool

logger = logging.getLogger(__name__)

# Gemini's current text embedding model — outputs 3072-dimensional vectors
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Google Gemini's text embedding models with multi-key pool failover."""

    def __init__(
        self,
        api_key: str | list[str] = "",
        model: str = GEMINI_EMBEDDING_MODEL,
        api_keys: list[str] | str | None = None,
    ):
        raw_keys = api_keys if api_keys is not None else api_key
        if not raw_keys:
            raise ValueError("Gemini API key is required for embeddings.")
        self.key_pool = APIKeyPool(raw_keys)
        self.model = model.replace("models/", "")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    @property
    def api_key(self) -> str:
        """Current active key for backwards compatibility."""
        return self.key_pool.get_current_key()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using Gemini batchEmbedContents with multi-key failover."""
        if not texts:
            return []

        requests = [
            {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": t}]},
                "taskType": "RETRIEVAL_DOCUMENT",
            }
            for t in texts
        ]

        url = f"{self.base_url}/models/{self.model}:batchEmbedContents"
        total_keys = len(self.key_pool)
        last_response = None

        for attempt in range(max(total_keys, 3)):
            active_key = self.key_pool.get_next_key(advance=True)
            try:
                response = await self._client.post(
                    url,
                    json={"requests": requests},
                    headers={"x-goog-api-key": active_key},
                )
                last_response = response
                if response.status_code == 200:
                    self.key_pool.mark_success(active_key)
                    data = response.json()
                    return [item["values"] for item in data.get("embeddings", [])]
                elif response.status_code in (429, 403, 503):
                    logger.warning(
                        "Gemini embedding key '%s...' hit HTTP %d. Rotating key.",
                        active_key[:8],
                        response.status_code,
                    )
                    self.key_pool.mark_rate_limited(active_key)
                    await asyncio.sleep(1.0)
                    continue
                else:
                    response.raise_for_status()
            except httpx.TimeoutException:
                logger.warning("Gemini embedding request with key '%s...' timed out. Retrying...", active_key[:8])
                await asyncio.sleep(1.0)
                continue

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("All Gemini API keys exhausted or rate-limited for embeddings.")

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single query text using Gemini embedContent with multi-key failover."""
        url = f"{self.base_url}/models/{self.model}:embedContent"
        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
        }
        total_keys = len(self.key_pool)
        last_response = None

        for attempt in range(max(total_keys, 3)):
            active_key = self.key_pool.get_next_key(advance=True)
            try:
                response = await self._client.post(
                    url,
                    json=payload,
                    headers={"x-goog-api-key": active_key},
                )
                last_response = response
                if response.status_code == 200:
                    self.key_pool.mark_success(active_key)
                    data = response.json()
                    return data["embedding"]["values"]
                elif response.status_code in (429, 403, 503):
                    logger.warning(
                        "Gemini query embedding key '%s...' hit HTTP %d. Rotating key.",
                        active_key[:8],
                        response.status_code,
                    )
                    self.key_pool.mark_rate_limited(active_key)
                    await asyncio.sleep(1.0)
                    continue
                else:
                    response.raise_for_status()
            except httpx.TimeoutException:
                logger.warning("Gemini query embedding with key '%s...' timed out. Retrying...", active_key[:8])
                await asyncio.sleep(1.0)
                continue

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("All Gemini API keys exhausted or rate-limited for single embedding.")

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
