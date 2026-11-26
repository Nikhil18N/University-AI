"""Structured deterministic flow orchestration extracted from agent.py."""
from __future__ import annotations

from typing import Any, Callable

from . import compound, fee_coordinator, fee_flow, fee_intake, fees, memory, tools


async def resolve_compound_plan(
    compound_plan: list[tuple[str, str]],
    message: str,
    session_id: str,
    conversation_id: str | None,
    *,
    resolve_sub_query: Callable[[str, str, str], Any],
    with_resume_chip: Callable[[str, str | None, list], Any],
) -> dict | None:
    """Resolve a deterministic compound multi-question plan into combined text, cards, and chips."""
    resolved_parts: list[str] = []
    combined_cards: list = []
    combined_chips: list = []
    seen_card_types: set[str] = set()

    for sq, sq_topic in compound_plan:
        part_text, part_cards, part_chips = await resolve_sub_query(sq, sq_topic, session_id)
        if part_text:
            resolved_parts.append(part_text.strip())
        for c in part_cards:
            ctype = c.get("type") if isinstance(c, dict) else str(c)
            if ctype not in seen_card_types:
                seen_card_types.add(ctype)
                combined_cards.append(c)
        for chip in part_chips:
            if chip not in combined_chips:
                combined_chips.append(chip)

    if resolved_parts and compound.from_other_state(message):
        conc = next((c for c in fees.load_data().get("special_concessions", []) if c["key"] == "non_local"), None)
        if conc:
            resolved_parts.append(
                f"Coming from outside Telangana and Andhra Pradesh? The 2027-28 fee circular has a special concession "
                f"of **{fees.inr(int(conc['amount']))} a year** for students from outside Telangana and AP, applied after the "
                "Admissions Office verifies your proof."
            )

    if not resolved_parts:
        return None

    chips = await with_resume_chip(session_id, conversation_id, combined_chips[:4])
    return {
        "text": "\n\n---\n\n".join(resolved_parts),
        "cards": combined_cards,
        "suggestions": chips,
    }


