"""Tests for chat intent routing."""

from app.services.intent_service import fast_classify


def test_university_query_detection():
    assert fast_classify("What is the exam schedule for next semester?") == "UNIVERSITY"
    assert fast_classify("How much are hostel fees?") == "UNIVERSITY"
    assert fast_classify("What is the attendance policy for CSE department?") == "UNIVERSITY"
    assert fast_classify("Where is the library located?") == "UNIVERSITY"
    assert fast_classify("Tell me about placement opportunities") == "UNIVERSITY"


def test_greeting_and_courtesy_detection():
    assert fast_classify("Hello there") == "GREETING"
    assert fast_classify("Hi, how are you?") == "GREETING"
    assert fast_classify("Good morning") == "GREETING"
    assert fast_classify("Thank you so much") == "THANKS"
    assert fast_classify("Goodbye!") == "GOODBYE"


def test_student_specific_detection():
    assert fast_classify("Can you check my attendance?") == "STUDENT_SPECIFIC"
    assert fast_classify("What is my GPA?") == "STUDENT_SPECIFIC"
    assert fast_classify("What are my grades?") == "STUDENT_SPECIFIC"
    assert fast_classify("Show my timetable") == "STUDENT_SPECIFIC"
    assert fast_classify("Pay my fee") == "STUDENT_SPECIFIC"


def test_general_query_returns_none_for_llm_routing():
    # Fast classifier returns None for open-ended queries so LLM classifier can decide
    assert fast_classify("Write a python function to reverse a string") is None
    assert fast_classify("What is quantum computing?") is None
    assert fast_classify("Who wrote Hamlet?") is None


def test_acknowledgment_detection():
    assert fast_classify("ok") == "ACKNOWLEDGMENT"
    assert fast_classify("got it") == "ACKNOWLEDGMENT"
    assert fast_classify("cool") == "ACKNOWLEDGMENT"
    assert fast_classify("great") == "ACKNOWLEDGMENT"
    assert fast_classify("sure") == "ACKNOWLEDGMENT"


def test_fast_conversational_responses_exist():
    from app.services.chat_service import (
        FAST_CONVERSATIONAL_RESPONSES,
        get_conversational_response,
    )

    assert "GREETING" in FAST_CONVERSATIONAL_RESPONSES
    assert "ACKNOWLEDGMENT" in FAST_CONVERSATIONAL_RESPONSES
    assert "THANKS" in FAST_CONVERSATIONAL_RESPONSES
    assert "GOODBYE" in FAST_CONVERSATIONAL_RESPONSES
    assert "HOW_ARE_YOU" in FAST_CONVERSATIONAL_RESPONSES
    assert "HELP" in FAST_CONVERSATIONAL_RESPONSES

    # Ensure multiple diverse greeting options exist
    assert len(FAST_CONVERSATIONAL_RESPONSES["GREETING"]) > 1

    # Ensure dynamic response returns valid strings for both initial and follow-up
    initial_greeting = get_conversational_response("GREETING", has_context=False)
    assert len(initial_greeting) > 10

    followup_greeting = get_conversational_response("GREETING", has_context=True)
    assert len(followup_greeting) > 5
