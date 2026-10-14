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

FEE_SUGGESTIONS = [
    "🎓 Merit Scholarships",
    "💳 Payment Schedule",
    "🏠 Hostel & Mess Fees",
    "📋 How to Apply",
]

HOSTEL_SUGGESTIONS = [
    "🍽️ Mess & Food Quality",
    "🕒 Hostel Timings & Rules",
    "🚌 Campus Transport",
    "⚽ Sports & Clubs",
]

CURRICULUM_SUGGESTIONS = [
    "🔬 Specialized AI Labs",
    "📊 Placement Stats",
    "🧑‍🏫 Faculty Guidance",
    "📋 How to Apply",
]

DEFAULT_GREETING_SUGGESTIONS = [
    "🎯 B.Tech Admissions",
    "💰 Fee Structure",
    "📊 Placement Highlights",
    "🧭 Start Admission Wizard",
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
        return PLACEMENT_SUGGESTIONS

    # 6. Fees, Tuition & Scholarships
    if any(k in msg_lower for k in ("fee", "fees", "tuition", "cost", "scholarship", "caution deposit")):
        return FEE_SUGGESTIONS

    # 7. Hostels, Mess & Campus Life
    if any(k in msg_lower for k in ("hostel", "mess", "food", "room", "curfew", "timing", "campus", "sports", "bus", "transport")):
        return HOSTEL_SUGGESTIONS

    # 8. Courses & Curriculum
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subject", "courses", "credits", "labs")):
        return CURRICULUM_SUGGESTIONS

    # 9. Greeting / General conversational
    if intent in ("GREETING", "HOW_ARE_YOU", "HELP", "ACKNOWLEDGMENT", "THANKS"):
        return DEFAULT_GREETING_SUGGESTIONS

    # 10. Default contextual fallbacks
    # Check if answer mentions placements, fees, or hostels
    if "placement" in ans_lower or "lpa" in ans_lower:
        return PLACEMENT_SUGGESTIONS
    if "fee" in ans_lower or "rs." in ans_lower or "₹" in ans_lower:
        return FEE_SUGGESTIONS
    if "hostel" in ans_lower:
        return HOSTEL_SUGGESTIONS

    return DEFAULT_UNIVERSITY_SUGGESTIONS
