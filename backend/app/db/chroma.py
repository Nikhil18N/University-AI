"""ChromaDB client provider supporting both HTTP and persistent storage."""

from pathlib import Path

import chromadb
from app.config import settings

_client = None


def get_chroma_client():
    """Return persistent or HTTP ChromaDB client depending on configuration."""
    global _client
    if _client is not None:
        return _client
    if settings.CHROMA_PERSIST_DIR:
        persist_path = Path(settings.CHROMA_PERSIST_DIR)
        if not persist_path.is_absolute():
            # Check current working directory first
            if not persist_path.exists():
                backend_dir = Path(__file__).resolve().parent.parent.parent
                candidates = [
                    backend_dir / persist_path,
                    backend_dir.parent / persist_path,
                    settings.PROJECT_ROOT / persist_path,
                    settings.PROJECT_ROOT / "backend" / persist_path,
                ]
                for cand in candidates:
                    if cand.exists():
                        persist_path = cand
                        break
        _client = chromadb.PersistentClient(path=str(persist_path))
    else:
        _client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
    return _client
