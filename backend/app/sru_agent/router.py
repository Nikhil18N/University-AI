"""API endpoints for the agent. Add to your FastAPI app with:

    from sru_agent.router import router as agent_router
    app.include_router(agent_router)
"""
import json
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, fees, memory
from .agent import run_agent

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
_on_turn_complete = None


def set_turn_logger(fn):
    """Optional. fn: async (session_id, conversation_id, user_text, answer, tools_used) -> None
    Use it to save agent chats in your existing conversations table."""
    global _on_turn_complete
    _on_turn_complete = fn


class AgentRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=config.AGENT_MAX_MESSAGE_CHARS)
    conversation_id: Optional[str] = None


class FeeRequest(BaseModel):
    program: str
    percent: Optional[float] = Field(default=None, ge=0, le=100)
    board: str = "state_board"
    eapcet_rank: Optional[int] = Field(default=None, ge=1)
    jee_percentile: Optional[float] = Field(default=None, ge=0, le=100)
    hostel: str = "none"
    specialization: bool = False


def _sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


@router.post("/stream")
async def agent_stream(req: AgentRequest):
    async def events():
        if not await memory.allow_request(req.session_id):
            yield _sse({"type": "error", "detail": "Too many messages. Please wait a minute and try again."})
            return
        async for event in run_agent(req.message, req.session_id, req.conversation_id):
            if event["type"] == "done" and _on_turn_complete:
                try:
                    await _on_turn_complete(req.session_id, req.conversation_id, req.message,
                                            event["answer"], event["tools_used"])
                except Exception:
                    pass  # logging must never break the chat
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
