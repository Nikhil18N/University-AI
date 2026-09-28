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
