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
    assert not any("B.Tech CSE" in s for s in suggestions)


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


def test_btech_cse_fee_query_shows_cse_only():
    """Verify B.Tech CSE fee query returns CSE tuition, without hostel or other branches."""
    from app.services.card_service import BTECH_CSE_FEE_CARD
    cards = generate_cards(
        user_message="What is the fee for btech cse?",
        answer="The tuition fee is ₹3,40,000 per year (₹1,70,000 per semester).",
    )
    assert len(cards) == 1
    assert cards[0] == BTECH_CSE_FEE_CARD
    categories = [item["category"] for item in cards[0]["items"]]
    assert any("CSE" in c for c in categories)
    assert not any("ECE" in c for c in categories)
    assert not any("Hostel" in c for c in categories)
    assert not any("Transport" in c for c in categories)


def test_btech_complete_fee_structure_shows_pure_academic_fees():
    """Verify general B.Tech fee query returns all engineering branch tuitions, strictly NO hostel or transport."""
    from app.services.card_service import BTECH_ACADEMIC_FEE_CARD
    cards = generate_cards(
        user_message="What is the complete fee structure and merit scholarship details for B.Tech?",
        answer="B.Tech tuition fees vary by branch: CSE is ₹3,40,000/yr, ECE is ₹2,70,000/yr, and Core is ₹2,00,000/yr.",
    )
    assert len(cards) == 1
    assert cards[0] == BTECH_ACADEMIC_FEE_CARD
    categories = [item["category"] for item in cards[0]["items"]]
    assert any("CSE" in c for c in categories)
    assert any("ECE" in c for c in categories)
    assert any("Core" in c for c in categories)
    assert any("Admission" in c for c in categories)
    # Strictly zero cross-contamination
    assert not any("Hostel" in c for c in categories)
    assert not any("Transport" in c for c in categories)
    assert not any("Bus" in c for c in categories)


def test_merit_scholarship_slabs_card():
    """Verify asking for merit scholarship details returns dedicated scholarship slab card."""
    from app.services.card_service import MERIT_SCHOLARSHIP_CARD
    cards = generate_cards(
        user_message="what are the merit scholarship details?",
        answer="Merit scholarships offer 10% to 50% tuition reduction based on your board or entrance scores.",
    )
    assert len(cards) == 1
    assert cards[0] == MERIT_SCHOLARSHIP_CARD
    categories = [item["category"] for item in cards[0]["items"]]
    assert any("40% Tuition Waiver" in c for c in categories)
    assert any("30% Tuition Waiver" in c for c in categories)
    assert not any("Hostel" in c for c in categories)
    assert not any("Transport" in c for c in categories)


def test_vague_fee_query_returns_no_card():
    """Verify that a bare ambiguous fee question does not dump cards, allowing assistant to ask."""
    cards = generate_cards(
        user_message="what is the fee?",
        answer="Fees depend on the program or facility. Which fee would you like to know about?",
    )
    # Should not attach an unprompted all-in-one card
    assert len(cards) == 0


def test_placement_excellence_card_generation():
    """Verify placement questions generate PLACEMENT_EXCELLENCE_CARD with image_url and 3 superstars."""
    from app.services.card_service import PLACEMENT_EXCELLENCE_CARD
    cards = generate_cards(
        user_message="tell me about campus placements and highest packages",
        answer="SR University achieved three consecutive years of excellence with highest package of 51 LPA at Microsoft.",
    )
    assert len(cards) == 1
    assert cards[0] == PLACEMENT_EXCELLENCE_CARD
    assert cards[0]["image_url"] == "/placements-three-years.png"
    assert len(cards[0]["superstars"]) == 3
    companies = [star["company"] for star in cards[0]["superstars"]]
    assert "Microsoft" in companies
    assert "Amazon" in companies
    assert "ServiceNow" in companies

    # Verify stats do NOT repeat the 3 superstars
    stat_values = [s["value"] for s in cards[0]["stats"]]
    assert "51 LPA" not in stat_values
    assert "49.30 LPA" not in stat_values
    assert "46.38 LPA" not in stat_values

    # Verify marquee_offers celebrates the other achievers
    assert len(cards[0]["marquee_offers"]) >= 5
    marquee_companies = [m["company"] for m in cards[0]["marquee_offers"]]
    assert "Salesforce" in marquee_companies
    assert "PayPal" in marquee_companies
    assert "Cisco" in marquee_companies


