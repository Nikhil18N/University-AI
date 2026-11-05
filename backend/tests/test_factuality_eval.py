"""Tests for automated factuality and hallucination verification service."""

import pytest
from app.services.factuality_eval_service import (
    BENCHMARK_POLICIES,
    evaluate_all_benchmark_answers,
    evaluate_answer_factuality,
)


class TestFactualityEvaluation:
    def test_btech_cutoff_grounded_answer(self):
        answer = (
            "Candidates seeking admission to B.Tech programs at SR University must have passed "
            "10+2 or Intermediate with a minimum of 50% aggregate marks in PCM (Mathematics, Physics, Chemistry). "
            "This corresponds to 500 marks out of 1000 in standard board examinations."
        )
        res = evaluate_answer_factuality("btech_eligibility_cutoff", answer)
        assert res.is_faithful is True
        assert res.score >= 0.85
        assert res.detected_hallucinations == []

    def test_btech_cutoff_catches_wrong_cutoff_hallucination(self):
        answer = (
            "At SR University, the minimum 75% cutoff is required for B.Tech admission."
        )
        res = evaluate_answer_factuality("btech_eligibility_cutoff", answer)
        assert res.is_faithful is False
        assert any("75%" in h for h in res.detected_hallucinations)

    def test_entrance_exam_direct_quota_grounded(self):
        answer = (
            "For direct or management quota admissions, you do not need to write JEE Main or EAMCET. "
            "No entrance exam is required; admission is granted purely based on your 10+2 intermediate marks."
        )
        res = evaluate_answer_factuality("direct_admission_entrance_exam", answer)
        assert res.is_faithful is True
        assert res.score >= 0.85
        assert res.detected_hallucinations == []

    def test_entrance_exam_catches_mandatory_jee_hallucination(self):
        answer = (
            "Students must appear for JEE Main for direct admission into engineering."
        )
        res = evaluate_answer_factuality("direct_admission_entrance_exam", answer)
        assert res.is_faithful is False
        assert any("JEE" in h for h in res.detected_hallucinations)

    def test_attendance_minimum_grounded(self):
        answer = (
            "SR University prescribes a minimum of 75% attendance for every registered course. "
            "Any claim that 50% attendance is allowed is strictly false; 50% attendance is not permitted."
        )
        res = evaluate_answer_factuality("attendance_minimum_requirement", answer)
        assert res.is_faithful is True
        assert res.detected_hallucinations == []

    def test_attendance_minimum_catches_50_percent_myth(self):
        answer = (
            "Yes, 50% attendance is allowed if you submit a request letter to the college."
        )
        res = evaluate_answer_factuality("attendance_minimum_requirement", answer)
        assert res.is_faithful is False
        assert any("50%" in h for h in res.detected_hallucinations)

    def test_attendance_condonation_grounded(self):
        answer = (
            "If your attendance falls marginally below 75% due to hospitalization, the Condonation Board "
            "led by Dean Academics can grant a waiver for attendance between 65% and 74% with valid medical "
            "certificates and discharge summaries. Students strictly below 65% are detained."
        )
        res = evaluate_answer_factuality("attendance_condonation_policy", answer)
        assert res.is_faithful is True
        assert res.score >= 0.85

    def test_attendance_condonation_catches_below_65_waiver_hallucination(self):
        answer = (
            "Students below 65% can be condoned easily by meeting the warden."
        )
        res = evaluate_answer_factuality("attendance_condonation_policy", answer)
        assert res.is_faithful is False
        assert any("below 65%" in h for h in res.detected_hallucinations)

    def test_cse_tuition_fee_grounded(self):
        answer = (
            "The official tuition fee for B.Tech Computer Science and Engineering (CSE) at SR University "
            "is ₹1,47,500 per semester, which equals ₹2,95,000 per year for annual tuition."
        )
        res = evaluate_answer_factuality("btech_cse_tuition_fee", answer)
        assert res.is_faithful is True
        assert res.score >= 0.85

    def test_highest_placement_package_grounded(self):
        answer = (
            "The highest placement package achieved by SR University students is 51 LPA at Microsoft. "
            "The overall average placement package is 6 LPA across engineering batches."
        )
        res = evaluate_answer_factuality("highest_placement_package", answer)
        assert res.is_faithful is True
        assert res.score >= 0.85

    def test_full_benchmark_batch_evaluation(self):
        sample_grounded_answers = {
            "btech_eligibility_cutoff": "Candidates must have 50% in 10+2 PCM (500/1000 marks) for B.Tech.",
            "direct_admission_entrance_exam": "No entrance exam is required for direct quota admission based on 10+2 board marks.",
            "attendance_minimum_requirement": "Students must have 75% attendance. 50% attendance is strictly not allowed.",
            "attendance_condonation_policy": "Attendance between 65% and 74% can be granted condonation for genuine medical reasons.",
            "btech_cse_tuition_fee": "The official tuition fee for CSE is ₹1,47,500 per semester (₹2,95,000 per year).",
            "merit_scholarships_slabs": "Students scoring 92% to 97.99% in intermediate qualify for a 40% merit scholarship for CSE.",
            "highest_placement_package": "The highest package is 51 LPA at Microsoft and average package is 6 LPA.",
        }
        benchmark_summary = evaluate_all_benchmark_answers(sample_grounded_answers)
        assert benchmark_summary["total_policies"] == 7
        assert benchmark_summary["faithful_answers"] == 7
        assert benchmark_summary["faithfulness_rate"] == 100.0
        assert benchmark_summary["mean_score"] >= 0.85
