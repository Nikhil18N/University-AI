"""Card service — detects and generates structured interactive cards for rich UI rendering."""

import re
from app.services.video_service import (
    create_video_card,
    get_relevant_videos,
    is_explicit_video_query,
    is_video_topic_query,
    should_display_videos,
)

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

BTECH_CSE_SEMESTER_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "B.Tech CSE Total Per-Semester Estimated Fee Breakdown (Official 2027-28)",
    "currency": "INR",
    "items": [
        {
            "category": "1st Semester Tuition Fee (B.Tech CSE)",
            "amount": "₹1,70,000",
            "frequency": "Semester 1",
            "note": "Base tuition (₹3,40,000/yr). Up to 40% merit scholarship waiver available",
        },
        {
            "category": "2nd Semester Tuition Fee (B.Tech CSE)",
            "amount": "₹1,70,000",
            "frequency": "Semester 2",
            "note": "Annual base ₹3,40,000 (+₹9,000/yr annual escalation in subsequent years)",
        },
        {
            "category": "One-Time Enrollment Fee",
            "amount": "₹5,000",
            "frequency": "One-Time (Semester 1)",
            "note": "Mandatory official enrollment component paid once in Year 1",
        },
        {
            "category": "Other & Examination Fees",
            "amount": "₹10,000 / Sem",
            "frequency": "₹20,000 / Year",
            "note": "₹15,000 other university fee + ₹5,000 semester-end examination fee",
        },
        {
            "category": "Total Per-Semester Payable (Regular)",
            "amount": "₹1,80,000 / Sem",
            "frequency": "₹3,60,000 / Year",
            "note": "Tuition (₹1,70,000) + Other & Exam Fees (₹10,000). Hostels separate.",
        },
        {
            "category": "Total 1st Semester Payable",
            "amount": "₹1,85,000",
            "frequency": "Semester 1",
            "note": "Regular semester total + one-time enrollment fee (₹5,000)",
        },
        {
            "category": "CSE Specialization Fee (From Year 2+)",
            "amount": "₹15,000 / Sem",
            "frequency": "₹30,000 / Year",
            "note": "Applicable from 3rd semester for AI & ML, Data Science, Cyber Security tracks",
        },
    ],
    "scholarship_note": "Merit scholarships provide 10% to 40% tuition fee waiver (up to ₹68,000/sem saved; net tuition ₹1,02,000/sem; total regular sem ₹1,12,000/sem). Hostel is optional & separate (₹1,15,000 to ₹1,35,000/yr). 2027-28 fees, as per Admissions Office.",
}

BTECH_CSE_WITH_HOSTEL_FEE_CARD = {
    "type": "fee_breakdown",
    "title": "B.Tech CSE Fee + Hostel Per-Semester Total Breakdown (Official 2027-28)",
    "currency": "INR",
    "items": [
        {
            "category": "1st Semester Tuition Fee (B.Tech CSE)",
            "amount": "₹1,70,000",
            "frequency": "Semester 1",
            "note": "Base tuition (₹3,40,000/yr). Up to 40% merit scholarship waiver available",
        },
        {
            "category": "2nd Semester Tuition Fee (B.Tech CSE)",
            "amount": "₹1,70,000",
            "frequency": "Semester 2",
            "note": "Annual base ₹3,40,000 (+₹9,000/yr annual escalation in subsequent years)",
        },
        {
            "category": "Residential Hostel & Mess (AC 4-Sharing)",
            "amount": "₹62,500 / Sem",
            "frequency": "₹1,25,000 / Year",
            "note": "4 daily meals in mega dining hall, laundry, high-speed Wi-Fi, 24/7 security",
        },
        {
            "category": "Other & Examination Fees",
            "amount": "₹10,000 / Sem",
            "frequency": "₹20,000 / Year",
            "note": "₹15,000 other university fee + ₹5,000 semester-end examination fee",
        },
        {
            "category": "One-Time Enrollment Fee",
            "amount": "₹5,000",
            "frequency": "One-Time (Semester 1)",
            "note": "Mandatory official enrollment component paid once in Year 1",
        },
        {
            "category": "Combined Total Per-Semester (Regular)",
            "amount": "₹2,42,500 / Sem",
            "frequency": "₹4,85,000 / Year",
            "note": "Combined Tuition (₹1.70L) + Other/Exam (₹10k) + Hostel & Mess (₹62.5k)",
        },
        {
            "category": "Combined Total 1st Semester Payable",
            "amount": "₹2,47,500",
            "frequency": "Semester 1",
            "note": "Regular combined total + one-time enrollment fee (₹5,000)",
        },
    ],
    "scholarship_note": "With 40% merit scholarship, net tuition is ₹1,02,000/sem, bringing the combined regular per-semester total to ₹1,74,500/sem. 2027-28 fees, as per Admissions Office.",
}

