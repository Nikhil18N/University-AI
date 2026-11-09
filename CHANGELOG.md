# Running CHANGELOG — SRU Buddy Hardening

## [T9] BM25 + RRF hybrid retrieval (P2)

### Already there
- ChromaDB dense vector retrieval with cosine distance thresholding (`RAG_MAX_DISTANCE`) and LLM reranking.

### Changed
- `backend/app/config.py`:
  - Added `HYBRID_RETRIEVAL_ENABLED: bool = True`.
- `backend/app/services/rag_service.py`:
  - Integrated BM25 sparse keyword search alongside dense ChromaDB vector search.
  - Fuses dense and sparse rankings using Reciprocal Rank Fusion (RRF, $k=60$) before downstream boost application and reranking.
- `backend/app/services/cache_service.py`:
  - Hooked `bump_index_version()` to call `invalidate_bm25_index()` so index version changes automatically rebuild the in-memory sparse index.

### Added
- `backend/app/services/bm25_service.py`:
  - Zero-dependency in-memory Okapi BM25 engine with title-weighted tokenization, length normalization ($k_1=1.5, b=0.75$), and standard IDF calculations.
  - `reciprocal_rank_fusion()` function combining multi-ranker outputs ($1 / (k + rank_i)$).
  - Version-aware cached index management with lazy instantiation and invalidation.
- `backend/tests/test_hybrid_retrieval.py`:
  - 4 unit tests validating exact keyword ranking ("Dr. Sumanth", "CSE-AIML-401"), RRF score boosting over dense-only results, and index invalidation lifecycle.
- Test suite expanded from 306 to 310 tests passed.

## [T8] Crisis detection second layer (P1)

### Already there
- Basic fast-path router checking a limited set of English distress tokens.
- Router LLM prompt routing sensitive queries.

### Changed
- `backend/app/services/router_service.py`:
  - Implemented `CRISIS_DISTRESS_REGEX` and `is_crisis_or_distress()` with comprehensive multi-lingual coverage across:
    - **English**: "ending it all", "suicide", "kill myself", "end my life", "hopeless", "lost all hope", "don't want to live", "better off dead", "harm myself".
    - **Telugu-English**: "asha ledu", "pranam theesukunta", "jeevitham meeda virakthi", "jeevitham meeda asha poindi", "chasthe bagunnu", "bathakali ani ledu", "chaavali anipistundi".
    - **Hinglish**: "koi umeed nahi", "marne ka mann kar raha", "sab khatam ho gaya", "sab khatam karna chahta hu", "zindagi se tang aa gaya", "jeene ki chahat nahi".
  - Fast-path execution runs before any LLM router invocation; matches instantly classify mode=sensitive with confidence=1.0 in < 2ms without invoking LLM.
  - Safe fallback: if router LLM times out or returns malformed JSON, router verifies distress regex before defaulting to factual.
- `backend/app/services/chat_service.py`:
  - Implemented sensitive turn takeover: if ANY decomposed sub-part is classified as sensitive or the query matches crisis/distress, the sensitive handler claims the entire turn.
  - Completely bypasses parallel factual/persuasive execution and the merge prompt.
  - Purges admissions pitches (tuition figures, application portal links, scholarship marketing) from distress replies.
  - Automatically surfaces configured national student helplines (Tele-MANAS, AASRA, Kiran) with empty source references.

### Added
- Expanded unit and pipeline tests in `backend/tests/test_router_service.py`:
  - Parameterized table of 13 distinct distress phrasings across 3 languages verifying 100% sensitive routing with 0 LLM calls.
  - Test verifying distress detection on broken JSON router fallbacks.
  - Integration test for combined query ("fees for CSE and I feel like ending it all") verifying that all fee details are dropped and only compassionate support is returned.
- Test suite expanded from 291 to 306 tests passed.

## [T7] Move contacts, helplines and boost terms to config/data (P1)

