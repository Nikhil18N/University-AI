# Running CHANGELOG — SRU Buddy Hardening

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

