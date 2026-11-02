"""Automatic background seeding for university documents when vector store is empty."""

import asyncio
import logging
from pathlib import Path

from app.config import settings
from app.db.chroma import get_chroma_client
from app.services.rag_service import COLLECTION_NAME

logger = logging.getLogger(__name__)


def _find_data_path(rel_path: str) -> Path | None:
    """Find a relative path within possible project data directories."""
    candidates = [
        Path.cwd() / "data" / rel_path,
        Path.cwd() / "backend" / "data" / rel_path,
        settings.PROJECT_ROOT / "data" / rel_path,
        settings.PROJECT_ROOT / "backend" / "data" / rel_path,
        Path(__file__).resolve().parent.parent.parent / "data" / rel_path,
        Path(__file__).resolve().parent.parent.parent.parent / "data" / rel_path,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


async def ensure_documents_seeded() -> int:
    """Check if ChromaDB collection has documents; if empty, ingest automatically."""
    try:
        import sys
        backend_dir = Path(__file__).resolve().parent.parent.parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        scripts_dir = backend_dir / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        count = collection.count()
        if count > 0:
            logger.info("ChromaDB '%s' collection has %d documents. No seeding needed.", COLLECTION_NAME, count)
            return count

        logger.warning(
            "ChromaDB '%s' collection is empty (%d chunks). Starting automatic document ingestion...",
            COLLECTION_NAME,
            count,
        )

        docx_path = _find_data_path("SRU Agentic AI.docx")
        if docx_path:
            logger.info("Auto-seeding FAQ from: %s", docx_path)
            from scripts.parse_university_docx import parse_university_docx
            from scripts.ingest_university_doc import _ingest_entries

            entries = parse_university_docx(docx_path)
            if entries:
                await _ingest_entries(entries, department_override=None, clear_existing=False)
                logger.info("Auto-seeded %d FAQ entries from docx.", len(entries))

        handbook_dir = _find_data_path("handbook")
        if handbook_dir and handbook_dir.is_dir():
            logger.info("Auto-seeding student handbook from: %s", handbook_dir)
            from scripts.ingest_handbook_docs import ingest_handbook

            await ingest_handbook()
            logger.info("Auto-seeded handbook markdown documents.")

        new_count = collection.count()
        logger.info("Document auto-seeding completed. Total chunks in ChromaDB: %d", new_count)
        return new_count

    except Exception as e:
        logger.error("Auto-seeding encountered an error: %s", e, exc_info=True)
        return 0
