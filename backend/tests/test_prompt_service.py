"""Tests for prompt service."""

import pytest
from app.services.prompt_service import load_prompt, render_prompt, clear_cache, needs_fee_policy


def test_load_system_prompt():
    clear_cache()
    prompt = load_prompt("system")
    assert prompt is not None
    assert "SR University" in prompt or "University AI" in prompt


def test_load_rag_prompt():
    clear_cache()
    prompt = load_prompt("rag")
    assert prompt is not None
    assert "{{question}}" in prompt
    assert "{{evidence}}" in prompt


def test_render_rag_prompt():
    clear_cache()
    rendered = render_prompt(
        "rag",
        question="When are the semester exams?",
        conversation="",
        evidence="Exams begin May 10th.",
    )
    assert "When are the semester exams?" in rendered
    assert "Exams begin May 10th." in rendered
    assert "{{question}}" not in rendered
    assert "{{evidence}}" not in rendered


def test_missing_prompt_raises():
    clear_cache()
    with pytest.raises(FileNotFoundError):
        load_prompt("non_existent_prompt_xyz")


def test_needs_fee_policy_detection():
    assert needs_fee_policy("What is B.Tech CSE fee?") is True
    assert needs_fee_policy("Do I get a scholarship for 92%?") is True
    assert needs_fee_policy("Tell me about hostel charges") is True
    assert needs_fee_policy("What is the minimum attendance?") is False
    assert needs_fee_policy("Who is the Vice-Chancellor?") is False


def test_load_prompt_omits_fee_policy_when_disabled():
    clear_cache()
    with_fee = load_prompt("system", include_fee_policy=True)
    without_fee = load_prompt("system", include_fee_policy=False)
    assert "FEE POLICY (2027-28" in with_fee
    assert "FEE POLICY (2027-28" not in without_fee
    assert "{{FEE_POLICY}}" not in without_fee
    assert len(with_fee) - len(without_fee) > 5000
