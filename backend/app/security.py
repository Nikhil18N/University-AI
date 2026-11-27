"""Security helpers shared by the API routes (see security/SECURITY_IMPLEMENTATION.md).

One place for:
  * deciding whether the server runs as production (the placeholder admin key and /docs are then refused);
  * the caller's IP address, read only from headers a trusted proxy sets (never the spoofable first
    X-Forwarded-For entry);
  * the admin-key check used by every admin route and by the chat's admin view;
  * limits on AI-backed requests (per student, per IP per minute and per day, and one daily budget for the
    whole server) so rotating session IDs cannot run up the model bill;
  * the session-ID format: the session ID is the only key to a student's name and mobile number.

Route handlers call these functions; they hold no security logic of their own.
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import secrets

from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger("security")
audit_logger = logging.getLogger("security.audit")

# A browser makes a UUID (36 characters). Short or odd IDs are refused so nobody can use (or guess) one.
SESSION_ID_PATTERN = r"^[A-Za-z0-9_-]{16,64}$"
_SESSION_ID_RE = re.compile(SESSION_ID_PATTERN)

PLACEHOLDER_ADMIN_KEY = "change-me-in-production"
MIN_ADMIN_KEY_LENGTH = 24


# ------------------------------------------------------------------ environment ----

def is_production() -> bool:
    """True when the server must run locked down.

    Production when APP_ENV says so, when the server runs on Render (Render sets RENDER=true on every
    service), or when debugging is switched off. So a deployment that forgets APP_DEBUG=false is still
    treated as production.
    """
    env = (settings.APP_ENV or "").strip().lower()
    return env in ("production", "prod") or bool(os.environ.get("RENDER")) or not settings.APP_DEBUG


def docs_enabled() -> bool:
    """/docs and /openapi.json only on a developer machine."""
    return settings.APP_DEBUG and not is_production()


# ------------------------------------------------------------------ admin key ----

def admin_key_problem() -> str | None:
    """Why the configured admin key may not be used, or None when it is fine."""
    key = settings.ADMIN_API_KEY or ""
    if not key.strip():
        return "missing"
    if key == PLACEHOLDER_ADMIN_KEY and is_production():
        return "placeholder"
    return None


def admin_key_is_weak() -> bool:
    key = settings.ADMIN_API_KEY or ""
    return key == PLACEHOLDER_ADMIN_KEY or len(key) < MIN_ADMIN_KEY_LENGTH


def admin_key_matches(provided: str | None) -> bool:
    """Constant-time comparison with the configured key. False when admin access is not configured."""
    if not provided or admin_key_problem():
        return False
    return secrets.compare_digest(provided.encode(), (settings.ADMIN_API_KEY or "").encode())


def startup_warnings() -> list[str]:
    """Configuration problems to log once at start-up (never the values themselves)."""
    warnings = []
    if is_production():
        problem = admin_key_problem()
        if problem:
            warnings.append(f"ADMIN_API_KEY is {problem}: the admin dashboard is locked until a strong key is set.")
        elif admin_key_is_weak():
            warnings.append(f"ADMIN_API_KEY is shorter than {MIN_ADMIN_KEY_LENGTH} characters: replace it with a "
                            f"long random value (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(32))\"`).")
        if settings.APP_DEBUG:
            warnings.append("APP_DEBUG is true on a production server: set APP_DEBUG=false.")
        if ".*\\.vercel\\.app" in (settings.CORS_ORIGIN_REGEX or ""):
            warnings.append("CORS_ORIGIN_REGEX allows every *.vercel.app site: narrow it to this project's domains.")
        if not settings.REDIS_URL:
            warnings.append("REDIS_URL is not set on a production server: rate limits and background job tracking are per-process only.")
    return warnings


# ------------------------------------------------------------------ client IP ----

def _valid_ip(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """The caller's IP address as seen by the trusted proxy in front of this server.

    * CLIENT_IP_HEADER (e.g. "cf-connecting-ip"): when the platform sets a dedicated header, use it.
    * Otherwise X-Forwarded-For, counted from the RIGHT: each trusted proxy appends the address it saw,
      so the entry TRUSTED_PROXY_HOPS from the end is the one the caller cannot forge. The first entry is
      whatever the caller sent and is never used.
    * With TRUSTED_PROXY_HOPS=0 (no proxy) the socket address is used.
    """
    header = (settings.CLIENT_IP_HEADER or "").strip().lower()
    if header:
        ip = _valid_ip(request.headers.get(header, ""))
        if ip:
            return ip
    hops = max(0, int(settings.TRUSTED_PROXY_HOPS or 0))
    if hops:
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
        if len(entries) >= hops:
            ip = _valid_ip(entries[-hops])
            if ip:
                return ip
    host = request.client.host if request.client else ""
    return _valid_ip(host) or (host or "unknown")[:64]


def ip_bucket(request: Request) -> str:
    """A short, non-reversible key for rate-limit counters (no raw IP addresses in Redis keys)."""
    return hashlib.sha256(client_ip(request).encode()).hexdigest()[:16]


# ------------------------------------------------------------------ audit ----

def audit(request: Request, action: str, outcome: str, **details) -> None:
    """One line per security-relevant event, for the platform's log store (no secrets, no PII)."""
    safe = " ".join(f"{k}={str(v)[:80]}" for k, v in details.items() if v is not None)
    audit_logger.info("audit action=%s outcome=%s method=%s path=%s ip_hash=%s %s", action, outcome,
                      request.method, request.url.path, ip_bucket(request), safe)


