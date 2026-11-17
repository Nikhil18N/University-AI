"""The agent's tools: what SRU Buddy can DO, not just say.

Each tool has (1) a declaration the AI model reads to decide when to call it
and (2) a Python function that runs it. To add a tool, add both.

THREE THINGS TO WIRE TO YOUR EXISTING CODE (done in app/main.py):
  set_knowledge_search(fn)  -> the ChromaDB document search
  set_lead_saver(fn)        -> saves a callback / visit request as a lead
  set_lead_canceller(fn)    -> marks a saved lead "do not contact"
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
    """fn: async (lead_id: str, reason: str) -> bool (True when the lead was marked do-not-contact)."""
    global _lead_canceller
    _lead_canceller = fn


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


_PHONE_IN_TEXT = re.compile(r"(?<![\d-])(?:\+?91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})(?!\d)")
_DIGIT_RUN = re.compile(r"(?<![\d,.])\d(?:[\s-]?\d){4,}(?![\d,.%])")


def find_phone(text: str):
    """First valid 10-digit Indian mobile number inside free text, else None."""
    for m in _PHONE_IN_TEXT.finditer(text or ""):
        phone = clean_phone(m.group(1))
        if phone:
            return phone
    return None


def find_bad_phone(text: str, min_digits: int = 8):
    """A phone-like run of digits that is NOT a valid mobile number (e.g. '12345678'), else None.
    Dates such as 2026-11-20 and amounts with commas are not mistaken for phone numbers."""
    if find_phone(text):
        return None
    for m in _DIGIT_RUN.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if min_digits <= len(digits) <= 13 and not re.fullmatch(r"(19|20)\d{6}", digits):
            return m.group(0).strip()
    return None


def _score_text(profile: dict):
    bits = []
    if profile.get("percent") is not None:
        bits.append(f"{profile['percent']}%")
    if profile.get("eapcet_rank") is not None:
        bits.append(f"EAPCET rank {profile['eapcet_rank']}")
    if profile.get("jee_percentile") is not None:
        bits.append(f"JEE Main {profile['jee_percentile']} percentile")
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
    profile = ctx.get("profile") or {}
    # Same request already saved in this chat (double click, model retry): do not create it twice.
    lead_key = f"{request_type}:{phone[-4:]}:{extra.get('visit_date', '')}"
    if profile.get("last_lead_key") == lead_key and profile.get("last_lead_id"):
        return {"status": "saved", "already_saved": True, "reference": str(profile["last_lead_id"])[:8],
                "name": name, "phone_last4": phone[-4:], **extra}
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
    lead_id = str((saved or {}).get("id", ""))
    label = "campus visit" if request_type == "campus_visit" else "callback"
    ctx["profile"] = await memory.update_profile(
        ctx["session_id"], name=name, phone_saved=True, last_lead_id=lead_id,
        last_lead_type=request_type, last_lead_key=lead_key,
        open_request=f"{label} request saved, reference {lead_id[:8]}")
    return {"status": "saved", "reference": lead_id[:8], "name": name,
            "phone_last4": phone[-4:], **extra}


_LEAD_PROFILE_KEYS = ("last_lead_id", "last_lead_type", "last_lead_key", "open_request", "phone_saved")


async def tool_cancel_contact_request(args, ctx):
    """Withdraw the callback / visit request saved from this chat. Honest about what really happened."""
    profile = ctx.get("profile") or await memory.get_profile(ctx["session_id"])
    lead_id = profile.get("last_lead_id")
    call_us = f"Ask the student to call {config.ADMISSIONS_PHONE} to have their number removed."
    if not lead_id:
        return {"status": "nothing_to_cancel",
                "note": "No callback or visit request was saved from this chat, so nothing was cancelled. "
                        "Say exactly that. If they shared their number somewhere else: " + call_us}
    reference = str(lead_id)[:8]
    request_type = profile.get("last_lead_type") or "callback"
    if _lead_canceller is None:
        return {"status": "not_available", "reference": reference, "request_type": request_type,
                "note": "This chat cannot cancel requests. Do NOT say it was cancelled. " + call_us}
    try:
        done = await _lead_canceller(str(lead_id), (args.get("reason") or "Student asked not to be contacted")[:200])
    except Exception as exc:
        return {"status": "failed", "reference": reference, "request_type": request_type,
                "note": "Could not cancel right now. Do NOT say it was cancelled. " + call_us, "_error": str(exc)}
    if not done:
        return {"status": "failed", "reference": reference, "request_type": request_type,
                "note": "The request could not be found. Do NOT say it was cancelled. " + call_us}
    ctx["profile"] = await memory.remove_profile_keys(ctx["session_id"], *_LEAD_PROFILE_KEYS)
    return {"status": "cancelled", "reference": reference, "request_type": request_type}


# ---------------------------------------------------------------- tools ----
async def tool_calculate_fee(args, ctx):
    p = ctx.get("profile") or {}
    result = fees.calculate_fee(
        program=args.get("program") or p.get("program_interest") or "",
        percent=args.get("percent", p.get("percent")),
        board=args.get("board") or p.get("board") or "state_board",
        eapcet_rank=args.get("eapcet_rank", p.get("eapcet_rank")),
        jee_percentile=args.get("jee_percentile", p.get("jee_percentile")),
        hostel=args.get("hostel") or "none",
        specialization=bool(args.get("specialization", False)),
        ib_score=args.get("ib_score", p.get("ib_score")),
        transport=bool(args.get("transport", False)),
    )
    if result.get("status") == "ok":
        summary = _fee_summary(result)
        ctx["last_fee"] = summary
        # Remember what the student told us, so "and with hostel?" works without asking again.
        told = {k: args.get(k) for k in ("percent", "board", "eapcet_rank", "jee_percentile", "ib_score")}
        if args.get("program"):
            told["program_interest"] = result.get("program_key") or args["program"]
        try:
            ctx["profile"] = await memory.update_profile(ctx["session_id"], last_fee=summary, **told)
        except Exception:
            pass
    return result


def _fee_summary(fee: dict) -> dict:
    """The few lines of a fee estimate worth sharing with a parent."""
    hostel = fee.get("hostel") or {}
    return {
        "program": fee.get("program"), "academic_year": fee.get("academic_year"),
        "scholarship_percent": fee.get("scholarship_percent"),
        "scholarship_basis": fee.get("scholarship_basis"),
        "tuition_first_year": fee.get("tuition_first_year"),
        "tuition_after_scholarship": fee.get("tuition_first_year_after_scholarship"),
        "hostel": hostel.get("type"), "hostel_per_year": hostel.get("per_year"),
        "sem1_total_payable": fee.get("sem1_total_payable"),
        "total_per_semester": fee.get("total_per_semester"),
        "first_year_total_payable": fee.get("first_year_total_payable"),
    }


async def tool_check_eligibility(args, ctx):
    p = ctx.get("profile") or {}
    return fees.check_eligibility(args.get("program") or p.get("program_interest") or "",
                                  args.get("percent", p.get("percent") or 0))


async def tool_get_program_info(args, ctx):
    p = ctx.get("profile") or {}
    return fees.program_info(args.get("program") or p.get("program_interest") or "")


async def tool_get_special_concessions(args, ctx):
    return fees.special_concessions(args.get("category") or "")


async def tool_compare_programs(args, ctx):
    p = ctx.get("profile") or {}
    return fees.compare_programs(
        args.get("program_a") or "", args.get("program_b") or "",
        percent=args.get("percent", p.get("percent")),
        board=args.get("board") or p.get("board") or "state_board",
        eapcet_rank=args.get("eapcet_rank", p.get("eapcet_rank")),
        jee_percentile=args.get("jee_percentile", p.get("jee_percentile")))


async def tool_share_fee_estimate(args, ctx):
    """A ready-to-send WhatsApp message with the student's latest fee estimate (to show parents)."""
    fee = ctx.get("last_fee") or (ctx.get("profile") or {}).get("last_fee")
    if not fee:
        return {"status": "no_estimate", "note": "No fee has been calculated in this chat yet. "
                "Call calculate_fee first, then call this tool again."}
    lines = [f"SR University {fee.get('academic_year', config.ADMISSION_YEAR)} fee estimate",
             f"Course: {fee.get('program')}"]
    if fee.get("scholarship_percent"):
        lines.append(f"Merit scholarship: {fee['scholarship_percent']}% ({fee.get('scholarship_basis')})")
    lines.append(f"Tuition, year 1: {fee.get('tuition_after_scholarship')} (before scholarship {fee.get('tuition_first_year')})")
    if fee.get("hostel"):
        lines.append(f"Hostel ({fee['hostel']}): {fee.get('hostel_per_year')} per year")
    lines += [f"Semester 1 payable: {fee.get('sem1_total_payable')}",
              f"Regular semester: {fee.get('total_per_semester')}",
              f"Year 1 total: {fee.get('first_year_total_payable')}",
              "Estimate only. Scholarship is subject to marksheet verification.",
              f"Admissions Office: {config.ADMISSIONS_PHONE} | Apply: {config.APPLY_URL}"]
    text = "\n".join(lines)
    out = {"status": "ok", "share_text": text,
           "whatsapp_share_url": "https://wa.me/?text=" + urllib.parse.quote(text),
           "how_to_present": "Give the student the whatsapp_share_url as a markdown link, e.g. "
                             "[Send this estimate on WhatsApp](URL). Do not paste the long URL as plain text."}
    if config.ADMISSIONS_WHATSAPP:
        out["ask_admissions_url"] = (f"https://wa.me/{config.ADMISSIONS_WHATSAPP}?text="
                                     + urllib.parse.quote("Hi, I have a question about this estimate:\n" + text))
    return out


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
    allowed = ("name", "program_interest", "percent", "board", "eapcet_rank", "jee_percentile",
               "ib_score", "city", "is_parent", "language")
    profile = await memory.update_profile(ctx["session_id"], **{k: args.get(k) for k in allowed})
    ctx["profile"] = profile
    hidden = ("phone_saved", "last_lead_id", "last_lead_key", "last_lead_type", "last_fee")
    return {"status": "remembered", "profile": {k: v for k, v in profile.items() if k not in hidden}}


