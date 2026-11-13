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

BTECH_ACADEMIC_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "SR University B.Tech Tuition Fee Breakdown (Official 2026-27)",
    "currency": "INR",
    "items": [
        {
            "category": "Tuition Fee (B.Tech CSE & Allied)",
            "amount": "₹1,70,000 / Sem",
            "frequency": "₹3,40,000 / Year",
            "note": "Annual base tuition ₹3,40,000 (+₹9k/yr increase); up to 40% merit scholarship",
        },
        {
            "category": "Tuition Fee (B.Tech AI & Robotics)",
            "amount": "₹2,00,000 / Sem",
            "frequency": "₹4,00,000 / Year",
            "note": "Annual base tuition ₹4,00,000 (+₹12k/yr increase)",
        },
        {
            "category": "Tuition Fee (B.Tech ECE)",
            "amount": "₹1,35,000 / Sem",
            "frequency": "₹2,70,000 / Year",
            "note": "Annual base tuition ₹2,70,000 (+₹8k/yr increase)",
        },
        {
            "category": "Tuition Fee (B.Tech Core: Mech / Civil / EEE / Biotech)",
            "amount": "₹1,00,000 / Sem",
            "frequency": "₹2,00,000 / Year",
            "note": "Annual base tuition ₹2,00,000 (+₹6k/yr increase)",
        },
        {
            "category": "Enrollment & Admission Fee (One-time)",
            "amount": "₹5,000",
            "frequency": "One-time (Year 1)",
            "note": "Mandatory enrollment component",
        },
        {
            "category": "Other & Exam Fees",
            "amount": "₹20,000 / Year",
            "frequency": "Annual",
            "note": "₹15,000 other fee + ₹5,000 exam fee",
        },
        {
            "category": "CSE Specialization Fee (Year 2+)",
            "amount": "₹30,000 / Year",
            "frequency": "From 2nd Year Onwards",
            "note": "Applicable for AIML, Data Science, Cyber Security, AR/VR, Robotics",
        },
    ],
    "scholarship_note": "Merit scholarships offer 10% to 40% tuition reduction based on board marks, JEE Main, or TG EAPCET ranks.",
}

# Alias for backwards compatibility
FEE_BREAKDOWN_CARD = BTECH_ACADEMIC_FEE_CARD

BTECH_CSE_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "B.Tech Computer Science & Engineering (CSE) Fee Structure",
    "currency": "INR",
    "items": [
        {
            "category": "Tuition Fee (B.Tech CSE)",
            "amount": "₹1,70,000 / Sem",
            "frequency": "₹3,40,000 / Year",
            "note": "Annual base tuition ₹3,40,000 (+₹9k/yr increase); up to 40% merit scholarship",
        },
        {
            "category": "Enrollment Fee (One-time)",
            "amount": "₹5,000",
            "frequency": "One-time (Year 1)",
            "note": "Mandatory enrollment component",
        },
        {
            "category": "Other & Exam Fees",
            "amount": "₹20,000 / Year",
            "frequency": "Annual",
            "note": "₹15,000 other fee + ₹5,000 exam fee",
        },
        {
            "category": "Specialization Fee (Year 2+)",
            "amount": "₹30,000 / Year",
            "frequency": "From 2nd Year Onwards",
            "note": "For AIML, Cyber Security, Data Science, AR/VR, Robotics",
        },
    ],
    "scholarship_note": "Up to 40% tuition scholarship (₹1,36,000 waiver/yr, net ₹2,04,000/yr) based on Inter/CBSE/JEE/EAPCET scores.",
}

