"""API endpoints for the agent. Add to your FastAPI app with:

    from sru_agent.router import router as agent_router
    app.include_router(agent_router)
"""
import json
import uuid
import logging
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.schemas.chat import ConversationRecoveryContext, ResetSessionRequest, ResetSessionResponse
from . import config, fees, memory
from .agent import run_agent
from app import security
from app.security import SESSION_ID_PATTERN

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
log = logging.getLogger("sru_agent")
_on_turn_complete = None
_conversation_resolver = None


def set_turn_logger(fn):
    """Optional. fn: async (session_id, conversation_id, user_text, answer, tools_used) -> None
    Use it to save agent chats in your existing conversations table."""
    global _on_turn_complete
    _on_turn_complete = fn


async def _log_turn(session_id, conv_id, message, event, started_at, channel=None):
    """Call the turn logger with the cards and suggestions too; older 5-argument loggers still work."""
    try:
        extra = {"channel": channel} if channel else {}
        for k in ("message_id", "user_message_id", "user_metadata"):
            if event.get(k):
                extra[k] = event[k]
        if event.get("telemetry"):
            extra["telemetry"] = event["telemetry"]
        await _on_turn_complete(session_id, conv_id, message, event["answer"], event["tools_used"],
                                cards=event.get("cards") or [], suggestions=event.get("suggestions") or [],
                                started_at=started_at, sources=event.get("sources") or [], **extra)
    except TypeError:
        await _on_turn_complete(session_id, conv_id, message, event["answer"], event["tools_used"])


_turn_queues: dict = {}  # conversation -> turns still to be saved, in order


def _save_turn_later(session_id, conv_id, message, event, started_at, channel=None):
    key = conv_id or session_id
    queue = _turn_queues.setdefault(key, [])
    queue.append((session_id, conv_id, message, dict(event), started_at, channel))
    if len(queue) > 1:
        return  # the task already saving this conversation will take this turn too

    async def _drain():
        try:
            while queue:
                args = queue[0]
                try:
                    await _log_turn(*args)
                except Exception:
                    log.exception("could not save the chat turn")  # logging must never break the chat
                queue.pop(0)
        finally:
            if not queue:
                _turn_queues.pop(key, None)

    if memory.in_background(_drain(), "chat save") is None:
        _turn_queues.pop(key, None)


def set_conversation_resolver(fn):
    """Optional. fn: async (session_id, conversation_id, message) -> str
    Use it to resolve or create a persistent conversation before the agent stream begins."""
    global _conversation_resolver
    _conversation_resolver = fn


class AcademicForm(BaseModel):
    """The academic details form (card type 'academic_details_form'), submitted as structured data.
    Values are validated again by the agent against the options the form offers."""
    mode: Literal["eligibility", "scholarship"] = "eligibility"
    program: Optional[str] = Field(default=None, max_length=40)
    board_key: Optional[Literal["ts_state_board", "ap_state_board", "cbse", "icse", "other_state_board", "ib"]] = None
    academic_stage: Optional[Literal["1st_year", "2nd_year", "completed"]] = None
    raw_marks: Optional[float] = Field(default=None, ge=0, le=2000)
    max_marks: Optional[float] = Field(default=None, gt=0, le=2000)
    stream: Optional[Literal["MPC", "BiPC", "MEC"]] = None
    show_stream: bool = False
    show_entrance: bool = False
    entrance_type: Optional[Literal["none", "tg_eapcet", "ap_eapcet", "jee_main"]] = None
    entrance_value: Optional[float] = Field(default=None, ge=0, le=1000000)


class AgentRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)
    message: str = Field(min_length=1, max_length=config.AGENT_MAX_MESSAGE_CHARS)
    conversation_id: Optional[str] = None
    # "web" (the website) or "widget" (the embeddable chat bubble); stored with the chat for staff.
    channel: Optional[str] = Field(default=None, max_length=12, pattern=r"^[a-z]+$")
    # Present only when the student submits the academic details form.
    form: Optional[AcademicForm] = None
    # "typed": the student typed the message (the model understands it). "button": the text of a chip, card
    # option or tile the bot offered (its fixed flow runs). Default "typed".
    source: Literal["typed", "button"] = "typed"
    # v4.17.1: reply to an earlier message of this conversation (its id), or edit the student's latest typed
    # message (its id; the message text is the corrected text).
    reply_to: Optional[str] = Field(default=None, pattern=r"^[0-9a-fA-F-]{36}$")
    edit_of: Optional[str] = Field(default=None, pattern=r"^[0-9a-fA-F-]{36}$")


class FeeRequest(BaseModel):
    program: str
    percent: Optional[float] = Field(default=None, ge=0, le=100)
    board: str = "state_board"
    eapcet_rank: Optional[int] = Field(default=None, ge=1)
    jee_percentile: Optional[float] = Field(default=None, ge=0, le=100)
    hostel: str = "none"
    specialization: bool = False
    ib_score: Optional[int] = Field(default=None, ge=0, le=45)
    transport: bool = False
    # Special-category concession keys from the fee policy (e.g. "sibling"); applied as annual deductions.
    concessions: list[str] = Field(default_factory=list, max_length=5)


def _sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@router.post("/stream")
async def agent_stream(req: AgentRequest, request: Request = None):
    async def events():
        # Per student, per IP (minute and day) and the server's daily budget: rotating session IDs
        # cannot buy unlimited AI calls (app/security.py). Called without an HTTP request (tests,
        # internal use) only the per-student limit applies.
        if request is not None:
            refusal = await security.ai_turn_refusal(request, req.session_id)
        else:
            refusal = None if await memory.allow_request(req.session_id) else security.BUSY_MESSAGE
        if refusal:
            yield _sse({"type": "error", "detail": refusal})
            return

        conv_id = req.conversation_id
        if _conversation_resolver:
            try:
                resolved = await _conversation_resolver(req.session_id, req.conversation_id, req.message)
                if resolved:
                    conv_id = str(resolved)
            except Exception:
                pass  # Fall back to req.conversation_id

        # v4.17.1: message ids known before the turn (Reply / Edit refer to them); reply and edit checked here
        from app.services import message_actions
        user_message_id, message_id = str(uuid.uuid4()), str(uuid.uuid4())
        user_metadata: dict = {"source": req.source}
        reply_ctx = None
        try:
            if req.edit_of:
                if not conv_id:
                    raise message_actions.MessageActionError("Only your latest message can be edited.")
                snap = await message_actions.prepare_edit(req.session_id, conv_id, req.edit_of,
                                                          await memory.get_turn_snapshot(req.session_id, conv_id))
                await memory.restore_turn_snapshot(req.session_id, conv_id, snap)
                user_metadata.update(edited=True, edited_from=req.edit_of)
            if req.reply_to:
                if not conv_id:
                    raise message_actions.MessageActionError("That message is not in this conversation.")
                reply_ctx = await message_actions.reply_context(req.session_id, conv_id, req.reply_to)
                user_metadata["reply_to"] = req.reply_to
        except message_actions.MessageActionError as err:
            yield _sse({"type": "error", "detail": str(err), "code": "message_action"})
            return

        started_at = datetime.now(timezone.utc)
        started_perf = time.perf_counter()
        first_token_perf = None
        async for event in run_agent(
            req.message,
            req.session_id,
            conv_id,
            require_contact_details=True,
            form=req.form.model_dump() if req.form else None,
            source=req.source,
            reply_context=reply_ctx,
            turn_id=user_message_id,
        ):
            if event["type"] == "token" and first_token_perf is None:
                first_token_perf = time.perf_counter()
            if event["type"] == "done":
                first_token_ms = (
                    round((first_token_perf - started_perf) * 1000, 1)
                    if first_token_perf is not None
                    else None
                )
                total_ms = round((time.perf_counter() - started_perf) * 1000, 1)
                event["timings"] = {
                    "first_token_ms": first_token_ms,
                    "total_ms": total_ms,
                }
                if isinstance(event.get("telemetry"), dict) and event["telemetry"].get("first_token_ms") is None and first_token_ms is not None:
                    event["telemetry"]["first_token_ms"] = first_token_ms
                log.info(
                    "AGENT_SSE_TIMING: session=%s conv=%s first_token_ms=%s total_ms=%.1f",
                    (req.session_id or "")[:8],
                    str(conv_id or "")[:8],
                    first_token_ms,
                    total_ms,
                )
                # What the chat now knows about the student, so Settings > My details stays in step.
                try:
                    event["profile"] = memory.public_profile(await memory.get_profile(req.session_id))
                except Exception:
                    event["profile"] = {}
            if event["type"] == "done":
                event.update(message_id=message_id, user_message_id=user_message_id, user_metadata=user_metadata)
                # a turn that completed an external action (callback / visit request) cannot be edited later
                try:
                    profile_now = await memory.get_profile(req.session_id)
                    snap = await memory.get_turn_snapshot(req.session_id, conv_id) or {}
                    acted = any(t.get("is_action") and t.get("status") in ("saved", "ok", "cancelled")
                                for t in event.get("tools_used") or [])
                    if acted or (profile_now.get("last_lead_id") or None) != (snap.get("lead_id") or None):
                        await memory.mark_turn_snapshot(req.session_id, conv_id, action_done=True)
                        user_metadata["action_done"] = True   # saved with the message: no Edit after a refresh
                except Exception:
                    log.exception("turn snapshot not updated")
            if event["type"] == "done" and _on_turn_complete:
                # Saved after the student has the answer (it used to hold the cards back by about
                # 1.5 seconds). In order per conversation, and a reopened chat still shows it.
                _save_turn_later(req.session_id, conv_id, req.message, event, started_at,
                                 req.channel if req.channel in ("web", "widget") else None)
            yield _sse(event)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/calculate")
