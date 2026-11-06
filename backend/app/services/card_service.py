"""Card service — detects and generates structured interactive cards for rich UI rendering."""

import re
from app.services.video_service import get_relevant_videos, create_video_card

COMPARISON_CSE_AIML = {
    "type": "comparison",
    "title": "Branch Comparison: CSE vs CSE (AI & ML)",
    "columns": [
        {
            "name": "B.Tech Computer Science (Core)",
            "badge": "Core Foundation",
            "focus": "Broad computing foundation: Algorithms, System Architecture, Operating Systems, Database Systems, and Full-Stack Engineering.",
            "careers": "Software Development Engineer (SDE), Cloud Architect, Systems Engineer, Backend Engineer.",
            "labs": "Advanced Computing Lab, Systems & Networks Lab, Open Source Studio.",
            "key_advantage": "Maximum career versatility across all sectors of software and tech industries.",
        },
        {
            "name": "B.Tech CSE (AI & Machine Learning)",
            "badge": "Specialized Tech",
            "focus": "Intelligent systems: Deep Learning, Natural Language Processing, Computer Vision, Generative AI, and MLOps.",
            "careers": "AI Engineer, Machine Learning Engineer, Data Scientist, NLP Specialist, Research Analyst.",
            "labs": "Center for Artificial Intelligence, NVIDIA GPU High-Performance Cluster.",
            "key_advantage": "Targeted industry readiness for high-demand AI roles from day one.",
        },
    ],
}

FEE_BREAKDOWN_CARD = {
    "type": "fee_breakdown",
    "title": "SR University Official Fee Breakdown (2026-27 / 2027-28)",
    "currency": "INR",
    "items": [
        {
            "category": "Tuition Fee (B.Tech CSE)",
            "amount": "₹1,47,500 / Sem",
            "frequency": "₹2,95,000 / Year",
            "note": "Semester-wise billing; 40% scholarship for 92%+ in Inter",
        },
        {
            "category": "Admission & Enrollment (One-time)",
            "amount": "₹30,000",
            "frequency": "One-time (Year 1)",
            "note": "₹5,000 enrollment + ₹25,000 admission fee",
        },
        {
            "category": "Girls Hostel (AC with Mess)",
            "amount": "₹1,25,000 – ₹1,35,000",
            "frequency": "Per Year",
            "note": "4-sharing / 3-sharing AC with 4 meals daily, Wi-Fi & laundry",
        },
        {
            "category": "Boys Hostel (with Mess)",
            "amount": "₹85,000 – ₹1,35,000",
            "frequency": "Per Year",
            "note": "Non-AC (₹85k-95k) or AC (₹1.20L-1.35L) with meals & laundry",
        },
        {
            "category": "Transport Facility (Optional)",
            "amount": "₹22,000 – ₹30,000",
            "frequency": "Per Year",
            "note": "Tri-cities bus routes (Warangal, Hanamkonda, Kazipet)",
        },
    ],
    "scholarship_note": "40% tuition scholarship for 92%–97.99% in 10+2 MPC for CSE; up to 100% for top rankers.",
}

TRANSPORT_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "SR University Transport & Bus Fee (2026-27 / 2027-28)",
    "currency": "INR",
    "items": [
        {
            "category": "Tri-Cities Bus Routes (Warangal, Hanamkonda, Kazipet)",
            "amount": "₹22,000 – ₹30,000",
            "frequency": "Per Year",
            "note": "GPS-tracked fleet with 30+ designated pickup stops across the tri-cities",
        },
        {
            "category": "Extended Outstation Routes (Huzurabad, Jammikunta, Karimnagar)",
            "amount": "As per distance slab",
            "frequency": "Per Year",
            "note": "Direct campus transit operated by SR University transport department",
        },
    ],
    "scholarship_note": "Transport in-charge: Mr. A. Keerthi Reddy (9640606408, transport@sru.edu.in).",
}

