"""Suggestion service — generates contextual quick-reply chips for chat interactions."""

import re

# Domain suggestion banks
ELIGIBILITY_CONFIRMED_SUGGESTIONS = [
    "📋 How to Apply",
    "💰 Fee Structure",
    "🏠 Hostel Details",
    "🔬 Lab Facilities",
]

ELIGIBILITY_QUERY_SUGGESTIONS = [
    "I scored 90%+",
    "I scored 75%",
    "I scored 60%",
    "What if I have < 60%?",
]

BRANCH_COMPARISON_SUGGESTIONS = [
    "🔬 Lab Facilities",
    "📊 Placement Stats",
    "🆚 Compare with ECE",
    "📋 How to Apply",
]

PLACEMENT_SUGGESTIONS = [
    "💼 Top Recruiters",
    "📈 Highest Package",
    "🎯 Internship Options",
    "🤝 SRiX Startup Incubator",
]

PLACEMENT_VIDEO_OFFER_SUGGESTIONS = [
    "🎥 Yes, watch video",
    "❌ No, thanks",
    "💼 Top Recruiters",
    "📈 Highest Package",
]

FEE_SUGGESTIONS = [
    "🎓 Merit Scholarships",
    "💳 Payment Schedule",
    "🏠 Hostel & Mess Fees",
    "📋 How to Apply",
]

HOSTEL_SUGGESTIONS = [
    "🎥 Watch Hostel Tour",
    "🍽️ Mess & Food Quality",
    "🕒 Hostel Timings & Rules",
    "🚌 Campus Transport",
]

HOSTEL_VIDEO_OFFER_SUGGESTIONS = [
    "🎥 Yes, watch video",
    "❌ No, thanks",
    "🍽️ Mess & Food Quality",
    "🕒 Hostel Timings & Rules",
]

CAMPUS_VIDEO_OFFER_SUGGESTIONS = [
    "🎥 Yes, watch video",
    "❌ No, thanks",
    "🔬 Specialized AI Labs",
    "⚽ Sports Arena",
]

SRIX_VIDEO_OFFER_SUGGESTIONS = [
    "🎥 Yes, watch video",
    "❌ No, thanks",
    "🚀 Student Startups",
    "🤝 Seed Funding & Grants",
]

TRANSPORT_SUGGESTIONS = [
    "🚌 Bus Timings",
    "💳 Transport Fee",
    "📍 Warangal & Hanamkonda Routes",
    "🏠 Hostel Facilities",
]

CURRICULUM_SUGGESTIONS = [
    "🔬 Specialized AI Labs",
    "📊 Placement Stats",
    "🧑‍🏫 Faculty Guidance",
    "📋 How to Apply",
]

DEFAULT_GREETING_SUGGESTIONS = [
    "🎯 B.Tech Admissions",
    "🎥 Virtual Campus Tour",
    "💰 Fee Structure",
    "📊 Placement Highlights",
]

VIDEO_TOUR_SUGGESTIONS = [
    "🎥 Watch Campus Tour",
    "🎥 Watch Hostel Walkthrough",
    "🚀 SRiX Startup Incubator",
    "💼 Placements & Packages",
]

DEFAULT_UNIVERSITY_SUGGESTIONS = [
    "📋 Admission Process",
    "💰 Fee Structure",
    "🏠 Hostel Facilities",
    "📊 Placement Records",
]


