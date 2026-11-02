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
    elif provider == "gemini":
        from app.providers.gemini import GeminiProvider
        api_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) must be set in environment variables.")
        return GeminiProvider(
            api_key=api_key,
            model=settings.LLM_MODEL,
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Supported: ollama, gemini"
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
    elif provider == "gemini":
        from app.providers.embedding_gemini import GeminiEmbeddingProvider
        api_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or GOOGLE_API_KEY) must be set in environment variables.")
        return GeminiEmbeddingProvider(
            api_key=api_key,
            model=settings.EMBEDDING_MODEL,
        )
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. Supported: ollama, gemini"
        )
