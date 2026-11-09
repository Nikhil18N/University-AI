#!/usr/bin/env python3
"""Shadow re-embedding script for text-embedding-004 migration (T11).

Embeds 162 university chunks into isolated shadow collections:
- sru_facts_v4 (768 dimensions)
- sru_highlights_v4 (768 dimensions)

Preserves existing 3072-dim production collections completely untouched.
Defaults to --dry-run for safety. Pass --execute to run live API calls.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.chroma import get_chroma_client
from app.providers.embedding_gemini import GeminiEmbeddingProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SHADOW_FACTS_COLLECTION = "sru_facts_v4"
SHADOW_HIGHLIGHTS_COLLECTION = "sru_highlights_v4"
TARGET_MODEL = "text-embedding-004"


async def shadow_reembed(execute: bool = False, batch_size: int = 10) -> dict[str, int]:
    client = get_chroma_client()
    source_facts = client.get_collection(getattr(settings, "CHROMA_FACTS_COLLECTION", "sru_facts"))
    source_high = client.get_collection(getattr(settings, "CHROMA_HIGHLIGHTS_COLLECTION", "sru_highlights"))

    facts_count = source_facts.count()
    high_count = source_high.count()
    total_chunks = facts_count + high_count

    logger.info("Found %d facts chunks and %d highlights chunks to shadow-embed (Total: %d)", facts_count, high_count, total_chunks)

    if not execute:
        logger.info(
            "DRY-RUN COMPLETE: Target model='%s'. "
            "Estimated tokens: ~%d (~$0.001). Pass --execute to perform live shadow embedding.",
            TARGET_MODEL,
            total_chunks * 300,
        )
        return {"facts": facts_count, "highlights": high_count}

    embedder = GeminiEmbeddingProvider(model=TARGET_MODEL)

    async def _process_collection(source_coll, target_name: str, scope: str):
        target_coll = client.get_or_create_collection(
            name=target_name,
            metadata={"hnsw:space": "cosine", "model": TARGET_MODEL, "dimensions": 768},
        )
        # Clear existing shadow data if rerun
        if target_coll.count() > 0:
            target_coll.delete(ids=target_coll.get()["ids"])

        data = source_coll.get(include=["documents", "metadatas"])
        docs = data["documents"]
        metas = data["metadatas"]
        ids = data["ids"]

        logger.info("Embedding %d chunks into shadow collection '%s'...", len(docs), target_name)

        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_metas = metas[i : i + batch_size]

            # Generate 768-dim embeddings via text-embedding-004
            embs = await embedder.embed(batch_docs)

            # Ensure scope tag is present in metadata
            for m in batch_metas:
                m["scope"] = scope
                m["embedding_model"] = TARGET_MODEL

            target_coll.add(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metas,
                embeddings=embs,
            )
            await asyncio.sleep(0.5)  # Pace requests smoothly

        logger.info("Shadow collection '%s' populated successfully with %d chunks.", target_name, target_coll.count())
        return target_coll.count()

    facts_shadow_count = await _process_collection(source_facts, SHADOW_FACTS_COLLECTION, "facts")
    high_shadow_count = await _process_collection(source_high, SHADOW_HIGHLIGHTS_COLLECTION, "highlights")

    await embedder.close()
    return {"facts": facts_shadow_count, "highlights": high_shadow_count}


async def main():
    parser = argparse.ArgumentParser(description="Shadow re-embed ChromaDB chunks into text-embedding-004 collections.")
    parser.add_argument("--execute", action="store_true", default=False, help="Perform live API embedding calls")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for embedding requests")
    args = parser.parse_args()

    await shadow_reembed(execute=args.execute, batch_size=args.batch_size)


if __name__ == "__main__":
    asyncio.run(main())

