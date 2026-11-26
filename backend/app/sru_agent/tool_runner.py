"""Tool schema building and concurrent tool execution for sru_agent."""
from __future__ import annotations

import asyncio
import logging

try:
    from google.genai import types
except ImportError:
    types = None

from . import tools

log = logging.getLogger("sru_agent")

CARD_TOOLS = {
    "calculate_fee",
    "check_eligibility",
    "request_counsellor_callback",
    "request_campus_visit_callback",
    "get_contact_and_apply_links",
    "get_university_videos",
    "find_faculty",
}


def tool_declarations(tool_names: list[str] | None = None):
    """Build Gemini Tool declarations for the selected tool subset (or all tools if None)."""
    names = tool_names if tool_names is not None else list(tools.TOOLS.keys())
    decls = [
        types.FunctionDeclaration(name=name, **tools.TOOLS[name][2])
        for name in names
        if name in tools.TOOLS
    ]
    return types.Tool(function_declarations=decls) if decls else None


async def run_action(name: str, args: dict, ctx: dict, used: list, cards: list) -> dict:
    """Run one tool on the student's behalf and record it like a model-requested call."""
    result = await tools.run_tool(name, args, ctx)
    error = result.pop("_error", None)
    if error:
        log.error("tool %s failed: %s", name, error)
    log.info("tool=%s status=%s session=%s (direct)", name, result.get("status"), ctx.get("session_id"))
    used.append({"name": name, "status": result.get("status"), "is_action": name in tools.ACTION_TOOLS})
    if name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok"):
        cards.append({"type": name, "data": result})
    return result


def tool_events(name: str, result: dict) -> list[dict]:
    """Emit running + done tool SSE events for a pre-executed or direct tool call."""
    label = tools.TOOLS[name][1] if name in tools.TOOLS else "Working"
    card_ready = name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok")
    return [
        {"type": "tool", "name": name, "status": "running", "label": label},
        {
            "type": "tool",
            "name": name,
            "status": "done",
            "result_status": result.get("status"),
            "result": result if card_ready else None,
        },
    ]


async def execute_tool_calls(calls, ctx: dict) -> list[dict]:
    """Execute multiple tool calls returned in a single turn concurrently."""
    return list(await asyncio.gather(*(
        tools.run_tool(call.name, dict(call.args or {}), ctx) for call in calls
    )))
