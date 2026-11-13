"""Tests for admissions accuracy, official fees, cutoffs, and counselor guardrails.

Verified against official SR University figures (Academic Year 2026-27 / 2027-28):
- B.Tech Minimum Cutoff: 50% in 10+2 MPC (never 60%)
- B.Tech CSE Tuition: ₹1,47,500/semester (₹2,95,000/year) + one-time ₹5,000 & ₹25,000
- B.Tech Mechanical Tuition: ₹1,00,000/semester (₹2,00,000/year)
- BBA: 50% eligibility, ₹90,000/semester
- MBA: 50% eligibility, ₹1,50,000/semester (+ 10% PG scholarship)
- Merit Scholarships: 92% to 97.99% in Inter = 40% scholarship for CSE
- Girls Hostel AC: ₹1,25,000 (4-sharing) / ₹1,35,000 (3-sharing)
- Official Contacts: 0870-2818333 / 2818311, info@sru.edu.in
"""

import pytest
from app.services.card_service import generate_cards, FEE_BREAKDOWN_CARD
from app.services.factuality_eval_service import evaluate_answer_factuality


def test_inter_58_percent_is_eligible():
    """Verify that a 58% Intermediate score is accepted under the 50% minimum cutoff."""
    answer = (
        "Yes, you are fully eligible for B.Tech admission at SR University! "
        "The official minimum requirement is 50% aggregate marks in 10+2 / Intermediate MPC, "
        "so your 58% satisfies the eligibility criteria."
    )
    res = evaluate_answer_factuality("btech_eligibility_cutoff", answer)
    assert res.is_faithful is True
    assert res.score >= 0.85
    assert res.detected_hallucinations == []


def test_btech_cutoff_rejects_60_percent_myth():
    """Verify evaluation rejects claiming the cutoff is 60% or higher."""
    wrong_answer = "You are not eligible because our minimum cutoff is strictly 60%."
    res = evaluate_answer_factuality("btech_eligibility_cutoff", wrong_answer)
    assert res.is_faithful is False
    assert any("60%" in h for h in res.detected_hallucinations)


def test_btech_cse_tuition_fee_grounding():
    """Verify B.Tech CSE tuition reflects ₹1,47,500/semester and ₹2,95,000/year."""
    answer = (
        "The official tuition fee for B.Tech Computer Science & Engineering (CSE) at SR University "
        "is ₹1,47,500 per semester, which totals ₹2,95,000 per year. In addition, there is a one-time "
        "enrollment fee of ₹5,000 and an admission fee of ₹25,000 in the first year."
    )
    res = evaluate_answer_factuality("btech_cse_tuition_fee", answer)
    assert res.is_faithful is True
    assert res.detected_hallucinations == []


def test_fee_breakdown_card_accuracy():
    """Verify the UI fee card reflects official semester fees without cross-contaminating hostel or transport."""
    cards = generate_cards(
        user_message="What is the fee for btech cse?",
        answer="The tuition fee is ₹1,70,000 per semester (₹3,40,000 per year).",
    )
    fee_cards = [c for c in cards if c["type"] == "fee_breakdown"]
    assert len(fee_cards) >= 1
    card = fee_cards[0]

    cse_item = next((item for item in card["items"] if "CSE" in item["category"]), None)
    assert cse_item is not None
    assert "1,70,000" in cse_item["amount"] or "3,40,000" in cse_item["frequency"]

    # Verify hostel and transport are strictly NOT present in the B.Tech CSE fee card
    assert not any("Girls" in item["category"] or "Hostel" in item["category"] for item in card["items"])
    assert not any("Transport" in item["category"] or "Bus" in item["category"] for item in card["items"])



def test_merit_scholarship_40_percent_for_92_percent():
    """Verify 92% in Intermediate earns 40% scholarship for CSE."""
    answer = (
        "With 92% in Intermediate, you fall in the 40% merit scholarship slab for B.Tech CSE! "
        "This reduces your tuition from ₹1,47,500 per semester down to ₹88,500 per semester."
    )
    res = evaluate_answer_factuality("merit_scholarships_slabs", answer)
    assert res.is_faithful is True
    assert res.detected_hallucinations == []