HOSTEL_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "SR University Residential Hostel & Dining Fees (Annual)",
    "currency": "INR",
    "items": [
        {
            "category": "Girls Hostel (AC 4-Sharing)",
            "amount": "₹1,25,000",
            "frequency": "Per Year",
            "note": "Includes 4 meals daily, Wi-Fi, laundry & 24/7 biometric security",
        },
        {
            "category": "Girls Hostel (AC 3-Sharing)",
            "amount": "₹1,35,000",
            "frequency": "Per Year",
            "note": "Includes 4 meals daily, Wi-Fi, laundry & 24/7 biometric security",
        },
        {
            "category": "Boys Hostel (Non-AC 4/3-Sharing)",
            "amount": "₹85,000 – ₹95,000",
            "frequency": "Per Year",
            "note": "Includes 4 meals daily, Wi-Fi, study lounges & laundry",
        },
        {
            "category": "Boys Hostel (AC 4/3-Sharing)",
            "amount": "₹1,20,000 – ₹1,35,000",
            "frequency": "Per Year",
            "note": "Includes 4 meals daily, Wi-Fi, gym & laundry",
        },
    ],
    "scholarship_note": "In-time curfew is 8:30 PM. Nutritious veg and non-veg dining provided 4 times daily.",
}

EXAM_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "SR University Examination Fee Structure",
    "currency": "INR",
    "items": [
        {
            "category": "Annual Examination Fee",
            "amount": "₹5,000",
            "frequency": "Per Year",
            "note": "Covers semester-end evaluations per Controller of Examinations notifications",
        },
    ],
}

ADMISSION_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "SR University One-Time Admission & Enrollment Fees",
    "currency": "INR",
    "items": [
        {
            "category": "Enrollment Fee (One-time)",
            "amount": "₹5,000",
            "frequency": "One-time (Year 1)",
            "note": "Mandatory one-time registration and enrollment fee",
        },
        {
            "category": "Admission Fee (One-time)",
            "amount": "₹25,000",
            "frequency": "One-time (Year 1)",
            "note": "Institutional admission and processing fee",
        },
    ],
}


CURRICULUM_CARD = {
    "type": "curriculum",
    "title": "B.Tech CSE Curriculum Architecture",
    "structure": [
        {
            "category": "Program Core (PC)",
            "credits": "52 Credits",
            "courses": [
                "Data Structures & Algorithms",
                "Operating Systems",
                "Database Management Systems (DBMS)",
                "Computer Networks",
                "Software Engineering",
                "Computer Organization & Architecture",
            ],
        },
        {
            "category": "Program Electives & Specialization (PE)",
            "credits": "24 Credits",
            "courses": [
                "Deep Learning & Neural Networks",
                "Cloud Computing & DevOps",
                "Big Data Analytics",
                "Cyber Security & Cryptography",
                "Full Stack Web Development",
            ],
        },
        {
            "category": "Foundations & Sciences (BS / ES / HS)",
            "credits": "48 Credits",
            "courses": [
                "Linear Algebra & Calculus",
                "Digital Logic Design",
                "Object Oriented Programming (Python/C++)",
                "Professional Ethics & Communication",
            ],
        },
        {
            "category": "Hands-on Innovation & Projects (PR)",
            "credits": "16 Credits",
            "courses": [
                "SRiX Startup & Innovation Project",
                "Summer Industry Internship",
                "Major Capstone Project",
            ],
        },
    ],
}

CAMPUS_TOUR_CARD = {
    "type": "campus_tour",
    "title": "SR University Campus Life & Facilities",
    "spots": [
        {
            "name": "Academic Blocks & Smart Classrooms",
            "desc": "Air-conditioned interactive lecture halls equipped with digital smart boards and ergonomic amphitheater seating.",
            "icon": "🏫",
        },
        {
            "name": "SRiX Technology Business Incubator",
            "desc": "DST-supported innovation center nurturing 50+ student startups with seed funding, maker spaces, and mentoring.",
            "icon": "🚀",
        },
        {
            "name": "Modern Residential Hostels",
            "desc": "Comfortable AC and non-AC rooms, high-speed Wi-Fi, study lounges, indoor gym, and round-the-clock medical care.",
            "icon": "🏠",
        },
        {
            "name": "Sports & Recreation Arena",
            "desc": "Floodlit cricket stadium, football ground, basketball courts, badminton complex, and running tracks.",
            "icon": "⚽",
        },
        {
            "name": "Central Library & Digital Commons",
            "desc": "50,000+ print volumes, 24/7 digital access to IEEE/ACM journals, and collaborative discussion zones.",
            "icon": "📚",
        },
    ],
}