async def calculate(req: FeeRequest):
    """Same calculation the agent uses. Point the Fee & Scholarship Calculator here
    so the chat and the calculator can never disagree."""
    return fees.calculate_fee(**req.model_dump())


@router.get("/programs")
async def programs():
    return fees.list_programs()


class ProfileUpdate(BaseModel):
    session_id: str = Field(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)
    name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=20)
    program_interest: Optional[str] = Field(default=None, max_length=120)
    # True when the browser copies its saved contact details into a session started with "Start afresh":
    # the details are kept for the contact form and callbacks, but the new conversation does not use the name.
    fresh_start: Optional[bool] = None


@router.get("/profile")
async def get_profile(session_id: str = Query(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)):
    """What the agent knows about this student (name, mobile number, course, marks).
    Settings > My details shows exactly this, so the chat and the settings cannot disagree."""
    return {"status": "ok", "profile": memory.public_profile(await memory.get_profile(session_id))}


@router.put("/profile")
async def update_profile(body: ProfileUpdate):
    """Save details edited in Settings > My details. The mobile number is also corrected on any
    callback / visit request already saved from this browser."""
    from . import tools

    ctx = {"session_id": body.session_id, "profile": await memory.get_profile(body.session_id)}
    if body.name or body.phone:
        result = await tools.run_tool("update_contact_details",
                                      {"name": body.name, "phone": body.phone}, ctx)
        if result.get("status") == "invalid":
            raise HTTPException(status_code=422, detail="Please enter a valid 10-digit mobile number.")
        if result.get("status") == "failed":
            raise HTTPException(status_code=503, detail="Could not save right now. Please try again.")
    if body.program_interest:
        await memory.update_profile(body.session_id, program_interest=body.program_interest.strip())
    if body.fresh_start is not None:
        # v4.15.0: "Start fresh" resets the conversation, not the student's identity: the name stays usable (a
        # shared computer uses "Not {name}?", which forgets the details instead).
        await memory.update_profile(body.session_id, address_by_name=True)
    return {"status": "ok", "profile": memory.public_profile(await memory.get_profile(body.session_id))}


