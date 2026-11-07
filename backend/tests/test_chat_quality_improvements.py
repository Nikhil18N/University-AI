"""Unit tests for chat quality, timezone greetings, privacy sanitization, and cache removal."""

from datetime import datetime
from unittest.mock import patch
import pytest

from app.services.chat_service import (
    IST,
    get_time_aware_greeting,
    sanitize_staff_contact_numbers,
    should_offer_video_tour,
)
from app.services.intent_service import _is_greeting_without_question, fast_classify


def test_ist_time_aware_greeting():
    """Verify greeting accurately reflects Indian Standard Time (IST, UTC+5:30)."""
    # 09:43 UTC is 15:13 IST (3:13 PM -> Afternoon)
    fake_time_1513 = datetime(2026, 11, 7, 15, 13, 0, tzinfo=IST)
    with patch("app.services.chat_service.datetime") as mock_dt:
        mock_dt.now.return_value = fake_time_1513
        assert get_time_aware_greeting() == "Good afternoon! 🌤️"

    # Morning (9:30 AM IST)
    fake_morning = datetime(2026, 11, 7, 9, 30, 0, tzinfo=IST)
    with patch("app.services.chat_service.datetime") as mock_dt:
        mock_dt.now.return_value = fake_morning
        assert get_time_aware_greeting() == "Good morning! ☀️"

    # Evening (6:30 PM IST)
    fake_evening = datetime(2026, 11, 7, 18, 30, 0, tzinfo=IST)
    with patch("app.services.chat_service.datetime") as mock_dt:
        mock_dt.now.return_value = fake_evening
        assert get_time_aware_greeting() == "Good evening! 🌙"

    # Night (11:00 PM IST)
    fake_night = datetime(2026, 11, 7, 23, 0, 0, tzinfo=IST)
    with patch("app.services.chat_service.datetime") as mock_dt:
        mock_dt.now.return_value = fake_night
        assert get_time_aware_greeting() == "Hello! ✨"


def test_greeting_classifier_does_not_swallow_time_corrections():
    """Verify that messages like 'hello it afternoon' route to conversational handling rather than blind greeting."""
    assert _is_greeting_without_question("hi") is True
    assert _is_greeting_without_question("hello") is True
    assert _is_greeting_without_question("good morning") is True

    # Corrections/remarks about time of day must not be treated as blind greetings
    assert _is_greeting_without_question("hello it afternoon") is False
    assert _is_greeting_without_question("hey it is afternoon") is False
    assert _is_greeting_without_question("am asking u is it morning or afternoon") is False
    assert _is_greeting_without_question("hello its morning") is False


def test_sanitize_staff_contact_numbers():
    """Verify personal staff numbers are redacted while official university helpline numbers remain."""
    raw = (
        "Our campus has 100% Wi-Fi. For assistance, reach out to our network support team members "
        "Mr. A. Bala Krishna at 8886522500 or Mr. E. Manikanta at 8008917297. "
        "For admissions, contact 0870-2818333."
    )
    cleaned = sanitize_staff_contact_numbers(raw)

    assert "8886522500" not in cleaned
    assert "8008917297" not in cleaned
    assert "helpdesk@sru.edu.in" in cleaned
    assert "0870-2818333" in cleaned


def test_should_offer_video_tour_scoping():
    """Verify video offers are restricted to genuine tour requests and not general evaluations or fees."""
    # Genuine visual tour questions
    assert should_offer_video_tour("can I see a campus tour video?") is True
    assert should_offer_video_tour("how does the campus look like?") is True
    assert should_offer_video_tour("show me hostel rooms walkthrough") is True

    # General evaluation / ad / fee questions should NOT trigger video prompts
    assert should_offer_video_tour("can I know if sr university is good?") is False
    assert should_offer_video_tour("thought instagram ad I came to this page, what should I ask you") is False
    assert should_offer_video_tour("what is the B.Tech CSE fee structure?") is False
    assert should_offer_video_tour("can I get admission with 78% in inter?") is False
