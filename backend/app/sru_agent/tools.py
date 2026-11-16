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
_lead_canceller = None


def set_knowledge_search(fn):
    """fn: async (query: str) -> list of {"title": str, "text": str}"""
    global _knowledge_search
    _knowledge_search = fn


def set_lead_saver(fn):
    """fn: async (lead: dict) -> dict. Replace the default HTTP saver if you prefer."""
    global _lead_saver
    _lead_saver = fn


def set_lead_canceller(fn):
    """fn: async (lead_id: str) -> bool. Replace the default HTTP canceller if you prefer."""
    global _lead_canceller
    _lead_canceller = fn


async def _default_lead_saver(lead: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(config.LEADS_API_URL, json=lead)
        resp.raise_for_status()
        return resp.json()


async def _default_lead_canceller(lead_id: str) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{config.LEADS_API_URL}/{lead_id}/status",
            json={"status": "rejected", "metadata": {"do_not_contact": True}},
        )
        return resp.status_code in (200, 204)


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
    lead_id = str(saved.get("id", "")) if isinstance(saved, dict) else ""
    update_kwargs = {"name": name, "phone_saved": True}
    if lead_id:
        update_kwargs["last_lead_id"] = lead_id
    await memory.update_profile(ctx["session_id"], **update_kwargs)
    if "profile" in ctx:
        ctx["profile"].update(update_kwargs)
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
    return {"status": "remembered", "profile": {k: v for k, v in profile.items() if k not in ("phone_saved", "last_lead_id")}}


async def tool_request_counsellor_callback(args, ctx):
    return await _save_lead(args, ctx, "callback",
                            {"preferred_time": args.get("preferred_time") or "any time"})


async def tool_cancel_contact_request(args, ctx):
    profile = ctx.get("profile", {})
    last_lead_id = profile.get("last_lead_id")
    if not last_lead_id:
        return {"status": "nothing_to_cancel"}

    try:
        canceller = _lead_canceller or _default_lead_canceller
        success = await canceller(str(last_lead_id))
        if success:
            await memory.update_profile(ctx["session_id"], last_lead_id=None)
            if "profile" in ctx:
                ctx["profile"]["last_lead_id"] = None
            return {"status": "cancelled"}
        return {"status": "not_cancelled"}
    except Exception as exc:
        return {"status": "not_cancelled", "_error": str(exc)}


