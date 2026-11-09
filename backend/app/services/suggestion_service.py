"""Suggestion service — generates contextual quick-reply chips for chat interactions."""

import re

# Specialist domain suggestion banks
ELIGIBILITY_CONFIRMED_SUGGESTIONS = [
    "📋 How to Apply Online",
    "💰 Complete Tuition Fee Schedule",
    "🏠 Hostel Room & Mess Details",
    "📊 Placement Statistics & Recruiters",
]

ELIGIBILITY_QUERY_SUGGESTIONS = [
    "I scored 90%+",
    "I scored 75%",
    "I scored 60%",
    "What if I have < 60%?",
]

BRANCH_COMPARISON_SUGGESTIONS = [
    "🚀 Innovation & SRiX Incubator",
    "📊 B.Tech CSE Placement Records",
    "🆚 Compare CSE with ECE",
    "📋 Admission Eligibility Criteria",
]

PLACEMENT_SUGGESTIONS = [
    "💼 Top Recruiting Companies",
    "📈 Microsoft 51 LPA Highest Package",
    "🎯 One Student–One Job Policy",
    "🚀 SRiX Startup Incubator",
]

PLACEMENT_VIDEO_OFFER_SUGGESTIONS = [
    "🎥 Yes, watch video",
    "❌ No, thanks",
    "💼 Top Recruiters",
    "📈 Highest Package",
]

GENERAL_FEE_SUGGESTIONS = [
    "🎓 B.Tech Tuition Fees",
    "💼 MBA & Management Fees",
    "🏠 Hostel & Mess Fees",
    "🧮 Scholarship Calculator",
]

BTECH_FEE_SUGGESTIONS = [
    "🎓 B.Tech CSE Fee Breakdown",
    "⚡ B.Tech ECE Fees",
    "🏠 Hostel & Mess Fees",
    "🧮 Scholarship Calculator",
]

SCHOLARSHIP_SUGGESTIONS = [
    "🧮 Open Scholarship Calculator",
    "🎓 B.Tech CSE Scholarship Slabs",
    "⚡ B.Tech ECE Scholarship Slabs",
    "🤝 Special Category Scholarship",
]

FEE_SUGGESTIONS = GENERAL_FEE_SUGGESTIONS

HOSTEL_SUGGESTIONS = [
    "🕒 Hostel Curfew & In-Time Rules",
    "🍽️ Mess Timings & Food Facilities",
    "🔒 Hostel Safety & Visitor Policy",
    "🏠 AC vs Non-AC Room Options",
]

ACADEMIC_SUGGESTIONS = [
    "📚 75% Attendance & Detention Rule",
    "🎓 Fully Flexible Credit System",
    "🏥 Medical Condonation Policy",
    "🔬 Core Labs & Projects",
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
    "🌳 150-Acre Green Campus",
    "🚀 SRiX Startup Incubator",
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
    "📍 Kazipet & Subedari Stops",
]

CURRICULUM_SUGGESTIONS = [
    "💻 Practical Project Curriculum",
    "📊 Average & Highest Placement CTC",
    "🧑‍🏫 Faculty Guidance & Mentorship",
    "📋 How to Register for Courses",
]

DEFAULT_GREETING_SUGGESTIONS = [
    "🎯 B.Tech Admissions 2026",
    "💰 Tuition Fees & Merit Scholarships",
    "🏠 Hostel Living & Curfew Rules",
    "📊 Placement Records & Top Packages",
]

VIDEO_TOUR_SUGGESTIONS = [
    "🎥 Watch Campus Virtual Tour",
    "🎥 Watch Hostel Living Walkthrough",
    "🚀 Explore SRiX Startup Incubator",
    "💼 Placement Drives & Microsoft CTC",
]

DEFAULT_UNIVERSITY_SUGGESTIONS = [
    "📋 B.Tech Admission Process",
    "💰 Fee Structure & Scholarships",
    "🏠 Hostel Amenities & Timings",
    "📊 Campus Placement Records",
]


UNAVAILABLE_CHIP_KEYWORDS = (
    "specialized ai",
    "sports arena",
    "international hostel",
)


