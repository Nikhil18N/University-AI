"""The agent's tools: what SRU Buddy can DO, not just say.

Each tool has (1) a declaration the AI model reads to decide when to call it
and (2) a Python function that runs it. To add a tool, add both.

TWO THINGS TO WIRE TO YOUR EXISTING CODE (see README, Step 4):
  set_knowledge_search(fn)  -> your existing ChromaDB document search
  set_lead_saver(fn)        -> optional; default posts to your /api/v1/leads
"""
import re
import urllib.parse
from datetime import date, datetime, timedelta

import httpx

from . import config, fees, memory

# ---------------------------------------------------------------- hooks ----
_knowledge_search = None
_lead_saver = None


def set_knowledge_search(fn):
    """fn: async (query: str) -> list of {"title": str, "text": str}"""
    global _knowledge_search
    _knowledge_search = fn


def set_lead_saver(fn):
    """fn: async (lead: dict) -> dict. Replace the default HTTP saver if you prefer."""
    global _lead_saver
    _lead_saver = fn


async def _default_lead_saver(lead: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(config.LEADS_API_URL, json=lead)
        resp.raise_for_status()
        return resp.json()


# -------------------------------------------------------------- helpers ----
def clean_phone(phone: str):
    """Return a 10-digit Indian mobile number, or None if it is not valid."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None


def _score_text(profile: dict):
    bits = []
    if profile.get("percent") is not None:
        bits.append(f"{profile['percent']}%")
    if profile.get("eapcet_rank") is not None:
        bits.append(f"EAPCET rank {profile['eapcet_rank']}")
    return ", ".join(bits) or None


async def _save_lead(args: dict, ctx: dict, request_type: str, extra: dict) -> dict:
    if args.get("consent") is not True:
        return {"status": "needs_consent",
                "ask_student": "Ask: 'May SR University's admissions team contact you on this "
                               "number about admissions?' Call this tool again only after a clear yes."}
    name = (args.get("name") or "").strip()
    phone = clean_phone(args.get("phone", ""))
    if len(name) < 2:
        return {"status": "invalid", "problem": "Name is missing. Ask for the student's full name."}
    if not phone:
        return {"status": "invalid", "problem": "Phone must be a 10-digit Indian mobile number. Ask again."}
    profile = ctx.get("profile", {})
    lead = {
        "name": name, "phone": phone,
        "program_interest": args.get("program_interest") or profile.get("program_interest"),
        "score": _score_text(profile),
        "exam_type": profile.get("board"),
        "source": "chat_inquiry",
        "conversation_id": ctx.get("conversation_id"),
        "metadata": {"request_type": request_type, "consent": True,
                     "is_parent": profile.get("is_parent"), **extra},
    }
    try:
        saved = await (_lead_saver or _default_lead_saver)(lead)
    except Exception as exc:  # never show a raw error to the student
        return {"status": "failed", "problem": "Could not save the request right now.",
                "fallback": f"Ask the student to call {config.ADMISSIONS_PHONE}.", "_error": str(exc)}
    await memory.update_profile(ctx["session_id"], name=name, phone_saved=True)
    return {"status": "saved", "reference": str(saved.get("id", ""))[:8], "name": name,
            "phone_last4": phone[-4:], **extra}


# ---------------------------------------------------------------- tools ----
async def tool_calculate_fee(args, ctx):
    p = ctx.get("profile", {})
    return fees.calculate_fee(
        program=args.get("program") or p.get("program_interest") or "",
        percent=args.get("percent", p.get("percent")),
        board=args.get("board") or p.get("board") or "state_board",
        eapcet_rank=args.get("eapcet_rank", p.get("eapcet_rank")),
        jee_percentile=args.get("jee_percentile"),
        hostel=args.get("hostel", "none"),
        specialization=bool(args.get("specialization", False)),
    )


async def tool_check_eligibility(args, ctx):
    return fees.check_eligibility(args.get("program", ""), args.get("percent", 0))


async def tool_list_programs(args, ctx):
    return fees.list_programs()


async def tool_search_university_info(args, ctx):
    if _knowledge_search is None:
        return {"status": "not_wired", "note": "Knowledge search is not connected yet. "
                "Give the admissions phone number instead of guessing."}
    try:
        hits = await _knowledge_search(args.get("query", ""))
    except Exception as exc:
        return {"status": "failed", "_error": str(exc)}
    if not hits:
        return {"status": "no_results", "note": "Nothing found. Say you do not have this "
                "confirmed and give the admissions phone number. Do not guess."}
    return {"status": "ok", "passages": [
        {"title": h.get("title", ""), "text": (h.get("text") or "")[:1200]} for h in hits[:5]]}


async def tool_remember_student_details(args, ctx):
    allowed = ("name", "program_interest", "percent", "board", "eapcet_rank", "city", "is_parent", "language")
    profile = await memory.update_profile(ctx["session_id"], **{k: args.get(k) for k in allowed})
    ctx["profile"] = profile
    return {"status": "remembered", "profile": {k: v for k, v in profile.items() if k != "phone_saved"}}


async def tool_request_counsellor_callback(args, ctx):
    return await _save_lead(args, ctx, "callback",
                            {"preferred_time": args.get("preferred_time") or "any time"})


async def tool_book_campus_visit(args, ctx):
    try:
        visit = datetime.strptime(args.get("visit_date", ""), "%Y-%m-%d").date()
    except ValueError:
        return {"status": "invalid", "problem": "Visit date must be a real date. Ask which day they want."}
    today = date.today()
    if visit < today or visit > today + timedelta(days=90):
        return {"status": "invalid", "problem": f"Visit date must be between {today} and "
                                               f"{today + timedelta(days=90)}. Ask for another date."}
    visitors = max(1, min(int(args.get("visitors") or 1), 10))
    return await _save_lead(args, ctx, "campus_visit",
                            {"visit_date": visit.isoformat(), "visitors": visitors,
                             "note": "Request only. The admissions team will confirm the visit by phone."})


async def tool_get_contact_and_apply_links(args, ctx):
    out = {"status": "ok", "apply_online": config.APPLY_URL, "phone": config.ADMISSIONS_PHONE,
           "email": config.ADMISSIONS_EMAIL}
    if config.ADMISSIONS_WHATSAPP:
        text = urllib.parse.quote("Hi, I have a question about SR University admissions: "
                                  + (args.get("topic") or ""))
        out["whatsapp"] = f"https://wa.me/{config.ADMISSIONS_WHATSAPP}?text={text}"
    return out


def _obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


_PROGRAM = {"type": "string", "description": "Course in the student's words, e.g. 'cse', 'mech', 'mba'."}
_PERCENT = {"type": "number", "description": "10+2 / Intermediate percentage (0-100). Convert marks out of 1000 to %."}
_CONSENT = {"type": "boolean", "description": "true ONLY if the student clearly agreed, in this chat, to be contacted."}
_PHONE = {"type": "string", "description": "10-digit mobile number exactly as the student typed it."}

# name -> (function, short label shown to the student, declaration)
TOOLS = {
    "calculate_fee": (tool_calculate_fee, "Calculating your fee", {
        "description": "Official fee and merit scholarship for one student. ALWAYS call this for any "
                       "question about fees, scholarship, total cost or cost after scholarship. "
                       "Never state a fee from memory.",
        "parameters_json_schema": _obj({
            "program": _PROGRAM, "percent": _PERCENT,
            "board": {"type": "string", "enum": ["state_board", "cbse"]},
            "eapcet_rank": {"type": "integer", "description": "TG/AP EAPCET (EAMCET) rank."},
            "jee_percentile": {"type": "number"},
            "hostel": {"type": "string", "enum": ["none", "non_ac_4", "non_ac_3", "ac_4", "ac_3"]},
            "specialization": {"type": "boolean", "description": "true for AI & ML, Data Science, Cyber Security tracks."},
        }, ["program"])}),
    "check_eligibility": (tool_check_eligibility, "Checking eligibility", {
        "description": "Checks if a student meets the minimum marks for a program. Call whenever marks "
                       "and a program are known and the student asks 'can I join'.",
        "parameters_json_schema": _obj({"program": _PROGRAM, "percent": _PERCENT}, ["program", "percent"])}),
    "list_programs": (tool_list_programs, "Looking up programs", {
        "description": "Lists programs with tuition and minimum marks. Use when the student has not chosen a course.",
        "parameters_json_schema": _obj({})}),
    "search_university_info": (tool_search_university_info, "Searching university information", {
        "description": "Searches official SRU documents for anything that is NOT a fee calculation: "
                       "hostel rules, placements, documents, dates, transport, accreditation, refund policy.",
        "parameters_json_schema": _obj({"query": {"type": "string"}}, ["query"])}),
    "remember_student_details": (tool_remember_student_details, "Noting your details", {
        "description": "Saves facts the student shares so they never have to repeat them: name, course, "
                       "marks, board, rank, city, whether a parent is asking, language. Call as soon as "
                       "any of these is mentioned.",
        "parameters_json_schema": _obj({
            "name": {"type": "string"}, "program_interest": {"type": "string"}, "percent": _PERCENT,
            "board": {"type": "string", "enum": ["state_board", "cbse"]},
            "eapcet_rank": {"type": "integer"}, "city": {"type": "string"},
            "is_parent": {"type": "boolean"},
            "language": {"type": "string", "description": "english, telugu, hindi or tenglish"}})}),
    "request_counsellor_callback": (tool_request_counsellor_callback, "Arranging a callback", {
        "description": "Asks the admissions team to phone the student. Use only after the student gave "
                       "name and phone AND agreed to be contacted.",
        "parameters_json_schema": _obj({
            "name": {"type": "string"}, "phone": _PHONE, "program_interest": {"type": "string"},
            "preferred_time": {"type": "string", "description": "e.g. 'tomorrow evening'"},
            "consent": _CONSENT}, ["name", "phone", "consent"])}),
    "book_campus_visit": (tool_book_campus_visit, "Requesting your campus visit", {
        "description": "Sends a campus visit request to the admissions team. Needs name, phone, date and consent.",
        "parameters_json_schema": _obj({
            "name": {"type": "string"}, "phone": _PHONE,
            "visit_date": {"type": "string", "description": "YYYY-MM-DD"},
            "visitors": {"type": "integer"}, "consent": _CONSENT},
            ["name", "phone", "visit_date", "consent"])}),
    "get_contact_and_apply_links": (tool_get_contact_and_apply_links, "Getting contact details", {
        "description": "Official apply link, admissions phone, email and WhatsApp link. Use for 'how to "
                       "apply', 'contact number', or when you cannot answer something.",
        "parameters_json_schema": _obj({"topic": {"type": "string"}})}),
}

# Tools that change something outside the chat (shown as 'actions' in the UI and logs).
ACTION_TOOLS = {"request_counsellor_callback", "book_campus_visit"}


async def run_tool(name: str, args: dict, ctx: dict) -> dict:
    if name not in TOOLS:
        return {"status": "unknown_tool"}
    try:
        return await TOOLS[name][0](args or {}, ctx)
    except Exception as exc:
        return {"status": "failed", "problem": "The tool had an internal error.", "_error": str(exc)}
