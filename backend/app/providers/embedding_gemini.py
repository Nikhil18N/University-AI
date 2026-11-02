"""Google Gemini embedding provider implementation."""

import logging
import httpx

from app.providers.embedding_base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Gemini's current text embedding model — outputs 3072-dimensional vectors
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Google Gemini's text embedding models."""

    def __init__(self, api_key: str, model: str = GEMINI_EMBEDDING_MODEL):
        if not api_key:
            raise ValueError("Gemini API key is required for embeddings.")
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"x-goog-api-key": self.api_key},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using Gemini batchEmbedContents."""
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
        response = await self._client.post(url, json={"requests": requests})
        response.raise_for_status()
        data = response.json()
        return [item["values"] for item in data.get("embeddings", [])]

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single query text using Gemini embedContent."""
        url = f"{self.base_url}/models/{self.model}:embedContent"
        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
        }
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["embedding"]["values"]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
