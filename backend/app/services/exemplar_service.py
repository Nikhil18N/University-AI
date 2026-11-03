"""Exemplar service — manages verified Q&A pairs for dynamic few-shot learning and self-improvement."""

import logging
from uuid import UUID
import chromadb

from app.config import settings
from app.providers.embedding_base import EmbeddingProvider

logger = logging.getLogger(__name__)

EXEMPLAR_COLLECTION_NAME = "verified_exemplars"


class ExemplarService:
    """Manages storage, retrieval, and pruning of verified high-quality answers."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self.embeddings = embedding_provider
        self._exemplar_count: int = 0
        try:
            from app.db.chroma import get_chroma_client
            self._chroma_client = get_chroma_client()
        except Exception as e:
            logger.warning("Could not connect to ChromaDB for exemplars: %s", e)
            self._chroma_client = None
        self._refresh_exemplar_count()

    def _refresh_exemplar_count(self) -> None:
        """Read the exemplar collection size and cache it; safe to call at startup."""
        try:
            collection = self._get_collection()
            if collection is not None:
                self._exemplar_count = collection.count()
        except Exception as e:  # pragma: no cover
            logger.warning("Could not refresh exemplar count: %s", e)
            self._exemplar_count = 0

    def _get_collection(self) -> chromadb.Collection | None:
        if not self._chroma_client:
            return None
        try:
            return self._chroma_client.get_or_create_collection(
                name=EXEMPLAR_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.warning("Failed to access exemplar collection: %s", e)
            return None

    async def register_exemplar(
        self,
        message_id: UUID,
        question: str,
        answer: str,
    ) -> bool:
        """Register a verified (question, answer) pair into ChromaDB upon positive feedback."""
        if not self.embeddings or not question.strip() or not answer.strip():
            return False

        collection = self._get_collection()
        if not collection:
            return False

        try:
            embedding = await self.embeddings.embed_single(question)
            collection.upsert(
                ids=[str(message_id)],
                embeddings=[embedding],
                documents=[question],
                metadatas=[{
                    "message_id": str(message_id),
                    "question": question[:1000],
                    "answer": answer[:3000],
                }],
            )
            self._exemplar_count += 1
            logger.info("Successfully registered verified exemplar for query: %s", question[:60])
            return True
        except Exception as e:
            logger.warning("Failed to register verified exemplar: %s", e)
            return False

    async def remove_exemplar(self, message_id: UUID) -> bool:
        """Remove a previously stored exemplar if marked negative."""
        collection = self._get_collection()
        if not collection:
            return False

        try:
            collection.delete(ids=[str(message_id)])
            self._exemplar_count = max(0, self._exemplar_count - 1)
            logger.info("Removed exemplar: %s", message_id)
            return True
        except Exception as e:
            logger.warning("Failed to remove exemplar %s: %s", message_id, e)
            return False

    async def find_matching_exemplar(
        self,
        query: str,
        distance_threshold: float = 0.28,
        precomputed_embedding: list[float] | None = None,
    ) -> dict | None:
        """Find a highly similar verified question and return its approved answer.

        Args:
            query: The user's question text.
            distance_threshold: Cosine distance threshold for a match to be accepted.
            precomputed_embedding: Optional pre-computed query embedding. When
                provided the ``embed_single()`` API call is skipped entirely.
        """
        if not self.embeddings or not query.strip():
            return None

        # Fast-path: skip embedding + DB round-trip when collection is empty.
        if self._exemplar_count == 0:
            return None

        collection = self._get_collection()
        if not collection:
            return None

        try:
            if precomputed_embedding is not None:
                query_embedding = precomputed_embedding
            else:
                query_embedding = await self.embeddings.embed_single(query)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=1,
                include=["metadatas", "distances"],
            )

            if (
                results["metadatas"]
                and results["metadatas"][0]
                and results["distances"]
                and results["distances"][0]
            ):
                dist = results["distances"][0][0]
                if dist <= distance_threshold:
                    meta = results["metadatas"][0][0]
                    logger.info(
                        "Found matching verified exemplar (dist=%.3f) for query: %s",
                        dist,
                        query[:60],
                    )
                    return {
                        "question": meta.get("question", ""),
                        "answer": meta.get("answer", ""),
                        "distance": dist,
                    }
        except Exception as e:
            logger.warning("Error querying verified exemplars: %s", e)

        return None
