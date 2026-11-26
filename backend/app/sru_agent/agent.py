"""The agent loop: the model decides, calls tools, reads results, then answers.

    student message
        -> quick checks the code can settle by itself (today's date, "don't call me",
           a callback / visit request that already has name + number)
        -> model (sees instructions + student profile + tools)
        -> wants a tool?  yes: run it, give the result back, ask again (max N rounds)
                          no : that text is the final answer
        -> honesty checks (never "saved" or "cancelled" unless a tool really did it)

Yields small event dicts so the API can stream progress to the browser:
    {"type": "start"} {"type": "tool", ...} {"type": "token", "delta": "..."} {"type": "done", ...}

Under load the agent (1) spreads students across every configured Gemini key, (2) moves to the
next key when one is rate limited, (3) waits and retries when Google is busy, (4) lets only
AGENT_MAX_CONCURRENCY model calls run at once, and (5) still answers fee questions from the fee
file if the model cannot be reached at all.
"""
import asyncio
import json
import contextvars
import logging
import re
import time
import weakref
from datetime import date, datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from . import affordability, ai_guard, config, dialogue, eligibility, journey, faculty, fee_flow, fee_intake, fees, followups, intents, knowledge, memory, responses, tools
from app.services import card_service
from . import campus_life, compound, fact_service, fee_coordinator, fee_journey, fee_plan, llm_loop, observability, policy_engine, policy_models, policy_service, postprocess, semantic_router, structured_flows, tool_runner
from .llm_loop import (
    GeminiAgentProvider,
    ModelUnavailable,
    _KeyRing,
    _apply_rounds_telemetry,
    _can_stream,
    _error_kind,
    _extract_usage_metadata,
    _gate,
    _gates,
    _generate,
    _generate_stream,
    _handle_call_error,
    _record_round_usage,
    _remaining_budget,
    _ring,
    _with_thinking,
)
from .tool_runner import (
    run_action as _run_action,
    tool_declarations as _tool_declarations,
    tool_events as _tool_events,
)
from .postprocess import (
    CARD_TOOLS,
    FEE_TOOLS as _FEE_TOOLS,
    HAS_MD_TABLE as _HAS_MD_TABLE,
    INFO_CARDS as _INFO_CARDS,
    VIDEO_CARDS as _VIDEO_CARDS,
    vary as _vary,
    with_topic_videos as _with_topic_videos,
)
from .prompt import build_dynamic_suffix, build_static_prefix, build_system_prompt

log = logging.getLogger("sru_agent")
_client = None
_TURN_STARTED: contextvars.ContextVar[float | None] = contextvars.ContextVar("_TURN_STARTED", default=None)
_TURN_TELEMETRY_RECORDED: contextvars.ContextVar[bool] = contextvars.ContextVar("_TURN_TELEMETRY_RECORDED", default=False)


def _should_persist_telemetry_db() -> bool:
    """Batch telemetry into agent_turn_logger when router._on_turn_complete is wired; else persist directly."""
    try:
        from . import router as agent_router
        return agent_router._on_turn_complete is None
    except Exception:
        return True


def _extract_usage_metadata(resp) -> dict[str, int]:
    """Extract Gemini usage_metadata token counts safely from a GenerateContentResponse."""
    meta = getattr(resp, "usage_metadata", None)
    if meta is None:
        return {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "thoughts_token_count": 0,
            "cached_content_token_count": 0,
        }
    return {
        "prompt_token_count": int(getattr(meta, "prompt_token_count", None) or 0),
        "candidates_token_count": int(getattr(meta, "candidates_token_count", None) or 0),
        "thoughts_token_count": int(getattr(meta, "thoughts_token_count", None) or 0),
        "cached_content_token_count": int(getattr(meta, "cached_content_token_count", None) or 0),
    }


def _record_round_usage(link: dict, model: str, resp, started_perf: float) -> None:
    round_ms = round((time.perf_counter() - started_perf) * 1000, 2)
    usage = _extract_usage_metadata(resp)
    link.setdefault("rounds", []).append({"model": model, "latency_ms": round_ms, **usage})


def _apply_rounds_telemetry(telemetry: observability.PolicyTurnTelemetry, link: dict | None) -> None:
    rounds = (link or {}).get("rounds") or []
    if not rounds:
        return
    telemetry.llm_rounds = len(rounds)
    telemetry.model = rounds[-1].get("model") or telemetry.model
    telemetry.prompt_tokens = sum(r.get("prompt_token_count", 0) for r in rounds)
    telemetry.candidates_tokens = sum(r.get("candidates_token_count", 0) for r in rounds)
    telemetry.thoughts_tokens = sum(r.get("thoughts_token_count", 0) for r in rounds)
    telemetry.cached_tokens = sum(r.get("cached_content_token_count", 0) for r in rounds)
    telemetry.round_latencies_ms = [r.get("latency_ms", 0.0) for r in rounds]
    telemetry.generation_latency_ms = round(sum(telemetry.round_latencies_ms), 2)

FALLBACK_OPTIONS = [
    f"I'm having trouble right now. Please call the Admissions Office at {config.ADMISSIONS_PHONE} or try again in a moment.",
    f"I'm experiencing a temporary connection issue. Please try again in a moment, or reach Admissions directly at {config.ADMISSIONS_PHONE}.",
    f"I couldn't reach the service just now. Please try again in a moment, or call the Admissions Office at {config.ADMISSIONS_PHONE}.",
]
FALLBACK = FALLBACK_OPTIONS[0]


def get_fallback_text(seed_str: str = "") -> str:
    if not seed_str:
        return FALLBACK
    import hashlib
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return FALLBACK_OPTIONS[h % len(FALLBACK_OPTIONS)]
# Results of these tools are sent to the browser so it can draw a card.
CARD_TOOLS = {"calculate_fee", "check_eligibility", "request_counsellor_callback",
              "request_campus_visit_callback", "get_contact_and_apply_links", "get_university_videos",
              "find_faculty"}
# When one of these ran, the answer is about this student's own numbers, so the generic
# "B.Tech CSE fee" table from card_service must not be shown underneath it.
_FEE_TOOLS = {"calculate_fee", "compare_programs", "get_program_info", "get_special_concessions"}
_FALLBACK_MODELS = ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash")
# Campus visits: SRU Buddy never books or confirms one (admissions brief, Nov 2026). It points to the
# admissions team (sru.edu.in/visit-us) and can pass the student's number on as a callback request.
def _visit_guide(date_text: str | None = None) -> str:
    asked = f" for {date_text}" if date_text else ""
    return (f"Campus visits{asked} are arranged by the SR University admissions team. I can't book or confirm a "
            f"visit myself, but they will help you plan it:\n"
            f"- Call or WhatsApp: {config.CAMPUS_VISIT_PHONE}\n"
            f"- Campus: {config.CAMPUS_ADDRESS}\n\n"
            f"Please confirm the day and time with them before you travel. If you like, share your name and "
            f"10-digit mobile number and I will ask the admissions team to call you back about the visit.")


_CAMPUS_TOUR_CHOICE_CHIPS = ["🎥 Virtual Tour (Videos & Info)", "🏛️ In-Person Campus Visit"]
_CAMPUS_TOUR_CHOICE_TEXT = (
    "We offer two ways to explore our 170-acre campus:\n\n"
    "1. 🎥 **Virtual Tour** – Watch official video walkthroughs and explore our smart classrooms, central library, "
    "AI & robotics centers, and student life online.\n"
    "2. 🏛️ **In-Person Visit** – Visit our Warangal campus in person, meet faculty, and take a guided tour "
    "arranged by our admissions team.\n\n"
    "Which one would you prefer?"
)

_VIRTUAL_TOUR_CHIPS = ["🏛️ In-Person Campus Visit", "Hostel details", "Why choose SRU?"]
_VIRTUAL_TOUR_TEXT = (
    "Here is the virtual walkthrough of our 170-acre Warangal campus!\n\n"
    "• 🏛️ **Academic & Research**: Smart IoT classrooms, digital central library, and 11 specialized research centers.\n"
    "• 🚀 **SRiX Innovation Exchange**: On-campus incubator with 14+ maker spaces supporting 171+ student startups.\n"
    "• 🏠 **Campus Life**: Modern sports arenas, secure hostels, and a 4,000-seat dining hall.\n\n"
    f"Explore the videos below! For an in-person guided tour, call Admissions at {config.CAMPUS_VISIT_PHONE}."
)

_VISIT_CHIPS = ["Ask counsellor to call me", "How to reach the campus", "🎥 Virtual Tour (Videos & Info)"]
_VISIT_DETAIL = re.compile(r"\b(?:parents?|timings?|hours?|allowed|dress|bring|documents?|reach|directions?|route|"
                           r"bus|train|far|distance|weekends?|sundays?|holidays?|accompan\w*|stay|guest|lunch|"
                           r"free|cost|charge)\b", re.IGNORECASE)


# ------------------------------------------------------------ model access ----
def get_client():
    """A Gemini client on the first configured key (kept for scripts and older code)."""
    global _client
    if _client is None:
        _client = _ring.client(_ring.next_key() or config.GEMINI_API_KEY)
    return _client


_DEFAULT_GET_CLIENT = get_client


def _gate() -> asyncio.Semaphore:
    """At most AGENT_MAX_CONCURRENCY model calls at a time; the rest queue instead of failing."""
    loop = asyncio.get_running_loop()
    gate = _gates.get(loop)
    if gate is None:
        gate = _gates[loop] = asyncio.Semaphore(max(1, config.AGENT_MAX_CONCURRENCY))
    return gate


def _error_kind(exc: Exception) -> str:
    """'model' (try another model), 'rate' (try another key / wait), 'busy' (wait), 'config' (the
    model refused a setting such as the thinking level), or 'fatal'."""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()
    if (code == 400 or "400" in text or "invalid_argument" in text) and "think" in text:
        return "config"
    if code == 404 or "not found" in text or "404" in text or "no longer available" in text:
        return "model"
    if code == 429 or "429" in text or "resource_exhausted" in text or "resource exhausted" in text \
            or "quota" in text or "rate limit" in text:
        return "rate"
    if isinstance(exc, (ConnectionError, OSError)) or "connecterror" in type(exc).__name__.lower() \
            or "connection" in text or "timed out" in text or "name resolution" in text:
        return "busy"  # the network or Google is unreachable: wait, then answer without the model
    if code in (500, 502, 503, 504) or isinstance(exc, (asyncio.TimeoutError, TimeoutError)) \
            or any(w in text for w in ("503", "unavailable", "overloaded", "deadline exceeded", "internal error")):
        return "busy"
    return "fatal"


class ModelUnavailable(Exception):
    """Every key has used up its quota: answer without the model instead of making students wait."""


def _remaining_budget(link: dict) -> float:
    deadline = link.get("deadline")
    if deadline is None:
        return config.AGENT_CALL_TIMEOUT
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ModelUnavailable("agent request time budget exhausted")
    return min(config.AGENT_CALL_TIMEOUT, remaining)


def _is_daily_limit(exc: Exception) -> bool:
    text = str(exc).lower().replace(" ", "").replace("_", "")
    return "perday" in text or "daily" in text or "requestsperday" in text


async def _handle_call_error(exc, link: dict, attempt: int, model: str) -> float | None:
    """Decide what to do after a failed model call: None = try the next model at once, a number =
    wait that long and retry; raises when there is nothing left to try."""
    kind = link["error_kind"] = _error_kind(exc)
    err_str = str(exc).lower()
    if "name resolution" in err_str or "clientconnectordnserror" in type(exc).__name__.lower():
        raise exc
    if kind == "model" and link["model_idx"] + 1 < len(link["models"]):
        log.warning("Agent model %s unavailable (%s), trying the next model", model, exc)
        link["model_idx"] += 1
        return None
    if kind == "config" and link.get("thinking"):
        log.warning("Model %s refused the thinking setting (%s); retrying without it", model, str(exc)[:120])
        link["thinking"] = False
        return None
    if kind in ("fatal", "model", "config") or attempt >= len(config.AGENT_RETRY_DELAYS):
        raise exc
    wait = config.AGENT_RETRY_DELAYS[attempt]
    if kind == "rate" and not link["fixed"]:
        # A per-day limit will not clear in a few seconds: rest that key for an hour.
        daily = _is_daily_limit(exc)
        new_key = _ring.rate_limited(link["key"], config.AGENT_DAILY_LIMIT_COOLDOWN if daily else None)
        if _ring.all_resting() and (daily or _ring.size() > 1):
            raise ModelUnavailable(str(exc)[:200]) from exc
        if new_key != link["key"]:
            link["key"], wait = new_key, 0.2  # a fresh key: go again almost at once
    log.warning("Model call %s (%s); retry %d in %.1fs", kind, str(exc)[:120], attempt + 1, wait)
    return wait


def _with_thinking(cfg, link: dict, model: str):
    """Ask for the least thinking the model allows (AGENT_THINKING_LEVEL), which is the biggest
    single speed setting on Gemini 3 models. Dropped automatically if a model refuses it."""
    level = (link.get("thinking_level") or config.AGENT_THINKING_LEVEL or "").upper()
    if not link.get("thinking") or not level or level == "DEFAULT":
        return cfg
    if model.startswith("gemini-2"):
        thinking = types.ThinkingConfig(thinking_budget=0)
    else:
        if level == "MINIMAL" and not any(model.startswith(m) for m in _MINIMAL_OK):
            level = "LOW"
        thinking = types.ThinkingConfig(thinking_level=level)
    return cfg.model_copy(update={"thinking_config": thinking})


# Models that accept thinking_level MINIMAL (the others get LOW).
_MINIMAL_OK = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash",
               "gemini-3-flash")


# (_generate, _can_stream, _generate_stream are imported from .llm_loop)


def _tool_declarations(tool_names: list[str] | None = None):
    names = tool_names if tool_names is not None else list(tools.TOOLS.keys())
    decls = [
        types.FunctionDeclaration(name=name, **tools.TOOLS[name][2])
        for name in names
        if name in tools.TOOLS
    ]
    return types.Tool(function_declarations=decls) if decls else None


def _chunks(text: str, words_per_chunk: int = 6):
    words = re.findall(r"\S+\s*", text)
    for i in range(0, len(words), words_per_chunk):
        yield "".join(words[i:i + words_per_chunk])


# ------------------------------------------------------- small reply helpers ----
def _is_personal_eligibility(fee: dict | None) -> bool:
    """True only when a fee calculation used the student's own marks AND eligibility.py confirmed they meet
    the programme's minimum (every source agrees, required subjects known). A plain programme fee ("CSE fee"),
    a hostel answer, a disputed score or a below-minimum score is not a celebration."""
    if not (isinstance(fee, dict) and fee.get("status") == "ok" and fee.get("scores_considered")):
        return False
    return (fee.get("admission_eligibility") or {}).get("eligible") is True


def _asks_question(answer) -> bool:
    """True when the reply ends by asking the student something (a "?" in its last lines)."""
    text = re.sub(r"[*_`>#]+", "", str(answer or "")).strip()
    tail = "\n".join(line for line in text.splitlines()[-3:] if line.strip())[-260:]
    return "?" in tail


_CHIP_STOP = {"would", "like", "know", "more", "about", "want", "your", "this", "that", "with", "have", "tell",
              "need", "please", "check", "explore", "also", "there", "here", "what", "which", "shall", "could", "should",
              "next", "help", "information", "details", "university", "sru", "the", "and", "for", "you", "any", "can"}
_OPEN_INVITE = re.compile(r"\bwhat\s+(?:else\s+)?(?:would|do|can)\s+you\s+(?:like|want)\b|\banything\s+else\b|"
                          r"\bwhat\s+can\s+i\s+help\b|\bwhere\s+would\s+you\s+like\s+to\s+start\b", re.IGNORECASE)


def _chip_words(text: str) -> set:
    words = set()
    for w in re.findall(r"[a-z]{3,}", str(text or "").lower()):
        if w in _CHIP_STOP:
            continue
        w = w[:-1] if w.endswith("s") and len(w) > 3 else w
        words.add(w[:5])
    return words


def _chips_for(answer, suggestions, options: bool) -> list:
    """Quick-response buttons (admin setting "suggestion_chips", v4.13.0). 'questions_only' (default):
    - the answer options of a step (Yes / No, rooms, boards...) are always kept, and so is "continue my fee estimate";
    - other suggestions only when the reply asks the student something, and only the ones that fit that question:
      a yes / no question -> its Yes / No; an open "what would you like to know?" -> up to 3 starting points; a
      specific question ("...hostel rooms, rules or fees?") -> up to 3 buttons about what it asks; nothing unrelated.
    'always': every suggestion, as before."""
    from app.services import app_settings
    chips = list(suggestions or [])
    if not chips or options or app_settings.get("suggestion_chips") == "always":
        return chips
    resume = [c for c in chips if c == fee_journey.RESUME]
    others = [c for c in chips if c != fee_journey.RESUME]
    if not _asks_question(answer):
        return resume
    text = re.sub(r"[*_`>#]+", "", str(answer or "")).strip()
    question = next((s for s in reversed(re.split(r"(?<=[.!?])\s+", text)) if "?" in s), "")
    if followups.needs_yes_no(answer) or all(re.match(r"^\W*(?:yes|no)\b", c, re.I) for c in others):
        return others + resume
    if _OPEN_INVITE.search(question):
        return others[:3] + resume
    if re.match(r"^\W*(?:which|what\s+(?:kind|type))\b", question, re.I):
        return others[:4] + resume   # "Which board / branch / room?": the buttons are its answers
    # The question and the paragraph it is in (options are often listed there: "...CSE, AI & Robotics or ECE?")
    last_paragraph = text.split("\n\n")[-1]
    asked = _chip_words(question) | _chip_words(last_paragraph)
    fitting = [c for c in others if _chip_words(c) & asked]
    return fitting[:3] + resume


def _answer_sources(answer: str, evidence: list, passages: str = "") -> list[dict]:
    """The sources that support this answer (v4.17.1): only evidence used in this turn, and only when the answer
    shares its specific content (names, figures, distinctive words). Links come from the sources' own metadata;
    none is ever made up."""
    def _tokens(text):
        text = (text or "").lower()
        return {w for w in re.findall(r"[a-z]{5,}|\d[\d,.]{1,}", text)}
    said = _tokens(answer)
    if not said:
        return []
    cands = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        tool, r = item.get("tool"), item.get("result") or {}
        if tool == "search_university_info":
            for ps in r.get("passages") or []:
                src = ps.get("source") or {}
                url = src.get("page_url") or (src.get("source") if str(src.get("source", "")).startswith("http") else None)
                cands.append({"document_id": str(src.get("document_id") or f"handbook:{ps.get('title', '')[:60]}"),
                              "title": ps.get("title") or "SR University document", "section": src.get("section"),
                              "page_url": url, "_text": ps.get("text", "")})
        elif tool == "find_faculty":
            for f in r.get("faculty") or []:
                cands.append({"document_id": f"faculty:{f.get('profile_url') or f.get('name')}",
                              "title": f"Faculty profile: {f.get('name', '')}", "page_url": f.get("profile_url"),
                              "department": f.get("department"), "_text": json.dumps(f, ensure_ascii=False)})
            for k in r.get("approved_knowledge") or []:
                cands.append({"document_id": f"knowledge:{k.get('title', '')[:60]}", "title": k.get("title", ""),
                              "_text": k.get("text", "")})
        elif tool in ("calculate_fee", "compare_programs", "check_eligibility", "get_special_concessions",
                      "get_program_info"):
            cands.append({"document_id": "fee-policy-2027-28",
                          "title": r.get("source") or "SR University Fee Circular 2027-28",
                          "_text": json.dumps(r, ensure_ascii=False, default=str)})
    for m in re.finditer(r"^\[(.+?) \| source: (.+?)\]\n(.*?)(?=^\[|\Z)", passages or "", re.M | re.S):
        cands.append({"document_id": f"handbook:{m.group(1)[:60]}", "title": m.group(1),
                      "page_url": m.group(2) if m.group(2).startswith("http") else None, "_text": m.group(3)})
    out, seen = [], set()
    for c in cands:
        overlap = said & _tokens(c.pop("_text", ""))
        key = c["document_id"]
        if key in seen or len(overlap) < 3:
            continue
        seen.add(key)
        out.append({k: v for k, v in c.items() if v})
        if len(out) >= 4:
            break
    return out


def _done(conversation_id, answer, used=(), cards=(), suggestions=(), telemetry=None, profile=None, eligible=None,
          options=False, sources=None):
    # Every answer passes here: one that leaks internal instructions or a secret-shaped string is replaced.
    answer = ai_guard.guard_reply(answer) if isinstance(answer, str) else answer
    suggestions = _chips_for(answer, suggestions, options)
    fee_plan.apply_card_settings(cards)   # the admin panel's concessions picker choice, for every card
    d = {"type": "done", "conversation_id": conversation_id, "answer": answer,
         "tools_used": list(used), "model": config.AGENT_MODEL,
         "sources": list(sources or []), "suggestions": list(suggestions), "cards": list(cards), "flow": None}
    if profile is not None:
        d["profile"] = profile
    if telemetry is not None:
        d["telemetry"] = telemetry
    if eligible is not None:
        d["eligible"] = eligible
    else:
        cards_list = list(cards)
        if any(isinstance(c, dict) and c.get("type") == "calculate_fee" and _is_personal_eligibility(c.get("data"))
               for c in cards_list):
            d["eligible"] = True
    return d


async def _counsellor_connect(message, session_id, conversation_id, profile, ctx):
    """'Talk to a counsellor': save the callback first, then ring the admin panel for a short wait (office hours)."""
    from app.services import app_settings, live_connect

    phone = tools.clean_phone(profile.get("phone") or "")
    name = str(profile.get("name") or "").strip()
    if not phone or len(name) < 2:
        await memory.update_conversation_state(session_id, conversation_id, pending_action="callback", pending_turns=0)
        async for ev in _say("Sure! To connect you with a counsellor, please send your full name and 10-digit mobile "
                             "number.", message, session_id, conversation_id, resume=False):
            yield ev
        return
    masked = "******" + phone[-4:]
    existing = await live_connect.current_for(session_id, conversation_id)
    if existing and existing["status"] in ("waiting", "accepted"):
        text = ("You're already in the queue; a counsellor is being reached." if existing["status"] == "waiting"
                else f"A counsellor is already calling you on {masked}.")
        async for ev in _say(text, message, session_id, conversation_id,
                             cards=[{"type": "counsellor_connect", "data": existing}], resume=False):
            yield ev
        return
    result = await tools.run_tool("request_counsellor_callback", {
        "name": name, "phone": phone, "consent": True,
        "preferred_time": "as soon as possible (asked to talk to a counsellor)"}, ctx)
    result.pop("_error", None)
    if result.get("status") != "saved":
        async for ev in _say(f"I couldn't reach the admissions team right now. Please call them on "
                             f"{config.ADMISSIONS_PHONE}.", message, session_id, conversation_id, resume=False):
            yield ev
        return
    used = [{"name": "request_counsellor_callback", "status": "saved", "is_action": True}]
    first = _first_name(name)
    first = (first[:1].upper() + first[1:]) if first and not tools.is_placeholder_name(first) else ""
    who = f", {first}" if first else ""
    if existing and existing["status"] == "busy" and result.get("already_saved"):
        async for ev in _say(f"Your callback request is already with our admissions team{who}. Our admissions "
                             f"counsellor will call you back on {masked}.",
                             message, session_id, conversation_id, used=used, resume=False):
            yield ev
        return
    if not app_settings.get("connect_enabled") or not live_connect.in_office_hours():
        when = (f"{live_connect.next_opening()} or soon after" if not live_connect.in_office_hours()
                else "as soon as possible")
        text = (f"Your callback request has been successfully submitted{who}. Our counsellors are available "
                f"{live_connect.hours_text()} (India time), and our admissions counsellor will call you back on "
                f"{masked} {when}.")
        async for ev in _say(text, message, session_id, conversation_id, used=used, resume=False):
            yield ev
        return
    from . import case_summary
    req = await live_connect.create(session_id, conversation_id, name, phone,
                                    (ctx.get("profile") or {}).get("last_lead_id"),
                                    case_summary.build(profile, ctx.get("conv_state"), ctx.get("history")))
    async for ev in _say("Connecting you to a counsellor…", message, session_id, conversation_id, used=used,
                         cards=[{"type": "counsellor_connect", "data": req}], resume=False):
        yield ev


# Cards that are information (videos may go with them); any other card means a workflow step (no videos then).
_INFO_CARDS = {"placement_highlights", "hostel_facilities", "campus_tour", "curriculum"}
_VIDEO_CARDS = {"video_recommendations", "get_university_videos", "event_highlights"}


async def _with_topic_videos(message: str, text: str, cards: list, session_id: str, conversation_id) -> list:
    """Up to 2 official SRU videos on the topic the student asked about (v4.15.1), only when the reply is information
    (not a fee step, a form, a callback or a question back), only from that topic, once per topic per chat, and
    never a video already shown in this chat."""
    from app.services import video_service

    types = {c.get("type") for c in cards if isinstance(c, dict)}
    if types & _VIDEO_CARDS:
        # videos chosen by another path: remembered, so the same topic / videos are not offered again in this chat
        vids = [v for c in cards if isinstance(c, dict) and c.get("type") in _VIDEO_CARDS
                for v in ((c.get("data") or c).get("videos") or []) if isinstance(v, dict)]
        if vids:
            state = await memory.get_conversation_state(session_id, conversation_id)
            topic = video_service.video_topic(message) or vids[0].get("category")
            await memory.update_conversation_state(
                session_id, conversation_id,
                video_topics=(list(state.get("video_topics") or []) + ([topic] if topic else []))[-12:],
                videos_shown=(list(state.get("videos_shown") or []) + [v.get("id") for v in vids])[-30:])
        return cards
    if types - _INFO_CARDS:
        return cards
    if re.search(r"(?:^|\n)\s*Step\s+\d|\bwhich\s+(?:programme|program|board|branch)\b", text or "", re.I):
        return cards
    state = await memory.get_conversation_state(session_id, conversation_id)
    if state.get("fee_intake", {}) and (state.get("fee_intake") or {}).get("waiting_for") not in (None, "done"):
        return cards                                       # the fee steps are open: keep the chat on them
    topics = list(state.get("video_topics") or [])
    shown = set(state.get("videos_shown") or [])
    topic = video_service.video_topic(message)
    if not topic or topic in topics:
        return cards
    topic, vids = video_service.topic_videos(message, exclude=shown, limit=2)
    if not vids:
        return cards
    await memory.update_conversation_state(session_id, conversation_id, video_topics=(topics + [topic])[-12:],
                                           videos_shown=(list(shown) + [v["id"] for v in vids])[-30:])
    return cards + [video_service.create_video_card(vids, topic=topic)]


def _vary(options: list[str], *seed) -> str:
    """One of several natural wordings for a line the code writes (v4.15.0: no fixed phrasing for the same line
    every time). The choice depends on the conversation and the turn, so a repeat is worded differently."""
    import hashlib
    key = "|".join(str(x) for x in seed)
    return options[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(options)]


def _other_program_named(message: str, conv_state: dict) -> bool:
    """'Can I join Civil with 88%?' during a CSE estimate: a question about another programme (an eligibility
    check), not a correction of the marks for the one being evaluated (v4.15.0)."""
    named = fees.find_program(message or "")
    current = fees.find_program(str((conv_state.get(fee_journey.KEY) or {}).get("program") or ""))
    return bool(named and current and named != current and not fee_journey._SWITCH.search(message or ""))


def _open_step(profile: dict, conv_state: dict) -> dict | None:
    """Delegate to fee_coordinator.open_step."""
    return fee_coordinator.open_step(profile, conv_state)


async def _with_resume_chip(session_id, conversation_id, chips, text: str = "") -> list:
    """A side question answered while a fee evaluation is unfinished: offer to continue it (one tap)."""
    try:
        state = (await memory.get_conversation_state(session_id, conversation_id)).get(fee_journey.KEY)
    except Exception:
        state = None
    chip = fee_journey.resume_chip(state)
    is_step = bool(re.search(r"(?:^|\n|\. )\s*Step\s+\d+\s+of\s+\d|^\s*(?:To work out your exact fee|Before I give you)",
                             text or ""))
    if not chip and not is_step and (_SIDE_TURN.get() or text):
        try:   # a side question while the scholarship / fee steps (fee_intake) wait for an answer
            intake = (await memory.get_conversation_state(session_id, conversation_id)).get("fee_intake") or {}
            if intake.get("waiting_for") not in (None, "done"):
                chip = fee_journey.RESUME
        except Exception:
            pass
    chips = list(chips or [])
    if not chip or chip in chips or chips == ["Yes", "No"]:
        return chips
    return (chips[:3] + [chip]) if len(chips) >= 4 else chips + [chip]


async def _counsellor_result(fee_result, details, c_text, chips, message, session_id, conversation_id,
                             conv_state, ctx, set_state):
    """The step-by-step scholarship flow has its result.

    Eligible (or eligible pending confirmation): the fee evaluation agent takes over. It confirms the
    qualification and introduces the special concessions BEFORE any fee card (fee_journey.after_scholarship);
    inside a running evaluation it simply moves to the next open step. Below the minimum marks: the existing
    explanation with the fee card, unchanged."""
    from . import eligibility
    verdict = counsellor_verdict(fee_result, details)
    used = [{"name": "calculate_fee", "status": "ok", "is_action": False}]
    blocked = verdict.get("status") == eligibility.BELOW or verdict.get("stream_ok") is False
    if blocked:
        async for ev in _say(c_text, message, session_id, conversation_id, used=used,
                             cards=[{"type": "calculate_fee", "data": fee_result}],
                             suggestions=chips, exact_chips=True, eligible=verdict.get("eligible")):
            yield ev
        return
    profile_now = ctx.get("profile") or {}
    fj = fee_journey.after_scholarship(conv_state.get(fee_journey.KEY), profile_now, c_text,
                                       verdict.get("eligible"), seed=f"{session_id}{message}",
                                       specialization=details.get("specialization"))
    fields = {fee_journey.KEY: fj["state"], "offer": None}
    if fj["state"].get("program"):
        fields["active_program"] = fj["state"]["program"]
    await set_state(**fields)
    async for ev in _say(fj["text"], message, session_id, conversation_id, used=used, cards=fj.get("cards") or [],
                         suggestions=fj.get("chips") or [], exact_chips=True, eligible=verdict.get("eligible"),
                         resume=False):
        yield ev


