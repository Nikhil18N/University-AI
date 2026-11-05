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

        # Also ensure foundational verified exemplars are seeded
        await ensure_exemplars_seeded()

        return new_count

    except Exception as e:
        logger.error("Auto-seeding encountered an error: %s", e, exc_info=True)
        return 0


async def ensure_exemplars_seeded():
    """Seed foundational verified exemplars into ChromaDB if not already present."""
    try:
        from app.providers.factory import create_embedding_provider
        from app.services.exemplar_service import ExemplarService
        import uuid

        embed = create_embedding_provider()
        svc = ExemplarService(embed)
        collection = svc._get_collection()
        if not collection:
            return

        q = "What is the eligibility criteria and admission process for B.Tech 2026?"
        match = await svc.find_matching_exemplar(q, distance_threshold=0.20)
        if not match:
            ans = (
                "To join our B.Tech program, you need to have passed your 10+2 or equivalent examination with "
                "a minimum of 60% aggregate marks in Physics, Chemistry, and Mathematics. The admission process "
                "is straightforward as we offer direct admissions based on your board marks, meaning there is no "
                "requirement to appear for any entrance exams.\n\n"
                "To help me confirm your eligibility, could you please share your 10+2 PCM percentage? \n\n"
                "Would you like to know more about our available engineering branches?"
            )
            await svc.register_exemplar(uuid.uuid4(), q, ans)
            await svc.register_exemplar(uuid.uuid4(), "What is the eligibility criteria and admission process for B.Tech?", ans)
            logger.info("Auto-seeded foundational B.Tech admission verified exemplar.")
    except Exception as e:
        logger.warning("Could not auto-seed exemplars: %s", e)

