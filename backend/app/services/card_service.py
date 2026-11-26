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

# ---- Fee cards: every amount is produced by the ONE fee engine (app/sru_agent/fees.py) --------------
# Nothing here is typed by hand. The cards used to carry their own figures (and split the other/exam fees
# across both semesters); they are now built from fee_policy_2027_28.json through fees.fee_schedule, the
# same calculator the chat, the admission flow and the website calculator use.
def _fees():
    from app.sru_agent import fees
    return fees


def _schedule_items(program_key: str, pct: float = 0, **options) -> tuple[list[dict], dict]:
    """Year-1 semester rows for a fee_breakdown card, straight from the engine."""
    f = _fees()
    plan = f.fee_schedule(program_key, pct, **options)
    y1 = plan["years"][0]
    items = []
    for sem in y1["semesters"]:
        n = sem["semester"]
        for it in sem["items"]:
            note = {"tuition": "Annual tuition split equally between the two semesters",
                    "enrollment_fee": "One-time, Year 1", "exam_fee": "Year 1 only",
                    "other_fee": "Annual, paid in Semester 1", "electricity_deposit": "One-time, refundable rules per hostel office",
                    }.get(it["key"], "Optional" if it["kind"] == "optional" else "")
            items.append({"category": f"Semester {n}: {it['label']}", "amount": f.inr(it["amount"]),
                          "frequency": f"Semester {n}", "note": note})
        items.append({"category": f"Semester {n} payable", "amount": f.inr(sem["total"]),
                      "frequency": f"Semester {n}", "note": "Total for this semester", "is_total": True})
    items.append({"category": "First-year payable", "amount": f.inr(y1["total"]), "frequency": "Year 1",
                  "note": "Semester 1 + Semester 2", "is_total": True})
    return items, plan


def _build_btech_fee_table_card() -> dict:
    f = _fees()
    data = f.load_data()
    rows = []
    for key in ("btech_cse", "btech_ai_robotics", "btech_ece", "btech_iep", "btech_mech"):
        p = data["programs"][key]
        label = ("B.Tech Core (Mech / Civil / EEE / Biotech / Food Tech / Engg Physics)" if key == "btech_mech"
                 else f.short_name(key))
        rows.append({"category": f"Tuition: {label}", "amount": f"{f.inr(p['tuition_per_year'])} / Year",
                     "frequency": f"{f.inr(p['tuition_per_year'] / 2)} tuition per semester",
                     "note": f"+{f.inr(p['yearly_increase'])} a year from Year 2; minimum {p['min_percent']:g}% in Intermediate"})
    ch = data["charges"]
    rows += [
        {"category": "Enrollment fee", "amount": f.inr(ch["enrollment_fee"]["amount"]), "frequency": "One-time",
         "note": "Semester 1, Year 1"},
        {"category": "Other fee", "amount": f"{f.inr(ch['other_fee']['amount'])} / Year", "frequency": "Annual",
         "note": "Paid in Semester 1 of each year"},
        {"category": "Exam fee (Year 1)", "amount": f.inr(ch["exam_fee"]["amount"]), "frequency": "Year 1 only",
         "note": "Semester 1, Year 1"},
        {"category": "Specialisation fee (B.Tech CSE)", "amount": f"{f.inr(ch['specialization_fee']['amount'])} / Year",
         "frequency": "From Year 2", "note": "Only when a specialisation applies"},
    ]
    return {"type": "fee_breakdown", "title": f"B.Tech Tuition & Fee Components ({data['academic_year']})",
            "currency": "INR", "items": rows,
            "scholarship_note": ("Merit scholarships (10% to 40%) reduce tuition only. The application form fee "
                                 f"({f.inr(ch['application_fee']['amount'])}) is paid separately.")}


def _build_cse_semester_card(hostel: str | None = None) -> dict:
    f = _fees()
    data = f.load_data()
    items, plan = _schedule_items("btech_cse", 0, hostel=hostel)
    with_h = f" + Hostel ({f.HOSTEL_LABELS.get(hostel)})" if hostel else ""
    note = ("Standard fee (no scholarship). Only tuition is split between semesters; the enrollment, other and "
            "Year-1 exam fees are paid in Semester 1. Application form fee "
            f"{f.inr(plan['application_fee'])} is paid separately.")
    if hostel:
        note += " Hostel fees are not on the fee circular and are confirmed by the Admissions Office."
    y1 = plan["years"][0]
    semesters = [{"semester": s["semester"], "total": f.inr(s["total"]),
                  "items": [{"item": i["label"], "amount": f.inr(i["amount"]), "kind": i["kind"]} for i in s["items"]]}
                 for s in y1["semesters"]]
    return {"type": "fee_breakdown",
            "title": f"B.Tech CSE{with_h}: Semester-wise Fee, Year 1 ({data['academic_year']})",
            "currency": "INR", "items": items, "semesters": semesters, "first_year_total": f.inr(y1["total"]),
            "scholarship_note": note, "note_label": "Note"}


def _build_merit_scholarship_card() -> dict:
    f = _fees()
    data = f.load_data()
    ug = data["slab_sets"]["ug"]
    base = data["programs"]["btech_cse"]["tuition_per_year"]
    names = {"state_board": "Inter", "cbse": "CBSE/ICSE", "jee_percentile": "JEE", "eapcet_rank": "EAPCET", "ib": "IB"}
    items = []
    for pct in (40, 30, 25, 20, 15, 10):
        parts = []
        for kind, table in ug.items():
            hit = [s for s in table if s["percent"] == pct]
            if hit:
                parts.append(f"{names[kind]} {f._range_text(kind, hit[0])}")
        items.append({"category": f"{pct}% tuition scholarship",
                      "amount": f"{f.inr(base * (100 - pct) / 100)} / Year (CSE)",
                      "frequency": f"Save {f.inr(base * pct / 100)} / Year", "note": " | ".join(parts)})
    return {"type": "fee_breakdown", "title": f"Merit Scholarship Slabs, UG ({data['academic_year']})",
            "currency": "INR", "items": items,
            "scholarship_note": (f"Shown on B.Tech CSE tuition ({f.inr(base)} a year). Scholarships apply to tuition "
                                 "only, never to other charges. Standard fee from 55% for CSE/ECE and 50% for other "
                                 "programmes. Subject to marksheet verification.")}


