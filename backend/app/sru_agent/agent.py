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
import logging
import re
import weakref
from datetime import date, datetime

from google import genai
from google.genai import types

from . import config, faculty, fee_intake, fees, intents, knowledge, memory, tools
from .prompt import build_system_prompt

log = logging.getLogger("sru_agent")
_client = None

FALLBACK = (f"I'm having trouble right now. Please call the Admissions Office at "
            f"{config.ADMISSIONS_PHONE} or try again in a moment.")
# Results of these tools are sent to the browser so it can draw a card.
CARD_TOOLS = {"calculate_fee", "check_eligibility", "request_counsellor_callback",
              "request_campus_visit_callback", "get_contact_and_apply_links", "get_university_videos",
              "find_faculty"}
# When one of these ran, the answer is about this student's own numbers, so the generic
# "B.Tech CSE fee" table from card_service must not be shown underneath it.
_FEE_TOOLS = {"calculate_fee", "compare_programs", "get_program_info", "get_special_concessions"}
_FALLBACK_MODELS = ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash")
# Campus visits: SRU Buddy never books or confirms one (admissions brief, Nov 2026). It points to the
# admissions team (sru.edu.in/visit-us) and can pass the student's number on as a callback request.
def _visit_guide(date_text: str | None = None) -> str:
    asked = f" for {date_text}" if date_text else ""
    return (f"Campus visits{asked} are arranged by the SR University admissions team. I can't book or confirm a "
            f"visit myself, but they will help you plan it:\n"
            f"- Call {config.ADMISSIONS_PHONE} or 0870-2818311\n"
            f"- Call or WhatsApp {config.CAMPUS_VISIT_PHONE}\n"
            f"- Email {config.ADMISSIONS_EMAIL}\n"
            f"- Campus: {config.CAMPUS_ADDRESS}\n\n"
            f"Please confirm the day and time with them before you travel. If you like, share your name and "
            f"10-digit mobile number and I will ask the admissions team to call you back about the visit.")


_VISIT_CHIPS = ["Ask admissions to call me", "How to reach the campus", "Hostel details"]
_VISIT_DETAIL = re.compile(r"\b(?:parents?|timings?|hours?|allowed|dress|bring|documents?|reach|directions?|route|"
                           r"bus|train|far|distance|weekends?|sundays?|holidays?|accompan\w*|stay|guest|lunch|"
                           r"free|cost|charge)\b", re.IGNORECASE)


# ------------------------------------------------------------ model access ----
class _KeyRing:
    """One Gemini client per configured API key, handed out in turn."""

    def __init__(self):
        self._pool = None
        self._clients = {}

    def _get_pool(self):
        if self._pool is None:
            keys = list(config.GEMINI_API_KEYS) or ([config.GEMINI_API_KEY] if config.GEMINI_API_KEY else [])
            if not keys:
                return None
            from app.providers.key_pool import APIKeyPool
            self._pool = APIKeyPool(keys, default_cooldown=config.AGENT_KEY_COOLDOWN_SECONDS)
        return self._pool

    def next_key(self) -> str:
        pool = self._get_pool()
        return pool.get_next_key() if pool else ""

    def client(self, key: str):
        if key not in self._clients:
            self._clients[key] = genai.Client(api_key=key)
        return self._clients[key]

    def rate_limited(self, key: str, cooldown: float | None = None) -> str:
        """Rest this key for a while; returns the key to use next (may be the same one)."""
        pool = self._get_pool()
        return pool.mark_rate_limited(key, cooldown) if pool else key

    def all_resting(self) -> bool:
        """True when every key is waiting out a limit (no point calling the model right now)."""
        pool = self._get_pool()
        return bool(pool) and pool.active_keys_count == 0

    def worked(self, key: str):
        pool = self._get_pool()
        if pool:
            pool.mark_success(key)

    def size(self) -> int:
        pool = self._get_pool()
        return len(pool) if pool else 0


_ring = _KeyRing()
_gates = weakref.WeakKeyDictionary()