async def tool_request_counsellor_callback(args, ctx):
    return await _save_lead(args, ctx, "callback",
                            {"preferred_time": args.get("preferred_time") or "any time"})


_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_WEEKDAYS_FULL = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
                  "saturday": 5, "sunday": 6}
_WEEKDAYS_SHORT = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3,
                   "fri": 4, "sat": 5, "sun": 6}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ORD = r"(?:st|nd|rd|th)"
# Things in a sentence that look like numbers but are not dates.
_DATE_NOISE = (
    re.compile(r"(?<![\d-])(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"),       # mobile numbers
    re.compile(r"(?<![\d/.-])\d{7,}(?![\d/.-])"),                                 # any other long number
    re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.?|p\.m\.?|o'?clock|hrs?)\b"),  # 10 am, 3:30 pm
    re.compile(r"\b\d{1,2}:\d{2}\b"),                                             # 10:30
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent(?:age|ile)?\b|marks?\b|lpa\b|lakhs?\b|k\b)"),
    re.compile(r"\b(?:rank|age|class|grade|room)\s*(?:is|of|:)?\s*\d+\b"),
    re.compile(r"\b\d+(?:st|nd|rd|th)?\s*(?:rank|class|grade|std|standard|year|sem(?:ester)?)\b"),
    re.compile(r"\b\d+\s*(?:people|persons?|members?|friends?|of\s+us|visitors?|students?|"
               r"parents?|adults?|kids?|guests?)\b"),
)