### Already there
- Contact numbers (`0870-2818333`), emails (`info@sru.edu.in`), and crisis helplines (`14416`) hardcoded across multiple prompt templates and Python service files.
- Hardcoded retrieval bonus values in `rag_service.py` for specific titles and keywords.

### Changed
- `backend/app/config.py`:
  - Added centralized university contacts: `ADMISSIONS_PHONE`, `ADMISSIONS_PHONE_ALT`, `ADMISSIONS_EMAIL`, `HELPDESK_EMAIL`, `ADMISSIONS_PORTAL_URL`, and `CAMPUS_LOCATION`.
  - Added structured crisis helpline registry `CRISIS_HELPLINES` (Tele-MANAS, AASRA, Kiran) with 24/7 hours, phone, alt_number, and language coverage.
- `prompts/*.md`:
  - Replaced all hardcoded phone, email, portal URLs, and helpline literals across `sensitive.md`, `factual.md`, `persona.md`, `rag.md`, and `system.md` with centralized placeholders (`{admissions_phone}`, `{admissions_email}`, `{admissions_portal_url}`, `{crisis_helplines}`).
- `backend/app/services/prompt_service.py`:
  - Added `interpolate_config_placeholders()` and `get_default_prompt_variables()` to interpolate centralized config variables at prompt load time.
- `backend/app/services/validator_service.py`:
  - Dynamically populates phone numbers and crisis helplines from config into the validator's grounding whitelist via `get_dynamic_allowed_numbers()`.
  - Dynamic fallback responses via `get_fallback_validator_block()` and `get_fallback_low_confidence()`.
- `backend/app/services/rag_service.py`:
  - Replaced hardcoded title/keyword boost bonuses with YAML-driven retrieval tuning via `load_retrieval_boosts()`.
- `backend/app/services/chat_service.py`:
  - Replaced hardcoded crisis keywords and staff fallback desks with config-derived contact entries.
- `backend/app/main.py`:
  - Added application startup verification checking that all required contacts, helplines, and `retrieval_boosts.yaml` exist.

### Added
- `backend/app/data/retrieval_boosts.yaml`:
  - Centralized retrieval boost configuration allowing staff to tune score bonuses and match keywords without Python code modifications.
- `backend/tests/test_config_centralization.py`:
  - 5 unit tests validating dynamic prompt propagation, validator whitelist synchronization, custom crisis helpline acceptance, YAML boost loading, and zero hardcoded literals in prompts.
- Test suite expanded from 286 to 291 tests passed.

## [T6] Log masking, DPDP notice, retention (P1)

### Already there
- PostgreSQL `evaluation_records` table and `record_evaluation` service logging queries and answers.
- Single conversation deletion endpoint `DELETE /api/v1/conversations/{conversation_id}`.

### Changed
- `backend/app/config.py`:
  - Added `CONVERSATION_RETENTION_DAYS: int = 90`.
- `backend/app/services/evaluation_service.py`:
  - Integrated PII masking: all user questions, assistant answers, expected answers, and metadata are sanitized through `mask_pii()` before saving to `evaluation_records`.
- `backend/app/main.py`:
  - Registered `privacy_router` for DPDP erasure operations.
- `frontend/src/pages/ChatPage.tsx` & `frontend/src/components/PrivacyModal.tsx`:
  - Added non-blocking DPDP privacy notice below the chat input: "Chats may be recorded to improve admission assistance. See privacy policy."
  - Added modal explaining data handling, masking under the DPDP Act, 90-day retention schedule, and one-click right to erasure ("Delete My Data").
- `frontend/src/services/api.ts`:
  - Added `deleteMyData` client function.

### Added
- `backend/app/utils/privacy.py`:
  - PII masking utilities for phone numbers (e.g. `98765*****`, `+91 98765*****`, `+91-98765-*****`) and emails (`s***@domain.edu`).
- `backend/app/schemas/privacy.py` & `backend/app/api/v1/privacy.py`:
  - `POST /api/v1/privacy/delete-my-data`: student and admin right-to-erasure endpoint that hard-deletes conversations, messages, evaluation records, and prospective leads given a `session_id` or `phone`.
