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
    else:
        logger.info("Database schema creation disabled; apply Alembic migrations before startup.")

    # Verify or auto-seed ChromaDB documents in background
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
        await ensure_documents_seeded()        # vector index, only when it is empty
        await retire_obsolete_fee_knowledge()  # never serve a fee from the retired policy
        await refresh_handbook_if_changed()    # vector index, when handbook files were edited

    asyncio.create_task(_prepare_knowledge())

    # Initialize optional Redis client for response caching
    fastapi_app.state.redis = None
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            fastapi_app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            logger.info("Redis response cache enabled (%s)", settings.REDIS_URL[:30])
        except Exception as e:
            logger.warning("Redis response cache disabled: %s", e)
    from app.sru_agent import memory as agent_memory
    agent_memory.set_redis_client(fastapi_app.state.redis)

    yield

    # Finish the chat saves still running in the background (at most 10 seconds).
    try:
        from app.sru_agent import memory as _agent_memory
        await asyncio.wait_for(_agent_memory.flush(), timeout=10)
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
    version="4.17.0",
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
from app.sru_agent import tools as agent_tools

# Connect agent knowledge retrieval to ChromaDB
async def agent_knowledge_search(query: str):
    """Approved-knowledge search for the agent (v4.17.1): the handbook keyword search AND the vector index,
    merged.

    Before, a keyword hit stopped the search, so a weak match on a handbook page ("Director" -> sports
    facilities) hid the right passage in the vector index (the university FAQ, documents uploaded in the admin
    console). Now both run: strong semantic matches come first, then the two lists alternate; near-identical
    passages are kept once; every passage keeps its source. The keyword search alone still answers when the
    embedding service is unavailable (cold start, quota)."""
    lexical, semantic = [], []
    try:
        from app.sru_agent import knowledge
        lexical = [{"title": f["title"], "text": f["text"][:1800], "source": f["source"], "retrieval": "keyword"}
                   for f in knowledge.search(query, k=4, min_score=3.0)]
    except Exception as err:
        logger.warning("keyword handbook search failed: %s", err)
    try:
        from app.db.chroma import get_chroma_client
        from app.services.rag_service import COLLECTION_NAME
        collection = get_chroma_client().get_or_create_collection(name=COLLECTION_NAME,
                                                                  metadata={"hnsw:space": "cosine"})
        from app.api.v1.deps import get_embedding_provider
        emb = await get_embedding_provider().embed_single(query)
        results = await asyncio.to_thread(collection.query, query_embeddings=[emb], n_results=12)
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0] or [None] * len(docs)
        keep = ("document_type", "page", "effective_date", "publication_date", "document_id", "section", "question",
                "page_url")
        for d, m, dist in zip(docs, metas, dists):
            if dist is not None and dist > _SEMANTIC_MAX_DISTANCE:
                continue                     # not about this question
            m = m or {}
            semantic.append({"title": m.get("title", ""), "text": d, "retrieval": "semantic",
                             "distance": round(dist, 3) if dist is not None else None,
                             **{k: m.get(k) for k in keep if m.get(k)}})
        semantic = _rerank_by_question_words(query, semantic)
    except Exception as err:
        logger.warning("vector knowledge search unavailable, keyword results only: %s", err)
    return _merge_evidence(semantic, lexical)


_GENERIC_WORDS = set("what which when where whom whose about does have there their with from that this then than "
                     "into your mine sru university universities college please tell know give show more some "
                     "much many like would could should will shall also only just very really".split())


def _rerank_by_question_words(query: str, hits: list) -> list:
    """Similar FAQ entries ("Who is the X of SR University?") sit close together in the vector space; the
    distinctive words of the student's own question decide between them. Each distinct question word found in
    a passage lowers its rank distance a little (stems of 5 letters, so "admission" matches "Admissions")."""
    import re as _re
    words = {w[:5] for w in _re.findall(r"[a-z]+", (query or "").lower()) if len(w) > 3 and w not in _GENERIC_WORDS}
    if not words:
        return hits
    def adjusted(h):
        text = f"{h.get('title', '')} {h.get('question', '')} {h.get('text', '')}".lower()
        found = {t[:5] for t in _re.findall(r"[a-z]+", text) if len(t) > 3}
        return (h.get("distance") or 0.5) - 0.03 * len(words & found)
    for h in hits:
        h["rank"] = round(adjusted(h), 3)
    return sorted(hits, key=lambda h: h["rank"])


