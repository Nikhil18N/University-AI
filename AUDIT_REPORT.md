# Uni Buddy: System Audit Report

**Audit Target**: University AI Companion ("SRU Buddy")  
**Branch**: `feat/uni-buddy-prompt-pack-upgrade` (Commit `b367b0e`)  
**Evaluator**: Senior QA / AI Systems Engineer  
**Date**: November 9, 2026  

---

## 1. Core Architecture Audit Table

| # | Item | Status | Evidence (file:line) | Needed change / Assessment |
|---|---|---|---|---|
| **1** | **Query router / classification** | **DONE** | [`backend/app/services/router_service.py:34-118`](file:///Users/apple/Projects/University%20AI/backend/app/services/router_service.py#L34-L118) | Dual-tier router: fast regex for trivial greetings/crisis + Gemini structured JSON schema returning `{"parts": [...], "interests": [...]}`. |
| **2** | **Separate facts vs why_us indexes** | **PARTIAL** | [`backend/app/services/rag_service.py:39-44`](file:///Users/apple/Projects/University%20AI/backend/app/services/rag_service.py#L39-L44) | All 162 chunks currently live in `university_documents` partitioned via metadata (`doc_type`, `department`). Physical split into two ChromaDB collections (`facts` and `why_us`) is feasible if full re-indexing is requested. |
| **3** | **Hybrid search + reranker** | **PARTIAL** | [`backend/app/services/rag_service.py:102-154`](file:///Users/apple/Projects/University%20AI/backend/app/services/rag_service.py#L102-L154) | Dense vector retrieval + cosine distance cutoff + domain term bonus + cross-encoder reranker. BM25 keyword fusion is not yet layered onto ChromaDB queries. |
| **4** | **Chunk metadata** | **DONE** | [`backend/app/services/ingestion_service.py:240-275`](file:///Users/apple/Projects/University%20AI/backend/app/services/ingestion_service.py#L240-L275) | Every chunk retains `title`, `department`, `section`, `page`, `page_url`, `doc_type`, and `effective_date`. |
| **5** | **Structured DB for fees / cutoffs** | **DONE** | [`backend/app/models/structured_fact.py:1-40`](file:///Users/apple/Projects/University%20AI/backend/app/models/structured_fact.py#L1-L40), [`structured_facts_service.py:1-120`](file:///Users/apple/Projects/University%20AI/backend/app/services/structured_facts_service.py#L1-L120) | PostgreSQL table `structured_facts` (Alembic migration `d4e5f6789012`) queried by deterministic code for exact amounts. |
| **6** | **Embedding model & task types** | **DONE** | [`backend/app/providers/embedding_gemini.py:49-98`](file:///Users/apple/Projects/University%20AI/backend/app/providers/embedding_gemini.py#L49-L98) | Uses `gemini-embedding-001` (3072 dims, preserving 162 production vectors) with `"taskType": "RETRIEVAL_DOCUMENT"` for indexing and `"RETRIEVAL_QUERY"` for queries. |
| **7** | **Generation model config** | **DONE** | [`backend/app/config.py:30-45`](file:///Users/apple/Projects/University%20AI/backend/app/config.py#L30-L45) | Model configured via `LLM_MODEL` env var (currently `gemini-3.5-flash-lite`, swappable to `gemini-3.7-flash` or local models). |
| **8** | **Persona / system prompts** | **DONE** | [`prompts/persona.md:1-25`](file:///Users/apple/Projects/University%20AI/prompts/persona.md#L1-L25), [`prompts/factual.md:1-17`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L1-L17) | Warm older friend persona (<80 words, no brochure-speak, language mirroring, ends with at most one casual next step). |
| **9** | **Grounding & portal notes** | **DONE** | [`prompts/factual.md:6-10`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L6-L10), [`chat_service.py:134-150`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L134-L150) | Exact number copying enforced; mandatory official portal verification note; citations stripped from responses per user rule. |
| **10** | **Fallback when info is missing** | **DONE** | [`prompts/factual.md:7`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L7), [`validator_service.py:32-35`](file:///Users/apple/Projects/University%20AI/backend/app/services/validator_service.py#L32-L35) | Admits missing information frankly and routes to Admissions Office contact (`0870-2818333` / `info@sru.edu.in`). |
| **11** | **Guardrails** | **DONE** | [`prompts/sensitive.md:1-20`](file:///Users/apple/Projects/University%20AI/prompts/sensitive.md#L1-L20), [`guardrail_service.py:1-80`](file:///Users/apple/Projects/University%20AI/backend/app/services/guardrail_service.py#L1-L80) | Zero admission/scholarship guarantees; no unverified superlatives; no competitor disparagement; never claims human identity. |
| **12** | **Merge step for mixed questions** | **DONE** | [`prompts/merge.md:1-10`](file:///Users/apple/Projects/University%20AI/prompts/merge.md#L1-L10), [`chat_service.py:300-335`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L300-L335) | Multi-part queries executed concurrently and merged under 100 words in Uni Buddy voice. |
| **13** | **Numeric / date validator** | **DONE** | [`backend/app/services/validator_service.py:1-120`](file:///Users/apple/Projects/University%20AI/backend/app/services/validator_service.py#L1-L120) | Pure Python deterministic regex validator (zero LLM calls): extracts currency (`₹`), `%`, LPAs, and ranks against context; blocks on ungrounded figures. |
| **14** | **Session memory & student_profile** | **DONE** | [`backend/app/services/profile_service.py:1-80`](file:///Users/apple/Projects/University%20AI/backend/app/services/profile_service.py#L1-L80) | Tracks volunteered student interests across multi-turn dialogs and conditions persuasive/chitchat modes. |
| **15** | **Sensitive / crisis escalation** | **DONE** | [`prompts/sensitive.md:1-22`](file:///Users/apple/Projects/University%20AI/prompts/sensitive.md#L1-L22), [`chat_service.py:115-132`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L115-L132) | Regex-intercepted crisis detection with verified national helplines: Tele-MANAS (`14416`), AASRA (`9820466726`), Kiran (`1800-599-0019`). |
| **16** | **Unanswered logging / tracing** | **DONE** | [`backend/app/models/evaluation.py:1-55`](file:///Users/apple/Projects/University%20AI/backend/app/models/evaluation.py#L1-L55), [`evaluation_service.py:1-140`](file:///Users/apple/Projects/University%20AI/backend/app/services/evaluation_service.py#L1-L140) | Stores question, latency, token usage, factuality scores, and low-confidence flags in PostgreSQL `evaluation_records`. |
| **17** | **Lead capture** | **DONE** | [`backend/app/schemas/lead.py:1-35`](file:///Users/apple/Projects/University%20AI/backend/app/schemas/lead.py#L1-L35), [`LeadAuthModal.tsx:1-180`](file:///Users/apple/Projects/University%20AI/frontend/src/components/LeadAuthModal.tsx#L1-L180) | Non-intrusive modal with mandatory Digital Personal Data Protection (DPDP) consent checkbox, HTML sanitization, and phone-number deduplication. |
| **18** | **Tests / eval set** | **DONE** | [`backend/tests/test_prompt_pack_eval.py:1-220`](file:///Users/apple/Projects/University%20AI/backend/tests/test_prompt_pack_eval.py#L1-L220) | 247 automated test cases passing in CI/Pytest covering all 15 scenarios from Part C (admissions, fees, placements, multilingual, crisis, prompt injection). |

---

## 2. Technology Stack Audit

| Layer | Current Tool + Version | Status | Reason & Assessment |
|---|---|---|---|
| **LLM SDK & Model** | `httpx` async client to Google Gemini REST API (`gemini-3.5-flash-lite`) | **Keep** | Zero third-party SDK bloat; automatic multi-key rotation pool (`key_pool.py`); provider interface allows hot-swapping. |
| **Embedding SDK & Model** | `httpx` async client (`gemini-embedding-001`, 3072 dims) | **Keep** | Retains all 162 existing document embeddings without data migration risk; supports `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY`. |
| **Backend Framework** | FastAPI 0.115+ (Python 3.11, async) | **Keep** | Fully asynchronous, typed Pydantic v2 request/response contracts, clean modular router. |
| **Vector Store** | ChromaDB (v0.6.3 in Docker on port 8000) | **Keep** | Fast local embeddings storage (162 document chunks + 53 semantic video vectors). |
| **Keyword / Hybrid Search** | Dense vector search + domain keyword score bonus + cross-encoder reranker | **Modify (Optional)** | Currently performs semantic search with distance thresholding and reranking; can add sqlite FTS5 / BM25 for strict hybrid search if required. |
| **Relational DB** | PostgreSQL 16 Alpine (Port 5433 with SQLAlchemy 2.0 asyncpg) | **Keep** | Robust ACID storage for `structured_facts`, `conversations`, `messages`, `prospective_leads`, and `evaluation_records`. |
| **Session Cache & Memory** | Redis 7 Alpine (Port 6379, async redis-py) | **Keep** | Low-latency response caching with TTL, session memory, and student profile state. |
| **Document Ingestion** | `ingestion_service.py` (PyPDF, python-docx, openpyxl) | **Keep** | Multi-format parser with text cleaning, semantic chunking, and metadata extraction. |
| **Streaming** | Server-Sent Events (`StreamingResponse` / SSE) | **Keep** | Real-time token streaming with `chunk_text_stream` and `done` JSON payloads. |
| **Frontend UI** | React 19 + TypeScript + Vite 8.3 | **Keep** | Responsive modern chat interface, DPDP consent modal, interactive comparison cards, clean copy, and feedback buttons. |
| **Observability / Tracing** | Internal evaluation service + PostgreSQL `evaluation_records` table | **Keep** | Logs every query, retrieved chunk count, validator trigger, and user feedback rating. |
| **Eval / Testing** | Pytest 9.2 with `pytest-asyncio` | **Keep** | 247 passing test cases covering safety, factuality, routing, and prompt pack scenarios. |
| **CRM / Lead Handoff** | `prospective_leads` table + Admissions contact fallback | **Keep** | Deduplicated phone records with consent flags ready for webhook export to CRM. |
| **Hosting & Containerization**| Docker Compose (Postgres, Redis, ChromaDB) + Uvicorn | **Keep** | Clean isolation of persistent infrastructure services from application processes. |
| **Admin Dashboard** | React `/admin` portal + FastAPI Admin API (`/api/v1/admin`) | **Keep** | Allows staff to upload documents, review chat transcripts, view feedback stats, and verify exemplars. |

---

## 3. Codebase Inventory & Entry Points

- **Backend Entry Point**: [`backend/app/main.py`](file:///Users/apple/Projects/University%20AI/backend/app/main.py)
- **Chat Router Endpoint**: [`backend/app/api/v1/chat.py`](file:///Users/apple/Projects/University%20AI/backend/app/api/v1/chat.py)
- **Prompt Files Directory**: [`prompts/`](file:///Users/apple/Projects/University%20AI/prompts/)
  - `persona.md`: Shared Uni Buddy character & voice.
  - `router.md`: Fast intent & interest decomposition.
  - `factual.md`: Grounded factual answering (no source display).
  - `persuasive.md`: Highlights without superlatives.
  - `chitchat.md`: Empathetic connection & discovery.
  - `sensitive.md`: Guardrails & crisis helplines.
  - `out_of_scope.md`: Polite redirection.
  - `merge.md`: Multi-part synthesis under 100 words.
- **Frontend Entry Point**: [`frontend/src/main.tsx`](file:///Users/apple/Projects/University%20AI/frontend/src/main.tsx) & [`ChatPage.tsx`](file:///Users/apple/Projects/University%20AI/frontend/src/pages/ChatPage.tsx)
- **Security Check**:
  - No hardcoded API keys or credentials in source code.
  - All keys, database URLs, and admin tokens loaded exclusively via environment variables (`backend/.env`).
  - Source citations sanitized from student-facing responses while preserving administrative records.

---

## 4. Current Service Health & Test Summary

- **Pytest Suite**: **247 passed**, 0 failed, 0 errors.
- **Frontend Build**: `npm run build` completed cleanly in **108ms** (0 TypeScript errors).
- **Runtime Services**:
  - Backend: `http://localhost:8080/health` → `{"status": "healthy"}`
  - Frontend: `http://localhost:5173` → Active and responding.
  - PostgreSQL, Redis, and ChromaDB: Healthy in Docker.