BTECH_ACADEMIC_FEE_CARD = _build_btech_fee_table_card()
FEE_BREAKDOWN_CARD = BTECH_ACADEMIC_FEE_CARD
BTECH_CSE_SEMESTER_FEE_CARD = _build_cse_semester_card()
BTECH_CSE_WITH_HOSTEL_FEE_CARD = _build_cse_semester_card("ac_4")
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




MERIT_SCHOLARSHIP_CARD = _build_merit_scholarship_card()


# ---- Charge cards: built from app/sru_agent/fee_policy_2027_28.json (the fee circular), never typed by hand.
def _fee_data() -> dict:
    from app.sru_agent import fees
    return fees.load_data()


def _inr(amount) -> str:
    from app.sru_agent import fees
    return fees.inr(amount)


def _build_transport_fee_card() -> dict:
    data = _fee_data()
    bus = data["charges"]["bus"]["amount"]
    return {
        "type": "fee_breakdown",
        "title": f"SR University Transport & Bus Fee ({data['academic_year']})",
        "currency": "INR",
        "items": [
            {
                "category": "University Bus: Tri-Cities (Warangal, Hanamkonda, Kazipet) and outstation routes",
                "amount": _inr(bus),
                "frequency": "Per Year",
                "note": "Optional; added to your fee only if you choose the bus. GPS-tracked fleet with pickup stops across the tri-cities",
            },
        ],
        "scholarship_note": "Transport in-charge: Mr. A. Keerthi Reddy (9640606408, transport@sru.edu.in).",
    }


def _build_hostel_fee_card() -> dict:
    from app.sru_agent import fees
    data = _fee_data()
    hostel = fees.hostel_per_year()
    elec = data["charges"]["electricity_deposit"]
    amenities = "4 meals daily in the 4,000-seat mega dining hall, 24/7 Wi-Fi, study areas & power backup"
    rooms = (("non_ac_4", "Non-AC 4-Sharing"), ("non_ac_3", "Non-AC 3-Sharing"),
             ("ac_4", "AC 4-Sharing"), ("ac_3", "AC 3-Sharing"))
    return {
        "type": "fee_breakdown",
        "title": f"SR University Residential Hostel & Dining Fees (Annual, {data['academic_year']})",
        "subtitle": "As the academic day comes to an end, the living and learning experience continues.",
        "currency": "INR",
        "items": [
            {
                "category": f"Boys Hostel / Girls Hostel ({label})",
                "amount": _inr(hostel[key]),
                "frequency": "Per Year",
                "note": amenities,
            }
            for key, label in rooms
        ] + [
            {"category": "Electricity deposit (one-time)", "amount": f"{_inr(elec['non_ac'])} Non-AC / {_inr(elec['ac'])} AC",
             "frequency": "One-time", "note": "From the 2027-28 fee circular; paid in the first hostel semester"},
        ],
        "scholarship_note": (
            "Room and meals are included. Hostel is optional. Hostel room fees are not on the 2027-28 fee circular, "
            "so the Admissions Office confirms them; the electricity deposit is from the circular."
        ),
    }


def _build_admission_fee_card() -> dict:
    data = _fee_data()
    ch = data["charges"]
    return {
        "type": "fee_breakdown",
        "title": "SR University One-Time Admission & Enrollment Fees",
        "currency": "INR",
        "items": [
            {
                "category": "Enrollment Fee (One-time)",
                "amount": _inr(ch["enrollment_fee"]["amount"]),
                "frequency": "One-time (Semester 1, Year 1)",
                "note": "Paid once with the first semester fee",
            },
            {
                "category": "Admission Application Form Fee",
                "amount": _inr(ch["application_fee"]["amount"]),
                "frequency": "One-time (when applying)",
                "note": "Paid with the online application at apply.sru.edu.in; not part of any semester fee",
            },
        ],
        "scholarship_note": f"{data['academic_year']} fee circular. Tuition and other charges are separate.",
    }


def _build_other_fees_card() -> dict:
    data = _fee_data()
    ch = data["charges"]
    return {
        "type": "fee_breakdown",
        "title": f"SR University Other Fees & Annual Charges ({data['academic_year']})",
        "subtitle": "Fee components other than tuition, from the official fee circular",
        "currency": "INR",
        "items": [
            {"category": "Enrollment Fee", "amount": _inr(ch["enrollment_fee"]["amount"]),
             "frequency": "One-time", "note": "Semester 1 of Year 1"},
            {"category": "Other Fee", "amount": _inr(ch["other_fee"]["amount"]),
             "frequency": "Per Year", "note": "Paid in Semester 1 of each year (not split)"},
            {"category": "Exam Fee (Year 1)", "amount": _inr(ch["exam_fee"]["amount"]),
             "frequency": "Year 1 only", "note": "Semester 1 of Year 1"},
            {"category": "Application Form Fee", "amount": _inr(ch["application_fee"]["amount"]),
             "frequency": "One-time, at application", "note": "Paid separately with the online application"},
            {"category": "Specialisation Fee", "amount": _inr(ch["specialization_fee"]["amount"]),
             "frequency": "Per Year, from Year 2", "note": "Only where a specialisation applies; never in Year 1"},
            {"category": "PhD Fee", "amount": _inr(ch["phd_fee"]["amount"]),
             "frequency": "Per Year", "note": "Annual fee for doctoral research scholars"},
        ],
        "scholarship_note": (
            f"Optional: University Bus {_inr(ch['bus']['amount'])} a year; hostel electricity deposit "
            f"{_inr(ch['electricity_deposit']['non_ac'])} (Non-AC) / {_inr(ch['electricity_deposit']['ac'])} (AC), one-time. "
            "Merit scholarships apply to tuition only, never to these charges."
        ),
    }


