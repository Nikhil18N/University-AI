import json
import logging
import re

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

    async def _rerank_chunks(self, query: str, chunks: list[dict], keep_top: int = 4) -> list[dict]:
        """Rerank retrieved candidate chunks using a lightweight LLM scoring prompt."""
        if len(chunks) <= keep_top:
            return chunks

        try:
            candidates_text = "\n\n".join(
                f"[{i}] Title: {c.get('metadata', {}).get('title', 'Document')}\n{c['content'][:250]}..."
                for i, c in enumerate(chunks, 1)
            )
            prompt = (
                f"You are a relevance scoring engine for SR University.\n"
                f"User Question: {query}\n\n"
                f"Candidate Chunks:\n{candidates_text}\n\n"
                f"Score each candidate chunk from 0 (irrelevant) to 10 (directly answers the question).\n"
                f"Respond with JSON map only: {{\"1\": score, \"2\": score, ...}}"
            )
            res = await self.llm.generate([{"role": "user", "content": prompt}], temperature=0.0)
            clean_res = re.search(r"\{[^{}]*\}", res, re.DOTALL)
            if clean_res:
                scores = json.loads(clean_res.group(0))
                scored_chunks = []
                for i, c in enumerate(chunks, 1):
                    score = float(scores.get(str(i), 5.0))
                    dist = c.get("distance") or 0.5
                    effective_score = score - (dist * 4.0)
                    scored_chunks.append((effective_score, c))
                scored_chunks.sort(key=lambda x: x[0], reverse=True)
                return [c for _, c in scored_chunks[:keep_top]]
        except Exception as e:
            logger.warning("Reranking fallback to distance sorting: %s", e)

        return sorted(chunks, key=lambda c: (c.get("distance") or 1.0))[:keep_top]

    async def retrieve(
        self, query: str, top_k: int | None = None
    ) -> list[dict]:
        """Retrieve the most relevant document chunks for a query.

        Uses vector similarity, verified knowledge boosts, and optional LLM reranking.
        """
        chunks, _ = await self.retrieve_with_embedding(query, top_k=top_k)
        return chunks

    async def retrieve_with_embedding(
        self, query: str, top_k: int | None = None
    ) -> tuple[list[dict], list[float]]:
        """Retrieve chunks and also return the query embedding vector.

        Returns ``(chunks, query_embedding)`` so callers can reuse the
        embedding (e.g. to skip a second ``embed_single()`` call in
        ``prepare_rag_request``).
        """
        if top_k is None:
            top_k = getattr(settings, "RAG_TOP_K", 8)

        query_embedding = await self.embeddings.embed_single(query)
        collection = self._get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        if results.get("documents") and results["documents"][0]:
            raw_metadatas = results.get("metadatas")
            has_metadatas = bool(raw_metadatas and raw_metadatas[0])
            raw_distances = results.get("distances")
            has_distances = bool(raw_distances and raw_distances[0])
            for i, doc in enumerate(results["documents"][0]):
                raw_meta = raw_metadatas[0][i] if (has_metadatas and i < len(raw_metadatas[0])) else {}
                metadata = raw_meta if isinstance(raw_meta, dict) else {}
                distance = raw_distances[0][i] if (has_distances and i < len(raw_distances[0])) else None
                chunks.append({
                    "content": doc,
                    "metadata": metadata,
                    "distance": distance,
                })

        max_dist = getattr(settings, "RAG_MAX_DISTANCE", 0.60)
        chunks = [
            chunk
            for chunk in chunks
            if chunk.get("distance") is None
            or chunk["distance"] <= max_dist
        ]

        # Prioritize verified registry and domain-specific terms
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            title = meta.get("title", "").lower()
            content = chunk.get("content", "").lower()
            bonus = 0.0
            if "verified knowledge registry" in title or "09_verified_sru_facts" in title:
                bonus += 0.06
            if any(term in content for term in ["51 lpa", "50%", "60%", "triple sharing", "curfew", "deepak garg", "varada reddy"]):
                bonus += 0.04
            if chunk.get("distance") is not None and bonus > 0:
                chunk["distance"] = max(0.0, chunk["distance"] - bonus)

        # Sort by distance
        chunks.sort(key=lambda c: (c.get("distance") or 1.0))

        # Rerank if enabled and more than 4 candidates
        if getattr(settings, "RAG_RERANK", True) and len(chunks) > 4:
            chunks = await self._rerank_chunks(query, chunks, keep_top=4)

        logger.info(
            "Retrieved and reranked %d chunks for query: %s",
            len(chunks),
            query[:100],
        )
        return chunks, query_embedding

    async def prepare_rag_request(
        self,
        question: str,
        conversation_context: str,
        retrieved_chunks: list[dict],
        precomputed_embedding: list[float] | None = None,
    ) -> tuple[list[dict[str, str]], list[dict], str]:
        """Format evidence and prompt for the LLM. Returns (messages, sources, evidence_text).

        Args:
            question: The user's question.
            conversation_context: Prior conversation history for context.
            retrieved_chunks: Chunks returned by ``retrieve()`` / ``retrieve_with_embedding()``.
            precomputed_embedding: Optional query embedding already computed
                during retrieval. When provided it is forwarded to
                ``find_matching_exemplar()`` so the embedding API is not called
                a second time.
        """
        if not retrieved_chunks:
            return [], [], ""

        evidence_parts = []
        sources = []
        seen_docs = set()

        for i, chunk in enumerate(retrieved_chunks, 1):
            if not isinstance(chunk, dict):
                continue
            raw_meta = chunk.get("metadata")
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            section = meta.get("section", "")
            page_url = meta.get("page_url", "")
            label = section or meta.get("title", "Unknown")
            chunk_content = chunk.get("content", "")
            evidence_parts.append(
                f"[Source {i}] {label}"
                + (f" — {page_url}" if page_url else "")
                + f"\n{chunk_content}"
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

        matching_exemplar = await self.exemplars.find_matching_exemplar(
            question, precomputed_embedding=precomputed_embedding
        )
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
        precomputed_embedding: list[float] | None = None,
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
            question,
            conversation_context,
            retrieved_chunks,
            precomputed_embedding=precomputed_embedding,
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

        # Clean any stray disclaimer text if generated by the LLM
        if answer:
            answer = re.sub(
                r">\s*⚠️?\s*\*?May contain inaccuracies\.?\s*Verify with official university sources\.?\*?",
                "",
                answer,
                flags=re.IGNORECASE,
            ).strip()

        return answer, sources

    async def query(
        self,
        question: str,
        conversation_context: str = "",
        top_k: int | None = None,
        search_query: str | None = None,
    ) -> tuple[str, list[dict]]:
        """Full RAG pipeline: retrieve → generate → return answer + sources."""
        retrieval_query = search_query or question
        query_embedding = None
        try:
            chunks, query_embedding = await self.retrieve_with_embedding(retrieval_query, top_k=top_k)
            self.last_query_embedding = query_embedding
        except Exception as e:
            logger.error("RAG retrieval failed: %s. Proceeding with fallback.", e)
            chunks = []
            self.last_query_embedding = None
        effective_question = question
        clean_q = question.lower().strip(" .!?,")
        if search_query and (
            clean_q in ("yes", "yeah", "yep", "sure", "ok", "tell me more", "more details", "go ahead", "definitely", "yes please", "why not")
            or len(clean_q.split()) <= 2
        ):
            effective_question = f"{question} ({search_query})"
        answer, sources = await self.generate_answer(
            effective_question,
            conversation_context,
            chunks,
            precomputed_embedding=query_embedding,
        )
        return answer, sources
