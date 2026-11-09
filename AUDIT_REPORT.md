# Uni Buddy: System Audit Report

**Audit Target**: University AI Companion ("SRU Buddy")  
**Branch**: `feat/uni-buddy-prompt-pack-upgrade` (Post-Hardening T1–T12 Complete)  
**Evaluator**: Senior QA / AI Systems Engineer  
**Date**: November 10, 2026  
**Verification Script**: `./scripts/run_all_checks.sh` (Exit code: 0)  
**Test Suite Status**: **315 / 315 tests passing** (0 regressions, 0 skips)  

---

## 1. Core Architecture Audit Table

| # | Item | Status | Evidence (file:line) | Hardened Assessment & Changes |
|---|---|---|---|---|
| **1** | **Query router / classification** | **DONE** | [`backend/app/services/router_service.py:34-142`](file:///Users/apple/Projects/University%20AI/backend/app/services/router_service.py#L34-L142) | Dual-tier router: deterministic regex for greetings/crisis (<2ms, 0 LLM calls) + Gemini structured JSON schema returning `{"parts": [...], "interests": [...]}`. Resolves sub-questions per part before response caching. |
| **2** | **Separate facts vs why_us indexes** | **DONE** | [`backend/app/config.py:46-52`](file:///Users/apple/Projects/University%20AI/backend/app/config.py#L46-L52), [`rag_service.py:40-85`](file:///Users/apple/Projects/University%20AI/backend/app/services/rag_service.py#L40-L85) | Dual ChromaDB collections (`sru_facts` with 95 chunks, `sru_highlights` with 67 chunks). Factual pipeline retrieves strictly with `scope="facts"`; persuasive pipeline retrieves strictly with `scope="highlights"`. Zero vector re-embedding cost. |
| **3** | **Hybrid search + reranker** | **DONE** | [`backend/app/services/bm25_service.py:1-120`](file:///Users/apple/Projects/University%20AI/backend/app/services/bm25_service.py#L1-L120), [`rag_service.py:100-195`](file:///Users/apple/Projects/University%20AI/backend/app/services/rag_service.py#L100-L195) | Pure Python Okapi BM25 sparse index combined with ChromaDB dense vector search using Reciprocal Rank Fusion (RRF, $k=60$). Title/keyword boosts loaded from `retrieval_boosts.yaml` with cross-encoder reranking. In-memory BM25 invalidation on index bumps. |
| **4** | **Chunk metadata** | **DONE** | [`backend/app/services/ingestion_service.py:240-275`](file:///Users/apple/Projects/University%20AI/backend/app/services/ingestion_service.py#L240-L275) | Every chunk retains `title`, `department`, `section`, `page`, `page_url`, `doc_type`, and `effective_date`. Preserved across both `sru_facts` and `sru_highlights` collections. |
| **5** | **Structured DB for fees / cutoffs** | **DONE** | [`backend/app/models/structured_fact.py:1-45`](file:///Users/apple/Projects/University%20AI/backend/app/models/structured_fact.py#L1-L45), [`structured_facts_service.py:1-150`](file:///Users/apple/Projects/University%20AI/backend/app/services/structured_facts_service.py#L1-L150) | PostgreSQL table `structured_facts` is the authoritative single source of truth. Cached in memory at startup, auto-refreshed on `facts_version` bump. Grounding validator reads from the same service. Zero hardcoded fact dictionaries at runtime. |
| **6** | **Embedding model & task types** | **DONE** | [`backend/app/providers/embedding_gemini.py:49-98`](file:///Users/apple/Projects/University%20AI/backend/app/providers/embedding_gemini.py#L49-L98), [`docs/decisions/2026-11-embedding-migration.md`](file:///Users/apple/Projects/University%20AI/docs/decisions/2026-11-embedding-migration.md) | Uses `gemini-embedding-001` (3072 dims) preserving 162 existing production vectors. Architectural Decision Record and shadow script `shadow_reembed_text_embedding_004.py` prepared for zero-downtime migration to `text-embedding-004`. |
| **7** | **Generation model config** | **DONE** | [`backend/app/config.py:30-45`](file:///Users/apple/Projects/University%20AI/backend/app/config.py#L30-L45) | Model configured via `LLM_MODEL` env var (`gemini-3.5-flash-lite`, swappable to `gemini-3.7-flash` or Ollama). Response cache key incorporates `generation_model` so model swaps automatically invalidate cached responses. |
| **8** | **Persona / system prompts** | **DONE** | [`prompts/persona.md:1-25`](file:///Users/apple/Projects/University%20AI/prompts/persona.md#L1-L25), [`prompts/factual.md:1-17`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L1-L17) | Warm older friend persona (<80 words, zero brochure-speak, language mirroring, at most one casual next step). All contact literals (`{admissions_phone}`, `{admissions_email}`, `{admissions_portal_url}`) centrally interpolated at prompt load time. |
| **9** | **Grounding & citation policy** | **DONE** | [`prompts/factual.md:6-10`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L6-L10), [`chat_service.py:134-165`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L134-L165) | Owner decision confirmed: source citations are stripped from student-facing chat for clean conversational UX (`SHOW_SOURCES=False`), but full source metadata is stored in PostgreSQL `messages.sources` for admin audits and SSE done payload. |
| **10** | **Fallback when info is missing** | **DONE** | [`prompts/factual.md:7`](file:///Users/apple/Projects/University%20AI/prompts/factual.md#L7), [`validator_service.py:40-60`](file:///Users/apple/Projects/University%20AI/backend/app/services/validator_service.py#L40-L60) | Frank admission of missing information routing to Admissions Office contacts (`0870-2818333` / `info@sru.edu.in`) dynamically populated from centralized config. |
| **11** | **Guardrails** | **DONE** | [`prompts/sensitive.md:1-25`](file:///Users/apple/Projects/University%20AI/prompts/sensitive.md#L1-L25), [`guardrail_service.py:1-85`](file:///Users/apple/Projects/University%20AI/backend/app/services/guardrail_service.py#L1-L85) | Zero admission/scholarship guarantees; no unverified superlatives; no competitor disparagement; never claims human identity. Verified with repeated live-model adversarial evaluations (T4). |
| **12** | **Merge step for mixed questions** | **DONE** | [`prompts/merge.md:1-10`](file:///Users/apple/Projects/University%20AI/prompts/merge.md#L1-L10), [`chat_service.py:320-375`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L320-L375) | Multi-part queries executed concurrently and merged under 100 words. If any sub-part triggers crisis/distress, sensitive turn takeover immediately halts merging and surfaces national helplines. |
| **13** | **Numeric / date validator** | **DONE** | [`backend/app/services/validator_service.py:1-210`](file:///Users/apple/Projects/University%20AI/backend/app/services/validator_service.py#L1-L210) | Pure Python deterministic regex validator: extracts currency (`₹`, INR, Lakhs with Indian comma grouping), `%`, LPAs, ordinal ranks, canonical dates across 4 formats, and multi-unit quantities (seats, credits, semesters, years, students). Whitelisted constants require rationale comments. |
| **14** | **Session memory & student_profile** | **DONE** | [`backend/app/services/profile_service.py:1-85`](file:///Users/apple/Projects/University%20AI/backend/app/services/profile_service.py#L1-L85), [`cache_service.py:25-90`](file:///Users/apple/Projects/University%20AI/backend/app/services/cache_service.py#L25-L90) | Extracts program, category, nationality, and exam to form canonical SHA-256 cache key. Sub-part scoping prevents cross-session pronoun pollution ("what about fees?"). |
| **15** | **Sensitive / crisis escalation** | **DONE** | [`router_service.py:18-35`](file:///Users/apple/Projects/University%20AI/backend/app/services/router_service.py#L18-L35), [`chat_service.py:115-135`](file:///Users/apple/Projects/University%20AI/backend/app/services/chat_service.py#L115-L135) | Multi-lingual crisis detection covering English, Telugu-English ("chavalanipisthondi"), and Hinglish ("mar jana chahta hu"). Fast-path bypasses LLM; sensitive turn takeover cancels factual/persuasive execution and provides Tele-MANAS (`14416`), AASRA (`9820466726`), Kiran (`1800-599-0019`). |
| **16** | **Unanswered logging & DPDP compliance** | **DONE** | [`privacy.py:1-65`](file:///Users/apple/Projects/University%20AI/backend/app/utils/privacy.py#L1-L65), [`evaluation_service.py:1-160`](file:///Users/apple/Projects/University%20AI/backend/app/services/evaluation_service.py#L1-L160) | All phone numbers and email addresses scrubbed before writing to logs or `evaluation_records`. 90-day retention purge script (`purge_old_conversations.py`) and user right-to-erasure endpoint (`POST /api/v1/privacy/delete-my-data`). |
| **17** | **Lead capture** | **DONE** | [`backend/app/schemas/lead.py:1-35`](file:///Users/apple/Projects/University%20AI/backend/app/schemas/lead.py#L1-L35), [`LeadAuthModal.tsx:1-180`](file:///Users/apple/Projects/University%20AI/frontend/src/components/LeadAuthModal.tsx#L1-L180) | Non-intrusive modal with mandatory DPDP consent checkbox, HTML sanitization, phone deduplication, and privacy policy modal link in chat header. |
| **18** | **Tests & Eval Set** | **DONE** | [`backend/tests/`](file:///Users/apple/Projects/University%20AI/backend/tests/), [`backend/evals/`](file:///Users/apple/Projects/University%20AI/backend/evals/) | **315 automated tests passing** across 38 suites in ~3s. Standalone live evaluation script (`scripts/eval_live.py`) with 100% pass on Part C, safety repetitions, and adversarial prompt injections. |

---

## 2. Technology Stack Audit

| Layer | Current Tool + Version | Status | Reason & Hardening Assessment |
|---|---|---|---|
| **LLM SDK & Model** | `httpx` async client to Google Gemini REST API (`gemini-3.5-flash-lite`) | **Keep** | Zero third-party SDK bloat; automatic multi-key rotation pool (`key_pool.py`); provider interface allows hot-swapping. |
| **Embedding SDK & Model** | `httpx` async client (`gemini-embedding-001`, 3072 dims) | **Keep** | Retains all 162 existing document embeddings without data migration risk; ADR and shadow script ready for `text-embedding-004`. |
| **Backend Framework** | FastAPI 0.115+ (Python 3.11, async) | **Keep** | Fully asynchronous, typed Pydantic v2 request/response contracts, clean modular router with zero business logic in routes. |
| **Vector Store** | ChromaDB (v0.6.3 in Docker on port 8000) | **Keep** | Physically partitioned into `sru_facts` (95 chunks) and `sru_highlights` (67 chunks) for strict content separation. |
| **Keyword / Hybrid Search** | Okapi BM25 sparse index + dense vector search + RRF ($k=60$) | **Hardened** | Staff-tunable keyword/title boost configuration via `backend/app/data/retrieval_boosts.yaml`. |
| **Relational DB** | PostgreSQL 16 Alpine (Port 5433 with SQLAlchemy 2.0 asyncpg) | **Keep** | Authoritative ACID storage for `structured_facts`, `conversations`, `messages`, `prospective_leads`, and `evaluation_records`. |
| **Session Cache & Memory** | Redis 7 Alpine (Port 6379, async redis-py) | **Hardened** | Per-part sub-question caching keyed on SHA-256 canonical tuples with `index_version` and `facts_version` invalidation counters. |
| **Document Ingestion** | `ingestion_service.py` (PyPDF, python-docx, openpyxl) | **Keep** | Multi-format parser with text cleaning, semantic chunking, and dual-collection auto-partitioning. |
| **Streaming** | Server-Sent Events (`StreamingResponse` / SSE) | **Keep** | Real-time token streaming with `chunk_text_stream` and `done` JSON payloads. |
| **Frontend UI** | React 19 + TypeScript + Vite 8.3 | **Keep** | Responsive modern chat interface, DPDP consent banner, privacy policy modal, interactive cards, and zero build/typecheck errors. |
| **Observability & Privacy** | Internal evaluation service + DPDP log masking | **Hardened** | PII masking (phones/emails) in logs, 90-day retention purge script, and GDPR/DPDP right-to-erasure endpoint. |
| **CI / Verification** | `./scripts/run_all_checks.sh` | **Added** | Single universal bash script executing prompt hygiene, TypeScript checks, 315 pytest cases, and configuration integrity. |

---

## 3. Codebase Inventory & Entry Points

- **Backend Entry Point**: [`backend/app/main.py`](file:///Users/apple/Projects/University%20AI/backend/app/main.py)
- **Chat Router Endpoint**: [`backend/app/api/v1/chat.py`](file:///Users/apple/Projects/University%20AI/backend/app/api/v1/chat.py)
- **Privacy Endpoints**: [`backend/app/api/v1/privacy.py`](file:///Users/apple/Projects/University%20AI/backend/app/api/v1/privacy.py)
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
  - Zero hardcoded API keys or credentials in source code.
  - Zero hardcoded contacts or helplines in prompts (interpolated dynamically).
  - DPDP compliance fully implemented (log scrubbing, retention purge, right-to-erasure).

---

## 4. Current Service Health & Test Summary

- **Pytest Suite**: **315 passed**, 0 failed, 0 errors in 3.00s.
- **Frontend Build & Typecheck**: `npx tsc --noEmit` exits 0 cleanly.
- **Universal Verification**: `./scripts/run_all_checks.sh` exits 0 with all 4 phases passing.
- **Runtime Services**:
  - Backend: `http://localhost:8080/health` → `{"status": "healthy"}`
  - Frontend: `http://localhost:5173` → Active and responding.
  - PostgreSQL, Redis, and ChromaDB: Healthy in Docker containers.
