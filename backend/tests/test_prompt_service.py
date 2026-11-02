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


def test_missing_prompt_raises():
    clear_cache()
    with pytest.raises(FileNotFoundError):
        load_prompt("non_existent_prompt_xyz")
