"""Idempotent seed script for populating the structured_facts PostgreSQL table.

Usage:
    python backend/scripts/seed_structured_facts.py [--dry-run]
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.structured_fact import StructuredFact
from app.services.structured_facts_service import VERIFIED_FACTS_REGISTRY


async def seed_structured_facts(dry_run: bool = False):
    """Seed structured_facts table from VERIFIED_FACTS_REGISTRY idempotently."""
    async with async_session_factory() as session:
        # Check existing facts
        stmt = select(StructuredFact)
        result = await session.execute(stmt)
        existing_facts = result.scalars().all()
        existing_keys = {(f.category, f.program, f.key_attribute) for f in existing_facts}

        to_insert = []
        for fact in VERIFIED_FACTS_REGISTRY:
            key_tuple = (fact["category"], fact["program"], fact["key_attribute"])
            if key_tuple not in existing_keys:
                to_insert.append(fact)

        print(f"Existing structured facts in DB: {len(existing_facts)}")
        print(f"New structured facts to insert: {len(to_insert)}")

        if not to_insert:
            print("Database is already up to date. Zero changes needed.")
            return

        print("\n--- DIFF / INSERTION PREVIEW ---")
        for f in to_insert:
            print(f"+ [{f['category'].upper()}] {f['program']} -> {f['key_attribute']}: {f['formatted_value']}")

        if dry_run:
            print("\n[DRY RUN] No database changes committed.")
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        for f in to_insert:
            row = StructuredFact(
                category=f["category"],
                program=f["program"],
                key_attribute=f["key_attribute"],
                numeric_value=f.get("numeric_value"),
                currency=f.get("currency"),
                formatted_value=f["formatted_value"],
                frequency=f.get("frequency"),
                academic_year="2026-27",
                source_doc=f.get("source_doc", "SRU Official Catalog"),
                notes=None,
                metadata_={
                    "source_url": "https://sru.edu.in/admissions",
                    "last_updated": now_iso,
                    "updated_by": "system_seed",
                },
            )
            session.add(row)

        await session.commit()
        print(f"\nSuccessfully seeded {len(to_insert)} structured facts into PostgreSQL table 'structured_facts'.")


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    asyncio.run(seed_structured_facts(dry_run=is_dry))