# Alias for backwards compatibility
BTECH_CSE_FEE_CARD = BTECH_CSE_SEMESTER_FEE_CARD

APPLICATION_AD_CARD = {
    "type": "application_ad",
    "sponsor_name": "SR University Admissions",
    "sponsor_logo": "/sru-logo.png",
    "image_url": "/early-bird-offer.png",
    "title": "Early Bird: 50% Off Online Application",
    "description": "Apply early for 2027-28 admissions. Save 50% on official application processing (pay ₹550 instead of ₹1,100).",
    "cta_text": "Apply Now ↗",
    "cta_url": "https://apply.sru.edu.in",
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
            "note": "Inter 92–97.9% | CBSE 90–94.9% | JEE 90–94.99%ile | TG EAPCET 2001–8000",
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
    "scholarship_note": "Calculated on standard B.Tech CSE base tuition (₹3,40,000/yr). Slabs apply similarly across all UG disciplines. Tuition rises ₹9,000 yearly. Subject to marksheet verification and Admissions Office confirmation.",
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
    "subtitle": "As the academic day comes to an end, the living and learning experience continues.",
    "currency": "INR",
    "items": [
        {
            "category": "Girls Hostel (AC 4-Sharing)",
            "amount": "₹1,25,000",
            "frequency": "Per Year",
            "note": "4,000-seat mega dining hall (4 meals daily), Wi-Fi, laundry & 24/7 biometric security",
        },
        {
            "category": "Girls Hostel (AC 3-Sharing)",
            "amount": "₹1,35,000",
            "frequency": "Per Year",
            "note": "4,000-seat mega dining hall (4 meals daily), Wi-Fi, laundry & 24/7 biometric security",
        },
        {
            "category": "Boys Hostel (Non-AC 4/3-Sharing)",
            "amount": "₹85,000 – ₹95,000",
            "frequency": "Per Year",
            "note": "4,000-seat mega dining hall (4 meals daily), Wi-Fi, study lounges & laundry",
        },
        {
            "category": "Boys Hostel (AC 4/3-Sharing)",
            "amount": "₹1,20,000 – ₹1,35,000",
            "frequency": "Per Year",
            "note": "4,000-seat mega dining hall (4 meals daily), Wi-Fi, gym & laundry",
        },
    ],
    "scholarship_note": "Hostels for Boys & Girls offer 4,000-seat mega dining hall, 24/7 surveillance, high-speed Wi-Fi, dedicated study areas, and on-campus medical care.",
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


# ---------------------------------------------------------------------------
# SRU ADVANTAGE COMPARISON CARD
# Highlights what makes SR University uniquely exceptional — framed entirely
# as SRU strengths (never naming or criticising any specific competitor).
# ---------------------------------------------------------------------------
SRU_ADVANTAGE_CARD = {
    "type": "sru_comparison",
    "title": "Why SR University Stands Apart",
    "subtitle": "What sets SRU uniquely ahead — verified facts, real results.",
    "advantages": [
        {
            "category": "Rankings & Accreditations",
            "icon": "🏆",
            "sru_highlight": "NIRF 91st in Engineering — top 100 for 4 consecutive years. All B.Tech programs carry Tier-1 NBA accreditation. School of Agriculture holds ICAR accreditation — the first private university in the Telugu States to earn it.",
            "standout": "Top 100 for 4 Straight Years",
        },
        {
            "category": "Global Recognition",
            "icon": "🌐",
            "sru_highlight": "Ranked 7th in India by THE World University Rankings 2027, 6th in Research Quality, and 19th among India's State Private Universities in QS Asia 2027. India's youngest private university in Telangana to achieve national and global ranks.",
            "standout": "Global Top Rankings",
        },
        {
            "category": "Placement Excellence",
            "icon": "💼",
            "sru_highlight": "Three consecutive record highest packages: 51 LPA @ Microsoft (2025), 49.3 LPA @ ServiceNow (2027), 46.38 LPA @ Amazon (2026). 1,300+ job offers, 3,500+ internships, 6 LPA average. Active recruiters: Accenture (254), Cognizant (165), TCS, Capgemini, Infosys & more.",
            "standout": "51 LPA Highest Package",
        },
        {
            "category": "Innovation & Startups (SRiX)",
            "icon": "🚀",
            "sru_highlight": "SR Innovation Exchange (SRiX) — a DST-backed Technology Business Incubator with 171+ startups launched and ₹76+ Crore in total funding. Students get real incubation, mentoring, and investor access from Day 1.",
            "standout": "171+ Startups, ₹76+ Cr Funded",
        },
        {
            "category": "Campus & Living Experience",
            "icon": "🌿",
            "sru_highlight": "170-acre vast lush green, master-planned living & learning campus in Warangal, backed by Sri Rajeshwara Educational Society's 1,00,000+ students and 17,000 teaching and non-teaching staff. Boys & Girls hostels with AC/Non-AC options, 24/7 security & CCTV, high-speed Wi-Fi, and a 4,000-seat mega dining hall with healthy hygienic food.",
            "standout": "4,000-Seat Mega Dining Hall",
        },
        {
            "category": "World-Class Faculty",
            "icon": "🎓",
            "sru_highlight": "Faculty holding doctoral and postdoctoral qualifications from IITs, NITs, and prestigious global universities. Research-active professors with international publications bringing real-world expertise into every classroom.",
            "standout": "IIT/NIT PhD Faculty",
        },
        {
            "category": "Global Collaborations",
            "icon": "🤝",
            "sru_highlight": "80+ international academic collaborations enabling semester exchange, joint research, dual degrees, and global exposure. Students access global knowledge networks without leaving the campus.",
            "standout": "80+ Global Tie-Ups",
        },
        {
            "category": "Flexible & Modern Curriculum",
            "icon": "📚",
            "sru_highlight": "Fully Flexible Credit System (FFCS) under Outcome-Based Education — students choose their own faculty and timetable slots. Forward-looking programs in AI, Quantum AI, Robotics, Cybersecurity, Food Technology, and Agri-AI.",
            "standout": "Student-Chosen Timetables",
        },
        {
            "category": "Vibrant Student Life",
            "icon": "🎉",
            "sru_highlight": "20+ student clubs, 50+ annual events, music festivals, cultural programs, hackathons, sports grounds, indoor arenas, and fitness zones — building well-rounded future leaders alongside academic excellence.",
            "standout": "20+ Clubs, 50+ Events/Year",
        },
        {
            "category": "Research Powerhouse",
            "icon": "🔬",
            "sru_highlight": "9,300+ research papers in top journals, 2,900+ patents filed, 159 patents granted, and 130+ top 10% globally cited publications. Ranked 6th in India in Research Quality by THE World University Rankings.",
            "standout": "9,300+ Papers, 2,900+ Patents",
        },
        {
            "category": "50-Year Legacy & Ecosystem",
            "icon": "🏛️",
            "sru_highlight": "Governed by Sri Rajeshwara Educational Society (est. 1976) with 185 institutions across Telangana, AP & Karnataka, serving 1,00,000+ students with 17,000 staff, 7,500+ faculty, and 5 Lakh+ alumni.",
            "standout": "185 Institutions, 5L+ Alumni",
        },
        {
            "category": "Merit Scholarships",
            "icon": "💰",
            "sru_highlight": "Up to 40% tuition fee waiver based on board/entrance scores. 19 special category concessions up to Rs.50,000/year for girl students, defence personnel, differently-abled, sports achievers, and more.",
            "standout": "Up to 40% Scholarship",
        },
    ],
}

CAMPUS_VISIT_FORM_CARD = {
    "type": "campus_visit_form",
    "title": "Schedule Your SR University Campus Visit",
    "subtitle": "Experience our 170-acre lush campus, state-of-the-art AI labs, hostels & sports complex in person.",
    "location": "170-Acre Lush Campus, Ananthasagar, Hasanparthy, Warangal, Telangana",
    "timings": "10:00 AM – 4:00 PM (Monday – Saturday)",
    "phone": "0870-2818333",
}

CAMPUS_TOUR_CARD = {
    "type": "campus_tour",
    "title": "SR University — Next-Generation Living & Learning Campus",
    "subtitle": "Where every step connects with nature, and every breath brings a spark of inspiration.",
    "spots": [
        {
            "name": "Largest Lush Green Campus & Top Rankings",
            "desc": "170-acre vast lush green, master-planned campus for next-generation innovators; NIRF 91st in Engineering (top 100 for 4 years), 19th in QS Asia, 7th in THE India, and 6th in Research Quality.",
            "icon": "🌿",
        },
        {
            "name": "World-Class Faculty & 1,00,000+ Student Heritage",
            "desc": "Doctoral and postdoctoral faculty from IITs, NITs, and top global institutions; backed by Sri Rajeshwara Educational Society's 185 institutions with 1,00,000+ students and 17,000 teaching and non-teaching staff members.",
            "icon": "🎓",
        },
        {
            "name": "Academic & AI/Robotics Infrastructure",
            "desc": "Digital classrooms, Central Library, high-tech labs, industry setups for AI & robotics, project studios, and 80+ international collaborations.",
            "icon": "🏫",
        },
        {
            "name": "Hostels & 4,000-Seat Mega Dining Hall",
            "desc": "'As the academic day comes to an end, the living and learning experience continues.' AC/Non-AC rooms, 24/7 security, Wi-Fi, and 4,000-seat hygienic dining hall.",
            "icon": "🏠",
        },
        {
            "name": "Vibrant Campus Life & Sports",
            "desc": "20+ student clubs, 50+ annual events, cultural music festivals, expansive sports grounds, indoor arenas, and fitness zones.",
            "icon": "⚽",
        },
        {
            "name": "SRiX Startup & Innovation Exchange",
            "desc": "DST-supported incubator powering 171+ startups with maker spaces, rapid prototyping labs, mentoring, and ₹76+ Cr funding.",
            "icon": "🚀",
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
        {"label": "Total Job Offers", "value": "1,300+", "note": "Till April and counting"},
        {"label": "Paid Internships", "value": "3,500+", "note": "Stipends up to ₹1.25L/month"},
        {"label": "Average Package", "value": "6 LPA", "note": "Across graduating cohorts"},
        {"label": "Highest Monthly Stipend", "value": "₹1.25L / mo", "note": "Microsoft (Batch 2025)"},
        {"label": "Top Recruiting MNCs", "value": "80+", "note": "Global tech & Fortune 500 recruiters"},
        {"label": "Placement Support", "value": "100%", "note": "One Student–One Job + Dream option"},
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
        {"student": "Thangallapally Nihal", "batch": "CSE 2025", "package": "44 LPA", "company": "Salesforce"},
        {"student": "Bijigiri Vignesh", "batch": "CSE 2025", "package": "44 LPA", "company": "ServiceNow"},
        {"student": "Ambati Krishna Sai", "batch": "CSE 2025", "package": "44 LPA", "company": "ServiceNow"},
        {"student": "Jonnadula Sahith", "batch": "CSE 2025", "package": "34.5 LPA", "company": "PayPal"},
        {"student": "Harsha Vardhan", "batch": "CSE 2025", "package": "34.5 LPA", "company": "PayPal"},
        {"student": "Repala Vignesh", "batch": "CSE 2025", "package": "25 LPA", "company": "Cisco"},
        {"student": "Suraram Hari Charan", "batch": "CSE 2026", "package": "19.75 LPA", "company": "JPMorgan Chase"},
        {"student": "Nadimadla Sanvitha", "batch": "ECE 2026", "package": "14.5 LPA", "company": "Flipkart"},
    ],
}

PROGRAMS_OFFERED_CARD = {
    "type": "programs_offered",
    "title": "Academic Programs & Degrees Offered by SR University",
    "subtitle": "Multidisciplinary Programs Across 6 Specialized Schools & Doctoral Studies",
    "schools": [
        {
            "name": "School of Computer Science & Artificial Intelligence",
            "short_name": "CS & AI",
            "icon": "💻",
            "highlight": "Cutting-edge curriculum in AI, Quantum Computing, and Advanced Cyber Systems",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "B.Tech Computer Science & Engineering (Core)",
                        "B.Tech CSE — Artificial Intelligence & Machine Learning (AIML)",
                        "B.Tech CSE — Cyber Security",
                        "B.Tech CSE — Data Science",
                        "B.Tech CSE — AI & Precision Agriculture",
                        "B.Tech CSE — Gaming, AR & VR",
                        "B.Tech CSE — Robotics & Automation",
                        "B.Tech CSE — Quantum AI",
                        "B.Tech in Artificial Intelligence & Robotics",
                        "BCA (Bachelor of Computer Applications)",
                        "B.Sc Computer Science",
                        "B.Sc Mathematics",
                        "B.Sc (Hons) Mathematics & AI",
                    ],
                },
                {
                    "level": "Postgraduate (PG)",
                    "degrees": [
                        "M.Tech Computer Science & Engineering",
                        "M.Tech CSE — Artificial Intelligence & Machine Learning",
                        "M.Tech CSE — Data Science",
                        "M.Tech CSE — Cyber Security",
                        "MCA (Master of Computer Applications)",
                        "M.Sc Computer Science",
                        "M.Sc Statistics",
                    ],
                },
            ],
        },
        {
            "name": "School of Engineering",
            "short_name": "Engineering",
            "icon": "⚙️",
            "highlight": "Tier-1 NBA Accredited B.Tech Programs with Smart Robotics & EV Testing Labs",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "B.Tech Electronics & Communication Engineering (AIML / VLSI / Robotics)",
                        "B.Tech Electrical & Electronics Engineering (Renewable Energy / EV / Robotics)",
                        "B.Tech Mechanical Engineering (Robotics & Automation / Smart Manufacturing)",
                        "B.Tech Civil Engineering",
                    ],
                },
                {
                    "level": "Postgraduate (PG)",
                    "degrees": [
                        "M.Tech Embedded Systems",
                        "M.Tech Electronic Design Technology (EDT)",
                        "M.Tech VLSI System Design",
                        "M.Tech Power Electronics",
                        "M.Tech Advanced Manufacturing Systems (AMS)",
                        "M.Tech Thermal Engineering",
                        "M.Tech Construction Technology & Management (CTM)",
                    ],
                },
            ],
        },
        {
            "name": "Astra School of Business",
            "short_name": "Business",
            "icon": "📊",
            "highlight": "Modern Case-Study & Business Analytics Pedagogy with Global Networking",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "BBA (General Management)",
                        "BBA (Finance, Operations, HR, Business Analytics, Marketing)",
                        "BBA (Hospitality & Event Management)",
                        "B.Com (Bachelor of Commerce)",
                    ],
                },
                {
                    "level": "Postgraduate (PG)",
                    "degrees": [
                        "MBA (Finance, Operations, HR, Business Analytics, Marketing)",
                        "MBA in Agri-Business Management",
                    ],
                },
            ],
        },
        {
            "name": "School of Agriculture",
            "short_name": "Agriculture",
            "icon": "🌾",
            "highlight": "ICAR-Accredited — 1st Private University in the Telugu States to achieve accreditation",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "B.Sc. (Hons.) Agriculture (ICAR-Accredited)",
                        "B.Tech Food Technology",
                    ],
                },
                {
                    "level": "Postgraduate (PG)",
                    "degrees": [
                        "M.Sc. Agriculture (Agronomy)",
                        "M.Sc. Agriculture (Genetics & Plant Breeding)",
                        "M.Sc. Agriculture (Horticulture)",
                        "M.Sc. Agriculture (Plant Pathology)",
                        "M.Sc. Agriculture (Soil Science)",
                        "M.Sc. Agriculture (Agricultural Economics)",
                    ],
                },
            ],
        },
        {
            "name": "School of Design",
            "short_name": "Design",
            "icon": "🎨",
            "highlight": "Studio-Based Creative & Digital Prototyping Pathways with Industry Mentors",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "B.Des Interior Design",
                        "B.Des Fashion Design",
                    ],
                },
            ],
        },
        {
            "name": "School of Sciences and Humanities",
            "short_name": "Sciences & Humanities",
            "icon": "🔬",
            "highlight": "Interdisciplinary Research in AI, Biotechnology & Space Engineering",
            "programs": [
                {
                    "level": "Undergraduate (UG)",
                    "degrees": [
                        "B.Sc (Physics, Chemistry, Biology)",
                        "B.Tech Biotechnology with AI",
                        "B.Tech Engineering Physics in AI / Robotics / Space Sciences",
                        "B.Tech Applied Chemistry in AI / Nano-Robotics / Drug Discovery",
                    ],
                },
                {
                    "level": "Postgraduate (PG)",
                    "degrees": [
                        "M.Sc Physics",
                        "M.Sc Chemistry",
                        "M.Sc Biotechnology & AI",
                        "M.A. English",
                    ],
                },
            ],
        },
        {
            "name": "Doctoral Studies & Research",
            "short_name": "Ph.D. Studies",
            "icon": "🎓",
            "highlight": "Full-Time & Part-Time Doctoral Research Across All Specializations",
            "programs": [
                {
                    "level": "Doctoral",
                    "degrees": [
                        "Ph.D. in Computer Science & Artificial Intelligence",
                        "Ph.D. in Engineering (ECE, EEE, Mechanical, Civil)",
                        "Ph.D. in Management & Business Studies",
                        "Ph.D. in Agricultural Sciences",
                        "Ph.D. in Basic Sciences & Humanities",
                    ],
                },
            ],
        },
    ],
}


