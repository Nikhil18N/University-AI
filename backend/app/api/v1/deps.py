"""Dependencies for API routes."""

from typing import Any
from fastapi import Depends, Header, HTTPException, Request, status

from app.config import settings
from app.db.session import get_db
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.providers.factory import create_embedding_provider, create_llm_provider
from app.services.rag_service import RAGService

# Singletons (created once, reused)
_llm_provider: LLMProvider | None = None
_embedding_provider: EmbeddingProvider | None = None
_rag_service: RAGService | None = None


def get_llm_provider() -> LLMProvider:
    """Get or create the LLM provider singleton."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = create_llm_provider()
    return _llm_provider


def get_embedding_provider() -> EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = create_embedding_provider()
    return _embedding_provider


def get_rag_service(
    llm: LLMProvider = Depends(get_llm_provider),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
) -> RAGService:
    """Get or create the RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(llm, embeddings)
    return _rag_service


async def verify_admin_key(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> str:
    """Verify the admin API key from request header."""
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )
    return x_admin_key


def get_redis(request: Request) -> Any | None:
    """Return the Redis client from app state, or None if not configured."""
    return getattr(request.app.state, "redis", None)
