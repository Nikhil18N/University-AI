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


def _handbook_fingerprint(handbook_dir: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    for path in sorted(handbook_dir.glob("*.md")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


async def refresh_handbook_if_changed() -> bool:
    """Re-index the handbook when its files changed since the vector index was built.

    The vector index is only seeded when it is empty, so an edited handbook file used to leave the
    OLD text in the index for ever. A fingerprint of the handbook files is kept beside the index;
    when it no longer matches, the handbook documents are replaced. Best effort: if the embedding
    quota is exhausted the old index stays and this is retried on the next start. (The admissions
    agent does not depend on it: it reads the handbook files directly.)
    """
    handbook_dir = settings.PROJECT_ROOT / "data" / "handbook"
    if not handbook_dir.is_dir():
        return False
    marker = Path(settings.CHROMA_PERSIST_DIR or "./chroma_data") / "handbook.sha256"
    fingerprint = _handbook_fingerprint(handbook_dir)
    try:
        if marker.exists() and marker.read_text(encoding="utf-8").strip() == fingerprint:
            return False
        logger.info("Handbook files changed since the last indexing; refreshing the vector index...")
        from scripts.ingest_handbook_docs import ingest_handbook
        await ingest_handbook()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(fingerprint, encoding="utf-8")
        return True
    except Exception as err:
        logger.warning("Handbook re-index skipped (will retry on next start): %s", err)
        return False


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
            try:
                from app.services.video_service import sync_video_vectors
                await sync_video_vectors()
            except Exception as ve:
                logger.warning("Could not sync video vectors: %s", ve)
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
            try:  # remember which handbook text is in the index (see refresh_handbook_if_changed)
                marker = Path(settings.CHROMA_PERSIST_DIR or "./chroma_data") / "handbook.sha256"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(_handbook_fingerprint(settings.PROJECT_ROOT / "data" / "handbook"), encoding="utf-8")
            except Exception as marker_err:
                logger.warning("Could not record the handbook fingerprint: %s", marker_err)

        # Ensure semantic video vectors are synced in ChromaDB
        try:
            from app.services.video_service import sync_video_vectors
            await sync_video_vectors()
        except Exception as ve:
            logger.warning("Could not sync video vectors during auto-seed: %s", ve)

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

        # Foundational B.Tech eligibility exemplar (50% cutoff)
        q1 = "What is the eligibility criteria and admission process for B.Tech?"
        match1 = await svc.find_matching_exemplar(q1, distance_threshold=0.20)
        if not match1:
            ans1 = (
                "To join our B.Tech program, you need to have passed your 10+2 or equivalent examination with "
                "a minimum of 50% aggregate marks in Mathematics, Physics, and Chemistry (MPC). We offer admissions based "
                "on board marks as well as JEE Main and TG EAPCET ranks.\n\n"
                "To help confirm your eligibility and merit scholarship slab, could you please share your 10+2 MPC percentage?"
            )
            await svc.register_exemplar(uuid.uuid4(), q1, ans1)

        # Gold standard score & fee breakdown exemplar (878/1000 score)
        q2 = "I scored 878/1000 in intermediate. What is my fee and scholarship?"
        match2 = await svc.find_matching_exemplar(q2, distance_threshold=0.20)
        if not match2:
            ans2 = (
                "Nice score! 87.8% falls in the 80–91.9% band, so you'd get the **25% merit waiver**: "
                "₹2,55,000/year tuition (₹1,27,500 per semester), subject to marksheet verification. Tuition rises ₹9,000 yearly.\n\n"
                "**Verification:** bring original 10th and 12th marksheets, TC, ID/category proof, and photos.\n"
                "**Hostel:** 3- or 4-sharing, AC or Non-AC, ₹1,15,000–₹1,35,000/year including 4 meals.\n"
                "**Rough first-year total:** about ₹3.70–3.90 lakh (tuition + room & mess), plus laundry and refundable deposits.\n\n"
                "Want me to compare AC vs Non-AC, or check extra concessions you may qualify for?"
            )
            await svc.register_exemplar(uuid.uuid4(), q2, ans2)
            logger.info("Auto-seeded gold standard merit scholarship verified exemplar.")
    except Exception as e:
        logger.warning("Could not auto-seed exemplars: %s", e)


