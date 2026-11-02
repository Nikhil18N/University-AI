"""Google Gemini embedding provider implementation."""

import logging
import httpx

from app.providers.embedding_base import EmbeddingProvider

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Google Gemini's text-embedding-004."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) is required.")
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self._client = httpx.AsyncClient(
            base_url=GEMINI_BASE_URL,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using batchEmbedContents."""
        if not texts:
            return []

        # Gemini supports batch requests up to 100 texts
        model_path = f"models/{self.model}"
        batch_size = 50
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            requests = [
                {
                    "model": model_path,
                    "content": {"parts": [{"text": text}]},
                }
                for text in chunk
            ]

            url = f"/{model_path}:batchEmbedContents?key={self.api_key}"
            response = await self._client.post(url, json={"requests": requests})
            response.raise_for_status()
            data = response.json()

            for item in data.get("embeddings", []):
                all_embeddings.append(item.get("values", []))

        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text using embedContent."""
        model_path = f"models/{self.model}"
        url = f"/{model_path}:embedContent?key={self.api_key}"
        payload = {
            "model": model_path,
            "content": {"parts": [{"text": text}]},
        }

        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["embedding"]["values"]

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