def resolve_campus_visit_date(date_str: str, today: date | None = None) -> dict:
    """Deterministically resolve and validate a campus visit date relative to today.
    Handles relative tokens ('today', 'tomorrow'), ordinals ('17th', '17'),
    weekdays ('next Monday', 'this Friday'), month names ('Nov 17'), and standard date formats.
    Validates operating hours/days (SRU is closed on Sundays for visits).
    """
    today = today or date.today()
    if not date_str or not isinstance(date_str, str):
        return {
            "date": None, "iso": None, "human": None,
            "is_valid": False, "is_sunday": False, "is_outside_window": False,
            "is_ambiguous": True, "reason": "No date provided.", "alternative_suggestions": []
        }

    s = str(date_str).strip().lower()
    # Strip common conversational phrases
    s = re.sub(r"^(i\s+want\s+to\s+visit\s+(on\s+)?|i\s+would\s+like\s+to\s+visit\s+(on\s+)?|visit\s+(on\s+)?|on\s+|for\s+)", "", s).strip()
    s = s.replace(",", " ").replace(".", " ").strip()

    target_date: date | None = None

    # 1. Relative tokens
    if s in ("today", "todays"):
        target_date = today
    elif s in ("tomorrow", "tomorrows", "tmrw"):
        target_date = today + timedelta(days=1)
    elif s in ("day after tomorrow", "day after tmrw"):
        target_date = today + timedelta(days=2)

    # 2. Weekday expressions (e.g. "next monday", "this friday", "on monday")
    weekdays = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }
    m_weekday = re.search(r"\b(next|this|coming)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b", s)
    if not target_date and m_weekday:
        prefix, wday_name = m_weekday.group(1), m_weekday.group(2)
        target_wday = weekdays[wday_name]
        days_ahead = (target_wday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # If today is Monday and user asks "next Monday", target next week
        elif prefix == "next" and days_ahead < 7:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)

    # 3. Standard ISO YYYY-MM-DD
    if not target_date:
        try:
            target_date = datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            pass

    # 4. Indian formats: DD-MM-YYYY, DD/MM/YYYY, DD MM YYYY
    if not target_date:
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d %m %Y"):
            try:
                target_date = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                pass

    # 5. Clean ordinals: 17th -> 17, 1st -> 1, 2nd -> 2, 3rd -> 3
    s_clean = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", s).strip()

    if not target_date:
        for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                target_date = datetime.strptime(s_clean, fmt).date()
                break
            except ValueError:
                pass

    month_names = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
        "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    if not target_date:
        tokens = s_clean.split()
        found_day = None
        found_month = None
        found_year = None
        for t in tokens:
            if t in month_names:
                found_month = month_names[t]
            elif t.isdigit():
                val = int(t)
                if val > 2000:
                    found_year = val
                elif 1 <= val <= 31 and found_day is None:
                    found_day = val
                elif 1 <= val <= 12 and found_month is None:
                    found_month = val

        if found_day is not None and found_month is not None:
            yr = found_year or today.year
            try:
                d = date(yr, found_month, found_day)
                if not found_year and d < today - timedelta(days=7):
                    d = date(yr + 1, found_month, found_day)
                target_date = d
            except ValueError:
                pass

    # 6. Bare day number or ordinal: e.g. "17th", "17", "on 17"
    if not target_date:
        m = re.search(r"\b(\d{1,2})\b", s_clean)
        if m:
            day_val = int(m.group(1))
            if 1 <= day_val <= 31:
                try:
                    # If day_val >= today.day, it refers to THIS current month
                    if day_val >= today.day:
                        target_date = date(today.year, today.month, day_val)
                    else:
                        # Target next month
                        next_month = today.month + 1 if today.month < 12 else 1
                        next_year = today.year if today.month < 12 else today.year + 1
                        target_date = date(next_year, next_month, day_val)
                except ValueError:
                    pass

    if not target_date:
        return {
            "date": None, "iso": None, "human": None,
            "is_valid": False, "is_sunday": False, "is_outside_window": False,
            "is_ambiguous": True,
            "reason": f"Could not determine a valid date from '{date_str}'. Please provide a date like 'tomorrow', '17th Nov', or 'YYYY-MM-DD'.",
            "alternative_suggestions": []
        }

    iso_str = target_date.isoformat()
    human_str = target_date.strftime("%B %d, %Y")
    max_date = today + timedelta(days=90)

    # Availability Validation: SR University campus visits are conducted Monday - Saturday
    is_sunday = (target_date.weekday() == 6)
    alt_suggestions = []
    if is_sunday:
        sat_alt = target_date - timedelta(days=1)
        mon_alt = target_date + timedelta(days=1)
        if sat_alt >= today:
            alt_suggestions.append({"date": sat_alt, "iso": sat_alt.isoformat(), "human": sat_alt.strftime("%A, %B %d, %Y")})
        alt_suggestions.append({"date": mon_alt, "iso": mon_alt.isoformat(), "human": mon_alt.strftime("%A, %B %d, %Y")})

    is_outside = target_date < today or target_date > max_date

    return {
        "date": target_date,
        "iso": iso_str,
        "human": human_str,
        "is_valid": not is_sunday and not is_outside,
        "is_sunday": is_sunday,
        "is_outside_window": is_outside,
        "is_ambiguous": False,
        "reason": None if (not is_sunday and not is_outside) else (
            f"The campus is closed for visits on Sunday, {human_str}." if is_sunday else
            f"Campus visits can only be scheduled within the next 90 days (between {today:%d %B %Y} and {max_date:%d %B %Y})."
        ),
        "alternative_suggestions": alt_suggestions,
    }


def parse_flexible_visit_date(date_str: str, today: date | None = None) -> date | None:
    """Backwards-compatible wrapper returning datetime.date or None."""
    res = resolve_campus_visit_date(date_str, today=today)
    return res.get("date") if res.get("is_valid") else (res.get("date") if res.get("is_sunday") or res.get("is_outside_window") else None)


async def tool_book_campus_visit(args, ctx):
    raw_date = args.get("visit_date", "")
    res = resolve_campus_visit_date(raw_date)
    if not res.get("date"):
        return {"status": "invalid", "problem": res.get("reason", f"Could not determine a valid date from '{raw_date}'. Please provide a date like 'tomorrow', '17th Nov', or 'YYYY-MM-DD'.")}
    
    if res.get("is_sunday"):
        alts = res.get("alternative_suggestions", [])
        alt_text = f" Would Saturday, {alts[0]['human']} or Monday, {alts[1]['human']} work for you?" if len(alts) >= 2 else ""
        return {
            "status": "invalid",
            "problem": f"Campus visits are conducted Monday through Saturday (9:30 AM to 4:30 PM). SR University is closed for visits on Sunday, {res['human']}.{alt_text}"
        }

    today = date.today()
    if res.get("is_outside_window"):
        return {
            "status": "invalid",
            "problem": f"Campus visits can only be scheduled within the next 90 days. {res['human']} is outside this window. Please choose a date within 90 days or contact Admissions at {config.ADMISSIONS_PHONE}."
        }

    visit = res["date"]
    visitors = max(1, min(int(args.get("visitors") or 1), 10))
    result = await _save_lead(args, ctx, "campus_visit",
                            {"visit_date": visit.isoformat(),
                             "confirmed_date": res["human"],
                             "visitors": visitors,
                             "note": "Request only. The admissions team will confirm the visit by phone."})
    if result.get("status") == "saved":
        result["confirmed_date"] = res["human"]
        result["visit_date"] = visit.isoformat()
    return result