async def _run_fee_journey(fj: dict, message, session_id, conversation_id, profile, set_state):
    """Carry out what the fee evaluation agent decided (fee_journey.decide / after_scholarship)."""
    if fj["kind"] == "info":   # an answer that does not change any evaluation (e.g. concession documents)
        async for ev in _say(fj["text"], message, session_id, conversation_id, cards=fj.get("cards") or [],
                             suggestions=fj.get("chips") or [], exact_chips=True, resume=False):
            yield ev
        return
    state = fj["state"]
    fields = {fee_journey.KEY: state, "offer": None}
    if state.get("program"):
        fields["active_program"] = state["program"]
    if fj.get("profile_updates"):   # e.g. an EAPCET rank given to the lowest-fee agent
        profile = await memory.update_profile(session_id, **fj["profile_updates"])
    if fj["kind"] == "scholarship_steps":
        # Hand over to the existing step-by-step scholarship flow for the marks that are missing; its result
        # comes back through fee_journey.after_scholarship.
        step = fee_intake.decide("Calculate my scholarship", profile,
                                 {"counsellor_mode": True, **({"program": state["program"]} if state.get("program") else {})})
        if step and step.get("action") == "ask":
            fields["fee_intake"] = step["state"]
            await set_state(**fields)
            lead = (fj.get("lead") or "").strip()
            text = (lead + "\n\n" if lead else "") + step["text"].replace("Sure! ", "").replace("Sure, ", "")
            plan = [c for c in fj.get("cards") or [] if c.get("type") == "agent_plan"]
            async for ev in _say(text, message, session_id, conversation_id, cards=plan + (step.get("cards") or []),
                                 suggestions=step.get("chips") or [], exact_chips=True, resume=False):
                yield ev
            return
        state["scholarship"] = "no"   # nothing to ask (should not happen): carry on without it
        fj = fee_journey.next_step(state, profile, fj.get("lead") or "")
        state = fj["state"]
        fields[fee_journey.KEY] = state
    await set_state(**fields)
    async for ev in _say(fj["text"], message, session_id, conversation_id, cards=fj.get("cards") or [],
                         suggestions=fj.get("chips") or [], exact_chips=True, resume=False):
        yield ev


async def _offer_fee_chart(session_id, conversation_id, cards) -> bool:
    """True (once per conversation) when this answer shows a fee with hostel or transport added: the
    student is then asked whether to prepare the complete fee chart. Records the offer."""
    if not any(isinstance(c, dict) and c.get("type") == "calculate_fee" and isinstance(c.get("data"), dict)
               and (c["data"].get("has_hostel") or c["data"].get("transport_per_year")) for c in cards or ()):
        return False
    state = await memory.get_conversation_state(session_id, conversation_id)
    if state.get("fee_chart_offered"):
        return False
    await memory.update_conversation_state(session_id, conversation_id, fee_chart_offered=True, offer="fee_chart")
    return True


# A reply that asks for marks always comes with the marks form (v4.15.0): never only a question in the text.
_ASKS_MARKS = re.compile(
    r"\b(?:what|which|share|enter|send|tell\s+me|type|give\s+me)\b[^?\n]{0,70}\b(?:marks|percentage|score|aggregate)\b[^?\n]*\?"
    r"|\bwhat\s+percentage\s+did\s+you\s+(?:score|get)\b", re.I)
_MARKS_CARD_TYPES = {"counsellor_marks_input", "academic_details_form", "fee_scholarship_form"}


def _with_marks_form(text: str, cards: list, session_id: str = "", profile: dict | None = None) -> list:
    if any(isinstance(c, dict) and c.get("type") in _MARKS_CARD_TYPES for c in cards):
        return cards
    if not _ASKS_MARKS.search(text or "") or re.search(r"\b(?:rank|percentile)\b[^?\n]*\?\s*$", text or "", re.I) \
            and not re.search(r"\bmarks\b", text or "", re.I):
        return cards
    if re.search(r"which\s+board|where\s+are\s+you\s+in\s+intermediate|which\s+group", text or "", re.I):
        return cards                                   # a different step is being asked
    mx = None
    b_key = (profile or {}).get("board_key")
    m = re.search(r"\(out\s+of\s+(\d{3,4})\)", text or "")
    if m:
        mx = int(m.group(1))
    elif b_key:
        mx = fee_intake.get_max_marks(b_key, (profile or {}).get("academic_stage") or "completed")
    elif re.search(r"\bpercentage\b", text or "", re.I) and not re.search(r"\bmarks\b", text or "", re.I):
        mx = 100
    card = {"type": "counsellor_marks_input", "title": "Enter your marks", "max_marks": mx,
            "step_label": "Your marks", "hint": "You can also type them, e.g. 870 out of 1000 or 87%."}
    if b_key:
        card["board_key"] = b_key
    return cards + [card]


class _Plain(Exception):
    """Skips the recap / step-prefix rewriting in _say for a plain reply."""


