"""Tests for lead cancellation, counsellor callback consent, and fee card deduplication."""

import pytest
from app.sru_agent import tools, prompt, fees
from app.services.card_service import (
    generate_cards,
    BTECH_CSE_SEMESTER_FEE_CARD,
    BTECH_CSE_WITH_HOSTEL_FEE_CARD,
    BTECH_ACADEMIC_FEE_CARD,
)


@pytest.mark.asyncio
async def test_lead_saved_stores_last_lead_id_and_cancel():
    """Verify that saving a lead sets last_lead_id, and cancelling it resets it."""
    saved_lead = None

    async def mock_saver(lead_data: dict):
        nonlocal saved_lead
        saved_lead = lead_data
        return {"id": "test-uuid-1234", "status": "new"}

    cancelled_ids = []

    async def mock_canceller(lead_id: str):
        cancelled_ids.append(lead_id)
        return True

    tools.set_lead_saver(mock_saver)
    tools.set_lead_canceller(mock_canceller)

    ctx = {"session_id": "test_session_canceller", "profile": {}}

    # 1. Save callback
    res = await tools.run_tool(
        "request_counsellor_callback",
        {"name": "Test QA", "phone": "9000000002", "consent": True},
        ctx,
    )
    assert res.get("status") == "saved"
    assert ctx["profile"].get("last_lead_id") == "test-uuid-1234"

    # 2. Cancel contact request
    cancel_res = await tools.run_tool("cancel_contact_request", {}, ctx)
    assert cancel_res.get("status") == "cancelled"
    assert "test-uuid-1234" in cancelled_ids
    assert ctx["profile"].get("last_lead_id") is None

    # 3. Second cancel attempt returns nothing_to_cancel
    cancel_res_2 = await tools.run_tool("cancel_contact_request", {}, ctx)
    assert cancel_res_2.get("status") == "nothing_to_cancel"


@pytest.mark.asyncio
async def test_cancel_contact_request_failure():
    """When canceller returns False, status is not_cancelled."""
    async def mock_failing_canceller(lead_id: str):
        return False

    tools.set_lead_canceller(mock_failing_canceller)
    ctx = {"session_id": "test_session_fail", "profile": {"last_lead_id": "existing-uuid"}}

    res = await tools.run_tool("cancel_contact_request", {}, ctx)
    assert res.get("status") == "not_cancelled"
    # last_lead_id remains in profile if cancellation failed
    assert ctx["profile"].get("last_lead_id") == "existing-uuid"


def test_cancel_contact_request_registered():
    """Verify cancel_contact_request is registered in TOOLS and ACTION_TOOLS."""
    assert "cancel_contact_request" in tools.TOOLS
    assert "cancel_contact_request" in tools.ACTION_TOOLS


def test_prompt_excludes_last_lead_id():
    """Verify that last_lead_id is never exposed to the model in build_system_prompt."""
    profile = {
        "name": "Test QA",
        "phone_saved": "9000000002",
        "last_lead_id": "secret-lead-uuid-9999",
        "percent": 88.0,
    }
    rendered = prompt.build_system_prompt(profile=profile)
    assert "secret-lead-uuid-9999" not in rendered
    assert "last_lead_id" not in rendered
    assert "Test QA" in rendered
    assert "cancel_contact_request" in rendered


def test_prompt_contains_cancellation_and_callback_rules():
    """Verify that instructions for cancellation and callback consent are in the prompt."""
    rendered = prompt.build_system_prompt(profile={})
    assert "cancel_contact_request" in rendered
    assert "nothing_to_cancel" in rendered
    assert "ALREADY agreed to be contacted" in rendered
    assert "Never claim you saved, booked, or cancelled anything unless" in rendered


def test_card_service_suppresses_legacy_fee_when_calculate_fee_present():
    """Verify generate_cards does NOT attach duplicate fee cards if has_calculate_fee=True."""
    cards_with_flag = generate_cards(
        user_message="what is the fee for btech cse with hostel?",
        answer="The first year fee is ₹3,40,000...",
        has_calculate_fee=True,
    )
    # None of the legacy fee breakdown cards should be attached
    for c in cards_with_flag:
        assert c.get("type") != "fee_breakdown"

    cards_without_flag = generate_cards(
        user_message="what is the fee for btech cse with hostel?",
        answer="The first year fee is ₹3,40,000...",
        has_calculate_fee=False,
    )
    # Without the flag, BTECH_CSE_WITH_HOSTEL_FEE_CARD is attached
    assert any(c.get("type") == "fee_breakdown" for c in cards_without_flag)


def test_legacy_fee_cards_titles_and_notes():
    """Verify legacy fee card titles and notes have no 40% calculation without marks."""
    assert "Fees before scholarship — B.Tech CSE (2027-28)" in BTECH_CSE_SEMESTER_FEE_CARD["title"]
    assert "Fees before scholarship — B.Tech CSE with Hostel (2027-28)" in BTECH_CSE_WITH_HOSTEL_FEE_CARD["title"]
    assert "Fees before scholarship — B.Tech Programs (2027-28)" in BTECH_ACADEMIC_FEE_CARD["title"]

    # Ensure no misleading net fee calculation like ₹1,02,000 is present in the notes
    assert "₹1,02,000" not in BTECH_CSE_SEMESTER_FEE_CARD["scholarship_note"]
    assert "₹1,02,000" not in BTECH_CSE_WITH_HOSTEL_FEE_CARD["scholarship_note"]
    assert "up to 40%" in BTECH_CSE_SEMESTER_FEE_CARD["scholarship_note"]

    # Verify stale items are completely removed from BTECH_ACADEMIC_FEE_CARD
    categories = [item["category"] for item in BTECH_ACADEMIC_FEE_CARD["items"]]
    assert not any("AI & Robotics" in c for c in categories)
    assert not any("Biotech" in c for c in categories)
    assert not any("Other & Exam" in c for c in categories)
    assert not any("Specialization" in c for c in categories)


def test_btech_fee_query_attaches_cse_semester_card_not_academic_table():
    """Verify general 'what is the fee for btech' query attaches BTECH_CSE_SEMESTER_FEE_CARD, not multi-branch table."""
    from app.services.card_service import generate_cards, BTECH_CSE_SEMESTER_FEE_CARD
    cards = generate_cards(
        user_message="What is the fee for btech?",
        answer="The tuition fee for B.Tech CSE is ₹1,70,000 per semester.",
    )
    assert len(cards) >= 1
    assert cards[0] == BTECH_CSE_SEMESTER_FEE_CARD
