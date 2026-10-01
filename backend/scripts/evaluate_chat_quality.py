"""Automated Chatbot Quality & Failure Mode Audit Suite.

Systematically audits the 6 core conversational RAG failure modes:
1. Topic Bleed & Cross-Contamination (switching topics without reciting past answers)
2. Coreference & Continuity (preserving entity context in follow-ups)
3. False Premise & Trick Question Refutation (rejecting false rules/myths)
4. Numerical & Boundary Cutoff Precision (strict mathematical comparisons)
5. Intent Hijacking by Courtesy/Slang (preventing 'thanks/bye' from swallowing queries)
6. Slang & Typo Normalization (handling phonetic misspellings and acronyms)
"""

import asyncio
import logging
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings
from app.db.session import async_session_factory
from app.providers.embedding_ollama import OllamaEmbeddingProvider
from app.providers.ollama import OllamaProvider
from app.schemas.chat import ChatRequest
from app.services.chat_service import handle_chat
from app.services.rag_service import RAGService

# Suppress noisy SQL logs during evaluation
logging.basicConfig(level=logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class TestResult:
    suite: str
    case_name: str
    user_query: str
    bot_response: str
    passed: bool
    diagnostic: str
    sources: list[str] = field(default_factory=list)


async def execute_turn(
    message: str,
    session_id: str,
    conv_id: str | None,
    llm: OllamaProvider,
    rag: RAGService,
) -> tuple[str, str | None, list[str]]:
    """Send a message to handle_chat and commit transaction."""
    async with async_session_factory() as db:
        req = ChatRequest(
            message=message,
            session_id=session_id,
            conversation_id=conv_id,
        )
        resp = await handle_chat(db, req, llm, rag)
        await db.commit()
        sources = [f"{s.title} (p.{s.page})" for s in resp.sources] if resp.sources else []
        return resp.answer, resp.conversation_id, sources


async def audit_topic_bleed(llm, rag) -> list[TestResult]:
    """Test 1: Verify switching to a new topic does NOT repeat prior answers."""
    results = []
    session_id = f"audit-bleed-{uuid.uuid4().hex[:6]}"
    conv_id = None

    # Turn 1: Attendance
    ans1, conv_id, _ = await execute_turn("what is the minimum attendence required?", session_id, conv_id, llm, rag)
    # Turn 2: Eligibility
    ans2, conv_id, _ = await execute_turn("eligibility criteria to get a admission?", session_id, conv_id, llm, rag)
    # Turn 3: Topic switch to Placements
    ans3, conv_id, src3 = await execute_turn("about placements", session_id, conv_id, llm, rag)

    # Check for topic bleed in Turn 3
    bleed_keywords = ["100% attendance", "75% in each individual", "minimum prescribed attendance", "minimum of 60% aggregate marks in your qualifying exam"]
    found_bleed = [kw for kw in bleed_keywords if kw.lower() in ans3.lower()]

    has_placements = any(term in ans3.lower() for term in ["placement", "51 lpa", "6 lpa", "cssp", "recruiter", "cjac"])

    passed = len(found_bleed) == 0 and has_placements
    diag = "No topic bleed detected; starts directly with placement data." if passed else f"Topic bleed detected! Repurposed past content: {found_bleed}"

    results.append(TestResult(
        suite="1. Topic Bleed & Cross-Contamination",
        case_name="Topic switch after attendance & admissions to 'about placements'",
        user_query="about placements",
        bot_response=ans3,
        passed=passed,
        diagnostic=diag,
        sources=src3,
    ))
    return results


async def audit_coreference_continuity(llm, rag) -> list[TestResult]:
    """Test 2: Verify pronouns and follow-up attributes are resolved correctly."""
    results = []
    session_id = f"audit-coref-{uuid.uuid4().hex[:6]}"
    conv_id = None

    # Turn 1: Set topic
    _, conv_id, _ = await execute_turn("what is the fee structure for btech cse?", session_id, conv_id, llm, rag)

    # Turn 2: Follow-up pronoun 'that'
    ans2, conv_id, src2 = await execute_turn("can i pay that in installments?", session_id, conv_id, llm, rag)
    has_installment = any(w in ans2.lower() for w in ["semester", "half", "1,05,000", "installment"])
    passed2 = has_installment
    diag2 = "Resolved pronoun 'that' to B.Tech CSE fee and explained semester payments." if passed2 else "Failed to resolve 'that' to fee payment."
    results.append(TestResult(
        suite="2. Coreference & Continuity",
        case_name="Pronoun resolution: 'can i pay that in installments?'",
        user_query="can i pay that in installments?",
        bot_response=ans2,
        passed=passed2,
        diagnostic=diag2,
        sources=src2,
    ))

    # Turn 3: Follow-up attribute: 'what about for other branches?'
    ans3, conv_id, src3 = await execute_turn("what about for other branches?", session_id, conv_id, llm, rag)
    has_other_branch_fee = any(w in ans3.lower() for w in ["20,000", "30,000", "lower", "1,80,000", "1,90,000"])
    passed3 = has_other_branch_fee
    diag3 = "Resolved 'other branches' to fee difference." if passed3 else "Failed to connect 'other branches' to fee structure."
    results.append(TestResult(
        suite="2. Coreference & Continuity",
        case_name="Contextual attribute: 'what about for other branches?'",
        user_query="what about for other branches?",
        bot_response=ans3,
        passed=passed3,
        diagnostic=diag3,
        sources=src3,
    ))

    return results


async def audit_false_premise_refutation(llm, rag) -> list[TestResult]:
    """Test 3: Verify the bot refutes false assumptions rather than accepting them."""
    results = []
    session_id = f"audit-premise-{uuid.uuid4().hex[:6]}"

    test_cases = [
        (
            "Since SR University allows 50% attendance for all engineering students, how do I apply for that relaxation?",
            ["does not allow", "no 50%", "not permit", "mandatory", "75%", "minimum 75"],
            ["apply for 50%", "here are the steps to get 50%"],
            "50% Attendance Myth",
        ),
        (
            "Can boys visit their female classmates inside their hostel rooms for group study?",
            ["strictly prohibited", "not allowed", "prohibited", "cannot enter", "visitor room", "common area"],
            ["yes, boys can", "you can visit between"],
            "Hostel Cross-Gender Room Visit Myth",
        ),
        (
            "Can students ride motorized vehicles or motorbikes inside the campus to reach classes?",
            ["prohibited", "not allowed", "barred", "gate 2", "outside the campus", "bicycles"],
            ["yes, you can ride your motorbike to class"],
            "Motor Vehicles on Campus Myth",
        ),
    ]

    for query, refutation_markers, forbidden_markers, label in test_cases:
        ans, _, src = await execute_turn(query, session_id, None, llm, rag)
        ans_lower = ans.lower()
        refuted = any(m in ans_lower for m in refutation_markers)
        accepted = any(m in ans_lower for m in forbidden_markers)
        passed = refuted and not accepted
        diag = "Correctly refuted false premise." if passed else "Failed to refute false premise; may have adopted misconception."
        results.append(TestResult(
            suite="3. False Premise & Myth Refutation",
            case_name=f"Refute myth: {label}",
            user_query=query,
            bot_response=ans,
            passed=passed,
            diagnostic=diag,
            sources=src,
        ))

    return results


async def audit_numerical_precision(llm, rag) -> list[TestResult]:
    """Test 4: Verify exact numerical comparisons and boundary conditions."""
    results = []
    session_id = f"audit-num-{uuid.uuid4().hex[:6]}"

    test_cases = [
        (
            "i scored 599 marks out of 1000 in my 12th class, am i eligible for btech cse admission?",
            ["59.9%", "below", "short", "60%", "600"],
            ["you are eligible to get admission", "you meet the minimum 60% requirement"],
            "Borderline 12th Score (599/1000)",
        ),
        (
            "60% in 12th, can i get a admission?",
            ["eligible", "meets", "meet"],
            ["59.9%", "shy of", "falls below", "not eligible", "short of the 60%"],
            "Exact Cutoff Match (60% in 12th)",
        ),
        (
            "my score is 61% in 12th class, am i eligible for admission?",
            ["eligible", "meets", "above", "exceeds"],
            ["59.9%", "shy of", "below the required", "not eligible", "short of"],
            "Cutoff Exceeding Score (61% in 12th)",
        ),
        (
            "i have a CGPA of 5.95 with zero backlogs. Can I sit for campus placements?",
            ["below", "not eligible", "short", "6.0", "7.5"],
            ["yes, you can register for placements", "you are eligible with 5.95"],
            "Borderline CGPA for Placements (5.95)",
        ),
    ]

    for query, required_markers, forbidden_markers, label in test_cases:
        ans, _, src = await execute_turn(query, session_id, None, llm, rag)
        ans_lower = ans.lower()
        correct_comparison = any(m in ans_lower for m in required_markers)
        hallucinated_pass = any(m in ans_lower for m in forbidden_markers)
        passed = correct_comparison and not hallucinated_pass
        diag = "Calculated exact percentage/cutoff and stated score falls short." if passed else "Failed numerical boundary comparison!"
        results.append(TestResult(
            suite="4. Numerical & Boundary Precision",
            case_name=f"Boundary check: {label}",
            user_query=query,
            bot_response=ans,
            passed=passed,
            diagnostic=diag,
            sources=src,
        ))

    return results


async def audit_intent_hijacking(llm, rag) -> list[TestResult]:
    """Test 5: Verify conversational courtesy words don't hijack university queries."""
    results = []
    session_id = f"audit-intent-{uuid.uuid4().hex[:6]}"

    test_cases = [
        (
            "thanks a lot bro! btw what is the highest package in placements?",
            ["51 lpa", "microsoft"],
            ["you're welcome! let me know if you need anything else"],
            "Thanks + Placements Query",
        ),
        (
            "bye for now! wait, what time does the library close on weekdays?",
            ["8:30 pm", "library"],
            ["goodbye! have a wonderful day"],
            "Goodbye + Library Timings Query",
        ),
    ]

    for query, required_markers, forbidden_markers, label in test_cases:
        ans, _, src = await execute_turn(query, session_id, None, llm, rag)
        ans_lower = ans.lower()
        answered_query = any(m in ans_lower for m in required_markers)
        only_courtesy = all(m in ans_lower for m in forbidden_markers)
        passed = answered_query and not only_courtesy
        diag = "Successfully routed compound courtesy + question to RAG." if passed else "Courtesy word hijacked intent; question ignored!"
        results.append(TestResult(
            suite="5. Intent Hijacking by Courtesy",
            case_name=f"Mixed message: {label}",
            user_query=query,
            bot_response=ans,
            passed=passed,
            diagnostic=diag,
            sources=src,
        ))

    return results


async def audit_slang_normalization(llm, rag) -> list[TestResult]:
    """Test 6: Verify noisy slang, acronyms, and spelling mistakes retrieve facts."""
    results = []
    session_id = f"audit-slang-{uuid.uuid4().hex[:6]}"

    test_cases = [
        (
            "wht is the min elgblty for btech admsn at sru?",
            ["60%"],
            "Typo: wht, elgblty, admsn",
        ),
        (
            "wht abt scholrshps? if i got 920 mrks can i get any schlrshp?",
            ["20%", "scholarship", "merit"],
            "Slang: wht abt, scholrshps, mrks",
        ),
        (
            "wht is the hostle intime on weekends?",
            ["9:30 pm"],
            "Typo: hostle, intime",
        ),
    ]

    for query, required_markers, label in test_cases:
        ans, _, src = await execute_turn(query, session_id, None, llm, rag)
        ans_lower = ans.lower()
        found_fact = any(m in ans_lower for m in required_markers)
        diag = f"Normalized slang and retrieved verified facts ({required_markers})." if found_fact else "Failed to retrieve correct facts under noisy slang."
        results.append(TestResult(
            suite="6. Slang & Typo Normalization",
            case_name=f"Noisy input: {label}",
            user_query=query,
            bot_response=ans,
            passed=found_fact,
            diagnostic=diag,
            sources=src,
        ))

    return results


async def main():
    print("=" * 80)
    print("STARTING COMPREHENSIVE CHAT QUALITY & FAILURE MODE AUDIT")
    print("=" * 80)

    llm = OllamaProvider(base_url=settings.LLM_BASE_URL, model=settings.LLM_MODEL)
    embedder = OllamaEmbeddingProvider(base_url=settings.LLM_BASE_URL, model=settings.EMBEDDING_MODEL)
    rag = RAGService(llm, embedder)

    all_results: list[TestResult] = []

    print("\n[Running Suite 1] Topic Bleed & Cross-Contamination...")
    all_results.extend(await audit_topic_bleed(llm, rag))

    print("[Running Suite 2] Coreference & Continuity...")
    all_results.extend(await audit_coreference_continuity(llm, rag))

    print("[Running Suite 3] False Premise & Myth Refutation...")
    all_results.extend(await audit_false_premise_refutation(llm, rag))

    print("[Running Suite 4] Numerical & Boundary Precision...")
    all_results.extend(await audit_numerical_precision(llm, rag))

    print("[Running Suite 5] Intent Hijacking by Courtesy...")
    all_results.extend(await audit_intent_hijacking(llm, rag))

    print("[Running Suite 6] Slang & Typo Normalization...")
    all_results.extend(await audit_slang_normalization(llm, rag))

    await llm.close()
    await embedder.close()

    print("\n" + "=" * 80)
    print("AUDIT RESULTS SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for r in all_results if r.passed)
    total_count = len(all_results)

    current_suite = ""
    for r in all_results:
        if r.suite != current_suite:
            current_suite = r.suite
            print(f"\n--- {current_suite} ---")
        status = "PASSED" if r.passed else "FAILED"
        print(f"[{status}] {r.case_name}")
        print(f"   Query: \"{r.user_query}\"")
        print(f"   Diagnostic: {r.diagnostic}")
        if not r.passed:
            print(f"   Response Snippet: {r.bot_response[:180]}...")

    score_pct = (passed_count / total_count) * 100
    print("\n" + "=" * 80)
    print(f"OVERALL AUDIT SCORE: {passed_count}/{total_count} ({score_pct:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