# ------------------------------------------------------------------ session IDs ----

def valid_session_id(session_id: str | None) -> bool:
    return bool(session_id and _SESSION_ID_RE.fullmatch(session_id))


def require_session_id(session_id: str | None) -> str:
    if not valid_session_id(session_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Invalid session. Please reload the page.")
    return session_id  # type: ignore[return-value]


# ------------------------------------------------------------------ AI usage limits ----

BUSY_MESSAGE = ("Too many messages right now. Please wait a minute and try again, or call the Admissions Office "
                "on 833 100 3030.")
DAILY_MESSAGE = ("SRU Buddy has reached today's message limit for this network. Please try again tomorrow, or call "
                 "the Admissions Office on 833 100 3030.")


async def ai_turn_refusal(request: Request, session_id: str, scope: str = "agent") -> str | None:
    """None when this AI-backed turn may run; otherwise the message to show the student.

    Order: per student per minute (the existing limit), per IP per minute, per IP per day, and the server's
    daily turn budget. Every counter lives in Redis when configured (shared by all server processes) and
    falls back to process memory.
    """
    from app.sru_agent import memory

    if not await memory.allow_request(f"{scope}:{session_id}" if scope != "agent" else session_id):
        return BUSY_MESSAGE
    bucket = ip_bucket(request)
    per_min = int(getattr(settings, "AI_IP_RATE_LIMIT_PER_MIN", 0) or 0)
    if per_min and not await memory.allow_in_window(f"ip:{bucket}", per_min, 60):
        audit(request, "ai_turn", "rate_limited_ip_minute")
        return BUSY_MESSAGE
    per_day = int(getattr(settings, "AI_IP_DAILY_LIMIT", 0) or 0)
    if per_day and not await memory.allow_in_window(f"ipday:{bucket}", per_day, 86400):
        audit(request, "ai_turn", "rate_limited_ip_day")
        return DAILY_MESSAGE
    budget = int(getattr(settings, "AI_DAILY_TURN_BUDGET", 0) or 0)
    if budget and not await memory.allow_in_window("global", budget, 86400):
        audit(request, "ai_turn", "daily_budget_reached")
        return DAILY_MESSAGE
    return None


# ------------------------------------------------------------------ request size ----

class BodySizeLimitMiddleware:
    """Refuse request bodies larger than the limit (HTTP 413) before they are read into memory.

    Checks the Content-Length header first, then counts the bytes actually received, so a chunked body
    without a Content-Length cannot get past it. Admin document uploads have their own, larger limit.
    """

    def __init__(self, app, default_limit: int, upload_limit: int, upload_paths: tuple[str, ...] = ()):
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_paths = upload_paths

    def _limit_for(self, path: str) -> int:
        return self.upload_limit if any(path.startswith(p) for p in self.upload_paths) else self.default_limit

    async def _too_large(self, send) -> None:
        body = b'{"error":"Request too large","detail":"The request is larger than this server accepts."}'
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        limit = self._limit_for(scope.get("path", ""))
        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                try:
                    if int(value) > limit:
                        return await self._too_large(send)
                except ValueError:
                    return await self._too_large(send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail="The request is larger than this server accepts.")
            return message

        return await self.app(scope, limited_receive, send)
