"""Tests for fast_classify expansion with common university phrase patterns (P2-C)."""

import pytest
from app.services.intent_service import fast_classify


@pytest.mark.parametrize(
    "query",
    [
        "tell me about placements",
        "how do I apply for admission",
        "information about hostel facilities",
        "what is the process for enrollment",
        "is there a gym on campus",
        "how much is the fee for btech",
        "difference between CSE and AIML",
        "tell me more about scholarships",
        "how many branches are there in university",
    ],
)
def test_fast_classify_university_queries(query: str):
    """Common university phrases should be recognized instantaneously in fast_classify."""
    result = fast_classify(query)
    assert result == "UNIVERSITY"


@pytest.mark.parametrize(
    "query",
    [
        "what do you think about AI ethics",
        "write me a python script to sort a list",
        "tell me a joke",
    ],
)
def test_fast_classify_non_university_queries_fall_through(query: str):
    """Generic or non-university questions should fall through to LLM (return None or GENERAL_CONVERSATION)."""
    result = fast_classify(query)
    assert result != "UNIVERSITY"