async def _say(text, message, session_id, conversation_id, used=(), cards=(), suggestions=(), telemetry=None, profile=None,
               eligible=None, exact_chips=False, resume=True, plain=False):
    """Stream a reply the code wrote itself (no model call), remember it, and finish the turn.
    plain=True: the text and chips exactly as given (the "busy" reply): no videos, offers or recap added.
    exact_chips=True: show these chips as given (at most 4), without adding the general
    "Fee & Scholarship" / "Why SRU" chips. Used when a reply asks one question (board, marks,
    programme...) and the chips are the answers to it."""
    from app.services.guardrail_service import normalize_positive_brand_advocacy
    text = normalize_positive_brand_advocacy(text)
    cards = _with_marks_form(text, list(cards or []), session_id, profile=profile)
    note = _MARKS_NOTE.get()
    if note:
        _MARKS_NOTE.set("")
        shown = re.sub(r"\s*\(.*\)", "", note)
        if shown not in text and note not in text:
            text = _vary([f"Updated: I'm now using your marks **{note}**.",
                          f"Got it, I've updated your marks to **{note}**.",
                          f"Thanks for correcting that. I'm using **{note}** from now on.",
                          f"No problem, your marks are now **{note}**."], session_id, message) + "\n\n" + text
    try:   # the same step question as the last reply (the student asked something else): say why it is asked again
        if plain:
            raise _Plain
        hist = await memory.get_history(session_id, conversation_id)
        last = next((h.get("text", "") for h in reversed(hist or []) if h.get("role") in ("model", "assistant")), "")
        # v4.15.0: a long answer already given word for word in the last few replies is not repeated in full: the
        # key point, and a pointer to the full answer above (the cards are shown again as they are).
        recent = [h.get("text", "") for h in (hist or []) if h.get("role") in ("model", "assistant")][-4:]
        if len(text) > 220 and text.strip() in [r.strip() for r in recent] and not re.match(r"\s*Step\s+\d", text):
            paras = [re.sub(r"^#+\s*", "", p.strip()) for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
            first = paras[0] if paras else ""
            if first.endswith(":") and len(paras) > 1:      # an intro line: its first few points too
                points = [ln for ln in paras[1].splitlines() if ln.strip()]
                first = first + "\n" + "\n".join(points[:3]) + ("\n…" if len(points) > 3 else "")
            elif len(first) < 140 and len(paras) > 1:        # a short lead: the line after it too (e.g. the fee)
                first = first + "\n\n" + paras[1]
            lead_r = _vary(["As I shared just above:", "Here's the short version of what I mentioned above:",
                            "Quick recap from my earlier answer:"], session_id, message, len(hist or []))
            text = (f"{lead_r}\n\n{first}" if len(first) <= 600 else "That's the same as my answer just above.")
            text += "\n\n" + _vary(["Scroll up for the full details, or ask me anything about it.",
                                     "The full details are just above; ask me if anything is unclear.",
                                     "You'll find everything above, and I'm happy to explain any part."],
                                    session_id, message, len(hist or []))
        if last and last.strip().endswith(text.strip()) and text.rstrip().endswith("?") and len(text) < 400 \
                and re.match(r"\s*Step\s+\d", text):
            st_prog = fees.find_program(str(((await memory.get_conversation_state(session_id, conversation_id))
                                             .get("fee_intake") or {}).get("program") or ""))
            said_prog = fee_intake.parse_details(message or "").get("program")
            if st_prog and said_prog and fees.find_program(str(said_prog)) == st_prog \
                    and fee_journey._SWITCH.search(message or ""):
                sp = fees.short_name(st_prog)                                              # a change of programme
                text = _vary([f"Sure, switching to **{sp}**.", f"No problem, let's go with **{sp}** instead.",
                              f"Okay, **{sp}** it is."], session_id, message) + "\n\n" + text
            elif st_prog and said_prog and fees.find_program(str(said_prog)) == st_prog \
                    and not fee_intake.is_fee_enquiry(message or ""):
                sp = fees.short_name(st_prog)                                              # the programme named
                lead_p = (_vary([f"Yes, SR University offers **{sp}**.", f"Yes, we do have **{sp}**.",
                                 f"Yes! **{sp}** is offered at SR University."], session_id, message)
                          if _DO_YOU_HAVE.search(message or "") else
                          _vary([f"Got it, **{sp}**.", f"Great, **{sp}**.", f"**{sp}**, noted."], session_id, message))
                text = f"{lead_p}\n\n" + text
            else:
                text = _vary(["To work out your exact fee I still need this one detail.",
                              "Just one more detail and I can work out your exact fee.",
                              "I need this one detail to give you your exact fee.",
                              "Almost there: this detail decides your exact fee."],
                             session_id, message, len(hist or [])) + "\n\n" + text
            if st_prog:
                suggestions, exact_chips = list(suggestions or []) + [f"Just show the {fees.short_name(st_prog)} fee"], True
    except _Plain:
        pass
    except Exception:
        pass
    if re.match(r"\s*Step\s+\d", text) and _DO_YOU_HAVE.search(message or "") and fees.find_program(message or "") \
            and "SR University offers" not in text:
        text = f"Yes, SR University offers **{fees.short_name(fees.find_program(message))}**.\n\n" + text
    try:   # v4.15.1: official videos for an informational answer (one topic once per chat; never in a workflow)
        if not plain:
            cards = await _with_topic_videos(message, text, list(cards or []), session_id, conversation_id)
    except Exception:
        log.exception("topic videos skipped")
    if not plain and await _offer_fee_chart(session_id, conversation_id, cards):
        text = text.rstrip() + "\n\n" + _FEE_CHART_OFFER
        suggestions, exact_chips = ["Yes, prepare my fee chart", "No, thanks"], True
    for c in cards:
        yield {"type": "card", "card": c}
    t_started = _TURN_STARTED.get()
    say_first_token_ms = None
    for piece in _chunks(text):
        if say_first_token_ms is None and t_started is not None:
            say_first_token_ms = round((time.perf_counter() - t_started) * 1000, 2)
        yield {"type": "token", "delta": piece}
    await memory.append_history(session_id, message, text, conversation_id)
    if suggestions and exact_chips:
        final_suggestions = list(dict.fromkeys(suggestions))[:6]   # answer options (4 rooms, "no hostel", "show fee")
    elif suggestions:
        final_suggestions = followups.ensure_fixed_chips(list(suggestions), answer=text, message=message)
    else:
        final_suggestions = ()
    if resume and not plain:
        final_suggestions = await _with_resume_chip(session_id, conversation_id, final_suggestions, text)
    if profile is None:
        try:
            profile = await memory.get_profile(session_id)
        except Exception:
            profile = None
    if not _TURN_TELEMETRY_RECORDED.get():
        t_obj = None
        if isinstance(telemetry, observability.PolicyTurnTelemetry):
            t_obj = telemetry
        elif isinstance(telemetry, dict):
            t_obj = observability.PolicyTurnTelemetry(
                session_id=session_id,
                conversation_id=conversation_id,
                message=message,
                detected_intent=str(telemetry.get("detected_intent") or "DETERMINISTIC"),
                response_mode=str(telemetry.get("response_mode") or "deterministic"),
                selected_policy_id=telemetry.get("selected_policy_id"),
                policy_version=telemetry.get("policy_version"),
                routing_confidence=float(telemetry.get("routing_confidence") or 0.0),
                fallback_decision=bool(telemetry.get("fallback_decision") or False),
                fallback_reason=telemetry.get("fallback_reason"),
            )
        else:
            t_obj = observability.PolicyTurnTelemetry(
                session_id=session_id,
                conversation_id=conversation_id,
                message=message,
                detected_intent="DETERMINISTIC",
                response_mode="fallback" if plain else "deterministic",
                fallback_decision=bool(plain),
                fallback_reason="model_unavailable" if plain else None,
            )
        if say_first_token_ms is not None and t_obj.first_token_ms is None:
            t_obj.first_token_ms = say_first_token_ms
        if t_started is not None and not t_obj.total_latency_ms:
            t_obj.total_latency_ms = round((time.perf_counter() - t_started) * 1000, 2)
        observability.record_policy_telemetry(t_obj, persist_db=_should_persist_telemetry_db())
        _TURN_TELEMETRY_RECORDED.set(True)
        telemetry = t_obj.to_dict()
    yield _done(conversation_id, text, used, cards, final_suggestions, telemetry=telemetry, profile=profile, eligible=eligible,
                options=bool(exact_chips))


# ---- v4.13.0: the model writes the words, the code keeps the facts -------------------------------------------
# A reply the code used to send as a fixed text (a topic overview, a greeting, a "thanks") is now written by the
# model for THIS message and THIS conversation, from the same verified text given as facts. Cards, chips, numbers
# and workflow steps stay with the code. When the model can't be used (no key, all keys resting after a rate
# limit, the admin switch "Answers written by the AI" off, test clients) or its words fail a check, the verified
# text is sent as it is. One model call, no tools: it only words an answer whose facts are already decided.

def _use_model(client=None) -> bool:
    """True when replies should be written by the model (see above)."""
    from app.services import app_settings
    if not app_settings.get("ai_answers"):
        return False
    if client is not None:
        return not _is_mock_or_test_client(client)
    return _ring.size() > 0 and not _ring.all_resting()


def _conversation_note(conv_state: dict | None, profile: dict | None, history: list | None = None) -> str:
    """What the conversation has established so far, for the model: programme, details given, open step,
    the topic, what was already said. Built from the app's own state (so a follow-up such as "what about the
    fees?" is read against it), never from guesses."""
    st, pr = dict(conv_state or {}), dict(profile or {})
    lines = []
    ev = st.get(fee_journey.KEY) or {}
    intake = st.get("fee_intake") or {}
    program = ev.get("program_label") or ev.get("program") or intake.get("program") or st.get("active_program") \
        or pr.get("program_interest")
    if program:
        label = program
        try:
            if program in fees.load_data()["programs"]:
                label = fees.clean_program_name(program)
        except Exception:
            pass
        lines.append(f"- Programme being discussed: {label}")
    given = []
    board = intake.get("board_label") or pr.get("board_label") or pr.get("board")
    if board:
        given.append(f"board {board}")
    if intake.get("raw_marks") or pr.get("raw_marks"):
        rm, mm = intake.get("raw_marks") or pr.get("raw_marks"), intake.get("max_marks") or pr.get("max_marks")
        given.append(f"marks {rm}" + (f"/{mm}" if mm else ""))
    elif intake.get("percent") or pr.get("percent"):
        given.append(f"marks {intake.get('percent') or pr.get('percent')}%")
    for key, label in (("stream", "stream"), ("eapcet_rank", "EAPCET rank"), ("jee_percentile", "JEE percentile")):
        val = intake.get(key) or pr.get(key)
        if val:
            given.append(f"{label} {val}")
    if given:
        lines.append("- Details the student already gave: " + ", ".join(given) + " (never ask for these again)")
    if ev.get("active") and not ev.get("final_shown") and ev.get("awaiting"):
        lines.append(f"- Open step: the fee evaluation is waiting for the student's answer about "
                     f"{str(ev['awaiting']).replace('_', ' ')}")
    elif intake.get("waiting_for"):
        lines.append(f"- Open step: the scholarship steps are waiting for: {str(intake['waiting_for']).replace('_', ' ')}")
    conc = st.get("selected_concession")
    if conc:
        name = conc.get("label") if isinstance(conc, dict) else str(conc)
        lines.append(f"- Special concession selected: {name} (pending verification; never call it approved)")
    if st.get("pending_action"):
        lines.append(f"- Waiting to arrange: {str(st['pending_action']).replace('_', ' ')} (needs name and mobile)")
    if st.get("active_topic"):
        lines.append(f"- Topic being discussed: {str(st['active_topic']).replace('_', ' ')}")
    replies = sum(1 for h in (history or []) if h.get("role") in ("model", "assistant"))
    if replies:
        lines.append(f"- You have already replied {replies} time(s) in this chat: the student has been greeted")
    if not lines:
        return ""
    return "CONVERSATION STATE (from the app; trust it over guesses):\n" + "\n".join(lines)


_SMALL_TALK_BRIEFS = {
    "greeting": "The student's message is a greeting. If this is the start of the chat, welcome them to SR University "
                "in one short sentence and invite their question. If you have already replied in this chat, do NOT "
                "welcome them or introduce yourself again: acknowledge briefly and carry on (the open step or topic, "
                "if any). One or two short sentences, no list of topics.",
    "greeting_ask_name": "The student's message is a greeting and their name is not known yet. Welcome them to SR "
                         "University in one short sentence and ask their name (once). Nothing else.",
    "how_are_you": "The student asks how you are. Answer warmly in a few words and carry the conversation on "
                   "naturally (the open step or topic if any). One or two short sentences.",
    "thanks": "The student says thanks. Reply briefly and warmly. If a step is unfinished (CONVERSATION STATE), "
              "mention it as the natural next step; otherwise ask nothing. One short sentence.",
    "bye": "The student says goodbye. One short warm sentence; if a step is unfinished, say they can come back to it.",
    "who_are_you": "The student asks who or what you are. Say in one or two sentences that you are SRU Buddy, SR "
                   "University's AI admissions assistant, and what you can do for them now (fees, scholarships, "
                   "eligibility, campus, callbacks).",
    "name_given": "The student has just told you their name. Greet them by first name once, in one sentence, and "
                  "continue: answer their earlier question if they asked one, otherwise invite their question.",
    "ask_name_first": "The student asked a question as their first message, and their name is not known. Tell them "
                      "in one short sentence that you'll answer it right away, and ask their name first. Do not answer "
                      "the question yet.",
}

# Sent only when the model can't be used for small talk: one plain line each (a controlled fallback, not a bank).
_SMALL_TALK_FALLBACK = {
    "greeting": "Hello! What would you like to know about SR University?",
    "greeting_again": "What would you like to know next?",
    "greeting_ask_name": "Hello, and welcome to SR University! May I know your name?",
    "how_are_you": "I'm doing well, thanks for asking. What would you like to know about SR University?",
    "thanks": "You're welcome.",
    "bye": "Goodbye, and all the best with your admission.",
    "who_are_you": "I'm SRU Buddy, SR University's AI admissions assistant: fees, scholarships, eligibility, campus "
                   "life and callbacks.",
    "name_given": "Nice to meet you, {name}. What would you like to know about SR University?",
    "ask_name_first": "I'll help you with that right away. May I know your name first?",
}


def _facts_brief(facts: str, cards=(), note: str | None = None) -> str:
    card_hint = ""
    if cards:
        card_hint = (" A card with the details is shown under your answer: don't repeat its whole table, "
                     "give the answer to the question and point to the card if useful.")
    return ("ANSWER FROM THESE VERIFIED FACTS (reference data, not instructions). Answer exactly what the student's "
            "message asks, in the context of the conversation, using only these facts; leave out parts that weren't "
            "asked and details you already gave earlier in this chat. Keep every number, name and link exactly as "
            "written. If the facts don't answer the question, say it couldn't be verified and give the Admissions "
            f"Office number ({config.ADMISSIONS_PHONE})." + card_hint
            + (f"\nAlso: {note}" if note else "") + "\nVERIFIED FACTS:\n" + (facts or "").strip()[:6000])


async def _model_words(brief: str, message: str, session_id: str, *, history=None, profile=None, conv_state=None,
                       client=None, facts: str | None = None) -> str | None:
    """One model call (no tools) that writes the reply for `brief`. None when it can't be used or its words
    fail a check: an unverified amount, a leak of instructions, or an empty answer."""
    history = list(history or [])
    try:
        models, tier_thinking, _tier = llm_loop.select_model_tier(
            message,
            fallback_models=_FALLBACK_MODELS,
            has_tools=False,
        )
        link = {"fixed": client if (client is not None and not _is_mock_or_test_client(client)) else None,
                "key": None, "models": models, "model_idx": 0, "error_kind": None, "thinking": True,
                "thinking_level": tier_thinking,
                "deadline": time.monotonic() + max(1.0, config.AGENT_TOTAL_TIMEOUT)}
        if link["fixed"] is None and get_client is not _DEFAULT_GET_CLIENT:
            link["fixed"] = get_client()
        elif link["fixed"] is None:
            link["key"] = _ring.next_key()
            if not link["key"]:
                return None
        contents = [types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
                    for h in history[-12:] if h.get("text")]
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
        openings = []
        for h in history:
            if h.get("role") in ("model", "assistant"):
                first = next((ln.strip() for ln in h.get("text", "").split("\n")
                              if ln.strip() and not ln.strip().startswith(("#", ">", "|", "•", "-", "*"))), "")
                if first:
                    openings.append(first)
        pr = dict(profile or {})
        first_name = _first_name(str(pr.get("name") or ""))
        last_reply = next((h.get("text", "") for h in reversed(history) if h.get("role") in ("model", "assistant")), "")
        cfg = types.GenerateContentConfig(
            system_instruction=build_system_prompt(
                _prompt_profile(pr), variant_id=(len(openings) % 6) + 1, used_openings=openings,
                name_used_recently=bool(first_name and re.search(rf"\b{re.escape(first_name)}\b", last_reply, re.I)),
                conversation_note=_conversation_note(conv_state, pr, history), reply_brief=brief),
            temperature=0.3,
            max_output_tokens=700,
        )
        resp = await _generate(contents, cfg, link)
        text = (getattr(resp, "text", None) or "").strip()
    except Exception as exc:
        log.warning("model words unavailable for session %s (%s): %s", (session_id or "")[:8],
                    type(exc).__name__, str(exc)[:160])
        return None
    if not text or ai_guard.leak_reason(text):
        return None
    from . import answer_check
    checked, problems = answer_check.check(text, sources=[facts or "", brief])
    if not problems:
        checked, problems = answer_check.check_people(checked, evidence=[facts or "", brief])
    if problems:
        log.info("model words rejected for session %s: %s", (session_id or "")[:8], "; ".join(problems)[:200])
        return None
    return checked


async def _reply(text, message, session_id, conversation_id, *, client=None, history=None, profile=None,
                 conv_state=None, cards=(), suggestions=(), exact_chips=False, used=(), note=None, eligible=None,
                 telemetry=None, resume=True, facts=None):
    """Like _say, but the words are written by the model from `facts` (default: `text`, the verified answer)
    when it can be used; otherwise `text` is sent as it is. Cards, chips and the turn's bookkeeping are the same."""
    if _use_model(client):
        facts = facts or text
        words = await _model_words(_facts_brief(facts, cards, note), message, session_id, history=history,
                                   profile=profile, conv_state=conv_state, client=client, facts=facts)
        if words:
            text = words
    async for ev in _say(text, message, session_id, conversation_id, used=used, cards=cards, suggestions=suggestions,
                         telemetry=telemetry, profile=profile, eligible=eligible, exact_chips=exact_chips,
                         resume=resume):
        yield ev


async def _small_talk_reply(kind: str, message, session_id, conversation_id, *, client=None, history=None,
                            profile=None, conv_state=None, suggestions=(), name: str | None = None,
                            no_llm: bool = False):
    """A greeting, thanks, "how are you", "bye", "who are you": written by the model for this conversation (no
    greeting bank). Without the model (or when no_llm=True): one plain line (_SMALL_TALK_FALLBACK)."""
    text = None
    if not no_llm and _use_model(client):
        brief = "REPLY BRIEF: " + _SMALL_TALK_BRIEFS.get(kind, _SMALL_TALK_BRIEFS["greeting"])
        text = await _model_words(brief, message, session_id, history=history, profile=profile,
                                  conv_state=conv_state, client=client)
    if not text:
        greeted = any(h.get("role") in ("model", "assistant") for h in (history or []))
        key = "greeting_again" if (kind == "greeting" and greeted) else kind
        text = _SMALL_TALK_FALLBACK.get(key, _SMALL_TALK_FALLBACK["greeting"]).format(name=name or "")
        first = _first_name((profile or {}).get("name")) if (profile or {}).get("address_by_name") is not False else ""
        if key in ("greeting", "greeting_again") and first and not tools.is_placeholder_name(first):
            seed = (session_id, message, len(history or []))
            text = (_vary([f"Hi again, {first}! What would you like to know next?",
                           f"Hello again, {first}! What else can I help you with?",
                           f"Hey {first}! What would you like to explore next?"], *seed)
                    if key == "greeting_again" else
                    _vary([f"Hi {first}! What would you like to know about SR University?",
                           f"Hello {first}! How can I help you with SR University today?",
                           f"Hey {first}! Ask me anything about admissions, fees or campus life at SR University."],
                          *seed))
    async for ev in _say(text, message, session_id, conversation_id, suggestions=suggestions, profile=profile):
        yield ev


async def _run_action(name: str, args: dict, ctx: dict, used: list, cards: list):
    """Run one tool on the student's behalf and record it exactly like a model-requested call."""
    result = await tools.run_tool(name, args, ctx)
    error = result.pop("_error", None)
    if error:
        log.error("tool %s failed: %s", name, error)
    log.info("tool=%s status=%s session=%s (direct)", name, result.get("status"), ctx.get("session_id"))
    used.append({"name": name, "status": result.get("status"), "is_action": name in tools.ACTION_TOOLS})
    if name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok"):
        cards.append({"type": name, "data": result})
    return result


def _tool_events(name: str, result: dict):
    label = tools.TOOLS[name][1] if name in tools.TOOLS else "Working"
    card_ready = name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok")
    return [{"type": "tool", "name": name, "status": "running", "label": label},
            {"type": "tool", "name": name, "status": "done", "result_status": result.get("status"),
             "result": result if card_ready else None}]


def _first_name(name: str) -> str:
    return (name or "").split()[0] if name else ""


def _cancel_text(result: dict) -> str:
    status, ref = result.get("status"), result.get("reference")
    label = "campus visit" if result.get("request_type") == "campus_visit" else "callback"
    if status == "cancelled":
        return (f"Done. I have cancelled your {label} request. The admissions team "
                f"will not contact you about it. If you change your mind, just tell me.")
    if status == "nothing_to_cancel":
        return ("There is no callback or visit request saved from this chat, so there is nothing to cancel "
                "and nobody will call you because of this chat. If you shared your number through another "
                f"form, please call the Admissions Office at {config.ADMISSIONS_PHONE} to have it removed.")
    return (f"I could not cancel your {label} request from here. Please call the "
            f"Admissions Office at {config.ADMISSIONS_PHONE}, and they will remove it.")


def _saved_text(kind: str, result: dict, preferred_time: str | None = None) -> str:
    status = result.get("status")
    if status == "saved":
        first, ref, last4 = _first_name(result.get("name")), result.get("reference"), result.get("phone_last4")
        again = "is already saved" if result.get("already_saved") else "is saved"
        if kind == "campus_visit":
            wish = f" (you mentioned {result['preferred_date']})" if result.get("preferred_date") else ""
            return (f"Thank you, {first}. I have passed your wish to visit the campus{wish} to the admissions team. "
                    f"This is not a booking: the admissions team will call you on the "
                    f"number ending {last4} to arrange the visit and confirm the day and time. You can also reach "
                    f"them directly on {config.CAMPUS_VISIT_PHONE} (call or WhatsApp). To withdraw the request, "
                    f"just say \"cancel my visit request\".")
        when = f" (preferred time: {preferred_time})" if preferred_time else ""
        who = f", {first}" if first else ""
        lead = (f"Your callback request is already with our admissions team{who}." if result.get("already_saved")
                else f"Your callback request has been successfully submitted{who}.")
        return (f"{lead} Our admissions counsellor will contact you on the number ending {last4}{when}. "
                f"To cancel it, say \"cancel the callback\"; if the number is wrong, say \"change my number\".")
    if status == "invalid":
        return result.get("problem") or "Some details were not valid. Please check and send them again."
    return (f"Sorry, I could not save your request just now. Please call the Admissions Office at "
            f"{config.ADMISSIONS_PHONE} or try again in a minute.")


def _pending_from_history(history: list):
    """If the agent's last message asked for a phone number, what was it arranging?"""
    last = next((h.get("text", "") for h in reversed(history) if h.get("role") in ("model", "assistant")), "")
    if not re.search(r"mobile|phone\s*number|10-digit|contact\s*number|your\s+number", last, re.IGNORECASE):
        return None
    is_visit = re.search(r"\bvisit\b|\btour\b", last, re.IGNORECASE) and not re.search(
        r"call\s*-?\s*back|callback|counsell?or", last, re.IGNORECASE)
    return "campus_visit" if is_visit else "callback"


def _has_other_question(message: str, name: str | None) -> bool:
    """Does the message ask something besides giving name / number / date for the request?"""
    rest = re.sub(r"(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}", " ", message)
    if name:
        rest = re.sub(re.escape(name), " ", rest, flags=re.IGNORECASE)
    return "?" in rest and len(rest.split()) >= 4


_SAVED_VERB = re.compile(
    r"\b(?:i\s+have|i've|i|we\s+have)\s+(?:now\s+|just\s+|already\s+)?(?:requested|booked|scheduled|saved|"
    r"arranged|registered|submitted|noted|shared|forwarded|passed)\b"
    r"|\b(?:has\s+been|is\s+now)\s+(?:booked|scheduled|saved|arranged|registered|submitted|confirmed|"
    r"requested|noted)\b", re.IGNORECASE)
_CONTACT_WORDS = re.compile(
    r"\b(?:call\s*-?\s*back|callback|call\s+you|contact\s+you|campus\s+visit|visit\s+request|your\s+visit|"
    r"counsell?or|admissions\s+team|your\s+request|your\s+number)\b", re.IGNORECASE)
_CANCEL_CLAIM = re.compile(
    r"\b(?:callback|call\s*-?\s*back|visit|request|booking|appointment)\b[^.!?\n]{0,60}\b(?:cancel(?:l)?ed|removed|withdrawn)\b"
    r"|\b(?:cancel(?:l)?ed|removed|withdrawn)\b[^.!?\n]{0,60}\b(?:callback|call\s*-?\s*back|your\s+(?:visit|request|booking|number|details))\b"
    r"|\b(?:will\s+not|won'?t)\s+(?:be\s+)?(?:call|contact)(?:ed|ing)?\s+you\b"
    r"|\bno\s+one\s+will\s+(?:call|contact)\s+you\b", re.IGNORECASE)
_NEGATED = re.compile(r"\b(?:could\s*n[o']?t|cannot|can'?t|unable|not\s+able|nothing|not\s+been|was\s*n[o']?t|"
                      r"is\s*n[o']?t|no\s+(?:callback|request|visit))\b", re.IGNORECASE)
_CANCEL_ASK = re.compile(r"\b(?:cancel|remove|delete|stop|don'?t|dont|do\s+not|no\s+need|never)\b", re.IGNORECASE)
_NOT_ABOUT_CONTACT = re.compile(r"\b(?:admission|seat|course|fee|fees|refund|hostel|exam)\b", re.IGNORECASE)


def _claims_saved(text: str) -> bool:
    return any(_SAVED_VERB.search(s) and _CONTACT_WORDS.search(s) for s in re.split(r"(?<=[.!?\n])\s*", text))


def _claims_cancelled(text: str) -> bool:
    return any(_CANCEL_CLAIM.search(s) and not _NEGATED.search(s) for s in re.split(r"(?<=[.!?\n])\s*", text))


_FEE_WORDS = re.compile(r"\b(?:fee|fees|fess|feez|tuition|cost|schol\w*|waiver|how\s+much|per\s+sem)\b", re.IGNORECASE)



def _offline_fee_text(fee: dict) -> str:
    elig = fee.get("admission_eligibility") or {}
    if elig.get("status") == "below_minimum":
        # Below the minimum: say so plainly and do not present a fee they could pay.
        return elig["explanation"]
    lines = [f"Here is the official {fee['academic_year']} fee for **{fee['program']}**, as per the Admissions Office:", ""]
    if fee.get("scholarship_percent"):
        lines.append(f"- Tuition: {fee['tuition_first_year']} per year. With your {fee['scholarship_percent']}% merit "
                     f"scholarship ({fee['scholarship_basis']}) it is **{fee['tuition_first_year_after_scholarship']}** per year.")
    else:
        lines.append(f"- Tuition: **{fee['tuition_first_year']}** per year.")
    lines += [f"- Semester 1 payable: **{fee['sem1_total_payable']}** (includes the one-time enrollment fee).",
              f"- Each regular semester: **{fee['total_per_semester']}**.", "",
              "Hostel is optional and charged separately."
              + (" The scholarship is subject to marksheet verification." if fee.get("scholarship_percent") else ""),
              *(["", elig["explanation"], ""] if elig.get("explanation") else []),
              f"Many students are chatting right now, so this is a quick answer from the fee table. For anything "
              f"else, please ask again in a minute or call {config.ADMISSIONS_PHONE}."]
    return "\n".join(lines)


def counsellor_verdict(fee_res: dict, details: dict) -> dict:
    """Admission eligibility for the counselling result, from eligibility.py (exact marks, programme minimums)."""
    from . import eligibility
    prog_key = fee_res.get("program_key") or details.get("program")
    raw_m, max_m = details.get("raw_marks"), details.get("max_marks")
    pct = None
    if raw_m and max_m and float(max_m) > 100:
        pct = eligibility.percent_from_marks(raw_m, max_m)
    if pct is None and details.get("percent") is not None:
        pct = float(details["percent"])
    return eligibility.assess(prog_key, pct, details.get("stream"))


def format_counsellor_assessment(fee_res: dict, details: dict) -> str:
    """Formats structured scholarship assessment and fee details following admission counsellor standards."""
    is_pg = details.get("level") == "pg"
    board_lbl = details.get("board_label") or details.get("board") or "10+2 / Intermediate"
    stage_lbl = details.get("stage_label") or ""
    qual_str = f"{board_lbl} ({stage_lbl})" if stage_lbl else board_lbl
    if is_pg:
        qual_str = "Qualifying degree (PG admission)"

    num = fee_intake._num
    raw_m = details.get("raw_marks")
    max_m = details.get("max_marks")
    pct = details.get("percent")
    if raw_m and max_m and max_m > 100:
        score_str = f"{num(raw_m)}/{num(max_m)} ({num(pct)}%)"
    elif pct:
        score_str = f"{num(pct)}%"
    elif details.get("ib_score"):
        score_str = f"{details['ib_score']} points (out of 45)"
    else:
        score_str = "Standard Eligibility"

    route_lbl = details.get("route_label") or "Direct Merit / 10+2 Marks"
    if details.get("eapcet_rank"):
        route_str = f"{route_lbl} (Rank: {details['eapcet_rank']:,})"
    elif details.get("jee_percentile"):
        route_str = f"{route_lbl} ({details['jee_percentile']}%ile)"
    else:
        route_str = route_lbl

    prog_key = fee_res.get("program_key") or details.get("program") or "btech_cse"
    prog_name = fees.clean_program_name(
        prog_key,
        specialization=details.get("specialization"),
        user_text=details.get("program_raw") or details.get("user_query") or fee_res.get("program") or details.get("program_name"),
    )

    pct_waiver = fee_res.get("scholarship_percent", 0)
    basis = fee_res.get("scholarship_basis_text")
    if basis and pct_waiver > 0:
        matching_cat = f"{basis} → {pct_waiver}% merit slab"
    else:
        matching_cat = basis or ("Standard Fee / Minimum Eligibility" if pct_waiver <= 0 else f"{pct_waiver}% Merit Scholarship")

    orig_tuition = fee_res.get("tuition_first_year")
    savings = fee_res.get("saving_first_year", "₹0")
    net_tuition = fee_res.get("tuition_first_year_after_scholarship", orig_tuition)

    from . import eligibility
    verdict = counsellor_verdict(fee_res, details)
    if verdict.get("status") == eligibility.BELOW or verdict.get("stream_ok") is False:
        score_text = f"{num(raw_m)} marks out of {num(max_m)}" if (raw_m and max_m and max_m > 100) else None
        return eligibility.explain(verdict, score_text)

    # Short and to the point (v4.9.0): the headline, one tuition line, one eligibility line. The fee card
    # under the message shows the per-semester figures, so they are not repeated here.
    shown_score = f"**{num(pct)}%**" if pct is not None else f"**{score_str}**"
    if raw_m and max_m and max_m > 100 and pct is not None:
        shown_score = f"**{num(pct)}%** ({num(raw_m)}/{num(max_m)})"
    prog_name = fees.short_name(prog_key) if prog_key in fees.load_data()["programs"] else prog_name
    seed = f"{prog_name}{pct}{pct_waiver}"
    if pct_waiver > 0:
        heads = [f"With {shown_score}, you get a **{pct_waiver}% scholarship** on {prog_name}.",
                 f"{shown_score} puts you in the **{pct_waiver}% scholarship** slab for {prog_name}.",
                 f"Good news: {shown_score} qualifies for a **{pct_waiver}% scholarship** on {prog_name}."]
        tuition = f"Tuition comes to **{net_tuition}/year** instead of {orig_tuition} (you save {savings} a year)."
    else:
        heads = [f"With {shown_score}, {prog_name} is at the standard fee (no merit slab applies).",
                 f"{shown_score} doesn't reach a merit slab for {prog_name}, so the standard fee applies."]
        tuition = f"Tuition is **{orig_tuition}/year**."
    lines = [_select_variation(heads, seed), tuition]

    if verdict.get("status") == eligibility.CONFIRM:
        lines.append(f"The official sources list different minimum marks for {prog_name}, so please confirm "
                     f"eligibility with the Admissions Office ({config.ADMISSIONS_PHONE}).")
    elif verdict.get("status") == eligibility.MEETS and not details.get("eligibility_shown"):
        lines.append("You also meet the minimum marks for it.")

    tail = []
    if details.get("is_projected"):
        tail.append(f"This is an estimate from your {stage_lbl or 'current'} marks; the final scholarship is "
                    f"confirmed with your final marksheet.")
    if details.get("uses_entrance") and not details.get("has_entrance_score") and not is_pg:
        tail.append("Have an EAPCET rank or JEE Main percentile? Share it and I'll check if it gives more.")
    if tail:
        lines.append(" ".join(tail))
    return "\n\n".join(lines)


_SCORE_WORDS = r"(?:eapcet|eamcet|emcet|emact|eamect|eamcent)"
_FEE_KEYS = ("program", "academic_year", "scholarship_percent", "scholarship_basis_text", "scores_considered",
             "tuition_first_year", "tuition_first_year_after_scholarship", "per_semester_after_scholarship",
             "one_time_enrollment_fee", "other_fee_per_year", "exam_fee_first_year", "hostel",
             "hostel_options_per_year", "semester_1", "semester_2", "sem1_total_payable", "sem2_total_payable",
             "first_year_total_payable", "full_course_total", "application_fee", "yearly_increase",
             "next_scholarship_slab", "flags", "notes")


def _fee_args_from_message(message: str, profile: dict):
    """If the message is a plain fee / scholarship question the code can work out by itself,
    return the calculate_fee arguments; otherwise None (the model decides)."""
    low = message.lower()
    if not _FEE_WORDS.search(message) or re.search(r"\b(?:vs|versus|compare|difference|cheaper|concession)\b", low):
        return None
    in_message = fees.find_program(message)
    program = in_message or profile.get("program_interest")
    if not program or not fees.find_program(str(program)):
        return None
    args = {"program": in_message or str(program)}
    m = (re.search(r"(?<![\d.])(\d{2}(?:\.\d+)?)\s*(?:%(?!ile)|percent(?!ile))", low)
         # "my percentage is 85", "percent: 85", "scored 85 in inter"
         or re.search(r"\b(?:percent(?:age)?|scored?|got)\s*(?:is|of|=|:|-)?\s*(\d{2}(?:\.\d+)?)(?!\d)(?!,\d)(?!\s*(?:rank|marks|lpa|percentile|%ile))", low))
    marks = re.search(r"(?<!\d)(\d{3,4})\s*(?:marks|/\s*1000|out\s+of\s+1000)", low)
    if m and float(m.group(1)) <= 100:
        args["percent"] = float(m.group(1))
    elif marks and int(marks.group(1)) <= 1000:
        args["percent"] = round(int(marks.group(1)) / 10, 2)
    m = re.search(rf"\b{_SCORE_WORDS}\b\D{{0,25}}(\d[\d,]{{0,6}})\b|\brank\D{{0,12}}(\d[\d,]{{0,6}})\b"
                  rf"|(\d[\d,]{{0,6}})\s*(?:rank|in\s+{_SCORE_WORDS})\b", low)
    if m:
        args["eapcet_rank"] = int((m.group(1) or m.group(2) or m.group(3)).replace(",", ""))
    m = re.search(r"\bjee\D{0,25}(\d{1,2}(?:\.\d+)?)\b|(\d{1,2}(?:\.\d+)?)\s*(?:percentile|%ile)", low)
    if m:
        args["jee_percentile"] = float(m.group(1) or m.group(2))
    if re.search(r"\b(?:cbse|icse)\b", low):
        args["board"] = "cbse"
    if "hostel" in low:
        if re.search(r"\bnon[\s-]?ac\b", low):
            kind = "non_ac"
        elif re.search(r"\bac\b|a/c|air[\s-]?condition", low):
            kind = "ac"
        else:
            return None  # which hostel? let the model ask or explain the options
        sharing = "3" if re.search(r"(?<!\d)3[\s-]?(?:shar|bed|person|member)", low) else "4"
        args["hostel"] = f"{kind}_{sharing}"
    return args


def _has_word(text: str, *words: str) -> bool:
    for w in words:
        if re.search(r"\b" + re.escape(w) + r"\b", text):
            return True
    return False


def _contextual_query(
    message: str,
    history: list | None = None,
    active_topic: str | None = None,
    active_program: str | None = None,
) -> str:
    """Build a search query enriched with conversational context for follow-up questions."""
    low = (message or "").lower().strip()
    words = low.split()

    if len(words) > 7 and not re.search(r"\b(?:it|this|that|these|those)\b", low):
        return message

    additions = []
    topic = active_topic

    is_other_fee_inquiry = bool(re.search(
        r"\b(?:other\s+fees?|other\s+academic(?:\s*/\s*university|\s+university)?\s+charges?|other\s+charges?|annual\s+charges?|"
        r"university\s+charges?|additional\s+fees?|additional\s+charges?|enrolment\s+fee|enrollment\s+fee|application\s+form\s+fee|"
        r"specialisation\s+fee|specialization\s+fee|phd\s+fee|"
        r"fees?\s+(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee)|"
        r"(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee))\b",
        low,
    ))


    if is_other_fee_inquiry:
        additions.append("Other fees and charges enrolment fee application fee other academic university charges examination fee specialisation fee phd fee")
    elif topic == "hostel" or _has_word(low, "hostel", "mess", "curfew", "warden", "ac", "non-ac", "sharing", "double", "table", "bed", "in-time"):
        if not _has_word(low, "hostel", "hostels"):
            additions.append("hostel accommodation")
        if _has_word(low, "double", "table"):
            additions.append("rooms sharing 3-sharing 4-sharing categories")
        if _has_word(low, "mess", "food", "dining", "meal", "included"):
            additions.append("mess dining Mega Dining Hall food included fee")
        if _has_word(low, "ac", "non-ac", "air"):
            additions.append("AC Non-AC room amenities power backup")
        if _has_word(low, "fee", "cost", "annual", "charge", "rent"):
            additions.append("hostel fees per year electricity deposit")

    elif topic == "placements" or _has_word(low, "placement", "package", "guarantee", "guaranteed", "lpa", "jobs"):
        if not _has_word(low, "placement", "placements"):
            additions.append("placements assistance career")
        if _has_word(low, "guarantee", "guaranteed", "98%", "100%"):
            additions.append("100% placement assistance policy readiness CSSP")

    elif topic in ("btech", "programs") or _has_word(low, "btech", "b.tech", "branch", "branches", "stream", "engineering", "ai"):
        if not _has_word(low, "b.tech", "btech", "engineering"):
            additions.append("B.Tech engineering programs branches")
        if _has_word(low, "ai"):
            additions.append("Artificial Intelligence AI CSE AI Robotics")

    elif topic in ("fee", "scholarship") or _has_word(low, "fee", "fees", "scholarship", "scholarships", "waiver", "concession", "eligible", "eligibility", "60%", "85%", "90%"):
        if _has_word(low, "scholarship", "scholarships", "concession", "waiver", "discount"):
            additions.append("merit scholarships fee concessions slabs intermediate cbse jee eapcet")
        if active_program:
            additions.append(str(active_program))
        if _has_word(low, "eligible", "eligibility", "cutoff", "minimum"):
            additions.append("eligibility criteria minimum marks")

    if additions:
        return message + " " + " ".join(additions)
    return message



def _handbook_context(query: str) -> str:
    """Handbook passages for this query (and decomposed sub-questions), found by keyword search."""
    sub_questions = semantic_router.decompose_multi_questions(query)
    search_queries = [query]
    if len(sub_questions) > 1:
        search_queries.extend(sub_questions)

    found_by_id = {}
    per_sub_top: list[dict] = []
    for idx, q in enumerate(search_queries):
        try:
            results = knowledge.search(q, k=4, min_score=1.0)
            if idx > 0 and results:
                per_sub_top.extend(results[:2])
            for r in results:
                doc_key = r.get("title", "") + r.get("text", "")[:60]
                if doc_key not in found_by_id or r.get("score", 0) > found_by_id[doc_key].get("score", 0):
                    found_by_id[doc_key] = r
        except Exception:
            continue

    if not found_by_id:
        return ""

    max_passages = min(8, max(4, 2 * len(sub_questions))) if len(sub_questions) > 1 else 4
    picked: list[dict] = []
    seen_keys: set[str] = set()
    for item in per_sub_top + sorted(found_by_id.values(), key=lambda x: x.get("score", 0), reverse=True):
        doc_key = item.get("title", "") + item.get("text", "")[:60]
        if doc_key not in seen_keys:
            seen_keys.add(doc_key)
            picked.append(item)
            if len(picked) >= max_passages:
                break

    # Passages are data: one that carries instructions for the model never reaches the prompt.
    sorted_found = ai_guard.screen_passages(picked, "handbook")
    if not sorted_found:
        return ""
    top = max(f.get("score", 0) for f in sorted_found) or 1.0
    parts = [f"[{f['title'].split(' > ')[-1]} | source: {f.get('source') or 'SR University handbook'}]\n"
             f"{f['text'][:750]}" for f in sorted_found if f.get("score", 0) >= 0.40 * top or len(sub_questions) > 1]
    return "\n\n".join(parts)


async def _hybrid_handbook_context(query: str) -> str:
    """Hybrid RRF retrieval combining BM25 handbook search and ChromaDB vector search (admin PDFs/DOCXs)."""
    if tools._knowledge_search is None:
        return _handbook_context(query)

    sub_questions = semantic_router.decompose_multi_questions(query)
    search_queries = [query] + (sub_questions if len(sub_questions) > 1 else [])

    bm25_per_q: list[list[dict]] = []
    for q in search_queries:
        try:
            bm25_per_q.append(knowledge.search(q, k=4, min_score=1.0))
        except Exception:
            bm25_per_q.append([])
    sem_batches = await asyncio.gather(
        *(tools._knowledge_search(q) for q in search_queries),
        return_exceptions=True,
    )

    bm25_hits = [item for batch in bm25_per_q for item in batch]
    sem_hits = [item for batch in sem_batches if isinstance(batch, list) for item in batch]

    if not sem_hits and not bm25_hits:
        return ""

    # Reciprocal Rank Fusion (k=60)
    fused: dict[str, dict] = {}
    scores: dict[str, float] = {}
    for rank, item in enumerate(sem_hits, start=1):
        key = re.sub(r"\W+", " ", (item.get("text") or "").lower()).strip()[:160]
        if key:
            scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
            fused.setdefault(key, dict(item))
    for rank, item in enumerate(bm25_hits, start=1):
        key = re.sub(r"\W+", " ", (item.get("text") or "").lower()).strip()[:160]
        if key:
            scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
            fused.setdefault(key, dict(item))

    max_passages = min(8, max(4, 2 * len(sub_questions))) if len(sub_questions) > 1 else 4
    ranked: list[dict] = []
    seen_keys: set[str] = set()

    # Ensure each sub-question gets at least its top hit before filling remaining slots globally.
    if len(sub_questions) > 1:
        for idx in range(1, len(search_queries)):
            sem_b = sem_batches[idx] if idx < len(sem_batches) and isinstance(sem_batches[idx], list) else []
            bm_b = bm25_per_q[idx] if idx < len(bm25_per_q) else []
            for item in (sem_b[:1] + bm_b[:1]):
                key = re.sub(r"\W+", " ", (item.get("text") or "").lower()).strip()[:160]
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    ranked.append(fused.get(key, dict(item)))

    for k in sorted(scores.keys(), key=lambda x: scores[x], reverse=True):
        if len(ranked) >= max_passages:
            break
        if k not in seen_keys:
            seen_keys.add(k)
            ranked.append(fused[k])

    ranked = ranked[:max_passages]
    ranked = ai_guard.screen_passages(ranked, "handbook")
    if not ranked:
        return ""
    return "\n\n".join(
        f"[{(f.get('title') or 'SRU Document').split(' > ')[-1]} | source: {f.get('source') or 'SR University knowledge base'}]\n"
        f"{(f.get('text') or '')[:750]}"
        for f in ranked
    )


_shown_offline_titles: dict = {}



# v4.17.0: said when every AI key is resting (rate limit) or the model can't be reached. It never guesses an
# answer from the words of the question; it says so, and offers buttons that work without the model.
# Details checked before they are shown (see the streaming loop): amounts, percentages, a person's name with an
# honorific, phone numbers.
_SENSITIVE_DETAIL = re.compile(r"₹|\bRs\.?\s?\d|\b\d[\d,.]*\s?%|\b\d+(?:\.\d+)?\s?LPA\b|"
                               r"\b(?:Dr|Prof|Mr|Mrs|Ms|Sri|Smt|Col)\.?\s+[A-Z]|\b\d{3}\s?\d{3}\s?\d{4}\b")
# A Markdown table in an answer (its header separator row, e.g. "|---|---|").
_HAS_MD_TABLE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$", re.MULTILINE)
_LIMIT_REPLY_OPTIONS = [
    ("I'm getting a lot of questions right now, so I couldn't read yours properly. Please send it again in a "
     "minute and I'll answer it fully. Meanwhile, the buttons below work straight away, or call the Admissions "
     f"Office at {config.ADMISSIONS_PHONE}."),
    ("Sorry, I'm handling many students at the moment and couldn't answer that just now. Please try again in a "
     "minute. The buttons below still work, and the Admissions Office is on "
     f"{config.ADMISSIONS_PHONE}."),
    ("I'm a little busy right now and didn't want to give you a guessed answer. Please ask again in a minute. "
     f"You can use the buttons below meanwhile, or call Admissions at {config.ADMISSIONS_PHONE}."),
]
# Buttons that work without the model: the calculator opens in the browser; the others run fixed flows.
_BUSY_CHIPS = ("Open fee calculator", "Calculate my scholarship", "Talk to a counsellor", "Plan a campus visit")
_LIMIT_REPLY = _LIMIT_REPLY_OPTIONS[0]


def get_limit_reply(seed_str: str = "") -> str:
    if not seed_str:
        return _LIMIT_REPLY
    import hashlib
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return _LIMIT_REPLY_OPTIONS[h % len(_LIMIT_REPLY_OPTIONS)]


def _select_variation(options: list[str], seed_str: str) -> str:
    import hashlib
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return options[h % len(options)]


def _is_first_interaction_name_query(message: str) -> bool:
    msg = (message or "").strip().lower()
    if any(k in msg for k in ("hostel", "mess", "food")):
        return False
    if any(k in msg for k in ("fee", "fees", "scholarship", "tuition", "cost", "waiver")):
        return True
    if any(k in msg for k in ("about sru", "about sr university", "tell me about sru", "tell me about sr university",
                              "what is sru", "what is sr university", "know about sru", "know about sr university")):
        return True
    if any(k in msg for k in ("how to apply", "how to join sru", "join sr university",
                              "courses in sru", "programs in sru", "b.tech in sru", "btech in sru")):
        return True
    return False


# Static response templates and catalogues are housed in responses.py (ONE copy: an older, much longer
# duplicate of these texts used to follow here and silently replaced the condensed versions).
from .responses import (
    _SMALL_TALK_CHIPS,
    _PLACEMENT_ASSISTANCE_CHIPS,
    _PLACEMENT_ASSISTANCE_RESPONSES,
    _SPECIAL_CONCESSIONS_TEXT,
    _NEXT_GEN_TECH_TEXT,
    _FEE_TREE_TEXT,
    _BTECH_TREE_TEXT,
    _BTECH_CSE_FEE_TEXT,
    get_btech_cse_fee_text,
    _BTECH_AI_ROBOTICS_FEE_TEXT,
    _BTECH_ECE_FEE_TEXT,
    _BTECH_CORE_FEE_TEXT,
    _MANAGEMENT_FEE_TEXT,
    _AGRICULTURE_FEE_TEXT,
    _COMP_APP_FEE_TEXT,
    _DESIGN_FEE_TEXT,
    _ALL_PROGRAMS_TEXT,
    _HOSTEL_INFO_TEXT,
    _HOSTEL_INFO_CHIPS,
    _HOSTEL_MESS_TEXT,
    _HOSTEL_MESS_CHIPS,
    _HOSTEL_CURFEW_RULES_TEXT,
    _HOSTEL_CURFEW_CHIPS,
    _HOSTEL_SAFETY_TEXT,
    _HOSTEL_SAFETY_CHIPS,
    _HOSTEL_FEE_TEXT,
    _HOSTEL_FEE_CHIPS,
    _COMBINED_HOSTEL_FEE_TEXT,
    _COMBINED_HOSTEL_FEE_CHIPS,
    _CAMPUS_CANTEEN_TEXT,
    _CAMPUS_CANTEEN_CHIPS,
    _ACADEMIC_EVALUATION_TEXT,
    _ACADEMIC_EVALUATION_CHIPS,
    _LAB_FACILITIES_TEXT,
    _LAB_FACILITIES_CHIPS,
    _ADMISSION_GUARANTEE_TEXT,
    _ADMISSION_GUARANTEE_CHIPS,
    _FUTURE_YEAR_FEE_TEXT,
    _FUTURE_YEAR_FEE_CHIPS,
)










_ABOUT_SRU_TEXT = """### 🎓 About SR University (SRU)

SR University is a multidisciplinary, research-driven institution in Warangal, Telangana, dedicated to innovation, academic excellence, and global readiness:

• **Top Private University of Telangana & AP**: SR University stands among the premier private universities in the Telugu States, and is the first private university in Telangana and AP to receive prestigious **ICAR accreditation** for agricultural programs.
• **Prestigious Rankings & Accreditations**: Ranked **91st in NIRF Engineering** (top 100 for 4 consecutive years), **Tier-1 NBA accreditation** across all eligible B.Tech programs, **NAAC 'A' Grade**, and ranked **7th among private universities in India** (6th in Research Quality) by Times Higher Education (THE).
• **Record Placements & Industry Readiness**: Exceptional career outcomes with packages reaching **₹51 LPA (Microsoft)**, **₹49.3 LPA (ServiceNow)**, and **₹46.38 LPA (Amazon)**, an average package of ₹6 LPA, over 1,300 job offers, and **100% placement readiness assistance** with 250+ marquee recruiters.
• **Global Collaborations**: Active tie-ups with **80+ top global universities** across the US, UK, Australia, and Europe for student exchange, semester abroad, and 2+2 dual-degree international pathways.
• **Next-Gen Living & Learning Campus**: A vibrant **170-acre green campus** featuring 15+ advanced research centers, DST-backed **SRiX Technology Business Incubator** (171+ startups, ₹76+ Cr funding), a 4,000-seat mega central dining complex, and modern 24/7 secured hostels."""

_WHY_CHOOSE_SRU_TEXT = """### 🌟 Why Choose SR University?

SR University delivers a distinctive education blending academic prestige, practical innovation, and high-impact career outcomes:

• **Top Private University of Telangana & AP**: The premier and fastest-growing private university in Telangana with recognized national and global standing, plus first-in-region ICAR accreditation.
• **Elite Rankings & Global Recognition**: **NIRF 91st in Engineering** (consistently in Top 100 for 4 consecutive years), **Tier-1 NBA** accredited B.Tech branches, **NAAC 'A' grade**, and ranked **7th among private Indian universities** by Times Higher Education.
• **Marquee Placements & High Packages**: Dream career packages of **₹51 LPA (Microsoft)**, **₹49.3 LPA (ServiceNow)**, and **₹46.38 LPA (Amazon)**, with 100% placement readiness assistance and 3,500+ internships.
• **Global Collaborations**: Strategic tie-ups with **80+ international universities** allowing students to study abroad, pursue joint research, or complete international engineering dual degrees.
• **Next-Gen Living & Learning Campus**: A state-of-the-art **170-acre campus** with modern AC/Non-AC hostels, 4,000-seat central dining hall, DST-funded **SRiX Startup Incubator** (₹76+ Cr raised), and flexible choice-based credit learning (FFCS)."""

# Overviews written once per conversation (see run_agent): a repeat goes to the model instead.
_OVERVIEW_INTENTS = {
    "NEXT_GEN_TECH_QUERY", "ALL_PROGRAMS_QUERY", "BTECH_PROGRAMS_QUERY", "PROGRAM_AI_ROBOTICS_QUERY",
    "PROGRAM_CSE_QUERY", "PROGRAM_ECE_QUERY", "PROGRAM_CORE_QUERY", "PROGRAM_MANAGEMENT_QUERY",
    "PROGRAM_AGRICULTURE_QUERY", "PROGRAM_COMP_APP_QUERY", "PROGRAM_DESIGN_QUERY", "CAMPUS_CANTEEN_QUERY",
    "ACADEMIC_EVALUATION_QUERY", "LAB_FACILITIES_QUERY",
}
# Aspects answered from the verified facts when the question is otherwise general.
_UNIVERSITY_FACT_ASPECTS = {"rankings", "accreditation", "research", "innovation", "international", "about"}
# A question about a fee, a form, a visit or a call is never answered with university highlights.
_TRANSACTIONAL_WORDS = re.compile(
    r"\b(fee|fees|cost|price|pay|hostel|eligib\w*|cutoff|marks?|percent\w*|apply|application|admission\s+process|"
    r"visit|tour|call|callback|counsell?or|document\w*|deadline|date|hall ticket|exam|scho\w*arship\w*|"
    r"eamcet|eapcet|emcet|emact|jee|neet|sat|cuet|percentile)\b|\d+\s*%|(?<!top )\b\d{3,}\b", re.IGNORECASE)
_BARE_WHY = re.compile(r"^\s*(?:but\s+)?(?:why|how come|why so|why is that)\s*[?!.]*\s*$", re.IGNORECASE)
_NAMES_SRU = re.compile(r"\b(sru|sr university|this (?:college|university)|your (?:college|university))\b", re.IGNORECASE)
_ABOUT_SRU_CHIPS = ["B.Tech CSE fees", "Calculate my scholarship", "Placement record", "Plan a campus visit"]












# "What is my number?", "which number did you save?", "do you have my mobile number?"
_ASKS_OWN_NUMBER = re.compile(
    r"\b(?:what(?:'s|\s+is)|which(?:\s+is)?|tell\s+me|show(?:\s+me)?|do\s+you\s+have|did\s+you\s+save|"
    r"is)\b[^?.!]{0,25}?\bmy\s+(?:mobile\s+|phone\s+|contact\s+|registered\s+)?(?:number|no\.?)(?=\W|$)",
    re.IGNORECASE)


_SWITCH_TO = re.compile(r"\b(?:change|switch|move|update|shift|instead)\b.*?\b(?:to|into)\s+(?P<target>.+)$",
                        re.IGNORECASE)


_CHANGE_ACADEMIC = re.compile(
    r"\b(?:change|update|edit|correct|modify|re-?enter)\b.{0,30}\b(?:academic\s+details|marks?|board|percentage|"
    r"group|stream|scores?|details)\b", re.IGNORECASE)
_FEE_CHART_REQUEST = re.compile(
    r"\b(?:fee\s+chart|fee\s+plan|(?:full|complete|whole|entire|total)\s+fee\s+(?:chart|plan|breakdown|details)|"
    r"prepare\s+(?:my|the|a)\s+(?:full\s+|complete\s+|whole\s+)?fee)\b", re.IGNORECASE)
_AFFIRM = re.compile(r"^\s*(?:yes|yeah|yep|yup|sure|ok(?:ay)?|please|go\s+ahead|do\s+it|prepare\s+it|haa?n?|avunu)\b",
                     re.IGNORECASE)
_DECLINE = re.compile(r"^\s*(?:no|nope|not\s+now|no\s+thanks?|later|skip)\b", re.IGNORECASE)
_FEE_CHART_OFFER = "Shall I prepare your complete fee chart (tuition, scholarship, hostel and other fees) to share?"
_ADD_CONCESSION = re.compile(r"\b(?:add|apply|include|use|deduct|with|in\s+my\s+fee|to\s+my\s+fee)\b", re.IGNORECASE)


# Asks WHAT the eligibility is (not "am I eligible?", "can I join?", which are the check).
_ELIGIBILITY_RULE_Q = re.compile(
    r"^(?!.*\b(?:am\s+i|can\s+i|will\s+i|do\s+i|my\s+(?:marks|percentage|score))\b).*(?:"
    r"\b(?:what|which)\b.{0,25}\b(?:eligibility|cut[- ]?off|minimum\s+(?:marks|percentage)|criteria|requirements?)\b|"
    r"\beligibility\s+(?:criteria|cut[- ]?off|requirements?|rules?)\b|\b(?:and|about)\s+(?:the\s+)?eligibility\b|"
    r"\bminimum\s+(?:marks|percentage)\s+(?:for|required|needed)\b)", re.IGNORECASE)
# A fee question that should evaluate first (see run_agent), and what keeps the standard fee at once instead.
_FEE_STANDARD_ONLY = re.compile(
    r"\b(?:just|only|standard|plain|basic)\b.{0,30}\bfees?\b|\bfees?\b.{0,20}\b(?:only|without\s+(?:my\s+)?"
    r"(?:marks|scholarship|details))\b|\bwithout\s+(?:my\s+)?(?:marks|scholarship|details)\b|"
    r"\bfee\s+(?:breakdown|table|chart)\b|\bper\s+sem(?:ester)?\b|\b(?:pay|payment|instal\w*|refund|due|deadline)\b",
    re.IGNORECASE)
_FEE_OTHER_TOPIC = re.compile(r"\b(?:hostel|mess|bus|transport|room|application\s+fee|exam\s+fee|other\s+fees?|"
                              r"4[- ]?years?|four[- ]years?|total\s+course|20\d\d)\b", re.IGNORECASE)
_FEE_STEP_OPENER = re.compile(r"^(?:Sure|Absolutely|Great)[^!.]*[!.]\s*(?:Let's work out your scholarship for \*\*[^*]+\*\*\.\s*)?",
                              re.IGNORECASE)


# v4.14.0 (1,000-student test): while the fee steps wait for the board / marks / programme, a question about
# something else ("how are the placements?", "fests in sru", "what is the AC room fee") is answered; it used to get
# the same step question back. The steps stay saved, and the reply offers "Continue my fee estimate".
_SIDE_TOPIC = re.compile(
    r"\b(?:placements?|placments?|packages?|recruit\w*|compan(?:y|ies)|jobs?|hostels?|hostals?|mess|food|canteen|"
    r"rooms?|events?|fests?|festivals?|clubs?|sports?|gym|campus|campas|rank(?:ed|ing|ings)?|nirf|naac|accredit\w*|"
    r"apply|application|admission\s+process|located|location|where\s+is|address|safe\w*|security|curfew|"
    r"in-?time|timings?|cut-?off|refund|courses|programmes|programs|branches|faculty|hod|library|labs?|bus|"
    r"transport|lumina|sparkrill|sparkill|navadhara|swagath\w*|swagatam|hackathons?|worth|fake|better\s+than|"
    r"why\s+(?:sru|should|choose)|life|vibe|culture)\b", re.IGNORECASE)
_STEP_ANSWER = re.compile(
    r"\d|\b(?:state\s+board|board|cbse|icse|isc|ib|igcse|nios|intermediate|inter|12th|10\+2|completed|"
    r"appearing|passed|writing|mpc|bipc|mec|cec|hec|yes|yeah|no|none|skip)\b", re.IGNORECASE)


_GENERAL_SCHOLARSHIP = re.compile(
    r"\b(?:what|which|any|list\s+of|types?\s+of|kinds?\s+of)\s+(?:are\s+the\s+)?(?:merit\s+)?scholarships?\b(?!\s+(?:for\s+me|can\s+i|will\s+i))|"
    r"\b(?:merit\s+)?scholarships?\s+(?:details|available|options|structure|policy|criteria|slabs?)\b|"
    r"\bscholarships?\s+for\s+toppers\b|\bdoes\s+(?:sru|sr\s+university)\s+(?:give|offer|provide)\s+scholarships?\b|"
    r"\btell\s+me\s+about\s+(?:the\s+)?scholarships?\b", re.I)
# "How much fee would I need to pay, and do I get any scholarship?": the student's OWN fee (the evaluation), not
# the general scholarship table (v4.15.0, 2,000-student test).
_OWN_FEE = re.compile(r"\bhow\s+much\b.{0,40}\b(?:i|me|my)\b|\b(?:i|me|my)\b.{0,30}\b(?:pay|payable)\b|"
                      r"\bmy\s+(?:fee|fees|total)\b|\b(?:will|would|do|can)\s+i\s+get\b.{0,20}\bscholarship", re.I)
_SIDE_TURN: contextvars.ContextVar[bool] = contextvars.ContextVar("sru_side_turn", default=False)
_PLACEMENT_Q = re.compile(
    r"\b(?:placements?|placments?|placemnts?|packages?|recruiters?|recruitment|hiring|"
    r"jobs?\s+after|get\s+(?:a\s+)?jobs?|companies\s+(?:come|visit)|highest\s+package|average\s+package)\b", re.I)


def _side_question(message: str, conv_state: dict) -> bool:
    """The fee steps are waiting and this message asks about something else (not an answer to the step)."""
    intake = conv_state.get("fee_intake") or {}
    if intake.get("waiting_for") in (None, "done"):
        return False
    text = (message or "").strip()
    if not text or fee_journey._CONTINUE.search(text) or _STEP_ANSWER.search(text) or _FEE_STANDARD_ONLY.search(text):
        return False
    if _DISCOUNT_ASK.search(text) and (fee_plan.infer_concession(text) or fee_plan.concessions_for_group(text)):
        return True      # "any fee concession for single parent?": that concession is answered first (v4.15.1)
    if fee_intake.is_fee_enquiry(text) and not re.search(r"\b(?:hostel|room|mess|bus|transport)\b", text, re.I):
        return False                                     # a fee question continues the fee steps
    # A programme's own label is an answer, even when it has words like "ICAR Accredited" in brackets (v4.15.0)
    if fees.find_program(text) and re.search(r"\b(?:details?|about|tell\s+me|info(?:rmation)?|explain|overview)\b",
                                             text, re.I) and not fee_intake.is_fee_enquiry(text):
        return True     # "tell me about BBA" / "B.Sc Agriculture details" at any step: answered first (v4.15.1)
    if intake.get("waiting_for") == "program" and fees.find_program(text) \
            and not _SIDE_TOPIC.search(re.sub(r"\([^)]*\)", " ", text)):
        return False
    return bool(_SIDE_TOPIC.search(text))


_intake_open = fee_coordinator.intake_open


def _starts_fee_evaluation(message: str, conv_state: dict) -> bool:
    """A plain fee question ("B.Tech CSE fees", "fee for MBA?") with no evaluation running: evaluate first."""
    from app.services import app_settings
    if app_settings.get("fee_questions") != "evaluate_first":
        return False
    text = message or ""
    if not fee_intake.is_fee_enquiry(text) or _FEE_STANDARD_ONLY.search(fee_intake._PAY_HOW_MUCH.sub(" fee ", text)) \
            or _FEE_OTHER_TOPIC.search(text) \
            or (_GENERAL_SCHOLARSHIP.search(text) and not _OWN_FEE.search(text)):
        return False
    if _FEE_CHART_REQUEST.search(text) or _concession_requested(text) or tools.find_phone(text) \
            or intents.is_callback_request(text):
        return False
    if _fee_overview_question(text):
        return False   # "fees for all branches", "BBA and MBA fees": show the fees, don't start the steps
    if affordability.is_affordability_query(text):
        return False   # "I can't afford the fee": the affordability answer, not the evaluation steps again
    if _DISCOUNT_ASK.search(text) and (fee_plan.infer_concession(text) or fee_plan.concessions_for_group(text)):
        return False   # "my brother studies at SRU, any discount?": that concession is the answer (v4.15.0)
    intake = conv_state.get("fee_intake") or {}
    evaluation = conv_state.get(fee_journey.KEY) or {}
    if intake.get("waiting_for") not in (None, "done") or (evaluation.get("active") and not evaluation.get("final_shown")):
        return False   # an evaluation is already running: its own steps answer
    return True


_FEE_OVERVIEW = re.compile(
    r"\b(?:all|every|each|different|various)\s+(?:the\s+)?(?:b\.?\s?tech\s+)?(?:branch(?:es)?|programm?es?|programs?|"
    r"courses?|streams?)\b|\bbranch[- ]?wise\b|\bcompar\w*\b|\bvs\.?\b|\bversus\b|\bdifference\b|\bcheape?st\b",
    re.IGNORECASE)


def _fee_overview_question(text: str) -> bool:
    """An overview or several programmes in one fee question: answered with the fees, not an evaluation."""
    if _FEE_OVERVIEW.search(text or ""):
        return True
    parts = [p for p in re.split(r"\band\b|,|&|/|\bor\b", text or "", flags=re.IGNORECASE) if p.strip()]
    named = {fees.find_program(p) for p in parts} - {None}
    return len(named) >= 2


_DISCOUNT_ASK = re.compile(r"\b(?:discounts?|concessions?|reductions?|waivers?|fee\s+relief|less\s+fee|benefits?|"
                           r"offers?|rebate|quota)\b|\bscholarships?\s+(?:for|to)\s+(?:girls?|daughters?|women|"
                           r"sports\w*|athletes?|single\s+parent|orphans?|defen[cs]e|police|army|military|ncc|siblings?|"
                           r"lateral\s+entry|alumni|(?:kids|children|sons?)\s+of)\b|"
                           r"\b(?:girl\s+child|siblings?|army|military|lateral\s+entry|ncc|alumni)\b.{0,30}"
                           r"\b(?:scholarships?|concessions?)\b", re.IGNORECASE)
_CUTOFF_FACT = re.compile(
    r"\bclosing\s+(?:rank|cut[- ]?off|marks?)|\bcut[- ]?off\s+(?:rank|ranks)\b|\brank\s+cut[- ]?off|"
    r"\blast\s+year'?s?\s+(?:closing|cut[- ]?off|ranks?)\b|\b(?:cut[- ]?off|closing)\b.{0,40}\blast\s+year\b",
    re.IGNORECASE)
_CUTOFF_TEXT = (
    "SR University does not publish closing ranks or cut-offs, so I can't give a verified figure: the Admissions "
    f"Office can confirm ({config.ADMISSIONS_PHONE}). Admission depends on meeting the programme's eligibility and on "
    "seat availability. Your EAPCET rank or JEE Main percentile also counts for the merit scholarship, and the best "
    "of your scores applies.")


# v4.15.0: the number of seats is not on the official pages: said plainly, never guessed (2,000-student test).
_SEATS_Q = re.compile(r"\bhow\s+many\s+seats\b|\b(?:number|no\.?)\s+of\s+seats\b|\bseat\s+(?:intake|matrix|count|capacity)\b|"
                      r"\btotal\s+seats\b|\bseats\s+(?:available|are\s+there)\b|\bintake\s+(?:for|in|of)\b", re.IGNORECASE)
_SEATS_TEXT = (
    "The number of seats in each programme isn't published on the official SR University pages I use, so I can't "
    f"give a verified figure: the Admissions Office can confirm it ({config.ADMISSIONS_PHONE}, info@sru.edu.in). "
    "Seats are filled on eligibility and merit, so applying early helps.")


def _concession_requested(message: str):
    """The special concession the student asks to add to their fee ({'label', 'amount'}), or None."""
    if not _ADD_CONCESSION.search(message or "") or not re.search(r"\bfee|concession|discount\b", message or "", re.I):
        return None
    exact = fee_plan.find_concession(message)   # the category picked in the table (its exact fee-card name)
    if exact:
        return exact
    if re.search(r"\d|%|\bmarks?\b|\bboard\b|\bpercent", message or "", re.I):
        return None   # a fee calculation with marks, not a concession request
    words = set(re.findall(r"[a-z]{3,}", (message or "").lower())) - {
        "add", "apply", "include", "use", "with", "fee", "fees", "the", "and", "their", "concession", "discount",
        "my", "for", "students", "student", "children", "child", "from", "deduct"}
    best, score = None, 0
    for c in fees.load_data().get("special_concessions", []):
        label_words = set(re.findall(r"[a-z]{3,}", c["label"].lower()))
        overlap = len(words & label_words)
        if overlap > score:
            best, score = c, overlap
    named = bool(re.search(r"\bconcession|discount\b", message or "", re.I))
    return ({"key": best["key"], "label": best["label"], "amount": best["amount"]}
            if best and (score >= 2 or named) and best.get("selectable", True) else None)


def _switch_target_program(message: str):
    """'change my programme from CSE to ECE' -> btech_ece (the programme after 'to'); None otherwise."""
    m = _SWITCH_TO.search(message or "")
    return fees.find_program(m.group("target")) if m else None


def _prompt_profile(profile: dict | None) -> dict:
    """What the model is told about the student: without the name in a session started afresh."""
    p = dict(profile or {})
    if p.pop("address_by_name", None) is False and p.get("name"):
        p["name_on_file"] = p.pop("name")      # still known for callbacks; just not used to address them
    return p


def _natural_first_name(profile: dict, history: list) -> str | None:
    """The student's first name when using it now would read naturally: never invented, and not when one of
    the last two replies already used it (so it is not forced into every message). None in a session started
    with "Start afresh" (address_by_name False): the name is on file only for the contact form."""
    if profile.get("address_by_name") is False:
        return None
    first = _first_name(str(profile.get("name") or "").strip())
    if not first or not first.isalpha():
        return None
    first = first[:1].upper() + first[1:]
    recent = [h.get("text", "") for h in history if h.get("role") in ("model", "assistant")][-2:]
    if any(re.search(rf"\b{re.escape(first)}\b", t, re.IGNORECASE) for t in recent):
        return None
    return first


_USE_SAVED = re.compile(r"^\s*(?:yes,?\s*)?use\s+my\s+saved\s+details\b", re.IGNORECASE)


def _read_academic_form(form: dict, profile: dict) -> tuple[dict, list[str], str | None, str]:
    """Validate a submitted academic details form. Returns (profile updates, problems, programme, mode).
    Every value is checked against the options the form offers; nothing is guessed."""
    updates, problems = {}, []
    mode = "scholarship" if form.get("mode") == "scholarship" else "eligibility"
    program = form.get("program")
    if program not in fees.load_data()["programs"]:
        program = None
    board = journey.board_fields(form.get("board_key"))
    if board:
        updates.update(board)
    else:
        problems.append("select your education board")
    stage = journey.stage_fields(form.get("academic_stage"))
    if stage:
        updates.update(stage)
    else:
        problems.append("select your current academic status")

    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    raw, total = _number(form.get("raw_marks")), _number(form.get("max_marks"))
    if board.get("board_key") == "ib":
        if raw is not None and 0 < raw <= 45:
            updates.update(ib_score=int(raw), raw_marks=raw, max_marks=45.0, marks_confirmed=True)
        else:
            problems.append("enter your IB Diploma points (out of 45)")
    elif raw is None or total is None or total <= 0 or raw <= 0 or raw > total:
        problems.append("enter your marks and the total they are out of (the marks cannot be more than the total)")
    elif total > 2000:
        problems.append("enter a valid maximum marks total up to 2000")
    else:
        updates.update(raw_marks=raw, max_marks=total, percent=round(raw / total * 100, 2), marks_confirmed=True)

    stream = form.get("stream")
    if stream in ("MPC", "BiPC", "MEC"):
        updates["stream"] = stream
    elif form.get("show_stream"):
        problems.append("select your 10+2 / Intermediate group")

    kind, value = form.get("entrance_type"), _number(form.get("entrance_value"))
    if kind in ("tg_eapcet", "ap_eapcet"):
        if value is not None and 1 <= value <= 500000:
            updates.update(admission_route=kind, route_label="TG EAPCET" if kind == "tg_eapcet" else "AP EAPCET",
                           eapcet_rank=int(value), no_entrance=None)
        else:
            problems.append("enter your EAPCET rank (a whole number)")
    elif kind == "jee_main":
        if value is not None and 0 <= value <= 100:
            updates.update(admission_route="jee_main", route_label="JEE Main", jee_percentile=value, no_entrance=None)
        else:
            problems.append("enter your JEE Main percentile (0 to 100)")
    elif kind == "none":
        updates["no_entrance"] = True
    return updates, problems, program, mode


# -------------------------------------------------------------------- the agent ----
def _is_mock_or_test_client(cl) -> bool:
    return cl is not None and type(cl).__name__ in (
        "DummyClient", "Recorder", "MockClient", "MockAgentClient", "ScriptedClient",
        "FakeClient", "StreamingClient", "FallbackClient", "KeyClient", "QuotaClient"
    )


def _one_question(message: str, profile: dict) -> bool:
    """True when a single-topic answer may take this message: it is not several questions (those are answered part
    by part by compound.plan, or by the model with the list of parts: v4.15.1)."""
    return compound.plan(message, profile) is None and not compound.model_note(message)


async def _resolve_sub_query(sub_q: str, topic: str, session_id: str) -> tuple[str, list, list]:
    """One part of a multi-question message, answered from verified content: (text, cards, chips).
    `topic` comes from compound.plan, which only plans topics this function can answer."""
    cards: list = []
    if topic == "cse_vs_aiml":
        return responses._CSE_VS_AIML_TEXT, cards, list(responses._CSE_VS_AIML_CHIPS)
    if topic == "why_sru":
        # v4.15.1: from the verified facts registry (not the long static text), and exactly the number asked for
        n = compound.asked_count(sub_q)
        picked = fact_service.retrieve("why choose sru", k=n or 3,
                                       aspects=["rankings", "placements", "accreditation", "campus", "research"])
        bullets = [f"{i}. {(f.metadata or {}).get('short', '').strip()}" for i, f in enumerate(picked[:n or 3], 1)
                   if (f.metadata or {}).get("short")]
        if bullets:
            head = f"**{len(bullets)} reasons to choose SRU:**" if n else "**Why students choose SRU:**"
            return head + "\n\n" + "\n".join(bullets), cards, list(_ABOUT_SRU_CHIPS)
        return _WHY_CHOOSE_SRU_TEXT, cards, list(_ABOUT_SRU_CHIPS)
    if topic == "about_sru":
        return _ABOUT_SRU_TEXT, cards, list(_ABOUT_SRU_CHIPS)
    if topic == "hostel_curfew":
        return responses._HOSTEL_CURFEW_RULES_TEXT, cards, list(_HOSTEL_CURFEW_CHIPS)
    if topic == "hostel_mess":
        return responses._HOSTEL_MESS_TEXT, cards, list(_HOSTEL_MESS_CHIPS)
    if topic == "hostel_fee":
        from app.services.card_service import HOSTEL_FEE_CARD
        return responses._HOSTEL_FEE_TEXT, [HOSTEL_FEE_CARD], list(_HOSTEL_FEE_CHIPS)
    if topic == "hostel_safety":
        return responses._HOSTEL_SAFETY_TEXT, cards, list(_HOSTEL_SAFETY_CHIPS)
    if topic == "hostel_info":
        from app.services.card_service import HOSTEL_FACILITIES_CARD
        return responses.get_hostel_info_text(session_id, sub_q), [HOSTEL_FACILITIES_CARD], list(_HOSTEL_INFO_CHIPS)
    if topic == "fees":  # B.Tech CSE (named or already chosen): compound.plan never plans another programme here
        cse_prog = fee_flow.SCHOOLS_DATA[0]["programs"]["ug"][0]
        spec = fee_flow.detect_specialization(sub_q, cse_prog)
        fee_card = fee_flow.build_detailed_fee_card(cse_prog, fee_flow.SCHOOLS_DATA[0], "2027-28", spec=spec, user_text=sub_q)
        text = get_btech_cse_fee_text(specialization=spec, user_msg=sub_q)
        return text, [fee_card], ["Calculate my scholarship", "Hostel details", "How do I apply?"]
    if topic == "fees_ask":
        return compound.FEES_ASK_TEXT, cards, list(compound.FEES_ASK_CHIPS)
    if topic == "placements":
        return responses._PLACEMENT_ASSISTANCE_RESPONSES[0], cards, list(responses._PLACEMENT_ASSISTANCE_CHIPS)
    if topic == "scholarships":
        return compound.scholarship_overview_text(), cards, list(responses._SCHOLARSHIP_CRITERIA_CHIPS)
    if topic == "qf":          # v4.15.1: an exact answer from the fee card or the handbook
        from . import quick_facts
        qa = quick_facts.answer(sub_q)
        return (qa.text, cards, list(qa.chips)) if qa else ("", cards, [])
    if topic.startswith("campus:"):
        ans = campus_life.answer(topic.split(":", 1)[1], sub_q)
        return ans.text, list(getattr(ans, "cards", None) or []), list(getattr(ans, "chips", None) or [])
    return "", cards, []


# ---- Marks: the latest value always wins (v4.15.0) ------------------------------------------------------------
# A student who gives or corrects their marks ("No, my actual marks are 671 out of 1000", "not 92, I got 82
# percent") must have that value used at once, everywhere: the profile, the fee steps (fee_intake) and every
# calculation after. Done once, at the start of the turn, before any workflow reads the marks; a stale value
# (old raw marks next to a new percentage) is removed, not left beside it. The reply then confirms the update.
_MARKS_NOTE: contextvars.ContextVar[str] = contextvars.ContextVar("sru_marks_note", default="")
_DO_YOU_HAVE = re.compile(r"^\W*(?:do\s+you\s+(?:have|offer)|is\s+there|does\s+(?:sru|sr\s+university)\s+(?:have|offer)|"
                          r"is\s+\S+(?:\s+\S+)?\s+(?:available|offered))\b", re.IGNORECASE)
_CORRECTION_LEAD = re.compile(r"^\W*(?:no|nope|nah|nahi|nahin|kaadu|ledu|not|wrong|sorry|actually|wait|oops|galti)\b|"
                              r"\b(?:wrong|mistake|correct\s+marks|actual\s+marks|real\s+marks|galti|sorry)\b",
                              re.IGNORECASE)
_MARKS_WORDS = re.compile(r"\b(?:marks?|percent(?:age)?|scored?|got|out\s+of|cgpa|gpa|aggregate)\b|%|\d\s*/\s*\d", re.I)


def _marks_text(raw, mx, pct) -> str:
    if raw is not None and mx and float(mx) > 100:
        return f"{fees_num(raw)}/{fees_num(mx)} ({fees_num(pct)}%)" if pct is not None else f"{fees_num(raw)}/{fees_num(mx)}"
    return f"{fees_num(pct)}%" if pct is not None else f"{fees_num(raw)} marks"


def fees_num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:.2f}".rstrip("0").rstrip(".")


