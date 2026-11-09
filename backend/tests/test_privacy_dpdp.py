"""Unit and integration tests for DPDP compliance: masking, retention purge, and delete-my-data endpoint (T6)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.evaluation import EvaluationRecord
from app.models.lead import ProspectiveLead
from app.models.message import Message
import sys
from pathlib import Path

# Ensure backend root and scripts are importable
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
if str(backend_root / "scripts") not in sys.path:
    sys.path.insert(0, str(backend_root / "scripts"))

from purge_old_conversations import purge_old_records
from app.services.evaluation_service import record_evaluation
from app.utils.privacy import mask_email, mask_phone, mask_pii

# Use NullPool for tests so asyncpg connections aren't shared across different event loops
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Unit tests: Regex & PII masking
# ---------------------------------------------------------------------------

def test_mask_email():
    assert mask_email("contact me at admissions@sru.edu.in") == "contact me at a***@sru.edu.in"
    assert mask_email("student.kumar.99@gmail.com") == "s***@gmail.com"
    assert mask_email("x@domain.org") == "x***@domain.org"
    assert mask_email("no email here") == "no email here"


def test_mask_phone():
    assert mask_phone("My mobile is 9876543210") == "My mobile is 98765*****"
    assert mask_phone("call +91-98765-43210 please") == "call +91-98765-***** please"
    assert mask_phone("reach out at +91 9123456789") == "reach out at +91 91234*****"
    assert mask_phone("fee is 125000") == "fee is 125000"  # Not a mobile number (doesn't start with 6-9)


def test_mask_pii_combined():
    raw = "Hi, my phone is 9876543210 and my email is test.user@example.com."
    masked = mask_pii(raw)
    assert "98765*****" in masked
    assert "t***@example.com" in masked
    assert "9876543210" not in masked
    assert "test.user@example.com" not in masked


# ---------------------------------------------------------------------------
# Service tests: evaluation_service record_evaluation masks inputs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_evaluation_masks_pii():
    raw_question = "Can I get admission? Phone: 9876543210, Email: rajesh@example.com"
    raw_answer = "Sure, reach Admissions at 0870-2818333. We noted your phone 9876543210."

    async with TestSession() as db_session:
        record = await record_evaluation(
            db=db_session,
            question=raw_question,
            actual_answer=raw_answer,
            metadata={"user_phone": "9876543210", "note": "contact rajesh@example.com"},
        )

        assert "9876543210" not in record.question
        assert "98765*****" in record.question
        assert "rajesh@example.com" not in record.question
        assert "r***@example.com" in record.question

        assert "9876543210" not in record.actual_answer
        assert "98765*****" in record.actual_answer

        assert record.metadata_["user_phone"] == "98765*****"
        assert record.metadata_["note"] == "contact r***@example.com"


# ---------------------------------------------------------------------------
# Retention Purge script tests (dry-run & actual purge)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purge_old_records_dry_run_and_execution():
    # Create fake old conversation & message (100 days old)
    old_time = datetime.now(timezone.utc) - timedelta(days=100)

    async with TestSession() as db_session:
        conv = Conversation(
            session_id=f"test-purge-session-{uuid4()}",
            title="Old Discussion",
            created_at=old_time,
        )
        db_session.add(conv)
        await db_session.flush()

        msg = Message(
            conversation_id=conv.id,
            role="user",
            content="Old message from 100 days ago",
            created_at=old_time,
        )
        db_session.add(msg)

        eval_rec = EvaluationRecord(
            conversation_id=conv.id,
            question="Old test question",
            actual_answer="Old test answer",
            created_at=old_time,
        )
        db_session.add(eval_rec)
        await db_session.commit()

        # 1. Test Dry Run: Counts should be reported but rows MUST remain untouched
        dry_counts = await purge_old_records(db_session, days=90, dry_run=True)
        assert dry_counts["conversations"] >= 1
        assert dry_counts["messages"] >= 1
        assert dry_counts["evaluation_records"] >= 1

        # Verify rows still exist
        check_conv = (await db_session.execute(select(Conversation).where(Conversation.id == conv.id))).scalar_one_or_none()
        assert check_conv is not None

        # 2. Test Execution: Deletes rows
        exec_counts = await purge_old_records(db_session, days=90, dry_run=False)
        assert exec_counts["conversations"] >= 1

        # Verify rows were deleted
        deleted_conv = (await db_session.execute(select(Conversation).where(Conversation.id == conv.id))).scalar_one_or_none()
        assert deleted_conv is None


# ---------------------------------------------------------------------------
# API endpoint tests: /api/v1/privacy/delete-my-data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_my_data_endpoint():
    unique_session = f"delete-me-session-{uuid4()}"
    test_phone = "9876599999"

    async with TestSession() as db_session:
        # Create dummy conversation and lead
        conv = Conversation(
            session_id=unique_session,
            title="Session to be erased",
        )
        db_session.add(conv)
        await db_session.flush()

        msg = Message(
            conversation_id=conv.id,
            role="user",
            content="Please delete this conversation later",
        )
        db_session.add(msg)

        lead = ProspectiveLead(
            name="Test Lead",
            phone=test_phone,
            email="testlead@example.com",
            conversation_id=conv.id,
        )
        db_session.add(lead)
        await db_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Bad request when neither session_id nor phone provided
            bad_resp = await client.post("/api/v1/privacy/delete-my-data", json={})
            assert bad_resp.status_code == 400

            # 2. Successful erasure by session_id & phone
            resp = await client.post(
                "/api/v1/privacy/delete-my-data",
                json={"session_id": unique_session, "phone": test_phone},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["deleted_conversations"] >= 1
            assert data["deleted_messages"] >= 1
            assert data["deleted_leads"] >= 1

        # Verify in DB that rows are gone
        conv_check = (await db_session.execute(select(Conversation).where(Conversation.session_id == unique_session))).scalar_one_or_none()
        assert conv_check is None

        lead_check = (await db_session.execute(select(ProspectiveLead).where(ProspectiveLead.phone == test_phone))).scalar_one_or_none()
        assert lead_check is None