MERIT_SCHOLARSHIP_CARD = {
    "type": "fee_breakdown",
    "title": "SR University B.Tech Merit Scholarship Slabs (2026-27)",
    "currency": "INR",
    "items": [
        {
            "category": "40% Tuition Waiver Slab",
            "amount": "₹2,04,000 / Year (CSE)",
            "frequency": "Save ₹1,36,000 / Year",
            "note": "Inter ≥ 98% | CBSE ≥ 95% | JEE ≥ 95%ile | TG EAPCET 1–2000",
        },
        {
            "category": "30% Tuition Waiver Slab",
            "amount": "₹2,38,000 / Year (CSE)",
            "frequency": "Save ₹1,02,000 / Year",
            "note": "Inter 92–97.9% | CBSE 90–94.9% | JEE 90–94.5%ile | TG EAPCET 2001–8000",
        },
        {
            "category": "25% Tuition Waiver Slab",
            "amount": "₹2,55,000 / Year (CSE)",
            "frequency": "Save ₹85,000 / Year",
            "note": "Inter 80–91.9% | CBSE 80–89.9% | JEE 80–89.9%ile | TG EAPCET 8001–20000",
        },
        {
            "category": "20% Tuition Waiver Slab",
            "amount": "₹2,72,000 / Year (CSE)",
            "frequency": "Save ₹68,000 / Year",
            "note": "Inter 70–79.9% | CBSE 70–79.9% | JEE 70–79.9%ile",
        },
        {
            "category": "15% Tuition Waiver Slab",
            "amount": "₹2,89,000 / Year (CSE)",
            "frequency": "Save ₹51,000 / Year",
            "note": "Inter 65–69.9% | CBSE 65–69.9% | JEE 60–69.9%ile",
        },
        {
            "category": "10% Tuition Waiver Slab",
            "amount": "₹3,06,000 / Year (CSE)",
            "frequency": "Save ₹34,000 / Year",
            "note": "Inter 60–64.9% | CBSE 60–64.9% | JEE 50–59.9%ile",
        },
    ],
    "scholarship_note": "Calculated on standard B.Tech CSE base tuition (₹3,40,000/yr). Slabs apply similarly across all UG disciplines.",
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

PLACEMENT_EXCELLENCE_CARD = {
    "type": "placement_highlights",
    "title": "Three Consecutive Years of Excellence in Highest Packages & Internships",
    "subtitle": "SR University Campus Recruitment & Corporate Placement Highlights",
    "image_url": "/placements-three-years.png",
    "image_alt": "Three Consecutive Years of Excellence in Highest Packages & Internships",
    "superstars": [
        {
            "name": "B. Shiva Krishna",
            "role": "Software Engineer",
            "company": "Microsoft",
            "package": "51 LPA",
            "stipend": "₹1.25L / month",
            "batch": "Batch 2025",
            "badge_color": "#10b981",
        },
        {
            "name": "Mohammed Akramuddin",
            "role": "Associate Software Engineer",
            "company": "ServiceNow",
            "package": "49.30 LPA",
            "stipend": "₹0.80L / month",
            "batch": "Batch 2027",
            "badge_color": "#6366f1",
        },
        {
            "name": "Kencha Bhavana",
            "role": "Software Development Engineer",
            "company": "Amazon",
            "package": "46.38 LPA",
            "stipend": "₹1.10L / month",
            "batch": "Batch 2026",
            "badge_color": "#0284c7",
        },
    ],
    "stats": [
        {"label": "Record Highest Package", "value": "51 LPA", "note": "Microsoft (Batch 2025)"},
        {"label": "ServiceNow Marquee Offer", "value": "49.30 LPA", "note": "ServiceNow (Batch 2027)"},
        {"label": "Amazon SDE Package", "value": "46.38 LPA", "note": "Amazon (Batch 2026)"},
        {"label": "Total Job Offers", "value": "1,300+", "note": "Till April and counting"},
        {"label": "Paid Internships", "value": "3,500+", "note": "Stipends up to ₹1.25L/month"},
        {"label": "Average Package", "value": "6 LPA", "note": "Across graduating cohorts"},
    ],
    "top_mnc_offers": [
        {"company": "Accenture", "offers": 254},
        {"company": "Cognizant", "offers": 165},
        {"company": "Brakes India", "offers": 66},
        {"company": "Capgemini", "offers": 57},
        {"company": "Virtusa", "offers": 48},
        {"company": "TCS", "offers": 45},
        {"company": "Savantis", "offers": 43},
        {"company": "Edufyi Tech", "offers": 38},
        {"company": "Infosys", "offers": 22},
    ],
    "marquee_offers": [
        {"student": "Thangallapally Nithal", "batch": "CSE 2025", "package": "44 LPA", "company": "Salesforce"},
        {"student": "Bijigiri Vignesh", "batch": "CSE 2025", "package": "44 LPA", "company": "ServiceNow"},
        {"student": "Ambati Krishna Sai", "batch": "CSE 2025", "package": "44 LPA", "company": "ServiceNow"},
        {"student": "Jonnadula Sahith", "batch": "CSE 2025", "package": "34.5 LPA", "company": "PayPal"},
        {"student": "Harsha Vardhan", "batch": "CSE 2025", "package": "34.5 LPA", "company": "PayPal"},
        {"student": "Repala Vignesh", "batch": "CSE 2025", "package": "25 LPA", "company": "Cisco"},
        {"student": "Suraram Hari Charan", "batch": "CSE 2026", "package": "19.75 LPA", "company": "JPMorgan Chase"},
        {"student": "Nadimadla Sanvitha", "batch": "ECE 2026", "package": "14.5 LPA", "company": "Flipkart"},
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
    is_scholarship_only_query = any(
        k in msg_lower for k in ("scholarship slab", "scholarship slabs", "merit scholarship details", "scholarship percentage", "scholarship criteria", "scholarship %", "merit scholarship")
    ) and not any(k in msg_lower for k in ("tuition fee", "fee structure", "how much fee", "complete fee"))

    is_cse_fee_query = any(k in msg_lower for k in ("cse", "computer science")) and any(
        k in msg_lower for k in ("fee", "fees", "tuition", "cost", "charge", "how much")
    ) and not any(k in msg_lower for k in ("all branches", "complete fee", "other branches", "overall", "fee structure"))

    is_btech_fee_query = any(k in msg_lower for k in ("btech", "b.tech", "engineering fee", "btech fee", "b.tech fee")) or (
        any(k in msg_lower for k in ("btech", "b.tech")) and any(k in msg_lower for k in ("fee", "fees", "tuition", "cost", "scholarship"))
    )

    if is_transport_fee_query:
        cards.append(TRANSPORT_FEE_CARD)
    elif is_hostel_fee_query:
        cards.append(HOSTEL_FEE_CARD)
    elif is_exam_fee_query:
        cards.append(EXAM_FEE_CARD)
    elif is_admission_fee_query:
        cards.append(ADMISSION_FEE_CARD)
    elif is_scholarship_only_query:
        cards.append(MERIT_SCHOLARSHIP_CARD)
    elif is_cse_fee_query:
        cards.append(BTECH_CSE_FEE_CARD)
    elif is_btech_fee_query:
        cards.append(BTECH_ACADEMIC_FEE_CARD)
    elif any(k in msg_lower for k in ("fee", "fees", "tuition", "cost of study", "how much is the fee")):
        # Only attach general breakdown if user explicitly asked for program fee structure / breakdown
        if any(k in msg_lower for k in ("structure", "complete fee", "breakdown", "all fees", "details", "academic", "tuition")):
            if not any(k in msg_lower for k in ("transport", "bus", "hostel", "mess", "exam")):
                cards.append(BTECH_ACADEMIC_FEE_CARD)

    # 3. Curriculum card
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subjects", "course structure", "credits")) and (
        "cse" in msg_lower or "computer science" in msg_lower or "engineering" in msg_lower
    ):
        cards.append(CURRICULUM_CARD)

    # 4. Placement Highlights card ("Three Consecutive Years of Excellence")
    if any(k in msg_lower for k in ("placement", "placements", "highest package", "average package", "recruiters", "job offers", "internship", "internships", "superstar", "highest offer", "salary", "ctc", "highest ctc", "jobs", "career", "companies visiting", "recruitment")):
        cards.append(PLACEMENT_EXCELLENCE_CARD)

    # 5. Campus tour card (render static spot highlights if explicitly asking for campus walkthrough/tour)
    is_video_query = any(k in msg_lower for k in ("video", "videos", "watch", "youtube", "clip", "tour", "shorts"))
    if not is_video_query and any(k in msg_lower for k in ("campus tour", "campus walkthrough", "see the campus", "visit the campus", "campus facilities")):
        if not any(k in msg_lower for k in ("fee", "cost", "vs")):
            cards.append(CAMPUS_TOUR_CARD)

    # 6. University YouTube Media Recommendations (Dense Semantic Search via ChromaDB)
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

    # 7. Student profile card (if board_score is known and user asked about eligibility or admission)
    if profile and profile.get("board_score"):
        score = profile.get("board_score")
        branch = profile.get("branch_interest") or "B.Tech CSE"
        is_eligible = False
        try:
            num = float(re.sub(r"[^\d.]", "", score))
            is_eligible = num >= 50.0
        except ValueError:
            is_eligible = True

        status_text = "Eligible (Minimum Cutoff: 50%)" if is_eligible else "Cutoff Requirement: 50%"
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
