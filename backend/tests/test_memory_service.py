import pytest
from fastapi import HTTPException

from app.services.memory_service import build_extractive_summary, validate_memory_key


def test_memory_allows_non_sensitive_preference_keys():
    assert validate_memory_key(" preferred_program ") == "preferred_program"


def test_memory_rejects_unapproved_keys():
    with pytest.raises(HTTPException) as error:
        validate_memory_key("attendance_percentage")
    assert error.value.status_code == 422


def test_extractive_summary_is_bounded_and_preserves_turn_roles():
    summary = build_extractive_summary(
        [
            {"role": "user", "content": "  I want B.Tech CSE  "},
            {"role": "assistant", "content": "Tell me your academic year."},
        ],
        max_chars=40,
    )
    assert "User: I want B.Tech CSE" in summary
    assert len(summary) <= 40
