#!/usr/bin/env python3
"""Split ChromaDB university_documents into two isolated collections: sru_facts and sru_highlights (T10 Option B).

Copies existing embeddings without re-embedding to preserve zero API cost and 100% vector fidelity.
"""

import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.chroma import get_chroma_client
from app.services.rag_service import COLLECTION_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HIGHLIGHT_TITLES = {
    "University FAQ — Placements",
    "University FAQ — Rankings",
    "University FAQ — Leadership",
    "University FAQ — SRiX",
    "University FAQ — Clubs & Events",
    "University FAQ — Facilities",
    "University FAQ — Labs",
    "University FAQ — Food",
    "University FAQ — Programs",
    "University FAQ — International Programs",
    "SRU Student Handbook — Campus Life, Facilities & Contacts",
}

FACTS_COLLECTION_NAME = "sru_facts"
HIGHLIGHTS_COLLECTION_NAME = "sru_highlights"


def split_collections() -> dict[str, int]:
    client = get_chroma_client()
    source_coll = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    total_count = source_coll.count()
    logger.info("Found %d total chunks in source collection '%s'", total_count, COLLECTION_NAME)

    if total_count == 0:
        logger.warning("Source collection is empty. Nothing to split.")
        return {"facts": 0, "highlights": 0}

    # Fetch all chunks including their existing embeddings
    data = source_coll.get(include=["documents", "metadatas", "embeddings"])
    ids = data["ids"]
    docs = data["documents"]
    metas = data["metadatas"]
    embs = data["embeddings"]

    facts_ids, facts_docs, facts_metas, facts_embs = [], [], [], []
    high_ids, high_docs, high_metas, high_embs = [], [], [], []

    for i in range(len(ids)):
        chunk_id = ids[i]
        doc = docs[i]
        meta = metas[i] if metas is not None and i < len(metas) else {}
        emb = embs[i].tolist() if embs is not None and i < len(embs) else None

        title = meta.get("title", "")
        if title in HIGHLIGHT_TITLES:
            high_ids.append(chunk_id)
            high_docs.append(doc)
            # Add scope tag for additional metadata clarity
            meta_copy = dict(meta)
            meta_copy["scope"] = "highlights"
            high_metas.append(meta_copy)
            high_embs.append(emb)
        else:
            facts_ids.append(chunk_id)
            facts_docs.append(doc)
            meta_copy = dict(meta)
            meta_copy["scope"] = "facts"
            facts_metas.append(meta_copy)
            facts_embs.append(emb)

    logger.info("Categorized %d facts chunks and %d highlights chunks", len(facts_ids), len(high_ids))

    # Initialize sru_facts
    facts_coll = client.get_or_create_collection(
        name=FACTS_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    # Clear existing if any
    existing_facts = facts_coll.count()
    if existing_facts > 0:
        facts_coll.delete(ids=facts_coll.get()["ids"])

    facts_coll.add(
        ids=facts_ids,
        documents=facts_docs,
        metadatas=facts_metas,
        embeddings=facts_embs,
    )
    logger.info("Successfully populated '%s' with %d chunks", FACTS_COLLECTION_NAME, facts_coll.count())

    # Initialize sru_highlights
    high_coll = client.get_or_create_collection(
        name=HIGHLIGHTS_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    existing_high = high_coll.count()
    if existing_high > 0:
        high_coll.delete(ids=high_coll.get()["ids"])

    high_coll.add(
        ids=high_ids,
        documents=high_docs,
        metadatas=high_metas,
        embeddings=high_embs,
    )
    logger.info("Successfully populated '%s' with %d chunks", HIGHLIGHTS_COLLECTION_NAME, high_coll.count())

    return {
        "facts": facts_coll.count(),
        "highlights": high_coll.count(),
    }


if __name__ == "__main__":
    split_collections()