def _build_exam_fee_card() -> dict:
    data = _fee_data()
    return {
        "type": "fee_breakdown",
        "title": "SR University Examination Fee",
        "currency": "INR",
        "items": [{"category": "Exam Fee (Year 1)", "amount": _inr(data["charges"]["exam_fee"]["amount"]),
                   "frequency": "Year 1 only", "note": "Paid in Semester 1 of Year 1, as on the 2027-28 fee circular"}],
    }


def _build_hostel_facilities_card() -> dict:
    return {
        "type": "hostel_facilities",
        "title": "SR University Residential Living & Campus Hostels",
        "subtitle": "Safe, vibrant, and disciplined residential living on campus",
        "room_types": [
            {
                "name": "3-Sharing & 4-Sharing AC",
                "amenities": "Air-conditioned comfort, dedicated study desk, ergonomic chair, personal wardrobe & power backup",
            },
            {
                "name": "3-Sharing & 4-Sharing Non-AC",
                "amenities": "Well-ventilated spacious rooms, dedicated study desk, ergonomic chair, personal wardrobe & 24/7 Wi-Fi",
            },
        ],
        "amenities": [
            {
                "icon": "wifi",
                "title": "High-Speed Wi-Fi",
                "desc": "24/7 campus fiber internet access across all rooms and study lounges",
            },
            {
                "icon": "dining",
                "title": "4,000-Seat Mega Dining",
                "desc": "4 wholesome meals/day (Breakfast, Lunch, Snacks, Dinner) with unlimited veg/non-veg buffet",
            },
            {
                "icon": "security",
                "title": "24/7 Security & CCTV",
                "desc": "Complete CCTV coverage, biometric attendance & dedicated security personnel",
            },
            {
                "icon": "medical",
                "title": "Health Center & Ambulance",
                "desc": "On-campus health clinic, resident nurses, 24/7 stationed ambulance & tie-up with Aaditya Hospital",
            },
            {
                "icon": "water",
                "title": "Purified RO & Hot Water",
                "desc": "RO stations on every floor; solar hot water supply (7:00–9:00 AM & 7:00–9:00 PM)",
            },
            {
                "icon": "sports",
                "title": "Gym & Indoor Sports",
                "desc": "Fitness center, indoor gymnasium, badminton, table tennis & recreation halls",
            },
        ],
        "rules_summary": [
            "Curfew In-Time: 9:00 PM (Mon–Fri) | 9:30 PM (Weekends & Holidays)",
            "Biometric Roll Call: 9:00 PM – 9:30 PM nightly across all blocks",
            "Digital Out-Pass: Required via Sruniv portal with parent SMS verification",
            "Zero Tolerance: 100% ragging-free campus, anti-substance policy & 10:00 PM silence hours",
        ],
    }


TRANSPORT_FEE_CARD = _build_transport_fee_card()

HOSTEL_FEE_CARD = _build_hostel_fee_card()

HOSTEL_FACILITIES_CARD = _build_hostel_facilities_card()

EXAM_FEE_CARD = _build_exam_fee_card()

ADMISSION_FEE_CARD = _build_admission_fee_card()
OTHER_FEES_CARD = _build_other_fees_card()


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
            "sru_highlight": "9,300+ research papers in top journals, 2,700+ patents filed, 159 patents granted, and 130+ top 10% globally cited publications. Ranked 6th in India in Research Quality by THE World University Rankings.",
            "standout": "9,300+ Papers, 2,700+ Patents",
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
            "sru_highlight": "Up to 40% tuition fee waiver based on board/entrance scores. 20 special category concessions up to Rs.50,000/year for girl students, defence personnel, differently-abled, sports achievers, and more.",
            "standout": "Up to 40% Scholarship",
        },
    ],
}

# Campus visits are arranged by the admissions team (sru.edu.in/visit-us); SRU Buddy never books or
# confirms one (admissions brief, Nov 2026). This card shows whom to contact; it has no booking form.
CAMPUS_VISIT_CONTACT_CARD = {
    "type": "campus_visit_contact",
    "title": "Plan your campus visit with the admissions team",
    "subtitle": "Visits are arranged and confirmed by the SR University admissions team. Please contact them "
                "before you travel.",
    "address": "SR University, Ananthasagar, Hasanparthy, Warangal Urban 506371, Telangana",
    "phone": "833 100 4040",
    "mobile": "833 100 4040",
    "whatsapp": "https://wa.me/918331004040?text=Hi%2C%20I%20would%20like%20to%20visit%20the%20SR%20University%20campus.",
    "visit_page": "https://sru.edu.in/visit-us",
}
# Older name, kept so existing imports keep working.
CAMPUS_VISIT_FORM_CARD = CAMPUS_VISIT_CONTACT_CARD

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


# ---------------------------------------------------------------------------
# WELCOME QUICK-ACTION TILES (shown under the opening welcome message, each with an incentive badge).
# The opening message is built in the browser (frontend/src/pages/ChatPage.tsx, WELCOME_QUICK_ACTIONS
# in components/Cards.tsx); keep the two lists the same. Badges use verified facts only: fee card
# slabs (up to 40%), NIRF 2025 Engineering rank 91, placements page (highest 51 LPA, 150+ recruiters,
# 1,300+ offers).
# ---------------------------------------------------------------------------
WELCOME_ACTIONS_CARD = {
    "type": "welcome_actions",
    "heading": "⚡ Quick start",
    "items": [
        {
            "id": "calculate_scholarship",
            "icon": "calculator",
            "color": "green",
            "badge": "Up to 40% off",
            "title": "Calculate My Scholarship",
            "subtitle": "Instant fee estimate in a few steps",
            "prompt": "Calculate my scholarship",
        },
        {
            "id": "explore_programs",
            "icon": "graduation-cap",
            "color": "blue",
            "badge": "NIRF #91",
            "title": "Explore Programmes",
            "subtitle": "B.Tech, MBA, Agriculture & more",
            "prompt": "Explore programs offered at SR University",
        },
        {
            "id": "placements",
            "icon": "briefcase",
            "color": "purple",
            "badge": "₹51 LPA",
            "title": "Placements & Careers",
            "subtitle": "150+ recruiters, 1,300+ offers",
            "prompt": "Tell me about placements at SRU",
        },
        {
            # v4.11.0: was "How to Apply" (still answered when asked). Starts the fee evaluation agent's
            # special consideration flow (sru_agent/fee_journey.py).
            "id": "special_consideration",
            "icon": "heart",
            "color": "amber",
            "badge": "₹15K–₹50K/yr",
            "title": "Special Consideration",
            "subtitle": "Check concessions you may qualify for",
            "prompt": "Special consideration",
        },
    ],
}


