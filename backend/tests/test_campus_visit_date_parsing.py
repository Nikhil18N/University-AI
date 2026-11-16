"""Tests for flexible campus visit date parsing, booking tool, and card triggers."""
from datetime import date, timedelta
import pytest

from app.sru_agent import tools
from app.sru_agent.tools import parse_flexible_visit_date
from app.services.card_service import generate_cards, CAMPUS_VISIT_FORM_CARD, CAMPUS_TOUR_CARD


def test_parse_flexible_visit_date_relative_tokens():
    mock_today = date(2026, 11, 16)
    assert parse_flexible_visit_date("today", today=mock_today) == date(2026, 11, 16)
    assert parse_flexible_visit_date("tomorrow", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("day after tomorrow", today=mock_today) == date(2026, 11, 18)


def test_parse_flexible_visit_date_ordinals_and_day_numbers():
    mock_today = date(2026, 11, 16)
    # 17th on Nov 16th -> Nov 17th, 2026
    assert parse_flexible_visit_date("17th", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("17", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("visit on 17th", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("for 18th", today=mock_today) == date(2026, 11, 18)
    # 5th on Nov 16th is past day in Nov -> resolves to Dec 5th, 2026
    assert parse_flexible_visit_date("5th", today=mock_today) == date(2026, 12, 5)


def test_parse_flexible_visit_date_month_and_day():
    mock_today = date(2026, 11, 16)
    assert parse_flexible_visit_date("17 Nov", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("17th November", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("November 17", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("Nov 17", today=mock_today) == date(2026, 11, 17)


def test_parse_flexible_visit_date_explicit_formats():
    mock_today = date(2026, 11, 16)
    assert parse_flexible_visit_date("2026-11-17", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("17-11-2026", today=mock_today) == date(2026, 11, 17)
    assert parse_flexible_visit_date("17/11/2026", today=mock_today) == date(2026, 11, 17)


def test_parse_flexible_visit_date_invalid_gibberish():
    mock_today = date(2026, 11, 16)
    assert parse_flexible_visit_date("whenever", today=mock_today) is None
    assert parse_flexible_visit_date("", today=mock_today) is None
    assert parse_flexible_visit_date(None, today=mock_today) is None


@pytest.mark.asyncio
async def test_tool_book_campus_visit_with_relative_date():
    saved = []
    async def mock_saver(lead):
        saved.append(lead)
        return {"id": "visit-ref-12345", "name": lead["name"]}

    tools.set_lead_saver(mock_saver)
    try:
        # Today is date.today() (e.g. 2026-11-16)
        # Passing "tomorrow"
        r = await tools.run_tool(
            "book_campus_visit",
            {"name": "Chitikeshi Mahesh", "phone": "7013295712", "visit_date": "tomorrow", "consent": True},
            {"session_id": "s-visit", "profile": {}}
        )
        assert r["status"] == "saved"
        assert r["reference"] == "visit-re"
        assert len(saved) == 1
        expected_date = (date.today() + timedelta(days=1)).isoformat()
        assert saved[0]["metadata"]["visit_date"] == expected_date
        assert saved[0]["name"] == "Chitikeshi Mahesh"
        assert saved[0]["phone"] == "7013295712"
    finally:
        tools.set_lead_saver(None)


@pytest.mark.asyncio
async def test_tool_book_campus_visit_outside_window_rejected():
    # 2027-05-17 is > 90 days from Nov 2026
    r = await tools.run_tool(
        "book_campus_visit",
        {"name": "Chitikeshi Mahesh", "phone": "7013295712", "visit_date": "2027-05-17", "consent": True},
        {"session_id": "s-visit", "profile": {}}
    )
    assert r["status"] == "invalid"
    assert "Campus visits can only be scheduled" in r["problem"]


def test_campus_visit_booking_card_trigger():
    """Verify that user asking how to book a campus tour triggers the interactive CAMPUS_VISIT_FORM_CARD."""
    cards = generate_cards(
        user_message="I want to visit the SR University campus. How can I book a campus tour?",
        answer="You are welcome to visit our 170-acre campus in Warangal.",
    )
    assert any(c.get("type") == "campus_visit_form" for c in cards)
    visit_card = next(c for c in cards if c.get("type") == "campus_visit_form")
    assert visit_card == CAMPUS_VISIT_FORM_CARD
    assert "Warangal" in visit_card["location"]
    # Static tour card should be suppressed in favor of interactive booking card
    assert not any(c.get("type") == "campus_tour" for c in cards)


def test_about_campus_general_still_shows_tour_card():
    """Verify general 'tell me about sru and the campus' still shows CAMPUS_TOUR_CARD."""
    cards = generate_cards(
        user_message="tell me about sru and the campus",
        answer="SR University is a next-generation living and learning campus in Warangal.",
    )
    assert any(c.get("type") == "campus_tour" for c in cards)
    assert not any(c.get("type") == "campus_visit_form" for c in cards)
