"""Tests for runtime guardrail and hallucination detection service."""

from app.services.guardrail_service import (
    verify_numeric_faithfulness,
    verify_retrieval_confidence,
)


def test_numeric_faithfulness_grounded():
    evidence = "B.Tech admission requires 60% aggregate marks in 10+2 PCM."
    context = ""
    question = "What is the cutoff for B.Tech?"
    answer = "You need a minimum of 60% aggregate marks in 10+2 PCM to be eligible for B.Tech."

    is_faithful, unsupported = verify_numeric_faithfulness(
        answer, evidence, context, question
    )
    assert is_faithful is True
    assert unsupported == []


def test_numeric_faithfulness_from_user_context():
    evidence = "B.Tech requires 60% cutoff."
    context = "user: I scored 78% in 12th PCM\nassistant: Welcome!"
    question = "Can I join CSE?"
    answer = "Since you scored 78%, which exceeds the 60% requirement, you are eligible."

    is_faithful, unsupported = verify_numeric_faithfulness(
        answer, evidence, context, question
    )
    assert is_faithful is True
    assert unsupported == []


def test_numeric_faithfulness_catches_hallucination():
    evidence = "B.Tech requires 60% cutoff."
    context = ""
    question = "im interested in B.Tech"
    # LLM hallucinates that student scored 75%
    answer = "Since you've scored 75% in PCM, you are above the 60% cutoff."

    is_faithful, unsupported = verify_numeric_faithfulness(
        answer, evidence, context, question
    )
    assert is_faithful is False
    assert "75%" in unsupported


def test_retrieval_confidence_threshold():
    # Good distance: 0.2 < 0.5
    high_conf_chunks = [{"content": "...", "distance": 0.2}]
    assert verify_retrieval_confidence(high_conf_chunks, confidence_threshold=0.5) is True

    # Poor distance: 0.8 > 0.5
    low_conf_chunks = [{"content": "...", "distance": 0.8}]
    assert verify_retrieval_confidence(low_conf_chunks, confidence_threshold=0.5) is False

    # Empty chunks
    assert verify_retrieval_confidence([], confidence_threshold=0.5) is False