- `backend/scripts/purge_old_conversations.py`:
  - Retention purge script supporting `--days`, `--dry-run` (default True), and `--yes` for safely purging records older than retention period without accidental deletions.
- `backend/tests/test_privacy_dpdp.py`:
  - 6 unit and integration tests covering phone/email masking, PII scrubbing in evaluation records, dry-run & live retention purge, and `delete-my-data` API endpoint.
- Test suite expanded from 280 to 286 tests passed.

## [T5] Extend the numeric and date validator (P1)

### Already there
- Basic numeric validator checking extracted integers against retrieved grounded numbers.
- Whitelist set with some unannotated constants.

### Changed
- `backend/app/services/validator_service.py`:
  - Replaced unannotated set with `WHITELISTED_CONSTANTS_WITH_REASONS: dict[str, str]` where every single constant (contact numbers, rankings, minimum marks percentages, fee scales) has an explicit documented rationale.
  - Added `format_indian_currency()` and `normalize_currency_amount()` supporting Indian numbering (e.g., "1,25,000"), Western comma grouping ("125,000"), raw digits ("125000"), and lakh representations ("1.25 lakh", "1.25lakh").
  - Added `normalize_date()` handling DD Month YYYY, Month DD YYYY, DD/MM/YYYY, and YYYY-MM-DD formats into canonical ISO representations so valid date paraphrasing passes verification.
  - Added unit quantity extraction (`extract_unit_numbers`) for seats, credits, semesters, years, and students.
  - Masked log entries: `mask_sensitive_token()` ensures tokens and rejection reasons logged do not expose raw student data or ungrounded values in plain text.

### Added
- Comprehensive test suite in `backend/tests/test_validator_service.py` (26 tests, up from 5):
  - Currency normalization and multi-format matching.
  - Indian comma grouping and lakh equivalents.
  - Date normalization across 4 distinct formats.
  - Unit numbers (seats, semesters, credits).
  - Whitelist justification test ensuring every entry in `WHITELISTED_CONSTANTS_WITH_REASONS` has a non-empty rationale.
  - Masked rejection logging validation.
- Test suite expanded from 259 to 280 tests passed.

## [T2] Make structured facts a single source of truth (P0)

### Already there
- PostgreSQL `structured_facts` table schema created via Alembic migration `d4e5f6789012`.
- Initial `VERIFIED_FACTS_REGISTRY` in `structured_facts_service.py` containing 22 ground-truth verified figures.

### Changed
- `backend/app/services/structured_facts_service.py`:
  - Made PostgreSQL table `structured_facts` the single authoritative ground truth.
  - Added `refresh_facts_cache_from_db()` to load rows into an in-memory cache on startup and whenever `facts_version` changes.
  - Refactored `get_structured_facts_text()` and `get_all_grounded_numbers()` to read exclusively from the authoritative active facts.
  - Added `update_structured_fact()` with full audit trail (`last_updated`, `updated_by`, `source_url`) and automatic `facts_version` bumping in Redis.
- `backend/app/main.py`:
  - Added startup hook to preload structured facts from PostgreSQL into memory.
- `backend/app/api/v1/admin.py`:
  - Added `GET /api/v1/admin/facts` and `PUT /api/v1/admin/facts/{fact_id}` endpoints for administrative facts management.
- `backend/app/schemas/admin.py`:
  - Added `StructuredFactItem` and `StructuredFactUpdateRequest` Pydantic models.

### Added
- `backend/scripts/seed_structured_facts.py`: Idempotent seed script that loaded 22 verified university facts into PostgreSQL.
- `backend/tests/test_structured_facts_service.py`: 5 service-level unit tests verifying DB loading, validator synchronization, facts update, and audit tracking.

## [T3] Citation policy (P0)

### Already there
- `Message.sources` stored in PostgreSQL for admin audits, transcript inspector, and QA evaluation.
- Regex sanitizers in `chat_service.py` stripping inline/trailing source mentions.

