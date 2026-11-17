"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _agent_memory_stays_in_the_test():
    """The live app keeps student profiles and chat context in PostgreSQL (app/main.py wires the
    hooks). Unit tests use fixed session names, so with a real database one run would find the
    profiles left by the previous run. Tests therefore run with the agent's memory in-process
    only; tests that check the lasting storage set the hooks themselves."""
    from app.sru_agent import memory

    before = (memory._profile_loader, memory._profile_saver, memory._history_loader)
    memory.set_profile_store(None, None)
    memory.set_history_loader(None)
    memory._local.clear()
    memory._hot.clear()
    memory._pending_writes.clear()
    r = memory._client()
    if r:
        try:
            import asyncio
            asyncio.run(r.flushdb())
        except Exception:
            pass
    yield
    memory._local.clear()
    memory._hot.clear()
    memory._pending_writes.clear()
    r = memory._client()
    if r:
        try:
            import asyncio
            asyncio.run(r.flushdb())
        except Exception:
            pass
    memory._profile_loader, memory._profile_saver, memory._history_loader = before
