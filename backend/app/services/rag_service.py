"""RAG service — retrieves relevant chunks and generates grounded answers."""

import logging

import chromadb

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.embedding_base import EmbeddingProvider
from app.services.exemplar_service import ExemplarService
from app.services.guardrail_service import (
    sanitize_hallucinated_urls,
    verify_numeric_faithfulness,
    verify_retrieval_confidence,
    verify_url_faithfulness,
)
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
        from app.db.chroma import get_chroma_client

        self.llm = llm_provider
        self.embeddings = embedding_provider
        self.exemplars = ExemplarService(embedding_provider)
        self._chroma_client = get_chroma_client()

    def _get_collection(self) -> chromadb.Collection:
        """Get or create the university documents collection."""
        return self._chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    async def retrieve(
        self, query: str, top_k: int = 4
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

    async def prepare_rag_request(
        self,
        question: str,
        conversation_context: str,
        retrieved_chunks: list[dict],
    ) -> tuple[list[dict[str, str]], list[dict], str]:
        """Format evidence and prompt for the LLM. Returns (messages, sources, evidence_text)."""
        if not retrieved_chunks:
            return [], [], ""

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

        matching_exemplar = await self.exemplars.find_matching_exemplar(question)
        if matching_exemplar:
            exemplar_block = (
                "Verified Exemplar (High-Quality Prior Answer for Reference):\n"
                f"Similar Question: {matching_exemplar['question']}\n"
                f"Approved Answer: {matching_exemplar['answer']}\n"
                "Note: Use the verified exemplar above as a structural and factual guide to ensure consistency.\n"
            )
        else:
            exemplar_block = ""

        rag_prompt = render_prompt(
            "rag",
            question=question,
            conversation=conversation_context,
            evidence=evidence_text,
            exemplar=exemplar_block,
        )

        messages = [
            {"role": "system", "content": rag_prompt},
            {"role": "user", "content": question},
        ]
        return messages, sources, evidence_text

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

        messages, sources, evidence_text = await self.prepare_rag_request(
            question, conversation_context, retrieved_chunks
        )
        answer = await self.llm.generate(messages, temperature=0.3)

        # Runtime Hallucination Guardrail 1: Verify numeric and percentage claims
        is_faithful, unsupported = verify_numeric_faithfulness(
            answer=answer,
            evidence_text=evidence_text,
            conversation_context=conversation_context,
            question=question,
        )
        if not is_faithful:
            logger.warning(
                "Self-correction triggered: LLM draft contained unverified numbers %s",
                unsupported,
            )
            correction_instruction = (
                f"CORRECTION: Your previous draft stated number(s) or percentage(s) that are NOT present "
                f"in the evidence or conversation: {', '.join(unsupported)}. "
                f"Do NOT invent or assume numbers. Rewrite your response using strictly verified numbers "
                f"from the evidence, or state that the specific detail is not specified in the documents."
            )
            correction_messages = messages + [
                {"role": "assistant", "content": answer},
                {"role": "user", "content": correction_instruction},
            ]
            corrected_answer = await self.llm.generate(correction_messages, temperature=0.1)
            second_check, still_unsupported = verify_numeric_faithfulness(
                corrected_answer, evidence_text, conversation_context, question
            )
            if second_check or len(still_unsupported) < len(unsupported):
                answer = corrected_answer

        # Runtime Hallucination Guardrail 2: Verify URLs & Portal links
        is_url_faithful, unverified_urls = verify_url_faithfulness(answer, evidence_text)
        if not is_url_faithful:
            logger.warning("Sanitizing hallucinated URLs from answer: %s", unverified_urls)
            answer = sanitize_hallucinated_urls(answer, unverified_urls)

        return answer, sources

    async def query(
        self,
        question: str,
        conversation_context: str = "",
        top_k: int = 4,
        search_query: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Full RAG pipeline: retrieve → generate → return answer + sources."""
        retrieval_query = search_query or question
        chunks = await self.retrieve(retrieval_query, top_k=top_k)
        effective_question = question
        clean_q = question.lower().strip(" .!?,")
        if search_query and (
            clean_q in ("yes", "yeah", "yep", "sure", "ok", "tell me more", "more details", "go ahead", "definitely", "yes please", "why not")
            or len(clean_q.split()) <= 2
        ):
            effective_question = f"{question} ({search_query})"
        answer, sources = await self.generate_answer(
            effective_question, conversation_context, chunks
        )
        return answer, sources
