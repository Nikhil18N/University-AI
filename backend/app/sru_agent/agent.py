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
        key = config.GEMINI_API_KEY
        if not key:
            try:
                from app.config import settings
                keys = settings.get_gemini_api_keys()
                key = keys[0] if keys else ""
            except Exception:
                key = ""
        if key and "," in key:
            key = key.split(",")[0].strip()
        _client = genai.Client(api_key=key)
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
    history = await memory.get_history(session_id)
    contents = [types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
                for h in history]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    # Extract assistant openings from history for anti-repetition & variation rotation
    assistant_openings = []
    for h in history:
        if h.get("role") in ("model", "assistant"):
            text = h.get("text", "")
            for line in text.split("\n"):
                line = line.strip()
                if line and not line.startswith(("#", ">", "|", "```", "•", "-", "*")):
                    assistant_openings.append(line)
                    break
    variant_id = (len(assistant_openings) % 6) + 1

    tool_decl = _tool_declarations()
    used, cards, final = [], [], ""
    try:
        for round_no in range(config.AGENT_MAX_TOOL_ROUNDS + 1):
            last_round = round_no == config.AGENT_MAX_TOOL_ROUNDS
            cfg = types.GenerateContentConfig(
                system_instruction=build_system_prompt(
                    ctx["profile"],
                    variant_id=variant_id,
                    used_openings=assistant_openings,
                ),
                tools=[tool_decl],
                temperature=0.2,
                max_output_tokens=900,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                # On the last round the model must answer in words, not call more tools.
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="NONE" if last_round else "AUTO")),
            )
            models_to_try = []
            for m in (config.AGENT_MODEL, "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"):
                if m and m not in models_to_try:
                    models_to_try.append(m)

            resp = None
            last_err = None
            for model_name in models_to_try:
                try:
                    resp = await client.aio.models.generate_content(
                        model=model_name, contents=contents, config=cfg)
                    break
                except Exception as model_err:
                    err_str = str(model_err).lower()
                    if "not found" in err_str or "404" in err_str or "no longer available" in err_str:
                        log.warning(
                            "Agent model %s unavailable (%s), attempting next fallback model...",
                            model_name,
                            model_err,
                        )
                        last_err = model_err
                        continue
                    raise

            if resp is None:
                if last_err:
                    raise last_err
                raise RuntimeError("All agent models failed to respond")

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

    # Attach contextual cards (such as early bird application ad or fee breakdown)
    try:
        from app.services.card_service import generate_cards
        contextual_cards = generate_cards(user_message=message, answer=final, profile=ctx.get("profile"))
        for c in contextual_cards:
            if c not in cards:
                cards.append(c)
    except Exception as card_err:
        log.warning("Could not generate contextual cards for agent: %s", card_err)

    yield {"type": "done", "conversation_id": conversation_id, "answer": final,
           "tools_used": used, "model": config.AGENT_MODEL,
           # kept so the existing frontend 'done' handler does not break
           "sources": [], "suggestions": [], "cards": cards, "flow": None}

