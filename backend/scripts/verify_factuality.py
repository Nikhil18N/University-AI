# -*- coding: utf-8 -*-
"""
Automated Factuality & Hallucination Verification Script.

Evaluates answers across canonical university policies (admissions, attendance,
fees, scholarships, placements) against official handbooks in data/handbook/.

Usage:
    python -m scripts.verify_factuality
"""

import io
import json
import logging
import os
import sys

# Suppress stderr logging warnings during stress tests
logging.getLogger("app.services.guardrail_service").setLevel(logging.ERROR)

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.factuality_eval_service import (
    BENCHMARK_POLICIES,
    evaluate_all_benchmark_answers,
    evaluate_answer_factuality,
)

# Reference sample grounded answers representing official knowledge base responses
REFERENCE_GROUNDED_RESPONSES = {
    "btech_eligibility_cutoff": (
        "Candidates seeking admission to B.Tech programs at SR University must have passed "
        "10+2 / Intermediate or equivalent with a minimum of 60% aggregate marks in PCM "
        "(Mathematics, Physics, Chemistry). In standard state boards, this corresponds to "
        "600 marks out of 1000. This 60% requirement applies across all branches including CSE, ECE, and AIML."
    ),
    "direct_admission_entrance_exam": (
        "No entrance exam is required for direct or management quota admissions at SR University. "
        "You do not need to write or submit scores for JEE Main, TS EAMCET, or any written entrance test. "
        "Admission is granted purely based on your 10+2 Intermediate board marks and seat availability."
    ),
    "attendance_minimum_requirement": (
        "SR University mandates a minimum prescribed attendance of 75% in each individual course. "
        "Any claim that a 50% attendance relaxation is allowed is completely false; 50% attendance "
        "is not permitted under university academic regulations."
    ),
    "attendance_condonation_policy": (
        "Students with attendance falling marginally below 75% due to severe medical exigencies "
        "or hospitalization can be reviewed by the Condonation Board led by Dean (Academics). "
        "The board may grant a waiver for attendance between 65% and 74% with genuine medical discharge "
        "summaries and payment of the prescribed condonation fee. Attendance strictly below 65% results in detention."
    ),
    "btech_cse_tuition_fee": (
        "The annual tuition fee for B.Tech Computer Science and Engineering (CSE) at SR University "
        "is Rs. 2,10,000/- per year. Tuition fees are payable on a semester basis at Rs. 1,05,000/- per semester."
    ),
    "merit_scholarships_slabs": (
        "SR University awards merit scholarships based on 12th / Intermediate board marks on a first-come, "
        "first-served basis: students with 97%+ (970+ marks out of 1000) are eligible for up to 30% tuition fee scholarship, "
        "and students with 90% to 96.9% (900-969 marks out of 1000) qualify for up to 20% scholarship."
    ),
    "highest_placement_package": (
        "The highest placement package at SR University is 51 LPA, secured by students at Microsoft. "
        "The overall average placement package is 6 LPA across engineering batches. Top recruiter eligibility "
        "requires a minimum CGPA of 7.5 and no active backlogs."
    ),
}

# Negative test suite: synthetic hallucinated answers to test detection engine
SYNTHETIC_HALLUCINATIONS = {
    "btech_eligibility_cutoff": "The minimum 75% cutoff is required for B.Tech CSE admission.",
    "direct_admission_entrance_exam": "Students must write JEE Main for direct admission into engineering.",
    "attendance_minimum_requirement": "50% attendance is allowed if you submit a leave form to your mentor.",
    "attendance_condonation_policy": "Students with attendance below 65% can be condoned by meeting the warden.",
    "btech_cse_tuition_fee": "The annual tuition fee for B.Tech CSE is Rs. 5,00,000 per year.",
    "merit_scholarships_slabs": "SR University guarantees 100% full scholarship free ride for all applicants.",
    "highest_placement_package": "The highest package is 1.5 Crore per annum at Google.",
}


def run_factuality_verification() -> None:
    print("=" * 72)
    print("  SR UNIVERSITY AI -- AUTOMATED FACTUALITY & HALLUCINATION BENCHMARK")
    print("=" * 72)
    print(f"  Benchmark Policies Loaded: {len(BENCHMARK_POLICIES)}")
    print("=" * 72)
    print()

    # 1. Run Grounded Knowledge Base Verification
    print("--- 1. Evaluating Grounded Knowledge Base Reference Answers ---")
    grounded_summary = evaluate_all_benchmark_answers(REFERENCE_GROUNDED_RESPONSES)

    for pid, res in grounded_summary["policy_evaluations"].items():
        policy = BENCHMARK_POLICIES[pid]
        status = "✅ PASS (Faithful)" if res["is_faithful"] else "❌ FAIL (Unfaithful)"
        print(f"\n[{status}] Policy: {policy.topic} ({pid})")
        print(f"  Question : {policy.question}")
        print(f"  Score    : {res['score']:.2f}/1.00")
        print(f"  Notes    : {res['explanation']}")

    print()
    print("-" * 72)
    print(f"  Grounded Verification Rate: {grounded_summary['faithfulness_rate']}% "
          f"({grounded_summary['faithful_answers']}/{grounded_summary['total_policies']} faithful)")
    print(f"  Mean Faithfulness Score   : {grounded_summary['mean_score']:.2f}/1.00")
    print("-" * 72)
    print()

    # 2. Run Hallucination Stress-Test (Negative Controls)
    print("--- 2. Hallucination Detection Negative Control Stress-Test ---")
    hallucinations_caught = 0
    total_stress = len(SYNTHETIC_HALLUCINATIONS)

    for pid, bad_answer in SYNTHETIC_HALLUCINATIONS.items():
        eval_res = evaluate_answer_factuality(pid, bad_answer)
        if not eval_res.is_faithful and eval_res.detected_hallucinations:
            hallucinations_caught += 1
            print(f"  🛡️  CAUGHT: [{pid}] -> {eval_res.detected_hallucinations[0]}")
        else:
            print(f"  ⚠️  MISSED: [{pid}] -> Bad answer was not flagged as hallucination!")

    catch_rate = round((hallucinations_caught / total_stress) * 100, 1)
    print()
    print("-" * 72)
    print(f"  Hallucination Catch Rate : {catch_rate}% ({hallucinations_caught}/{total_stress} caught)")
    print("-" * 72)

    # Save artifact
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    report_path = os.path.join(os.path.dirname(__file__), "factuality_report.json")
    full_report = {
        "grounded_evaluation": grounded_summary,
        "hallucination_stress_test": {
            "total_synthetic_attacks": total_stress,
            "hallucinations_caught": hallucinations_caught,
            "catch_rate_percent": catch_rate,
        },
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)

    print(f"\n  Report saved to: {os.path.abspath(report_path)}\n")


if __name__ == "__main__":
    run_factuality_verification()
