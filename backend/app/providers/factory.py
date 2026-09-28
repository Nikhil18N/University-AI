"""Provider factory — creates the correct provider based on config."""

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider


def create_llm_provider() -> LLMProvider:
    """Create an LLM provider based on the configured LLM_PROVIDER."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "ollama":
        from app.providers.ollama import OllamaProvider
        return OllamaProvider(
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Supported: ollama"
        )


def create_embedding_provider() -> EmbeddingProvider:
    """Create an embedding provider based on the configured EMBEDDING_PROVIDER."""
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "ollama":
        from app.providers.embedding_ollama import OllamaEmbeddingProvider
        return OllamaEmbeddingProvider(
            base_url=settings.LLM_BASE_URL,
            model=settings.EMBEDDING_MODEL,
        )
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. Supported: ollama"
        )