def get_client():
    """A Gemini client on the first configured key (kept for scripts and older code)."""
    global _client
    if _client is None:
        _client = _ring.client(_ring.next_key() or config.GEMINI_API_KEY)
    return _client


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


def _is_daily_limit(exc: Exception) -> bool:
    text = str(exc).lower().replace(" ", "").replace("_", "")
    return "perday" in text or "daily" in text or "requestsperday" in text


async def _handle_call_error(exc, link: dict, attempt: int, model: str) -> float | None:
    """Decide what to do after a failed model call: None = try the next model at once, a number =
    wait that long and retry; raises when there is nothing left to try."""
    kind = link["error_kind"] = _error_kind(exc)
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
    level = (config.AGENT_THINKING_LEVEL or "").upper()
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


async def _generate(contents, cfg, link: dict):
    """One model call that survives a retired model, a rate-limited key and a busy server.

    `link` carries the connection for this student message: a fixed client (tests) or the
    current key, plus the model that last worked. This function, _generate_stream and _KeyRing
    are the only code that talks to the AI provider: moving to a paid Gemini plan needs only new
    keys in the environment; another provider needs only a replacement for these functions.
    """
    attempt = 0
    if not link["fixed"] and _ring.all_resting():
        link["error_kind"] = "rate"
        raise ModelUnavailable("all Gemini keys are resting after a rate limit")
    while True:
        client = link["fixed"] or _ring.client(link["key"])
        model = link["models"][link["model_idx"]]
        try:
            async with _gate():
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(model=model, contents=contents,
                                                       config=_with_thinking(cfg, link, model)),
                    timeout=config.AGENT_CALL_TIMEOUT)
            if not link["fixed"]:
                _ring.worked(link["key"])
            return resp
        except Exception as exc:
            wait = await _handle_call_error(exc, link, attempt, model)
            if wait is None:
                continue
            attempt += 1
            await asyncio.sleep(wait)


def _can_stream(link: dict) -> bool:
    client = link["fixed"] or (_ring.client(link["key"]) if link["key"] else None)
    return bool(config.AGENT_STREAM) and client is not None and \
        hasattr(getattr(getattr(client, "aio", None), "models", None), "generate_content_stream")


async def _generate_stream(contents, cfg, link: dict):
    """Like _generate, but hands over the answer while the model is still writing it.

    Yields ("text", piece) as words arrive, then ("done", response) with every part the model
    sent (function calls and their thought signatures included), so the agent loop treats it
    exactly like a normal response. Errors before the first piece are retried like _generate;
    an error in the middle of an answer is raised (the words already shown are replaced by the
    final reply or the error message)."""
    attempt = 0
    if not link["fixed"] and _ring.all_resting():
        link["error_kind"] = "rate"
        raise ModelUnavailable("all Gemini keys are resting after a rate limit")
    while True:
        client = link["fixed"] or _ring.client(link["key"])
        model = link["models"][link["model_idx"]]
        started = False
        try:
            async with _gate():
                stream = await asyncio.wait_for(
                    client.aio.models.generate_content_stream(model=model, contents=contents,
                                                              config=_with_thinking(cfg, link, model)),
                    timeout=config.AGENT_CALL_TIMEOUT)
                parts, last = [], None
                iterator = stream.__aiter__()
                while True:
                    try:
                        chunk = await asyncio.wait_for(iterator.__anext__(), timeout=config.AGENT_CALL_TIMEOUT)
                    except StopAsyncIteration:
                        break
                    last = chunk
                    cand = (chunk.candidates or [None])[0]
                    for part in ((cand.content.parts if cand and cand.content else None) or []):
                        parts.append(part)
                        if part.text and not getattr(part, "thought", False):
                            started = True
                            yield ("text", part.text)
            if not link["fixed"]:
                _ring.worked(link["key"])
            merged = types.GenerateContentResponse(candidates=[types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=getattr((last.candidates or [None])[0], "finish_reason", None) if last else None)])
            yield ("done", merged)
            return
        except Exception as exc:
            if started:
                link["error_kind"] = _error_kind(exc)
                raise
            wait = await _handle_call_error(exc, link, attempt, model)
            if wait is None:
                continue
            attempt += 1
            await asyncio.sleep(wait)


