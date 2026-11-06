"""Tests for strict single-category fee scoping across cards and suggestions."""

import pytest
from app.services.card_service import (
    generate_cards,
    TRANSPORT_FEE_CARD,
    HOSTEL_FEE_CARD,
    EXAM_FEE_CARD,
    ADMISSION_FEE_CARD,
    FEE_BREAKDOWN_CARD,
)
from app.services.suggestion_service import (
    generate_suggestions,
    TRANSPORT_SUGGESTIONS,
    BTECH_FEE_SUGGESTIONS,
    GENERAL_FEE_SUGGESTIONS,
)


def test_transport_fee_scoping():
    """Verify that asking for transport fee returns only transport card and suggestions."""
    cards = generate_cards(
        user_message="what is the transport fee?",
        answer="The transport fee for tri-cities bus routes (Warangal, Hanamkonda, Kazipet) is ₹22,000 – ₹30,000 per year.",
    )
    assert len(cards) == 1
    assert cards[0] == TRANSPORT_FEE_CARD
    # Ensure no tuition or hostel items exist in the card
    categories = [item["category"] for item in cards[0]["items"]]
    assert any("Tri-Cities" in c for c in categories)
    assert not any("CSE" in c for c in categories)
    assert not any("Hostel" in c for c in categories)

    suggestions = generate_suggestions(
        intent="FEES_AND_SCHOLARSHIPS",
        user_message="what is the transport fee?",
        answer="Transport fee is ₹22,000 – ₹30,000 per year.",
    )
    assert suggestions == TRANSPORT_SUGGESTIONS


def test_bus_fee_query_scoping():
    """Verify that asking for bus fee returns only transport card."""
    cards = generate_cards(
        user_message="how much is bus fees?",
        answer="Bus fees range from ₹22,000 to ₹30,000 annually.",
    )
    assert len(cards) == 1
    assert cards[0]["title"] == TRANSPORT_FEE_CARD["title"]


def test_hostel_fee_scoping():
    """Verify that asking for hostel fee returns only hostel card and hostel suggestions."""
    cards = generate_cards(
        user_message="what is hostel fee?",
        answer="Girls AC hostel is ₹1,25,000 (4-sharing) and ₹1,35,000 (3-sharing). Boys hostel is ₹85,000–₹95,000 (Non-AC).",
    )
    assert len(cards) == 1
    assert cards[0] == HOSTEL_FEE_CARD
    # Ensure no transport or tuition items exist in the card
    categories = [item["category"] for item in cards[0]["items"]]
    assert any("Girls Hostel" in c for c in categories)
    assert any("Boys Hostel" in c for c in categories)
    assert not any("Transport" in c for c in categories)
    assert not any("CSE" in c for c in categories)

    suggestions = generate_suggestions(
        intent="FEES_AND_SCHOLARSHIPS",
        user_message="what is hostel fee?",
        answer="Hostel fee is ₹1,25,000 per year.",
    )
    assert any("Girls AC Hostel Fee" in s for s in suggestions)
    assert not any("B.Tech CSE Fees" in s for s in suggestions)


def test_exam_fee_scoping():
    """Verify that asking for exam fee returns only exam fee card."""
    cards = generate_cards(
        user_message="what is exam fee?",
        answer="The annual exam fee is ₹5,000.",
    )
    assert len(cards) == 1
    assert cards[0] == EXAM_FEE_CARD
    assert "Examination Fee" in cards[0]["items"][0]["category"]


def test_admission_fee_scoping():
    """Verify that asking for admission fee / enrollment fee returns only admission fee card."""
    cards = generate_cards(
        user_message="how much is one-time admission fee?",
        answer="One-time fees are ₹5,000 enrollment + ₹25,000 admission fee = ₹30,000 in Year 1.",
    )
    assert len(cards) == 1
    assert cards[0] == ADMISSION_FEE_CARD
    assert any("Enrollment" in i["category"] for i in cards[0]["items"])
    assert any("Admission" in i["category"] for i in cards[0]["items"])


def test_btech_cse_fee_query_shows_tuition_breakdown():
    """Verify general B.Tech CSE fee query returns comprehensive tuition breakdown."""
    cards = generate_cards(
        user_message="What is the fee for btech cse?",
        answer="The tuition fee is ₹1,47,500 per semester (₹2,95,000 per year).",
    )
    fee_cards = [c for c in cards if c["type"] == "fee_breakdown"]
    assert len(fee_cards) >= 1
    assert fee_cards[0] == FEE_BREAKDOWN_CARD
