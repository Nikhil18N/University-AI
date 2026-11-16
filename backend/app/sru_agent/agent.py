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
from datetime import date, datetime

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
              "book_campus_visit", "get_contact_and_apply_links", "get_university_videos"}


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
    message = (message or "").strip()[:config.AGENT_MAX_MESSAGE_CHARS]
    yield {"type": "start", "conversation_id": conversation_id}
    if not message:
        yield {"type": "error", "detail": "Please type a question."}
        return

    ctx = {"session_id": session_id, "conversation_id": conversation_id,
           "profile": await memory.get_profile(session_id)}
    history = await memory.get_history(session_id, conversation_id)

    # Deterministic intent checks (Date query, Confusion, Campus visit info/booking)
    from .intents import classify_agent_intent
    from .tools import resolve_campus_visit_date

    conv_state = await memory.get_conversation_state(session_id, conversation_id)
    intent = classify_agent_intent(message, conv_state)

    if intent == "DATE_QUERY":
        today_human = date.today().strftime("%B %d, %Y")
        final = f"Today is {today_human}."
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
        await memory.append_history(session_id, message, final, conversation_id)
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "answer": final,
            "tools_used": [],
            "model": config.AGENT_MODEL,
            "sources": [],
            "suggestions": ["How can I visit campus?", "What are the B.Tech CSE fees?", "Hostel rules & curfew"],
            "cards": [],
            "flow": None,
        }
        return

    if intent == "CONFUSION_QUERY":
        final = "Sorry for the confusion! I can help you with campus visit details, directions, timings, or scheduling a visit."
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
        await memory.append_history(session_id, message, final, conversation_id)
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "answer": final,
            "tools_used": [],
            "model": config.AGENT_MODEL,
            "sources": [],
            "suggestions": ["Visiting timings & guidelines", "Schedule a campus visit", "Campus location & directions"],
            "cards": [],
            "flow": None,
        }
        return

    if intent == "CAMPUS_VISIT_INFO":
        await memory.update_conversation_state(session_id, conversation_id, active_topic="campus_visit")
        final = "Are you looking for information about visiting the SR University campus, or would you like to schedule a campus visit?"
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
        await memory.append_history(session_id, message, final, conversation_id)
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "answer": final,
            "tools_used": [],
            "model": config.AGENT_MODEL,
            "sources": [],
            "suggestions": ["I want to schedule a visit", "Campus visiting hours & location", "Can parents accompany me?"],
            "cards": [],
            "flow": None,
        }
        return

    if intent == "DATE_CONFIRMATION_YES":
        pending_date_iso = conv_state.get("pending_visit_date")
        if pending_date_iso:
            try:
                dt = datetime.strptime(pending_date_iso, "%Y-%m-%d").date()
                date_human = dt.strftime("%B %d, %Y")
            except Exception:
                date_human = pending_date_iso

            final = f"Great! Let me help you submit a campus visit request for {date_human}."
            for piece in _chunks(final):
                yield {"type": "token", "delta": piece}

            await memory.update_conversation_state(
                session_id, conversation_id,
                awaiting_date_confirmation=False,
                confirmed_visit_date=pending_date_iso,
                active_topic="campus_visit",
            )
            await memory.append_history(session_id, message, final, conversation_id)

            from app.services.card_service import CAMPUS_VISIT_FORM_CARD
            visit_card = dict(CAMPUS_VISIT_FORM_CARD)
            visit_card["suggested_date"] = pending_date_iso
            visit_card["title"] = f"Schedule Campus Visit — {date_human}"

            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "answer": final,
                "tools_used": ["confirm_visit_date"],
                "model": config.AGENT_MODEL,
                "sources": [],
                "suggestions": ["What are the timings?", "Directions to campus", "Hostel tour"],
                "cards": [visit_card],
                "flow": None,
            }
            return

    if intent == "DATE_CONFIRMATION_NO":
        await memory.update_conversation_state(
            session_id, conversation_id,
            awaiting_date_confirmation=False,
            pending_visit_date=None,
            active_topic="campus_visit",
        )
        final = "No problem! Which date would you prefer to visit the campus?"
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
        await memory.append_history(session_id, message, final, conversation_id)
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "answer": final,
            "tools_used": [],
            "model": config.AGENT_MODEL,
            "sources": [],
            "suggestions": ["Tomorrow", "Next Monday", "This Saturday"],
            "cards": [],
            "flow": None,
        }
        return

    if intent == "CAMPUS_VISIT_BOOKING_WITH_DATE":
        res = resolve_campus_visit_date(message)
        if res.get("date"):
            if res.get("is_sunday"):
                alts = res.get("alternative_suggestions", [])
                alt_text = f" Would Saturday, {alts[0]['human']} or Monday, {alts[1]['human']} work better for you?" if len(alts) >= 2 else ""
                final = (
                    f"SR University campus visits are conducted Monday through Saturday (9:30 AM to 4:30 PM). "
                    f"The campus is closed for visits on Sunday, {res['human']}.{alt_text}"
                )
                for piece in _chunks(final):
                    yield {"type": "token", "delta": piece}
                await memory.append_history(session_id, message, final, conversation_id)
                suggs = [f"Visit on {a['human']}" for a in alts] if alts else ["Select another weekday"]
                yield {
                    "type": "done",
                    "conversation_id": conversation_id,
                    "answer": final,
                    "tools_used": [],
                    "model": config.AGENT_MODEL,
                    "sources": [],
                    "suggestions": suggs,
                    "cards": [],
                    "flow": None,
                }
                return

            if res.get("is_outside_window"):
                final = (
                    f"Campus visits can only be scheduled within the next 90 days. "
                    f"{res['human']} is outside this window. Please choose a date within the next 90 days "
                    f"or contact the Admissions Office at {config.ADMISSIONS_PHONE}."
                )
                for piece in _chunks(final):
                    yield {"type": "token", "delta": piece}
                await memory.append_history(session_id, message, final, conversation_id)
                yield {
                    "type": "done",
                    "conversation_id": conversation_id,
                    "answer": final,
                    "tools_used": [],
                    "model": config.AGENT_MODEL,
                    "sources": [],
                    "suggestions": ["Choose a date this week", "Contact Admissions Office"],
                    "cards": [],
                    "flow": None,
                }
                return

            # Valid date -> Ask confirmation before booking!
            await memory.update_conversation_state(
                session_id, conversation_id,
                pending_visit_date=res["iso"],
                awaiting_date_confirmation=True,
                active_topic="campus_visit",
            )
            final = f"Do you mean {res['human']}?"
            for piece in _chunks(final):
                yield {"type": "token", "delta": piece}
            await memory.append_history(session_id, message, final, conversation_id)
            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "answer": final,
                "tools_used": [],
                "model": config.AGENT_MODEL,
                "sources": [],
                "suggestions": ["Yes", "No, different date"],
                "cards": [],
                "flow": None,
            }
            return

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
    from app.services.rag_service import determine_about_sru_angle, is_about_sru_query
    about_sru_angle = (
        determine_about_sru_angle(
            "\n".join(f"{h.get('role')}: {h.get('text', '')}" for h in history),
            message,
        )
        if is_about_sru_query(message)
        else 1
    )

    tool_decl = _tool_declarations()
    used, cards, final = [], [], ""
    client = client or get_client()
    try:
        for round_no in range(config.AGENT_MAX_TOOL_ROUNDS + 1):
            last_round = round_no == config.AGENT_MAX_TOOL_ROUNDS
            cfg = types.GenerateContentConfig(
                system_instruction=build_system_prompt(
                    ctx["profile"],
                    variant_id=variant_id,
                    used_openings=assistant_openings,
                    about_sru_angle=about_sru_angle,
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
                is_card_ready = call.name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok")
                if is_card_ready:
                    cards.append({"type": call.name, "data": result})
                yield {"type": "tool", "name": call.name, "status": "done",
                       "result_status": result.get("status"),
                       "result": result if is_card_ready else None}
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
    await memory.append_history(session_id, message, final, conversation_id)

    # Attach contextual cards (such as early bird application ad, fee breakdown, or video recommendations)
    try:
        from app.services.card_service import generate_cards
        from app.services.video_service import is_explicit_video_query, should_display_videos
        from app.api.v1.deps import get_embedding_provider

        query_embedding = None
        if is_explicit_video_query(message) or should_display_videos(message):
            try:
                emb_provider = get_embedding_provider()
                query_embedding = await emb_provider.embed_single(message)
            except Exception as emb_err:
                log.warning("Could not compute embedding for video lookup: %s", emb_err)

        contextual_cards = generate_cards(
            user_message=message,
            answer=final,
            profile=ctx.get("profile"),
            session_id=session_id,
            query_embedding=query_embedding,
        )
        for c in contextual_cards:
            if c not in cards:
                cards.append(c)
    except Exception as card_err:
        log.warning("Could not generate contextual cards for agent: %s", card_err)

    # Generate contextual suggestions
    suggestions = []
    try:
        from app.services.suggestion_service import generate_suggestions
        suggestions = generate_suggestions(
            intent="UNIVERSITY",
            user_message=message,
            answer=final,
            profile=ctx.get("profile"),
        )
    except Exception as sugg_err:
        log.warning("Could not generate suggestions for agent: %s", sugg_err)

    yield {"type": "done", "conversation_id": conversation_id, "answer": final,
           "tools_used": used, "model": config.AGENT_MODEL,
           # kept so the existing frontend 'done' handler does not break
           "sources": [], "suggestions": suggestions, "cards": cards, "flow": None}