def _safe_date(year: int, month: int, day: int):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _find_visit_date(text: str, today: date):
    """Pull a date out of free text ('17th', 'next Monday', 'on 2026-11-20, my number is 98...')."""
    s = " " + str(text).lower() + " "
    for noise in _DATE_NOISE:
        s = noise.sub(" ", s)
    s = re.sub(r"[,;!?()]", " ", s)
    s = re.sub(r"\s+", " ", s)

    # 1. 2026-11-20 / 2026/11/20
    m = re.search(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", s)
    if m:
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d
    # 2. 20-11-2026 / 20/11/26 / 20 11 2026 (Indian day-first order)
    m = (re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2}|\d{2})(?!\d)", s)
         or re.search(r"(?<!\d)(\d{1,2}) (\d{1,2}) (20\d{2})(?!\d)", s))
    if m:
        year = int(m.group(3))
        d = _safe_date(year + 2000 if year < 100 else year, int(m.group(2)), int(m.group(1)))
        if d:
            return d
    # 3. 17 Nov / 17th of November 2026 / Nov 17 / November 17th, 2026
    m = re.search(rf"(?<!\d)(\d{{1,2}}){_ORD}?\s*(?:of\s+)?({_MONTH_RE})\b\.?(?:\s*(20\d{{2}}))?", s)
    day = month = year = None
    if m:
        day, month, year = int(m.group(1)), _MONTHS[m.group(2)], m.group(3)
    else:
        m = re.search(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}}){_ORD}?(?!\d)(?:\s*(20\d{{2}}))?", s)
        if m:
            day, month, year = int(m.group(2)), _MONTHS[m.group(1)], m.group(3)
    if day and month:
        if year:
            d = _safe_date(int(year), month, day)
        else:
            d = _safe_date(today.year, month, day)
            if d and d < today - timedelta(days=7):  # "5 Jan" said in November means next January
                d = _safe_date(today.year + 1, month, day)
        if d:
            return d
    # 4. today / tomorrow / day after tomorrow
    if re.search(r"\bday after (?:tomorrow|tmrw|tmr)\b|\boverm?orrow\b", s):
        return today + timedelta(days=2)
    if re.search(r"\b(?:tomorrow|tomorrows|tmrw|tmr|tomm?or+ow|repu)\b", s):
        return today + timedelta(days=1)
    if re.search(r"\b(?:today|todays|ee roju|aaj)\b", s):
        return today
    # 5. next Monday / this Friday / on sat
    short_ok = len(s.split()) <= 2
    m = re.search(r"\b(next|this|coming|on)?\s*\b(" + "|".join(_WEEKDAYS_FULL) + r")\b", s)
    wday = _WEEKDAYS_FULL[m.group(2)] if m else None
    if m is None:
        m = re.search(r"\b(next|this|coming|on)\s+(" + "|".join(_WEEKDAYS_SHORT) + r")\b", s)
        if m is None and short_ok:
            m = re.search(r"\b()(" + "|".join(_WEEKDAYS_SHORT) + r")\b", s)
        wday = _WEEKDAYS_SHORT[m.group(2)] if m else None
    if m:
        days_ahead = (wday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # "Monday" said on a Monday means next week
        elif m.group(1) == "next":
            days_ahead += 7
        return today + timedelta(days=days_ahead)
    # 6. "17th" anywhere, or a bare day number when that is all the student typed ("17", "on 17")
    m = (re.search(rf"(?<!\d)(\d{{1,2}}){_ORD}\b", s)
         or re.fullmatch(r"\s*(?:i\s+(?:want|would like)\s+to\s+(?:visit|come)\s+)?(?:on|for|at|date)?\s*"
                         r"(?:the\s+)?(\d{1,2})\s*\.?\s*", s))
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            if day >= today.day:
                d = _safe_date(today.year, today.month, day)
            else:
                d = _safe_date(today.year + (today.month == 12), today.month % 12 + 1, day)
            if d:
                return d
    return None


def resolve_campus_visit_date(date_str: str, today: date | None = None) -> dict:
    """Resolve and validate a campus visit date relative to today.

    Accepts a bare date ('17th', 'tomorrow', 'next Monday', 'Nov 17', '2026-11-17') or a whole
    sentence that contains one ('book a visit on 20 Nov, I am Ravi, 9876543210, 3 people').
    Phone numbers, times, marks and visitor counts are ignored. Visits run Monday to Saturday,
    from today up to 90 days ahead.
    """
    today = today or date.today()
    empty = {"date": None, "iso": None, "human": None, "is_valid": False, "is_sunday": False,
             "is_outside_window": False, "is_past": False, "is_ambiguous": True,
             "alternative_suggestions": []}
    if not date_str or not isinstance(date_str, str):
        return {**empty, "reason": "No date provided."}

    target_date = _find_visit_date(date_str, today)
    if not target_date:
        return {**empty, "reason": f"Could not determine a valid date from '{date_str[:60]}'. "
                                   "Please provide a date like 'tomorrow', '17th Nov', or 'YYYY-MM-DD'."}

    human_str = target_date.strftime("%B %d, %Y")
    max_date = today + timedelta(days=90)
    is_sunday = target_date.weekday() == 6
    is_past = target_date < today
    is_outside = is_past or target_date > max_date

    alt_suggestions = []
    if is_sunday:
        for alt in (target_date - timedelta(days=1), target_date + timedelta(days=1)):
            if alt >= today:
                alt_suggestions.append({"date": alt, "iso": alt.isoformat(),
                                        "human": alt.strftime("%A, %B %d, %Y")})

    reason = None
    if is_past:
        reason = (f"{human_str} has already passed. Campus visits can only be scheduled from today "
                  f"({today:%d %B %Y}) up to {max_date:%d %B %Y}.")
    elif is_sunday:
        reason = f"The campus is closed for visits on Sunday, {human_str}."
    elif is_outside:
        reason = (f"Campus visits can only be scheduled within the next 90 days "
                  f"(between {today:%d %B %Y} and {max_date:%d %B %Y}).")
    return {
        "date": target_date, "iso": target_date.isoformat(), "human": human_str,
        "is_valid": not is_sunday and not is_outside, "is_sunday": is_sunday,
        "is_outside_window": is_outside, "is_past": is_past, "is_ambiguous": False,
        "reason": reason, "alternative_suggestions": alt_suggestions,
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
    
    if res.get("is_past"):
        return {"status": "invalid", "problem": res["reason"]}

    if res.get("is_sunday"):
        alts = res.get("alternative_suggestions", [])
        alt_text = (" Would " + " or ".join(a["human"] for a in alts) + " work for you?") if alts else ""
        return {
            "status": "invalid",
            "problem": f"Campus visits are conducted Monday through Saturday (9:30 AM to 4:30 PM). SR University is closed for visits on Sunday, {res['human']}.{alt_text}"
        }

    if res.get("is_outside_window"):
        return {
            "status": "invalid",
            "problem": f"Campus visits can only be scheduled within the next 90 days. {res['human']} is outside this window. Please choose a date within 90 days or contact Admissions at {config.ADMISSIONS_PHONE}."
        }

    visit = res["date"]
    try:
        visitors = max(1, min(int(args.get("visitors") or 1), 10))
    except (TypeError, ValueError):
        visitors = 1
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
            "board": {"type": "string", "enum": ["state_board", "cbse"],
                      "description": "cbse also covers ICSE. Default state_board (Intermediate)."},
            "eapcet_rank": {"type": "integer", "description": "TG/AP EAPCET (EAMCET) rank."},
            "jee_percentile": {"type": "number", "description": "JEE Main percentile (0-100)."},
            "ib_score": {"type": "integer", "description": "IB Diploma score out of 45."},
            "transport": {"type": "boolean", "description": "true only if the student asked for the university bus."},
            "hostel": {"type": "string", "enum": ["none", "non_ac_4", "non_ac_3", "ac_4", "ac_3"], "description": "Pass ONLY if student explicitly requested hostel. Default is 'none'."},
            "specialization": {"type": "boolean", "description": "true for AI & ML, Data Science, Cyber Security tracks."},
        }, ["program"])}),

    "check_eligibility": (tool_check_eligibility, "Checking eligibility", {
        "description": "Checks if a student meets the minimum marks for a program. Call whenever marks "
                       "and a program are known and the student asks 'can I join'.",
        "parameters_json_schema": _obj({"program": _PROGRAM, "percent": _PERCENT}, ["program", "percent"])}),
    "get_program_info": (tool_get_program_info, "Looking up the course", {
        "description": "Eligibility, duration, yearly tuition and scholarship slabs of ONE course when the "
                       "student has NOT given marks, e.g. 'MBA eligibility', 'what is BBA fee', "
                       "'scholarship slabs for B.Tech'.",
        "parameters_json_schema": _obj({"program": _PROGRAM}, ["program"])}),
    "compare_programs": (tool_compare_programs, "Comparing the two courses", {
        "description": "Side-by-side cost of two courses for the same student (tuition, scholarship, "
                       "year 1 total, full course total). Use for 'CSE vs ECE fee', 'which is cheaper'.",
        "parameters_json_schema": _obj({
            "program_a": _PROGRAM, "program_b": _PROGRAM, "percent": _PERCENT,
            "board": {"type": "string", "enum": ["state_board", "cbse"]},
            "eapcet_rank": {"type": "integer"}, "jee_percentile": {"type": "number"}},
            ["program_a", "program_b"])}),
    "get_special_concessions": (tool_get_special_concessions, "Checking special concessions", {
        "description": "Official special fee concessions other than merit: sibling, girl child, single "
                       "parent, defence, sports, disability, staff children and others. Returns the "
                       "matching categories and the full official list.",
        "parameters_json_schema": _obj({"category": {
            "type": "string", "description": "What the student asked about, e.g. 'state level sports', 'sibling'."}})}),
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
            "eapcet_rank": {"type": "integer"}, "jee_percentile": {"type": "number"},
            "ib_score": {"type": "integer"}, "city": {"type": "string"},
            "is_parent": {"type": "boolean"},
            "language": {"type": "string", "description": "english, telugu, hindi or tenglish"}})}),
    "request_counsellor_callback": (tool_request_counsellor_callback, "Arranging a callback", {
        "description": "Saves a request for the admissions team to phone the student. Needs name and a "
                       "10-digit mobile number. A student who ASKED for a call has agreed to be contacted "
                       "(consent=true). Call it as soon as you have name and number; never just 'note' them.",
        "parameters_json_schema": _obj({
            "name": {"type": "string"}, "phone": _PHONE, "program_interest": {"type": "string"},
            "preferred_time": {"type": "string", "description": "e.g. 'tomorrow evening'"},
            "consent": _CONSENT}, ["name", "phone", "consent"])}),
    "book_campus_visit": (tool_book_campus_visit, "Requesting your campus visit", {
        "description": "Sends a campus visit request to the admissions team. Needs name, phone and date. "
                       "A student who asked to book a visit has agreed to be contacted about it (consent=true).",
        "parameters_json_schema": _obj({
            "name": {"type": "string"}, "phone": _PHONE,
            "visit_date": {"type": "string", "description": "Preferred date e.g. 'YYYY-MM-DD', 'tomorrow', '17th Nov', or day number like '17th' (relative to current date)"},
            "visitors": {"type": "integer"}, "consent": _CONSENT},
            ["name", "phone", "visit_date", "consent"])}),
    "cancel_contact_request": (tool_cancel_contact_request, "Cancelling your request", {
        "description": "Withdraws the callback or campus visit request saved from this chat. Call it when "
                       "the student says 'don't call me', 'cancel the callback', 'cancel my visit'. "
                       "Only say it is cancelled if this tool returns status 'cancelled'.",
        "parameters_json_schema": _obj({"reason": {"type": "string"}})}),
    "share_fee_estimate": (tool_share_fee_estimate, "Preparing a shareable estimate", {
        "description": "Builds a WhatsApp link carrying the fee estimate just calculated, so the student "
                       "can send it to their parents. Use when they say 'send this to my father', "
                       "'share on WhatsApp', or after a fee answer if they want to keep it.",
        "parameters_json_schema": _obj({})}),
    "get_contact_and_apply_links": (tool_get_contact_and_apply_links, "Getting contact details", {
        "description": "Official apply link, admissions phone, email and WhatsApp link. Use for 'how to "
                       "apply', 'contact number', or when you cannot answer something.",
        "parameters_json_schema": _obj({"topic": {"type": "string"}})}),
    "get_university_videos": (tool_get_university_videos, "Finding official university videos", {
        "description": "Finds official SR University YouTube videos and tours for campus life, hostels, "
                       "placements, labs, sports, student clubs, and infrastructure. Call whenever the student "
                       "asks to see, watch, or get videos/tours of SR University.",
        "parameters_json_schema": _obj({"topic": {"type": "string", "description": "e.g. 'campus', 'hostel life', 'placements', 'infrastructure'"}})}),
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
