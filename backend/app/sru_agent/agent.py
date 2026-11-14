"""The agent loop: the model decides, calls tools, reads results, then answers.

    student message
        -> model (sees instructions + student profile + tools)
        -> wants a tool?  yes: run it, give the result back, ask again (max N rounds)
                          no : that text is the final answer

Yields small event dicts so the API can stream progress to the browser:
    {"type": "start"} {"type": "tool", ...} {"type": "token", "delta": "..."} {"type": "done", ...}
"""
import logging
import re

from google import genai
from google.genai import types

from . import config, memory, tools
from .prompt import build_system_prompt

log = logging.getLogger("sru_agent")
_client = None

FALLBACK = (f"I'm having trouble right now. Please call the Admissions Office at "
            f"{config.ADMISSIONS_PHONE} or try again in a moment.")
# Results of these tools are sent to the browser so it can draw a card.
CARD_TOOLS = {"calculate_fee", "check_eligibility", "request_counsellor_callback",
              "book_campus_visit", "get_contact_and_apply_links"}


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _tool_declarations():
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, **decl) for name, (_fn, _label, decl) in tools.TOOLS.items()])


def _chunks(text: str, words_per_chunk: int = 6):
    words = re.findall(r"\S+\s*", text)
    for i in range(0, len(words), words_per_chunk):
        yield "".join(words[i:i + words_per_chunk])


async def run_agent(message: str, session_id: str, conversation_id=None, client=None):
    """Async generator of events for one student message."""
    client = client or get_client()
    message = (message or "").strip()[:config.AGENT_MAX_MESSAGE_CHARS]
    yield {"type": "start", "conversation_id": conversation_id}
    if not message:
        yield {"type": "error", "detail": "Please type a question."}
        return

    ctx = {"session_id": session_id, "conversation_id": conversation_id,
           "profile": await memory.get_profile(session_id)}
    contents = [types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
                for h in await memory.get_history(session_id)]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    tool_decl = _tool_declarations()
    used, cards, final = [], [], ""
    try:
        for round_no in range(config.AGENT_MAX_TOOL_ROUNDS + 1):
            last_round = round_no == config.AGENT_MAX_TOOL_ROUNDS
            cfg = types.GenerateContentConfig(
                system_instruction=build_system_prompt(ctx["profile"]),
                tools=[tool_decl],
                temperature=0.2,
                max_output_tokens=900,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                # On the last round the model must answer in words, not call more tools.
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="NONE" if last_round else "AUTO")),
            )
            resp = await client.aio.models.generate_content(
                model=config.AGENT_MODEL, contents=contents, config=cfg)

            calls = resp.function_calls or []
            if not calls:
                final = (resp.text or "").strip()
                break

            contents.append(resp.candidates[0].content)  # keep the model's turn exactly as returned
            result_parts = []
            for call in calls:
                label = tools.TOOLS[call.name][1] if call.name in tools.TOOLS else "Working"
                yield {"type": "tool", "name": call.name, "status": "running", "label": label}
                result = await tools.run_tool(call.name, dict(call.args or {}), ctx)
                error = result.pop("_error", None)
                if error:
                    log.error("tool %s failed: %s", call.name, error)
                log.info("tool=%s status=%s session=%s", call.name, result.get("status"), session_id)
                used.append({"name": call.name, "status": result.get("status"),
                             "is_action": call.name in tools.ACTION_TOOLS})
                if call.name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok"):
                    cards.append({"type": call.name, "data": result})
                yield {"type": "tool", "name": call.name, "status": "done",
                       "result_status": result.get("status"),
                       "result": result if call.name in CARD_TOOLS else None}
                result_parts.append(types.Part(function_response=types.FunctionResponse(
                    name=call.name, response=result, id=getattr(call, "id", None))))
            contents.append(types.Content(role="user", parts=result_parts))
    except Exception:
        log.exception("agent failed for session %s", session_id)
        yield {"type": "error", "detail": FALLBACK}
        return

    final = final or FALLBACK
    for piece in _chunks(final):
        yield {"type": "token", "delta": piece}
    await memory.append_history(session_id, message, final)
    yield {"type": "done", "conversation_id": conversation_id, "answer": final,
           "tools_used": used, "model": config.AGENT_MODEL,
           # kept so the existing frontend 'done' handler does not break
           "sources": [], "suggestions": [], "cards": cards, "flow": None}