def test_hostel_card_includes_4000_seat_dining_and_living_motto():
    """Verify hostel card includes living & learning subtitle and 4,000 capacity dining hall."""
    from app.services.card_service import HOSTEL_FEE_CARD
    cards = generate_cards(
        user_message="what are the hostel fees and facilities?",
        answer="Hostel fees range from ₹85,000 to ₹1,35,000 per year with modern amenities.",
    )
    assert len(cards) == 1
    assert cards[0] == HOSTEL_FEE_CARD
    assert "living and learning experience continues" in cards[0].get("subtitle", "").lower()
    assert any("4,000-seat" in item.get("note", "") for item in cards[0]["items"])


def test_about_sru_triggers_campus_tour_card():
    """Verify general 'about sru' questions trigger CAMPUS_TOUR_CARD."""
    from app.services.card_service import CAMPUS_TOUR_CARD
    cards = generate_cards(
        user_message="tell me about sru and the campus",
        answer="SR University is a next-generation living and learning campus located in Warangal, Telangana.",
    )
    assert len(cards) == 1
    assert cards[0] == CAMPUS_TOUR_CARD
    assert any("4,000-Seat" in spot["name"] for spot in cards[0]["spots"])
    assert any("Faculty" in spot["name"] for spot in cards[0]["spots"])


def test_sru_advantage_comparison_card_trigger():
    """Verify comparison / 'why sru' queries trigger SRU_ADVANTAGE_CARD."""
    from app.services.card_service import SRU_ADVANTAGE_CARD
    
    test_queries = [
        "why should I choose SRU over other colleges?",
        "how is sru different from other private universities?",
        "compare sru with other colleges",
        "what makes sru unique and special?",
        "is sru better than other colleges?",
    ]
    for q in test_queries:
        cards = generate_cards(
            user_message=q,
            answer="SR University uniquely offers Tier-1 NBA accredited programs, NIRF Top-100 ranking, and 51 LPA highest placement.",
        )
        assert any(c.get("type") == "sru_comparison" for c in cards), f"Failed for query: {q}"
        sru_card = next(c for c in cards if c.get("type") == "sru_comparison")
        assert sru_card == SRU_ADVANTAGE_CARD
        assert len(sru_card["advantages"]) >= 8
        categories = [adv["category"] for adv in sru_card["advantages"]]
        assert "Rankings & Accreditations" in categories
        assert "Placement Excellence" in categories
        assert "Innovation & Startups (SRiX)" in categories


def test_no_150_acres_in_cards_or_descriptions():
    """Verify 150 acres is completely absent from all card definitions."""
    import json
    from app.services.card_service import (
        CAMPUS_TOUR_CARD,
        SRU_ADVANTAGE_CARD,
        PLACEMENT_EXCELLENCE_CARD,
        HOSTEL_FEE_CARD,
    )
    for card in (CAMPUS_TOUR_CARD, SRU_ADVANTAGE_CARD, PLACEMENT_EXCELLENCE_CARD, HOSTEL_FEE_CARD):
        card_str = json.dumps(card).lower()
        assert "150 acre" not in card_str
        assert "150-acre" not in card_str
        assert "150+ acre" not in card_str


def test_170_acres_in_campus_tour_and_advantage_cards():
    """Verify 170 acres is prominently featured in campus tour and advantage cards."""
    import json
    from app.services.card_service import CAMPUS_TOUR_CARD, SRU_ADVANTAGE_CARD
    campus_tour_str = json.dumps(CAMPUS_TOUR_CARD).lower()
    advantage_str = json.dumps(SRU_ADVANTAGE_CARD).lower()
    assert "170-acre" in campus_tour_str or "170 acres" in campus_tour_str
    assert "170-acre" in advantage_str or "170 acres" in advantage_str



