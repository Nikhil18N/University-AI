"""Document ingestion service — processes files into searchable chunks."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentVersion
from app.providers.embedding_base import EmbeddingProvider
from app.services.rag_service import COLLECTION_NAME

logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}

# Chunking configuration
CHUNK_SIZE = 500        # target words per chunk
CHUNK_OVERLAP = 50      # overlap words between chunks


def _compute_checksum(file_bytes: bytes) -> str:
    """Compute SHA-256 checksum of file content."""
    return hashlib.sha256(file_bytes).hexdigest()


def _extract_text_from_pdf(file_path: Path) -> list[dict]:
    """Extract text from a PDF, returning a list of {page, text} dicts."""
    import pymupdf

    pages = []
    doc = pymupdf.open(str(file_path))
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            pages.append({"page": page_num + 1, "text": text.strip()})
    doc.close()
    return pages


def _extract_text_from_txt(file_path: Path) -> list[dict]:
    """Extract text from a plain text or markdown file."""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    
    metadata = {}
    if file_path.suffix.lower() == ".md" and text.startswith("---"):
        try:
            import yaml
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                if isinstance(frontmatter, dict):
                    metadata = frontmatter
                text = parts[2].strip()
        except Exception as e:
            logger.warning("Failed to parse YAML frontmatter: %s", e)
            
    return [{"page": 1, "text": text.strip(), "okf_metadata": metadata}]


def _extract_text_from_docx(file_path: Path) -> list[dict]:
    """Extract text from a DOCX file."""
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(str(file_path))
        full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return [{"page": 1, "text": full_text}]
    except ImportError:
        logger.warning("python-docx not installed, falling back to plain text")
        return _extract_text_from_txt(file_path)


def _extract_text(file_path: Path) -> list[dict]:
    """Extract text based on file extension."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif ext in (".txt", ".md"):
        return _extract_text_from_txt(file_path)
    elif ext == ".docx":
        return _extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-based chunks.

    Tries to break at paragraph boundaries when possible.
    """
    if not text.strip():
        return []

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk: list[str] = []
    current_word_count = 0

    for para in paragraphs:
        para_words = para.split()
        para_word_count = len(para_words)

        # If adding this paragraph exceeds chunk_size, finalize current chunk
        if current_word_count + para_word_count > chunk_size and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Overlap: keep last part of current chunk
            overlap_text = " ".join(chunk_text.split()[-overlap:])
            current_chunk = [overlap_text, para]
            current_word_count = overlap + para_word_count
        else:
            current_chunk.append(para)
            current_word_count += para_word_count

    # Don't forget the last chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


class IngestionService:
    """Processes documents: extract → chunk → embed → store in ChromaDB."""

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embeddings = embedding_provider

    async def ingest_document(
        self,
        db: AsyncSession,
        file_bytes: bytes,
        filename: str,
        title: str,
        document_type: str,
        department: str | None = None,
        effective_date: datetime | None = None,
        publication_date: datetime | None = None,
    ) -> Document:
        """Full ingestion pipeline for a single document.

        Steps per docs/10-document-ingestion.md:
        1. Validate → 2. Checksum → 3. Save file → 4. Extract text →
        5. Chunk → 6. Embed → 7. Store in ChromaDB → 8. Mark active
        """
        import chromadb

        # 1. Validate file type
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        # 2. Compute checksum
        checksum = _compute_checksum(file_bytes)

        # 3. Save file to disk
        upload_dir = settings.UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{file_id}{ext}"
        file_path.write_bytes(file_bytes)

        # Create DB records (status = "processing")
        doc = Document(
            title=title,
            document_type=document_type,
            department=department,
            status="processing",
        )
        db.add(doc)
        await db.flush()

        doc_version = DocumentVersion(
            document_id=doc.id,
            version=1,
            checksum=checksum,
            effective_date=effective_date,
            publication_date=publication_date,
            storage_location=str(file_path),
        )
        db.add(doc_version)
        await db.flush()

        try:
            # 4. Extract text
            pages = _extract_text(file_path)
            if not pages:
                raise ValueError("No text could be extracted from the document")

            # 5. Chunk content
            all_chunks = []
            for page_info in pages:
                page_chunks = _chunk_text(page_info["text"])
                okf = page_info.get("okf_metadata", {})
                
                for chunk in page_chunks:
                    chunk_prefix = ""
                    if okf:
                        parts = []
                        if "title" in okf: parts.append(f"Title: {okf['title']}")
                        if "type" in okf: parts.append(f"Type: {okf['type']}")
                        if "description" in okf: parts.append(f"Description: {okf['description']}")
                        if parts:
                            chunk_prefix = " | ".join(parts) + "\n\n"
                            
                    all_chunks.append({
                        "text": chunk_prefix + chunk,
                        "page": page_info["page"],
                        "okf_metadata": okf,
                    })

            if not all_chunks:
                raise ValueError("Document produced no chunks after processing")

            logger.info(
                "Document %s: extracted %d pages, %d chunks",
                doc.id, len(pages), len(all_chunks),
            )

            # 6. Generate embeddings
            chunk_texts = [c["text"] for c in all_chunks]
            embeddings = await self.embeddings.embed(chunk_texts)

            # 7. Store in ChromaDB
            from app.db.chroma import get_chroma_client

            chroma_client = get_chroma_client()
            collection = chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

            chunk_ids = [f"{doc.id}_{i}" for i in range(len(all_chunks))]
            metadatas = [
                {
                    "document_id": str(doc.id),
                    "version_id": str(doc_version.id),
                    "title": str(chunk["okf_metadata"].get("title", title))[:100],
                    "document_type": str(chunk["okf_metadata"].get("type", document_type))[:100],
                    "department": department or "",
                    "page": chunk["page"],
                    "effective_date": (
                        effective_date.isoformat() if effective_date else ""
                    ),
                    "publication_date": (
                        str(chunk["okf_metadata"].get("timestamp", "")) if chunk["okf_metadata"].get("timestamp")
                        else (publication_date.isoformat() if publication_date else "")
                    ),
                }
                for chunk in all_chunks
            ]

            collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=metadatas,
            )

            # 8. Mark as active
            doc_version.chunk_count = len(all_chunks)
            doc_version.indexed_at = datetime.now(timezone.utc)
            doc_version.active = True
            doc.status = "active"

            logger.info(
                "Successfully ingested document %s: %d chunks indexed",
                doc.id, len(all_chunks),
            )

        except Exception as e:
            logger.error("Ingestion failed for document %s: %s", doc.id, e)
            doc.status = "error"
            doc_version.error_message = str(e)
            raise

        return doc