async def _sync_marks(message: str, session_id: str, conversation_id, profile: dict, conv_state: dict) -> dict:
    """Read marks given in this message and make them the only marks on file (see above). Returns the profile."""
    _MARKS_NOTE.set("")
    d = fee_intake.parse_details(message or "")
    new_raw, new_max, new_pct = d.get("raw_marks"), d.get("max_marks"), d.get("percent")
    if (new_raw is None and new_pct is None) or d.get("jee_percentile") is not None or d.get("eapcet_rank") is not None:
        return profile
    intake = dict(conv_state.get("fee_intake") or {})
    waiting_marks = intake.get("waiting_for") in ("marks", "marks_max", "percent")
    if not (_MARKS_WORDS.search(message or "") or waiting_marks):
        return profile
    if fee_intake._marks_problem(message, d, None, {**profile, **intake}, intake.get("waiting_for") or "marks"):
        return profile                                    # marks that can't be right are never saved
    old_raw = intake.get("raw_marks", profile.get("raw_marks"))
    old_pct = intake.get("percent", profile.get("percent"))
    old_max = intake.get("max_marks") or profile.get("max_marks")
    board = d.get("board_key") or intake.get("board_key") or profile.get("board_key")
    stage = d.get("academic_stage") or intake.get("academic_stage") or profile.get("academic_stage")
    fields: dict = {}
    clear: list = []
    if new_raw is None:                                   # a percentage (or CGPA) only: no raw marks any more
        fields["percent"] = float(new_pct)
        clear = ["raw_marks", "max_marks", "pending_raw_marks"]
    else:
        new_raw = float(new_raw)
        mx = new_max
        if not mx and old_max and new_raw <= float(old_max):
            mx = old_max
        if not mx and board:
            board_max = fee_intake.get_max_marks(board, stage or "completed")
            mx = board_max if board_max and new_raw <= board_max else None
        fields["raw_marks"] = new_raw
        if mx:
            fields["max_marks"] = float(mx)
            fields["percent"] = float(new_pct) if new_pct is not None else round(new_raw / float(mx) * 100, 2)
        else:
            clear = ["percent", "max_marks"]               # unknown total: the old percentage must not stay
    if fields.get("raw_marks") == old_raw and fields.get("percent", old_pct) == old_pct:
        if _CORRECTION_LEAD.match(message or "") and (old_raw is not None or old_pct is not None):
            # "No, my marks are 50%" with the same marks: confirmed (and the "No" is not an answer to the step)
            _MARKS_NOTE.set(_marks_text(old_raw if fields.get("raw_marks") is not None else None,
                                        intake.get("max_marks") or profile.get("max_marks"),
                                        fields.get("percent", old_pct)))
        return profile                                    # the same marks again: nothing changes
    profile = await memory.update_profile(session_id, **fields)
    if clear:
        profile = await memory.remove_profile_keys(session_id, *clear)
    if intake:
        intake.update(fields)
        for k in clear:
            intake.pop(k, None)
        intake.pop("needs_marks_confirmation", None)
        conv_state["fee_intake"] = intake
        await memory.update_conversation_state(session_id, conversation_id, fee_intake=intake)
    if old_raw is not None or old_pct is not None:        # a correction (not the first marks): confirm it
        _MARKS_NOTE.set(_marks_text(fields.get("raw_marks"), fields.get("max_marks"), fields.get("percent")))
    return profile


# v4.15.0 (2,000-student test): the misspellings students type most, read as the word they meant, so "hostal fees?"
# is about the hostel (it started a programme fee evaluation) and "eligiblity" finds the eligibility rule.
_TYPOS = [(re.compile(p, re.IGNORECASE), w) for p, w in (
    (r"\bhost(?:a|e)?ls?\b(?<!\bhostels)(?<!\bhostel)", "hostel"), (r"\bhostle?s?\b", "hostel"),
    (r"\bfe(?:es?s|ez|ss)\b", "fees"), (r"\bplac(?:e)?m(?:e|a)?nt(s)?\b", r"placement\1"),
    (r"\beligi?bi?li?ty\b", "eligibility"),
    (r"\bcampas\b", "campus"), (r"^\W*fes\W*$", "fees"), (r"\bhstel\b|\bhostl\b", "hostel"),
    (r"\bpl[ae]?cm(?:e)?nts?\b|\bplcmnt\w*", "placement"), (r"\badmsn\b|\badmisn\b", "admission"),
    (r"\bsch(?:o)?l(?:a)?r(?:s)?h(?:i)?p\b|\bschlrshp\b", "scholarship"), (r"\bevnts\b", "events"), (r"\badmi?s+ion\b", "admission"),
    (r"\bcolle?a?ge\b", "college"), (r"\bcoures?\b|\bcorse\b", "course"))]