async def run_fee_or_explore_turn(
    *,
    message: str,
    intent: str,
    is_multi_q: bool,
    side_q: bool,
    natural_name: str,
    session_id: str,
    conv_state: dict,
    profile: dict,
    ctx: dict,
    client: Any,
    set_state: Callable,
    is_mock_client: Callable[[Any], bool],
    format_counsellor_assessment: Callable[[dict, dict], str],
) -> dict:
    """Coordinate fee_intake and fee_flow steps cleanly outside agent.py.

    Returns a dict with:
      - ``outcome``: ``"none"`` | ``"say"`` | ``"counsellor"``
      - ``intake_decision``: latest fee_intake decision (or None)
      - ``is_other_fee_inquiry``: bool
      - ``profile``: possibly updated profile dict
      - plus payload fields when ``outcome != "none"``.
    """
    intake_state = dict(conv_state.get("fee_intake") or {})
    if not intake_state.get("program"):
        candidate_p = (
            conv_state.get("fee_flow_prog")
            or conv_state.get("active_program")
            or (profile.get("program_interest") if profile else None)
        )
        if candidate_p:
            intake_state["program"] = candidate_p
    flags = fee_coordinator.classify_fee_turn(message, intent, is_multi_q)
    is_other_fee = flags["is_other_fee_inquiry"]
    is_schol_calc = flags["is_scholarship_calc_q"]
    is_bare_score = flags["is_bare_score_msg"]
    is_branch_guidance = flags["is_branch_guidance"]
    is_seat_guarantee = flags["is_seat_guarantee"]
    is_future_year = flags["is_future_year"]

    if is_other_fee and conv_state.get("fee_intake"):
        await set_state(fee_intake=None)
        intake_state = {}
    if (is_seat_guarantee or is_future_year) and conv_state.get("fee_intake"):
        await set_state(fee_intake=None)
        intake_state = {}

    intake_in_progress = fee_coordinator.intake_open(conv_state, message) and not is_multi_q and not side_q
    guard_ok = not is_other_fee and not is_branch_guidance and not is_seat_guarantee and not is_future_year
    intake_decision = None

    async def _handle_intake_decision(dec: dict) -> dict | None:
        nonlocal profile
        action = dec.get("action")
        if action == "ineligible":
            await set_state(fee_intake={k: v for k, v in dec["state"].items()
                                        if k in ("program", "ineligible", "counsellor_mode")})
            kept = {
                k: dec["state"].get(k)
                for k in ("percent", "raw_marks", "max_marks", "board", "board_key", "board_label", "academic_stage")
                if dec["state"].get(k) not in (None, "")
            }
            if kept.get("percent") is not None:
                profile = await memory.update_profile(session_id, **kept)
                ctx["profile"] = profile
            return {
                "outcome": "say",
                "text": dec["text"],
                "cards": [],
                "suggestions": dec.get("chips", []),
                "eligible": False,
                "exact_chips": True,
                "intake_decision": dec,
                "is_other_fee_inquiry": is_other_fee,
                "profile": profile,
            }
        if action == "ask":
            if dec.get("profile_clear"):
                profile = await memory.remove_profile_keys(session_id, *dec["profile_clear"])
                ctx["profile"] = profile
            profile = await fee_coordinator.sync_intake_updates(dec["state"], session_id, profile, ctx, set_state)
            return {
                "outcome": "say",
                "text": dec["text"],
                "cards": dec.get("cards", []),
                "suggestions": dec["chips"],
                "exact_chips": True,
                "intake_decision": dec,
                "is_other_fee_inquiry": is_other_fee,
                "profile": profile,
            }
        if action == "calculate" and dec.get("counsellor") and not is_mock_client(client):
            profile = await fee_coordinator.sync_intake_updates(dec["state"], session_id, profile, ctx, set_state)
            fee_args = dict(dec["args"])
            fee_result = await tools.run_tool("calculate_fee", fee_args, ctx)
            if fee_result.get("status") == "ok":
                c_det = dec.get("counsellor_details", {})
                c_text = format_counsellor_assessment(fee_result, c_det)
                if c_det.get("uses_entrance") and not c_det.get("has_entrance_score"):
                    chips = ["Add my EAPCET rank", "Add my JEE Main percentile", "Hostel fee details", "How do I apply?"]
                else:
                    chips = ["Hostel fee details", "How do I apply?", "Talk to an admission counsellor", "Campus visit"]
                return {
                    "outcome": "counsellor",
                    "fee_result": fee_result,
                    "c_det": c_det,
                    "c_text": c_text,
                    "chips": chips,
                    "intake_decision": dec,
                    "is_other_fee_inquiry": is_other_fee,
                    "profile": profile,
                }
        return None

    # 1. Active or explicit scholarship/fee intake
    if guard_ok and (intake_in_progress or is_schol_calc or (is_bare_score and client is None)):
        intake_decision = fee_intake.decide(message, profile, intake_state, first_name=natural_name)
        if intake_decision:
            res = await _handle_intake_decision(intake_decision)
            if res is not None:
                return res

    # 2. Exploratory school & course browsing flow
    low_msg = (message or "").lower()
    in_selection_flow = conv_state.get("fee_flow_state") in ("awaiting_school_selection", "awaiting_course_selection")
    wants_course_explore = any(
        k in low_msg
        for k in ("explore programs", "explore schools", "browse courses", "browse schools",
                  "change school", "different course", "change programme")
    )
    if not is_branch_guidance and (in_selection_flow or wants_course_explore or is_mock_client(client)):
        flow_result = fee_flow.process_fee_flow(message, session_id, profile, conv_state)
        if flow_result is not None:
            await set_state(**flow_result["new_state"])
            return {
                "outcome": "say",
                "text": flow_result["text"],
                "cards": flow_result.get("cards", []),
                "suggestions": flow_result.get("suggestions", []),
                "exact_chips": False,
                "intake_decision": intake_decision,
                "is_other_fee_inquiry": is_other_fee,
                "profile": profile,
            }

    # 3. Fallback check for fee intake if not yet evaluated
    if guard_ok and (is_schol_calc or intake_in_progress):
        if not intake_decision:
            intake_decision = fee_intake.decide(message, profile, intake_state, first_name=natural_name)
        if intake_decision:
            res = await _handle_intake_decision(intake_decision)
            if res is not None:
                return res

    if intake_decision and not intake_decision.get("counsellor"):
        await set_state(fee_intake=None)

    return {
        "outcome": "none",
        "intake_decision": intake_decision,
        "is_other_fee_inquiry": is_other_fee,
        "profile": profile,
    }