def filter_available_suggestions(chips: list[str]) -> list[str]:
    """Filter out candidate chips that refer to unanswerable topics or known information gaps."""
    clean = []
    for chip in chips:
        c_lower = chip.lower()
        if any(bad in c_lower for bad in UNAVAILABLE_CHIP_KEYWORDS):
            continue
        clean.append(chip)
    if len(clean) < 2:
        return DEFAULT_UNIVERSITY_SUGGESTIONS[:4]
    return clean


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
        return filter_available_suggestions(flow_state["options"][:4])

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
    if any(k in msg_lower for k in ("eligible", "eligibility", "cutoff", "percentage", "marks", "percent", "criteria", "admission", "process")):
        if any(w in ans_lower for w in ("fully eligible", "you are eligible", "meets the", "exceeds the", "congratulations", "welcome")):
            return ELIGIBILITY_CONFIRMED_SUGGESTIONS
        if any(w in ans_lower for w in ("share your", "board percentage", "qualifying percentage", "minimum 60%", "pcm percentage")):
            return ELIGIBILITY_QUERY_SUGGESTIONS

    if any(w in ans_lower for w in ("share your 10+2", "share your pcm", "pcm percentage", "share your board percentage")):
        return ELIGIBILITY_QUERY_SUGGESTIONS

    # 4. Branch comparison (e.g. CSE vs AIML)
    if any(k in msg_lower for k in ("vs", "compare", "difference between", "specialization")):
        return BRANCH_COMPARISON_SUGGESTIONS

    # 5. Placements & Jobs
    if any(k in msg_lower for k in ("placement", "package", "ctc", "recruiter", "job", "internship", "hiring", "salary")):
        if "watch a short video" in ans_lower or "(yes / no)" in ans_lower:
            return PLACEMENT_VIDEO_OFFER_SUGGESTIONS
        return PLACEMENT_SUGGESTIONS

    # 6. Fees, Tuition & Scholarships (Strict Category Scoping)
    if any(k in msg_lower for k in ("scholarship", "scholarships", "calculator", "waiver")):
        return SCHOLARSHIP_SUGGESTIONS
    if any(k in msg_lower for k in ("bus", "transport", "commute", "van route")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "pass")
    ):
        return TRANSPORT_SUGGESTIONS
    if any(k in msg_lower for k in ("hostel", "mess", "boarding", "room rent")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "rent")
    ):
        return [
            "🏠 Girls AC Hostel Fee",
            "🏠 Boys Non-AC & AC Fee",
            "🍽️ Mess & Food Facilities",
            "🕒 Hostel Curfew & In-Time",
        ]
    if any(k in msg_lower for k in ("btech", "b.tech", "cse", "ece", "mech", "civil", "engineering")) and any(k in msg_lower for k in ("fee", "fees", "tuition")):
        return BTECH_FEE_SUGGESTIONS
    if any(k in msg_lower for k in ("fee", "fees", "tuition", "cost", "caution deposit")):
        return GENERAL_FEE_SUGGESTIONS


    # 7. Startups & SRiX incubator
    if any(k in msg_lower for k in ("srix", "startup", "incubator", "entrepreneur")):
        if "watch a short video" in ans_lower or "(yes / no)" in ans_lower:
            return SRIX_VIDEO_OFFER_SUGGESTIONS
        raw_suggestions = SRIX_VIDEO_OFFER_SUGGESTIONS

    # 8. Hostels, Mess & Living
    elif any(k in msg_lower for k in ("hostel", "mess", "food", "room", "curfew", "timing", "warden")):
        if "watch a short video" in ans_lower or "(yes / no)" in ans_lower:
            return HOSTEL_VIDEO_OFFER_SUGGESTIONS
        raw_suggestions = HOSTEL_SUGGESTIONS

    # 9. Campus Life & Infrastructure
    elif any(k in msg_lower for k in ("campus", "infrastructure", "library", "blocks", "sports")):
        if "watch a short video" in ans_lower or "(yes / no)" in ans_lower:
            return CAMPUS_VIDEO_OFFER_SUGGESTIONS
        raw_suggestions = CAMPUS_VIDEO_OFFER_SUGGESTIONS

    # 10. Academics, Attendance & Condonation
    elif any(k in msg_lower for k in ("attendance", "detention", "condon", "exam", "gpa", "cgpa", "credit", "ffcs")):
        raw_suggestions = ACADEMIC_SUGGESTIONS

    # 11. Courses & Curriculum
    elif any(k in msg_lower for k in ("curriculum", "syllabus", "subject", "courses", "credits", "labs")):
        raw_suggestions = CURRICULUM_SUGGESTIONS

    # 12. Greeting / General conversational
    elif intent in ("GREETING", "HOW_ARE_YOU", "HELP", "ACKNOWLEDGMENT", "THANKS"):
        raw_suggestions = DEFAULT_GREETING_SUGGESTIONS

    # 13. Default contextual fallbacks based on answer content
    elif "placement" in ans_lower or "lpa" in ans_lower:
        raw_suggestions = PLACEMENT_SUGGESTIONS
    elif "fee" in ans_lower or "rs." in ans_lower or "₹" in ans_lower:
        raw_suggestions = GENERAL_FEE_SUGGESTIONS
    elif "hostel" in ans_lower:
        raw_suggestions = HOSTEL_SUGGESTIONS
    elif "attendance" in ans_lower:
        raw_suggestions = ACADEMIC_SUGGESTIONS
    elif "campus" in ans_lower:
        raw_suggestions = CAMPUS_VIDEO_OFFER_SUGGESTIONS
    else:
        raw_suggestions = DEFAULT_UNIVERSITY_SUGGESTIONS

    # Anti-duplicate filter: never suggest a chip that matches what user just asked
    filtered = [
        s for s in raw_suggestions
        if not any(word in msg_lower for word in s.lower().replace("📋", "").replace("💰", "").replace("🏠", "").replace("📊", "").replace("📚", "").replace("🎓", "").replace("💼", "").split() if len(word) > 4)
    ]
    res = filtered[:4] if len(filtered) >= 2 else raw_suggestions[:4]
    return filter_available_suggestions(res)