async def tool_get_contact_and_apply_links(args, ctx):
    out = {"status": "ok", "apply_online": config.APPLY_URL, "phone": config.ADMISSIONS_PHONE,
           "email": config.ADMISSIONS_EMAIL}
    if config.ADMISSIONS_WHATSAPP:
        text = urllib.parse.quote("Hi, I have a question about SR University admissions: "
                                  + (args.get("topic") or ""))
        out["whatsapp"] = f"https://wa.me/{config.ADMISSIONS_WHATSAPP}?text={text}"
    return out


async def tool_get_university_videos(args, ctx):
    topic = (args.get("topic") or "").strip()
    try:
        from app.api.v1.deps import get_embedding_provider
        from app.services.video_service import get_relevant_videos, load_videos
        provider = get_embedding_provider()
        search_text = topic or "campus life at SR University"
        emb = await provider.embed_single(search_text)
        videos = get_relevant_videos(user_message=search_text, query_embedding=emb, is_explicit=True)
        if not videos:
            campus_vids = [v for v in load_videos() if v.get("category") == "Campus Tour & Infrastructure"]
            videos = campus_vids[:2] if campus_vids else load_videos()[:2]
        return {
            "status": "ok",
            "type": "video_recommendations",
            "title": f"Official SR University Videos: {topic}" if topic else "Official SR University Video Tours",
            "channel_name": "SR University Official",
            "channel_url": "https://www.youtube.com/@SRUniversity/videos",
            "videos": videos,
        }
    except Exception as exc:
        return {"status": "failed", "problem": "Could not retrieve videos right now.", "_error": str(exc)}


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
                       "question about fees, scholarship, total cost, or per-semester breakdown. "
                       "Pass hostel parameter ONLY if the student explicitly selected or asked for hostel (e.g. 'with hostel'). "
                       "If the student did not ask for hostel, keep hostel='none'. Never state a fee from memory.",
        "parameters_json_schema": _obj({
            "program": _PROGRAM, "percent": _PERCENT,
            "board": {"type": "string", "enum": ["state_board", "cbse"]},
            "eapcet_rank": {"type": "integer", "description": "TG/AP EAPCET (EAMCET) rank."},
            "jee_percentile": {"type": "number"},
            "hostel": {"type": "string", "enum": ["none", "non_ac_4", "non_ac_3", "ac_4", "ac_3"], "description": "Pass ONLY if student explicitly requested hostel. Default is 'none'."},
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
            "visit_date": {"type": "string", "description": "Preferred date e.g. 'YYYY-MM-DD', 'tomorrow', '17th Nov', or day number like '17th' (relative to current date)"},
            "visitors": {"type": "integer"}, "consent": _CONSENT},
            ["name", "phone", "visit_date", "consent"])}),
    "get_contact_and_apply_links": (tool_get_contact_and_apply_links, "Getting contact details", {
        "description": "Official apply link, admissions phone, email and WhatsApp link. Use for 'how to "
                       "apply', 'contact number', or when you cannot answer something.",
        "parameters_json_schema": _obj({"topic": {"type": "string"}})}),
    "get_university_videos": (tool_get_university_videos, "Finding official university videos", {
        "description": "Finds official SR University YouTube videos and tours for campus life, hostels, "
                       "placements, labs, sports, student clubs, and infrastructure. Call whenever the student "
                       "asks to see, watch, or get videos/tours of SR University.",
        "parameters_json_schema": _obj({"topic": {"type": "string", "description": "e.g. 'campus', 'hostel life', 'placements', 'infrastructure'"}})}),
    "cancel_contact_request": (tool_cancel_contact_request, "Cancelling contact request", {
        "description": "Cancels a previously requested counsellor callback or campus visit. Call when the "
                       "student asks to cancel their callback/visit or says 'don't contact me'.",
        "parameters_json_schema": _obj({"reason": {"type": "string", "description": "Optional reason for cancellation"}})}),
}

# Tools that change something outside the chat (shown as 'actions' in the UI and logs).
ACTION_TOOLS = {"request_counsellor_callback", "book_campus_visit", "cancel_contact_request"}


async def run_tool(name: str, args: dict, ctx: dict) -> dict:
    if name not in TOOLS:
        return {"status": "unknown_tool"}
    try:
        return await TOOLS[name][0](args or {}, ctx)
    except Exception as exc:
        return {"status": "failed", "problem": "The tool had an internal error.", "_error": str(exc)}