@router.delete("/profile")
async def forget_profile(session_id: str = Query(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)):
    """Settings > Forget my details: the agent forgets this student. Saved callback / visit
    requests stay with the Admissions Office; say 'cancel my callback' in the chat to withdraw one."""
    await memory.clear_profile(session_id)
    return {"status": "ok", "profile": {}}


@router.get("/welcome-actions")
async def welcome_actions():
    """The Quick Start tiles under the opening welcome message, as set in Admin -> Agent (v4.13.0). Public: the
    widget shows them before the student types anything. Only enabled tiles, in order."""
    from app.services import app_settings
    await app_settings.refresh()
    tiles = [t for t in app_settings.get("welcome_tiles") or [] if t.get("enabled", True)]
    return {"heading": "Quick start", "items": [{k: t.get(k, "") for k in ("id", "title", "badge", "icon", "prompt",
                                                                         "subtitle")} for t in tiles]}


@router.get("/chat-ads")
async def chat_ads():
    """The small ads at the bottom of the chat, as set in Admin -> Campus media -> Ads (v4.14.0). Public: the
    widget shows them. Only ads switched on, in order."""
    from app.services import app_settings
    await app_settings.refresh()
    ads = [a for a in app_settings.get("chat_ads") or [] if a.get("enabled") and a.get("link_url")]
    keys = ("id", "title", "subtitle", "tag", "image_url", "cta_text", "link_url")
    return {"rotate_seconds": app_settings.get("ads_rotate_seconds"), "items": [{k: a.get(k, "") for k in keys}
                                                                                for a in ads]}


@router.get("/media/{media_id}")
async def media(media_id: str = Path(..., pattern=r"^[a-f0-9]{20}$")):
    """An image uploaded in the admin panel for an ad or event card (v4.15.1). Public; never changes (the id is
    its hash), so browsers may keep it for a year."""
    from fastapi import Response
    from app.services import media_store

    found = await media_store.load(media_id)
    if not found:
        raise HTTPException(status_code=404, detail="Image not found.")
    data, ctype = found
    return Response(content=data, media_type=ctype, headers={
        "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'", "Cross-Origin-Resource-Policy": "cross-origin"})


@router.get("/videos")
async def official_videos():
    """The official SRU YouTube videos the chat may show (the built-in list with the admin panel's changes)."""
    from app.services.video_service import catalog
    return {"items": catalog()}


@router.get("/fee-config")
async def fee_config():
    """Everything the Fee & Scholarship Calculator needs to draw itself: programs, the exams each
    one accepts, scholarship slabs, hostel and one-time fees. Read from the same fee file the
    agent uses, so the calculator never carries its own copy of the numbers."""
    return fees.fee_config()


@router.get("/connect/{request_id}")
async def counsellor_connect_status(
    request_id: str = Path(..., min_length=16, max_length=64, pattern=r"^[a-f0-9]+$"),
    session_id: str = Query(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN),
):
    """'Talk to a counsellor': the student's card polls this while it waits (v4.12.0). Only the student's own
    request; no full number."""
    from app.services import live_connect

    found = await live_connect.status(request_id, session_id)
    if not found:
        raise HTTPException(status_code=404, detail="Request not found.")
    return found


@router.get("/recovery-context", response_model=ConversationRecoveryContext)
async def get_recovery_context(session_id: str = Query(..., min_length=16, max_length=64, pattern=SESSION_ID_PATTERN)):
    """Retrieve structured recovery context for returning students."""
    from app.services import recovery_service
    return await recovery_service.get_recovery_context(session_id)


@router.post("/reset-session", response_model=ResetSessionResponse)
async def reset_session(body: ResetSessionRequest):
    """Reset active conversation state while preserving verified identity & database records."""
    from app.services import recovery_service
    return await recovery_service.reset_session_conversation(body.session_id, body.conversation_id)

