"""v4.18.0: migrations applied at startup must work with real hosted URLs, and never log the password."""
import configparser


def test_alembic_gets_the_cleaned_url_with_percent_escaped(monkeypatch):
    from app.db import session
    pasted = 'DATABASE_URL=postgresql://user.proj:p%26ss-5@pooler.example.com:5432/postgres?ssl=require\n'
    monkeypatch.setattr(session.settings, "DATABASE_URL", pasted)
    url = session.alembic_database_url()
    parser = configparser.ConfigParser()             # what Alembic's config uses
    parser.add_section("alembic")
    parser.set("alembic", "sqlalchemy.url", url)
    assert parser.get("alembic", "sqlalchemy.url") == \
        "postgresql+asyncpg://user.proj:p%26ss-5@pooler.example.com:5432/postgres?ssl=require"


def test_startup_warnings_never_contain_the_connection_url():
    from app.main import _without_urls
    msg = ("invalid interpolation syntax in 'DATABASE_URL=postgresql+asyncpg://u:secret%26pw@host:5432/db?ssl=require\\n'"
           " at position 68")
    cleaned = _without_urls(msg)
    assert "secret" not in cleaned and "host:5432" not in cleaned and "<connection URL hidden>" in cleaned
