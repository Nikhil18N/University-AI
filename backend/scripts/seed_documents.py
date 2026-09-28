"""Seed script to ingest sample university documents and verify RAG retrieval."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.session import async_session_factory
from app.providers.embedding_ollama import OllamaEmbeddingProvider
from app.providers.ollama import OllamaProvider
from app.services.ingestion_service import IngestionService
from app.services.rag_service import RAGService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_DOCS = [
    {
        "file": "academic_calendar_2026.md",
        "title": "University Academic Calendar 2026",
        "document_type": "calendar",
        "department": "Academic Affairs",
        "effective_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
    },
    {
        "file": "hostel_regulations.md",
        "title": "Campus Hostel Rules and Regulations 2026",
        "document_type": "regulation",
        "department": "Student Welfare",
        "effective_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
    },
    {
        "file": "fee_structure_2026.md",
        "title": "University Fee Structure and Payment Regulations 2026",
        "document_type": "policy",
        "department": "Finance Office",
        "effective_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
    },
]


async def seed_documents():
    """Ingest sample documents and test RAG pipeline."""
    sample_dir = settings.PROJECT_ROOT / "data" / "sample_documents"
    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )
    llm_provider = OllamaProvider(
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )

    ingestion_service = IngestionService(embedding_provider)
    rag_service = RAGService(llm_provider, embedding_provider)

    print("\n--- 1. Ingesting Sample Documents ---")
    async with async_session_factory() as db:
        for doc_info in SAMPLE_DOCS:
            file_path = sample_dir / doc_info["file"]
            if not file_path.exists():
                print(f"Error: {file_path} not found!")
                continue

            file_bytes = file_path.read_bytes()
            print(f"Ingesting {doc_info['title']} ({file_path.name})...")

            doc = await ingestion_service.ingest_document(
                db=db,
                file_bytes=file_bytes,
                filename=file_path.name,
                title=doc_info["title"],
                document_type=doc_info["document_type"],
                department=doc_info["department"],
                effective_date=doc_info["effective_date"],
            )
            await db.commit()
            print(f"  [OK] Indexed document ID: {doc.id}, status: {doc.status}")

    print("\n--- 2. Testing End-to-End RAG Queries ---")
    test_queries = [
        "When is exam registration?",
        "What are the hostel rules?",
        "What is the fee for next semester?",
    ]

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        answer, sources = await rag_service.query(q)
        print("Answer:")
        print(answer.strip())
        print("Sources Cited:")
        for s in sources:
            print(f"  - [{s.get('title')}] (Dept: {s.get('department')}, Page {s.get('page')})")

    await embedding_provider.close()
    await llm_provider.close()
    print("\n[OK] Seeding and RAG verification completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_documents())