def _tool_declarations():
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, **decl) for name, (_fn, _label, decl) in tools.TOOLS.items()])


def _chunks(text: str, words_per_chunk: int = 6):
    words = re.findall(r"\S+\s*", text)
    for i in range(0, len(words), words_per_chunk):
        yield "".join(words[i:i + words_per_chunk])


# ------------------------------------------------------- small reply helpers ----
def _done(conversation_id, answer, used=(), cards=(), suggestions=()):
    return {"type": "done", "conversation_id": conversation_id, "answer": answer,
            "tools_used": list(used), "model": config.AGENT_MODEL,
            # kept so the existing frontend 'done' handler does not break
            "sources": [], "suggestions": list(suggestions), "cards": list(cards), "flow": None}


async def _say(text, message, session_id, conversation_id, used=(), cards=(), suggestions=()):
    """Stream a reply the code wrote itself (no model call), remember it, and finish the turn."""
    for piece in _chunks(text):
        yield {"type": "token", "delta": piece}
    await memory.append_history(session_id, message, text, conversation_id)
    yield _done(conversation_id, text, used, cards, suggestions)


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
        return (f"Done. I have cancelled your {label} request (reference **{ref}**). The admissions team "
                f"will not contact you about it. If you change your mind, just tell me.")
    if status == "nothing_to_cancel":
        return ("There is no callback or visit request saved from this chat, so there is nothing to cancel "
                "and nobody will call you because of this chat. If you shared your number through another "
                f"form, please call the Admissions Office at {config.ADMISSIONS_PHONE} to have it removed.")
    return (f"I could not cancel your {label} request (reference **{ref}**) from here. Please call the "
            f"Admissions Office at {config.ADMISSIONS_PHONE} and quote that reference, and they will remove it.")


def _saved_text(kind: str, result: dict, preferred_time: str | None = None) -> str:
    status = result.get("status")
    if status == "saved":
        first, ref, last4 = _first_name(result.get("name")), result.get("reference"), result.get("phone_last4")
        again = "is already saved" if result.get("already_saved") else "is saved"
        if kind == "campus_visit":
            wish = f" (you mentioned {result['preferred_date']})" if result.get("preferred_date") else ""
            return (f"Thank you, {first}. I have passed your wish to visit the campus{wish} to the admissions team "
                    f"(reference **{ref}**). This is not a booking: the admissions team will call you on the "
                    f"number ending {last4} to arrange the visit and confirm the day and time. You can also reach "
                    f"them directly on {config.CAMPUS_VISIT_PHONE} (call or WhatsApp). To withdraw the request, "
                    f"just say \"cancel my visit request\".")
        when = f" (preferred time: {preferred_time})" if preferred_time else ""
        return (f"Thank you, {first}. Your callback request {again} (reference **{ref}**). An admissions "
                f"counsellor will call you on the number ending {last4}{when}. "
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


def _offline_fee_reply(message: str, ctx: dict, fee: dict | None = None):
    """A fee answer straight from the fee file, for when the model cannot be reached."""
    if fee and fee.get("status") == "ok":
        return _offline_fee_text(fee), fee
    if not _FEE_WORDS.search(message):
        return None
    profile = ctx.get("profile") or {}
    program = message if fees.find_program(message) else profile.get("program_interest")
    if not program:
        return None
    m = re.search(r"(?<!\d)(\d{2}(?:\.\d+)?)\s*(?:%|percent)", message, re.IGNORECASE)
    percent = float(m.group(1)) if m else profile.get("percent")
    m = re.search(r"\b(?:eapcet|eamcet)\D{0,20}(\d{1,6})\b|\brank\D{0,10}(\d{1,6})\b", message, re.IGNORECASE)
    rank = int(m.group(1) or m.group(2)) if m else profile.get("eapcet_rank")
    board = "cbse" if re.search(r"\b(?:cbse|icse)\b", message, re.IGNORECASE) else profile.get("board") or "state_board"
    fee = fees.calculate_fee(program=program, percent=percent, board=board, eapcet_rank=rank)
    if fee.get("status") != "ok":
        return None
    return _offline_fee_text(fee), fee


def _offline_fee_text(fee: dict) -> str:
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
              f"Many students are chatting right now, so this is a quick answer from the fee table. For anything "
              f"else, please ask again in a minute or call {config.ADMISSIONS_PHONE}."]
    return "\n".join(lines)


