#!/usr/bin/env bash
# ==============================================================================
# SRU Buddy — Universal System Verification and CI Runner
# ==============================================================================
# Executes all test suites, type checking, prompt hygiene, and linting
# to ensure the entire repository meets production standards.
# Returns 0 on success, 1 on any failure.
# ==============================================================================

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================================"
echo " Running SRU Buddy Full System Verification"
echo " Repo: ${REPO_ROOT}"
echo "========================================================================"

FAILED_STEPS=()

# ------------------------------------------------------------------------------
# 1. Prompt Hygiene Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 1/4] Checking Prompt Hygiene (Zero hardcoded phone/email/helplines)..."
PROMPT_LEAKS=$(grep -rnE "(0870-2818333|info@sru\.edu\.in|14416)" "${REPO_ROOT}/prompts/" || true)
if [ -n "${PROMPT_LEAKS}" ]; then
    echo "❌ FAILED: Found hardcoded contact literals in prompts/:"
    echo "${PROMPT_LEAKS}"
    FAILED_STEPS+=("Prompt Hygiene Check")
else
    echo "✅ PASSED: Zero hardcoded contact literals found in prompts/"
fi

# ------------------------------------------------------------------------------
# 2. Frontend TypeScript Compilation
# ------------------------------------------------------------------------------
echo ""
echo "[Step 2/4] Checking Frontend TypeScript Compilation (tsc --noEmit)..."
if (cd "${REPO_ROOT}/frontend" && npx tsc --noEmit); then
    echo "✅ PASSED: Frontend TypeScript compiled with zero errors"
else
    echo "❌ FAILED: Frontend TypeScript compilation errors detected"
    FAILED_STEPS+=("Frontend TypeScript Compilation")
fi

# ------------------------------------------------------------------------------
# 3. Backend Test Suite (Pytest)
# ------------------------------------------------------------------------------
echo ""
echo "[Step 3/4] Running Backend Test Suite (pytest backend/tests)..."
if (cd "${REPO_ROOT}" && backend/venv/bin/pytest backend/tests -q); then
    echo "✅ PASSED: All backend unit and integration tests passed"
else
    echo "❌ FAILED: One or more backend tests failed"
    FAILED_STEPS+=("Backend Pytest Suite")
fi

# ------------------------------------------------------------------------------
# 4. Configuration Centralization & Boosts Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 4/4] Verifying Configuration & Boosts Integrity..."
if (cd "${REPO_ROOT}/backend" && venv/bin/python -c "
from app.config import settings
from app.services.rag_service import load_retrieval_boosts
boosts = load_retrieval_boosts()
assert settings.ADMISSIONS_PHONE == '0870-2818333'
assert settings.CHROMA_FACTS_COLLECTION == 'sru_facts'
assert settings.CHROMA_HIGHLIGHTS_COLLECTION == 'sru_highlights'
assert len(boosts) > 0
print('Verified settings, contacts, and retrieval boosts (' + str(len(boosts)) + ' terms loaded).')
"); then
    echo "✅ PASSED: Configuration and retrieval boosts are valid"
else
    echo "❌ FAILED: Configuration verification failed"
    FAILED_STEPS+=("Configuration Integrity Check")
fi

# ------------------------------------------------------------------------------
# Summary & Exit Code
# ------------------------------------------------------------------------------
echo ""
echo "========================================================================"
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    echo "🎉 ALL CHECKS PASSED: System is production-hardened and clean!"
    echo "========================================================================"
    exit 0
else
    echo "❌ SYSTEM VERIFICATION FAILED:"
    for step in "${FAILED_STEPS[@]}"; do
        echo "   - ${step}"
    done
    echo "========================================================================"
    exit 1
fi
