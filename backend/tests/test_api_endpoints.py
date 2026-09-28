"""Tests for FastAPI endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import get_db
from app.main import app

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


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert data["services"]["database"] == "healthy"


@pytest.mark.asyncio
async def test_list_conversations_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/conversations?session_id=test-session-123")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


@pytest.mark.asyncio
async def test_feedback_submission():
    import uuid
    from app.services import conversation_service

    async with TestSession() as session:
        # Create a conversation and message first
        conv = await conversation_service.get_or_create_conversation(
            session, "test-session-456", None
        )
        msg = await conversation_service.add_message(
            session, conv.id, "assistant", "Sample response"
        )
        await session.commit()
        conv_id = str(conv.id)
        msg_id = str(msg.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "session_id": "test-session-456",
            "conversation_id": conv_id,
            "message_id": msg_id,
            "rating": 1,
            "comment": "Helpful answer!",
        }
        response = await client.post("/api/v1/feedback", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "received"
        assert "id" in data
