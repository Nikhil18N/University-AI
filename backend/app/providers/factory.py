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
        keys = settings.get_gemini_api_keys()
        if not keys:
            raise ValueError(
                "GEMINI_API_KEYS, GEMINI_API_KEY, or LLM_API_KEY is required when LLM_PROVIDER='gemini'."
            )
        model = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL.lower() else "gemini-3.5-flash-lite"
        return GeminiProvider(
            api_keys=keys,
            model=model,
        )
    elif provider in ("openrouter", "openai"):
        from app.providers.openrouter import OpenRouterProvider
        api_key = settings.OPENROUTER_API_KEY or settings.LLM_API_KEY
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY or LLM_API_KEY is required when LLM_PROVIDER='openrouter'."
            )
        model = settings.LLM_MODEL if settings.LLM_MODEL and not settings.LLM_MODEL.startswith("gemini") and not settings.LLM_MODEL.startswith("llama3") else "meta-llama/llama-3.3-70b-instruct:free"
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            base_url=settings.LLM_BASE_URL if "openrouter" not in settings.LLM_BASE_URL and "localhost" not in settings.LLM_BASE_URL else "https://openrouter.ai/api/v1",
        )
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. Supported: ollama, gemini, openrouter"
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
        keys = settings.get_gemini_api_keys()
        if not keys:
            raise ValueError(
                "GEMINI_API_KEYS, GEMINI_API_KEY, or LLM_API_KEY is required when EMBEDDING_PROVIDER='gemini'."
            )
        return GeminiEmbeddingProvider(
            api_keys=keys,
            model=settings.EMBEDDING_MODEL,
        )
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. Supported: ollama, gemini"
        )