# Cosine distance above which a vector match is not about the question (measured on the index: right answers
# 0.19-0.34, unrelated passages 0.45+).
_SEMANTIC_MAX_DISTANCE = 0.42


def _merge_evidence(semantic: list, lexical: list, limit: int = 6) -> list:
    """Strong semantic matches (distance < 0.33) first, then semantic and keyword results alternate; the same
    passage found by both is kept once."""
    import re as _re
    strong = [h for h in semantic if (h.get("rank", h.get("distance")) or 1) < 0.33]
    rest_sem = [h for h in semantic if h not in strong]
    ordered = strong[:]
    for pair in zip_longest_lists(lexical, rest_sem):
        ordered.extend(pair)
    seen, out = set(), []
    for h in ordered:
        key = _re.sub(r"\W+", " ", (h.get("text") or "").lower())[:160]
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def zip_longest_lists(a: list, b: list):
    for i in range(max(len(a), len(b))):
        yield [x for x in ((a[i] if i < len(a) else None), (b[i] if i < len(b) else None)) if x is not None]

# Connect agent lead saving directly to PostgreSQL
async def agent_lead_saver(lead_data: dict):
    from app.db.session import async_session_factory
    from app.schemas.lead import LeadCreate
    from app.services import lead_service
    lead_obj = LeadCreate(**lead_data)
    # A brand-new chat's conversation row is written in the background; a request made in its very first
    # message ("talk to a counsellor") must wait for it, or the lead's link to the conversation fails (v4.12.0).
    conv_id = lead_data.get("conversation_id")
    creating = _creating_conversations.get(str(conv_id)) if conv_id else None
    if creating is not None:
        try:
            await creating
        except Exception:
            pass
    async with async_session_factory() as session:
        created = await lead_service.create_lead(session, lead_obj)
        return {"id": str(created.id), "status": created.status}

# "Don't call me": mark the lead do-not-contact so the admissions team does not phone the student
async def agent_lead_canceller(lead_id: str, reason: str = "") -> bool:
    import uuid
    from app.db.session import async_session_factory
    from app.services import lead_service
    async with async_session_factory() as session:
        lead = await lead_service.cancel_lead(session, uuid.UUID(str(lead_id)), reason)
        return lead is not None

_known_conversations: dict = {}   # (session_id, conversation_id) -> True, for this server process
_creating_conversations: dict = {}  # conversation_id -> task creating its database row


def _remember_conversation(session_id: str, conversation_id: str):
    if len(_known_conversations) > 20000:
        _known_conversations.clear()
    _known_conversations[(session_id, conversation_id)] = True


async def _create_conversation_row(session_id: str, conv_uuid, title: str):
    from app.db.session import async_session_factory
    from app.models.conversation import Conversation
    async with async_session_factory() as session:
        session.add(Conversation(id=conv_uuid, session_id=session_id, title=title))
        await session.commit()


async def agent_conversation_resolver(session_id: str, conversation_id: str | None, message: str) -> str:
    """Resolve or create a persistent conversation before streaming starts.

    Fast paths (no database trip before the answer starts):
    - a new chat gets its id at once; its row is written in the background, and the turn logger
      waits for that write before saving the messages;
    - a chat this server already resolved for this student is not checked again.
    """
    try:
        import uuid
        from app.sru_agent import config as agent_config, memory as agent_memory

        clean_title = (message or "").strip()
        if len(clean_title) > 50:
            clean_title = clean_title[:47].rstrip() + "..."
        if not clean_title:
            clean_title = "Chat"

        conv_uuid = None
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except (ValueError, TypeError):
                conv_uuid = None
        if conv_uuid and (session_id, str(conv_uuid)) in _known_conversations:
            return str(conv_uuid)

        if conv_uuid is None and agent_config.AGENT_LOCAL_CACHE and agent_config.AGENT_BACKGROUND_WRITES:
            new_id = uuid.uuid4()
            task = agent_memory.in_background(
                _create_conversation_row(session_id, new_id, clean_title), "conversation create")
            if task is not None:
                _creating_conversations[str(new_id)] = task
                task.add_done_callback(lambda _t, k=str(new_id): _creating_conversations.pop(k, None))
                _remember_conversation(session_id, str(new_id))
                agent_memory.seed_new_conversation(session_id, str(new_id))
                return str(new_id)

        from app.db.session import async_session_factory
        from app.services import conversation_service
        async with async_session_factory() as session:
            conv = await conversation_service.get_or_create_conversation(
                session, session_id, conv_uuid, title=clean_title
            )
            await session.commit()
            if conv_uuid is None or conv.id != conv_uuid:
                agent_memory.seed_new_conversation(session_id, str(conv.id))
            _remember_conversation(session_id, str(conv.id))
            return str(conv.id)
    except Exception as err:
        logger.warning("agent_conversation_resolver error: %s", err)
        return conversation_id or ""

