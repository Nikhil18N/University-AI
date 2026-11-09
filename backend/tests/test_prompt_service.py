"""Tests for prompt service."""

import pytest
from app.services.prompt_service import load_prompt, render_prompt, clear_cache


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


def test_load_prompt_pack_templates():
    clear_cache()
    for name in ["router", "persona", "factual", "persuasive", "chitchat", "sensitive", "out_of_scope", "merge"]:
        content = load_prompt(name)
        assert content is not None
        assert len(content) > 20


def test_render_factual_with_automatic_persona():
    clear_cache()
    rendered = render_prompt(
        "factual",
        structured_facts="Tuition: ₹1,47,500/sem",
        retrieved_chunks="Source 1: CSE",
        student_profile="interests: robotics",
        part_text="What are the fees for CSE?",
    )
    assert "SRU Buddy" in rendered
    assert "Tuition: ₹1,47,500/sem" in rendered
    assert "What are the fees for CSE?" in rendered
    assert "{{persona}}" not in rendered
    assert "{{part_text}}" not in rendered
