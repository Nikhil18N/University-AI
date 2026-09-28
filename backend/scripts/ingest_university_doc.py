"""
Ingest a university FAQ DOCX into the RAG knowledge base.

Usage:
    # Drop your DOCX into data/ then run from the backend/ directory:
    .\\venv\\Scripts\\activate
    python scripts/ingest_university_doc.py --file ../data/your_university_doc.docx

    # Optional flags:
    --department "Student Services"   (defaults to section name)
    --dry-run                         (parse only, no DB/Chroma writes)
    --verbose                         (show each parsed Q&A entry)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend root is on sys.path when run directly
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from scripts.parse_university_docx import ParsedEntry, parse_university_docx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── ChromaDB metadata key for page URL ────────────────────────────────────────
CHROMA_PAGE_URL_KEY = "page_url"
CHROMA_SECTION_KEY = "section"
CHROMA_QUESTION_KEY = "question"


async def _ingest_entries(
    entries: list[ParsedEntry],
    department_override: str | None,
) -> None:
    """Embed and store parsed entries in ChromaDB + PostgreSQL."""
    import chromadb

    from app.config import settings
    from app.db.session import async_session_factory
    from app.models.document import Document, DocumentVersion
    from app.providers.embedding_ollama import OllamaEmbeddingProvider
    from app.services.rag_service import COLLECTION_NAME

    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )

    chroma_client = chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
    )
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Group entries by section so each section becomes one Document record
    sections: dict[str, list[ParsedEntry]] = {}
    for entry in entries:
        sections.setdefault(entry.section, []).append(entry)

    total_chunks = 0

    async with async_session_factory() as db:
        for section_name, section_entries in sections.items():
            department = department_override or section_name
            title = f"University FAQ — {section_name}"
            page_url = section_entries[0].page_url  # representative URL for the section

            logger.info(
                "Section [%s]: %d Q&A pairs → creating document record",
                section_name, len(section_entries),
            )

            # Create DB document record
            doc = Document(
                title=title,
                document_type="faq",
                department=department,
                status="processing",
            )
            db.add(doc)
            await db.flush()

            doc_version = DocumentVersion(
                document_id=doc.id,
                version=1,
                checksum=str(uuid.uuid4()),  # content hash not critical for FAQ entries
                effective_date=datetime.now(timezone.utc),
                storage_location="inline:docx",
            )
            db.add(doc_version)
            await db.flush()

            try:
                chunk_texts = [e.chunk_text for e in section_entries]
                embeddings = await embedding_provider.embed(chunk_texts)

                chunk_ids = [f"{doc.id}_{i}" for i in range(len(section_entries))]
                metadatas = [
                    {
                        "document_id": str(doc.id),
                        "version_id": str(doc_version.id),
                        "title": title,
                        "document_type": "faq",
                        "department": department,
                        CHROMA_SECTION_KEY: entry.section,
                        CHROMA_QUESTION_KEY: entry.question[:200],
                        CHROMA_PAGE_URL_KEY: entry.page_url or "",
                        "page": 1,
                        "effective_date": "",
                        "publication_date": "",
                    }
                    for entry in section_entries
                ]

                collection.add(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    documents=chunk_texts,
                    metadatas=metadatas,
                )

                doc_version.chunk_count = len(section_entries)
                doc_version.indexed_at = datetime.now(timezone.utc)
                doc_version.active = True
                doc.status = "active"

                await db.commit()
                total_chunks += len(section_entries)
                logger.info(
                    "  [OK] doc_id=%s  chunks=%d  url=%s",
                    doc.id, len(section_entries), page_url or "(none)",
                )

            except Exception as exc:
                logger.error("Failed to ingest section [%s]: %s", section_name, exc, exc_info=True)
                doc.status = "error"
                doc_version.error_message = str(exc)
                await db.commit()
                raise

    await embedding_provider.close()
    logger.info("Done. Total chunks indexed: %d", total_chunks)


def _print_summary(entries: list[ParsedEntry]) -> None:
    from collections import Counter
    section_counts = Counter(e.section for e in entries)
    answered = len(entries)
    print(f"\n{'='*60}")
    print(f"  Parsed {answered} answered Q&A entries")
    print(f"{'='*60}")
    for section, count in section_counts.items():
        print(f"  {section:<40} {count:>4} entries")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a university FAQ DOCX into the knowledge base."
    )
    parser.add_argument(
        "--file", required=True,
        help="Path to the university DOCX file (relative to project root or absolute).",
    )
    parser.add_argument(
        "--department", default=None,
        help="Override department name for all entries (default: section name).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse only — do not write to DB or ChromaDB.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print each parsed Q&A entry.",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = (_BACKEND_DIR.parent / file_path).resolve()

    if not file_path.exists():
        print(f"Error: file not found: {file_path}")
        sys.exit(1)

    print(f"\nParsing: {file_path}")
    entries = parse_university_docx(file_path)

    if not entries:
        print("No answerable Q&A entries found. Check your document format.")
        sys.exit(1)

    _print_summary(entries)

    if args.verbose:
        for i, e in enumerate(entries, 1):
            print(f"[{i}] [{e.section}]")
            print(f"     Q: {e.question}")
            print(f"     A: {e.answer[:120]}{'...' if len(e.answer) > 120 else ''}")
            print(f"     URL: {e.page_url or '(none)'}")
            print()

    if args.dry_run:
        print("[dry-run] Skipping DB/ChromaDB ingestion.")
        return

    print("Ingesting into knowledge base...")
    asyncio.run(_ingest_entries(entries, args.department))
    print("\n[OK] University data ingested successfully!")


if __name__ == "__main__":
    main()
