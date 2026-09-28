"""Ollama embedding provider implementation."""

import logging

import httpx

from app.providers.embedding_base import EmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Ollama's local embedding models."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Ollama processes one at a time."""
        embeddings = []
        for text in texts:
            embedding = await self.embed_single(text)
            embeddings.append(embedding)
        return embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text using Ollama."""
        response = await self._client.post(
            "/api/embed",
            json={"model": self.model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