# Chips after the personal greeting: different topics from the four welcome tiles, so nothing repeats.
POST_WELCOME_CHIPS = ("B.Tech CSE fees", "Hostel fees & facilities", "Placements at SRU", "Plan a campus visit")


# Session memory for shown cards to prevent repeating cards within the same session.
# Externalized to Redis (sru:shown_cards:{session_id}, TTL 24h) for multi-worker consistency.
_SESSION_SHOWN_CARDS: dict[str, set[str]] = {}
_SHOWN_CARDS_TTL = 86400


def _redis_cards_key(session_id: str) -> str:
    return f"sru:shown_cards:{session_id}"


def _get_agent_redis():
    try:
        from app.sru_agent import memory
        return memory.get_redis()
    except Exception:
        return None


def get_session_shown_cards(session_id: str) -> set[str]:
    """Retrieve the set of card types already shown in the given session."""
    if not session_id:
        return set()
    return _SESSION_SHOWN_CARDS.setdefault(session_id, set())


async def get_session_shown_cards_async(session_id: str) -> set[str]:
    """Retrieve shown card types from Redis (multi-worker safe) with local fallback."""
    if not session_id:
        return set()
    r = _get_agent_redis()
    if r is not None:
        try:
            members = await r.smembers(_redis_cards_key(session_id))
            if members:
                local = _SESSION_SHOWN_CARDS.setdefault(session_id, set())
                local.update(str(m) for m in members)
                return set(local)
        except Exception:
            pass
    return set(get_session_shown_cards(session_id))


def record_session_card(session_id: str, card_type: str) -> None:
    """Record that a card type has been shown in the session (sync + background Redis)."""
    if not (session_id and card_type):
        return
    _SESSION_SHOWN_CARDS.setdefault(session_id, set()).add(card_type)
    r = _get_agent_redis()
    if r is not None:
        try:
            from app.sru_agent import memory
            async def _push():
                key = _redis_cards_key(session_id)
                await r.sadd(key, card_type)
                await r.expire(key, _SHOWN_CARDS_TTL)
            memory.in_background(_push(), "shown_cards")
        except Exception:
            pass


async def record_session_card_async(session_id: str, card_type: str) -> None:
    """Record a shown card directly in Redis and local cache."""
    if not (session_id and card_type):
        return
    _SESSION_SHOWN_CARDS.setdefault(session_id, set()).add(card_type)
    r = _get_agent_redis()
    if r is not None:
        try:
            key = _redis_cards_key(session_id)
            await r.sadd(key, card_type)
            await r.expire(key, _SHOWN_CARDS_TTL)
        except Exception:
            pass


