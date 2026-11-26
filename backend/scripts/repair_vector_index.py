"""Find (and with --fix, restore) knowledge chunks that have no vector in the Chroma index (v4.17.1).

A chunk whose metadata and text are in the index but whose vector is missing can never be returned by the vector
search ("Error finding id" in the logs, and the agent falls back to keyword search, which does not cover the FAQ).
This happened to every University FAQ chunk in the index committed with the Phases 1-4 change.

Usage (from backend/):
    python scripts/repair_vector_index.py            # report only
    python scripts/repair_vector_index.py --fix      # re-embed the missing chunks and write their vectors back
    python scripts/repair_vector_index.py --rebuild-to ../chroma_rebuilt
        # copy every collection (ids, texts, metadata, vectors, settings) into a NEW directory, so the vector index
        # and its metadata are consistent again; then replace chroma_data with it (keep the old one as a backup)

--fix re-embeds each chunk's own stored text with the configured embedding provider and upserts it under the SAME id,
text and metadata. Nothing is deleted. It refuses to write vectors of a different size from the ones already stored.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _has_vector(coll, doc_id: str) -> bool:
    try:
        got = coll.get(ids=[doc_id], include=["embeddings"])["embeddings"]
        return got is not None and len(got) > 0 and len(got[0]) > 0
    except Exception:
        return False


def scan(coll) -> tuple[list[tuple[str, dict, str]], int, int | None]:
    """(chunks without a vector, total chunks, size of the stored vectors)."""
    everything = coll.get(include=["metadatas", "documents"])
    missing, dims = [], None
    for doc_id, meta, text in zip(everything["ids"], everything["metadatas"], everything["documents"]):
        if _has_vector(coll, doc_id):
            if dims is None:
                dims = len(coll.get(ids=[doc_id], include=["embeddings"])["embeddings"][0])
        else:
            missing.append((doc_id, meta or {}, text or ""))
    return missing, len(everything["ids"]), dims


def report(label: str, missing, total: int) -> None:
    print(f"{label}: {total} chunks, {total - len(missing)} with a vector, {len(missing)} without")
    for title, n in collections.Counter(m.get("title", "?") for _, m, _ in missing).most_common():
        print(f"   {n:4d}  {title}")


async def fix(coll, missing, dims: int | None, batch: int = 20) -> int:
    from app.api.v1.deps import get_embedding_provider

    provider = get_embedding_provider()
    written = 0
    for start in range(0, len(missing), batch):
        part = [m for m in missing[start:start + batch] if m[2].strip()]
        if not part:
            continue
        for attempt in range(4):
            try:
                vectors = await provider.embed([text for _, _, text in part])
                break
            except Exception as exc:  # rate limit or a network error: wait and try again
                if attempt == 3:
                    raise
                wait = 20 * (attempt + 1)
                print(f"   embedding failed ({type(exc).__name__}); retrying in {wait}s")
                await asyncio.sleep(wait)
        if dims is not None and any(len(v) != dims for v in vectors):
            raise SystemExit(f"Refusing to write: new vectors have {len(vectors[0])} dimensions, the index has {dims}.")
        coll.upsert(ids=[i for i, _, _ in part], embeddings=vectors,
                    documents=[t for _, _, t in part], metadatas=[m for _, m, _ in part])
        written += len(part)
        print(f"   restored {written}/{len(missing)}")
    return written


def rebuild(src_client, out_dir: str) -> None:
    """Copy every collection into a fresh Chroma directory. A chunk without a vector is reported and not copied."""
    import chromadb

    dst = chromadb.PersistentClient(path=out_dir)
    for col in src_client.list_collections():
        name = getattr(col, "name", col)
        src = src_client.get_collection(name)
        data = src.get(include=["embeddings", "documents", "metadatas"])
        kwargs = {"name": name, "metadata": src.metadata or None, "embedding_function": None}
        config = getattr(src, "configuration_json", None) or getattr(src, "configuration", None)
        try:
            new = dst.create_collection(configuration=config, **kwargs) if config else dst.create_collection(**kwargs)
        except Exception:
            new = dst.create_collection(**kwargs)
        rows = [(i, e, d, m) for i, e, d, m in zip(data["ids"], data["embeddings"], data["documents"],
                                                    data["metadatas"]) if e is not None and len(e)]
        for start in range(0, len(rows), 100):
            part = rows[start:start + 100]
            new.add(ids=[r[0] for r in part], embeddings=[list(r[1]) for r in part],
                    documents=[r[2] for r in part], metadatas=[r[3] or None for r in part])
        print(f"   {name}: copied {new.count()} of {len(data['ids'])} (space: {(src.metadata or {}).get('hnsw:space', 'default')})")


async def main() -> int:
    from app.config import settings

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="re-embed and write back the missing vectors")
    parser.add_argument("--path", default=None, help="Chroma directory (default: the app's CHROMA_PERSIST_DIR)")
    parser.add_argument("--collection", default=None, help="collection name (default: the app's collection)")
    parser.add_argument("--rebuild-to", default=None, help="copy all collections into this NEW directory")
    args = parser.parse_args()

    import chromadb

    path = args.path or getattr(settings, "CHROMA_PERSIST_DIR", None) or "chroma_data"
    name = args.collection or getattr(settings, "CHROMA_COLLECTION_NAME", None) or "university_documents"
    client = chromadb.PersistentClient(path=str(path))
    if args.rebuild_to:
        if Path(args.rebuild_to).exists() and any(Path(args.rebuild_to).iterdir()):
            raise SystemExit(f"{args.rebuild_to} is not empty; give a new directory.")
        rebuild(client, args.rebuild_to)
        return 0
    coll = client.get_collection(name)
    missing, total, dims = scan(coll)
    report(f"{name} ({path})", missing, total)
    if not args.fix or not missing:
        return 0 if not missing else 1
    await fix(coll, missing, dims)
    still, total, _ = scan(coll)
    report("after the repair", still, total)
    return 0 if not still else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
