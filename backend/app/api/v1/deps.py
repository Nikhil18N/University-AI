"""Dependencies for API routes."""

from typing import TYPE_CHECKING, Any
from fastapi import Depends, Header, HTTPException, Query, Request, status

from app.config import settings
from app.db.session import get_db
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.providers.factory import create_embedding_provider, create_llm_provider

if TYPE_CHECKING:
    from app.services.rag_service import RAGService

# Singletons (created once, reused)
_llm_provider: LLMProvider | None = None
_embedding_provider: EmbeddingProvider | None = None
_rag_service: Any = None


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
):
    """Get or create the RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        from app.services.rag_service import RAGService

        _rag_service = RAGService(llm, embeddings)
    return _rag_service


async def verify_admin_key(
    request: Request,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> str:
    """Verify the admin API key from the X-Admin-Key header (never from the URL).

    * The placeholder key that ships in the source code is public: on a production server (APP_ENV=production,
      on Render, or APP_DEBUG=false) it is refused and the admin panel stays locked until a real key is set.
    * Failed attempts are limited per caller IP, read from the trusted proxy (app.security.client_ip), so a
      forged X-Forwarded-For header cannot reset the counter.
    * Every admin request is written to the audit log (action, outcome, hashed IP; never the key).
    """
    from app import security
    from app.sru_agent import memory

    if isinstance(request, str):  # direct call from code / tests
        x_admin_key, request = request, None

    problem = security.admin_key_problem()
    if problem:
        if request is not None:
            security.audit(request, "admin_auth", f"refused_{problem}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin access is disabled until ADMIN_API_KEY is set on the server.",
        )

    if not security.admin_key_matches(x_admin_key):
        bucket = security.ip_bucket(request) if request is not None else "direct"
        allowed = await memory.allow_request(f"admin_fail:{bucket}", limit=5)
        if request is not None:
            security.audit(request, "admin_auth", "invalid_key" if allowed else "locked")
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed admin key attempts. Access temporarily locked.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key",
        )

    if request is not None:
        security.audit(request, "admin_request", "allowed")
    return x_admin_key


def get_session_id(
    x_session_id: str | None = Header(None, alias="X-Session-Id"),
    session_id: str | None = Query(None),
) -> str:
    """Resolve and validate session ID from X-Session-Id header (preferred) or query parameter."""
    import re
    from app.security import SESSION_ID_PATTERN

    raw = (x_session_id or session_id or "").strip()
    if not raw or not (16 <= len(raw) <= 64) or not re.fullmatch(SESSION_ID_PATTERN, raw):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Valid X-Session-Id header or session_id is required.",
        )
    return raw


def get_redis(request: Request) -> Any | None:
    """Return the Redis client from app state, or None if not configured."""
    return getattr(request.app.state, "redis", None)
