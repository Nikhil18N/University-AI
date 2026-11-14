"""Script to ingest SR University Student Handbook markdown documents into ChromaDB & PostgreSQL."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import select
from app.config import settings
from app.db.session import async_session_factory
from app.models.document import Document, DocumentVersion
from app.providers.factory import create_embedding_provider
from app.services.ingestion_service import IngestionService
from app.services.rag_service import COLLECTION_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

HANDBOOK_DOCS = [
    {
        "file": "01_campus_life_and_facilities.md",
        "title": "SRU Student Handbook — Campus Life, Facilities & Contacts",
        "document_type": "handbook",
        "department": "Student Affairs",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "02_academic_regulations_and_examinations.md",
        "title": "SRU Student Handbook — Academic Regulations & Examinations",
        "document_type": "regulation",
        "department": "Academic Affairs",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "03_phd_and_research_regulations.md",
        "title": "SRU Student Handbook — Ph.D. Regulations & Research",
        "document_type": "regulation",
        "department": "Research & Development",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "04_hostels_rules_and_discipline_code.md",
        "title": "SRU Student Handbook — Hostel Rules & Discipline Code",
        "document_type": "regulation",
        "department": "Student Welfare",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "05_career_and_placement_policy.md",
        "title": "SRU Student Handbook — Placement & Career Policy",
        "document_type": "policy",
        "department": "Centre for Student Services and Placements",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "06_curricula_and_course_structures.md",
        "title": "SRU Student Handbook — Curricula & Course Structures",
        "document_type": "curriculum",
        "department": "Academic Affairs",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "07_attendance_and_detention_policy.md",
        "title": "SRU Student Handbook — Attendance Regulations & Condonation",
        "document_type": "policy",
        "department": "Academic Affairs",
        "effective_date": datetime(2023, 8, 1, tzinfo=timezone.utc),
    },
    {
        "file": "08_admissions_fees_scholarships_and_eligibility.md",
        "title": "SRU Student Handbook — Admissions, Fees, Scholarships & Eligibility",
        "document_type": "admissions_policy",
        "department": "Admissions & Financial Aid",
        "effective_date": datetime(2026, 6, 1, tzinfo=timezone.utc),
    },
    {
        "file": "09_verified_sru_facts.md",
        "title": "SRU Verified Knowledge Registry — Official Facts & Standards",
        "document_type": "registry",
        "department": "Admissions & University Administration",
        "effective_date": datetime(2026, 10, 30, tzinfo=timezone.utc),
    },
    {
        "file": "10_admissions_presentation_oct2026.md",
        "title": "SRU Admissions Presentation Facts (30 Oct 2026)",
        "document_type": "admissions_deck",
        "department": "Admissions & Marketing",
        "effective_date": datetime(2026, 10, 30, tzinfo=timezone.utc),
    },
]


async def clear_existing_handbook_docs(db, collection):
    """Remove previously ingested handbook documents to prevent duplicate chunks."""
    handbook_titles = {d["title"] for d in HANDBOOK_DOCS}

    if collection is not None:
        for t in handbook_titles:
            try:
                existing = collection.get(where={"title": t})
                if existing and existing.get("ids"):
                    collection.delete(ids=existing["ids"])
                    logger.info("  Deleted %d chunks for '%s' from ChromaDB", len(existing["ids"]), t)
            except Exception as e:
                logger.warning("  Chroma error: %s", e)

    stmt = select(Document).where(Document.title.in_(handbook_titles))
    res = await db.execute(stmt)
    docs = res.scalars().all()

    for doc in docs:
        logger.info("Removing old handbook version: %s (id=%s)", doc.title, doc.id)
        ver_stmt = select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
        ver_res = await db.execute(ver_stmt)
        for v in ver_res.scalars().all():
            await db.delete(v)
        await db.delete(doc)

    await db.commit()


async def ingest_handbook():
    import chromadb

    handbook_dir = settings.PROJECT_ROOT / "data" / "handbook"
    if not handbook_dir.exists():
        logger.error("Handbook directory not found: %s", handbook_dir)
        return

    embedding_provider = create_embedding_provider()
    ingestion_service = IngestionService(embedding_provider)

    from app.db.chroma import get_chroma_client
    chroma_client = get_chroma_client()
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    async with async_session_factory() as db:
        await clear_existing_handbook_docs(db, collection)

        for doc_info in HANDBOOK_DOCS:
            file_path = handbook_dir / doc_info["file"]
            if not file_path.exists():
                logger.warning("File not found: %s — skipping", file_path)
                continue

            content_bytes = file_path.read_bytes()
            logger.info("Ingesting: %s (%d bytes)", doc_info["title"], len(content_bytes))

            doc = await ingestion_service.ingest_document(
                db=db,
                file_bytes=content_bytes,
                filename=doc_info["file"],
                title=doc_info["title"],
                document_type=doc_info["document_type"],
                department=doc_info["department"],
                effective_date=doc_info["effective_date"],
            )
            logger.info("  [OK] Ingested as document_id=%s (status=%s)", doc.id, doc.status)
            await asyncio.sleep(1.5)

        await db.commit()

    await embedding_provider.close()
    logger.info("Successfully ingested all SRU Student Handbook sections!")

    # Invalidate cached answers (cache keys include index_version), as the admin upload path does.
    try:
        import redis.asyncio as aioredis
        from app.services.cache_service import bump_index_version

        redis_client = aioredis.from_url(settings.REDIS_URL)
        try:
            await bump_index_version(redis_client)
        finally:
            await redis_client.aclose()
        logger.info("index_version bumped in Redis; cached answers invalidated.")
    except Exception as exc:
        logger.warning("Could not bump index_version in Redis (restart Redis or bump manually): %s", exc)


if __name__ == "__main__":
    asyncio.run(ingest_handbook())
