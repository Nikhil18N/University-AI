"""FastAPI application entry point."""
# Reload configuration trigger for apodex model

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas.common import ErrorResponse, HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting University AI Companion")
    logger.info("LLM Provider: %s (%s)", settings.LLM_PROVIDER, settings.LLM_MODEL)
    if settings.LLM_PROVIDER.lower() == "gemini":
        gemini_keys = settings.get_gemini_api_keys()
        logger.info("Gemini API Key Pool: %d key(s) active with auto-failover", len(gemini_keys))
    logger.info("Embedding Model: %s", settings.EMBEDDING_MODEL)

    # Ensure upload directory exists
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Auto-initialize database tables if using fresh database (e.g. Supabase)
    try:
        from app.db.session import engine
        from app.db.base import Base
        import app.models.conversation
        import app.models.message
        import app.models.feedback
        import app.models.document
        import app.models.lead

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema verified/created in PostgreSQL.")
    except Exception as e:
        logger.warning("Database schema check skipped or deferred: %s", e)

    # Preload authoritative structured facts from PostgreSQL into memory
    try:
        from app.db.session import async_session_factory
        from app.services.structured_facts_service import refresh_facts_cache_from_db
        async with async_session_factory() as session:
            await refresh_facts_cache_from_db(session)
    except Exception as e:
        logger.warning("Structured facts startup cache preload deferred: %s", e)

    # Verify or auto-seed ChromaDB documents in background
    import asyncio
    from app.services.auto_seed import ensure_documents_seeded

    asyncio.create_task(ensure_documents_seeded())

    # Initialize optional Redis client for response caching
    fastapi_app.state.redis = None
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            fastapi_app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("Redis response cache enabled (%s)", settings.REDIS_URL[:30])
        except Exception as e:
            logger.warning("Redis response cache disabled: %s", e)

    yield

    # Cleanup
    if getattr(fastapi_app.state, "redis", None) is not None:
        try:
            await fastapi_app.state.redis.aclose()
        except Exception:
            pass

    from app.api.v1.deps import _llm_provider, _embedding_provider

    if _llm_provider and hasattr(_llm_provider, "close"):
        await _llm_provider.close()
    if _embedding_provider and hasattr(_embedding_provider, "close"):
        await _embedding_provider.close()

    logger.info("Shutting down University AI Companion")


# Create the FastAPI app
app = FastAPI(
    title="University AI Companion",
    description="Conversational AI with RAG for university knowledge",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Global exception handler ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler — never expose stack traces per docs/18-error-handling.md."""
    logger.error("Unhandled error: %s", exc, exc_info=True)
    
    # Ensure CORS headers are attached to error responses
    origin = request.headers.get("origin")
    response_headers = {}
    if origin:
        response_headers["Access-Control-Allow-Origin"] = origin
        response_headers["Access-Control-Allow-Credentials"] = "true"
        response_headers["Access-Control-Allow-Methods"] = "*"
        response_headers["Access-Control-Allow-Headers"] = "*"

    detail_msg = "An unexpected error occurred. Please try again later."
    exc_str = str(exc)
    if "Connect call failed" in exc_str or "ConnectionRefused" in exc_str or "Could not connect to a Chroma server" in exc_str or "WinError 10061" in exc_str:
        detail_msg = "Required backend service (PostgreSQL, ChromaDB, or Redis) is not reachable. Please ensure Docker Desktop is open and run 'docker compose up -d'."

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Service error",
            detail=detail_msg,
        ).model_dump(),
        headers=response_headers,
    )


# ---- Root status ----
@app.get("/", tags=["system"])
@app.head("/", tags=["system"])
async def root():
    """Root health check for Render / load balancer pings."""
    return {
        "status": "healthy",
        "service": "University AI Companion API",
        "docs": "/docs",
        "health": "/health",
        "api_v1": "/api/v1",
    }


# ---- Health check ----
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    services = {}

    # Check database
    try:
        from app.db.session import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception:
        services["database"] = "unhealthy"

    # Check Redis
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unhealthy"

    # Check ChromaDB
    try:
        from app.db.chroma import get_chroma_client
        from app.services.rag_service import COLLECTION_NAME

        client = get_chroma_client()
        client.heartbeat()
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        count = collection.count()
        services["chromadb"] = f"healthy ({count} docs)"
    except Exception as e:
        services["chromadb"] = f"unhealthy ({e})"

    # Check LLM / Embedding Provider
    if settings.LLM_PROVIDER.lower() == "ollama" or settings.EMBEDDING_PROVIDER.lower() == "ollama":
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.LLM_BASE_URL}/api/tags")
                services["ollama"] = "healthy" if resp.status_code == 200 else "unhealthy"
        except Exception:
            services["ollama"] = "unhealthy"
    else:
        # Provider is Gemini or OpenRouter
        has_gemini = bool(settings.get_gemini_api_keys())
        has_openrouter = bool(settings.OPENROUTER_API_KEY)
        is_healthy = has_gemini if settings.LLM_PROVIDER.lower() == "gemini" else has_openrouter
        services[settings.LLM_PROVIDER.lower()] = "healthy" if is_healthy else "unconfigured (missing API key)"

    overall = "healthy" if all(v.startswith("healthy") for v in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)


# ---- Register routers ----
from app.api.v1.chat import router as chat_router
from app.api.v1.admin import router as admin_router
from app.api.v1.lead import router as lead_router

app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(lead_router)

