"""RAG service — retrieves relevant chunks and generates grounded answers."""

import logging

import chromadb

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.services.prompt_service import render_prompt

logger = logging.getLogger(__name__)

COLLECTION_NAME = "university_documents"


class RAGService:
    """Handles retrieval-augmented generation for university questions."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
    ):
        self.llm = llm_provider
        self.embeddings = embedding_provider
        self._chroma_client = chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
        )

    def _get_collection(self) -> chromadb.Collection:
        """Get or create the university documents collection."""
        return self._chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    async def retrieve(
        self, query: str, top_k: int = 6
    ) -> list[dict]:
        """Retrieve the most relevant document chunks for a query.

        Returns a list of dicts with keys: content, metadata, distance.
        """
        query_embedding = await self.embeddings.embed_single(query)
        collection = self._get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else None
                chunks.append({
                    "content": doc,
                    "metadata": metadata,
                    "distance": distance,
                })

        chunks = [
            chunk
            for chunk in chunks
            if chunk["distance"] is None
            or chunk["distance"] <= settings.RAG_MAX_DISTANCE
        ]

        logger.info(
            "Retrieved %d chunks for query: %s",
            len(chunks),
            query[:100],
        )
        return chunks

    async def generate_answer(
        self,
        question: str,
        conversation_context: str,
        retrieved_chunks: list[dict],
    ) -> tuple[str, list[dict]]:
        """Generate a grounded answer using retrieved evidence.

        Returns (answer_text, source_references).
        """
        if not retrieved_chunks:
            return (
                "I couldn't find relevant information in the university documents "
                "to answer that question. You may want to check with the university "
                "office directly.",
                [],
            )

        # Format evidence for the prompt
        evidence_parts = []
        sources = []
        seen_docs = set()

        for i, chunk in enumerate(retrieved_chunks, 1):
            meta = chunk["metadata"]
            section = meta.get("section", "")
            page_url = meta.get("page_url", "")
            label = section or meta.get("title", "Unknown")
            evidence_parts.append(
                f"[Source {i}] {label}"
                + (f" — {page_url}" if page_url else "")
                + f"\n{chunk['content']}"
            )

            # Deduplicate source references
            doc_key = (meta.get("document_id", ""), meta.get("section", meta.get("page", "")))
            if doc_key not in seen_docs:
                seen_docs.add(doc_key)
                sources.append({
                    "document_id": meta.get("document_id", ""),
                    "title": meta.get("title", "Unknown"),
                    "section": meta.get("section", ""),
                    "page": meta.get("page"),
                    "page_url": meta.get("page_url", ""),
                    "department": meta.get("department"),
                    "effective_date": meta.get("effective_date"),
                })

        evidence_text = "\n\n".join(evidence_parts)

        # Build the RAG prompt from the versioned template
        rag_prompt = render_prompt(
            "rag",
            question=question,
            conversation=conversation_context,
            evidence=evidence_text,
        )

        # Call the LLM
        messages = [
            {"role": "system", "content": rag_prompt},
            {"role": "user", "content": question},
        ]
        answer = await self.llm.generate(messages, temperature=0.3)

        return answer, sources

    async def query(
        self,
        question: str,
        conversation_context: str = "",
        top_k: int = 6,
    ) -> tuple[str, list[dict]]:
        """Full RAG pipeline: retrieve → generate → return answer + sources."""
        chunks = await self.retrieve(question, top_k=top_k)
        answer, sources = await self.generate_answer(
            question, conversation_context, chunks
        )
        return answer, sources
