"""ChromaDB client provider supporting both HTTP and persistent storage."""

import chromadb
from app.config import settings


def get_chroma_client():
    """Return persistent or HTTP ChromaDB client depending on configuration."""
    if settings.CHROMA_PERSIST_DIR:
        return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
    )