async def agent_turn_logger(session_id: str, conversation_id: str | None, user_text: str, answer: str,
                            tools_used: list, cards: list | None = None, suggestions: list | None = None,
                            started_at=None, channel: str | None = None, sources: list | None = None,
                            message_id: str | None = None, user_message_id: str | None = None,
                            user_metadata: dict | None = None):
    """Save one agent turn so a reopened chat looks exactly as it did live: the question first
    (stamped when it was asked), then the answer with its cards and follow-up suggestions."""
    try:
        import uuid
        from datetime import datetime, timedelta, timezone
        from app.db.session import async_session_factory
        from app.services import conversation_service
        from app.sru_agent import config as agent_config
        creating = _creating_conversations.get(str(conversation_id)) if conversation_id else None
        if creating is not None:
            try:
                await creating  # the row of a brand-new chat is still being written
            except Exception:
                pass
        async with async_session_factory() as session:
            conv_uuid = uuid.UUID(conversation_id) if conversation_id else None
            clean_title = (user_text or "").strip()
            if len(clean_title) > 50:
                clean_title = clean_title[:47].rstrip() + "..."
            conv = await conversation_service.get_or_create_conversation(
                session, session_id, conv_uuid, title=clean_title
            )
            # Title the chat by its first real question, not by "hi" or "thanks".
            from app.sru_agent import intents as agent_intents
            if clean_title and not agent_intents.small_talk(user_text) and (
                    conv.title in ("New conversation", "Chat", "") or agent_intents.small_talk(conv.title)):
                conv.title = clean_title
            finished_at = datetime.now(timezone.utc)
            asked_at = started_at or finished_at
            if asked_at >= finished_at:
                asked_at = finished_at - timedelta(milliseconds=1)
            # the ids the student's browser already has (Reply / Edit refer to them), the reply / edit markers
            await conversation_service.add_message(
                session, conv.id, "user", user_text, created_at=asked_at,
                metadata={k: v for k, v in (user_metadata or {}).items() if v} or None,
                message_id=uuid.UUID(user_message_id) if user_message_id else None)
            await conversation_service.add_message(
                session,
                conv.id,
                "assistant",
                answer,
                model=agent_config.AGENT_MODEL,
                metadata={"tools_used": tools_used, "cards": cards or [], "suggestions": suggestions or [],
                          **({"channel": channel} if channel else {})},
                # the sources that supported the answer, so a reopened chat shows them too (v4.17.1)
                sources=[s for s in (sources or []) if isinstance(s, dict) and s.get("document_id") and s.get("title")],
                created_at=finished_at,
                message_id=uuid.UUID(message_id) if message_id else None,
            )
            await session.commit()
    except Exception as err:
        logger.warning("agent_turn_logger error: %s", err)

from app.sru_agent.router import set_turn_logger, set_conversation_resolver
set_turn_logger(agent_turn_logger)
set_conversation_resolver(agent_conversation_resolver)
agent_tools.set_knowledge_search(agent_knowledge_search)
agent_tools.set_lead_saver(agent_lead_saver)
agent_tools.set_lead_canceller(agent_lead_canceller)

# Keep student profiles and chat context in PostgreSQL as well, so they survive restarts and the
# 24-hour cache, and so Settings > My details always shows what the chat knows.
from app.services import agent_profile_store
from app.sru_agent import memory as agent_memory
agent_memory.set_profile_store(agent_profile_store.load_profile, agent_profile_store.save_profile)
agent_memory.set_history_loader(agent_profile_store.load_history)
agent_memory.set_state_store(agent_profile_store.load_conversation_state, agent_profile_store.save_conversation_state)
agent_tools.set_lead_updater(agent_profile_store.update_lead_contact)

app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(lead_router)
app.include_router(finance_router)
app.include_router(memory_router)
app.include_router(agent_router)

