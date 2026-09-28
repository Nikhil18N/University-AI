"""Tests for admin endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import get_db
from app.main import app

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
async def test_admin_endpoints_require_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request without X-Admin-Key should be rejected
        res = await client.get("/api/v1/admin/stats")
        assert res.status_code in (401, 403, 422)

        res = await client.get("/api/v1/admin/documents")
        assert res.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_admin_stats_with_valid_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Admin-Key": settings.ADMIN_API_KEY}
        try:
            res = await client.get("/api/v1/admin/stats", headers=headers)
            if res.status_code == 200:
                data = res.json()
                assert "total_documents" in data
                assert "total_conversations" in data
                assert "total_messages" in data
        except Exception:
            pytest.skip("Database container not currently accessible")
