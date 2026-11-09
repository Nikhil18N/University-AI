# Running CHANGELOG — SRU Buddy Hardening

## [T1] Fix response-cache key and scope (P0)

### Already there
- `backend/app/services/cache_service.py` with basic MD5 query hashing and TTL support.
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
