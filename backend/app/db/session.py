"""Async SQLAlchemy engine and session factory."""

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
except ImportError:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker as async_sessionmaker

from app.config import settings

def get_database_url() -> str:
    url = (settings.DATABASE_URL or "").strip().strip('"').strip("'")
    if url.startswith("DATABASE_URL="):
        url = url[len("DATABASE_URL="):].strip().strip('"').strip("'")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def alembic_database_url() -> str:
    """The same cleaned URL for Alembic. Its config reader treats '%' as interpolation, so a URL-encoded password
    ('%26' for '&') must be written as '%%26' there."""
    return get_database_url().replace("%", "%%")


_db_url = get_database_url()
_connect_args = {}
if ":6543" in _db_url:
    _connect_args["prepared_statement_cache_size"] = 0
elif _db_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

try:
    engine = create_async_engine(
        _db_url,
        echo=settings.APP_DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        connect_args=_connect_args,
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
except Exception:
    engine = None
    async_session_factory = None


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
