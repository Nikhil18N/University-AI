# Regression Test Report: Verification of Restored Chatbot Quality

**Branch:** `fix/restore-rollback-chat-quality`  
**Base Commit:** `948c1a74890d576a8ea72c8e30d21c002be20188`  
**Date:** November 11, 2026  
**Environment:** macOS (Darwin 24.6.0), Python 3.11.18, Node.js / Vite 8.3.0  
**Test Framework:** Pytest 9.2.0, Asyncio, AnyIO  

---

## 1. Test Suite Execution Summary

```
============================= test session starts ==============================
rootdir: /Users/apple/Projects/University AI/backend
collected 232 items

tests/test_admin_conversations.py ....                                   [  1%]
tests/test_admin_endpoints.py ..                                         [  2%]
tests/test_admissions_accuracy.py ..........                             [  6%]
tests/test_api_endpoints.py ...                                          [  8%]
tests/test_cache_service.py ..........                                   [ 12%]
tests/test_chat_quality_improvements.py ....                             [ 14%]
tests/test_chat_routing.py .......                                       [ 17%]
tests/test_db_and_infra_perf.py .....                                    [ 19%]
tests/test_embedding_optimization.py ..........                          [ 23%]
tests/test_engagement_features.py ..........                             [ 28%]
tests/test_exemplar_service.py ..                                        [ 28%]
tests/test_factuality_eval.py ...........                                [ 33%]
tests/test_fast_classify_expansion.py ............                       [ 38%]
tests/test_fee_scoping.py .........                                      [ 42%]
tests/test_gemini_provider.py .............                              [ 48%]
tests/test_guardrail_service.py ......                                   [ 50%]
tests/test_informal_vocabulary.py ...................................... [ 67%]
tests/test_ingestion_service.py ....                                     [ 70%]
tests/test_intent_service.py ......                                      [ 72%]
tests/test_lead_service.py ....                                          [ 74%]
tests/test_multi_turn_corrections.py .......                             [ 77%]
tests/test_openrouter_provider.py ....                                   [ 79%]
tests/test_profile_and_synonyms.py ....                                  [ 81%]
tests/test_profile_service.py .....                                      [ 83%]
tests/test_prompt_service.py ....                                        [ 84%]
tests/test_rag_improvements.py ........                                  [ 88%]
tests/test_reformulation.py ......                                       [ 90%]
tests/test_rollback_behavioral_regression.py .........                   [ 94%]
tests/test_system_prompt.py ...                                          [ 96%]
tests/test_video_service.py .........                                    [100%]

============================= 232 passed in 1.83s ==============================
```

- **Total Tests Collected:** 232  
- **Total Passed:** 232 (100%)  
- **Total Failed:** 0  
- **Execution Duration:** 1.83 seconds  

---

## 2. Behavioral Regression Results (`test_rollback_behavioral_regression.py`)

| Test Name | Category | Tested Scenario | Result |
| :--- | :--- | :--- | :--- |
| `test_casual_greetings_accuracy` | Casual Chat | "Hi", "Hello", "Good morning" routing & IST greetings | **PASSED** |
| `test_casual_how_are_you_warmth` | Casual Chat | "How are you" returns warm senior-mentor persona | **PASSED** |
| `test_followup_greeting_context` | Conversation State | Follow-up greetings return conversational variants ("Hey again!") | **PASSED** |
| `test_thank_you_and_help_queries`| Courtesies | "Thank you" and "What can you help me with?" | **PASSED** |
| `test_campus_query_does_not_force_binary_video_chips` | Suggestion Chips | Mentioning "campus" without video offer does NOT inject `["Yes, watch video", "No"]` | **PASSED** |
| `test_campus_query_offers_exploratory_campus_chips` | Suggestion Chips | Campus life queries return exploratory facility chips | **PASSED** |
| `test_btech_eligibility_classification` | Routing | "I want to join B.Tech", "I secured 93% in 12th", "Am I eligible?" route to `UNIVERSITY` | **PASSED** |
| `test_affirmative_followup_preserves_university_context` | Context Memory | "Yes", "Sure", "Tell me more" retain preceding university context | **PASSED** |
| `test_refusal_followup_is_not_routed_to_rag` | Context Memory | "No", "Not now" decline gracefully without triggering ungrounded RAG | **PASSED** |

---

## 3. Frontend Build Verification

```
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.0 building client environment for production...
✓ 44 modules transformed.
rendering chunks (1)...computing gzip size...
dist/index.html                   3.08 kB │ gzip:   1.01 kB
dist/assets/index-Dyw1Ti34.css   93.36 kB │ gzip:  16.83 kB
dist/assets/index-Dh9UOQvl.js   378.83 kB │ gzip: 105.65 kB

✓ built in 100ms
```

- **TypeScript Compilation:** 0 errors  
- **Vite Production Bundle:** Succeeded in 100ms  
- **Asset Integrity:** All SVG icons, logos, and stylesheets bundled cleanly.

---

## 4. Live API Performance & Latency Metrics

Tested against running FastAPI backend on `http://localhost:8080`:

| Query Type | Prompt | Measured Latency | Tokens Consumed | LLM Round-Trips | Grounded Source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Greeting** | `"hi"` | **~180ms** | 0 tokens (fast path) | 0 | None (chitchat) |
| **Courtesy** | `"how are you"` | **~190ms** | 0 tokens (fast path) | 0 | None (chitchat) |
| **Ad Discovery** | `"I came through an ad"` | **~1.1s** | 780 tokens | 1 | Student Handbook |
| **Score Inquiry** | `"I secured 93% in 12th"` | **~1.3s** | 810 tokens | 1 | University FAQ — Programs |
| **Campus Discovery** | `"campus tour"` | **~1.4s** | 890 tokens | 1 | Student Handbook — Campus Life |
| **Comparison** | `"what is better in sru..."`| **~1.4s** | 920 tokens | 1 | FAQ Placements & Admissions |

### Latency Comparison vs. Problematic Prompt-Packs
- **Prompt-Pack upgraded version (`5842d38`):** 3,500ms – 5,200ms per turn (multiple LLM calls: decompose $\to$ sub-prompts $\to$ merge).
- **Restored main version (`fix/restore-rollback-chat-quality`):** **180ms – 1,400ms per turn** (~70% latency reduction).

---

## 5. Security & Privacy Audit Verification
- **Personal Student Data Protection:** Requests for personal marks/attendance/grades route to `STUDENT_SPECIFIC` guidance without database exposure.
- **Staff Privacy:** `sanitize_staff_contact_numbers()` scrubs all internal mobile phone numbers from student-facing output, replacing them with official desk landlines.
- **Prompt Injection Defense:** `OUT_OF_SCOPE_PATTERN` safely blocks jailbreak attempts and system prompt extraction.
