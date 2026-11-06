"""Tests for the upgraded system prompt and RAG prompt."""

from pathlib import Path
from app.services.prompt_service import load_prompt, render_prompt


def test_system_prompt_contains_all_core_sections():
    """Verify system.md contains all core intelligence upgrade sections."""
    prompt = load_prompt("system")
    assert "## 1. Identity & Role" in prompt
    assert "## 2. Core Principles" in prompt
    assert "## 3. Knowledge Grounding Rules" in prompt
    assert "## 4. Student Context & Memory" in prompt
    assert "## 5. Conversation Behaviour & Anti-Repetition" in prompt
    assert "## 6. Admission Guidance Flow" in prompt
    assert "## 7. Specialist Workflows & Domain Standards" in prompt
    assert "## 8. Out-of-Scope & Privacy Boundaries" in prompt
    assert "## 9. Response Style & Markdown Standards" in prompt
    assert "## 10. Final Quality Checklist" in prompt


def test_system_prompt_contains_critical_rules():
    """Verify key facts and behavioral rules are present."""
    prompt = load_prompt("system")
    assert "SRU Buddy" in prompt
    assert "60% aggregate marks" in prompt
    assert "Fully Flexible Credit System" in prompt
    assert "Strictly No Double Questions" in prompt


def test_rag_prompt_contains_core_formatting():
    """Verify rag.md contains the core formatting standards."""
    prompt = load_prompt("rag")
    assert "MARKDOWN FORMATTING STANDARDS" in prompt

