"""ChromaDB client provider supporting both HTTP and persistent storage."""

from pathlib import Path

import chromadb
from app.config import settings

_client = None


def _find_chroma_persist_dir() -> Path:
    target = settings.CHROMA_PERSIST_DIR or "./chroma_data"
    target_path = Path(target)
    name = target_path.name

    here = Path(__file__).resolve().parent
    app_dir = here.parent
    backend_dir = app_dir.parent
    repo_dir = backend_dir.parent

    candidates = [
        backend_dir / name,
        repo_dir / name,
        repo_dir / "backend" / name,
        Path.cwd() / target_path,
        Path.cwd() / "backend" / target_path,
        settings.PROJECT_ROOT / name,
        settings.PROJECT_ROOT / "backend" / name,
    ]

    for cand in candidates:
        sqlite_file = cand / "chroma.sqlite3"
        if sqlite_file.exists() and sqlite_file.stat().st_size > 1000:
            return cand

    return backend_dir / name if (backend_dir / name).exists() else Path.cwd() / target_path


def get_chroma_client():
    """Return persistent or HTTP ChromaDB client depending on configuration."""
    global _client
    if _client is not None:
        return _client
    if settings.CHROMA_PERSIST_DIR:
        persist_path = _find_chroma_persist_dir()
        _client = chromadb.PersistentClient(path=str(persist_path))
    else:
        _client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )
    return _client
