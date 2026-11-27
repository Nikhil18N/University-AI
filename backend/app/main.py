"""FastAPI application entry point."""
# Reload configuration trigger for apodex model

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app import security
from app.config import settings
from app.schemas.common import ErrorResponse, HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _without_urls(text: str) -> str:
    """Never write a connection string (it holds the database password) to the logs."""
    import re as _re
    return _re.sub(r"(?:[A-Za-z_]+=)?[a-z][a-z0-9+.-]*://\S+", "<connection URL hidden>", text or "")[:300]


# Row Level Security on every public table that has none yet, and no table access for the Supabase API roles
# (anon / authenticated): the public anon key must not reach app data through Supabase's REST API. The API itself
# connects as the table owner, which RLS does not restrict. Tables that already have RLS are left as they are.
_LOCK_PUBLIC_TABLES_SQL = """DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM anon', t.tablename);
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', t.tablename);
    END IF;
  END LOOP;
END $$;"""


async def _lock_public_tables() -> None:
    try:
        from sqlalchemy import text as _text
        from app.db.session import engine
        async with engine.begin() as conn:
            await conn.execute(_text(_LOCK_PUBLIC_TABLES_SQL))
        logger.info("Row Level Security checked on public tables.")
    except Exception as err:
        logger.warning("Row Level Security not applied: %s: %s", type(err).__name__, _without_urls(str(err)))