def generate_cards(
    user_message: str,
    answer: str,
    profile: dict | None = None,
    sources: list[dict] | None = None,
    query_embedding: list[float] | None = None,
    is_video_confirmed: bool = False,
) -> list[dict]:
    """Generate structured interactive cards based on message context and student profile."""
    cards = []
    msg_lower = user_message.lower()
    ans_lower = answer.lower()

    # 1. Branch comparison card
    if any(k in msg_lower for k in ("vs", "compare", "comparison", "difference")) and (
        "cse" in msg_lower or "ai" in msg_lower or "aiml" in msg_lower or "machine learning" in msg_lower
    ):
        cards.append(COMPARISON_CSE_AIML)

    # 2. Fee breakdown card (Strict Category Scoping — show only what the user asks for)
    is_transport_fee_query = any(k in msg_lower for k in ("bus", "transport", "commute", "van")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "pass", "ticket")
    )
    is_hostel_fee_query = any(k in msg_lower for k in ("hostel", "mess", "boarding", "room rent")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "package")
    )
    is_exam_fee_query = any(k in msg_lower for k in ("exam", "examination", "supply", "supplementary", "revaluation")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "how much")
    )
    is_admission_fee_query = any(
        k in msg_lower for k in ("admission fee", "enrollment fee", "one-time fee", "onetime fee", "registration fee")
    )

    if is_transport_fee_query:
        cards.append(TRANSPORT_FEE_CARD)
    elif is_hostel_fee_query:
        cards.append(HOSTEL_FEE_CARD)
    elif is_exam_fee_query:
        cards.append(EXAM_FEE_CARD)
    elif is_admission_fee_query:
        cards.append(ADMISSION_FEE_CARD)
    elif any(k in msg_lower for k in ("fee", "fees", "tuition", "cost of study", "how much is the fee")):
        # Only attach general breakdown if not an isolated single facility query
        if not any(k in msg_lower for k in ("transport", "bus", "hostel", "mess", "exam")):
            cards.append(FEE_BREAKDOWN_CARD)


    # 3. Curriculum card
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subjects", "course structure", "credits")) and (
        "cse" in msg_lower or "computer science" in msg_lower or "engineering" in msg_lower
    ):
        cards.append(CURRICULUM_CARD)

    # 4. Campus tour card (render static spot highlights if explicitly asking for campus walkthrough/tour)
    is_video_query = any(k in msg_lower for k in ("video", "videos", "watch", "youtube", "clip", "tour", "shorts"))
    if not is_video_query and any(k in msg_lower for k in ("campus tour", "campus walkthrough", "see the campus", "visit the campus", "campus facilities")):
        if not any(k in msg_lower for k in ("fee", "cost", "vs")):
            cards.append(CAMPUS_TOUR_CARD)

    # 5. University YouTube Media Recommendations (Dense Semantic Search via ChromaDB)
    # Zero keyword matching: relevance is governed purely by ChromaDB semantic cosine distance.
    # Attached only when explicitly requested or confirmed via affirmative Yes/No response.
    if (is_video_query or is_video_confirmed) and query_embedding:
        relevant_videos = get_relevant_videos(
            user_message=user_message,
            answer=answer,
            sources=sources,
            query_embedding=query_embedding,
            is_explicit=is_video_query,
        )
        if relevant_videos:
            cards.append(create_video_card(relevant_videos, is_explicit=True))

    # 5. Student profile card (if board_score is known and user asked about eligibility or admission)
    if profile and profile.get("board_score"):
        score = profile.get("board_score")
        branch = profile.get("branch_interest") or "B.Tech CSE"
        is_eligible = False
        try:
            num = float(re.sub(r"[^\d.]", "", score))
            is_eligible = num >= 60.0
        except ValueError:
            is_eligible = True

        status_text = "Eligible (Minimum Cutoff: 60%)" if is_eligible else "Cutoff Requirement: 60%"
        status_color = "success" if is_eligible else "warning"

        profile_card = {
            "type": "profile",
            "title": "Your Admission Evaluation",
            "data": {
                "degree": profile.get("degree_level") or "B.Tech",
                "branch": branch,
                "score": score,
                "status": status_text,
                "status_color": status_color,
                "next_steps": (
                    "Submit Application Form → Document Verification → Seat Allocation"
                    if is_eligible
                    else "Explore Diploma Lateral Entry or Vocational Programs"
                ),
            },
        }
        # Only attach if eligibility is being discussed or confirmed
        if any(k in msg_lower or k in ans_lower for k in ("eligible", "score", "cutoff", "admission", "percentage", "%")):
            cards.append(profile_card)

    return cards
