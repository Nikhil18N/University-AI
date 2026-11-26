"""Unified coordinator over fee_intake, fee_journey, and fee_flow state."""
from __future__ import annotations

import re

from . import fee_intake, fee_journey, fees

_FEE_STEP_OPENER = re.compile(r"^(?:Sure!?\s*|Certainly!?\s*)", re.I)


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
