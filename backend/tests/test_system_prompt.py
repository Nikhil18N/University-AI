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


def test_system_prompt_about_sru_8_pillars():
    """Verify system.md defines all 8 core pillars for About SRU inquiries."""
    prompt = load_prompt("system")
    assert "1. **CAMPUS LIFE**" in prompt
    assert "2. **FACULTY**" in prompt
    assert "3. **INFRA" in prompt
    assert "4. **PLACEMENTS**" in prompt
    assert "5. **RANKINGS**" in prompt
    assert "6. **RESEARCH**" in prompt
    assert "7. **ACADEMIC**" in prompt
    assert "8. **HOSTEL - LIVING & DINING**" in prompt
    assert "As the academic day comes to an end, the living and learning experience continues" in prompt


def test_170_acres_present_in_prompts():
    """Verify 170 acres is grounded in system and rag prompts, and 150 acres is absent."""
    system_prompt = load_prompt("system")
    rag_prompt = load_prompt("rag")
    assert "170 acres" in system_prompt or "170-acre" in system_prompt
    assert "170 acres" in rag_prompt or "170-acre" in rag_prompt
    assert "150 acres" not in system_prompt
    assert "150-acre" not in system_prompt
    assert "150 acres" not in rag_prompt
    assert "150-acre" not in rag_prompt


def test_website_facts_grounded_in_prompts():
    """Verify official website facts are grounded in prompts."""
    prompt = load_prompt("system")
    assert "Sri Rajeshwara Educational Society" in prompt
    assert "Deepak Garg" in prompt
    assert "9,300+" in prompt
    assert "2,900+" in prompt
    assert "UI GreenMetric" in prompt
    assert "Sparkrill" in prompt


