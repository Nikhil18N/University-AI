"""Tests for multi-turn topic switching, interruptions, and slot corrections."""

import pytest
from app.services.profile_service import (
    build_counsellor_guidance,
    extract_student_profile,
)


class TestMultiTurnBranchCorrection:
    def test_branch_switch_with_explicit_command(self):
        messages = [
            {"role": "user", "content": "I want to apply for B.Tech CSE"},
            {"role": "assistant", "content": "Great choice! CSE is very popular at SRU."},
            {"role": "user", "content": "Actually, change my branch to ECE instead"},
        ]
        profile = extract_student_profile(messages)
        assert profile["degree"] == "B.Tech"
        assert "Electronics & Communication" in profile["branch"]

    def test_branch_switch_with_prefer_signal(self):
        messages = [
            {"role": "user", "content": "im interested in mechanical engineering"},
            {"role": "assistant", "content": "Mechanical is a core branch."},
            {"role": "user", "content": "now i want AI & ML rather than mechanical"},
        ]
        profile = extract_student_profile(messages)
        assert profile["branch"] == "AI & Machine Learning"

    def test_comparison_does_not_overwrite_chosen_branch(self):
        messages = [
            {"role": "user", "content": "I want to join B.Tech CSE"},
            {"role": "assistant", "content": "CSE is great."},
            {"role": "user", "content": "Can you compare CSE vs ECE placements?"},
        ]
        profile = extract_student_profile(messages)
        assert profile["branch"] == "Computer Science & Engineering (CSE)"


class TestMultiTurnScoreCorrection:
    def test_score_correction_flips_eligibility(self):
        # Turn 1: Below cutoff (55%)
        messages = [
            {"role": "user", "content": "I got 55% in 12th boards, want B.Tech CSE"},
        ]
        profile1 = extract_student_profile(messages)
        assert profile1["score_pct"] == 55.0
        guidance1 = build_counsellor_guidance(profile1)
        assert "below the 60% cutoff" in guidance1

        # Turn 2: Student corrects the score (75%)
        messages.extend([
            {"role": "assistant", "content": "Unfortunately 55% is below our 60% cutoff."},
            {"role": "user", "content": "Sorry typo, my marks are actually 75% in PCM!"},
        ])
        profile2 = extract_student_profile(messages)
        assert profile2["score_pct"] == 75.0
        assert profile2["score_raw"] == "75.0%" or profile2["score_raw"] == "75%"
        guidance2 = build_counsellor_guidance(profile2)
        assert "CONFIRM DIRECTLY THAT THEY ARE ELIGIBLE" in guidance2

    def test_score_fraction_to_percent_correction(self):
        messages = [
            {"role": "user", "content": "my marks are 580 out of 1000"},
            {"role": "assistant", "content": "580/1000 is 58%, which is below 60%."},
            {"role": "user", "content": "My mistake, recount showed 680 out of 1000 marks"},
        ]
        profile = extract_student_profile(messages)
        assert profile["score_pct"] == 68.0
        guidance = build_counsellor_guidance(profile)
        assert "CONFIRM DIRECTLY THAT THEY ARE ELIGIBLE" in guidance


class TestMultiTurnDegreeSwitching:
    def test_degree_switch_from_btech_to_mtech(self):
        messages = [
            {"role": "user", "content": "Tell me about B.Tech programs"},
            {"role": "assistant", "content": "We offer B.Tech in CSE, ECE, EEE, and more."},
            {"role": "user", "content": "Actually switch to M.Tech, what are the post-graduate options?"},
        ]
        profile = extract_student_profile(messages)
        assert profile["degree"] == "M.Tech"


class TestMultiTurnTopicSwitchingInterruption:
    def test_topic_switching_interruption_preserves_context(self):
        """Student starts admissions flow, gets interrupted by hostel/sports, then returns."""
        messages = [
            # Turn 1: Admissions intent
            {"role": "user", "content": "Hi, I am interested in B.Tech CSE"},
            {"role": "assistant", "content": "Awesome! What was your 12th board score?"},

            # Turn 2: Score provided
            {"role": "user", "content": "I scored 82% in 12th PCM"},
            {"role": "assistant", "content": "You are fully eligible! Anything else you'd like to check?"},

            # Turn 3: Topic switch -> Hostel
            {"role": "user", "content": "What is the hostel curfew time and do you have AC rooms?"},
            {"role": "assistant", "content": "Hostel curfew is 9:00 PM and we offer both AC and Non-AC rooms."},

            # Turn 4: Topic switch -> Campus Sports
            {"role": "user", "content": "Is there a gym and badminton court on campus?"},
            {"role": "assistant", "content": "Yes, SRU features indoor sports, gym, and badminton facilities."},

            # Turn 5: Return to Admissions
            {"role": "user", "content": "Okay great, am I eligible to register now?"},
        ]

        # Profile should retain ALL slots through the interruptions
        profile = extract_student_profile(messages)
        assert profile["degree"] == "B.Tech"
        assert "Computer Science" in profile["branch"]
        assert profile["has_score"] is True
        assert profile["score_pct"] == 82.0

        # Guidance on return should recognize student is eligible without re-asking
        guidance = build_counsellor_guidance(profile, current_query="am I eligible to register now?")
        assert "DO NOT ask what degree" in guidance
        assert "DO NOT ask what branch" in guidance
        assert "DO NOT ask for their score or percentage again" in guidance
        assert "CONFIRM DIRECTLY THAT THEY ARE ELIGIBLE" in guidance