async def _apply_migrations_on_start() -> None:
    """`alembic upgrade head` at startup, for hosts without a shell (Render free tier). Never blocks the start: if
    Alembic cannot run (e.g. a database created without Alembic history), the tables the agent writes to that may be
    missing (turn telemetry) are created on their own (create-if-missing; nothing existing is altered or dropped)."""
    import asyncio as _asyncio
    from pathlib import Path as _Path
    try:
        from alembic import command as _alembic_command
        from alembic.config import Config as _AlembicConfig

        ini = _Path(__file__).resolve().parent.parent / "alembic.ini"
        cfg = _AlembicConfig(str(ini))
        cfg.set_main_option("script_location", str(ini.parent / "alembic"))
        cfg.attributes["configure_logger"] = False   # keep the API's own logging configuration
        await _asyncio.wait_for(_asyncio.to_thread(_alembic_command.upgrade, cfg, "head"), timeout=90)
        logger.info("Database migrations applied (alembic upgrade head).")
        await _lock_public_tables()
        return
    except Exception as err:
        if "already exists" in str(err):
            # a database created from the models (not through Alembic) has no Alembic history: every migration
            # would try to create what is already there. The changes the API needs are applied directly below.
            logger.info("Database has no Alembic history (created from the models); applying the required "
                        "changes directly.")
        else:
            logger.warning("alembic upgrade at startup did not run (%s: %s); creating missing agent tables only",
                           type(err).__name__, _without_urls(str(err)))
    try:
        from app.db.session import engine
        from app.models.telemetry import TurnTelemetry

        from sqlalchemy import text as _text
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: TurnTelemetry.__table__.create(c, checkfirst=True))
            # migration i9j0k1l2m345: user_memories.memory_value varchar(255) -> text (only when still varchar)
            await conn.execute(_text(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
                "AND table_name = 'user_memories' AND column_name = 'memory_value' "
                "AND data_type = 'character varying') THEN "
                "ALTER TABLE public.user_memories ALTER COLUMN memory_value TYPE TEXT; END IF; END $$;"))
        logger.info("turn_telemetry table and user_memories.memory_value checked.")
    except Exception as err:
        logger.warning("turn_telemetry table not created: %s: %s", type(err).__name__, _without_urls(str(err)))
    await _lock_public_tables()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting University AI Companion")
    logger.info("LLM Provider: %s (%s)", settings.LLM_PROVIDER, settings.LLM_MODEL)
    if settings.LLM_PROVIDER.lower() == "gemini":
        gemini_keys = settings.get_gemini_api_keys()
        logger.info("Gemini API Key Pool: %d key(s) active with auto-failover", len(gemini_keys))
    logger.info("Embedding Model: %s", settings.EMBEDDING_MODEL)
    if settings.admin_key_is_default():
        logger.error(
            "ADMIN_API_KEY is still the built-in default. The admin panel (leads, phone numbers, "
            "documents) is %s. Set ADMIN_API_KEY to a long random value in the server environment.",
            "locked until you do" if security.is_production() else "usable on this development machine only",
        )
    for warning in security.startup_warnings():
        logger.warning("SECURITY CONFIGURATION: %s", warning)

    # Ensure upload directory exists
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if settings.AUTO_CREATE_SCHEMA:
        # Development-only fallback for a fresh local database. Production schemas
        # must be applied with `alembic upgrade head` before starting the API.
        try:
            from app.db.session import engine
            from app.db.base import Base
            import app.models.conversation
            import app.models.message
            import app.models.feedback
            import app.models.document
            import app.models.lead
            import app.models.memory
            import app.models.agent
            import app.models.calculation
            import app.models.agent_task

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Development database schema created or verified.")
        except Exception as e:
            logger.warning("Development schema initialization skipped or deferred: %s", e)
    elif settings.RUN_MIGRATIONS_ON_START:
        await _apply_migrations_on_start()
    else:
        logger.info("Database schema creation disabled; apply Alembic migrations before startup.")

    # Initialize optional Redis client for response caching & multi-worker locks
    fastapi_app.state.redis = None
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            fastapi_app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("Redis response cache enabled (%s)", _without_urls(settings.REDIS_URL))   # no password
        except Exception as e:
            logger.warning("Redis response cache disabled: %s", e)
    from app.sru_agent import memory as agent_memory
    agent_memory.set_redis_client(fastapi_app.state.redis)

    # Verify or auto-seed ChromaDB documents in background (guarded by Redis lock for multi-worker safety)
    import asyncio
    from app.services.auto_seed import (ensure_documents_seeded, refresh_handbook_if_changed,
                                        retire_obsolete_fee_knowledge)

    async def _prepare_knowledge():
        # The agent's own handbook search reads the files directly: ready at once, no AI calls.
        try:
            from app.sru_agent import knowledge
            logger.info("Handbook keyword index ready: %d passages.", knowledge.reload())
        except Exception as err:
            logger.warning("Handbook keyword index could not be built: %s", err)

        r = getattr(fastapi_app.state, "redis", None)
        if r is not None:
            try:
                acquired = await r.set("sru:startup_seed_lock", "1", nx=True, ex=300)
                if not acquired:
                    logger.info("Another worker holds startup_seed_lock; skipping duplicate vector seeding.")
                    return
            except Exception:
                pass

        await ensure_documents_seeded()        # vector index, only when it is empty
        await retire_obsolete_fee_knowledge()  # never serve a fee from the retired policy
        await refresh_handbook_if_changed()    # vector index, when handbook files were edited

    asyncio.create_task(_prepare_knowledge())

    yield

    # Finish the chat saves and state writes still running in the background (at most 10 seconds).
    try:
        from app.sru_agent import memory as _agent_memory
        await _agent_memory.shutdown_flush(timeout=10.0)
    except Exception:
        pass

    # Cleanup
    if getattr(fastapi_app.state, "redis", None) is not None:
        try:
            await fastapi_app.state.redis.aclose()
        except Exception:
            pass
    agent_memory.set_redis_client(None)

    from app.api.v1.deps import _llm_provider, _embedding_provider

    if _llm_provider and hasattr(_llm_provider, "close"):
        await _llm_provider.close()
    if _embedding_provider and hasattr(_embedding_provider, "close"):
        await _embedding_provider.close()

    logger.info("Shutting down University AI Companion")


# Create the FastAPI app (public docs disabled in production per audit security requirements)
app = FastAPI(
    title="University AI Companion",
    description="Conversational AI with RAG and Function-Calling Agent for university knowledge",
    version="4.18.0",
    lifespan=lifespan,
    docs_url="/docs" if security.docs_enabled() else None,
    redoc_url="/redoc" if security.docs_enabled() else None,
    openapi_url="/openapi.json" if security.docs_enabled() else None,
)

# Request size limit (HTTP 413). Added before CORS so the 413 still carries CORS headers.
app.add_middleware(
    security.BodySizeLimitMiddleware,
    default_limit=settings.MAX_REQUEST_BYTES,
    upload_limit=settings.MAX_UPLOAD_BYTES,
    upload_paths=("/api/v1/admin/documents", "/api/v1/admin/media"),   # media: images for ads / events (v4.15.1)
)