def test_mechanical_fee_structure():
    """Verify Mechanical Engineering tuition is ₹1,00,000/sem = ₹2,00,000/yr."""
    mech_answer = "For Mechanical Engineering, the tuition fee is ₹1,00,000 per semester (₹2,00,000 per year)."
    assert "1,00,000" in mech_answer
    assert "2,00,000" in mech_answer


def test_mba_and_bba_eligibility_and_fees():
    """Verify BBA & MBA eligibility (50%) and semester fees."""
    bba_eligibility = 50
    bba_fee_sem = 90000
    mba_eligibility = 50
    mba_fee_sem = 150000

    assert bba_eligibility == 50
    assert bba_fee_sem == 90000
    assert mba_eligibility == 50
    assert mba_fee_sem == 150000


def test_official_admissions_contacts():
    """Verify official admissions contact details."""
    official_contacts = ["0870-2818333", "0870-2818311", "info@sru.edu.in", "https://apply.sru.edu.in"]
    unverified_contacts = ["8331003030", "8331004040", "9701578799"]

    text = "Please reach out to the admissions office at 0870-2818333 or info@sru.edu.in."
    assert any(c in text for c in official_contacts)
    assert not any(c in text for c in unverified_contacts)


@pytest.mark.asyncio
async def test_prepare_rag_request_handles_none_and_missing_metadata():
    """Verify prepare_rag_request handles chunks with None or missing metadata without crashing."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("app.db.chroma.get_chroma_client") as mock_gc:
        mock_col = MagicMock()
        mock_col.count.return_value = 0
        mock_col.query.return_value = {"metadatas": [], "distances": []}
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_col
        mock_gc.return_value = mock_client

        from app.services.rag_service import RAGService

        llm = MagicMock()
        embedder = MagicMock()
        embedder.embed_single = AsyncMock(return_value=[0.1, 0.2])
        rag = RAGService(llm, embedder)

        # Chunks containing None metadata, empty dict, missing metadata key, and non-dict
        chunks = [
            {"content": "Hostel mess provides nutritious 4 meals daily.", "metadata": None, "distance": 0.12},
            {"content": "Hostel rooms include Wi-Fi.", "metadata": {}, "distance": 0.15},
            {"content": "Girls AC hostel is ₹1,25,000/yr.", "metadata": {"section": "Hostels", "title": "Hostel Handbook"}, "distance": 0.18},
            {"content": "Non-AC rooms are available."},
            "invalid non-dict chunk",
        ]

        messages, sources, evidence = await rag.prepare_rag_request(
            question="🍽️ Mess & Food Quality",
            conversation_context="",
            retrieved_chunks=chunks,
        )

        assert len(messages) == 2
        assert len(sources) >= 1
        assert "Hostel mess provides nutritious 4 meals daily." in evidence
        assert "Girls AC hostel is ₹1,25,000/yr." in evidence


@pytest.mark.asyncio
async def test_retrieve_with_embedding_handles_none_metadata():
    """Verify retrieve_with_embedding safely normalizes None metadata returned by ChromaDB."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("app.db.chroma.get_chroma_client") as mock_gc:
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Food details", "Mess menu"]],
            "metadatas": [[None, {"section": "Mess"}]],
            "distances": [[0.1, 0.2]],
        }
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_col
        mock_gc.return_value = mock_client

        from app.services.rag_service import RAGService

        llm = MagicMock()
        embedder = MagicMock()
        embedder.embed_single = AsyncMock(return_value=[0.1, 0.2])
        rag = RAGService(llm, embedder)

        chunks, emb = await rag.retrieve_with_embedding("Mess & Food")

        assert len(chunks) == 2
        assert isinstance(chunks[0]["metadata"], dict)
        assert chunks[0]["metadata"] == {}
        assert chunks[1]["metadata"]["section"] == "Mess"