def generate_suggestions(
    intent: str,
    user_message: str,
    answer: str,
    sources: list[dict] | None = None,
    profile: dict | None = None,
    flow_state: dict | None = None,
) -> list[str]:
    """Generate 3-4 contextual suggestion chips based on intent, topic, and dialogue state."""
    # 1. If guided flow has explicit choices, prioritize them
    if flow_state and flow_state.get("options"):
        return flow_state["options"][:4]

    msg_lower = user_message.lower()
    ans_lower = answer.lower()

    # 2. Student specific auth guardrail
    if intent == "STUDENT_SPECIFIC":
        return [
            "📞 Contact Academic Section",
            "🏢 Department Coordinators",
            "📋 Admission Inquiries",
        ]

    # 2b. Out of scope guardrail
    if intent == "OUT_OF_SCOPE":
        return [
            "🎓 B.Tech Programs & Admissions",
            "💰 Fee Structure & Scholarships",
            "🏢 Campus & Hostel Facilities",
            "💼 Placement Records & CTC",
        ]

    # 2b-2. Transport & Bus queries (no videos)
    if any(k in msg_lower for k in ("bus", "buses", "transport", "transportation", "commute", "van", "route", "rtc")):
        return TRANSPORT_SUGGESTIONS

    # 2c. Video or Tour explicit query
    is_explicit_video = any(k in msg_lower for k in ("video", "videos", "watch", "tour", "walkthrough", "drone", "look like"))
    if is_explicit_video:
        if "hostel" in msg_lower:
            return HOSTEL_SUGGESTIONS
        if "srix" in msg_lower:
            return SRIX_VIDEO_OFFER_SUGGESTIONS
        if "placement" in msg_lower:
            return PLACEMENT_SUGGESTIONS
        return VIDEO_TOUR_SUGGESTIONS

    # 3. Eligibility & Cutoff
    if any(k in msg_lower for k in ("eligible", "eligibility", "cutoff", "percentage", "marks", "percent", "criteria")):
        if any(w in ans_lower for w in ("fully eligible", "you are eligible", "meets the", "exceeds the", "congratulations", "welcome")):
            return ELIGIBILITY_CONFIRMED_SUGGESTIONS
        if any(w in ans_lower for w in ("share your", "board percentage", "qualifying percentage", "minimum 60%")):
            return ELIGIBILITY_QUERY_SUGGESTIONS

    # 4. Branch comparison (e.g. CSE vs AIML)
    if any(k in msg_lower for k in ("vs", "compare", "difference between", "specialization")):
        return BRANCH_COMPARISON_SUGGESTIONS

    # 5. Placements & Jobs
    if any(k in msg_lower for k in ("placement", "package", "ctc", "recruiter", "job", "internship", "hiring", "salary")):
        if "watch a short video" in ans_lower or "(yes / no)" in ans_lower:
            return PLACEMENT_VIDEO_OFFER_SUGGESTIONS
        return PLACEMENT_SUGGESTIONS

    # 6. Fees, Tuition & Scholarships
    if any(k in msg_lower for k in ("fee", "fees", "tuition", "cost", "scholarship", "caution deposit")):
        return FEE_SUGGESTIONS

    # 7. Startups & SRiX incubator
    if any(k in msg_lower for k in ("srix", "startup", "incubator", "entrepreneur")):
        return SRIX_VIDEO_OFFER_SUGGESTIONS

    # 8. Hostels, Mess & Living
    if any(k in msg_lower for k in ("hostel", "mess", "food", "room", "curfew", "timing", "warden")):
        return HOSTEL_VIDEO_OFFER_SUGGESTIONS

    # 9. Campus Life & Infrastructure
    if any(k in msg_lower for k in ("campus", "infrastructure", "library", "blocks")):
        return CAMPUS_VIDEO_OFFER_SUGGESTIONS

    # 10. Courses & Curriculum
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subject", "courses", "credits", "labs")):
        return CURRICULUM_SUGGESTIONS

    # 11. Greeting / General conversational
    if intent in ("GREETING", "HOW_ARE_YOU", "HELP", "ACKNOWLEDGMENT", "THANKS"):
        return DEFAULT_GREETING_SUGGESTIONS

    # 12. Default contextual fallbacks
    # Check if answer mentions placements, fees, or hostels
    if "placement" in ans_lower or "lpa" in ans_lower:
        return PLACEMENT_SUGGESTIONS
    if "fee" in ans_lower or "rs." in ans_lower or "₹" in ans_lower:
        return FEE_SUGGESTIONS
    if "hostel" in ans_lower:
        return HOSTEL_VIDEO_OFFER_SUGGESTIONS
    if "campus" in ans_lower:
        return CAMPUS_VIDEO_OFFER_SUGGESTIONS

    return DEFAULT_UNIVERSITY_SUGGESTIONS