# Session memory for shown cards to prevent repeating cards within the same session
_SESSION_SHOWN_CARDS: dict[str, set[str]] = {}


def get_session_shown_cards(session_id: str) -> set[str]:
    """Retrieve the set of card types already shown in the given session."""
    if not session_id:
        return set()
    return _SESSION_SHOWN_CARDS.setdefault(session_id, set())


def record_session_card(session_id: str, card_type: str) -> None:
    """Record that a card type has been shown in the session."""
    if session_id and card_type:
        _SESSION_SHOWN_CARDS.setdefault(session_id, set()).add(card_type)


def clear_session_cards(session_id: str | None = None) -> None:
    """Clear session shown cards (for testing or session reset)."""
    if session_id:
        _SESSION_SHOWN_CARDS.pop(session_id, None)
    else:
        _SESSION_SHOWN_CARDS.clear()


def generate_cards(
    user_message: str,
    answer: str,
    profile: dict | None = None,
    sources: list[dict] | None = None,
    query_embedding: list[float] | None = None,
    is_video_confirmed: bool = False,
    session_id: str | None = None,
    seen_card_types: set[str] | None = None,
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

    is_cse_join_query = any(k in msg_lower for k in ("cse", "computer science")) and any(
        k in msg_lower for k in (
            "join", "want to join", "how to join", "admission", "take admission",
            "enroll", "enrol", "apply for cse", "apply cse", "seat in cse",
            "joining", "btech cse join", "select cse", "interested in cse", "opt cse", "choose cse"
        )
    )

    is_cse_fee_query = is_cse_join_query or (
        any(k in msg_lower for k in ("cse", "computer science")) and any(
            k in msg_lower for k in ("fee", "fees", "tuition", "cost", "charge", "how much", "breakdown", "per sem", "semester", "sem fee")
        ) and not any(k in msg_lower for k in ("all branches", "complete fee", "other branches", "overall", "fee structure"))
    )

    is_ad_query = any(k in msg_lower for k in (
        "50% off", "50% discount", "early bird", "application discount", "application fee discount",
        "sponsored", "discount on application", "cheap application", "coupon", "promo", "voucher", "early ad"
    )) or bool(re.search(r"\bad\b", msg_lower)) or (
        any(k in msg_lower for k in ("apply online", "how to apply", "application form", "apply now", "register online", "online application"))
        and not any(k in msg_lower for k in ("transport", "bus", "hostel", "admission fee", "one-time", "enrollment fee"))
    )

    is_join_interest_query = (
        any(k in msg_lower for k in (
            "interested to join", "interested in joining", "want to join", "how to join",
            "how can i join", "like to join", "wishing to join", "planning to join",
            "join sru", "join sr university", "join sr", "join the university",
            "take admission in sru", "take admission at sru", "get admission in sru",
            "admission in sru", "admissions in sru", "admission at sru", "admission process",
            "how to get admission", "how do i get admission", "how can i get admission",
            "apply to sru", "apply at sru", "how to apply to sru", "apply for sru",
            "interested in admission", "interested in sru", "interested to study at sru",
            "want to study at sru", "enroll at sru", "enrol at sru", "seat in sru",
            "how to get a seat in sru", "admission open", "eligibility to join",
            "can i join sru", "can i get admission in sru", "admission procedure",
            "join btech", "join b.tech", "join mba", "join bba", "join mtech"
        )) or is_cse_join_query or (
            any(k in msg_lower for k in ("join", "take admission", "interested in joining", "want to join")) and
            any(k in msg_lower for k in ("sru", "sr university", "here", "college", "campus", "this university"))
        )
    ) and not is_admission_fee_query


    is_fee_with_hostel_query = any(k in msg_lower for k in (
        "with hostel", "including hostel", "plus hostel", "hostel and tuition",
        "tuition and hostel", "both tuition and hostel", "and hostel fee", "add hostel",
        "hostel fee included", "fee along with hostel", "along with hostel"
    )) or (
        any(k in msg_lower for k in ("hostel", "mess", "boarding")) and
        any(k in msg_lower for k in ("tuition", "cse fee", "btech fee", "b.tech fee", "total fee", "per sem"))
    )

    is_btech_fee_query = any(k in msg_lower for k in ("btech", "b.tech", "engineering fee", "btech fee", "b.tech fee")) or (
        any(k in msg_lower for k in ("btech", "b.tech")) and any(k in msg_lower for k in ("fee", "fees", "tuition", "cost", "scholarship"))
    )

    if is_transport_fee_query:
        cards.append(TRANSPORT_FEE_CARD)
    elif is_fee_with_hostel_query:
        # User explicitly asked to include hostel in the fee breakdown
        cards.append(BTECH_CSE_WITH_HOSTEL_FEE_CARD)
    elif is_hostel_fee_query and not (is_cse_fee_query or is_btech_fee_query):
        # User asked purely for hostel fees
        cards.append(HOSTEL_FEE_CARD)
    elif is_exam_fee_query:
        cards.append(EXAM_FEE_CARD)
    elif is_admission_fee_query:
        cards.append(ADMISSION_FEE_CARD)
    elif is_scholarship_only_query:
        cards.append(MERIT_SCHOLARSHIP_CARD)
    elif is_cse_fee_query:
        # User asked for CSE fee WITHOUT hostel (hostel not added)
        cards.append(BTECH_CSE_SEMESTER_FEE_CARD)
    elif is_btech_fee_query:
        cards.append(BTECH_ACADEMIC_FEE_CARD)
    elif any(k in msg_lower for k in ("fee", "fees", "tuition", "cost of study", "how much is the fee")):
        # Only attach general breakdown if user explicitly asked for program fee structure / breakdown
        if any(k in msg_lower for k in ("structure", "complete fee", "breakdown", "all fees", "details", "academic", "tuition")):
            if not any(k in msg_lower for k in ("transport", "bus", "hostel", "mess", "exam")):
                cards.append(BTECH_ACADEMIC_FEE_CARD)


    # 2b. Sponsored Early Bird Application Ad Card (media_1794676975023.png reference)
    # Attached whenever student is interested in joining SRU, querying application discount, applying online, or early bird offers
    if (is_join_interest_query or is_ad_query or (is_cse_fee_query and any(k in msg_lower for k in ("join", "admission", "apply", "want", "breakdown")))) and not is_admission_fee_query:
        if APPLICATION_AD_CARD not in cards:
            cards.append(APPLICATION_AD_CARD)



    # 3. Curriculum card
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subjects", "course structure", "credits")) and (
        "cse" in msg_lower or "computer science" in msg_lower or "engineering" in msg_lower
    ):
        cards.append(CURRICULUM_CARD)

    # 3b. Academic Programs & Courses Offered card
    is_courses_query = any(
        k in msg_lower for k in (
            "course", "courses", "programs", "programmes", "what can i study",
            "what does sru offer", "courses offered", "programs offered",
            "degrees offered", "branches available", "what streams", "degrees",
            "schools and courses", "which courses", "all courses", "list of courses",
            "what to study", "fields of study", "specializations offered", "schools offered"
        )
    ) and not any(k in msg_lower for k in ("fee", "fees", "cost", "how much", "tuition", "vs", "compare", "curriculum", "syllabus"))
    if is_courses_query:
        cards.append(PROGRAMS_OFFERED_CARD)

    # 4. Placement Highlights card ("Three Consecutive Years of Excellence")
    if any(k in msg_lower for k in ("placement", "placements", "highest package", "average package", "recruiters", "job offers", "internship", "internships", "superstar", "highest offer", "salary", "ctc", "highest ctc", "jobs", "career", "companies visiting", "recruitment")):
        cards.append(PLACEMENT_EXCELLENCE_CARD)

    # 4b. Interactive Campus Visit Booking Box (Form card to schedule an in-person campus visit)
    _visit_booking_triggers = (
        "book campus tour", "schedule campus visit", "how can i book a campus tour",
        "book a campus tour", "schedule visit", "book a visit", "book a tour",
        "schedule a tour", "schedule tour", "tour booking", "campus visit booking",
        "how to book a visit", "i want to book a visit", "i want to schedule a visit",
        "register for campus visit", "reserve a slot", "book my visit",
    )
    is_visit_booking_query = any(k in msg_lower for k in _visit_booking_triggers) and not any(k in msg_lower for k in ("fee", "fees", "cost", "vs", "compare"))
    if is_visit_booking_query:
        cards.append(CAMPUS_VISIT_FORM_CARD)

    # 5. Campus tour card (render static spot highlights if asking for about sru, campus walkthrough/tour, or facilities)
    is_video_query = (
        is_explicit_video_query(user_message)
        and is_video_topic_query(user_message)
    )
    if not is_video_query and not is_visit_booking_query and any(k in msg_lower for k in ("campus tour", "campus walkthrough", "see the campus", "visit the campus", "campus facilities", "about sru", "tell me about sru", "about sr university", "why sru", "why choose sru", "campus life", "overview of sru", "tell me about the university", "what is sru", "what is sr university", "describe sru")):
        if not any(k in msg_lower for k in ("fee", "cost", "vs")):
            # Show Campus Tour card only the 1st time in a session
            already_shown = False
            if session_id and "campus_tour" in get_session_shown_cards(session_id):
                already_shown = True
            if seen_card_types and "campus_tour" in seen_card_types:
                already_shown = True

            if not already_shown:
                cards.append(CAMPUS_TOUR_CARD)
                if session_id:
                    record_session_card(session_id, "campus_tour")

    # 5b. SRU Advantage Comparison Card — triggered on comparison / "why SRU" intent
    _comparison_triggers = (
        "why sru", "why choose sru", "why should i choose sru", "is sru good",
        "compare sru", "sru vs", "how is sru different", "is sru better",
        "what makes sru unique", "sru better than", "sru special",
        "advantages of sru", "benefits of sru", "sru advantage",
        "what sru offers", "sru unique", "sru stand out", "sru stands out",
        "compare with other", "how does sru compare", "sru worth it",
        "is sru worth", "sru highlight", "sru highlights",
    )
    if any(k in msg_lower for k in _comparison_triggers):
        cards.append(SRU_ADVANTAGE_CARD)

    # 6. University YouTube Media Recommendations (Dense Semantic Search via ChromaDB)
    # Zero keyword matching: relevance is governed purely by ChromaDB semantic cosine distance.
    # Directly displayed for visual / campus / placement queries or when asked/confirmed.
    if query_embedding:
        is_explicit_req = is_video_query or is_explicit_video_query(user_message)
        should_show_videos = is_explicit_req or is_video_confirmed or should_display_videos(user_message)
        if should_show_videos:
            relevant_videos = get_relevant_videos(
                user_message=user_message,
                answer=answer,
                sources=sources,
                query_embedding=query_embedding,
                is_explicit=is_explicit_req,
            )
            if relevant_videos:
                cards.append(create_video_card(relevant_videos, is_explicit=is_explicit_req))

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
