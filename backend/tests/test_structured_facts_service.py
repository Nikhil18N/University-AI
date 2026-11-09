"""Unit and service tests for authoritative structured facts service (P0 Hardening T2)."""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.models.structured_fact import StructuredFact
from app.services.structured_facts_service import (
    get_active_facts,
    get_all_grounded_numbers,
    get_structured_facts_text,
    refresh_facts_cache_from_db,
    update_structured_fact,
)
from app.services.validator_service import validate_response_grounding


@pytest.mark.asyncio
async def test_load_facts_from_db():
    mock_db = MagicMock()
    fake_fact = StructuredFact(
        id=uuid.uuid4(),
        category="fee",
        program="B.Tech Data Science",
        key_attribute="tuition_fee_sem",
        numeric_value=135000.0,
        currency="INR",
        formatted_value="₹1,35,000 per semester",
        frequency="per_semester",
        academic_year="2026-27",
        source_doc="Test Catalog",
        metadata_={"source_url": "https://sru.edu.in", "last_updated": "2026-11-09T00:00:00Z", "updated_by": "tester"},
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_fact]
    mock_db.execute = AsyncMock(return_value=mock_result)

    facts = await refresh_facts_cache_from_db(mock_db)
    assert len(facts) == 1
    assert facts[0]["program"] == "B.Tech Data Science"
    assert facts[0]["formatted_value"] == "₹1,35,000 per semester"
    assert facts[0]["updated_by"] == "tester"


def test_validator_grounding_set_reads_from_structured_facts_service():
    """Validator grounding set directly imports from structured facts service."""
    grounded_numbers = get_all_grounded_numbers()
    assert "₹1,47,500" in grounded_numbers
    assert "147500" in grounded_numbers
    assert "51 LPA" in grounded_numbers
    assert "6 LPA" in grounded_numbers


@pytest.mark.asyncio
async def test_update_structured_fact_bumps_facts_version():
    mock_db = MagicMock()
    fact_id = uuid.uuid4()
    existing_fact = StructuredFact(
        id=fact_id,
        category="fee",
        program="B.Tech CSE",
        key_attribute="tuition_fee_sem",
        numeric_value=147500.0,
        currency="INR",
        formatted_value="₹1,47,500 per semester",
        frequency="per_semester",
        academic_year="2026-27",
        source_doc="Old Fee Doc",
        metadata_={"last_updated": "2026-01-01T00:00:00Z", "updated_by": "seed"},
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_fact
    mock_result.scalars.return_value.all.return_value = [existing_fact]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(return_value=2)

    updated = await update_structured_fact(
        db=mock_db,
        fact_id=fact_id,
        updates={"formatted_value": "₹1,55,000 per semester", "numeric_value": 155000.0},
        editor="admin_qa",
        redis_client=mock_redis,
    )

    assert updated is not None
    assert updated["formatted_value"] == "₹1,55,000 per semester"
    assert updated["updated_by"] == "admin_qa"
    mock_redis.incr.assert_called_once()
    mock_db.commit.assert_called_once()


def test_validator_accepts_grounded_structured_numbers():
    """Validator accepts numbers that match active structured facts."""
    ans = "The tuition fee for B.Tech CSE is ₹1,47,500 per semester."
    is_valid, ungrounded = validate_response_grounding(
        ans,
        evidence_text="",
        structured_data_text="B.Tech CSE tuition: ₹1,47,500 per semester",
        user_message="cse fees?",
    )
    assert is_valid is True
    assert len(ungrounded) == 0


def test_validator_rejects_hallucinated_unstructured_numbers():
    """Validator blocks numbers that do not appear in structured facts or context."""
    ans = "The tuition fee for B.Tech CSE is ₹9,99,999 per semester."
    is_valid, ungrounded = validate_response_grounding(
        ans,
        evidence_text="Regular fee details",
        structured_data_text="B.Tech CSE tuition: ₹1,47,500 per semester",
        user_message="cse fees?",
    )
    assert is_valid is False
    assert any("999999" in u or "9,99,999" in u for u in ungrounded)
