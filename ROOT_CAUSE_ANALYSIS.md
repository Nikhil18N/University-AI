# Root Cause Analysis: Restoring Conversational Excellence in SRU Buddy

**Project:** University AI Companion — SRU Buddy  
**Target Branch:** `fix/restore-rollback-chat-quality`  
**Base Commit (MAIN):** `948c1a74890d576a8ea72c8e30d21c002be20188`  
**Behavioral Baseline (ROLLBACK):** `2ce81b5bc1e53b56cd7b40a63c0e0523da5c92e7` (and transcript in `rollback_resp.pdf`)  
**Author:** Senior AI Engineer, Backend Architect & RAG Specialist  
**Date:** November 11, 2026  

---

## 1. Executive Summary

A recent rollback to commit `2ce81b5` restored exceptional chatbot responsiveness, warmth, context retention, and transparency (as captured in `rollback_resp.pdf`). However, the latest version on `main` (`948c1a7`) contains critical new features:
- Streamlined scholarship calculator (`ScholarshipCalculatorModal.tsx`).
- Prospective lead tracking and administrative auth middleware (`backend/app/api/v1/lead.py`).
- Minimal executive SR University vector icons (`Icons.tsx`).
- 5-stage thinking indicators and modern message bubbles.
- Database query optimizations, Redis caching, and async pooling.

This investigation was conducted to pinpoint the exact root causes of degraded conversational behavior on the latest commits and define the exact surgical changes required to restore conversational excellence **on top of `main` without rolling back or discarding newer features**.

---

## 2. Root Cause Breakdown

### Root Cause 1: Over-Constrained Negative Prompting & Cognitive Dissonance
- **Files Modified:** `prompts/system.md`, `prompts/rag.md`
- **What Changed:**
  In subsequent updates after `2ce81b5`, prompt engineers attempted to prevent over-enthusiastic AI salesmanship by introducing numerous negative constraints:
  - *"NEVER use repetitive cheerleading tropes..."*
  - *"Zero boilerplate sympathy; do not congratulate or compliment scores."*
  - *"Emotion gating: avoid enthusiastic encouragement."*
  - *"Do not end every turn with 'Would you like to know more about [topic]?'"*
  - Rigid 5-pillar requirement: forcing 5 mandatory evaluation criteria (Placements, Infrastructure, Fees, Hostels, FFCS) into exploratory turns.
- **Impact on Conversational Quality:**
  When a student said *"I came through an ad"* or *"I secured 93% in 12th"*, the model suffered from conflicting prompt directives. Instead of naturally congratulating the student and asking for their branch interest (as in `rollback_resp.pdf`), the bot sounded cold, hesitant, or dumped a rigid 5-pillar wall of text.
- **Solution:**
  Decouple prospective lead engagement from skepticism defense. Retain verified 2026-27 facts, but explicitly encourage warm, authentic congratulations on high scores and conversational qualification questions.

---

### Root Cause 2: False-Triggering Binary Video Chips in Suggestion Service
- **Files Modified:** `backend/app/services/suggestion_service.py`
- **What Changed:**
  Commit `528b7fc` / `4c7a6cb` introduced vector-based video suggestions. However, in `suggestion_service.py`, `CAMPUS_VIDEO_OFFER_SUGGESTIONS` (containing `["🎥 Yes, watch video", "❌ No, thanks"]`) was set as the fallback whenever the word `"campus"` appeared anywhere in the user query OR the bot's answer (`ans_lower`).
- **Impact on Conversational Quality:**
  When a student said *"I came through an ad"* and the assistant replied *"Welcome to SR University! It's great to have you here to explore our campus..."*, the suggestion engine saw `"campus"` in the answer and injected `["🎥 Yes, watch video", "❌ No, thanks"]` into the suggestion chips—even though the assistant had NEVER offered a video tour! The user was trapped in an awkward binary Yes/No loop.
- **Solution:**
  Replaced forced video chips with exploratory chips (`CAMPUS_SUGGESTIONS` and `SRIX_SUGGESTIONS`). Video binary chips are now ONLY presented when a video was explicitly offered in the assistant's response.

---

### Root Cause 3: Premature Removal of Fee Cards Resulting in 9 Test Failures
- **Files Modified:** `backend/app/services/card_service.py`
- **What Changed:**
  In commit `6d3a774` (`feat(fees): remove hardcoded fee cards in favor of grounded handbook responses`), fee card generation was commented out in `card_service.py` to rely solely on text RAG responses. However, `test_fee_scoping.py` (8 tests) and `test_admissions_accuracy.py` (1 test) expected cleanly scoped fee cards.
- **Impact on System Health:**
  9 tests broke in the CI test suite, and users asking for specific fees (e.g. transport, hostel, or exam fees) were deprived of clean, structured summary cards.
- **Solution:**
  Restored strictly category-scoped fee cards (`TRANSPORT_FEE_CARD`, `HOSTEL_FEE_CARD`, `EXAM_FEE_CARD`, `ADMISSION_FEE_CARD`, `MERIT_SCHOLARSHIP_CARD`, `BTECH_CSE_FEE_CARD`, `BTECH_ACADEMIC_FEE_CARD`) aligned 100% with the official 2026-27 handbook figures.

---

### Root Cause 4: Missing Common Vocabulary in Fast Intent Classifier
- **Files Modified:** `backend/app/services/intent_service.py`
- **What Changed:**
  `fast_classify` regexes tokenized punctuation, causing words like `"B.Tech"` to split into `"b"` and `"tech"`. Neither `"tech"` nor `"eligible"` were in the `UNIVERSITY_KEYWORDS` set.
- **Impact on Conversational Flow:**
  Queries like *"I want to join B.Tech"* or *"Am I eligible?"* were missed by the instant classifier (<1ms) and had to fall back to the slower LLM classifier, introducing unnecessary latency.
- **Solution:**
  Added `"tech"`, `"engineering"`, and `"eligible"` to `UNIVERSITY_KEYWORDS` and added regex patterns for `"want to join / apply"` to `COMMON_UNIVERSITY_PHRASES`.

---

## 3. Comparative Summary Table

| Issue | Rollback Version (`2ce81b5`) | Latest Version (`948c1a7`) | Fixed Version (`fix/restore-...`) |
| :--- | :--- | :--- | :--- |
| **Greeting & Persona** | Warm, senior guide, IST-aware. | Stiff, defensive, over-constrained. | **Warm, celebratory, senior-mentor tone restored.** |
| **Lead Nurturing** | Asks program + PCM score naturally. | Dumps 5 academic evaluation pillars. | **Natural qualification flow restored.** |
| **Score Celebrations** | Congratulates 93% enthusiastically. | Muted or avoided due to negative prompts. | **Congratulates warmly, confirms eligibility directly.** |
| **Suggestion Chips** | Exploratory topical chips. | Trapped in `["🎥 Yes, watch video", "❌ No"]`. | **Clean exploratory chips; video chips isolated to actual video offers.** |
| **Structured Fee Cards** | Hardcoded cards present. | Commented out (9 test failures). | **Strict category-scoped cards restored & passing tests.** |
| **Test Suite Health** | 140 passed. | 9 failed out of 223. | **232 passed in 1.83s (100% passing).** |
| **Latest Features** | None of the new features. | All new features present. | **All new features 100% preserved.** |