def _fix_typos(message: str) -> str:
    out = message
    for rx, word in _TYPOS:
        out = rx.sub(word, out)
    return out


_BARE_NUMBER = re.compile(r"^\s*\d{1,6}(?:[.,]\d+)?\s*(?:%|percent|/\s*\d{2,4}|out\s+of\s+\d{2,4})?\s*$",
                          re.IGNORECASE)
_DATE_WORDS = re.compile(r"\d|\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan|feb|"
                         r"mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.IGNORECASE)


def _answers_open_step(message: str, conv_state: dict) -> str | None:
    """Which open step this message answers, or None (v4.17.1).

    The message must give what that step asked for, read by the step's own parser (a board, a stage, marks, a
    stream, a rank, a programme, a room, a concession, yes / no, a name or phone number). Its length or punctuation
    decides nothing: "placement record" while the board is asked answers nothing, so the model takes it and the
    step stays open (its "continue" chip brings the student back)."""
    text = (message or "").strip()
    if not text:
        return None
    try:
        d = fee_intake.parse_details(text) or {}
    except Exception:
        d = {}
    program = fees.find_program(text)
    yes_no = bool(_AFFIRM.match(text) or _DECLINE.match(text) or fee_journey._YES.match(text)
                  or fee_journey._NO.match(text))
    number = bool(_BARE_NUMBER.match(text))
    marks = number or any(d.get(k) is not None for k in ("raw_marks", "percent", "max_marks"))
    entrance = any(d.get(k) is not None for k in ("eapcet_rank", "jee_percentile", "no_entrance", "admission_route"))
    wants = {
        "board": bool(d.get("board") or d.get("board_key")),
        "stage": bool(d.get("academic_stage")),
        "marks": marks, "percent": marks, "marks_max": marks, "degree_percent": marks, "total": marks,
        "stream": bool(d.get("stream") or eligibility.parse_stream(text)),
        "rank": entrance or number or yes_no, "ib": d.get("ib_score") is not None or number,
        "program": bool(program), "branch": bool(program), "confirm_details": yes_no or bool(d),
    }
    intake = conv_state.get("fee_intake") or {}
    waiting = intake.get("waiting_for")
    if waiting and waiting not in ("done",):
        if waiting == "form" or wants.get(waiting) or (waiting not in wants and (bool(d) or yes_no)):
            return f"fee_step:{waiting}"
    fee_eval = conv_state.get(fee_journey.KEY) or {}
    aw = fee_eval.get("awaiting") if fee_eval.get("active") and not fee_eval.get("final_shown") else None
    if aw:
        ok = {"program": bool(program),
              "concession": bool(fee_plan.find_concession(text)) or yes_no,
              "hostel": bool(fee_journey._read_hostel(text)) or yes_no,
              "entrance": bool(fee_journey._read_entrance(text, aw)) or entrance or yes_no,
              "eapcet_value": number, "jee_value": number,
              "scholarship_steps": bool(d) or bool(program)}.get(aw, yes_no)
        if ok:
            return f"fee_evaluation:{aw}"
    if conv_state.get("pending_action") or conv_state.get("gate_pending") or conv_state.get("awaiting_name"):
        if tools.find_phone(text) or yes_no or intents.extract_name(text, bare_ok=True):
            return "contact_details"
    if conv_state.get("offer") and (yes_no or (conv_state.get("offer") == "fee_chart_program" and program)):
        return "offer"
    if conv_state.get("pending_concession") and program:
        return "concession_programme"
    if (conv_state.get("awaiting_date_confirmation") or conv_state.get("pending_visit_date")) \
            and (yes_no or _DATE_WORDS.search(text)):
        return "visit_date"
    if (conv_state.get("fee_flow_state") in ("awaiting_school_selection", "awaiting_course_selection")
            or conv_state.get("fee_tree_step")) and program:
        return "fee_browser"
    flow = conv_state.get("affordability_flow") or {}
    if isinstance(flow, dict) and flow.get("step"):
        if (flow["step"] == "awaiting_academics" and (marks or program)) or \
                (flow["step"] == "awaiting_concession" and (fee_plan.find_concession(text) or yes_no)):
            return "affordability"
    dlg = conv_state.get("dialogue") or {}
    step = dlg.get("step")
    if step:
        if step in wants and wants[step]:
            return f"journey:{step}"
        if step in ("topic_aspect", "program_aspect"):
            from . import dialogue as _dialogue
            topic = _dialogue.TOPICS.get(dlg.get("topic") or "", {})
            if any(re.search(rx, text, re.IGNORECASE) for _label, rx, _q in topic.get("aspects", [])):
                return f"journey:{step}"
        if step in ("goal", "interest") and (program or yes_no):
            return f"journey:{step}"
    return None


def _structured_turn(source, rewritten: bool, conv_state: dict, message: str, step_answer: bool,
                     dlg_busy: bool) -> str | None:
    """Why this turn belongs to a fixed flow, or None when the model should understand it (v4.17.0 / v4.17.1).

    Only facts about the TURN are used, never the meaning of topic words: what the student pressed, a submitted
    form, a phone number (data the callback flow must save exactly), or a typed answer that GIVES what the open
    step asked for (_answers_open_step). Anything else typed during an open step - a question, a new topic,
    "placement record" while the board is asked - is understood by the model, which sees the whole
    conversation; the step stays open and its "continue" chip brings the student back."""
    if source != "typed":
        return "button" if source == "button" else "internal"
    if rewritten:
        return "form"
    if tools.find_phone(message or ""):
        return "phone_number"
    answered = _answers_open_step(message, conv_state)
    if answered:
        return f"answer:{answered}"
    return None


async def run_agent(
    message: str,
    session_id: str,
    conversation_id=None,
    client=None,
    require_contact_details: bool = False,
    form: dict | None = None,
    source: str | None = None,
):
    """Async generator of events for one student message.
    form: a submitted academic details form (structured; see _read_academic_form).
    source: "typed" (the student typed it: understood by the model) or "button" (a chip / card / tile the bot
    offered: the fixed flow for that button). None = an internal caller (tests, replays): treated as a button."""
    started = time.perf_counter()
    _TURN_STARTED.set(started)
    _TURN_TELEMETRY_RECORDED.set(False)
    message = _fix_typos((message or "").strip()[:config.AGENT_MAX_MESSAGE_CHARS])
    yield {"type": "start", "conversation_id": conversation_id}
    if not message:
        yield {"type": "error", "detail": "Please type a question."}
        return

    # OWASP LLM01 / LLM06: Prompt injection and adversarial guardrail pre-screening
    refusal = intents.check_adversarial_guardrail(message)
    if refusal:
        async for ev in _say(refusal, message, session_id, conversation_id):
            yield ev
        return

    # Three independent reads, done together (each one may need a trip to Redis or the database), plus the
    # admin panel's chat settings (cached; reloaded at most every 20 seconds).
    from app.services import app_settings
    await memory.warm_turn_keys(session_id, conversation_id)
    profile, history, conv_state, _settings = await asyncio.gather(
        memory.get_profile(session_id), memory.get_history(session_id, conversation_id),
        memory.get_conversation_state(session_id, conversation_id), app_settings.refresh())
    # Academic details belong to one conversation: a new chat starts clean (journey.py).
    profile = await journey.scope_profile(session_id, conversation_id, profile, conv_state)
    try:
        profile = await _sync_marks(message, session_id, conversation_id, profile, conv_state)
    except Exception:
        log.exception("marks sync failed for session %s", (session_id or "")[:8])
    ctx = {"session_id": session_id, "conversation_id": conversation_id, "profile": profile, "message": message,
           "conv_state": conv_state, "history": history}   # conv_state / history: for the counsellor's case summary
    natural_name = _natural_first_name(profile, history)

    if require_contact_details:
        existing_phone = tools.clean_phone(profile.get("phone") or "")
        extracted_phone = tools.find_phone(message)
        extracted_name = intents.extract_name(message, bare_ok=not profile.get("name"))
        if extracted_name and not profile.get("name"):
            profile = await memory.update_profile(session_id, name=extracted_name)
        elif extracted_name and profile.get("address_by_name") is False:
            # A fresh start, and the student introduced themselves: use the name they gave from now on.
            profile = await memory.update_profile(session_id, name=extracted_name, address_by_name=True)
            ctx["profile"] = profile
            natural_name = _natural_first_name(profile, history)
        if extracted_phone and not existing_phone:
            profile = await memory.update_profile(session_id, phone=extracted_phone)
        existing_name = str(profile.get("name") or "").strip()
        existing_phone = tools.clean_phone(profile.get("phone") or "")
        gate_pending = conv_state.get("gate_pending")
        only_details = bool(extracted_name or extracted_phone) and not re.search(r"\?|\b(?:fee|fees|call|counsell?or|"
                                                                                 r"scholarship|hostel|admission)\b",
                                                                                 message, re.I)

        if existing_name and existing_phone and gate_pending and only_details:
            # v4.15.0: the student was asked for their name (or number) before a request, and gave it: carry out
            # the request they made ("call me back"), instead of leaving it behind.
            conv_state["gate_pending"] = None
            await memory.update_conversation_state(session_id, conversation_id, gate_pending=None)
            ctx["profile"] = profile
            natural_name = _natural_first_name(profile, history)
            message = gate_pending
        elif not (existing_name and existing_phone):
            if not only_details:
                conv_state["gate_pending"] = message
                await memory.update_conversation_state(session_id, conversation_id, gate_pending=message)
            if not existing_name and not existing_phone:
                reply = ("Before I can help, please share your full name and 10-digit mobile number, and I'll take it "
                         "from there.")
            elif not existing_name:
                reply = "May I have your full name first? Then I'll take care of that right away."
            else:
                reply = "May I have your 10-digit mobile number first? Then I'll take care of that right away."
            async for ev in _say(reply, message, session_id, conversation_id):
                yield ev
            return

    rewritten = False   # the message was rewritten from a form / "use my saved details" (a structured turn)
    # ---- Academic details form submitted: validate, store as this conversation's details, then continue as
    # the request the form was for, so eligibility / scholarship are evaluated by the usual code. ----------
    if form:
        updates, problems, form_program, form_mode = _read_academic_form(form, profile)
        form_program = form_program or conv_state.get("active_program") or profile.get("program_interest")
        if problems or not form_program:
            # Nothing is saved from a form with problems; it comes back with exactly what was entered.
            if not form_program:
                problems.append("choose the programme first")
            entered = {**profile, **{k: v for k, v in form.items() if v not in (None, "")}}
            if form.get("entrance_type") in ("tg_eapcet", "ap_eapcet"):
                entered.update(eapcet_rank=form.get("entrance_value"), admission_route=form.get("entrance_type"))
            elif form.get("entrance_type") == "jee_main":
                entered.update(jee_percentile=form.get("entrance_value"))
            card = card_service.build_academic_details_form(
                form_mode, form_program, fees.short_name(form_program) if form_program else None, entered,
                show_stream=bool(form.get("show_stream")), show_entrance=bool(form.get("show_entrance")))
            text = "Almost there! Please " + "; ".join(problems) + ", then submit again."
            async for ev in _say(text, message, session_id, conversation_id, cards=[card]):
                yield ev
            return
        clean = {k: v for k, v in updates.items() if v is not None}
        if clean:
            profile = await memory.update_profile(session_id, **clean)
        if "no_entrance" in updates and updates["no_entrance"] is None and profile.pop("no_entrance", None):
            await memory.replace_profile(session_id, profile)  # an entrance score was given after all
        ctx["profile"] = profile
        fresh_intake = {"counsellor_mode": True, "program": form_program, "turns": 1, "waiting_for": "form",
                        "ack_shown": bool((conv_state.get("fee_intake") or {}).get("ack_shown"))}
        await memory.update_conversation_state(session_id, conversation_id, active_program=form_program,
                                               fee_intake=fresh_intake if form_mode == "scholarship" else None)
        conv_state["active_program"] = form_program
        conv_state["fee_intake"] = fresh_intake if form_mode == "scholarship" else None
        full_name = fees.clean_program_name(form_program)
        message = (f"Calculate my scholarship for {full_name}" if form_mode == "scholarship"
                   else f"Am I eligible for {full_name}?")
        rewritten = True

    if _USE_SAVED.match(message) and profile.get("saved_academic"):
        profile = await journey.restore_saved(session_id, profile)
        ctx["profile"] = profile
        pending_prog = (conv_state.get("dialogue") or {}).get("program") or conv_state.get("active_program")
        intake_wait = (conv_state.get("fee_intake") or {}).get("waiting_for")
        if pending_prog and intake_wait and (conv_state.get("fee_intake") or {}).get("counsellor_mode"):
            message, rewritten = f"Calculate my scholarship for {fees.clean_program_name(pending_prog)}", True
        elif pending_prog:
            message, rewritten = f"Am I eligible for {fees.clean_program_name(pending_prog)}?", True
        else:
            text = (f"Done! I'll use your saved details ({journey.saved_summary(profile)}) in this chat. "
                    "What would you like to check?")
            async for ev in _say(text, message, session_id, conversation_id,
                                 suggestions=["Check my eligibility", "Calculate my scholarship"], exact_chips=True):
                yield ev
            return

    # ---- Conversation manager (no AI call): broad topics -> "which aspect?", the admission journey
    # (programme -> branch -> goal -> marks -> subjects -> verdict), and short follow-ups about the programme
    # being discussed. Specific questions pass through untouched. See dialogue.py.
    dlg_busy = bool(conv_state.get("pending_action") in ("callback", "campus_visit")
                    or conv_state.get("affordability_flow") or conv_state.get("awaiting_date_confirmation")
                    or conv_state.get("pending_visit_date") or conv_state.get("awaiting_name")
                    # the school / course browser and the fee tree are waiting for a tap on their own options
                    or conv_state.get("fee_flow_state") in ("awaiting_school_selection", "awaiting_course_selection")
                    or conv_state.get("fee_tree_step"))
    intake_now = conv_state.get("fee_intake") or {}
    side_q = _side_question(message, conv_state)
    _SIDE_TURN.set(side_q)
    if _FEE_STANDARD_ONLY.search(message or "") and fees.find_program(message or "") \
            and (intake_now.get("waiting_for") not in (None, "done") or (conv_state.get("dialogue") or {}).get("step")):
        # "Just show the B.Tech CSE fee": the standard fee now, the evaluation steps closed.
        conv_state["fee_intake"], intake_now = None, {}
        conv_state["dialogue"] = {k: v for k, v in (conv_state.get("dialogue") or {}).items() if k != "step"}
        await memory.update_conversation_state(session_id, conversation_id, fee_intake=None,
                                               dialogue=conv_state["dialogue"])
    if not dlg_busy and not side_q and intake_now.get("waiting_for") not in (None, "done") \
            and not (conv_state.get("dialogue") or {}).get("step"):
        try:  # the fee intake is waiting for an answer and this message is one: let it continue
            dlg_busy = fee_intake.decide(message, profile, dict(intake_now)) is not None
        except Exception:
            dlg_busy = False
    # v4.15.0: this message answers the open fee step ("AI and Robotics" to "which programme?"): no topic answer
    # (labs, programmes...) may take it; the steps continue.
    step_answer = bool(dlg_busy and not side_q and intake_now.get("waiting_for") not in (None, "done"))
    # v4.15.1: specific questions answered exactly from the fee card's terms / verified facts (quick_facts.py)
    used, cards = [], []

    async def set_state(**fields):
        conv_state.update(fields)
        await memory.update_conversation_state(session_id, conversation_id, **fields)

    async def clear_pending():
        await set_state(pending_action=None, pending_phone=None, pending_name=None, pending_turns=0)

    # ---- Model-first understanding (v4.17.0) -----------------------------------------------------------------
    # A message the student TYPED is understood by the language model, with the whole conversation, the
    # student's saved details, the verified facts and the tools (fee engine, eligibility, callbacks...). No
    # keyword or phrase decides what a typed question means. The fixed flows below run only for STRUCTURED
    # turns: a button / chip / card the bot itself offered, a submitted form, or an answer to the question the
    # bot has just asked (see _structured_turn). Fee amounts still come only from the fee engine (tools).
    structured = _structured_turn(source, rewritten, conv_state, message, step_answer, dlg_busy)
    model_first = structured is None
    # ---- Deterministic fast-path before model_first (Phase 2: 0 LLM calls for small talk, quick_facts, contact/apply)
    if model_first and not tools.find_phone(message or "") and not intents.is_callback_request(message or ""):
        fast_chat = intents.small_talk(message)
        if fast_chat:
            if fast_chat == "greeting" and not profile.get("name"):
                await set_state(awaiting_name=True, name_asked=True)
            fast_kind = fast_chat if fast_chat in _SMALL_TALK_BRIEFS else "greeting"
            if fast_chat == "greeting" and not profile.get("name"):
                fast_kind = "greeting_ask_name"
            fast_chips = [] if fast_chat in ("thanks", "bye") else _SMALL_TALK_CHIPS
            async for ev in _small_talk_reply(
                fast_kind, message, session_id, conversation_id,
                history=history, profile=profile, conv_state=conv_state,
                suggestions=fast_chips, no_llm=True,
            ):
                yield ev
            return
        if not compound.model_note(message) and not fees.find_program(message or ""):
            from . import quick_facts
            fast_qa = quick_facts.answer(message, profile)
            if fast_qa:
                async for ev in _say(
                    fast_qa.text, message, session_id, conversation_id,
                    cards=list(fast_qa.cards or []), suggestions=fast_qa.chips, exact_chips=True,
                    profile=profile,
                ):
                    yield ev
                return
            if re.match(
                r"^\s*(?:how\s+(?:do\s+i|to)\s+apply|apply\s+link|application\s+link|"
                r"admissions?\s+(?:contact|phone|number|email|helpline)|contact\s+(?:details|number|admissions?))\s*[?!.]*\s*$",
                message or "",
                re.I,
            ):
                contact_res = await _run_action("get_contact_and_apply_links", {"topic": message}, ctx, used, cards)
                for ev in _tool_events("get_contact_and_apply_links", contact_res):
                    yield ev
                contact_text = (
                    f"You can apply online at **{config.APPLY_URL}**.\n\n"
                    f"• **Admissions Helpline:** {config.ADMISSIONS_PHONE}\n"
                    f"• **Email:** {config.ADMISSIONS_EMAIL}\n"
                    f"• **Campus Visit Helpline:** {config.CAMPUS_VISIT_PHONE}"
                )
                async for ev in _say(
                    contact_text, message, session_id, conversation_id,
                    used=used, cards=cards,
                    suggestions=["Calculate my fee", "Check my eligibility", "Plan a campus visit"],
                    profile=profile,
                ):
                    yield ev
                return

    if model_first:
        intent, action, action_note, canned_action_text = "GENERAL", None, None, None
        intake_decision, is_other_fee_inquiry, early_details = None, False, {}
        active_topic = conv_state.get("active_topic")
        active_program = conv_state.get("active_program")
        named_prog = fees.find_program(message)       # context for the model, never an answer by itself
        if named_prog and named_prog != active_program:
            active_program = named_prog
            await set_state(active_program=named_prog)
        if require_contact_details and not (conv_state.get("welcome_actions_shown")
                                            or profile.get("welcome_actions_shown")):
            await set_state(welcome_actions_shown=True)
            await memory.update_profile(session_id, welcome_actions_shown=True)
        persona = intents.detect_user_persona(message, history, profile)
        # The student asked something new instead of answering the bot's last question: that question is not
        # waiting any more (a fee evaluation in progress stays, with its "continue" chip).
        stale = {}
        if (conv_state.get("dialogue") or {}).get("step") in ("topic_aspect", "program_aspect"):
            # a "which aspect?" question; the admission journey's steps (programme, board, marks...) are kept
            stale["dialogue"] = {k: v for k, v in (conv_state.get("dialogue") or {}).items() if k != "step"}
        if conv_state.get("offer"):
            stale["offer"] = None
        if stale:
            await set_state(**stale)
        shown_facts = list(conv_state.get("facts_shown") or [])
        sub_qs = semantic_router.decompose_multi_questions(message)
        if len(sub_qs) > 1:
            picked = []
            seen_fact_ids = set()
            for sq in sub_qs[:4]:
                for f in fact_service.retrieve(sq, k=3, exclude=shown_facts):
                    fid = getattr(f, "id", None) or str(f)
                    if fid not in seen_fact_ids:
                        seen_fact_ids.add(fid)
                        picked.append(f)
            picked = picked[:8]
        else:
            picked = fact_service.retrieve(message, k=6, exclude=shown_facts)
        facts_note = fact_service.format_facts_for_prompt(picked) if picked else None
        turn_telemetry = observability.PolicyTurnTelemetry(
            session_id=session_id, conversation_id=conversation_id, message=message,
            detected_intent="MODEL_FIRST", response_mode="model",
            routing_latency_ms=round((time.perf_counter() - started) * 1000, 2))
        log.info("model-first turn (session %s)", (session_id or "")[:8])
    else:
        log.info("structured turn (%s) session %s", structured, (session_id or "")[:8])

    if not model_first:
        from . import quick_facts
        # a phone number or callback request goes to the callback flow; several questions go to the multi-question step
        # below, which answers every part (a single quick fact would answer only one of them)
        qa = None if (step_answer or tools.find_phone(message) or intents.is_callback_request(message)
                      or compound.model_note(message)) else quick_facts.answer(message, profile)
        if qa:
            async for ev in _reply(qa.text, message, session_id, conversation_id, cards=list(qa.cards or []),
                                   suggestions=qa.chips, exact_chips=True,
                                   client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return
        # v4.15.1 (live chat): a fee question for a programme the student's marks don't qualify for gets the honest "not
        # eligible" answer with the programmes they can join, never a fee summary for a programme they can't join.
        if not step_answer and profile.get("percent") not in (None, "") and fee_intake.is_fee_enquiry(message or "") \
                and not tools.find_phone(message) and not intents.is_callback_request(message):
            asked_prog = fees.find_program(message or "") or (
                conv_state.get("active_program") if not fees.find_program(message or "") else None)
            blocked = fee_journey.not_eligible({"program": asked_prog}, profile) if asked_prog else None
            if blocked:
                async for ev in _reply(blocked["text"], message, session_id, conversation_id, suggestions=blocked["chips"],
                                       exact_chips=True, client=client, history=history, profile=profile,
                                       conv_state=conv_state):
                    yield ev
                return
        # v4.15.1 (2,000-student run): a cut-off question after "how to apply" was taken by the admission steps; it is
        # a figure SRU doesn't publish, so it is answered here, before any step can ask for marks.
        if _CUTOFF_FACT.search(message or "") and not step_answer \
                and not (conv_state.get("fee_intake") or {}).get("waiting_for"):
            async for ev in _reply(_CUTOFF_TEXT, message, session_id, conversation_id,
                                   suggestions=["Eligibility for B.Tech CSE", "Calculate my scholarship", "How do I apply?"],
                                   client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return
        if _SEATS_Q.search(message or "") and not step_answer:   # a figure SRU doesn't publish: said plainly
            async for ev in _reply(_SEATS_TEXT, message, session_id, conversation_id,
                                   suggestions=["How do I apply?", "Check my eligibility", "Talk to a counsellor"],
                                   client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return
        # ---- "What is the eligibility (for it)?": the RULE for the programme named or already being discussed, then
        # the offer to check the student's own marks (v4.13.0: information asked, information given; "am I eligible?"
        # is the action and still goes to the check).
        if not dlg_busy and _ELIGIBILITY_RULE_Q.search(message or "") and not re.search(r"\d", message or "") \
                and not _CUTOFF_FACT.search(message or "") and not intents.is_callback_request(message):
            rule_prog = fees.find_program(message) or (conv_state.get("dialogue") or {}).get("program") \
                or (conv_state.get("fee_intake") or {}).get("program") or conv_state.get("active_program") \
                or profile.get("program_interest")
            if rule_prog in fees.load_data()["programs"]:
                # the programme is now the one being discussed (an open "which branch?" is answered by it)
                dlg_now = {k: v for k, v in (conv_state.get("dialogue") or {}).items() if k != "step"}
                dlg_now["program"] = rule_prog
                await memory.update_conversation_state(session_id, conversation_id, active_program=rule_prog,
                                                       dialogue=dlg_now)
                conv_state["active_program"] = rule_prog
                conv_state["dialogue"] = dlg_now
                async for ev in _reply(eligibility.rule_text(rule_prog), message, session_id, conversation_id,
                                       suggestions=["Check my eligibility with my marks", f"{fees.short_name(rule_prog)} fees",
                                                    "Calculate my scholarship"],
                                       exact_chips=True, client=client, history=history, profile=profile,
                                       conv_state=conv_state):
                    yield ev
                return
        # ---- "Talk to a counsellor / a person" (v4.12.0): a short real attempt to reach a counsellor (it rings in the
        # admin panel), then a callback on the number on file. "Call me" stays the callback flow below.
        if not form and intents.is_connect_request(message) and not tools.find_phone(message):
            async for ev in _counsellor_connect(message, session_id, conversation_id, profile, ctx):
                yield ev
            return

        # ---- The fee evaluation agent (fee_journey): special consideration, concession picked, "final fee",
        # and the answers to its own questions (programme, proof, scholarship, hostel, bus). It works from the
        # conversation's saved selections, so a side question in between does not lose the progress.
        if not form:
            last_fee_args = conv_state.get("last_fee_args") or {}
            last_reply = next((h.get("text", "") for h in reversed(history) if h.get("role") in ("model", "assistant")),
                              "")
            fj = fee_journey.decide(message, conv_state.get(fee_journey.KEY), profile, {
                "program": (conv_state.get("active_program") or profile.get("program_interest")
                            or (conv_state.get("fee_intake") or {}).get("program") or last_fee_args.get("program")),
                # v4.15.1: a room type only when the student chose one ("AC 4 sharing"), never one the model assumed
                "hostel": last_fee_args.get("hostel") if last_fee_args.get("hostel") not in (None, "none") and (
                    fee_journey._read_hostel(message or "") or any(
                        fee_journey._read_hostel(h.get("text", "") or "") for h in history[-12:] if h.get("role") == "user"))
                    else None,
                "transport": True if last_fee_args.get("transport") else None,
                "last_reply": last_reply,
                "selected_concession": conv_state.get("selected_concession"),
                "fuzzy_concession": _concession_requested(message),
                "marks_corrected": bool(_MARKS_NOTE.get()) and not _other_program_named(message, conv_state),
                "evaluate_first": app_settings.get("fee_questions") == "evaluate_first",
                "offer": conv_state.get("offer"),
                "seed": f"{session_id}{len(history)}",
            })
            if fj:
                async def _save_state(**fields):
                    conv_state.update(fields)
                    await memory.update_conversation_state(session_id, conversation_id, **fields)
                async for ev in _run_fee_journey(fj, message, session_id, conversation_id, profile, _save_state):
                    yield ev
                return

        # ---- A fee question ("B.Tech CSE fees", "MBA fee?") evaluates first (v4.13.0, admin "fee_questions"): the
        # marks and eligibility, the merit scholarship, special concessions, hostel, then the FINAL fee, step by step
        # (fee_intake's counsellor steps -> fee_journey). "Just show the ... fee" gives the standard fee at once.
        if not form and not dlg_busy and _starts_fee_evaluation(message, conv_state):
            fee_prog = fees.find_program(message) or (conv_state.get("dialogue") or {}).get("program") \
                or conv_state.get("active_program") or profile.get("program_interest")
            if fee_prog not in fees.load_data()["programs"]:
                fee_prog = None
            start = {"counsellor_mode": True, **({"program": fee_prog} if fee_prog else {})}
            step = fee_intake.decide("Calculate my scholarship. " + message, profile, start, first_name=natural_name)
            if step and step.get("action") == "ask":
                conv_state["fee_intake"] = step["state"]
                await memory.update_conversation_state(session_id, conversation_id, fee_intake=step["state"],
                                                       **({"active_program": fee_prog} if fee_prog else {}))
                short = fees.short_name(fee_prog) if fee_prog else ""
                lead = (f"Before I give you the **{short}** fee, let's check your eligibility and scholarship, so any "
                        "merit scholarship or special concession you qualify for is included in your final fee."
                        if fee_prog else
                        "Before I give you the fee, let's check your eligibility and scholarship, so any merit "
                        "scholarship or special concession you qualify for is included in your final fee.")
                body = _FEE_STEP_OPENER.sub("", step["text"]).strip()
                if not fee_prog:
                    body = ("Which B.Tech branch are you interested in?" if "branch" in step["text"]
                            else "Which programme are you interested in?")
                chips = list(step.get("chips") or [])
                if fee_prog:
                    chips.append(f"Just show the {short} fee")
                async for ev in _say(f"{lead}\n\n{body}", message, session_id, conversation_id,
                                     cards=step.get("cards") or [], suggestions=chips, exact_chips=True, profile=profile):
                    yield ev
                return
            if step and step.get("action") == "calculate":
                # Everything is known already: the same evaluation as "Calculate my scholarship", at once.
                conv_state["fee_intake"] = start
                await memory.update_conversation_state(session_id, conversation_id, fee_intake=start)
                message = "Calculate my scholarship" + (f" for {fees.short_name(fee_prog)}" if fee_prog else "")

        # Our own fee-plan questions and requests are answered below, not by the topic clarification:
        # a concession picked in the table, "prepare my fee chart", the programme for a pending concession or
        # chart, and yes / no to the fee chart offer.
        fee_plan_turn = bool(
            _FEE_CHART_REQUEST.search(message or "") or _concession_requested(message)
            or ((conv_state.get("pending_concession") or conv_state.get("offer") == "fee_chart_program")
                and fees.find_program(message))
            or (conv_state.get("offer") == "fee_chart" and (_AFFIRM.match(message or "") or _DECLINE.match(message or ""))))
        # ---- "What scholarships does SRU give?" (v4.14.0, 1,000-student test): the merit scholarship slabs from the
        # official fee data, then the offer to work out the student's own. (It used to start the step questions at once.)
        if not fee_plan_turn and _GENERAL_SCHOLARSHIP.search(message or "") and not re.search(r"\d", message or "") \
                and not _OWN_FEE.search(message or "") \
                and _one_question(message, profile):
            sch_prog = fees.find_program(message or "") or conv_state.get("active_program") \
                or profile.get("program_interest") or "btech_cse"
            if sch_prog not in fees.load_data()["programs"]:
                sch_prog = "btech_cse"
            try:
                slabs = compound.scholarship_overview_text(sch_prog)
            except Exception:
                slabs = ""
            if slabs:
                text = slabs
                async for ev in _reply(text, message, session_id, conversation_id, client=client, history=history,
                                       profile=profile, conv_state=conv_state,
                                       suggestions=["Calculate my scholarship", "Special consideration"], exact_chips=True):
                    yield ev
                return

        # ---- Placements (v4.14.0, 1,000-student test): "how are the placements?", "highest package", "do students get
        # jobs after BBA" get the verified placement answer at once (it used to ask "what about placements?" first, or go
        # to the model). Guarantee / recruiters / training / internships each get their own answer.
        if not fee_plan_turn and _PLACEMENT_Q.search(message or "") and not tools.find_phone(message) \
                and not intents.is_callback_request(message) and _one_question(message, profile) \
                and not re.search(r"\b(?:fees?|cost|scholarship|eligib\w*|hostel|cut-?off)\b", message or "", re.I) \
                and (side_q or not (dlg_busy or (conv_state.get("dialogue") or {}).get("step"))) \
                and responses.placement_aspect(message) != "guarantee" \
                and not re.search(r"\b(?:this|that|my|the\s+same)\s+(?:branch|course|programme|program)\b", message or "", re.I) \
                and not (dialogue._broad_topic(message) == "placements" and len(re.findall(r"\w+", re.sub(
                    r"^\s*(?:and\s+)?(?:what|how)\s+about|^\s*tell\s+me\s+about|\b(?:the|please|pls|at\s+sru|in\s+sru)\b",
                    "", message or "", flags=re.I))) <= 2):
            # (a guarantee question keeps its approved answer; "this branch" needs the programme; a bare "placements"
            # still asks which aspect, as designed for broad topics)
            from app.services.card_service import PLACEMENT_EXCELLENCE_CARD, get_session_shown_cards, record_session_card
            p_text, p_chips, _aspect = responses.placement_reply(message, f"{session_id}{len(history)}")
            p_prog = fees.find_program(message or "")
            if p_prog and _aspect == "record":
                p_text = (f"Yes. SRU's placement support (training and campus drives with 150+ recruiters) is for every "
                          f"programme, including **{fees.short_name(p_prog)}**. " + p_text)
            p_scope = f"{session_id}:{conversation_id or ''}"
            p_cards = [] if "placement_card" in get_session_shown_cards(p_scope) else [PLACEMENT_EXCELLENCE_CARD]
            if p_cards:
                record_session_card(p_scope, "placement_card")
            await memory.update_conversation_state(session_id, conversation_id, active_topic="placements")
            async for ev in _reply(p_text, message, session_id, conversation_id, client=client, history=history,
                                   profile=profile, conv_state=conv_state, cards=p_cards, suggestions=p_chips):
                yield ev
            return

        # ---- Events, campus life, clubs, sports, hostel life and food (v4.14.0): answered from the approved facts and
        # the admin panel's events (campus_life.py), with the events' photo cards and the official videos. A word that
        # answers a pending step ("sports" for a concession) is left to that step; several questions go to compound.
        if not fee_plan_turn and not tools.find_phone(message) and not intents.is_callback_request(message):
            step_waiting = not side_q and bool(dlg_busy or (conv_state.get("dialogue") or {}).get("step")
                                or conv_state.get("pending_concession") or conv_state.get("offer")
                                or (conv_state.get(fee_journey.KEY) or {}).get("awaiting"))
            campus_key = campus_life.topic(message, waiting=step_waiting)
            if campus_key is None and conv_state.get("campus_offer") and _AFFIRM.match(message or "") \
                    and len((message or "").split()) <= 4:
                campus_key = conv_state.get("campus_offer")      # "yes" to "Would you like to see the other events?"
            if campus_key and _one_question(message, profile):
                ans = campus_life.answer(campus_key, message)
                told = list(conv_state.get("campus_told") or [])
                if campus_key in told and not campus_key.startswith("event:"):
                    ans = campus_life.recap(campus_key, ans, message)  # asked again: a short recap, not the same block
                told = (told + [campus_key])[-20:]
                campus_cards = []
                carousel = campus_life.event_cards(ans.event_ids)
                if carousel:
                    campus_cards.append(carousel)
                from app.services.video_service import create_video_card, get_keyword_videos, video_by_id
                vids = [v for v in (video_by_id(i) for i in ans.video_ids) if v]
                if not vids and ans.video_query:
                    shown = {v.get("id") for h in history or [] for c in (h.get("cards") or [])
                             if isinstance(c, dict) for v in (c.get("videos") or []) if isinstance(v, dict)}
                    vids = get_keyword_videos(ans.video_query, limit=2, exclude=shown)
                if vids:
                    campus_cards.append(create_video_card(vids[:2]))
                offer = "events" if campus_key.startswith("event:") else (
                    "clubs" if ans.text.rstrip().endswith("all 39 clubs?") else None)
                await memory.update_conversation_state(session_id, conversation_id, campus_offer=offer,
                                                       active_topic="campus_life", campus_told=told)
                async for ev in _reply(ans.text, message, session_id, conversation_id, client=client, history=history,
                                       profile=profile, conv_state=conv_state, cards=campus_cards, suggestions=ans.chips,
                                       exact_chips=ans.options,
                                       note="Answer only from these facts; do not add links or sources."):
                    yield ev
                return

        if not dlg_busy and not fee_plan_turn and not tools.find_phone(message) and not intents.is_callback_request(message) \
                and not intents.is_cancel_contact(message, bool(profile.get("last_lead_id"))):
            dlg = dialogue.decide(message, conv_state, profile, name=natural_name)
            if dlg:
                new_dialogue = dlg.get("state")
                if new_dialogue is not None:
                    conv_state["dialogue"] = new_dialogue
                    extra = {"active_program": new_dialogue["program"]} if new_dialogue.get("program") else {}
                    conv_state.update(extra)
                    await memory.update_conversation_state(session_id, conversation_id, dialogue=new_dialogue, **extra)
                if dlg.get("profile_updates"):
                    profile = await memory.update_profile(session_id, **dlg["profile_updates"])
                    ctx["profile"] = profile
                if dlg["kind"] == "reply":
                    async for ev in _say(dlg["text"], message, session_id, conversation_id,
                                         cards=dlg.get("cards") or [],
                                         suggestions=dlg.get("chips") or [], profile=profile, exact_chips=True,
                                         eligible=dlg.get("eligible")):
                        yield ev
                    return
                if dlg["kind"] == "rewrite":
                    message = dlg["message"]

        # ---- Semantic Routing & Approved Answer Policy Matching ----
        t0_routing = time.perf_counter()
        routing_decision = semantic_router.route_message(message, history, conv_state)
        routing_latency_ms = round((time.perf_counter() - t0_routing) * 1000, 2)

        # State preservation: detect interruptions to active admission dialogue
        is_admission_in_progress = bool(_intake_open(conv_state, message) or conv_state.get("admission_stage"))
        paused_intent = conv_state.get("paused_intent")
        if is_admission_in_progress and routing_decision.intent_id not in ("ADMISSION_DATA_INPUT", "ADMISSION_COUNSELLING"):
            paused_intent = conv_state.get("current_intent") or "ADMISSION_COUNSELLING"

        # Map semantic policy intent to agent execution intent
        _SEMANTIC_TO_AGENT_INTENT = {
            "ABOUT_SRU": "ABOUT_SRU_QUERY",
            "WHY_CHOOSE_SRU": "WHY_CHOOSE_SRU_QUERY",
            "PLACEMENT_GUARANTEE": "PLACEMENT_GUARANTEE_QUERY",
            "ADMISSION_GUARANTEE": "ADMISSION_GUARANTEE_QUERY",
            "HOSTEL_CURFEW": "HOSTEL_CURFEW_RULES_QUERY",
            "HOSTEL_INFO": "HOSTEL_INFO_QUERY",
            "FUTURE_YEAR_FEE": "FUTURE_YEAR_FEE_QUERY",
            "SPECIAL_CONCESSIONS": "SPECIAL_CONCESSIONS_QUERY",
            "DATE_QUERY": "DATE_QUERY",
            "LAB_FACILITIES": "LAB_FACILITIES_QUERY",
        }
        legacy_intent = intents.classify_agent_intent(message, conv_state)
        _SPECIFIC_FLOW_INTENTS = {
            "FEE_TREE_QUERY", "BTECH_TREE_QUERY", "BTECH_CSE_FEE_QUERY", "BTECH_AI_ROBOTICS_FEE_QUERY",
            "BTECH_ECE_FEE_QUERY", "BTECH_CORE_FEE_QUERY", "MANAGEMENT_FEE_QUERY", "AGRICULTURE_FEE_QUERY",
            "COMP_APP_FEE_QUERY", "DESIGN_FEE_QUERY", "CAMPUS_TOUR_DISPATCH", "CAMPUS_TOUR_VIRTUAL",
            "CAMPUS_VISIT_BOOKING_WITH_DATE", "CAMPUS_VISIT_BOOKING", "CAMPUS_VISIT_INFO", "JOIN_SRU_QUERY",
            "CONFUSION_QUERY", "NEXT_GEN_TECH_QUERY", "ALL_PROGRAMS_QUERY", "OTHER_FEES_QUERY",
            "HOSTEL_FEE_QUERY", "HOSTEL_MESS_QUERY", "HOSTEL_SAFETY_QUERY", "COMBINED_FEE_HOSTEL_QUERY",
            "CAMPUS_CANTEEN_QUERY", "ACADEMIC_EVALUATION_QUERY", "ABOUT_SRU_QUERY",
        }
        if step_answer and not intents.is_callback_request(message):
            intent = "GENERAL"            # the open fee step answers it (below)
        elif legacy_intent in _SPECIFIC_FLOW_INTENTS:
            intent = legacy_intent
        elif routing_decision.policy_id and not routing_decision.is_fallback:
            mapped_intent = _SEMANTIC_TO_AGENT_INTENT.get(routing_decision.intent_id)
            intent = mapped_intent if mapped_intent else legacy_intent
        else:
            intent = legacy_intent


        # A fixed overview (a programme, labs, canteen, evaluation, all programmes...) is given once per
        # conversation. Asked again, the question goes to the model with the conversation, which answers
        # the follow-up instead of re-sending the same block.
        if intent in _OVERVIEW_INTENTS:
            given = list(conv_state.get("overviews_given") or [])
            if intent in given:
                intent = "GENERAL"
            else:
                await set_state(overviews_given=(given + [intent])[-20:])

        # Check if welcome quick-action cards have been shown after lead collection
        welcome_actions_shown = bool(
            conv_state.get("welcome_actions_shown")
            or profile.get("welcome_actions_shown")
        )
        answered_before = any(h.get("role") in ("model", "assistant") for h in history or [])
        if require_contact_details and not welcome_actions_shown and existing_name and existing_phone \
                and (intents.small_talk(message) != "greeting" or answered_before):
            # (a "hi" after earlier answers in this chat is not a first visit: no welcome again, v4.14.0)
            # A real question as the first message: answer it, and do not show the welcome greeting later.
            await set_state(welcome_actions_shown=True)
            await memory.update_profile(session_id, welcome_actions_shown=True)
            welcome_actions_shown = True
        if require_contact_details and not welcome_actions_shown and existing_name and existing_phone:
            await set_state(welcome_actions_shown=True)
            await memory.update_profile(session_id, welcome_actions_shown=True)
            card_service.record_session_card(f"{session_id}:{conversation_id or ''}", "welcome_actions")
            first_name = _first_name(existing_name)
            first_name = first_name[:1].upper() + first_name[1:]
            # The quick-action tiles are already on the opening welcome message, so they are not repeated here.
            welcome_text = (
                f"Welcome to SR University, **{first_name}**! 🎓\n\n"
                "I'm **SRU Buddy**, your official AI companion. Tap one of the quick options above, or ask me "
                "anything about programmes, fees, scholarships or campus life."
            )
            async for ev in _say(
                welcome_text,
                message,
                session_id,
                conversation_id,
                suggestions=list(card_service.POST_WELCOME_CHIPS),
                exact_chips=True,
            ):
                yield ev
            return

        # ---- One message, several questions: answer each part (compound.plan has the safety rules) ----
        compound_plan = None
        if not form and not dlg_busy and not fee_plan_turn and not _concession_requested(message) \
                and not conv_state.get("offer"):
            compound_plan = compound.plan(message, profile)
        if compound_plan:
            log.info("Agent compound query: %d parts for '%s'", len(compound_plan), message[:60])
            resolved = await structured_flows.resolve_compound_plan(
                compound_plan,
                message,
                session_id,
                conversation_id,
                resolve_sub_query=_resolve_sub_query,
                with_resume_chip=_with_resume_chip,
            )
            if resolved:
                # A side question during an unfinished fee evaluation keeps the "continue" button (docs/36 rule 2).
                async for ev in _reply(
                    resolved["text"],
                    message,
                    session_id,
                    conversation_id,
                    cards=resolved["cards"],
                    suggestions=resolved["suggestions"],
                    exact_chips=True,
                    resume=False,
                    client=client, history=history, profile=profile, conv_state=conv_state,
                    note="The message asks several things: answer every part, each in its own short section.",
                ):
                    yield ev
                return

        # Persist preserved state variables
        await set_state(
            current_intent=routing_decision.intent_id,
            paused_intent=paused_intent,
            collected_data=profile or {},
            pending_question=conv_state.get("pending_user_question"),
        )

        turn_telemetry = observability.PolicyTurnTelemetry(
            session_id=session_id,
            conversation_id=conversation_id,
            message=message,
            detected_intent=routing_decision.intent_id,
            selected_policy_id=routing_decision.policy_id,
            policy_version=routing_decision.policy_version,
            response_mode=routing_decision.response_mode.value if hasattr(routing_decision.response_mode, "value") else str(routing_decision.response_mode),
            retrieved_evidence_ids=routing_decision.evidence_ids,
            routing_confidence=routing_decision.confidence,
            fallback_decision=routing_decision.is_fallback,
            fallback_reason=routing_decision.fallback_reason,
            routing_latency_ms=routing_latency_ms,
        )

        # Track conversational topic and program across turns
        active_topic = conv_state.get("active_topic")
        active_program = conv_state.get("active_program")

        current_topic = followups.topic_of(message, used, active_topic=active_topic)
        if current_topic:
            active_topic = current_topic
            await set_state(active_topic=active_topic)

        # Track conversational program and course changes across turns. "Change CSE to ECE" / "switch from MBA
        # to BBA" names two programmes: the one after "to" is the student's new choice.
        explicit_msg_prog = _switch_target_program(message) or fees.find_program(message)
        previous_active_prog = conv_state.get("active_program") or (profile.get("program_interest") if profile else None)

        if explicit_msg_prog:
            active_program = explicit_msg_prog
            if profile is not None:
                profile["program_interest"] = explicit_msg_prog
            await memory.update_profile(session_id, program_interest=explicit_msg_prog)

            # Handle course switch
            if previous_active_prog and previous_active_prog != explicit_msg_prog:
                data = fees.load_data()
                old_level = data.get("programs", {}).get(previous_active_prog, {}).get("level", "ug")
                new_level = data.get("programs", {}).get(explicit_msg_prog, {}).get("level", "ug")
                current_intake = dict(conv_state.get("fee_intake") or {})
                if current_intake:
                    current_intake["program"] = explicit_msg_prog
                    if old_level != new_level:
                        for k_clr in (
                            "board", "board_label", "board_key", "academic_stage", "stage_label",
                            "raw_marks", "max_marks", "percent", "is_projected", "admission_route",
                            "route_label", "eapcet_rank", "jee_percentile", "ib_score"
                        ):
                            current_intake.pop(k_clr, None)
                            if profile is not None:
                                profile.pop(k_clr, None)
                await set_state(
                    active_program=explicit_msg_prog,
                    fee_flow_prog=explicit_msg_prog,
                    fee_tree_step=None,
                    fee_intake=current_intake if current_intake.get("waiting_for") else None,
                )
            else:
                current_intake = dict(conv_state.get("fee_intake") or {})
                if current_intake.get("waiting_for"):
                    current_intake["program"] = explicit_msg_prog
                    await set_state(
                        active_program=active_program,
                        fee_flow_prog=active_program,
                        fee_intake=current_intake,
                    )
                else:
                    await set_state(
                        active_program=active_program,
                        fee_flow_prog=active_program,
                    )
        else:
            # The student's latest choice wins: program_interest is also changed from Settings > My details and by
            # the "update my programme" tool, which do not touch this conversation's state.
            active_program = (
                (profile.get("program_interest") if profile else None)
                or conv_state.get("active_program")
                or ((conv_state.get("fee_intake") or {}).get("program"))
            )
            if active_program:
                intake_prog = (conv_state.get("fee_intake") or {}).get("program")
                if intake_prog and fees.find_program(str(intake_prog)) not in (None, active_program):
                    # an estimate started for the previous programme continues for the new one
                    await set_state(fee_intake={**conv_state["fee_intake"], "program": active_program},
                                    fee_flow_prog=active_program)
                await set_state(active_program=active_program)
                if profile is not None and not profile.get("program_interest"):
                    profile["program_interest"] = active_program
                    await memory.update_profile(session_id, program_interest=active_program)

        # Early extract academic facts (board, stage, marks, rank) so they are preserved across turns
        early_details = fee_intake.parse_details(message)
        academic_updates = {}
        for k in (
            "board", "board_label", "board_key", "academic_stage", "stage_label",
            "raw_marks", "max_marks", "percent", "is_projected", "admission_route",
            "route_label", "eapcet_rank", "jee_percentile", "ib_score"
        ):
            if early_details.get(k) is not None:
                if profile is not None:
                    profile[k] = early_details[k]
                academic_updates[k] = early_details[k]

        # Synchronize percentage when raw marks are corrected in a multi-turn session
        if early_details.get("raw_marks") is not None:
            old_raw = (profile or {}).get("raw_marks")
            new_raw = early_details["raw_marks"]
            if old_raw and old_raw != new_raw and not early_details.get("percent"):
                max_m = (profile or {}).get("max_marks")
                if max_m and max_m > 0:
                    new_pct = round((new_raw / max_m) * 100, 2)
                    academic_updates["percent"] = new_pct
                    if profile is not None:
                        profile["percent"] = new_pct
                else:
                    academic_updates["percent"] = None
                    if profile is not None:
                        profile["percent"] = None
        if early_details.get("generic_btech") and not (profile or {}).get("degree_interest") and not (profile or {}).get("program_interest"):
            academic_updates["degree_interest"] = "btech"
            academic_updates["generic_btech"] = True
            if profile is not None:
                profile["degree_interest"] = "btech"
                profile["generic_btech"] = True
        if academic_updates:
            await memory.update_profile(session_id, **academic_updates)
            current_intake = dict(conv_state.get("fee_intake") or {})
            if current_intake.get("waiting_for"):
                current_intake.update(academic_updates)
                await set_state(fee_intake=current_intake)

        # Detect user persona and style
        persona = intents.detect_user_persona(message, history, profile)
        if persona == "parent" and not profile.get("is_parent"):
            profile["is_parent"] = True
            await memory.update_profile(session_id, is_parent=True)

        # Extract name if user provided one
        awaiting_name = bool(conv_state.get("awaiting_name"))
        extracted_name = intents.extract_name(message, bare_ok=awaiting_name)
        if extracted_name and not profile.get("name"):
            profile["name"] = extracted_name
            await memory.update_profile(session_id, name=extracted_name)
            await set_state(name_asked=True, awaiting_name=False)

        # ---- Handle Turn 2 after name was requested ----
        if awaiting_name:
            if extracted_name:
                await set_state(awaiting_name=False)
                pending_q = conv_state.get("pending_user_question")
                if pending_q:
                    # Answer the question asked in Turn 1 immediately
                    await set_state(pending_user_question=None)
                    message = pending_q
                    intent = intents.classify_agent_intent(message, conv_state)
                else:
                    # User had only sent a greeting in Turn 1
                    async for ev in _small_talk_reply("name_given", message, session_id, conversation_id, client=client,
                                                      history=history, profile=profile, conv_state=conv_state,
                                                      suggestions=_SMALL_TALK_CHIPS,
                                                      name=_first_name(extracted_name)):
                        yield ev
                    return
            else:
                # User declined, skipped, or asked another question
                await set_state(awaiting_name=False)
                pending_q = conv_state.get("pending_user_question")
                if pending_q and intents.is_refusal_or_skip(message):
                    await set_state(pending_user_question=None)
                    message = pending_q
                    intent = intents.classify_agent_intent(message, conv_state)
                elif pending_q:
                    await set_state(pending_user_question=None)

        # ---- 1. Things the code can answer by itself ------------------------------------------
        if intent == "DATE_QUERY":
            async for ev in _say(f"Today is {date.today():%B %d, %Y}.", message, session_id, conversation_id,
                                 suggestions=["Plan a campus visit", "What are the B.Tech CSE fees?",
                                              "Hostel rules & curfew"]):
                yield ev
            return

        if intent == "CONFUSION_QUERY":
            async for ev in _reply("Sorry for the confusion! I'm here to help clarify. Could you share what specific details you're looking for? "
                                   "I can help with B.Tech & PG programs, fee structure, scholarships, placements, or visiting the campus.",
                                   message, session_id, conversation_id,
                                   suggestions=["B.Tech CSE fees", "Scholarship slabs", "Placements at SRU", "Plan a campus visit"],
                                   client=client, history=history, profile=profile, conv_state=conv_state,
                                   note="The student is confused: use the conversation to see what about, clear it up in "
                                        "one or two sentences, and ask one specific question only if still needed."):
                yield ev
            return

        if intent == "JOIN_SRU_QUERY":
            flow_card = fee_flow.build_school_selection_card()
            async for ev in _reply(
                "That's great! Which course or degree are you interested in pursuing at SR University?\n\n"
                "We offer diverse undergraduate and postgraduate programs across Engineering, Management, "
                "Agriculture, Computer Applications, and Sciences. Choose an academic area below or tell me your preferred course:",
                message,
                session_id,
                conversation_id,
                cards=[flow_card],
                suggestions=["B.Tech Engineering", "MBA", "BBA", "B.Sc (Hons) Agriculture", "Explore all programs"],
                client=client, history=history, profile=profile, conv_state=conv_state,
                note="Ask which course they want (one question); never assume a course.",
            ):
                yield ev
            return

        # Greetings and small talk: written by the model for this conversation (v4.13.0: no greeting bank).
        chat = intents.small_talk(message) if intent not in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO") else None
        if chat:
            if chat == "greeting" and not profile.get("name"):
                # No name on file (the widget's contact form normally collects it): the next message is read as the name.
                await set_state(awaiting_name=True, name_asked=True)
            kind = chat if chat in _SMALL_TALK_BRIEFS else "greeting"
            if chat == "greeting" and not profile.get("name"):
                kind = "greeting_ask_name"
            step = _open_step(profile, conv_state) if chat in ("greeting", "how_are_you") and profile.get("name") else None
            if step:
                # A greeting in the middle of the fee steps: say hello, then the same question again (nothing reset).
                first = _first_name(profile.get("name")) if profile.get("address_by_name") is not False else ""
                name_bit = f", {first}" if first else ""
                hello = (_vary(["I'm doing well, thanks for asking!", "All good here, thank you!",
                                "Doing great, thanks!"], session_id, message, len(history or []))
                         if chat == "how_are_you" else
                         _vary([f"Hi{name_bit}!", f"Hello{name_bit}!", f"Hey{name_bit}!"],
                               session_id, message, len(history or [])))
                if _use_model(client):   # the hello is written for this conversation; the step itself stays exact
                    words = await _model_words(
                        "REPLY BRIEF: The student said hello (or asked how you are) in the middle of their fee estimate. "
                        "Reply warmly in ONE short sentence (use their first name if known) and say you'll carry on with "
                        "the estimate. Do not ask any question and do not mention amounts.", message, session_id,
                        history=history, profile=profile, conv_state=conv_state, client=client)
                    if words and "?" not in words and len(words) < 200:
                        hello = words.strip()
                if step.get("fee_state"):
                    await set_state(**{fee_journey.KEY: step["fee_state"]})
                joined = hello if re.search(r"carry on|continue|pick up", hello, re.I) else \
                    f"{hello} " + _vary(["Let's carry on with your fee estimate.", "Let's pick up your fee estimate.",
                                         "We were in the middle of your fee estimate, so let's continue."],
                                        session_id, len(history or []))
                async for ev in _say(f"{joined}\n\n{step['text']}", message,
                                     session_id, conversation_id, cards=step["cards"], suggestions=step["chips"],
                                     exact_chips=True, profile=profile, resume=False):
                    yield ev
                return
            # Starting points after a greeting; nothing after "thanks" / "bye" (the student is wrapping up).
            chips = [] if chat in ("thanks", "bye") else _SMALL_TALK_CHIPS
            async for ev in _small_talk_reply(kind, message, session_id, conversation_id, client=client, history=history,
                                              profile=profile, conv_state=conv_state, suggestions=chips):
                yield ev
            return

        # ---- 1b. Deterministic quick responses (placement assistance, special concessions, next-gen tech, fee tree, all programs) ----
        # "Change my academic details / marks": forget them for this chat and ask again, one step at a time.
        _has_marks = any(fee_intake.parse_details(message).get(k) is not None for k in ("raw_marks", "percent"))
        if _CHANGE_ACADEMIC.search(message) and not tools.find_phone(message) and not _has_marks:
            keys = [k for k in fee_intake._ACADEMIC_FIELDS if profile.get(k) not in (None, "")]
            if keys or (conv_state.get("fee_intake") or {}).get("ineligible"):
                profile = await memory.remove_profile_keys(session_id, *keys) if keys else profile
                ctx["profile"] = profile
                prog = active_program or (conv_state.get("fee_intake") or {}).get("program")
                fresh_intake = {"counsellor_mode": True, **({"program": prog} if prog else {})}
                step = fee_intake.decide("Calculate my scholarship", profile, fresh_intake)
                if step and step.get("action") == "ask":
                    await set_state(fee_intake=step["state"])
                    async for ev in _say("No problem, let's update them. " + step["text"].replace("Sure! ", "").replace(
                            "Sure, ", ""), message, session_id, conversation_id, cards=step.get("cards") or [],
                            suggestions=step.get("chips") or [], exact_chips=True):
                        yield ev
                    return

        # (v4.11.0) A concession picked or asked for ("add the sibling concession to my fee") is handled by the fee
        # evaluation agent above (fee_journey): it is evaluated, never applied straight away.

        # The complete first-year fee chart (asked for, or "yes" to the offer made after a fee with hostel or
        # transport): every line from the official fee data, with a Share button on the card.
        offer = conv_state.get("offer")
        wants_chart = bool(_FEE_CHART_REQUEST.search(message or "")) or (
            offer in ("fee_chart", "fee_chart_program") and bool(_AFFIRM.match(message or "")))
        if offer == "fee_chart_program" and fees.find_program(message):
            wants_chart = True
        if offer and not wants_chart:
            await set_state(offer=None)
            if offer == "fee_chart" and _DECLINE.match(message or ""):
                async for ev in _say("No problem! What else would you like to know?", message, session_id,
                                     conversation_id):
                    yield ev
                return
        if wants_chart:
            last = conv_state.get("last_fee_args") or {}
            program = fees.find_program(message) or last.get("program") or active_program
            if not program:
                await set_state(offer="fee_chart_program")
                async for ev in _say("Sure! Which programme should the fee chart be for?", message, session_id,
                                     conversation_id, suggestions=["B.Tech CSE", "B.Tech ECE", "B.Tech AI & Robotics", "BBA"],
                                     exact_chips=True):
                    yield ev
                return
            said = _fee_args_from_message(message, profile) or {}
            hostel = said.get("hostel") or (last.get("hostel") if last.get("program") == program else None) or "none"
            transport = bool(said.get("transport") or (last.get("transport") if last.get("program") == program else False))
            chart = fee_plan.full_fee_chart(program, profile, hostel=hostel, transport=transport,
                                            concession=conv_state.get("selected_concession"))
            if chart:
                chart["share_text"] = fee_plan.chart_share_text(chart)
                await set_state(offer=None, active_program=program)
                chips = ["How is the fee paid each semester?", "How do I apply for 2027-28?"]
                if not conv_state.get("selected_concession"):
                    chips.insert(0, "Special category concessions")
                if hostel == "none":
                    chips.insert(0, f"Add hostel to my {fees.short_name(program)} fee")
                async for ev in _say(f"Here's your complete {chart['academic_year']} fee chart for **{chart['program']}**. "
                                     "Tap **Share** to send it to your family.", message, session_id, conversation_id,
                                     cards=[{"type": "fee_plan", "data": chart}], suggestions=chips[:3], exact_chips=True):
                    yield ev
                return

        if intent in ("PLACEMENT_GUARANTEE_QUERY", "PLACEMENT_INFO_QUERY"):
            # A short answer to the aspect asked (record, recruiters, training, internships, guarantee); the
            # placement card once per conversation, under the record / recruiters answers.
            from app.services.card_service import PLACEMENT_EXCELLENCE_CARD, get_session_shown_cards, record_session_card
            reply, chips, aspect = responses.placement_reply(message, f"{session_id}{len(history)}{message}")
            scope = f"{session_id}:{conversation_id or ''}"
            cards_to_show = []
            if aspect in ("record", "recruiters", "guarantee") and "placement_highlights" not in get_session_shown_cards(scope):
                cards_to_show = [PLACEMENT_EXCELLENCE_CARD]
                record_session_card(scope, "placement_highlights")
            await set_state(placement_seen=True)
            async for ev in _reply(reply, message, session_id, conversation_id,
                                 cards=cards_to_show, suggestions=chips, client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        if intent == "ADMISSION_GUARANTEE_QUERY":
            await set_state(fee_intake=None)
            async for ev in _reply(_ADMISSION_GUARANTEE_TEXT, message, session_id, conversation_id,
                                 suggestions=_ADMISSION_GUARANTEE_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        if intent == "FUTURE_YEAR_FEE_QUERY":
            await set_state(fee_intake=None)
            text = _FUTURE_YEAR_FEE_TEXT
            named = fees.find_program(message)
            if named:
                # The programme asked about: its latest verified figure, clearly labelled as 2027-28.
                prog = fees.load_data()["programs"][named]
                text = text.replace(
                    "\n\nWould you like the 2027-28 fees for a particular programme?",
                    f"\n\nThe latest verified figure for **{fees.clean_program_name(named)}** is the "
                    f"{config.ADMISSION_YEAR} tuition of **{fees.inr(prog['tuition_per_year'])} per year** "
                    f"(yearly increase for students admitted in {config.ADMISSION_YEAR}: "
                    f"{fees.inr(prog.get('yearly_increase', 0))}). Would you like the full {config.ADMISSION_YEAR} "
                    f"fee breakdown for it?")
            async for ev in _reply(text, message, session_id, conversation_id,
                                 suggestions=_FUTURE_YEAR_FEE_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        # A cut-off / closing-rank question asks for a figure SRU doesn't publish: say so (never the scholarship steps).
        if _CUTOFF_FACT.search(message or "") and not (conv_state.get("fee_intake") or {}).get("waiting_for"):
            async for ev in _reply(_CUTOFF_TEXT, message, session_id, conversation_id,
                                   suggestions=["Eligibility for B.Tech CSE", "Calculate my scholarship", "How do I apply?"],
                                   client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        # A student describing a special category ("my brother studies at SRU, any discount?"): the concessions, with
        # that category named, not the scholarship steps (v4.13.0, docs/36 rule 1: the meaning before the keyword).
        asks_discount = bool(_DISCOUNT_ASK.search(message or ""))
        group = fee_plan.concessions_for_group(message) if asks_discount and not fee_plan.find_concession(message) else []
        described = fee_plan.infer_concession(message) if asks_discount and not group else None
        if intent == "SPECIAL_CONCESSIONS_QUERY" or described or group:
            # The answer IS the table (pick a row to apply it to your fee), so it is shown every time it is asked,
            # with a one-line lead instead of the list in text.
            data = fees.special_concessions()
            lead = responses.special_concessions_lead(data, active_program)
            if group:
                lead = ("These official concessions may fit:\n\n"
                        + "\n".join(f"• **{g['label']}**: {fees.inr(g['amount'])} a year" for g in group)
                        + "\n\nEach is applied only after the Admissions Office verifies the proof: pick the one that "
                          "applies below to see what it would mean for your fee.")
            elif described:
                lead = (f"The **{described['label']}** concession (**{fees.inr(described['amount'])} a year**) looks like "
                        "it fits. It is applied only after the Admissions Office verifies the proof: pick it below to see "
                        "what it would mean for your fee.")
            async for ev in _reply(lead, message,
                                   session_id, conversation_id,
                                   used=[{"name": "get_special_concessions", "status": "ok", "is_action": False}],
                                   cards=[fee_plan.concession_card(active_program, in_evaluation=False)],
                                   suggestions=["Calculate my scholarship", "Documents needed for the concession"],
                                   exact_chips=True, client=client, history=history, profile=profile,
                                   conv_state=conv_state):
                yield ev
            return

        if intent == "NEXT_GEN_TECH_QUERY":
            async for ev in _reply(_NEXT_GEN_TECH_TEXT, message, session_id, conversation_id,
                                 suggestions=["Fee for AI & Robotics", "B.Tech CSE fee structure",
                                              "Calculate my scholarship", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        if intent == "ALL_PROGRAMS_QUERY":
            async for ev in _reply(_ALL_PROGRAMS_TEXT, message, session_id, conversation_id,
                                 suggestions=["Fee Structure 2027-28", "Next-Gen Tech Programs",
                                              "Special Concessions", "Calculate my scholarship"], client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        if intent == "OTHER_FEES_QUERY" and (_is_mock_or_test_client(client) or client is None):
            from app.services.card_service import OTHER_FEES_CARD, get_session_shown_cards, record_session_card
            cards_to_show = []
            if "fee_breakdown" not in get_session_shown_cards(f"{session_id}:{conversation_id or ''}"):
                cards_to_show = [OTHER_FEES_CARD]
                record_session_card(f"{session_id}:{conversation_id or ''}", "fee_breakdown")
            async for ev in _reply(responses._OTHER_FEES_TEXT, message, session_id, conversation_id,
                                 cards=cards_to_show,
                                 suggestions=responses._OTHER_FEES_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                yield ev
            return

        if bool(tools.find_phone(message) or intents.is_callback_request(message)):
            canned_intents = (
                "FEE_TREE_QUERY", "BTECH_TREE_QUERY", "BTECH_CSE_FEE_QUERY", "BTECH_AI_ROBOTICS_FEE_QUERY",
                "BTECH_ECE_FEE_QUERY", "BTECH_CORE_FEE_QUERY", "MANAGEMENT_FEE_QUERY", "AGRICULTURE_FEE_QUERY",
                "COMP_APP_FEE_QUERY", "DESIGN_FEE_QUERY", "HOSTEL_INFO_QUERY", "HOSTEL_MESS_QUERY",
                "HOSTEL_CURFEW_RULES_QUERY", "HOSTEL_SAFETY_QUERY", "HOSTEL_FEE_QUERY", "COMBINED_FEE_HOSTEL_QUERY",
                "CAMPUS_CANTEEN_QUERY", "ACADEMIC_EVALUATION_QUERY", "ALL_PROGRAMS_QUERY", "OTHER_FEES_QUERY",
                "LAB_FACILITIES_QUERY", "WHY_CHOOSE_SRU_QUERY", "ABOUT_SRU_QUERY", "ADMISSION_GUARANTEE_QUERY",
                "FUTURE_YEAR_FEE_QUERY", "BTECH_PROGRAMS_QUERY", "PROGRAM_AI_ROBOTICS_QUERY", "PROGRAM_CSE_QUERY",
                "PROGRAM_ECE_QUERY", "PROGRAM_CORE_QUERY", "PROGRAM_MANAGEMENT_QUERY", "PROGRAM_AGRICULTURE_QUERY",
                "PROGRAM_COMP_APP_QUERY", "PROGRAM_DESIGN_QUERY", "ELIGIBILITY_QUERY",
            )
            if intent in canned_intents:
                intent = "GENERAL"
        # The scholarship steps asked "which programme?": the programme named is the answer to that question,
        # not a request for the programme's overview.
        if (conv_state.get("fee_intake") or {}).get("waiting_for") == "program" and intent.startswith("PROGRAM_"):
            intent = "GENERAL"

        _SPECIFIC_SUBTOPIC_KEYWORDS = (
            "cyber", "cybersecurity", "security", "cloud", "data science",
            "robotics", "ece", "vlsi", "eee", "civil", "mechanical", "biotech", "agriculture",
            "bba", "mba", "bca", "mca", "b.des", "design", "fee", "fees", "cost", "price",
            "scholarship", "eligibility", "hostel", "cutoff", "sports",
            "library", "canteen", "mess", "curfew", "timing", "bus", "transport", "syllabus",
            "curriculum", "available", "offered", "how to apply",
        )
        # Short words are matched as whole words: "ai" must not match "detail", nor "cs" "physics".
        _SPECIFIC_SUBTOPIC_WORDS = re.compile(
            r"\b(?:vs|versus|compare|comparison|difference|better|easier|cse|cs|aiml|ai|artificial\s+intelligence|"
            r"machine\s+learning)\b",
            re.IGNORECASE,
        )
        if intent in ("WHY_CHOOSE_SRU_QUERY", "ABOUT_SRU_QUERY") and (
            any(k in (message or "").lower() for k in _SPECIFIC_SUBTOPIC_KEYWORDS)
            or _SPECIFIC_SUBTOPIC_WORDS.search(message or "")
        ):
            intent = "GENERAL"

        # ---- Questions about the university itself: why SRU, about SRU, rankings, accreditation, research,
        # startups, international links, campus life, and challenges ("is SRU bad?", "is X better?").
        # The answer is built from the verified facts retrieved for THIS question (fact_service.retrieve), not
        # from a fixed text: facts already told in this conversation are skipped, so a repeat brings new
        # information. With a language model, the facts go into the prompt and the model writes the answer;
        # without one, responses.facts_reply frames them. University-reported claims are attributed.
        if intent == "WHY_CHOOSE_SRU_QUERY" and history and _BARE_WHY.match(message or ""):
            intent = "GENERAL"   # "why?" after an answer asks about that answer, not "why choose SRU?"
        fact_aspects = fact_service.detect_aspects(message)
        # (A step that is waiting for marks or a board does not stop this: "is SRU NBA accredited?" in the middle
        # of the scholarship steps is a new question; the transactional check keeps answers like "85%" out.)
        about_university = not step_answer and (intent in ("WHY_CHOOSE_SRU_QUERY", "ABOUT_SRU_QUERY") or (
            intent == "GENERAL" and not _TRANSACTIONAL_WORDS.search(message or "")
            and (set(fact_aspects) & _UNIVERSITY_FACT_ASPECTS
                 or (responses._CHALLENGE.search(message or "") and _NAMES_SRU.search(message or "")))))
        facts_note = None
        if about_university:
            shown_facts = list(conv_state.get("facts_shown") or [])
            # A challenge ("is SRU bad?", "is X better?") is answered with SRU's strongest distinctions first.
            lookup_aspects = fact_aspects or (["rankings", "placements", "accreditation"]
                                              if responses._CHALLENGE.search(message or "") else [])
            picked = fact_service.retrieve(message, k=4, exclude=shown_facts, aspects=lookup_aspects)
            recap = bool(picked) and all(f.fact_id in shown_facts for f in picked)
            # Asked "why SRU?" again: the new facts are framed as "a few more things".
            repeat = not recap and bool(shown_facts) and intent in ("WHY_CHOOSE_SRU_QUERY", "ABOUT_SRU_QUERY")
            new_ids = [f.fact_id for f in picked if f.fact_id not in shown_facts]
            await set_state(facts_shown=(shown_facts + new_ids)[-30:])
            from app.services.card_service import get_session_shown_cards, record_session_card
            scope = f"{session_id}:{conversation_id or ''}"
            cards_to_show = []
            if intent in ("WHY_CHOOSE_SRU_QUERY", "ABOUT_SRU_QUERY") and "why_sru_video" not in get_session_shown_cards(scope):
                from app.services.video_service import get_relevant_videos, get_keyword_videos, create_video_card
                vids = get_relevant_videos(message, limit=2) or get_keyword_videos(message, limit=2, prefer_campus=True)
                vid_card = create_video_card(vids) if vids else None
                if vid_card:
                    cards_to_show = [vid_card]
                    record_session_card(scope, "why_sru_video")
            if client is None or _is_mock_or_test_client(client):
                text_to_say, fact_chips = responses.facts_reply(
                    message, picked, f"{session_id}{len(history)}{message}", lookup_aspects, repeat=repeat, recap=recap)
                async for ev in _reply(text_to_say, message, session_id, conversation_id, cards=cards_to_show,
                                     suggestions=fact_chips, exact_chips=True, client=client, history=history, profile=profile, conv_state=conv_state,
                                     facts=(fact_service.format_facts_for_prompt(picked) if picked else None),
                                     note=("The student asked about SRU again: give the new facts, not a repeat of earlier "
                                           "points." if repeat else None)):
                    yield ev
                return
            cards.extend(c for c in cards_to_show if c not in cards)
            facts_note = fact_service.format_facts_for_prompt(picked)

        is_course_comparison = bool(re.search(r"\b(?:vs|versus|better|easier|compare|difference\s+between)\b", message or "", re.IGNORECASE))
        if (intent == "BRANCH_GUIDANCE_QUERY" or intents.is_branch_guidance_query(message)) and not is_course_comparison:
            await set_state(active_topic="career_guidance")
            if client is None or _is_mock_or_test_client(client):
                raw_marks = early_details.get("raw_marks") or (profile.get("raw_marks") if profile else None)
                bg_text = responses.get_branch_guidance_text(raw_marks, session_id=session_id)
                async for ev in _reply(bg_text, message, session_id, conversation_id,
                                     suggestions=responses._BRANCH_GUIDANCE_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "FEE_TREE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step="category")
                flow_card = fee_flow.build_school_selection_card()
                async for ev in _say(_FEE_TREE_TEXT, message, session_id, conversation_id,
                                     cards=[flow_card],
                                     suggestions=["B.Tech Engineering", "Management (BBA / MBA)",
                                                  "B.Sc (Hons) Agriculture", "Computer Applications (BCA / MCA)"]):
                    yield ev
                return

        if intent == "BTECH_TREE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step="btech_branch")
                flow_card = fee_flow.build_course_selection_card(fee_flow.SCHOOLS_DATA[0], level="ug")
                async for ev in _say(_BTECH_TREE_TEXT, message, session_id, conversation_id,
                                     cards=[flow_card],
                                     suggestions=["B.Tech CSE & Allied", "B.Tech AI & Robotics",
                                                  "B.Tech ECE", "B.Tech Core Engineering"]):
                    yield ev
                return

        if intent == "BTECH_CSE_FEE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_cse"
            await memory.update_profile(session_id, program_interest="btech_cse")
            await set_state(fee_tree_step=None, active_program="btech_cse", fee_flow_prog="btech_cse")
            if client is None or _is_mock_or_test_client(client):
                cse_prog = fee_flow.SCHOOLS_DATA[0]["programs"]["ug"][0]
                spec = fee_flow.detect_specialization(message, cse_prog)
                fee_card = fee_flow.build_detailed_fee_card(cse_prog, fee_flow.SCHOOLS_DATA[0], "2027-28", spec=spec, user_text=message)
                fee_text = get_btech_cse_fee_text(specialization=spec, user_msg=message)
                async for ev in _reply(fee_text, message, session_id, conversation_id,
                                     cards=[fee_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "BTECH_AI_ROBOTICS_FEE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_ai_robotics"
            await memory.update_profile(session_id, program_interest="btech_ai_robotics")
            await set_state(fee_tree_step=None, active_program="btech_ai_robotics", fee_flow_prog="btech_ai_robotics")
            if client is None or _is_mock_or_test_client(client):
                fee_card = fee_flow.build_detailed_fee_card(fee_flow.SCHOOLS_DATA[0]["programs"]["ug"][1], fee_flow.SCHOOLS_DATA[0], "2027-28")
                async for ev in _reply(_BTECH_AI_ROBOTICS_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[fee_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "BTECH_ECE_FEE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_ece"
            await memory.update_profile(session_id, program_interest="btech_ece")
            await set_state(fee_tree_step=None, active_program="btech_ece", fee_flow_prog="btech_ece")
            if client is None or _is_mock_or_test_client(client):
                fee_card = fee_flow.build_detailed_fee_card(fee_flow.SCHOOLS_DATA[1]["programs"]["ug"][0], fee_flow.SCHOOLS_DATA[1], "2027-28")
                async for ev in _reply(_BTECH_ECE_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[fee_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "BTECH_CORE_FEE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_mech"
            await memory.update_profile(session_id, program_interest="btech_mech")
            await set_state(fee_tree_step=None, active_program="btech_mech", fee_flow_prog="btech_mech")
            if client is None or _is_mock_or_test_client(client):
                fee_card = fee_flow.build_detailed_fee_card(fee_flow.SCHOOLS_DATA[1]["programs"]["ug"][1], fee_flow.SCHOOLS_DATA[1], "2027-28")
                async for ev in _reply(_BTECH_CORE_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[fee_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "MANAGEMENT_FEE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step=None)
                lvl = "ug" if "bba" in message.lower() else ("pg" if "mba" in message.lower() else None)
                course_card = fee_flow.build_course_selection_card(fee_flow.SCHOOLS_DATA[3], level=lvl)
                async for ev in _reply(_MANAGEMENT_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[course_card],
                                     suggestions=["Calculate my fee with scholarship", "MBA specializations",
                                                  "Hostel details", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "AGRICULTURE_FEE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step=None)
                lvl = "ug" if ("bsc" in message.lower() or "b.sc" in message.lower() or "agri" in message.lower()) else ("pg" if "msc" in message.lower() else None)
                course_card = fee_flow.build_course_selection_card(fee_flow.SCHOOLS_DATA[2], level=lvl)
                async for ev in _reply(_AGRICULTURE_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[course_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "COMP_APP_FEE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step=None)
                lvl = "ug" if "bca" in message.lower() else ("pg" if "mca" in message.lower() else None)
                course_card = fee_flow.build_course_selection_card(fee_flow.SCHOOLS_DATA[0], level=lvl)
                async for ev in _reply(_COMP_APP_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[course_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "DESIGN_FEE_QUERY":
            if client is None or _is_mock_or_test_client(client):
                await set_state(fee_tree_step=None)
                course_card = fee_flow.build_course_selection_card(fee_flow.SCHOOLS_DATA[5], level="ug")
                async for ev in _reply(_DESIGN_FEE_TEXT, message, session_id, conversation_id,
                                     cards=[course_card],
                                     suggestions=["Calculate my scholarship", "Hostel details",
                                                  "Special category concessions", "How do I apply?"], client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "BTECH_PROGRAMS_QUERY":
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._BTECH_PROGRAMS_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._BTECH_PROGRAMS_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_AI_ROBOTICS_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_ai_robotics"
            await memory.update_profile(session_id, program_interest="btech_ai_robotics")
            await set_state(fee_tree_step=None, active_program="btech_ai_robotics", fee_flow_prog="btech_ai_robotics")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._BTECH_AI_ROBOTICS_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._BTECH_AI_ROBOTICS_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_CSE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_cse"
            await memory.update_profile(session_id, program_interest="btech_cse")
            await set_state(fee_tree_step=None, active_program="btech_cse", fee_flow_prog="btech_cse")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._BTECH_CSE_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._BTECH_CSE_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_ECE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_ece"
            await memory.update_profile(session_id, program_interest="btech_ece")
            await set_state(fee_tree_step=None, active_program="btech_ece", fee_flow_prog="btech_ece")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._BTECH_ECE_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._BTECH_ECE_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_CORE_QUERY":
            if profile is not None:
                profile["program_interest"] = "btech_core"
            await memory.update_profile(session_id, program_interest="btech_core")
            await set_state(fee_tree_step=None, active_program="btech_core", fee_flow_prog="btech_core")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._BTECH_CORE_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._BTECH_CORE_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_MANAGEMENT_QUERY":
            await set_state(fee_tree_step=None, active_program="mba", fee_flow_prog="mba")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._PROGRAM_MANAGEMENT_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._PROGRAM_MANAGEMENT_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_AGRICULTURE_QUERY":
            if profile is not None:
                profile["program_interest"] = "bsc_agri"
            await memory.update_profile(session_id, program_interest="bsc_agri")
            await set_state(fee_tree_step=None, active_program="bsc_agri", fee_flow_prog="bsc_agri")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._PROGRAM_AGRICULTURE_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._PROGRAM_AGRICULTURE_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_COMP_APP_QUERY":
            await set_state(fee_tree_step=None, active_program="bca", fee_flow_prog="bca")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._PROGRAM_COMP_APP_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._PROGRAM_COMP_APP_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "PROGRAM_DESIGN_QUERY":
            await set_state(fee_tree_step=None, active_program="bdes", fee_flow_prog="bdes")
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._PROGRAM_DESIGN_OVERVIEW_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._PROGRAM_DESIGN_OVERVIEW_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "ELIGIBILITY_QUERY":
            if client is None or _is_mock_or_test_client(client):
                async for ev in _reply(responses._ELIGIBILITY_TEXT, message, session_id, conversation_id,
                                     suggestions=responses._ELIGIBILITY_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "HOSTEL_INFO_QUERY":
            from app.services.card_service import HOSTEL_FACILITIES_CARD
            if HOSTEL_FACILITIES_CARD not in cards:
                cards.append(HOSTEL_FACILITIES_CARD)

        elif intent == "HOSTEL_FEE_QUERY":
            from app.services.card_service import HOSTEL_FEE_CARD
            if HOSTEL_FEE_CARD not in cards:
                cards.append(HOSTEL_FEE_CARD)

        elif intent == "COMBINED_FEE_HOSTEL_QUERY":
            from app.services.card_service import BTECH_CSE_WITH_HOSTEL_FEE_CARD
            if BTECH_CSE_WITH_HOSTEL_FEE_CARD not in cards:
                cards.append(BTECH_CSE_WITH_HOSTEL_FEE_CARD)

        if intent == "CAMPUS_CANTEEN_QUERY":
            if client is None:
                async for ev in _reply(_CAMPUS_CANTEEN_TEXT, message, session_id, conversation_id,
                                     suggestions=_CAMPUS_CANTEEN_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "ACADEMIC_EVALUATION_QUERY":
            if client is None:
                async for ev in _reply(_ACADEMIC_EVALUATION_TEXT, message, session_id, conversation_id,
                                     suggestions=_ACADEMIC_EVALUATION_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        if intent == "LAB_FACILITIES_QUERY":
            if client is None:
                async for ev in _reply(_LAB_FACILITIES_TEXT, message, session_id, conversation_id,
                                     suggestions=_LAB_FACILITIES_CHIPS, client=client, history=history, profile=profile, conv_state=conv_state):
                    yield ev
                return

        # First interaction direct question name collection:
        has_replied = any(h.get("role") in ("model", "assistant") for h in history)
        if not has_replied and client is None and not profile.get("name") and not conv_state.get("name_asked"):
            if extracted_name:
                await set_state(name_asked=True, awaiting_name=False)
            elif _is_first_interaction_name_query(message) and not intents.is_cancel_contact(message) and not intents.is_number_update(message) and not intents.is_visit_request(message) and intent != "CAMPUS_VISIT_INFO":
                await set_state(pending_user_question=message, awaiting_name=True, name_asked=True)
                async for ev in _small_talk_reply("ask_name_first", message, session_id, conversation_id, client=client,
                                                  history=history, profile=profile, conv_state=conv_state,
                                                  suggestions=_SMALL_TALK_CHIPS):
                    yield ev
                return

        # ---- 2. "Don't call me" / "cancel my visit": run the cancel tool, report what really happened
        pending = conv_state.get("pending_action")
        has_open_request = bool(profile.get("last_lead_id"))
        if intent not in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO") and \
                intents.is_cancel_contact(message, has_open_request or bool(pending)):
            result = await _run_action("cancel_contact_request", {"reason": message[:200]}, ctx, used, cards)
            for ev in _tool_events("cancel_contact_request", result):
                yield ev
            if pending and result.get("status") == "nothing_to_cancel":
                text = ("No problem, I will not arrange it. Nothing was saved, so nobody will call you. "
                        "Is there anything else about SR University I can help you with?")
            else:
                text = _cancel_text(result)
            await clear_pending()
            await set_state(awaiting_date_confirmation=False, pending_visit_date=None)
            async for ev in _say(text, message, session_id, conversation_id, used, cards,
                                 ["B.Tech CSE fees", "Scholarship slabs", "Hostel details"]):
                yield ev
            return

        # ---- 2b. "Change my number" / "my number is ...": one place for the number, everywhere ------
        phone = tools.find_phone(message)
        asked_for_call = intents.is_callback_request(message)
        wants_update = intents.is_number_update(message) or (pending == "update_number" and bool(phone))
        if wants_update and not asked_for_call and intent not in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO"):
            if phone:
                result = await _run_action("update_contact_details", {"phone": phone}, ctx, used, cards)
                for ev in _tool_events("update_contact_details", result):
                    yield ev
                await clear_pending()
                last4 = result.get("phone_last4")
                if result.get("status") == "updated":
                    text = f"Done. Your mobile number is now the one ending {last4}."
                    if result.get("saved_request_updated"):
                        text += " Your saved request has the new number too."
                    text += " You can see or change it any time from the menu under My details."
                elif result.get("status") == "unchanged":
                    text = f"That is already the number I have for you (ending {last4}). Nothing needed to change."
                else:
                    text = (f"Sorry, I could not update your number just now. Please try again in a minute or call "
                            f"the Admissions Office at {config.ADMISSIONS_PHONE}.")
            else:
                wrong = tools.find_bad_phone(message, min_digits=5)
                await set_state(pending_action="update_number", pending_turns=0)
                text = (f"\"{wrong}\" does not look like a valid 10-digit mobile number. Please type the correct one."
                        if wrong else
                        "Sure. Please type your new 10-digit mobile number here and I will update it. You can also "
                        "change it yourself from the menu under My details.")
            async for ev in _say(text, message, session_id, conversation_id, used, cards,
                                 ["B.Tech CSE fees", "Scholarship slabs", "Hostel details"]):
                yield ev
            return
        if not phone and not asked_for_call and profile.get("phone") and _ASKS_OWN_NUMBER.search(message):
            # "What is my number?": answered here from the student's own profile, so the full number never
            # has to be in the model's prompt (it sees only the last four digits).
            saved = str(profile["phone"])
            text = (f"The mobile number saved for you is **{saved[:5]} {saved[5:]}**. To change it, say "
                    f"\"change my number\" or open My details from the menu.")
            async for ev in _say(text, message, session_id, conversation_id, used, cards,
                                 ["B.Tech CSE fees", "Scholarship slabs", "Hostel details"]):
                yield ev
            return
        if phone and intents.is_number_statement(message) and not asked_for_call:
            # "my mobile number is ...": remember it (and fix a saved request) before answering
            await _run_action("update_contact_details", {"phone": phone}, ctx, used, cards)
            profile = ctx["profile"]

        # ---- 3. Callback / campus visit requests: save them as soon as name + number are known ----
        bad_phone = None if phone else tools.find_bad_phone(message, min_digits=5 if asked_for_call else 8)
        # A bare "Ravi Kumar" counts as a name only when the agent has just asked for one.
        last_reply = next((h.get("text", "") for h in reversed(history) if h.get("role") in ("model", "assistant")), "")
        name_known = bool(profile.get("name") or conv_state.get("pending_name"))
        awaiting_name = bool(pending and not name_known and (
            conv_state.get("pending_phone") or re.search(r"\bname\b", last_reply, re.IGNORECASE)))
        name = intents.extract_name(message, bare_ok=awaiting_name)
        visit_words = intent in ("CAMPUS_VISIT_BOOKING", "CAMPUS_VISIT_BOOKING_WITH_DATE") or intents.is_visit_request(message)

        action = None
        if pending == "campus_visit" and not visit_words and not phone and not bad_phone and not asked_for_call:
            await set_state(pending_action=None, active_topic=None)
            pending = None

        if asked_for_call:
            # "Ask counsellor to call me" / "Ask admissions to call me" right after visit guidance is a visit callback.
            action = "campus_visit" if (pending == "campus_visit" or visit_words) else "callback"
        elif visit_words and (phone or bad_phone or pending == "campus_visit"):
            action = "campus_visit"
        elif pending in ("callback", "campus_visit") and intent not in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO") and \
                (phone or bad_phone or name or (pending == "campus_visit" and intent == "CAMPUS_VISIT_BOOKING_WITH_DATE")):
            action = pending
        elif phone:
            action = _pending_from_history(history)  # the agent had asked for the number

        action_note = None
        if action:
            # A number the student gave earlier (in the chat or in My details) is used as it is: they
            # are not asked for it again. The reply names its last four digits so a wrong one is noticed.
            use_phone = phone or conv_state.get("pending_phone") or tools.clean_phone(profile.get("phone") or "")
            use_name = name or profile.get("name") or conv_state.get("pending_name")
            visit = tools.resolve_campus_visit_date(message, today=date.today()) if action == "campus_visit" else None
            what = "campus visit callback" if action == "campus_visit" else "callback"
            await set_state(pending_action=action, pending_phone=use_phone, pending_name=use_name, pending_turns=0)
            if action == "campus_visit":
                await set_state(active_topic="campus_visit")

            text = None
            if bad_phone and not use_phone:
                text = (f"\"{bad_phone}\" does not look like a valid 10-digit mobile number. Please send the correct "
                        f"number and I will arrange the {what}.")
            elif use_phone and not use_name:
                text = "Thank you. May I have your full name, so the admissions team knows whom to ask for?"
            elif action == "campus_visit" and asked_for_call and not use_phone and not use_name and not bad_phone:
                text = (f"Sure. Please share your full name and 10-digit mobile number, and I will ask the admissions "
                        f"team to call you{' about visiting the campus' if action == 'campus_visit' else ''}.")
            elif name and not use_phone and len(message.split()) <= 6:
                text = (f"Thank you, {_first_name(name)}. Please send your 10-digit mobile number so the "
                        f"admissions team can reach you about the {what}.")
            elif use_phone and use_name:
                if action == "campus_visit":
                    args = {"name": use_name, "phone": use_phone, "consent": True,
                            "preferred_date": (visit or {}).get("human") if (visit or {}).get("date") and
                                              not (visit or {}).get("is_past") else "",
                            "visitors": intents.extract_visitors(message) or 1}
                    tool_name = "request_campus_visit_callback"
                else:
                    args = {"name": use_name, "phone": use_phone, "consent": True,
                            "preferred_time": intents.extract_preferred_time(message)}
                    tool_name = "request_counsellor_callback"
                result = await _run_action(tool_name, args, ctx, used, cards)
                for ev in _tool_events(tool_name, result):
                    yield ev
                text = _saved_text(action, result, args.get("preferred_time"))
                if result.get("status") == "saved":
                    await clear_pending()
                    await set_state(awaiting_date_confirmation=False, pending_visit_date=None, confirmed_visit_date=None, active_topic=None)
                    if _has_other_question(message, name):
                        # The request is saved; let the model answer the rest of the message too.
                        action_note = (f"The system has ALREADY saved this student's {what} request in this turn: "
                                       f"name {result.get('name')}, phone ending "
                                       f"{result.get('phone_last4')}. Confirm that in one line, then "
                                       f"answer their other question. Do not call the {tool_name} tool again.")
            if text and not action_note:
                async for ev in _say(text, message, session_id, conversation_id, used, cards,
                                     ["How to reach the campus", "B.Tech CSE fees", "Hostel details"]
                                     if action == "campus_visit" else
                                     ["B.Tech CSE fees", "Scholarship slabs", "Hostel details"]):
                    yield ev
                return
            canned_action_text = text
            if not text:
                action = None  # nothing to do yet: the guided visit flow / the model takes it from here
        else:
            canned_action_text = None

        # ---- 4. Campus tour dispatch & in-person visit guidance -----------------
        if conv_state.get("awaiting_date_confirmation") or conv_state.get("pending_visit_date"):
            await set_state(awaiting_date_confirmation=False, pending_visit_date=None, confirmed_visit_date=None)

        # 4a. Ambiguous / General Campus Tour -> Directly offer the two options
        if intent == "CAMPUS_TOUR_DISPATCH" and not action:
            await set_state(active_topic="campus_tour")
            async for ev in _say(_CAMPUS_TOUR_CHOICE_TEXT, message, session_id, conversation_id,
                                 used, cards, _CAMPUS_TOUR_CHOICE_CHIPS):
                yield ev
            return

        # 4b. Explicit Virtual Tour / Videos & Info
        if intent == "CAMPUS_TOUR_VIRTUAL" and not action:
            await set_state(active_topic="campus_tour_virtual")
            video_result = await _run_action("get_university_videos", {"topic": "campus tour"}, ctx, used, cards)
            for ev in _tool_events("get_university_videos", video_result):
                yield ev
            async for ev in _say(_VIRTUAL_TOUR_TEXT, message, session_id, conversation_id,
                                 used, cards, _VIRTUAL_TOUR_CHIPS):
                yield ev
            return

        # 4c. In-Person Campus Visit
        asks_to_visit = intents.is_visit_request(message)
        visit = (tools.resolve_campus_visit_date(message, today=date.today())
                 if intent.startswith("CAMPUS_VISIT") or asks_to_visit else {})
        detail_question = bool(_VISIT_DETAIL.search(message))
        wants_visit = not detail_question and (
            intent == "CAMPUS_VISIT_BOOKING" or asks_to_visit
            or (intent == "CAMPUS_VISIT_BOOKING_WITH_DATE" and visit.get("date"))
            or (intent == "CAMPUS_VISIT_INFO" and len(message.split()) <= 4))
        if wants_visit and not action:
            await set_state(active_topic="campus_visit", pending_action="campus_visit", pending_turns=0)
            contact = await _run_action("get_contact_and_apply_links", {"topic": "campus visit"}, ctx, used, cards)
            for ev in _tool_events("get_contact_and_apply_links", contact):
                yield ev
            async for ev in _say(_visit_guide(visit.get("human") if visit.get("date") else None), message,
                                 session_id, conversation_id, used, cards, _VISIT_CHIPS):
                yield ev
            return
        if intent in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO"):
            intent = "GENERAL"  # an old chat that was waiting for a visit date: answer normally

        # ---- 4b. Course Selection & Fee Enquiry Flow ----------------
        intake_decision = None
        # Read again in the fallback below when the model fails: it must exist even when this block is skipped
        # (a pending callback / campus visit), or that fallback crashes (v4.15.1).
        is_other_fee_inquiry = False
        if not action_note and not action and conv_state.get("pending_action") not in ("callback", "campus_visit") \
                and intent not in ("CAMPUS_VISIT_BOOKING", "CAMPUS_VISIT_BOOKING_WITH_DATE", "DATE_CONFIRMATION_YES",
                                   "DATE_CONFIRMATION_NO"):
            # 0. Check affordability and concession multi-step flow
            if conv_state.get("affordability_flow") or affordability.is_affordability_query(message):
                afford_res = affordability.process_affordability_flow(message, profile, conv_state)
                if afford_res is not None:
                    await set_state(**afford_res["new_state"])
                    async for ev in _say(afford_res["text"], message, session_id, conversation_id,
                                         cards=afford_res.get("cards", []),
                                         suggestions=afford_res.get("suggestions", [])):
                        yield ev
                    return

            # 1-3. Coordinated fee_intake and exploratory school/course flows
            is_multi_q = len(semantic_router.decompose_multi_questions(message)) > 1
            flow_res = await structured_flows.run_fee_or_explore_turn(
                message=message,
                intent=intent,
                is_multi_q=is_multi_q,
                side_q=side_q,
                natural_name=natural_name,
                session_id=session_id,
                conv_state=conv_state,
                profile=profile,
                ctx=ctx,
                client=client,
                set_state=set_state,
                is_mock_client=_is_mock_or_test_client,
                format_counsellor_assessment=format_counsellor_assessment,
            )
            profile = flow_res["profile"]
            intake_decision = flow_res["intake_decision"]
            is_other_fee_inquiry = flow_res["is_other_fee_inquiry"]
            if flow_res["outcome"] == "say":
                async for ev in _say(
                    flow_res["text"],
                    message,
                    session_id,
                    conversation_id,
                    cards=flow_res.get("cards", []),
                    suggestions=flow_res.get("suggestions", []),
                    eligible=flow_res.get("eligible"),
                    exact_chips=flow_res.get("exact_chips", False),
                ):
                    yield ev
                return
            if flow_res["outcome"] == "counsellor":
                for ev in _tool_events("calculate_fee", flow_res["fee_result"]):
                    yield ev
                async for ev in _counsellor_result(
                    flow_res["fee_result"],
                    flow_res["c_det"],
                    flow_res["c_text"],
                    flow_res["chips"],
                    message,
                    session_id,
                    conversation_id,
                    conv_state,
                    ctx,
                    set_state,
                ):
                    yield ev
                return

    # ---- 5. Everything else: the model, with tools --------------------------------------------
    ctx["message"] = message   # the student's own words: a score the model passes must appear in them (tools)
    contents = [types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
                for h in history]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    # First lines of earlier replies, so the model does not start every answer the same way.
    assistant_openings = []
    for h in history:
        if h.get("role") in ("model", "assistant"):
            for line in h.get("text", "").split("\n"):
                line = line.strip()
                if line and not line.startswith(("#", ">", "|", "```", "•", "-", "*")):
                    assistant_openings.append(line)
                    break
    variant_id = (len(assistant_openings) % 6) + 1
    from app.services.rag_service import determine_about_sru_angle, is_about_sru_query
    about_sru_angle = (
        determine_about_sru_angle("\n".join(f"{h.get('role')}: {h.get('text', '')}" for h in history), message)
        if is_about_sru_query(message) else 1)

    pending = conv_state.get("pending_action")
    if pending and not action:
        turns = int(conv_state.get("pending_turns") or 0) + 1
        if turns > 3:  # the student moved on; stop nudging
            await clear_pending()
            pending = None
        else:
            await set_state(pending_turns=turns)

    # No answer cache: an answer is always built for this question from the current data. (A cache keyed
    # by the message text served the same reply to every student for hours and outlived data updates.)

    if not model_first and is_about_sru_query(message):
        from app.services.card_service import generate_cards
        why_cards = generate_cards(message, "", session_id=session_id)
        for wc in why_cards:
            if wc not in cards:
                cards.append(wc)

    # Do the look-ups the code can do for free, so the model can usually answer in ONE call:
    # the fee calculation for a plain fee question, and the handbook passages for everything else.
    # Speculative 1-round tool execution: when a named-programme fee or faculty query is unambiguous,
    # pre-run the tool concurrently with retrieval so Gemini can answer in 1 round instead of 2.
    prefetched_fee = None
    speculative_single_round = False
    is_compare_q = bool(re.search(r"\b(?:vs|versus|compare|comparison)\b", message or "", re.I))
    if intake_decision and intake_decision["action"] == "calculate":
        fee_args = dict(intake_decision["args"])
        hostel_args = _fee_args_from_message(message, profile) or {}
        if hostel_args.get("hostel"):
            fee_args["hostel"] = hostel_args["hostel"]
    elif model_first:
        fee_args = (
            _fee_args_from_message(message, profile)
            if (
                not action_note
                and not is_compare_q
                and not compound.model_note(message)
                and fees.find_program(message or "")
                and re.search(r"\b(?:fee|fees|tuition|scholarship|cost|payable)\b", message or "", re.I)
            )
            else None
        )
    else:
        fee_args = _fee_args_from_message(message, profile) if not action_note else None

    want_spec_faculty = bool(
        not fee_args
        and not action_note
        and not is_compare_q
        and not compound.model_note(message)
        and faculty.is_faculty_question(message)
    )
    search_q = _contextual_query(message, history, active_topic=active_topic, active_program=active_program)

    async def _run_spec_fee():
        return await tools.run_tool("calculate_fee", fee_args, ctx) if fee_args else None

    async def _run_spec_faculty():
        return await tools.run_tool("find_faculty", {"query": message}, ctx) if want_spec_faculty else None

    async def _empty_passages():
        return ""

    fee_result, fac_result, passages = await asyncio.gather(
        _run_spec_fee(),
        _run_spec_faculty(),
        _hybrid_handbook_context(search_q) if not (fee_args or want_spec_faculty) else _empty_passages(),
    )
    if fee_result and fee_result.get("status") == "ok":
        prefetched_fee = fee_result
        if model_first:
            speculative_single_round = True
    fee_note = None
    if prefetched_fee:
        import json as _json
        fee_note = _json.dumps({k: prefetched_fee[k] for k in _FEE_KEYS if prefetched_fee.get(k) is not None},
                               ensure_ascii=False)
        details = (intake_decision or {}).get("details") or {}
        if details.get("board"):
            fee_note += f"\nBoard given by the student: {details.get('board_label') or details['board']}."
        if details.get("no_entrance"):
            fee_note += "\nThe student has no JEE Main / EAPCET score."
        fee_note += (f"\nOfficial fee & scholarship calculator to mention: {fee_intake.FEE_PORTAL_URL}")
    prefetched_faculty = None
    if fac_result and fac_result.get("status") == "ok":
        prefetched_faculty = fac_result
        if model_first:
            speculative_single_round = True
    faculty_note = None
    if prefetched_faculty:
        import json as _json
        faculty_note = _json.dumps({k: v for k, v in prefetched_faculty.items() if k != "status"},
                                   ensure_ascii=False)[:3500]
    if facts_note:
        # The verified facts for this question come first; the handbook passages only add detail.
        passages = ("VERIFIED FACTS FOR THIS QUESTION (use these; attribute any marked 'as stated by SRU'):\n"
                    + facts_note + ("\n\n" + passages if passages else ""))

    # ---- Policy-safe Redis FAQ cache check (Phase 3: 0 LLM tokens on repeated FAQs) ----
    use_faq_cache = (client is None and get_client is _DEFAULT_GET_CLIENT) or getattr(client, "enable_faq_cache", False)
    faq_key = (
        memory.faq_cache_key(message, ctx.get("profile"), conv_state, has_history=bool(history))
        if (model_first and use_faq_cache)
        else None
    )
    if faq_key:
        cached_faq = await memory.get_faq_cache(faq_key)
        if cached_faq and cached_faq.get("answer"):
            async for ev in _say(
                cached_faq["answer"],
                message,
                session_id,
                conversation_id,
                used=cached_faq.get("used") or [],
                cards=cached_faq.get("cards") or [],
                suggestions=cached_faq.get("suggestions") or [],
                telemetry={"detected_intent": "FAQ_CACHE", "response_mode": "cache"},
                profile=ctx.get("profile"),
                exact_chips=bool(cached_faq.get("suggestions")),
            ):
                yield ev
            return

    selected_tools = tools.select_tools_for_message(message, conv_state, ctx.get("profile"))
    tool_decl = _tool_declarations(selected_tools)
    models, tier_thinking, model_tier = llm_loop.select_model_tier(
        message,
        fallback_models=_FALLBACK_MODELS,
        has_tools=bool(tool_decl),
        is_compound=bool(compound.model_note(message)),
        is_compare=is_compare_q,
        speculative_single_round=speculative_single_round,
        has_pending_action=bool(pending or action_note),
    )
    final = ""
    model_text = None   # the model's own words (the self-check runs only on these)
    link = {"fixed": client, "key": None, "models": models, "model_idx": 0, "error_kind": None,
            "thinking": True, "thinking_level": tier_thinking, "model_tier": model_tier,
            "deadline": time.monotonic() + max(1.0, config.AGENT_TOTAL_TIMEOUT),
            "static_prefix": build_static_prefix(), "cache_tag": ",".join(selected_tools)}
    # Words are shown while Gemini writes them, except when the reply is about a callback / visit
    # request or a cancellation: those are checked for honesty first and only then shown.
    live_ok = not (pending or action_note or _CANCEL_ASK.search(message) or intents.is_callback_request(message))
    streamed = ""
    shown, hold_from = 0, None        # live text shown so far / where the first sensitive detail starts
    turn_evidence: list = []          # every tool result of this turn: the self-check's evidence
    try:
        if link["fixed"] is None and get_client is not _DEFAULT_GET_CLIENT:
            link["fixed"] = get_client()
        else:
            link["key"] = None if client else _ring.next_key()
            if link["fixed"] is None and not link["key"]:
                link["fixed"] = get_client()
        last_assistant_text = next(
            (h.get("text", "") for h in reversed(history) if h.get("role") in ("model", "assistant")),
            ""
        )
        student_name = ctx["profile"].get("name") or ""
        first_name = _first_name(student_name)
        name_used_recently = bool(
            first_name and re.search(rf"\b{re.escape(first_name)}\b", last_assistant_text, re.IGNORECASE)
        )

        for round_no in range(config.AGENT_MAX_TOOL_ROUNDS + 1):
            last_round = round_no == config.AGENT_MAX_TOOL_ROUNDS
            prompt_kwargs = dict(
                profile=_prompt_profile(ctx["profile"]), variant_id=variant_id, used_openings=assistant_openings,
                about_sru_angle=about_sru_angle, pending_action=pending, action_note=action_note,
                handbook_passages=passages, fee_result=fee_note, faculty_result=faculty_note,
                persona=persona, name_used_recently=name_used_recently,
                conversation_note=_conversation_note(conv_state, ctx["profile"], history),
                reply_brief=compound.model_note(message),     # several questions: answer each (v4.15.1)
                focus_program=(fees.clean_program_name(conv_state["active_program"])
                               if conv_state.get("active_program") in fees.load_data()["programs"] else None),
            )
            link["dynamic_suffix"] = build_dynamic_suffix(**prompt_kwargs)
            cfg = types.GenerateContentConfig(
                system_instruction=build_system_prompt(**prompt_kwargs),
                tools=[tool_decl] if (tool_decl and not speculative_single_round) else None,
                temperature=0.2,
                max_output_tokens=900,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                # On the last round (or speculative 1-round execution) the model answers in words.
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="NONE" if (last_round or speculative_single_round) else "AUTO")),
            )
            provider = GeminiAgentProvider(link, ring=_ring)
            if live_ok and _can_stream(link, ring=_ring):
                resp, round_text = None, ""
                async for kind, value in provider.stream_with_tools(contents, cfg):
                    if kind == "text":
                        round_text += value
                        streamed += value
                        # v4.17.1: text is shown live only up to the first sensitive detail (an amount, a
                        # percentage, a person's name, a phone number); from there the answer is sent after the
                        # self-check, so a wrong name or fee never appears and then disappears. A short tail is
                        # always held back, so a half-written detail is never shown either. A leak stops it too.
                        if hold_from is None:
                            sens = _SENSITIVE_DETAIL.search(streamed, shown)
                            if sens:
                                hold_from = sens.start()
                        if hold_from is not None:
                            # Release verified complete lines/sentences incrementally instead of stalling
                            # the remainder of the response until generation finishes.
                            tail = streamed[hold_from:]
                            nl = tail.rfind("\n")
                            if nl > 0:
                                candidate_end = hold_from + nl + 1
                                seg = streamed[shown:candidate_end]
                                from . import answer_check
                                ev_sources = [passages or "", facts_note or "", fee_note or "", faculty_note or ""] + [
                                    str(item.get("result") or "") for item in turn_evidence
                                ]
                                checked_seg, seg_probs = answer_check.check(seg, sources=ev_sources)
                                if not seg_probs:
                                    _, seg_probs = answer_check.check_people(checked_seg, evidence=ev_sources)
                                if not seg_probs and checked_seg == seg and not ai_guard.leak_reason(streamed):
                                    if turn_telemetry.first_token_ms is None:
                                        turn_telemetry.first_token_ms = round((time.perf_counter() - started) * 1000, 2)
                                    yield {"type": "token", "delta": seg}
                                    shown = candidate_end
                                    next_sens = _SENSITIVE_DETAIL.search(streamed, shown)
                                    hold_from = next_sens.start() if next_sens else None
                        limit = len(streamed) - 12 if hold_from is None else min(hold_from, len(streamed) - 12)
                        if limit > shown and not ai_guard.leak_reason(streamed):
                            if turn_telemetry.first_token_ms is None:
                                turn_telemetry.first_token_ms = round((time.perf_counter() - started) * 1000, 2)
                            yield {"type": "token", "delta": streamed[shown:limit]}
                            shown = limit
                    else:
                        resp = value
            else:
                resp = await provider.generate_with_tools(contents, cfg)
            if resp is None:
                link["error_kind"] = "busy"
                raise RuntimeError("Model stream produced no response")
            calls = resp.function_calls or []
            if not calls:
                final = (resp.text or "").strip()
                model_text = final
                if not final and not last_round and round_no == 0:
                    # An empty reply (the model sometimes returns nothing): ask once more, plainly.
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(
                        text="(Please answer the student's last message in a few clear sentences.)")]))
                    continue
                break

            contents.append(resp.candidates[0].content)  # keep the model's turn exactly as returned
            for call in calls:
                label = tools.TOOLS[call.name][1] if call.name in tools.TOOLS else "Working"
                yield {"type": "tool", "name": call.name, "status": "running", "label": label}
            results = await tool_runner.execute_tool_calls(calls, ctx)
            result_parts = []
            for call, result in zip(calls, results):
                error = result.pop("_error", None)
                if error:
                    log.error("tool %s failed: %s", call.name, error)
                log.info("tool=%s status=%s session=%s", call.name, result.get("status"), (session_id or "")[:8])
                used.append({"name": call.name, "status": result.get("status"),
                             "is_action": call.name in tools.ACTION_TOOLS})
                is_card_ready = call.name in CARD_TOOLS and result.get("status") in ("calculated", "saved", "ok")
                if call.name == "calculate_fee":
                    prefetched_fee = None  # the model asked for its own calculation: show that one
                    cards[:] = [c for c in cards if c.get("type") != "calculate_fee"]
                if call.name == "find_faculty":
                    prefetched_faculty = None
                    cards[:] = [c for c in cards if c.get("type") != "find_faculty"]
                if is_card_ready:
                    cards.append({"type": call.name, "data": result})
                yield {"type": "tool", "name": call.name, "status": "done",
                       "result_status": result.get("status"),
                       "result": result if is_card_ready else None}
                turn_evidence.append({"tool": call.name, "result": result})
                result_parts.append(types.Part(function_response=types.FunctionResponse(
                    name=call.name, response=result, id=getattr(call, "id", None))))
            contents.append(types.Content(role="user", parts=result_parts))
    except Exception as exc:
        if link.get("error_kind") in ("rate", "busy"):
            # expected on the free tier: one line in the log, not a stack trace
            log.warning("model unavailable (%s) for session %s: %s", link["error_kind"], session_id, str(exc)[:160])
        else:
            log.exception("agent failed for session %s", session_id)
        if canned_action_text:  # the request itself was saved; say so even though the model failed
            async for ev in _say(canned_action_text, message, session_id, conversation_id, used, cards):
                yield ev
            return
        # v4.17.0: no keyword-matched answer when the model can't be reached. A canned text picked from the
        # words of the question was often about something else; the student is told plainly that the assistant
        # is busy, with buttons that work without the model (each one runs its own fixed flow).
        if not model_first and not used and prefetched_fee:
            # A button / step whose fee the engine already calculated for this turn: that calculation is shown
            # as it is (exact engine figures, nothing read from the words of a typed question).
            for ev in _tool_events("calculate_fee", prefetched_fee):
                yield ev
            async for ev in _say(_offline_fee_text(prefetched_fee), message, session_id, conversation_id,
                                 [{"name": "calculate_fee", "status": "ok", "is_action": False}],
                                 [{"type": "calculate_fee", "data": prefetched_fee}],
                                 eligible=True if _is_personal_eligibility(prefetched_fee) else None):
                yield ev
            return
        if link.get("error_kind") in ("rate", "busy"):
            async for ev in _say(get_limit_reply(session_id), message, session_id, conversation_id, used,
                                 cards if used else [], list(_BUSY_CHIPS), exact_chips=True, plain=True):
                yield ev
            return
        yield {"type": "error", "detail": get_fallback_text(session_id)}
        return

    if prefetched_fee:  # the model answered from the calculation the code had already done
        used.append({"name": "calculate_fee", "status": "ok", "is_action": False})
        cards.append({"type": "calculate_fee", "data": prefetched_fee})
        for ev in _tool_events("calculate_fee", prefetched_fee):
            yield ev

    if prefetched_faculty:  # the model answered from the faculty profiles the code had found
        used.append({"name": "find_faculty", "status": "ok", "is_action": False})
        cards.append({"type": "find_faculty", "data": prefetched_faculty})
        for ev in _tool_events("find_faculty", prefetched_faculty):
            yield ev

    # ---- 6. Honesty checks: the words must match what the tools actually did ------------------
    statuses = {(t["name"], t["status"]) for t in used}
    saved_now = any(t["is_action"] and t["status"] == "saved" for t in used)
    if any(name_ == "cancel_contact_request" for name_, _ in statuses) or (
            final and _claims_cancelled(final) and _CANCEL_ASK.search(message)
            and not _NOT_ABOUT_CONTACT.search(message)):
        if ("cancel_contact_request", "cancelled") not in statuses:
            ran = next((t for t in used if t["name"] == "cancel_contact_request"), None)
            if ran is None:
                result = await _run_action("cancel_contact_request", {"reason": message[:200]}, ctx, used, cards)
                for ev in _tool_events("cancel_contact_request", result):
                    yield ev
                final = _cancel_text(result)
            elif _claims_cancelled(final):
                final = _cancel_text({"status": ran["status"], "reference": str(profile.get("last_lead_id", ""))[:8],
                                      "request_type": profile.get("last_lead_type")})
    elif final and _claims_saved(final) and not saved_now and not (ctx.get("profile") or {}).get("last_lead_id"):
        is_visit = bool(re.search(r"\bvisit\b|\btour\b", final + " " + message, re.IGNORECASE))
        await set_state(pending_action="campus_visit" if is_visit else "callback", pending_turns=0)
        final = ("I have not saved anything yet. To ask the admissions team to call you about a "
                 + ("campus visit, please send your full name and 10-digit mobile number. I can't book or confirm "
                    "a visit myself."
                    if is_visit else "callback, please send your full name and 10-digit mobile number."))
    if saved_now:
        await clear_pending()

    final = final or canned_action_text or get_fallback_text(session_id)
    if model_text and final == model_text:
        # Self-check (v4.12.0): the model's numbers against this turn's verified data before sending.
        from . import answer_check
        fee_card = next((c["data"] for c in cards if isinstance(c, dict) and c.get("type") == "calculate_fee"
                         and isinstance(c.get("data"), dict)), None)
        evidence = [passages, fee_note or "", faculty_note or "", facts_note or "", cards, *turn_evidence]
        final, problems = answer_check.check(final, fee_result=fee_card or prefetched_fee, sources=evidence)
        final, people_problems = answer_check.check_people(final, evidence=evidence)
        problems += people_problems
        if problems:
            log.warning("self-check corrected the model's answer: %s", "; ".join(problems)[:300])
    from app.services.guardrail_service import normalize_positive_brand_advocacy
    final = normalize_positive_brand_advocacy(final)
    # A fee with hostel or transport added: offer the complete fee chart once per conversation.
    offered_chart = await _offer_fee_chart(session_id, conversation_id, cards)
    if offered_chart:
        final = final.rstrip() + "\n\n" + _FEE_CHART_OFFER
        conv_state.update(fee_chart_offered=True, offer="fee_chart")
    if not streamed:
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
    elif final.startswith(streamed[:shown]):
        # the checked answer continues what was shown live: send the rest (held-back details, the tail)
        for piece in _chunks(final[shown:]):
            yield {"type": "token", "delta": piece}
    # (otherwise the 'done' event carries the corrected final text, which the browser shows in place of what it
    # streamed; a held-back detail was never on screen)
    await memory.append_history(session_id, message, final, conversation_id)

    # ---- 7. Cards and follow-up suggestions ---------------------------------------------------
    try:
        from app.services.card_service import generate_cards

        # Videos are matched on their own titles and keywords (video_service.get_keyword_videos),
        # so no embedding call is spent here.
        query_embedding = None

        seen_card_types = set()
        for h in history:
            for c in h.get("cards") or []:
                if isinstance(c, dict) and c.get("type"):
                    seen_card_types.add(c["type"])
        for c in cards:
            if isinstance(c, dict) and c.get("type"):
                seen_card_types.add(c["type"])

        # "Already shown" is remembered per CONVERSATION (a new chat may show a card again), and only for
        # cards that are actually delivered below (a card dropped here must not block it later).
        from app.services.card_service import get_session_shown_cards
        card_scope = f"{session_id}:{conversation_id or ''}"
        shown_before = set(get_session_shown_cards(card_scope))
        contextual_cards = generate_cards(
            user_message=message, answer=final, profile=ctx.get("profile"),
            session_id=card_scope, seen_card_types=seen_card_types,
            query_embedding=query_embedding, keyword_videos=True)
        personalised = any(t["name"] in _FEE_TOOLS for t in used)
        if any(isinstance(c, dict) and c.get("type") == "calculate_fee" for c in cards):
            # The student's own fee card is shown: a generic fee table (e.g. "CSE with hostel") would be a
            # second, different set of numbers for the same question.
            cards[:] = [c for c in cards if not (isinstance(c, dict) and c.get("type") == "fee_breakdown")]
        has_video_card = any(c.get("type") in ("get_university_videos", "video_recommendations") for c in cards)
        for c in contextual_cards:
            if personalised and c.get("type") == "fee_breakdown":
                continue  # the student already has their own numbers; no generic table underneath
            if has_video_card and c.get("type") in ("get_university_videos", "video_recommendations"):
                continue  # tool already provided video card; do not duplicate
            if c not in cards:
                cards.append(c)
        # v4.17.0: the answer already has its own comparison table: the generic comparison card would repeat it
        if _HAS_MD_TABLE.search(final or ""):
            cards[:] = [c for c in cards if not (isinstance(c, dict) and c.get("type") == "comparison")]
    except Exception as card_err:
        log.warning("Could not generate contextual cards for agent: %s", card_err)

    suggestions = []
    try:
        department = None
        fac = next((c["data"] for c in cards if c.get("type") == "find_faculty"), None)
        if fac:
            department = fac.get("department") or next(
                (p.get("department") for p in fac.get("faculty") or [] if p.get("department")), None)
        base_suggestions = followups.suggest(
            message, used, ctx.get("profile"), department,
            history=history, active_topic=active_topic, answer=final,
        )

        async def _cards_coro():
            if not any(isinstance(c, dict) and c.get("type") in _VIDEO_CARDS for c in cards):
                return await _with_topic_videos(message, final, list(cards), session_id, conversation_id)
            return list(cards)

        async def _sugg_coro():
            if offered_chart:
                return ["Yes, prepare my fee chart", "No, thanks"]
            return await _with_resume_chip(session_id, conversation_id, base_suggestions)

        cards[:], suggestions = await postprocess.parallel_cards_and_suggestions(
            cards_coro=_cards_coro(),
            suggestions_coro=_sugg_coro(),
        )
        from app.services.card_service import get_session_shown_cards
        card_scope = f"{session_id}:{conversation_id or ''}"
        delivered = {c.get("type") for c in cards if isinstance(c, dict)}
        shown_now = get_session_shown_cards(card_scope)
        for card_type in list(shown_now - shown_before):
            if card_type not in delivered:
                shown_now.discard(card_type)
    except Exception as sugg_err:
        log.warning("Could not run parallel card/suggestion post-processing: %s", sugg_err)

    _apply_rounds_telemetry(turn_telemetry, link)
    turn_telemetry.total_latency_ms = round((time.perf_counter() - started) * 1000, 2)
    if turn_telemetry.first_token_ms is None and (streamed or final):
        turn_telemetry.first_token_ms = turn_telemetry.total_latency_ms
    if not _TURN_TELEMETRY_RECORDED.get():
        observability.record_policy_telemetry(turn_telemetry, persist_db=_should_persist_telemetry_db())
        _TURN_TELEMETRY_RECORDED.set(True)
    if (
        faq_key
        and final
        and not any(t.get("is_action") for t in used)
        and not any(t.get("name") in ("calculate_fee", "check_eligibility", "remember_student_details", "share_fee_estimate") for t in used)
    ):
        await memory.set_faq_cache(
            faq_key,
            {
                "answer": final,
                "used": used,
                "cards": cards,
                "suggestions": list(suggestions),
            },
        )
    try:
        sources = _answer_sources(final, turn_evidence, passages)
    except Exception:
        log.exception("source references skipped")
        sources = []
    yield _done(conversation_id, final, used, cards, suggestions, telemetry=turn_telemetry.to_dict(), profile=profile,
                sources=sources)
