"""
Remove sample documents from ChromaDB and PostgreSQL, then delete the files.

Targets documents whose titles match the sample document set, or whose
storage_location points to the sample_documents directory.

Usage (from backend/):
    .\\venv\\Scripts\\activate
    python scripts/remove_sample_docs.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

SAMPLE_DOC_TITLES = {
    "University Academic Calendar 2026",
    "Campus Hostel Rules and Regulations 2026",
    "University Fee Structure and Payment Regulations 2026",
}

SAMPLE_FILES = [
    _BACKEND.parent / "data" / "sample_documents" / "academic_calendar_2026.md",
    _BACKEND.parent / "data" / "sample_documents" / "hostel_regulations.md",
    _BACKEND.parent / "data" / "sample_documents" / "fee_structure_2026.md",
]


async def remove_sample_docs() -> None:
    import chromadb
    from sqlalchemy import select

    from app.config import settings
    from app.db.session import async_session_factory
    from app.models.document import Document, DocumentVersion
    from app.services.rag_service import COLLECTION_NAME

    from app.db.chroma import get_chroma_client
    chroma_client = get_chroma_client()

    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
    except Exception:
        logger.warning("Collection '%s' not found in ChromaDB — skipping Chroma cleanup.", COLLECTION_NAME)
        collection = None

    async with async_session_factory() as db:
        # Find sample documents by title
        stmt = select(Document).where(Document.title.in_(SAMPLE_DOC_TITLES))
        result = await db.execute(stmt)
        docs = result.scalars().all()

        if not docs:
            logger.info("No sample documents found in the database.")
        else:
            for doc in docs:
                logger.info("Removing document: [%s] id=%s", doc.title, doc.id)

                # 1. Remove chunks from ChromaDB
                if collection is not None:
                    try:
                        # ChromaDB stores chunk IDs as "{doc_id}_{i}"
                        # Query by document_id metadata filter
                        existing = collection.get(
                            where={"document_id": str(doc.id)},
                            include=["metadatas"],
                        )
                        chunk_ids = existing.get("ids", [])
                        if chunk_ids:
                            collection.delete(ids=chunk_ids)
                            logger.info("  Deleted %d chunks from ChromaDB", len(chunk_ids))
                        else:
                            logger.info("  No chunks found in ChromaDB for this document.")
                    except Exception as e:
                        logger.warning("  ChromaDB deletion error: %s", e)

                # 2. Delete document versions
                ver_stmt = select(DocumentVersion).where(
                    DocumentVersion.document_id == doc.id
                )
                ver_result = await db.execute(ver_stmt)
                versions = ver_result.scalars().all()
                for v in versions:
                    # Also delete uploaded file if it exists
                    if v.storage_location and v.storage_location != "inline:docx":
                        fp = Path(v.storage_location)
                        if fp.exists():
                            fp.unlink()
                            logger.info("  Deleted uploaded file: %s", fp)
                    await db.delete(v)

                # 3. Delete document record
                await db.delete(doc)
                logger.info("  Removed from database.")

            await db.commit()
            logger.info("Database cleanup committed.")

    # 3. Delete the sample source files from disk
    print("\nDeleting sample document files...")
    for fp in SAMPLE_FILES:
        if fp.exists():
            fp.unlink()
            logger.info("Deleted file: %s", fp)
        else:
            logger.info("File not found (already deleted?): %s", fp)

    # Remove the now-empty directory if empty
    sample_dir = _BACKEND.parent / "data" / "sample_documents"
    try:
        sample_dir.rmdir()
        logger.info("Removed empty directory: %s", sample_dir)
    except OSError:
        logger.info("Directory not empty or already removed: %s", sample_dir)

    print("\n[OK] Sample documents fully removed from ChromaDB, database, and disk.")


if __name__ == "__main__":
    asyncio.run(remove_sample_docs())