### Changed
- Deliberate policy enforcement based on owner decision: citations are kept hidden from student-facing responses while source references remain preserved in PostgreSQL for auditing.
- Added `SHOW_SOURCES: bool = False` to `backend/app/config.py`.
- `chat_service.py` gates response `sources` list on `SHOW_SOURCES`.

### Added
- Documented policy alignment across prompts, services, and tests.


## [T4] Live-model evals for safety cases (P0)

### Already there
- Offline test suite in `backend/tests/test_prompt_pack_eval.py` asserting on mocked router and validator responses.

### Changed
- `backend/app/providers/gemini.py`:
  - Increased HTTP client timeout to 35.0s (connect: 10.0s) to handle transient Gemini API queue latency.
- `backend/app/services/router_service.py` & `prompts/router.md`:
  - Expanded fast-path distress detection regex to cover feelings of hopelessness, despair, and multilingual distress.
  - Added explicit prompt rules distinguishing study passion advice (`persuasive`) from small talk.

### Added
- `backend/scripts/eval_live.py`:
  - Standalone live model evaluation harness gated behind `RUN_LIVE_EVALS=1`.
  - Runs all 15 Part C test cases against live Gemini model and ChromaDB index.
  - Runs 5x repeated runs for critical safety cases 9 (admission guarantee), 10 (hopelessness), and 11 (missing fee).
  - Runs 6 adversarial prompt injection and safety bypass cases.
  - Generates dated Markdown report in `backend/evals/results/` with commit hash and model details.
- Verified live results: **15/15 Part C Passed (100%)**, **5/5 Case 9 Passed (100%)**, **5/5 Case 10 Passed (100%)**, **5/5 Case 11 Passed (100%)**, **6/6 Adversarial Passed (100%)**, **0 ungrounded numbers**.

## [T1] Fix response-cache key and scope (P0)
- Redis client initialization on application startup (`main.py`) bound to `request.app.state.redis`.
- Redis dependency injection in `deps.py` (`get_redis`).

### Changed
- `backend/app/services/cache_service.py`:
  - Upgraded cache key from naive raw query hashing to canonical delimited tuple:
    `cache_schema_version | mode | resolved_question_normalized | relevant_profile_fields | prompt_version | generation_model | index_version | facts_version`.
  - Added strict mode gating: only `factual` queries are cacheable. Persuasive, chitchat, sensitive, out of scope, merged multi-part answers, validator fallback blocks, and clarifying questions back to students are completely excluded from caching.
  - Sanitized log output: logs key digests rather than raw query text or student PII.
  - Added Redis counter trackers (`index_version` and `facts_version`) for automatic cache invalidation upon document ingestion or fact updates.
- `backend/app/services/chat_service.py`:
  - Wired `get_cached_part` and `set_cached_part` into `execute_prompt_pack_pipeline`.
  - Cache lookup operates at the resolved sub-question level after pronoun resolution.
  - Passed `redis_client` through `handle_chat_request` and `stream_chat_response`.
- `backend/app/api/v1/admin.py`:
  - Integrated `bump_index_version(redis)` into `upload_document` and `deactivate_document`.
- `backend/app/config.py`:
  - Added `RESPONSE_CACHE_ENABLED: bool = True`.

### Added
- Scoped cache unit and integration tests in `backend/tests/test_cache_service.py` (total tests expanded from 247 to 254):
  - Deterministic key hashing with `v2` schema prefix.
  - Collision prevention for identical raw strings with different resolved pronouns.
  - Degree/branch profile isolation.
  - Exclusion of student interests from factual keys.
  - Mode gating verification for non-factual intents.
  - Exclusion of multi-part merged replies.
  - Clarifying question exclusion.
  - Validator block fallback exclusion.
  - `index_version` and `facts_version` bump invalidation.
  - Global `RESPONSE_CACHE_ENABLED` disable toggle verification.

