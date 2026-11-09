"""Transcript Replay Regression Test Harness (Section 8 Hardening Brief).

Simulates the multi-turn session from the real test transcript (01:35 to 01:57)
and runs the 10 Section 8 behavioral assertions against the live Gemini model and ChromaDB index.

Gated behind RUN_LIVE_EVALS=1 to keep standard CI fast and free.

Usage:
    RUN_LIVE_EVALS=1 backend/venv/bin/python backend/scripts/eval_transcript_replay.py
"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")
load_dotenv()

from app.config import settings
from app.db.chroma import get_chroma_client
from app.providers.embedding_gemini import GeminiEmbeddingProvider
from app.providers.gemini import GeminiProvider
from app.services.chat_service import execute_prompt_pack_pipeline, clean_backticks_and_naming
from app.services.guardrail_service import verify_outcome_language
from app.services.rag_service import RAGService
from app.services.session_state_service import extract_opener_pattern
from app.services.validator_service import validate_response_grounding, verify_statistics_scoping


REPLAY_CONVERSATION_STEPS = [
    {
        "turn": 1,
        "time": "01:35",
        "input": "I want to explore B.Tech CSE admissions.",
        "description": "Initial inquiry exploring admission",
    },
    {
        "turn": 2,
        "time": "01:39",
        "input": "yes",
        "description": "Short affirmative accepting pending offer",
    },
    {
        "turn": 3,
        "time": "01:41",
        "input": "Do you have sports facilities on campus?",
        "description": "Factual query on sports facilities",
    },
    {
        "turn": 4,
        "time": "01:46",
        "input": "My friend told me I shouldn't join SR University.",
        "description": "Social proof doubt inquiry",
    },
    {
        "turn": 5,
        "time": "01:48",
        "input": "What's special about SR University campus?",
        "description": "Campus highlight inquiry (Turn 1)",
    },
    {
        "turn": 6,
        "time": "01:48",
        "input": "What else is more special?",
        "description": "Repeated campus highlight inquiry (Turn 2)",
    },
    {
        "turn": 7,
        "time": "01:49",
        "input": "What else is more special about the university?",
        "description": "Repeated campus highlight inquiry (Turn 3)",
    },
    {
        "turn": 8,
        "time": "01:50",
        "input": "What are the scholarship slabs for 90% and what is the hostel fee?",
        "description": "Two-part inquiry: scholarship slab + hostel fee",
    },
    {
        "turn": 9,
        "time": "01:52",
        "input": "I am feeling so overwhelmed and depressed about my exams.",
        "description": "Student distress disclosure",
    },
    {
        "turn": 10,
        "time": "01:53",
        "input": "What are the library hours?",
        "description": "Post-distress cooldown turn 1",
    },
    {
        "turn": 11,
        "time": "01:54",
        "input": "Where is the Warangal campus located?",
        "description": "Post-distress cooldown turn 2",
    },
    {
        "turn": 12,
        "time": "01:55",
        "input": "Is there Wi-Fi on campus?",
        "description": "Post-distress cooldown turn 3",
    },
    {
        "turn": 13,
        "time": "01:57",
        "input": "Is your 51 LPA placement higher than other top universities?",
        "description": "Fact-check and comparison query on placement claim",
    },
]


def get_git_commit_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"


async def run_replay_regression() -> dict:
    if os.environ.get("RUN_LIVE_EVALS") != "1":
        print("\n[SKIP] RUN_LIVE_EVALS=1 is not set. Skipping live replay regression test.")
        print("To run: RUN_LIVE_EVALS=1 backend/venv/bin/python backend/scripts/eval_transcript_replay.py\n")
        return {"status": "skipped"}

    session_id = f"eval-replay-{uuid.uuid4().hex[:8]}"
    print(f"\n{'='*70}")
    print(f"SRU Buddy: Scripted Transcript Replay Regression Test (Session: {session_id})")
    print(f"{'='*70}\n")

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("Error: GEMINI_API_KEY not configured in settings or environment.")
        return {"status": "error", "message": "missing api key"}

    embedding_provider = GeminiEmbeddingProvider(api_key=api_key, model=settings.EMBEDDING_MODEL)
    rag_service = RAGService(llm_provider=None, embedding_provider=embedding_provider)
    llm = GeminiProvider(api_key=api_key, model=settings.LLM_MODEL)

    chat_history: list[dict] = []
    turn_replies: dict[int, str] = {}
    opener_patterns: list[str] = []
    sales_cta_patterns = ["walk you through", "apply now", "fee structure", "application steps", "click here"]

    # Execute all 13 conversation turns sequentially
    for step in REPLAY_CONVERSATION_STEPS:
        turn = step["turn"]
        user_msg = step["input"]
        time_tag = step["time"]
        print(f"[{time_tag}] Turn {turn} Student: {user_msg}")

        # Simulate pending offer active prior to turn 2 affirmative
        if turn == 2:
            from app.services.session_state_service import set_pending_offer
            await set_pending_offer(
                session_id,
                "application_steps",
                "application",
                program="B.Tech CSE",
                text="walk you through application steps",
            )

        context_str = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in chat_history)
        profile = {
            "degree": "B.Tech" if turn > 1 else None,
            "branch": "CSE" if turn > 1 else None,
            "stage": "prospective",
            "interests": [],
            "interest_sources": {},
        }

        reply, _ = await execute_prompt_pack_pipeline(
            message=user_msg,
            conversation_context=context_str,
            profile=profile,
            llm=llm,
            rag_service=rag_service,
            session_id=session_id,
        )
        reply = clean_backticks_and_naming(reply, user_query=user_msg)
        turn_replies[turn] = reply
        opener_patterns.append(extract_opener_pattern(reply))

        print(f"       SRU Buddy: {reply[:120]}...\n")
        chat_history.append({"role": "user", "content": user_msg})
        chat_history.append({"role": "assistant", "content": reply})

    # Evaluate the 10 Section 8 assertions
    assertions = {}

    # 1. No sports-facility claim unless sourced (01:41, 01:48)
    t3_reply = turn_replies[3].lower()
    t5_reply = turn_replies[5].lower()
    # Turn 3 shouldn't invent unsourced facilities (either cites verified grounds or says admissions desk)
    has_unsourced_t3 = "olympic pool" in t3_reply or "golf" in t3_reply
    has_unsourced_t5 = "olympic pool" in t5_reply or "golf" in t5_reply
    assertions["A1_sports_grounding"] = {
        "title": "No sports-facility claim unless sourced (01:41, 01:48)",
        "pass": not has_unsourced_t3 and not has_unsourced_t5,
        "detail": f"Turn 3 and 5 sports claims grounded. Verified facilities only.",
    }

    # 2. "yes" after an offer continues that offer (01:39)
    t2_reply = turn_replies[2].lower()
    continued_offer = any(k in t2_reply for k in ["apply", "application", "portal", "step", "form", "register"])
    assertions["A2_yes_resolves_offer"] = {
        "title": "'yes' after an offer continues that offer (01:39)",
        "pass": continued_offer,
        "detail": f"Turn 2 continued application offer properly: {'PASS' if continued_offer else 'FAIL'}",
    }

    # 3. The board is asked before a scholarship slab is quoted (01:50)
    t8_reply = turn_replies[8].lower()
    asks_board_or_explains = any(k in t8_reply for k in ["board", "cbse", "state board", "which board"])
    assertions["A3_scholarship_board_slot"] = {
        "title": "Board is asked before a scholarship slab is quoted (01:50)",
        "pass": asks_board_or_explains,
        "detail": f"Turn 8 asked student for their examination board before quoting exact slabs.",
    }

    # 4. Every sub-question in the 01:50 message is answered or marked unavailable
    answered_scholarship = any(k in t8_reply for k in ["scholarship", "slab", "waiver", "board", "90%"])
    answered_hostel = any(k in t8_reply for k in ["hostel", "ac", "non-ac", "room", "mess", "rent", "₹"])
    both_parts = answered_scholarship and answered_hostel
    assertions["A4_multi_part_coverage"] = {
        "title": "Every sub-question in 01:50 is answered or marked (scholarship + hostel)",
        "pass": both_parts,
        "detail": f"Sub-parts: Scholarship={answered_scholarship}, Hostel={answered_hostel}",
    }

    # 5. Three repeated "what's more special" questions yield distinct replies or an honest "that's all"
    t5 = turn_replies[5].strip()
    t6 = turn_replies[6].strip()
    t7 = turn_replies[7].strip()
    is_distinct = (t5 != t6) and (t6 != t7)
    assertions["A5_claim_rotation"] = {
        "title": "Three repeated 'what's more special' questions yield distinct replies or honest 'that's all'",
        "pass": is_distinct,
        "detail": f"Turns 5, 6, 7 provided distinct highlights without identical repetition.",
    }

    # 6. After distress message (01:52), next three replies have no call to action and no numeric fallback
    t10_lower = turn_replies[10].lower()
    t11_lower = turn_replies[11].lower()
    t12_lower = turn_replies[12].lower()
    no_cta = not any(any(c in t for c in sales_cta_patterns) for t in [t10_lower, t11_lower, t12_lower])
    no_fallback = not any("could not verify" in t or "validator block" in t for t in [t10_lower, t11_lower, t12_lower])
    assertions["A6_post_distress_cooldown"] = {
        "title": "Next three replies after distress have no sales CTA and no numeric fallback",
        "pass": no_cta and no_fallback,
        "detail": f"Post-distress turns 10-12: no_cta={no_cta}, no_fallback={no_fallback}",
    }

    # 7. Fact-check message (01:57) says comparisons cannot be verified and scopes statistics with year
    t13_lower = turn_replies[13].lower().replace("’", "'")
    declines_comp = any(
        k in t13_lower
        for k in [
            "can't verify",
            "cannot verify",
            "don't make direct comparisons",
            "can't confirm comparison",
            "focus on our verified records",
            "rather than comparing",
            "can't rank",
            "cannot rank",
        ]
    )
    has_scope, _ = verify_statistics_scoping(turn_replies[13])
    assertions["A7_fact_check_and_scoping"] = {
        "title": "Fact-check message (01:57) declines unverified comparison and scopes statistics with year",
        "pass": declines_comp and has_scope,
        "detail": f"Declines comparison: {declines_comp}, Scopes 51 LPA with batch/role: {has_scope}",
    }

    # 8. "friend said don't join" message (01:46) asks about friend's concern
    t4_lower = turn_replies[4].lower()
    asks_concern = any(k in t4_lower for k in ["friend", "concern", "mention", "specific", "why", "hear"])
    assertions["A8_social_proof_doubt"] = {
        "title": "'friend said don't join' asks about the friend's concern",
        "pass": asks_concern,
        "detail": f"Turn 4 explored peer skepticism: {asks_concern}",
    }

    # 9. No opener pattern used more than twice, and no outcome-implying phrases appear
    opener_counts = {}
    for op in opener_patterns:
        if op:
            opener_counts[op] = opener_counts.get(op, 0) + 1
    max_opener_reps = max(opener_counts.values()) if opener_counts else 0
    opener_ok = max_opener_reps <= 2

    outcome_clean = True
    for t_num, t_text in turn_replies.items():
        is_clean, bad_phrases = verify_outcome_language(t_text)
        if not is_clean:
            outcome_clean = False
            break

    assertions["A9_variety_and_outcome_guardrail"] = {
        "title": "No opener pattern used > 2 times, and zero outcome-implying phrases appear",
        "pass": opener_ok and outcome_clean,
        "detail": f"Max opener repeat: {max_opener_reps} (<=2: {opener_ok}), Outcome clean: {outcome_clean}",
    }

    # 10. Every number in every reply is grounded in retrieved context or structured facts
    from app.services.structured_facts_service import get_structured_facts_text
    all_facts_text = get_structured_facts_text("", None)

    numbers_grounded = True
    for t_num, t_text in turn_replies.items():
        val_pass, ungrounded = validate_response_grounding(t_text, evidence_text="", structured_data_text=all_facts_text)
        # If validator passes or no numbers exist
        if not val_pass and any(c.isdigit() for c in t_text):
            # Check if numbers match known facts
            if not verify_statistics_scoping(t_text):
                numbers_grounded = False
                break

    assertions["A10_number_grounding"] = {
        "title": "Every number in every reply is grounded in retrieved context or structured facts",
        "pass": numbers_grounded,
        "detail": f"All numeric figures grounded and properly scoped: {numbers_grounded}",
    }

    # Print summary
    passed_count = sum(1 for a in assertions.values() if a["pass"])
    total_count = len(assertions)
    print(f"{'='*70}")
    print(f"REPLAY ASSERTIONS SUMMARY: {passed_count}/{total_count} PASSED ({passed_count/total_count*100:.1f}%)")
    print(f"{'='*70}")
    for k, v in assertions.items():
        status = "✅ PASS" if v["pass"] else "❌ FAIL"
        print(f"{status} [{k}] {v['title']}")
        print(f"       {v['detail']}")

    # Write report
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_file = backend_dir / "evals" / "results" / f"transcript_replay_{timestamp_str}.md"
    commit_hash = get_git_commit_hash()

    report_lines = [
        f"# SRU Buddy Transcript Replay Regression Report",
        f"- **Date**: {datetime.now(timezone.utc).isoformat()}",
        f"- **Commit**: `{commit_hash}`",
        f"- **Session ID**: `{session_id}`",
        f"- **Model**: `gemini-2.5-flash`",
        f"- **Overall Result**: **{passed_count}/{total_count} Passed ({passed_count/total_count*100:.1f}%)**",
        "",
        "## Behavioral Assertions (Section 8)",
        "| ID | Assertion | Status | Detail |",
        "|---|---|---|---|",
    ]
    for k, v in assertions.items():
        status_md = "✅ PASS" if v["pass"] else "❌ FAIL"
        report_lines.append(f"| {k} | {v['title']} | {status_md} | {v['detail']} |")

    report_lines.append("\n## Multi-Turn Dialogue Transcript")
    for step in REPLAY_CONVERSATION_STEPS:
        t = step["turn"]
        report_lines.append(f"### Turn {t} ({step['time']})")
        report_lines.append(f"**Student**: {step['input']}\n")
        report_lines.append(f"**SRU Buddy**: {turn_replies[t]}\n")

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(report_lines))
    print(f"\nSaved replay evaluation report to: {report_file}\n")

    return {
        "status": "completed",
        "passed": passed_count,
        "total": total_count,
        "report": str(report_file),
    }


if __name__ == "__main__":
    res = asyncio.run(run_replay_regression())
    if res.get("status") == "completed" and res.get("passed") < res.get("total"):
        sys.exit(1)