# CORS
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
# The website sends no cookies (students are identified by a random id in the request), so
# credentials are not allowed: another site can never make a request "as" a student.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" not in origins else ["*"],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# GZip compression — reduces JSON payload size by ~60-80% for large RAG answers.
# Must be added AFTER CORSMiddleware so CORS headers are present before compression.
app.add_middleware(GZipMiddleware, minimum_size=500)


def _origin_allowed(origin: str) -> bool:
    import re as _re
    if not origin:
        return False
    if "*" in origins or origin in origins:
        return True
    return bool(settings.CORS_ORIGIN_REGEX and _re.fullmatch(settings.CORS_ORIGIN_REGEX, origin))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Basic protection headers on every API response."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("text/event-stream"):
        response.headers.setdefault("Server-Timing", f"app;dur={elapsed_ms:.1f}")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")  # the API is never shown in a frame
    if security.is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# ---- Global exception handler ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler — never expose stack traces per docs/18-error-handling.md."""
    logger.error("Unhandled error: %s", exc, exc_info=True)
    
    # Ensure CORS headers are attached to error responses
    origin = request.headers.get("origin")
    response_headers = {}
    if _origin_allowed(origin):  # only the sites CORS allows; never echo an arbitrary origin
        response_headers["Access-Control-Allow-Origin"] = origin
        response_headers["Vary"] = "Origin"

    detail_msg = "An unexpected error occurred. Please try again later."
    exc_str = str(exc)
    if "Connect call failed" in exc_str or "ConnectionRefused" in exc_str or "Could not connect to a Chroma server" in exc_str or "WinError 10061" in exc_str:
        detail_msg = "A required service is temporarily unavailable. Please try again in a minute."

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
        "live": "/live",
        "ready": "/ready",
        "api_v1": "/api/v1",
    }


@app.get("/live", tags=["system"])
async def liveness_check():
    """Fast process-only probe for load balancers and restart controllers."""
    return {"status": "alive"}


# ---- Keep-awake ping (v4.12.0) ----
@app.api_route("/ping", methods=["GET", "HEAD"], tags=["system"], include_in_schema=False)
async def ping() -> dict:
    """For the keep-awake pinger: touches nothing (no database, Redis or search index), so pinging every few
    minutes keeps the server awake without waking the database. Real health monitoring stays on /health."""
    return {"status": "ok"}


# ---- Health check ----
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check(request: Request) -> HealthResponse:
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

        r = getattr(request.app.state, "redis", None)
        owns_client = r is None
        r = r or aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        if owns_client:
            await r.aclose()
        services["redis"] = "healthy"
    except Exception:
        services["redis"] = "unhealthy"

    # Check ChromaDB
    try:
        from app.db.chroma import get_chroma_client
        from app.services.rag_service import COLLECTION_NAME

        client = get_chroma_client()
        await asyncio.to_thread(client.heartbeat)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        count = await asyncio.to_thread(collection.count)
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


@app.get("/ready", response_model=HealthResponse, tags=["system"])
async def readiness_check(request: Request) -> HealthResponse:
    """Dependency-aware probe; returns 503 while required services are degraded."""
    result = await health_check(request)
    if result.status != "healthy":
        raise HTTPException(status_code=503, detail=result.model_dump())
    return result


# ---- Register routers ----
from app.api.v1.chat import router as chat_router
from app.api.v1.admin import router as admin_router
from app.api.v1.lead import router as lead_router
from app.api.v1.finance import router as finance_router
from app.api.v1.memory import router as memory_router
from app.sru_agent.router import router as agent_router
from app.services.agent_knowledge_service import (  # noqa: E402, F401
    _EMB_CACHE_TTL,
    _EMB_LOCAL_CACHE,
    _GENERIC_WORDS,
    _SEMANTIC_MAX_DISTANCE,
    _cached_embed_query,
    _merge_evidence,
    _rerank_by_question_words,
    agent_knowledge_search,
    zip_longest_lists,
)
from app.services.agent_bridge import (  # noqa: E402, F401
    _create_conversation_row,
    _creating_conversations,
    _known_conversations,
    _remember_conversation,
    agent_conversation_resolver,
    agent_lead_canceller,
    agent_lead_saver,
    agent_turn_logger,
    wire_agent_callbacks,
)

wire_agent_callbacks()

app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(lead_router)
app.include_router(finance_router)
app.include_router(memory_router)
app.include_router(agent_router)

