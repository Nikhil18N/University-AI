"""API endpoints for the agent. Add to your FastAPI app with:

    from sru_agent.router import router as agent_router
    app.include_router(agent_router)
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, fees, memory
from .agent import run_agent

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
        await _on_turn_complete(session_id, conv_id, message, event["answer"], event["tools_used"],
                                cards=event.get("cards") or [], suggestions=event.get("suggestions") or [],
                                started_at=started_at, **extra)
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


class AgentRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=config.AGENT_MAX_MESSAGE_CHARS)
    conversation_id: Optional[str] = None
    # "web" (the website) or "widget" (the embeddable chat bubble); stored with the chat for staff.
    channel: Optional[str] = Field(default=None, max_length=12, pattern=r"^[a-z]+$")


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


def _sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@router.post("/stream")
async def agent_stream(req: AgentRequest):
    async def events():
        if not await memory.allow_request(req.session_id):
            yield _sse({"type": "error", "detail": "Too many messages. Please wait a minute and try again."})
            return

        conv_id = req.conversation_id
        if _conversation_resolver:
            try:
                resolved = await _conversation_resolver(req.session_id, req.conversation_id, req.message)
                if resolved:
                    conv_id = str(resolved)
            except Exception:
                pass  # Fall back to req.conversation_id

        started_at = datetime.now(timezone.utc)
        async for event in run_agent(req.message, req.session_id, conv_id):
            if event["type"] == "done":
                # What the chat now knows about the student, so Settings > My details stays in step.
                try:
                    event["profile"] = memory.public_profile(await memory.get_profile(req.session_id))
                except Exception:
                    event["profile"] = {}
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
    session_id: str = Field(..., min_length=8, max_length=64)
    name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=20)
    program_interest: Optional[str] = Field(default=None, max_length=120)


@router.get("/profile")
async def get_profile(session_id: str = Query(..., min_length=8, max_length=64)):
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
    return {"status": "ok", "profile": memory.public_profile(await memory.get_profile(body.session_id))}


@router.delete("/profile")
async def forget_profile(session_id: str = Query(..., min_length=8, max_length=64)):
    """Settings > Forget my details: the agent forgets this student. Saved callback / visit
    requests stay with the Admissions Office; say 'cancel my callback' in the chat to withdraw one."""
    await memory.clear_profile(session_id)
    return {"status": "ok", "profile": {}}


@router.get("/fee-config")
async def fee_config():
    """Everything the Fee & Scholarship Calculator needs to draw itself: programs, the exams each
    one accepts, scholarship slabs, hostel and one-time fees. Read from the same fee file the
    agent uses, so the calculator never carries its own copy of the numbers."""
    return fees.fee_config()