_SCORE_WORDS = r"(?:eapcet|eamcet|emcet|emact|eamect|eamcent)"
_FEE_KEYS = ("program", "academic_year", "scholarship_percent", "scholarship_basis_text", "scores_considered",
             "tuition_first_year", "tuition_first_year_after_scholarship", "per_semester_after_scholarship",
             "one_time_enrollment_fee", "other_yearly_fees", "hostel", "hostel_options_per_year",
             "sem1_total_payable", "total_per_semester", "first_year_total_payable", "yearly_increase",
             "next_scholarship_slab", "notes")


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
    m = re.search(r"(?<![\d.])(\d{2}(?:\.\d+)?)\s*(?:%|percent)", low)
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
        args["hostel"] = f"{kind}_{'3' if re.search(r'(?<!\d)3[\s-]?(?:shar|bed|person|member)', low) else '4'}"
    return args


def _handbook_context(message: str) -> str:
    """Handbook passages for this message, found by keyword search (no AI call)."""
    try:
        found = knowledge.search(message, k=3, min_score=5.0)
    except Exception:
        return ""
    if not found:
        return ""
    top = found[0]["score"]
    parts = [f"[{f['title'].split(' > ')[-1]}]\n{f['text'][:750]}" for f in found if f["score"] >= 0.55 * top]
    return "\n\n".join(parts)


def _offline_knowledge_reply(message: str):
    """The most relevant handbook passage, shown as it is, for when the model cannot be reached."""
    try:
        found = knowledge.search(message, k=1, min_score=7.0)
    except Exception:
        found = []
    if not found:
        return None
    text = re.sub(r"\[FACT-ID:[^\]]*\]\s*|\[STATUS:[^\]]*\]\s*|\[SOURCE:[^\]]*\]\s*", "", found[0]["text"]).strip()
    if len(text) > 900:
        text = text[:900].rsplit("\n", 1)[0] + "\n..."
    return (f"I cannot reach my AI model right now (the free limit for today has been used), so here is the "
            f"matching part of the SR University handbook, **{found[0]['title'].split(' > ')[-1]}**:\n\n{text}\n\n"
            f"I can still calculate fees and scholarships, find faculty profiles and arrange a callback. "
            f"For anything else, please call the Admissions Office at {config.ADMISSIONS_PHONE}.")


_LIMIT_REPLY = (f"Many students are using SRU Buddy right now and the free AI limit has been reached, so I cannot "
                f"answer that question at the moment. I can still do these without it: calculate a fee or "
                f"scholarship (for example \"CSE fee with 85%\"), arrange a counsellor callback (\"call me\"), "
                f"find a faculty member, or share the campus visit contacts. You can also call the Admissions Office at {config.ADMISSIONS_PHONE}.")

_SMALL_TALK = {
    "greeting": ("Hello{name}! 👋 I'm SRU Buddy, the admissions assistant of SR University. Ask me about courses, "
                 "fees, scholarships, hostels or placements.",
                 "Hello again{name}! 👋 What would you like to know about SR University today?"),
    "how_are_you": ("I'm doing well, thank you{name}! Ready to help with anything about SR University admissions. "
                    "What would you like to know?",) * 2,
    "thanks": ("You're welcome{name}! If you have more questions about SR University, just ask.",) * 2,
    "bye": (f"Goodbye{{name}}! All the best. You can come back any time, and the Admissions Office is on "
            f"{config.ADMISSIONS_PHONE}.",) * 2,
    "who_are_you": (f"I'm SRU Buddy, the AI admissions assistant of SR University, Warangal. I can work out your fee "
                    f"and scholarship, check eligibility, compare courses, tell you about our faculty, help you "
                    f"plan a campus visit and arrange a counsellor callback. I'm an AI, so the Admissions Office ({config.ADMISSIONS_PHONE}) gives "
                    f"the final confirmation.",) * 2,
}
_SMALL_TALK_CHIPS = ["B.Tech CSE fees", "Scholarship for my marks", "Placements at SRU", "Plan a campus visit"]