def clear_session_cards(session_id: str | None = None) -> None:
    """Clear session shown cards (for testing or session reset)."""
    if session_id:
        _SESSION_SHOWN_CARDS.pop(session_id, None)
        r = _get_agent_redis()
        if r is not None:
            try:
                from app.sru_agent import memory
                memory.in_background(r.delete(_redis_cards_key(session_id)), "clear_shown_cards")
            except Exception:
                pass
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
    keyword_videos: bool = False,
) -> list[dict]:
    """Generate structured interactive cards based on message context and student profile."""
    cards = []
    msg_lower = user_message.lower()
    ans_lower = answer.lower()

    def _can_show(card_type: str) -> bool:
        if session_id and card_type in get_session_shown_cards(session_id):
            return False
        if seen_card_types and card_type in seen_card_types:
            return False
        return True

    def _mark_shown(card_type: str) -> None:
        if session_id:
            record_session_card(session_id, card_type)

    # 0. Branch comparison card (Shown at most once per session)
    # Only for CSE (core) vs CSE (AI & ML): "cse vs ece" or a fee comparison must not get this card.
    if any(k in msg_lower for k in ("vs", "compare", "comparison", "difference")) and "cse" in msg_lower and re.search(
        r"\b(?:aiml|ai\s*&\s*ml|ai\s+and\s+ml|ai\s*/\s*ml|machine\s+learning)\b", msg_lower
    ) and not re.search(r"\b(?:fee|fees|cost|tuition)\b", msg_lower):
        if _can_show("comparison"):
            cards.append(COMPARISON_CSE_AIML)
            _mark_shown("comparison")

    # 1. Fee breakdown card (Strict Category Scoping — show only what the user asks for)
    is_other_fee_query = bool(re.search(
        r"\b(?:other\s+fees?|other\s+academic(?:\s*/\s*university|\s+university)?\s+charges?|other\s+charges?|annual\s+charges?|"
        r"university\s+charges?|additional\s+fees?|additional\s+charges?|enrolment\s+fee|enrollment\s+fee|application\s+form\s+fee|"
        r"specialisation\s+fee|specialization\s+fee|phd\s+fee|"
        r"fees?\s+(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee)|"
        r"(?:other\s+than|apart\s+from|besides|excluding|except)\s+(?:sem(?:ester)?\s+fee|tuition(?:\s+fee)?|course\s+fee))\b",
        msg_lower,
    ))

    is_transport_fee_query = any(k in msg_lower for k in ("bus", "transport", "commute", "van")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "pass", "ticket")
    )
    is_hostel_fee_query = any(k in msg_lower for k in ("hostel", "mess", "boarding", "room rent")) and any(
        k in msg_lower for k in ("fee", "fees", "cost", "charge", "price", "how much", "rate", "package")
    )
    is_hostel_facilities_query = any(k in msg_lower for k in ("hostel", "hostels", "dorm", "accommodation", "boarding", "residential")) and not is_hostel_fee_query
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

    is_cse_fee_query = not is_other_fee_query and (is_cse_join_query or (
        any(k in msg_lower for k in ("cse", "computer science")) and any(
            k in msg_lower for k in ("fee", "fees", "tuition", "cost", "charge", "how much", "breakdown", "per sem", "semester", "sem fee")
        ) and not any(k in msg_lower for k in ("all branches", "complete fee", "other branches", "overall", "fee structure"))
        # a comparison with another programme ("cse vs ece fees") never gets a CSE-only card
        and not re.search(r"\b(?:vs|versus|compar\w*|difference)\b", msg_lower)
    ))

    is_ad_query = any(k in msg_lower for k in (
        "50% off", "50% discount", "early bird", "application discount", "application fee discount",
        "sponsored", "discount on application", "cheap application", "coupon", "promo", "voucher", "early ad"
    )) or bool(re.search(r"\bad\b", msg_lower)) or (
        any(k in msg_lower for k in ("apply online", "how to apply", "application form", "apply now", "register online", "online application"))
        and not any(k in msg_lower for k in ("transport", "bus", "hostel", "admission fee", "one-time", "enrollment fee", "other fee"))
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
    ) and not is_admission_fee_query and not is_other_fee_query


    is_fee_with_hostel_query = any(k in msg_lower for k in (
        "with hostel", "including hostel", "plus hostel", "hostel and tuition",
        "tuition and hostel", "both tuition and hostel", "and hostel fee", "add hostel",
        "hostel fee included", "fee along with hostel", "along with hostel"
    )) or (
        any(k in msg_lower for k in ("hostel", "mess", "boarding")) and
        any(k in msg_lower for k in ("tuition", "cse fee", "btech fee", "b.tech fee", "total fee", "per sem"))
    )

    # The all-branch B.Tech table only when the student asks to see or compare every branch; a question
    # about one programme (or "fee details" with no programme) never gets another programme's figures.
    is_btech_fee_query = any(k in msg_lower for k in ("btech", "b.tech", "b tech", "engineering")) and any(
        k in msg_lower for k in ("fee", "fees", "tuition", "cost")) and any(
        k in msg_lower for k in ("all branches", "all b.tech", "all btech", "every branch", "branch wise",
                                 "branch-wise", "compare", "comparison", "each branch", "all the branches"))

    if is_other_fee_query:
        if _can_show("fee_breakdown"):
            cards.append(OTHER_FEES_CARD)
            _mark_shown("fee_breakdown")
    elif is_transport_fee_query:
        if _can_show("fee_breakdown"):
            cards.append(TRANSPORT_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_fee_with_hostel_query:
        # User explicitly asked to include hostel in the fee breakdown
        if _can_show("fee_breakdown"):
            cards.append(BTECH_CSE_WITH_HOSTEL_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_hostel_fee_query and not (is_cse_fee_query or is_btech_fee_query):
        # User asked purely for hostel fees
        if _can_show("fee_breakdown"):
            cards.append(HOSTEL_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_hostel_facilities_query and not (is_cse_fee_query or is_btech_fee_query):
        # User asked for hostel facilities / living details
        if _can_show("hostel_facilities"):
            cards.append(HOSTEL_FACILITIES_CARD)
            _mark_shown("hostel_facilities")
    elif is_exam_fee_query:
        if _can_show("fee_breakdown"):
            cards.append(EXAM_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_admission_fee_query:
        if _can_show("fee_breakdown"):
            cards.append(ADMISSION_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_scholarship_only_query:
        if _can_show("fee_breakdown"):
            cards.append(MERIT_SCHOLARSHIP_CARD)
            _mark_shown("fee_breakdown")
    elif is_cse_fee_query:
        # User asked for CSE fee WITHOUT hostel (hostel not added)
        if _can_show("fee_breakdown"):
            cards.append(BTECH_CSE_SEMESTER_FEE_CARD)
            _mark_shown("fee_breakdown")
    elif is_btech_fee_query:
        if _can_show("fee_breakdown"):
            cards.append(BTECH_ACADEMIC_FEE_CARD)
            _mark_shown("fee_breakdown")
    # (No fallback card for other fee wording: "fee details" alone is answered by asking which programme.)


    # 2. Sponsored Early Bird Application Ad Card (media_1794676975023.png reference)
    # Shown at most once per session when student is interested in joining SRU
    from app.config import settings as _settings
    if _settings.SHOW_EARLY_BIRD_OFFER and (is_join_interest_query or is_ad_query or (is_cse_fee_query and any(k in msg_lower for k in ("join", "admission", "apply", "want", "breakdown")))) and not is_admission_fee_query:
        if _can_show("application_ad") and APPLICATION_AD_CARD not in cards:
            cards.append(APPLICATION_AD_CARD)
            _mark_shown("application_ad")

    # 2b. Curriculum card (Shown at most once per session)
    if any(k in msg_lower for k in ("curriculum", "syllabus", "subjects", "course structure", "credits")) and (
        "cse" in msg_lower or "computer science" in msg_lower or "engineering" in msg_lower
    ):
        if _can_show("curriculum"):
            cards.append(CURRICULUM_CARD)
            _mark_shown("curriculum")

    # 3. Academic Programs & Courses Offered card (Shown at most once per session)
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
        if _can_show("programs_offered"):
            cards.append(PROGRAMS_OFFERED_CARD)
            _mark_shown("programs_offered")

    # 4. Placement Highlights card ("Three Consecutive Years of Excellence") - Shown at most once per session
    if any(k in msg_lower for k in ("placement", "placements", "highest package", "average package", "recruiters", "job offers", "internship", "internships", "superstar", "highest offer", "salary", "ctc", "highest ctc", "jobs", "career", "companies visiting", "recruitment")):
        if _can_show("placement_highlights"):
            cards.append(PLACEMENT_EXCELLENCE_CARD)
            _mark_shown("placement_highlights")

    # 4b. Campus visit: whom to contact (no booking form; visits are arranged by the admissions team)
    _visit_booking_triggers = (
        "book campus tour", "schedule campus visit", "how can i book a campus tour",
        "book a campus tour", "schedule visit", "book a visit", "book a tour",
        "schedule a tour", "schedule tour", "tour booking", "campus visit booking",
        "how to book a visit", "i want to book a visit", "i want to schedule a visit",
        "register for campus visit", "reserve a slot", "book my visit",
    )
    is_visit_booking_query = any(k in msg_lower for k in _visit_booking_triggers) and not any(k in msg_lower for k in ("fee", "fees", "cost", "vs", "compare"))
    if is_visit_booking_query:
        if _can_show("campus_visit_contact"):
            cards.append(CAMPUS_VISIT_CONTACT_CARD)
            _mark_shown("campus_visit_contact")

    # 5. Campus tour card (render static spot highlights if asking for about sru, campus walkthrough/tour, or facilities)
    is_video_query = (
        is_explicit_video_query(user_message)
        and is_video_topic_query(user_message)
    )
    if not is_video_query and not is_visit_booking_query and any(k in msg_lower for k in ("campus tour", "campus walkthrough", "see the campus", "visit the campus", "campus facilities", "about sru", "tell me about sru", "about sr university", "why sru", "why choose sru", "campus life", "overview of sru", "tell me about the university", "what is sru", "what is sr university", "describe sru")):
        if not any(k in msg_lower for k in ("fee", "cost", "vs")):
            if _can_show("campus_tour"):
                cards.append(CAMPUS_TOUR_CARD)
                _mark_shown("campus_tour")

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
    elif keyword_videos:
        # No embedding (the agent does not spend an AI call on videos): match on the videos' own
        # titles, categories and keywords instead.
        is_explicit_req = is_video_query or is_explicit_video_query(user_message)
        if is_explicit_req or is_video_confirmed or should_display_videos(user_message):
            from app.services.video_service import get_keyword_videos, is_about_sru_or_campus_query
            relevant_videos = get_keyword_videos(
                user_message, limit=2, prefer_campus=is_about_sru_or_campus_query(user_message))
            if not relevant_videos and is_explicit_req:
                relevant_videos = get_keyword_videos("campus tour", limit=2)
            if relevant_videos:
                cards.append(create_video_card(relevant_videos, is_explicit=is_explicit_req))

    return cards


def _TUITION(key: str) -> int:
    """Annual tuition from the fee policy (never typed here)."""
    return int(_fees().load_data()["programs"][key]["tuition_per_year"])


_ALL_FORM_PROGRAMS = [
    # Undergraduate Programmes (UG)
    {"key": "btech_cse", "name": "B.Tech Computer Science & Engineering (CSE)", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_cse")},
    {"key": "btech_ai_robotics", "name": "B.Tech in Artificial Intelligence & Robotics", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_ai_robotics")},
    {"key": "btech_ece", "name": "B.Tech Electronics & Communication (ECE)", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_ece")},
    {"key": "btech_mech", "name": "B.Tech Mechanical Engineering", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_mech")},
    {"key": "btech_civil", "name": "B.Tech Civil Engineering", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_civil")},
    {"key": "btech_eee", "name": "B.Tech Electrical & Electronics (EEE)", "degree": "B.Tech", "level": "ug", "annual_tuition": _TUITION("btech_eee")},
    {"key": "bsc_agri", "name": "B.Sc (Hons.) Agriculture (ICAR Accredited)", "degree": "B.Sc", "level": "ug", "annual_tuition": _TUITION("bsc_agri")},
    {"key": "bba", "name": "BBA (Bachelor of Business Administration)", "degree": "BBA", "level": "ug", "annual_tuition": _TUITION("bba")},
    {"key": "bca", "name": "BCA (Bachelor of Computer Applications)", "degree": "BCA", "level": "ug", "annual_tuition": _TUITION("bca")},
    {"key": "bdes", "name": "B.Des (School of Design)", "degree": "B.Des", "level": "ug", "annual_tuition": _TUITION("bdes")},
    {"key": "bcom", "name": "B.Com (Bachelor of Commerce)", "degree": "B.Com", "level": "ug", "annual_tuition": _TUITION("bcom")},

    # Postgraduate Programmes (PG)
    {"key": "mba", "name": "MBA (Finance, Operations, HR, Business Analytics, Marketing)", "degree": "MBA", "level": "pg", "annual_tuition": _TUITION("mba")},
    {"key": "mba_agri", "name": "MBA in Agri-Business Management", "degree": "MBA", "level": "pg", "annual_tuition": _TUITION("mba_agri")},
    {"key": "mca", "name": "MCA (Master of Computer Applications)", "degree": "MCA", "level": "pg", "annual_tuition": _TUITION("mca")},
    {"key": "mtech", "name": "M.Tech CSE", "degree": "M.Tech", "level": "pg", "annual_tuition": _TUITION("mtech")},
    {"key": "msc", "name": "M.Sc Sciences & Agriculture", "degree": "M.Sc", "level": "pg", "annual_tuition": _TUITION("msc")},
]


def build_fee_scholarship_form_card(
    selected_program: str | None = None,
    selected_board: str | None = None,
    level: str | None = None,
    only_selected: bool = False,
) -> dict:
    """Constructs an interactive in-chat Fee & Scholarship Assessment Form card.

    Strictly scopes programs according to what the user selected or asked for:
    - If user selected/asked for a UG course: displays ONLY UG courses (or only the selected course).
    - If user selected/asked for a PG course: displays ONLY PG courses.
    - If only_selected is True: restricts the card strictly to what the user selected.
    """
    # Detect level from selected_program if not explicitly given
    if selected_program and not level:
        pg_keys = {"mba", "mba_agri", "mca", "mtech", "msc"}
        level = "pg" if (selected_program in pg_keys or selected_program.startswith("m")) else "ug"

    # Filter programs
    if only_selected and selected_program:
        filtered_progs = [p for p in _ALL_FORM_PROGRAMS if p["key"] == selected_program]
        if not filtered_progs:
            filtered_progs = [p for p in _ALL_FORM_PROGRAMS if p["level"] == (level or "ug")]
    elif level:
        filtered_progs = [p for p in _ALL_FORM_PROGRAMS if p["level"] == level]
    else:
        filtered_progs = list(_ALL_FORM_PROGRAMS)

    # Ensure selected program is in the filtered list
    active_prog = selected_program if (selected_program and any(p["key"] == selected_program for p in filtered_progs)) else (selected_program or None)

    return {
        "type": "fee_scholarship_form",
        "title": "Fee & Merit Scholarship Assessment Form",
        "subtitle": "Select your course and 10+2 board, then enter your marks or rank to calculate your exact net fee." if level != "pg" else "Select your postgraduate programme and enter your qualifying degree marks to calculate your fee & scholarship.",
        "level": level or "ug",
        "only_selected": only_selected,
        "selected_program": active_prog,
        "selected_board": selected_board or "ts_state_board",
        "programs": filtered_progs,
        "boards": [
            {"key": "ts_state_board", "label": "Telangana State Board (BIE TS)", "slab_key": "state_board"},
            {"key": "ap_state_board", "label": "Andhra Pradesh State Board (BIE AP)", "slab_key": "state_board"},
            {"key": "cbse", "label": "CBSE (Central Board)", "slab_key": "cbse"},
            {"key": "icse", "label": "ICSE / ISC (CISCE)", "slab_key": "cbse"},
            {"key": "other_state_board", "label": "Other State Boards (All Over India)", "slab_key": "state_board"},
            {"key": "nios", "label": "NIOS / National Open School", "slab_key": "cbse"},
            {"key": "ib", "label": "International Baccalaureate (IB)", "slab_key": "ib"},
        ] if level != "pg" else [
            {"key": "degree_university", "label": "Recognised University / College", "slab_key": "pg"},
        ],
    }


def build_counsellor_board_card(selected_board: str | None = None) -> dict:
    """Builds interactive board selection card for guided scholarship counselling."""
    return {
        "type": "counsellor_board_selection",
        "title": "Where did you complete your schooling / Intermediate education?",
        "subtitle": "Select the board under which you studied so I can use the appropriate academic assessment criteria.",
        "selected_board": selected_board,
        "options": [
            {"key": "ts_state_board", "label": "Telangana Intermediate (TSBIE)", "short": "TSBIE", "code": "TSBIE"},
            {"key": "ap_state_board", "label": "Andhra Pradesh Intermediate (BIEAP)", "short": "BIEAP", "code": "BIEAP"},
            {"key": "cbse", "label": "CBSE", "short": "CBSE", "code": "CBSE"},
            {"key": "icse", "label": "ISC / ICSE", "short": "ISC", "code": "ISC"},
            {"key": "other_state_board", "label": "Other State Board", "short": "Other State Board", "code": "Other"},
            {"key": "ib", "label": "International Baccalaureate (IB)", "short": "IB", "code": "IB"},
        ],
    }


_FORM_STAGE_OPTIONS = [
    {"key": "1st_year", "label": "Studying Intermediate 1st Year (Class 11)"},
    {"key": "2nd_year", "label": "Studying Intermediate 2nd Year (Class 12)"},
    {"key": "completed", "label": "Completed Intermediate / Class 12 (passed out)"},
]
_FORM_STREAM_OPTIONS = [
    {"key": "MPC", "label": "MPC (Maths, Physics, Chemistry)"},
    {"key": "BiPC", "label": "BiPC (Biology, Physics, Chemistry)"},
    {"key": "MEC", "label": "MEC / CEC / Other"},
]
_FORM_ENTRANCE_OPTIONS = [
    {"key": "none", "label": "No entrance score / not yet"},
    {"key": "tg_eapcet", "label": "TG EAPCET rank"},
    {"key": "ap_eapcet", "label": "AP EAPCET rank"},
    {"key": "jee_main", "label": "JEE Main percentile"},
]


def build_academic_details_form(
    mode: str,
    program_key: str | None,
    program_name: str | None,
    values: dict | None = None,
    show_stream: bool = False,
    show_entrance: bool = False,
    saved_summary: str | None = None,
) -> dict:
    """ONE form for the academic details an admission journey needs: board -> current status -> marks
    (+ 10+2 group when the programme names one, + an optional entrance score for B.Tech / B.Sc Agriculture).
    Values already known in this conversation are pre-filled. Submitting sends the details as structured data
    (``form`` on /api/v1/agent/stream), which the agent validates and evaluates (eligibility or scholarship)."""
    from app.sru_agent.fee_intake import get_max_marks

    values = dict(values or {})
    boards = build_counsellor_board_card()["options"]
    max_table = {b["key"]: {s["key"]: get_max_marks(b["key"], s["key"]) for s in _FORM_STAGE_OPTIONS} for b in boards}
    return {
        "type": "academic_details_form",
        "mode": "scholarship" if mode == "scholarship" else "eligibility",
        "program": program_key,
        "program_name": program_name,
        "title": "Your academic details",
        "subtitle": (f"For {program_name}. " if program_name else "") + "Already shared details are filled in; complete the rest and submit.",
        "boards": [{"key": b["key"], "label": b["label"]} for b in boards],
        "stages": _FORM_STAGE_OPTIONS,
        "max_marks_table": max_table,
        "show_stream": bool(show_stream),
        "streams": _FORM_STREAM_OPTIONS,
        "show_entrance": bool(show_entrance),
        "entrances": _FORM_ENTRANCE_OPTIONS,
        "values": {
            "board_key": values.get("board_key"),
            "academic_stage": values.get("academic_stage"),
            "raw_marks": values.get("raw_marks"),
            "max_marks": values.get("max_marks"),
            "percent": values.get("percent"),
            "stream": values.get("stream"),
            "entrance_type": ("tg_eapcet" if values.get("eapcet_rank") and values.get("admission_route") != "ap_eapcet"
                              else "ap_eapcet" if values.get("eapcet_rank") else
                              "jee_main" if values.get("jee_percentile") else None),
            "entrance_value": values.get("eapcet_rank") or values.get("jee_percentile"),
        },
        "saved_summary": saved_summary,
        "submit_label": "Calculate my scholarship" if mode == "scholarship" else "Check my eligibility",
    }


def build_counsellor_stage_card(board_label: str | None = None, selected_stage: str | None = None) -> dict:
    """Builds interactive academic stage card for guided scholarship counselling."""
    return {
        "type": "counsellor_stage_selection",
        "title": "Which year are you currently studying in?",
        "subtitle": f"Select your academic stage{' under ' + board_label if board_label else ''} so I can ask for the correct marks.",
        "board_label": board_label,
        "selected_stage": selected_stage,
        "options": [
            {
                "key": "1st_year",
                "label": "Intermediate 1st Year (11th)",
                "desc": "Currently in 1st year / completed 1st year exams",
            },
            {
                "key": "2nd_year",
                "label": "Intermediate 2nd Year (12th)",
                "desc": "Currently in 2nd year; preliminary assessment on completed 1st year marks",
            },
            {
                "key": "completed",
                "label": "Completed Intermediate (Passed out)",
                "desc": "Completed 10+2 / Intermediate with final examination score",
            },
        ],
    }


def build_counsellor_marks_card(
    board_key: str | None = None,
    stage_key: str | None = None,
    max_marks: int = 1000,
    board_label: str | None = None,
    default_val: float | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    step_label: str = "Step 3: Academic Marks",
) -> dict:
    """Builds interactive marks input card with inline validation and continue button."""
    is_ib = board_key == "ib" or max_marks == 45
    unit = "/ 45" if is_ib else ("%" if max_marks <= 100 else f"/ {max_marks}")
    stage_name = "Intermediate 1st Year" if stage_key in ("1st_year", "2nd_year") else "Intermediate"
    default_title = (
        "What is your IB Diploma score (out of 45)?" if is_ib else f"What marks have you scored in {stage_name}?"
    )
    default_subtitle = (
        f"Enter your IB Diploma points out of 45 under {board_label or 'International Baccalaureate (IB)'}."
        if is_ib
        else (
            f"Enter your marks scored out of {max_marks} under {board_label or 'your board'}."
            if max_marks > 100
            else f"Enter your percentage scored under {board_label or 'your board'}."
        )
    )
    return {
        "type": "counsellor_marks_input",
        "step_label": step_label,
        "title": title or default_title,
        "subtitle": subtitle or default_subtitle,
        "board_key": board_key or "ts_state_board",
        "stage_key": stage_key or "completed",
        "max_marks": max_marks,
        "board_label": board_label,
        "unit": unit,
        "placeholder": "e.g. 38" if is_ib else (f"e.g. {int(max_marks * 0.88)}" if max_marks > 100 else "e.g. 88%"),
        "default_val": default_val,
    }


def build_counsellor_route_card(selected_route: str | None = None, program_title: str = "B.Tech",
                                step_label: str = "Step 5: Admission Route") -> dict:
    """Builds interactive admission route card for guided scholarship counselling."""
    return {
        "type": "counsellor_route_selection",
        "step_label": step_label,
        "title": f"Which admission route are you planning to use for {program_title}?",
        "subtitle": "Select your admission pathway so we can factor in any entrance rank scholarships.",
        "selected_route": selected_route,
        "options": [
            {"key": "tg_eapcet", "label": "TG EAPCET", "desc": "Telangana State Engineering Entrance (Ranks 1 to 20,000)"},
            {"key": "ap_eapcet", "label": "AP EAPCET", "desc": "Andhra Pradesh State Engineering Entrance (Ranks 1 to 20,000)"},
            {"key": "jee_main", "label": "JEE Main", "desc": "NTA JEE Main (50 to 95+ Percentile)"},
            {"key": "srsat", "label": "SR University SRSAT", "desc": "SR University Scholastic Aptitude Test"},
            {"key": "other", "label": "Other", "desc": "Other state or national entrance exam"},
            {"key": "not_decided", "label": "Not decided yet", "desc": "Assess based on 10+2 Intermediate marks alone"},
        ],
    }


def build_counsellor_program_card(selected_program: str | None = None, step_label: str = "Step 1: Preferred Programme") -> dict:
    """Builds interactive programme selection card across disciplines."""
    return {
        "type": "counsellor_program_selection",
        "title": "Which course are you considering?",
        "subtitle": "Choose a programme or degree to view your exact fee and scholarship breakdown.",
        "step_label": step_label,
        "selected_program": selected_program or None,
        "programs": [
            {"key": "btech_cse", "name": "B.Tech Computer Science & Engineering (CSE)", "short": "B.Tech CSE", "annual_tuition": _fees().inr(_TUITION("btech_cse"))},
            {"key": "btech_ai_robotics", "name": "B.Tech in Artificial Intelligence & Robotics", "short": "AI & Robotics", "annual_tuition": _fees().inr(_TUITION("btech_ai_robotics"))},
            {"key": "btech_ece", "name": "B.Tech ECE (AIML, VLSI, Robotics)", "short": "B.Tech ECE", "annual_tuition": _fees().inr(_TUITION("btech_ece"))},
            {"key": "btech_mech", "name": "B.Tech Mechanical / Civil / EEE", "short": "Core Engineering", "annual_tuition": _fees().inr(_TUITION("btech_mech"))},
            {"key": "mba", "name": "Master of Business Administration (MBA)", "short": "MBA", "annual_tuition": _fees().inr(_TUITION("mba"))},
            {"key": "bba", "name": "Bachelor of Business Administration (BBA)", "short": "BBA", "annual_tuition": _fees().inr(_TUITION("bba"))},
            {"key": "bsc_agri", "name": "B.Sc (Hons.) Agriculture (ICAR Accredited)", "short": "B.Sc Agriculture", "annual_tuition": _fees().inr(_TUITION("bsc_agri"))},
        ],
    }

