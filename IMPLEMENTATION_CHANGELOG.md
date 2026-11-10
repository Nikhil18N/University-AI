# Implementation Changelog: Restoring Chatbot Quality on Main

**Branch:** `fix/restore-rollback-chat-quality`  
**Base Commit:** `948c1a74890d576a8ea72c8e30d21c002be20188`  
**Date:** November 11, 2026  

---

## 1. Overview of Changes

All modifications were implemented with minimal, surgical precision directly on top of `948c1a7` without discarding any newer features, schemas, or UI upgrades.

---

## 2. File-by-File Changelog

### `prompts/system.md`
- **Location:** Section 6 (Admission Guidance Flow & Student Skepticism).
- **Changes:**
  - Decoupled incoming prospective student lead inquiries ("I came through an ad", "Saw your post") from adversarial student skepticism handling.
  - Instructed the model to welcome ad visitors warmly and naturally ask for their program of interest and 12th/Intermediate percentage.
  - Softened anti-enthusiasm negative constraints while preserving strict factual accuracy against 2026-27 university regulations.
- **Why:** Restores the natural conversational lead qualification demonstrated in `rollback_resp.pdf`.

### `prompts/rag.md`
- **Location:** Rules & Directives section (lines 24–45).
- **Changes:**
  - Created a dedicated section for "Prospective Student & Ad Inquiries" instructing warm, direct welcome messaging.
  - Streamlined skepticism handling so the bot shares objective highlights without robotic or formulaic answers.
  - Re-emphasized celebrating qualifying student scores warmly.
- **Why:** Eliminates cognitive conflicts in LLM instructions and restores engaging senior-guide conversation.

### `backend/app/services/suggestion_service.py`
- **Location:** `CAMPUS_SUGGESTIONS`, `SRIX_SUGGESTIONS`, and lines 235–270.
- **Changes:**
  - Added dedicated exploratory suggestion sets: `CAMPUS_SUGGESTIONS` and `SRIX_SUGGESTIONS`.
  - Fixed false-positive bug where any response mentioning `"campus"` defaulted to `CAMPUS_VIDEO_OFFER_SUGGESTIONS` (`["🎥 Yes, watch video", "❌ No, thanks"]`).
  - Ensured binary video chips appear strictly when a video tour is actively offered in the assistant's answer.
- **Why:** Prevents trapping users in unintended binary Yes/No loops on non-video turns.

### `backend/app/services/card_service.py`
- **Location:** `generate_cards` function (lines 325–375).
- **Changes:**
  - Re-enabled strict single-category scoped fee cards (`TRANSPORT_FEE_CARD`, `HOSTEL_FEE_CARD`, `EXAM_FEE_CARD`, `ADMISSION_FEE_CARD`, `MERIT_SCHOLARSHIP_CARD`, `BTECH_CSE_FEE_CARD`, `BTECH_ACADEMIC_FEE_CARD`).
  - Preserved strict category isolation (never cross-contaminates hostel or transport fees into tuition cards).
- **Why:** Fixed 9 failing tests in `test_fee_scoping.py` and `test_admissions_accuracy.py` and restored structured fee cards.

### `backend/app/services/intent_service.py`
- **Location:** `UNIVERSITY_KEYWORDS`, `COMMON_UNIVERSITY_PHRASES`, and `FAST_PATTERNS`.
- **Changes:**
  - Added `"tech"`, `"engineering"`, and `"eligible"` to `UNIVERSITY_KEYWORDS`.
  - Added regex pattern for `"want/plan to join/apply"` to `COMMON_UNIVERSITY_PHRASES`.
  - Expanded `HELP` regex pattern to support `"what can you help me with"`.
- **Why:** Enables fast-path (<1ms) routing for core admission inquiries without falling back to slow LLM classification.

### `backend/tests/test_engagement_features.py`
- **Location:** Line 56 (`test_cards_fee_breakdown`).
- **Changes:**
  - Restored verification of scoped fee card attachment for comprehensive fee inquiries.
- **Why:** Aligns test suite with restored scoped fee card architecture.

### `backend/tests/test_rollback_behavioral_regression.py`
- **Location:** New file under `backend/tests/`.
- **Changes:**
  - Added 9 automated tests verifying:
    1. Greeting classification and warm time-aware salutations.
    2. "How are you" enthusiastic senior-mentor persona.
    3. Multi-turn follow-up greetings ("Hey again!").
    4. Thank-you and capabilities/help responses.
    5. Suggestion chip isolation (no binary video chips when no video is offered).
    6. Exploratory campus suggestion chips.
    7. Admission & eligibility fast classification.
    8. Affirmative follow-up context retention.
    9. Negative follow-up routing.
- **Why:** Guarantees future commits cannot silently regress conversational behavior.

---

## 3. Preserved Features Verification

The following newer features on `main` remain **100% active and untouched**:
- ✅ `ScholarshipCalculatorModal.tsx` & CSS (streamlined marks input, fee roadmap).
- ✅ `LeadAuthModal.tsx` & CSS (lead authentication modal).
- ✅ `AdminPage.tsx` & `admin_service.py` (admin analytics, lead management, export).
- ✅ `Icons.tsx` (minimalist executive university vector icons).
- ✅ `ThinkingIndicator.tsx` (5-stage thinking animation).
- ✅ Redis client connection pooling and response caching.
- ✅ Dynamic IST greeting calculation.
- ✅ Staff contact number sanitization (scrubbing personal mobiles).
- ✅ Async SQLAlchemy database pooler configurations.