def _cache_key(message: str) -> str:
    import hashlib
    norm = re.sub(r"[^a-z0-9 ]+", " ", message.lower())
    return "sru:answer:" + hashlib.sha1(" ".join(norm.split()).encode()).hexdigest()


# -------------------------------------------------------------------- the agent ----
async def run_agent(message: str, session_id: str, conversation_id=None, client=None):
    """Async generator of events for one student message."""
    message = (message or "").strip()[:config.AGENT_MAX_MESSAGE_CHARS]
    yield {"type": "start", "conversation_id": conversation_id}
    if not message:
        yield {"type": "error", "detail": "Please type a question."}
        return

    # Three independent reads, done together (each one may need a trip to Redis or the database).
    profile, history, conv_state = await asyncio.gather(
        memory.get_profile(session_id), memory.get_history(session_id, conversation_id),
        memory.get_conversation_state(session_id, conversation_id))
    ctx = {"session_id": session_id, "conversation_id": conversation_id, "profile": profile}
    intent = intents.classify_agent_intent(message, conv_state)
    used, cards = [], []

    async def set_state(**fields):
        conv_state.update(fields)
        await memory.update_conversation_state(session_id, conversation_id, **fields)

    async def clear_pending():
        await set_state(pending_action=None, pending_phone=None, pending_name=None, pending_turns=0)

    # ---- 1. Things the code can answer by itself ------------------------------------------
    if intent == "DATE_QUERY":
        async for ev in _say(f"Today is {date.today():%B %d, %Y}.", message, session_id, conversation_id,
                             suggestions=["Plan a campus visit", "What are the B.Tech CSE fees?",
                                          "Hostel rules & curfew"]):
            yield ev
        return

    if intent == "CONFUSION_QUERY":
        async for ev in _say("Sorry for the confusion! I can share how to reach the campus and whom to contact "
                             "to plan a visit, or answer anything else about admissions.", message, session_id,
                             conversation_id, suggestions=["Plan a campus visit", "How to reach the campus",
                                                           "B.Tech CSE fees"]):
            yield ev
        return

    # Greetings and thanks need no model call.
    chat = intents.small_talk(message) if intent not in ("DATE_CONFIRMATION_YES", "DATE_CONFIRMATION_NO") else None
    if chat:
        seen_before = any(h.get("role") in ("model", "assistant") for h in history)
        name_bit = f", {_first_name(profile['name'])}" if profile.get("name") else ""
        text = _SMALL_TALK[chat][1 if seen_before else 0].format(name=name_bit)
        async for ev in _say(text, message, session_id, conversation_id, suggestions=_SMALL_TALK_CHIPS):
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
                    text += f" Your saved request (reference **{result.get('reference')}**) has the new number too."
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
    if asked_for_call:
        # "Ask admissions to call me" right after visit guidance is a visit callback.
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
                await set_state(awaiting_date_confirmation=False, pending_visit_date=None, confirmed_visit_date=None)
                if _has_other_question(message, name):
                    # The request is saved; let the model answer the rest of the message too.
                    action_note = (f"The system has ALREADY saved this student's {what} request in this turn: "
                                   f"reference {result.get('reference')}, name {result.get('name')}, phone ending "
                                   f"{result.get('phone_last4')}. Confirm that in one line with the reference, then "
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

    # ---- 4. Campus visits: guide to the admissions team; never book or confirm -----------------
    if conv_state.get("awaiting_date_confirmation") or conv_state.get("pending_visit_date"):
        await set_state(awaiting_date_confirmation=False, pending_visit_date=None, confirmed_visit_date=None)
    asks_to_visit = intents.is_visit_request(message)
    visit = (tools.resolve_campus_visit_date(message, today=date.today())
             if intent.startswith("CAMPUS_VISIT") or asks_to_visit else {})
    # A detailed question about visiting (parents, timings, directions...) goes to the model, which
    # follows the same never-book rules; a plain "I want to visit" gets the guide at once.
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

    # ---- 4b. Fee enquiries: collect the details a correct fee needs, then calculate ----------------
    intake_decision = None
    if not action_note and not action and conv_state.get("pending_action") not in ("callback", "campus_visit") \
            and intent not in ("CAMPUS_VISIT_BOOKING", "CAMPUS_VISIT_BOOKING_WITH_DATE", "DATE_CONFIRMATION_YES",
                               "DATE_CONFIRMATION_NO"):
        intake_decision = fee_intake.decide(message, profile, conv_state.get("fee_intake"))
        if intake_decision and intake_decision["action"] == "ask":
            await set_state(fee_intake=intake_decision["state"])
            async for ev in _say(intake_decision["text"], message, session_id, conversation_id,
                                 suggestions=intake_decision["chips"]):
                yield ev
            return
        if intake_decision or conv_state.get("fee_intake"):
            await set_state(fee_intake=None)

    # ---- 5. Everything else: the model, with tools --------------------------------------------
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

    # The same first question (often a suggestion button) from a student we know nothing about
    # gets the saved answer instead of a new model call.
    personal = any(profile.get(k) not in (None, "") for k in memory.PUBLIC_PROFILE_KEYS)
    cacheable = (client is None and config.AGENT_ANSWER_CACHE_SECONDS > 0 and not history and not personal
                 and not pending and not action_note and not tools.find_phone(message))
    if cacheable:
        saved = await memory.get_cached_answer(_cache_key(message), config.AGENT_ANSWER_CACHE_SECONDS)
        if saved:
            async for ev in _say(saved["answer"], message, session_id, conversation_id,
                                 saved.get("used", []), saved.get("cards", []), saved.get("suggestions", [])):
                yield ev
            return

    # Do the look-ups the code can do for free, so the model can usually answer in ONE call:
    # the fee calculation for a plain fee question, and the handbook passages for everything else.
    prefetched_fee = None
    if intake_decision and intake_decision["action"] == "calculate":
        fee_args = dict(intake_decision["args"])
        hostel_args = _fee_args_from_message(message, profile) or {}
        if hostel_args.get("hostel"):
            fee_args["hostel"] = hostel_args["hostel"]
    else:
        fee_args = _fee_args_from_message(message, profile) if not action_note else None
    if fee_args:
        fee_result = await tools.run_tool("calculate_fee", fee_args, ctx)
        if fee_result.get("status") == "ok":
            prefetched_fee = fee_result
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
    if not prefetched_fee and not action_note and faculty.is_faculty_question(message):
        fac = await tools.run_tool("find_faculty", {"query": message}, ctx)
        if fac.get("status") == "ok":
            prefetched_faculty = fac
    faculty_note = None
    if prefetched_faculty:
        import json as _json
        faculty_note = _json.dumps({k: v for k, v in prefetched_faculty.items() if k != "status"},
                                   ensure_ascii=False)[:3500]
    passages = "" if (prefetched_fee or prefetched_faculty) else _handbook_context(message)

    models = []
    for m in (config.AGENT_MODEL, *_FALLBACK_MODELS):
        if m and m not in models:
            models.append(m)
    tool_decl = _tool_declarations()
    final = ""
    link = {"fixed": client, "key": None, "models": models, "model_idx": 0, "error_kind": None,
            "thinking": True}
    # Words are shown while Gemini writes them, except when the reply is about a callback / visit
    # request or a cancellation: those are checked for honesty first and only then shown.
    live_ok = not (pending or action_note or _CANCEL_ASK.search(message) or intents.is_callback_request(message))
    streamed = ""
    try:
        link["key"] = None if client else _ring.next_key()
        if link["fixed"] is None and not link["key"]:
            link["fixed"] = get_client()
        for round_no in range(config.AGENT_MAX_TOOL_ROUNDS + 1):
            last_round = round_no == config.AGENT_MAX_TOOL_ROUNDS
            cfg = types.GenerateContentConfig(
                system_instruction=build_system_prompt(
                    ctx["profile"], variant_id=variant_id, used_openings=assistant_openings,
                    about_sru_angle=about_sru_angle, pending_action=pending, action_note=action_note,
                    handbook_passages=passages, fee_result=fee_note, faculty_result=faculty_note),
                tools=[tool_decl],
                temperature=0.2,
                max_output_tokens=900,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                # On the last round the model must answer in words, not call more tools.
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="NONE" if last_round else "AUTO")),
            )
            if live_ok and _can_stream(link):
                resp, round_text = None, ""
                async for kind, value in _generate_stream(contents, cfg, link):
                    if kind == "text":
                        round_text += value
                        streamed += value
                        yield {"type": "token", "delta": value}
                    else:
                        resp = value
            else:
                resp = await _generate(contents, cfg, link)
            calls = resp.function_calls or []
            if not calls:
                final = (resp.text or "").strip()
                if not final and not last_round and round_no == 0:
                    # An empty reply (the model sometimes returns nothing): ask once more, plainly.
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(
                        text="(Please answer the student's last message in a few clear sentences.)")]))
                    continue
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
        if not used:
            offline = _offline_fee_reply(message, ctx, prefetched_fee)
            if offline:
                text, fee = offline
                for ev in _tool_events("calculate_fee", fee):
                    yield ev
                async for ev in _say(text, message, session_id, conversation_id,
                                     [{"name": "calculate_fee", "status": "ok", "is_action": False}],
                                     [{"type": "calculate_fee", "data": fee}]):
                    yield ev
                return
        if link.get("error_kind") in ("rate", "busy"):
            # The AI limit is reached: give the handbook passage if one fits, else say what still works.
            text = (None if used else _offline_knowledge_reply(message)) or _LIMIT_REPLY
            async for ev in _say(text, message, session_id, conversation_id, used, cards,
                                 ["CSE fee with 85%", "Call me", "Plan a campus visit"]):
                yield ev
            return
        yield {"type": "error", "detail": FALLBACK}
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

    final = final or canned_action_text or FALLBACK
    if not streamed:
        for piece in _chunks(final):
            yield {"type": "token", "delta": piece}
    # (when the words were streamed live, the 'done' event carries the final text, which the
    # browser shows in place of what it streamed)
    await memory.append_history(session_id, message, final, conversation_id)

    # ---- 7. Cards and follow-up suggestions ---------------------------------------------------
    try:
        from app.services.card_service import generate_cards

        # Videos are matched on their own titles and keywords (video_service.get_keyword_videos),
        # so no embedding call is spent here.
        query_embedding = None

        contextual_cards = generate_cards(
            user_message=message, answer=final, profile=ctx.get("profile"),
            session_id=session_id, query_embedding=query_embedding, keyword_videos=True)
        personalised = any(t["name"] in _FEE_TOOLS for t in used)
        for c in contextual_cards:
            if personalised and c.get("type") == "fee_breakdown":
                continue  # the student already has their own numbers; no generic table underneath
            if c not in cards:
                cards.append(c)
    except Exception as card_err:
        log.warning("Could not generate contextual cards for agent: %s", card_err)

    suggestions = []
    try:
        from . import followups
        department = None
        fac = next((c["data"] for c in cards if c.get("type") == "find_faculty"), None)
        if fac:
            department = fac.get("department") or next(
                (p.get("department") for p in fac.get("faculty") or [] if p.get("department")), None)
        suggestions = followups.suggest(message, used, ctx.get("profile"), department)
    except Exception as sugg_err:
        log.warning("Could not generate suggestions for agent: %s", sugg_err)

    if cacheable and final != FALLBACK and not any(t["is_action"] for t in used):
        await memory.set_cached_answer(_cache_key(message), {
            "answer": final, "used": used, "cards": cards, "suggestions": suggestions})
    yield _done(conversation_id, final, used, cards, suggestions)
