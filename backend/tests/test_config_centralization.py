"""Tests for Task T7: Centralization of university contacts, helplines, and retrieval boosts."""

from pathlib import Path
from unittest.mock import patch
import pytest

from app.config import settings
from app.services.prompt_service import clear_cache, load_prompt, render_prompt
from app.services.rag_service import load_retrieval_boosts
from app.services.validator_service import get_dynamic_allowed_numbers, validate_response_grounding


def test_admissions_phone_propagation_in_prompts(monkeypatch):
    """Changing ADMISSIONS_PHONE in config must dynamically propagate into rendered prompts."""
    test_phone = "0870-9998877"
    monkeypatch.setattr(settings, "ADMISSIONS_PHONE", test_phone)
    clear_cache()

    for prompt_name in ["sensitive", "factual", "persona", "system", "rag"]:
        content = load_prompt(prompt_name)
        assert test_phone in content, f"Expected {test_phone} in {prompt_name}.md prompt"
        assert "{admissions_phone}" not in content, f"Uninterpolated placeholder found in {prompt_name}.md"


def test_admissions_phone_propagation_in_validator(monkeypatch):
    """Changing ADMISSIONS_PHONE must dynamically update the validator's whitelist."""
    test_phone = "0870-7766554"
    monkeypatch.setattr(settings, "ADMISSIONS_PHONE", test_phone)

    allowed = get_dynamic_allowed_numbers()
    assert test_phone in allowed
    assert "7766554" in allowed

    # Response citing the new phone number must pass validator grounding
    is_valid, ungrounded = validate_response_grounding(
        f"You can reach out to admissions at {test_phone}."
    )
    assert is_valid is True
    assert ungrounded == []


def test_crisis_helplines_propagation(monkeypatch):
    """Custom crisis helplines in config must be accepted by validator without rejection."""
    custom_helplines = [
        {
            "name": "CustomHelpline",
            "number": "19999",
            "alt_number": "1800-999-9999",
            "hours": "24/7",
            "languages": "English",
        }
    ]
    monkeypatch.setattr(settings, "CRISIS_HELPLINES", custom_helplines)

    allowed = get_dynamic_allowed_numbers()
    assert "19999" in allowed
    assert "1800-999-9999" in allowed

    is_valid, _ = validate_response_grounding("Please call CustomHelpline at 19999 immediately.")
    assert is_valid is True


def test_rag_service_loads_boosts_from_yaml():
    """rag_service must load title and keyword boosts from backend/app/data/retrieval_boosts.yaml."""
    boosts = load_retrieval_boosts()
    assert isinstance(boosts, dict)
    assert "title_boosts" in boosts
    assert "keyword_boosts" in boosts

    title_terms = [t for tb in boosts["title_boosts"] for t in tb.get("match_terms", [])]
    assert any("verified knowledge registry" in t.lower() for t in title_terms)

    keyword_terms = [k for kb in boosts["keyword_boosts"] for k in kb.get("match_terms", [])]
    assert any("51 lpa" in k.lower() for k in keyword_terms)
    assert any("curfew" in k.lower() for k in keyword_terms)


def test_no_hardcoded_contact_literals_in_prompts():
    """Grep verification: prompts/ directory must have zero hardcoded phone or helpline numbers."""
    prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
    forbidden_literals = ["0870-2818333", "14416", "9820466726", "1800-599-0019"]

    for prompt_file in prompts_dir.glob("*.md"):
        raw_text = prompt_file.read_text(encoding="utf-8")
        for literal in forbidden_literals:
            assert literal not in raw_text, (
                f"Found hardcoded literal '{literal}' in {prompt_file.name}. "
                "Must use centralized placeholder (e.g. {admissions_phone})."
            )
