"""Automated Factuality & Hallucination Verification Service.

Verifies generated answers and RAG responses against the official ground truth
assertions extracted from SR University handbooks (admissions, attendance, fees,
scholarships, and placements).
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any

from app.services.guardrail_service import (
    PERCENT_PATTERN,
    URL_PATTERN,
    verify_numeric_faithfulness,
    verify_url_faithfulness,
)

logger = logging.getLogger(__name__)


@dataclass
class FactualityBenchmarkItem:
    policy_id: str
    topic: str
    question: str
    handbook_source: str
    ground_truth_claims: list[str]
    required_keywords_any: list[list[str]]  # Each sublist must have at least 1 keyword match
    prohibited_hallucinations: list[tuple[re.Pattern, str]]  # (regex, reason)
    allowed_numbers: list[str]


@dataclass
class FactualityEvaluationResult:
    policy_id: str
    is_faithful: bool
    score: float  # 0.0 to 1.0
    detected_hallucinations: list[str] = field(default_factory=list)
    missing_required_facts: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    unsupported_urls: list[str] = field(default_factory=list)
    explanation: str = ""


# Canonical ground-truth benchmark policies from data/handbook/
BENCHMARK_POLICIES: dict[str, FactualityBenchmarkItem] = {
    "btech_eligibility_cutoff": FactualityBenchmarkItem(
        policy_id="btech_eligibility_cutoff",
        topic="Admissions & Eligibility",
        question="What is the minimum eligibility criteria for B.Tech admission at SR University?",
        handbook_source="data/handbook/08_admissions_fees_scholarships_and_eligibility.md",
        ground_truth_claims=[
            "Minimum 60% aggregate marks in 10+2 / Intermediate PCM",
            "Corresponds to 600 marks out of 1000",
            "Applies uniformly across all engineering branches",
        ],
        required_keywords_any=[
            ["60%", "60 percent", "600"],
            ["10+2", "12th", "intermediate", "pcm", "qualifying"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"(?:minimum\s+)?(?:50|55|70|75|80)\s*%\s*(?:cutoff|aggregate|marks|percentage|required|eligibility)", re.I),
                "Hallucinated cutoff: B.Tech cutoff is strictly 60%, not 50%, 55%, 70%, 75%, or 80%",
            ),
            (
                re.compile(r"\b(599|590|580|550|500)\s*(?:out\s+of\s+1000|\/1000)?\s*(?:is\s+eligible|qualifies|accepted)\b", re.I),
                "Hallucination: Marks below 600/1000 claimed as eligible",
            ),
        ],
        allowed_numbers=["60%", "600", "1000", "10+2", "12th", "8331003030", "8331004040"],
    ),
    "direct_admission_entrance_exam": FactualityBenchmarkItem(
        policy_id="direct_admission_entrance_exam",
        topic="Admissions & Entrance Exams",
        question="Do I need to write JEE Main or EAMCET for direct/management quota admission?",
        handbook_source="data/handbook/08_admissions_fees_scholarships_and_eligibility.md",
        ground_truth_claims=[
            "No entrance exam is required for direct / management quota admission",
            "Admission is based purely on 10+2 / Intermediate board marks and seat availability",
        ],
        required_keywords_any=[
            ["no entrance exam", "not require", "do not need", "no need", "without any entrance", "not mandatory", "purely on"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b(must\s+(?:write|appear|take|submit|have)|mandatory|compulsory)\b.*?\b(jee|eamcet)\b.*?\b(direct|management)\b", re.I),
                "Hallucination: Claiming JEE or EAMCET is mandatory for direct/management quota",
            ),
        ],
        allowed_numbers=["10+2", "12th"],
    ),
    "attendance_minimum_requirement": FactualityBenchmarkItem(
        policy_id="attendance_minimum_requirement",
        topic="Attendance Regulations",
        question="What is the minimum attendance required at SR University, and is 50% attendance allowed?",
        handbook_source="data/handbook/07_attendance_and_detention_policy.md",
        ground_truth_claims=[
            "Minimum prescribed attendance is 75% in each individual course",
            "50% attendance is strictly NOT allowed or recognized",
        ],
        required_keywords_any=[
            ["75%", "75 percent"],
            ["not allow", "never allow", "false", "no", "not permitted", "strictly not", "myth", "cannot"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b50\s*%\s*attendance\s*(?:is\s+)?(?:allowed|permitted|accepted)\b", re.I),
                "Hallucination: Claiming 50% attendance is allowed (handbook explicitly rejects this myth)",
            ),
        ],
        allowed_numbers=["75%", "100%", "25%", "50%"],
    ),
    "attendance_condonation_policy": FactualityBenchmarkItem(
        policy_id="attendance_condonation_policy",
        topic="Medical Condonation & Detention",
        question="Can attendance below 75% be condoned if I was hospitalized?",
        handbook_source="data/handbook/07_attendance_and_detention_policy.md",
        ground_truth_claims=[
            "Condonation board can grant 10% to 25% waiver for attendance between 65% and 74%",
            "Requires official medical certificates and hospital discharge summaries",
            "Strictly below 65% results in detention ('R' grade, barred from End Semester Exam)",
        ],
        required_keywords_any=[
            ["condonation", "condone", "waiver"],
            ["65%", "74%", "65"],
            ["medical", "hospital", "doctor"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b(below\s+65%|under\s+65%|less\s+than\s+65%)\s*(can\s+be\s+condoned|is\s+condoned|allowed\s+condonation)\b", re.I),
                "Hallucination: Claiming attendance strictly below 65% can be condoned",
            ),
        ],
        allowed_numbers=["65%", "74%", "75%", "10%", "25%", "71%"],
    ),
    "btech_cse_tuition_fee": FactualityBenchmarkItem(
        policy_id="btech_cse_tuition_fee",
        topic="Fee Structure",
        question="What is the annual tuition fee for B.Tech Computer Science (CSE)?",
        handbook_source="data/handbook/08_admissions_fees_scholarships_and_eligibility.md",
        ground_truth_claims=[
            "Annual tuition fee for CSE is Rs. 2,10,000/- per year",
            "Semester-wise fee is Rs. 1,05,000/- per semester",
        ],
        required_keywords_any=[
            ["2,10,000", "210000", "2.10 lakh", "2.1 lakh", "2.10lakh", "2,10,000/-"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b(?:rs\.?|inr|₹)?\s*(?:50,000|1,00,000|3,50,000|5,00,000|5\s*lakhs?|10\s*lakhs?)\b", re.I),
                "Hallucination: Fabricated tuition fee number for CSE",
            ),
        ],
        allowed_numbers=["2,10,000", "1,05,000", "2.1", "2.10", "20,000", "30,000"],
    ),
    "merit_scholarships_slabs": FactualityBenchmarkItem(
        policy_id="merit_scholarships_slabs",
        topic="Scholarships & Concessions",
        question="What merit scholarships does SR University offer for intermediate students?",
        handbook_source="data/handbook/08_admissions_fees_scholarships_and_eligibility.md",
        ground_truth_claims=[
            "Merit scholarships are awarded strictly based on 12th / Intermediate marks",
            "97%+ (970+ marks out of 1000) qualifies for up to 30% scholarship",
            "90% to 96.9% (900-969 marks out of 1000) qualifies for up to 20% scholarship",
            "Allocated on a first-come, first-served basis",
        ],
        required_keywords_any=[
            ["30%", "30 percent"],
            ["20%", "20 percent"],
            ["97", "970", "90", "900"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b(100%\s*(full\s*scholarship|free\s*ride|guaranteed\s*free))\b", re.I),
                "Hallucination: Claiming 100% full fee waiver is unconditionally guaranteed for all intermediate students",
            ),
        ],
        allowed_numbers=["30%", "20%", "97%", "90%", "970", "1000", "900", "969"],
    ),
    "highest_placement_package": FactualityBenchmarkItem(
        policy_id="highest_placement_package",
        topic="Placements & Recruiters",
        question="What is the highest and average placement package at SR University?",
        handbook_source="data/handbook/08_admissions_fees_scholarships_and_eligibility.md",
        ground_truth_claims=[
            "Highest placement package is 51 LPA, secured at Microsoft",
            "Average placement package is 6 LPA across graduating batches",
            "Top recruiters require minimum CGPA 7.5 and no active backlogs",
        ],
        required_keywords_any=[
            ["51", "51 lpa", "51lpa"],
            ["6", "6 lpa", "6lpa"],
            ["microsoft"],
        ],
        prohibited_hallucinations=[
            (
                re.compile(r"\b(1\s*crore|1\.5\s*crore|75\s*lpa|100\s*lpa)\b", re.I),
                "Hallucination: Fabricated highest placement figure (official is 51 LPA)",
            ),
        ],
        allowed_numbers=["51", "6", "7.5", "51 LPA", "6 LPA"],
    ),
}


def evaluate_answer_factuality(
    policy_id: str,
    answer: str,
    allowed_context: str = "",
) -> FactualityEvaluationResult:
    """Evaluate whether an answer adheres to the ground truth policy and contains no hallucinations."""
    item = BENCHMARK_POLICIES.get(policy_id)
    if not item:
        raise ValueError(f"Unknown policy_id: {policy_id}. Available: {list(BENCHMARK_POLICIES.keys())}")

    detected_hallucinations: list[str] = []
    missing_required_facts: list[str] = []
    ans_lower = answer.lower()

    # 1. Check for prohibited hallucinations
    for pattern, reason in item.prohibited_hallucinations:
        for m in pattern.finditer(answer):
            # If the mention is in the context of explicitly debunking a myth, do not flag
            start = max(0, m.start() - 40)
            end = min(len(answer), m.end() + 40)
            surrounding = answer[start:end].lower()
            if any(debunk in surrounding for debunk in ["strictly false", "myth", "not true", "not allowed", "not permitted", "never allowed", "untrue", "is false", "claim that"]):
                continue
            detected_hallucinations.append(reason)
            break

    # 2. Check for required keyword coverage
    for kw_group in item.required_keywords_any:
        matched = any(kw.lower() in ans_lower for kw in kw_group)
        if not matched:
            missing_required_facts.append(f"Missing required policy reference: one of {kw_group}")

    # 3. Numeric Faithfulness check
    # Check if percentage numbers in the answer belong to allowed numbers or context
    evidence_text = " ".join(item.allowed_numbers) + " " + " ".join(item.ground_truth_claims)
    is_num_faithful, unsupported_nums = verify_numeric_faithfulness(
        answer=answer,
        evidence_text=evidence_text,
        conversation_context=allowed_context,
        question=item.question,
    )

    # 4. URL Faithfulness check
    is_url_faithful, unsupported_urls = verify_url_faithfulness(
        answer=answer,
        evidence_text=evidence_text + " sru.edu.in",
    )

    # Calculate overall score:
    # - Prohibited hallucinations: severe penalty (-0.4 per hallucination)
    # - Missing facts: penalty (-0.15 per missing group)
    # - Unsupported numbers: penalty (-0.2 per unsupported number)
    # - Unsupported URLs: penalty (-0.15 per unsupported url)
    score = 1.0
    if detected_hallucinations:
        score -= len(detected_hallucinations) * 0.4
    if missing_required_facts:
        score -= len(missing_required_facts) * 0.15
    if unsupported_nums:
        score -= len(unsupported_nums) * 0.2
    if unsupported_urls:
        score -= len(unsupported_urls) * 0.15

    score = max(0.0, min(1.0, round(score, 2)))
    is_faithful = (score >= 0.70) and not detected_hallucinations and not unsupported_nums

    reasons = []
    if detected_hallucinations:
        reasons.append(f"Hallucinations detected: {'; '.join(detected_hallucinations)}")
    if missing_required_facts:
        reasons.append(f"Missing facts: {'; '.join(missing_required_facts)}")
    if unsupported_nums:
        reasons.append(f"Unsupported numbers: {', '.join(unsupported_nums)}")
    if unsupported_urls:
        reasons.append(f"Unsupported URLs: {', '.join(unsupported_urls)}")
    if not reasons:
        reasons.append("Answer is 100% faithful and grounded in official handbook documentation.")

    return FactualityEvaluationResult(
        policy_id=policy_id,
        is_faithful=is_faithful,
        score=score,
        detected_hallucinations=detected_hallucinations,
        missing_required_facts=missing_required_facts,
        unsupported_numbers=unsupported_nums,
        unsupported_urls=unsupported_urls,
        explanation=" | ".join(reasons),
    )


def evaluate_all_benchmark_answers(answers: dict[str, str]) -> dict[str, Any]:
    """Evaluate a map of {policy_id: answer_text} across all benchmark policies."""
    results: dict[str, Any] = {}
    total_score = 0.0
    faithful_count = 0

    for policy_id in BENCHMARK_POLICIES:
        answer = answers.get(policy_id, "")
        if not answer:
            results[policy_id] = {
                "score": 0.0,
                "is_faithful": False,
                "explanation": "No answer provided for evaluation.",
            }
            continue

        eval_res = evaluate_answer_factuality(policy_id, answer)
        results[policy_id] = {
            "score": eval_res.score,
            "is_faithful": eval_res.is_faithful,
            "detected_hallucinations": eval_res.detected_hallucinations,
            "missing_required_facts": eval_res.missing_required_facts,
            "unsupported_numbers": eval_res.unsupported_numbers,
            "explanation": eval_res.explanation,
        }
        total_score += eval_res.score
        if eval_res.is_faithful:
            faithful_count += 1

    count = len(BENCHMARK_POLICIES)
    summary = {
        "total_policies": count,
        "faithful_answers": faithful_count,
        "faithfulness_rate": round((faithful_count / count) * 100, 1),
        "mean_score": round(total_score / count, 2),
        "policy_evaluations": results,
    }
    return summary
