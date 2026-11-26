"""Unified coordinator over fee_intake, fee_journey, and fee_flow state."""
from __future__ import annotations

import re

from . import fee_intake, fee_journey, fees, intents, memory

_FEE_STEP_OPENER = re.compile(r"^(?:Sure!?\s*|Certainly!?\s*)", re.I)
_OTHER_FEE_RE = re.compile(
    r"\b(?:other\s+fees?|other\s+academic(?:\s*/\s*university|\s+university)?\s+charges?|other\s+charges?|annual\s+charges?|"
    r"university\s+charges?|additional\s+fees?|additional\s+charges?|enrolment\s+fee|enrollment\s+fee|application\s+form\s+fee|"
    r"specialisation\s+fee|specialization\s+fee|phd\s+fee|"
    r"fees?\s+(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee)|"
    r"(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee))\b",
    re.I,
)
_SCHOLARSHIP_CALC_RE = re.compile(
    r"\b(?:(?:schol\w*|s[ck]?h?o[lr]+[ae]?r?s+h?i*p+\w*)|waiver|concession|discount|fee\s+assessment|scholarship\s+assessment|assessment\s+form|"
    r"calculate\s+(?:[\w\s]+\s+)?(?:fee|tuition|scholarship)|fee\s+calculation|my\s+fee|expected\s+scholarship|"
    r"scholarship\s+counsell?or|fee\s+counsell?or)\b",
    re.I,
)
_GENERAL_SCHOLARSHIP_RE = re.compile(
    r"\b(?:what\s+(?:are\s+the\s+)?scholarships|which\s+scholarships|scholarships\s+available|"
    r"are\s+there\s+scholarships|any\s+scholarships|do\s+you\s+(?:have|offer|provide)\s+scholarships|"
    r"scholarship\s+options|list\s+of\s+scholarships|details\s+about\s+scholarships)\b",
    re.I,
)
_BARE_SCORE_RE = re.compile(
    r"^\s*(?:i\s+(?:got|scored|have|secured|obtained)\s+)?\d{2,4}(?:\.\d+)?\s*(?:marks?|%|percent)?\s*$",
    re.I,
)


def intake_open(conv_state: dict | None, message: str) -> bool:
    """True when fee_intake is waiting on the student, or re-opens on new academic details."""
    waiting = ((conv_state or {}).get("fee_intake") or {}).get("waiting_for")
    if not waiting:
        return False
    if waiting != "done":
        return True
    return bool(set(fee_intake.parse_details(message)) & set(fee_intake._ACADEMIC_FIELDS))


def classify_fee_turn(message: str, intent: str, is_multi_q: bool) -> dict[str, bool]:
    """Classify fee/scholarship/guard flags once for structured flow coordination."""
    low_msg = (message or "").lower()
    is_other_fee = bool(_OTHER_FEE_RE.search(low_msg))
    is_general_schol = bool(_GENERAL_SCHOLARSHIP_RE.search(low_msg))
    is_schol_calc = (not is_other_fee) and bool(_SCHOLARSHIP_CALC_RE.search(low_msg))
    if is_multi_q or is_general_schol:
        is_schol_calc = False
    is_bare_score = bool(_BARE_SCORE_RE.match(low_msg)) or bool(re.fullmatch(r"\s*\d{2,4}(?:\.\d+)?\s*%?\s*", low_msg))
    is_branch_guidance = (intent == "BRANCH_GUIDANCE_QUERY") or intents.is_branch_guidance_query(message)
    is_seat_guarantee = (intent == "ADMISSION_GUARANTEE_QUERY") or bool(intents._ADMISSION_GUARANTEE_PATTERN.search(message))
    is_future_year = (intent == "FUTURE_YEAR_FEE_QUERY") or bool(intents._FUTURE_YEAR_FEE_PATTERN.search(message))
    if is_seat_guarantee or is_future_year:
        is_schol_calc = False
    return {
        "is_other_fee_inquiry": is_other_fee,
        "is_scholarship_calc_q": is_schol_calc,
        "is_bare_score_msg": is_bare_score,
        "is_branch_guidance": is_branch_guidance,
        "is_seat_guarantee": is_seat_guarantee,
        "is_future_year": is_future_year,
    }


async def sync_intake_updates(
    state_dict: dict,
    session_id: str,
    profile: dict,
    ctx: dict,
    set_state,
) -> dict:
    """Persist fee_intake state and sync collected academic/programme fields into student profile."""
    await set_state(fee_intake=state_dict)
    prof_updates = {}
    for k in (
        "program", "board", "board_label", "board_key", "academic_stage", "stage_label",
        "raw_marks", "max_marks", "percent", "admission_route", "route_label",
        "eapcet_rank", "jee_percentile", "stream", "ib_score",
    ):
        val = state_dict.get(k)
        if val is not None:
            if k == "program":
                prof_updates["program_interest"] = val
                await set_state(active_program=val, fee_flow_prog=val)
            else:
                prof_updates[k] = val
    if prof_updates:
        profile = await memory.update_profile(session_id, **prof_updates)
        ctx["profile"] = profile
    return profile


def is_active_fee_step(conv_state: dict | None) -> bool:
    """Return True if either fee_intake or fee_journey has an unfinished interactive step."""
    st = conv_state or {}
    intake = st.get("fee_intake") or {}
    if intake.get("counsellor_mode") and intake.get("waiting_for") not in (None, "done"):
        return True
    ev = st.get(fee_journey.KEY) or {}
    return bool(ev.get("active") and not ev.get("final_shown"))


def active_fee_program(conv_state: dict | None, profile: dict | None = None) -> str | None:
    """Resolve the active programme key across fee_journey, fee_intake, conv_state, and profile."""
    st = conv_state or {}
    pr = profile or {}
    ev = st.get(fee_journey.KEY) or {}
    intake = st.get("fee_intake") or {}
    for candidate in (
        ev.get("program"),
        intake.get("program"),
        st.get("active_program"),
        pr.get("program_interest"),
    ):
        if candidate:
            found = fees.find_program(str(candidate))
            if found:
                return found
    return None


def open_step(profile: dict, conv_state: dict) -> dict | None:
    """Return the active fee step question (text, cards, chips) so a greeting/interruption can resume it."""
    intake = conv_state.get("fee_intake") or {}
    if intake.get("counsellor_mode") and intake.get("waiting_for") not in (None, "done"):
        try:
            r = fee_intake.decide("Calculate my scholarship", profile, dict(intake))
        except Exception:
            r = None
        if r and r.get("action") == "ask":
            return {
                "text": _FEE_STEP_OPENER.sub("", r.get("text") or "").strip(),
                "cards": r.get("cards") or [],
                "chips": r.get("chips") or [],
            }
    st = conv_state.get(fee_journey.KEY)
    if st and st.get("active") and st.get("awaiting") not in (None, "scholarship_steps"):
        try:
            r = fee_journey.next_step(dict(st), profile)
        except Exception:
            r = None
        if r and r.get("kind") == "reply" and r.get("text"):
            return {
                "text": r["text"],
                "cards": r.get("cards") or [],
                "chips": r.get("chips") or [],
                "fee_state": r.get("state"),
            }
    return None
