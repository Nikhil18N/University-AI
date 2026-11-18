"""Intelligent Course Selection & Fee Enquiry Flow for SRU Buddy.

Implements a structured multi-step conversational state machine:
  Fee Enquiry -> School Selection -> Programme Selection -> Specialization (if applicable) -> Detailed Fee Structure.
All figures are grounded in fees_2027_28.json and the verified admissions handbook.
"""
import re
from typing import Any

from . import config, fees

FEE_PORTAL_URL = config.FEE_PORTAL_URL
DEFAULT_ACADEMIC_YEAR = config.ADMISSION_YEAR  # "2027-28"

# -----------------------------------------------------------------------------
# 1. Official SR University Schools Directory & Verified Program Mappings
# -----------------------------------------------------------------------------

SCHOOLS_DATA = [
    {
        "id": "school_cs_ai",
        "key": "cs_ai",
        "number": 1,
        "name": "School of Computer Science & Artificial Intelligence",
        "display_name": "School of Computer Science & Artificial Intelligence (CSE)",
        "short_name": "CS & AI (CSE)",
        "icon": "💻",
        "highlight": "Cutting-edge curriculum in AI, Quantum Computing & Advanced Cyber Systems",
        "keywords": ["cse", "computer science", "cs & ai", "cs and ai", "artificial intelligence", "ai", "aiml", "cyber", "data science"],
        "programs": {
            "ug": [
                {
                    "key": "btech_cse",
                    "name": "B.Tech Computer Science & Engineering (CSE)",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 340000,
                    "has_specializations": True,
                    "specializations": [
                        "Artificial Intelligence & Machine Learning (AIML)",
                        "Data Science",
                        "Cyber Security",
                        "Robotics and Automation",
                        "Quantum AI",
                        "Core CSE",
                    ],
                },
                {
                    "key": "btech_ai_robotics",
                    "name": "B.Tech in Artificial Intelligence & Robotics",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 400000,
                    "has_specializations": False,
                },
                {
                    "key": "bca",
                    "name": "BCA (Bachelor of Computer Applications)",
                    "degree": "BCA",
                    "duration_years": 3,
                    "tuition_per_year": 150000,
                    "has_specializations": False,
                },
                {
                    "key": "bsc_cs",
                    "name": "B.Sc Computer Science (Hons.)",
                    "degree": "B.Sc",
                    "duration_years": 3,
                    "tuition_per_year": 150000,
                    "has_specializations": False,
                },
                {
                    "key": "bsc_maths_ai",
                    "name": "B.Sc (Hons.) in Mathematics & AI",
                    "degree": "B.Sc",
                    "duration_years": 3,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
            ],
            "pg": [
                {
                    "key": "mtech",
                    "name": "M.Tech CSE (AIML, Data Science, Cyber Security)",
                    "degree": "M.Tech",
                    "duration_years": 2,
                    "tuition_per_year": 100000,
                    "has_specializations": True,
                },
                {
                    "key": "mca",
                    "name": "MCA (Master of Computer Applications)",
                    "degree": "MCA",
                    "duration_years": 2,
                    "tuition_per_year": 150000,
                    "has_specializations": False,
                },
                {
                    "key": "msc",
                    "name": "M.Sc Computer Science",
                    "degree": "M.Sc",
                    "duration_years": 2,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
            ],
        },
    },
    {
        "id": "school_engineering",
        "key": "engineering",
        "number": 2,
        "name": "School of Engineering",
        "display_name": "School of Engineering",
        "short_name": "School of Engineering",
        "icon": "⚙️",
        "highlight": "Tier-1 NBA Accredited B.Tech Programs with Smart Robotics & EV Labs",
        "keywords": ["engineering", "ece", "eee", "mech", "mechanical", "civil", "electronics", "electrical", "iep"],
        "programs": {
            "ug": [
                {
                    "key": "btech_ece",
                    "name": "B.Tech Electronics & Communication Engineering (ECE)",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 270000,
                    "has_specializations": True,
                    "specializations": ["AIML", "VLSI System Design", "Robotics and Automation"],
                },
                {
                    "key": "btech_eee",
                    "name": "B.Tech Electrical & Electronics Engineering (EEE)",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": True,
                    "specializations": ["Electric Vehicles (EV)", "Renewable Energy"],
                },
                {
                    "key": "btech_mech",
                    "name": "B.Tech Mechanical Engineering",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": True,
                    "specializations": ["Robotics and Automation", "Smart Manufacturing"],
                },
                {
                    "key": "btech_civil",
                    "name": "B.Tech Civil Engineering",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
                {
                    "key": "btech_iep",
                    "name": "B.Tech International Engineering Programme (IEP)",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 340000,
                    "has_specializations": False,
                },
            ],
            "pg": [
                {
                    "key": "mtech",
                    "name": "M.Tech Engineering (VLSI, Embedded Systems, EDT, AMS, Thermal, CTM)",
                    "degree": "M.Tech",
                    "duration_years": 2,
                    "tuition_per_year": 100000,
                    "has_specializations": True,
                },
            ],
        },
    },
    {
        "id": "school_agriculture",
        "key": "agriculture",
        "number": 3,
        "name": "School of Agriculture",
        "display_name": "School of Agriculture",
        "short_name": "School of Agriculture",
        "icon": "🌾",
        "highlight": "ICAR-Accredited — 1st Private University in Telugu States to earn ICAR accreditation",
        "keywords": ["agriculture", "agri", "icar", "bsc agri", "farming", "food tech", "food technology"],
        "programs": {
            "ug": [
                {
                    "key": "bsc_agri",
                    "name": "B.Sc. (Hons.) Agriculture (ICAR-Accredited)",
                    "degree": "B.Sc",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
                {
                    "key": "btech_food_tech",
                    "name": "B.Tech Food Technology",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
            ],
            "pg": [
                {
                    "key": "msc",
                    "name": "M.Sc. Agriculture (Agronomy, Genetics, Horticulture, Pathology, Soil Science)",
                    "degree": "M.Sc",
                    "duration_years": 2,
                    "tuition_per_year": 100000,
                    "has_specializations": True,
                },
            ],
        },
    },
    {
        "id": "school_business",
        "key": "business",
        "number": 4,
        "name": "Astra School of Business",
        "display_name": "Astra School of Business",
        "short_name": "Astra School of Business",
        "icon": "📊",
        "highlight": "Modern Case-Study & Business Analytics Pedagogy with Global Networking",
        "keywords": ["business", "astra", "management", "bba", "mba", "bcom", "commerce", "hospitality"],
        "programs": {
            "ug": [
                {
                    "key": "bba",
                    "name": "BBA (Bachelor of Business Administration)",
                    "degree": "BBA",
                    "duration_years": 3,
                    "tuition_per_year": 150000,
                    "has_specializations": False,
                },
                {
                    "key": "bba_specialised",
                    "name": "BBA Specialised (Finance, Operations, HR, Business Analytics, Marketing)",
                    "degree": "BBA",
                    "duration_years": 3,
                    "tuition_per_year": 200000,
                    "has_specializations": True,
                    "specializations": ["Finance", "Business Analytics", "Marketing", "HR", "Operations"],
                },
                {
                    "key": "bcom",
                    "name": "B.Com. (Bachelor of Commerce)",
                    "degree": "B.Com",
                    "duration_years": 3,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
                {
                    "key": "bsc_hospitality",
                    "name": "B.Sc in Hospitality and Event Management",
                    "degree": "B.Sc",
                    "duration_years": 3,
                    "tuition_per_year": 150000,
                    "has_specializations": False,
                },
            ],
            "pg": [
                {
                    "key": "mba",
                    "name": "MBA (Finance, Operations, HR, Business Analytics, Marketing)",
                    "degree": "MBA",
                    "duration_years": 2,
                    "tuition_per_year": 300000,
                    "has_specializations": True,
                    "specializations": ["Finance", "Business Analytics", "Marketing", "HR", "Operations"],
                },
                {
                    "key": "mba_agri",
                    "name": "MBA in Agri-Business Management",
                    "degree": "MBA",
                    "duration_years": 2,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
            ],
        },
    },
    {
        "id": "school_sciences_humanities",
        "key": "sciences",
        "number": 5,
        "name": "School of Sciences & Humanities",
        "display_name": "School of Sciences & Humanities",
        "short_name": "School of Sciences & Humanities",
        "icon": "🔬",
        "highlight": "Interdisciplinary Research in AI, Biotechnology & Space Engineering",
        "keywords": ["sciences", "humanities", "biotech", "physics", "chemistry", "biology", "maths"],
        "programs": {
            "ug": [
                {
                    "key": "btech_biotech",
                    "name": "B.Tech Biotechnology with AI",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
                {
                    "key": "btech_engg_physics",
                    "name": "B.Tech Engineering Physics in AI, Robotics & Space",
                    "degree": "B.Tech",
                    "duration_years": 4,
                    "tuition_per_year": 200000,
                    "has_specializations": False,
                },
                {
                    "key": "bsc_physics",
                    "name": "B.Sc Physics",
                    "degree": "B.Sc",
                    "duration_years": 3,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
                {
                    "key": "bsc_chemistry",
                    "name": "B.Sc Chemistry",
                    "degree": "B.Sc",
                    "duration_years": 4,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
            ],
            "pg": [
                {
                    "key": "msc",
                    "name": "M.Sc Sciences & Mathematics",
                    "degree": "M.Sc",
                    "duration_years": 2,
                    "tuition_per_year": 100000,
                    "has_specializations": False,
                },
            ],
        },
    },
    {
        "id": "school_design",
        "key": "design",
        "number": 6,
        "name": "School of Design",
        "display_name": "School of Design",
        "short_name": "School of Design",
        "icon": "🎨",
        "highlight": "Studio-Based Creative & Digital Prototyping Pathways with Industry Mentors",
        "keywords": ["design", "bdes", "fashion", "interior", "fashion design", "interior design"],
        "programs": {
            "ug": [
                {
                    "key": "bdes",
                    "name": "B.Des (Design: Interior Design, Fashion Design)",
                    "degree": "B.Des",
                    "duration_years": 4,
                    "tuition_per_year": 210000,
                    "has_specializations": True,
                    "specializations": ["Interior Design", "Fashion Design"],
                },
            ],
            "pg": [],
        },
    },
]

# -----------------------------------------------------------------------------
# 2. Helpers for Intent & Entity Detection
# -----------------------------------------------------------------------------

_FEE_TRIGGER_WORDS = re.compile(
    r"\b(?:fee|fees|fess|feez|tuition|cost|costs|expense|expenses|hostel\s*fee|mess\s*fee|"
    r"bus\s*fee|transport\s*fee|admission\s*fee|fee\s*structure|total\s*cost|how\s*much\s*to\s*study|"
    r"tuition\s*and\s*accommodation|fee\s*for\s*cse|fees\s*for\s*agriculture)\b",
    re.IGNORECASE,
)

_BACK_NAVIGATION_WORDS = re.compile(
    r"\b(?:go\s*back|back|change\s*school|different\s*school|other\s*school|another\s*school|"
    r"change\s*course|different\s*programme|change\s*programme|previous\s*menu|restart\s*selection)\b",
    re.IGNORECASE,
)

_FEE_EXCLUSIONS = re.compile(
    r"\b(?:refund|refunds|cancellation\s*refund|cancel\s*my\s*admission|cancel\s*admission|admission\s*cancel|"
    r"calculate|calculation|how\s+to\s+pay|mode\s+of\s+payment|payment\s+mode|payment\s+method|due\s+date|last\s+date|deadline)\b",
    re.IGNORECASE,
)

_ACADEMIC_YEAR_REGEX = re.compile(r"\b(202\d[-–]\d{2,4})\b")


def extract_academic_year(message: str, fallback: str = DEFAULT_ACADEMIC_YEAR) -> str:
    m = _ACADEMIC_YEAR_REGEX.search(message or "")
    if m:
        raw = m.group(1).replace("–", "-")
        # Normalize 2027-2028 -> 2027-28
        parts = raw.split("-")
        if len(parts) == 2 and len(parts[1]) == 4:
            return f"{parts[0]}-{parts[1][-2:]}"
        return raw
    return fallback


def is_broad_fee_query(message: str) -> bool:
    """Matches broad fee queries that initiate the structured academic flow."""
    if _FEE_EXCLUSIONS.search(message or ""):
        return False
    return bool(_FEE_TRIGGER_WORDS.search(message or ""))


def detect_back_navigation(message: str) -> bool:
    return bool(_BACK_NAVIGATION_WORDS.search(message or ""))


def detect_school(message: str) -> dict | None:
    """Matches free text or number selection to one of the 6 schools."""
    low = (message or "").lower().strip()
    # Number matching: "1", "option 1", "school 1"
    num_match = re.search(r"\b(?:option\s*|school\s*)?([1-6])\b", low)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(SCHOOLS_DATA):
            return SCHOOLS_DATA[idx]

    # Keyword / Name matching
    for school in SCHOOLS_DATA:
        if school["name"].lower() in low or school["display_name"].lower() in low:
            return school
        if any(re.search(rf"\b{re.escape(kw)}\b", low) for kw in school["keywords"]):
            return school
    return None


def detect_program_under_school(message: str, school: dict | None) -> dict | None:
    """Matches message to a program under the given school or any school."""
    low = (message or "").lower().strip()
    schools_to_search = [school] if school else SCHOOLS_DATA

    for sch in schools_to_search:
        all_progs = sch["programs"].get("ug", []) + sch["programs"].get("pg", [])
        for prog in all_progs:
            # Check program name, degree, or key
            if prog["name"].lower() in low or prog["key"] in low:
                return prog
            # Check degree words (e.g. "btech cse", "bca", "mtech", "bdes")
            if re.search(rf"\b{re.escape(prog['degree'].lower())}\b", low):
                # If specific words match
                if "cse" in low and "cse" in prog["key"]:
                    return prog
                if "robotics" in low and "robotics" in prog["key"]:
                    return prog
                if "ece" in low and "ece" in prog["key"]:
                    return prog
                if "eee" in low and "eee" in prog["key"]:
                    return prog
                if "mech" in low and "mech" in prog["key"]:
                    return prog
                if "civil" in low and "civil" in prog["key"]:
                    return prog
                if "food" in low and "food" in prog["key"]:
                    return prog
                if "agri" in low and "agri" in prog["key"]:
                    return prog
                if "bba" in low and "bba" in prog["key"]:
                    return prog
                if "mba" in low and "mba" in prog["key"]:
                    return prog
                if "bdes" in low or "design" in low and "bdes" in prog["key"]:
                    return prog
                if "bca" in low and "bca" in prog["key"]:
                    return prog
                if "mca" in low and "mca" in prog["key"]:
                    return prog

    # Fallback to general find_program
    found_key = fees.find_program(message)
    if found_key:
        for sch in SCHOOLS_DATA:
            all_progs = sch["programs"].get("ug", []) + sch["programs"].get("pg", [])
            for prog in all_progs:
                if prog["key"] == found_key:
                    return prog
    return None


def detect_specialization(message: str, prog: dict) -> str | None:
    low = (message or "").lower()
    specs = prog.get("specializations", [])
    for spec in specs:
        spec_low = spec.lower()
        # Clean words from spec like (AIML) -> aiml
        words = re.findall(r"[a-z0-9]+", spec_low)
        if any(w in low for w in words if len(w) >= 3):
            return spec
    return None


# -----------------------------------------------------------------------------
# 3. Card Generators for Frontend
# -----------------------------------------------------------------------------

def build_school_selection_card() -> dict:
    return {
        "type": "school_selection",
        "title": "Select Academic School",
        "subtitle": "Choose your preferred school or academic area to explore programmes & fee structures",
        "schools": [
            {
                "id": s["id"],
                "number": s["number"],
                "name": s["display_name"],
                "short_name": s["short_name"],
                "icon": s["icon"],
                "highlight": s["highlight"],
            }
            for s in SCHOOLS_DATA
        ],
        "allow_custom": True,
    }


def build_course_selection_card(school: dict) -> dict:
    return {
        "type": "course_selection",
        "title": f"Programmes in {school['short_name']}",
        "subtitle": "Select your intended degree or programme",
        "school_id": school["id"],
        "school_name": school["display_name"],
        "icon": school["icon"],
        "programs_ug": school["programs"].get("ug", []),
        "programs_pg": school["programs"].get("pg", []),
    }


def build_detailed_fee_card(prog: dict, school: dict, year: str, spec: str | None = None) -> dict:
    tuition = prog.get("tuition_per_year", 0)
    sem_tuition = tuition // 2
    duration = prog.get("duration_years", 4)

    # Verified components from fees_2027_28.json
    fee_data = fees.load_data()
    one_time = fee_data.get("one_time", {})
    enrollment = one_time.get("enrollment_fee", 5000)
    application = one_time.get("application_fee", 1100)
    one_time_total = enrollment + application

    yearly_other = fee_data.get("yearly_other", {})
    other_fee = yearly_other.get("other_fee", 15000)
    exam_fee = yearly_other.get("exam_fee", 5000)
    annual_academic_other = other_fee + exam_fee

    transport_fee = fee_data.get("transport_per_year", 30000)

    hostel_per_year = fee_data.get("hostel_per_year", {})
    hostel_deposits = fee_data.get("hostel_deposits", {})

    spec_fee_y2 = 30000 if prog.get("has_specializations") and "btech_cse" in prog.get("key", "") else 0

    first_year_academic = tuition + one_time_total + annual_academic_other
    total_programme_tuition = tuition * duration

    return {
        "type": "fee_structure_detailed",
        "title": f"Fee Structure — {prog['name']}",
        "academic_year": year,
        "school_name": school["display_name"],
        "program_name": prog["name"],
        "specialization": spec,
        "degree": prog.get("degree", "Degree"),
        "duration_years": duration,
        "tuition": {
            "annual": tuition,
            "semester": sem_tuition,
            "formatted_annual": fees.inr(tuition),
            "formatted_semester": fees.inr(sem_tuition),
        },
        "one_time_charges": [
            {"label": "Enrolment Fee (One-Time)", "amount": enrollment, "formatted": fees.inr(enrollment)},
            {"label": "Application Processing Fee", "amount": application, "formatted": fees.inr(application)},
        ],
        "one_time_total": one_time_total,
        "formatted_one_time_total": fees.inr(one_time_total),
        "annual_academic_charges": [
            {"label": "Academic & Facility Other Fee", "amount": other_fee, "formatted": fees.inr(other_fee)},
            {"label": "Examination Fee", "amount": exam_fee, "formatted": fees.inr(exam_fee)},
        ],
        "annual_academic_other_total": annual_academic_other,
        "formatted_annual_other": fees.inr(annual_academic_other),
        "specialization_fee": spec_fee_y2,
        "first_year_academic_total": first_year_academic,
        "formatted_first_year_academic": fees.inr(first_year_academic),
        "total_programme_tuition": total_programme_tuition,
        "formatted_total_programme_tuition": fees.inr(total_programme_tuition),
        "transport_annual": transport_fee,
        "formatted_transport": fees.inr(transport_fee),
        "hostel_options": [
            {"type": "AC, 3-Sharing Room", "fee": hostel_per_year.get("ac_3", 135000), "formatted": fees.inr(hostel_per_year.get("ac_3", 135000))},
            {"type": "AC, 4-Sharing Room", "fee": hostel_per_year.get("ac_4", 125000), "formatted": fees.inr(hostel_per_year.get("ac_4", 125000))},
            {"type": "Non-AC, 3-Sharing Room", "fee": hostel_per_year.get("non_ac_3", 125000), "formatted": fees.inr(hostel_per_year.get("non_ac_3", 125000))},
            {"type": "Non-AC, 4-Sharing Room", "fee": hostel_per_year.get("non_ac_4", 115000), "formatted": fees.inr(hostel_per_year.get("non_ac_4", 115000))},
        ],
        "hostel_deposits": [
            {"label": "Refundable Caution Deposit", "amount": hostel_deposits.get("caution_deposit", 5000), "formatted": fees.inr(hostel_deposits.get("caution_deposit", 5000))},
            {"label": "Annual Laundry Fee", "amount": hostel_deposits.get("laundry_per_year", 5000), "formatted": fees.inr(hostel_deposits.get("laundry_per_year", 5000))},
            {"label": "AC Electricity Security Deposit", "amount": hostel_deposits.get("electricity_deposit_ac", 10000), "formatted": fees.inr(hostel_deposits.get("electricity_deposit_ac", 10000))},
            {"label": "Non-AC Electricity Security Deposit", "amount": hostel_deposits.get("electricity_deposit_non_ac", 5000), "formatted": fees.inr(hostel_deposits.get("electricity_deposit_non_ac", 5000))},
        ],
        "dining_info": "Nutritious multi-cuisine mess dining included in residential fee, served in SRU's 4,000-seat central dining facility.",
        "verified": True,
        "source": "SR University Official Admissions & Fee Structure 2027-28",
    }


# -----------------------------------------------------------------------------
# 4. State Machine Execution & Transition Engine
# -----------------------------------------------------------------------------

def process_fee_flow(
    message: str,
    session_id: str,
    profile: dict,
    conv_state: dict,
) -> dict | None:
    """Executes the fee enquiry state machine.

    Returns dict with keys:
      - text: str
      - cards: list[dict]
      - suggestions: list[str]
      - new_state: dict
    or None if this message is not part of the fee flow.
    """
    msg = message.strip()
    low = msg.lower()
    current_state = conv_state.get("fee_flow_state")
    saved_school_id = conv_state.get("fee_flow_school")
    saved_prog_key = conv_state.get("fee_flow_prog")
    saved_year = conv_state.get("fee_flow_year") or extract_academic_year(msg, DEFAULT_ACADEMIC_YEAR)
    is_fee_query = is_broad_fee_query(msg)
    user_name = profile.get("name")
    name_prefix = f"{user_name}, " if user_name else ""

    # Check for back navigation
    if detect_back_navigation(msg) and current_state:
        # Step back to school selection
        return {
            "text": f"No problem{', ' + user_name if user_name else ''}! Let's select your preferred school or academic area:",
            "cards": [build_school_selection_card()],
            "suggestions": [s["display_name"] for s in SCHOOLS_DATA],
            "new_state": {
                "fee_flow_state": "awaiting_school_selection",
                "fee_flow_school": None,
                "fee_flow_prog": None,
                "fee_flow_year": saved_year,
            },
        }

    # -------------------------------------------------------------------------
    # Initial Trigger: Not in flow yet
    # -------------------------------------------------------------------------
    if not current_state:
        # If user provides personal entrance/board scores (e.g. 85%, EAPCET rank),
        # pass through to the dedicated scholarship calculation tools/model.
        has_scores = bool(
            re.search(r"(?<![\d.])(\d{2}(?:\.\d+)?)\s*(?:%|percent|percentage)", low)
            or re.search(r"\b(?:eapcet|eamcet|jee|rank|percentile)\s*[\d,]+", low)
            or re.search(r"\b\d{1,6}\s*(?:rank|percentile)\b", low)
            or "inter (" in low
            or "no entrance" in low
        )
        if has_scores:
            return None

        if not is_fee_query and not any(kw in low for kw in ("school of", "astra school")):
            return None

        # Check if user mentioned an unverified year (e.g. 2028-29, 2030)
        mentioned_year = extract_academic_year(msg, "")
        year_unverified_notice = ""
        if mentioned_year and mentioned_year not in ("2027-28", "2026-27"):
            year_unverified_notice = (
                f"Note: The official fee structure for Academic Year **{mentioned_year}** has not yet been finalized "
                f"by the university. I am displaying the latest verified fee structure for **{DEFAULT_ACADEMIC_YEAR}**.\n\n"
            )
            saved_year = DEFAULT_ACADEMIC_YEAR
        elif mentioned_year:
            saved_year = mentioned_year

        # Check if user ALREADY specified a School directly (e.g. "fees for Agriculture", "Astra School of Business")
        matched_school = detect_school(msg)
        has_specific_prog_word = bool(re.search(
            r"\b(?:b\.?\s?tech|m\.?\s?tech|b\.?\s?sc|m\.?\s?sc|bba|mba|bca|mca|b\.?\s?com|b\.?\s?des|"
            r"cse|ece|eee|mech|civil|food\s*tech|biotech|physics|chemistry|design)\b",
            low,
        ))
        matched_prog = detect_program_under_school(msg, matched_school) if (has_specific_prog_word or not matched_school) else None

        if matched_prog:
            # User named a specific program (e.g. "B.Tech CSE fee for 2027-28" or "hostel fee for B.Tech")
            # Find the school of this program
            sch = matched_school
            if not sch:
                for s in SCHOOLS_DATA:
                    all_p = s["programs"].get("ug", []) + s["programs"].get("pg", [])
                    if any(p["key"] == matched_prog["key"] for p in all_p):
                        sch = s
                        break
            sch = sch or SCHOOLS_DATA[0]
            spec = detect_specialization(msg, matched_prog)
            fee_card = build_detailed_fee_card(matched_prog, sch, saved_year, spec)

            tuition_fmt = fee_card["tuition"]["formatted_annual"]
            sem_fmt = fee_card["tuition"]["formatted_semester"]
            one_time_fmt = fee_card["formatted_one_time_total"]
            annual_other_fmt = fee_card["formatted_annual_other"]

            reply_text = (
                f"{year_unverified_notice}Sure {name_prefix}! Here is the complete verified fee breakdown for "
                f"**{matched_prog['name']}** ({sch['short_name']}) for Academic Year **{saved_year}**:\n\n"
                f"• **Tuition Fee**: {tuition_fmt} per year ({sem_fmt} per semester)\n"
                f"• **One-Time Charges**: {one_time_fmt} (Enrolment ₹5,000 + Application ₹1,100)\n"
                f"• **Annual Academic Charges**: {annual_other_fmt} (Other fee ₹15,000 + Exam fee ₹5,000)\n"
                f"• **Hostel Accommodation**: ₹1,15,000 – ₹1,35,000/year (Includes multi-cuisine dining in 4,000-seat central dining; AC & Non-AC 3/4 sharing options available)\n"
                f"• **Transport Fee**: ₹30,000/year (Tri-cities: Warangal, Hanamkonda, Kazipet)\n\n"
                f"You can also check merit scholarship slabs (up to 40% waiver) or connect with admissions counsellors."
            )

            follow_up_chips = [
                "Calculate scholarship for my marks",
                "Hostel room options",
                "Placement records for this course",
                "Change school / programme",
            ]

            return {
                "text": reply_text,
                "cards": [fee_card],
                "suggestions": follow_up_chips,
                "new_state": {
                    "fee_flow_state": "completed",
                    "fee_flow_school": sch["id"],
                    "fee_flow_prog": matched_prog["key"],
                    "fee_flow_year": saved_year,
                },
            }

        elif matched_school:
            # User named the School directly (e.g. "fees for Agriculture", "interested in Astra School of Business")
            prog_card = build_course_selection_card(matched_school)
            ug_progs = matched_school["programs"].get("ug", [])
            pg_progs = matched_school["programs"].get("pg", [])
            all_progs = ug_progs + pg_progs

            chips = [p["name"] for p in all_progs[:5]] + ["Change School"]

            return {
                "text": (
                    f"{year_unverified_notice}Great choice{', ' + user_name if user_name else ''}! "
                    f"Here are the verified programmes offered under the **{matched_school['display_name']}**.\n\n"
                    f"Which degree or programme would you like to explore for Academic Year **{saved_year}**?"
                ),
                "cards": [prog_card],
                "suggestions": chips,
                "new_state": {
                    "fee_flow_state": "awaiting_course_selection",
                    "fee_flow_school": matched_school["id"],
                    "fee_flow_prog": None,
                    "fee_flow_year": saved_year,
                },
            }

        else:
            # General fee query: "What is the complete fee structure?", "What is the hostel fee?", "total cost"
            # Initiate Step 1: School selection
            school_card = build_school_selection_card()
            chips = [
                "1. CS & AI (CSE)",
                "2. School of Engineering",
                "3. School of Agriculture",
                "4. Astra School of Business",
                "5. Sciences & Humanities",
                "6. School of Design",
            ]

            return {
                "text": (
                    f"{year_unverified_notice}Sure{', ' + user_name if user_name else ''}! "
                    f"I can help you explore the tuition fees, hostel charges, and other applicable expenses at SR University for Academic Year **{saved_year}**.\n\n"
                    f"First, which academic area or school interests you?"
                ),
                "cards": [school_card],
                "suggestions": chips,
                "new_state": {
                    "fee_flow_state": "awaiting_school_selection",
                    "fee_flow_school": None,
                    "fee_flow_prog": None,
                    "fee_flow_year": saved_year,
                },
            }

    # -------------------------------------------------------------------------
    # State: awaiting_school_selection
    # -------------------------------------------------------------------------
    if current_state == "awaiting_school_selection":
        matched_school = detect_school(msg)
        # Check if user typed a programme manually directly
        matched_prog = detect_program_under_school(msg, matched_school)

        if matched_prog:
            sch = matched_school
            if not sch:
                for s in SCHOOLS_DATA:
                    all_p = s["programs"].get("ug", []) + s["programs"].get("pg", [])
                    if any(p["key"] == matched_prog["key"] for p in all_p):
                        sch = s
                        break
            sch = sch or SCHOOLS_DATA[0]
            fee_card = build_detailed_fee_card(matched_prog, sch, saved_year)
            reply_text = (
                f"Excellent choice {name_prefix}! Here is the complete verified fee breakdown for "
                f"**{matched_prog['name']}** ({sch['short_name']}) for Academic Year **{saved_year}**:\n\n"
                f"• **Tuition Fee**: {fee_card['tuition']['formatted_annual']} per year ({fee_card['tuition']['formatted_semester']} per semester)\n"
                f"• **One-Time Charges**: {fee_card['formatted_one_time_total']} (Enrolment ₹5,000 + Application ₹1,100)\n"
                f"• **Annual Academic Charges**: {fee_card['formatted_annual_other']} (Other fee ₹15,000 + Exam fee ₹5,000)\n"
                f"• **Hostel Accommodation**: ₹1,15,000 – ₹1,35,000/year (Includes central mess dining; AC & Non-AC 3/4 sharing options available)\n"
                f"• **Transport Fee**: ₹30,000/year (Warangal / Hanamkonda / Kazipet tri-cities)\n\n"
                f"Would you like to calculate your merit scholarship or check hostel options?"
            )
            return {
                "text": reply_text,
                "cards": [fee_card],
                "suggestions": ["Calculate scholarship for my marks", "Hostel room options", "Change school / programme"],
                "new_state": {
                    "fee_flow_state": "completed",
                    "fee_flow_school": sch["id"],
                    "fee_flow_prog": matched_prog["key"],
                    "fee_flow_year": saved_year,
                },
            }

        if matched_school:
            prog_card = build_course_selection_card(matched_school)
            ug_progs = matched_school["programs"].get("ug", [])
            pg_progs = matched_school["programs"].get("pg", [])
            all_progs = ug_progs + pg_progs
            chips = [p["name"] for p in all_progs[:5]] + ["Change School"]

            return {
                "text": (
                    f"Great choice{', ' + user_name if user_name else ''}! "
                    f"Here are the verified programmes offered under the **{matched_school['display_name']}**.\n\n"
                    f"Which degree or programme would you like to explore for Academic Year **{saved_year}**?"
                ),
                "cards": [prog_card],
                "suggestions": chips,
                "new_state": {
                    "fee_flow_state": "awaiting_course_selection",
                    "fee_flow_school": matched_school["id"],
                    "fee_flow_prog": None,
                    "fee_flow_year": saved_year,
                },
            }

        # If user typed something not matching any school or course, politely prompt again with options
        return {
            "text": (
                f"I'd love to help you find the exact fee details{', ' + user_name if user_name else ''}. "
                f"Please select one of our 6 schools below or type the name of the programme you're interested in:"
            ),
            "cards": [build_school_selection_card()],
            "suggestions": [s["display_name"] for s in SCHOOLS_DATA],
            "new_state": conv_state,
        }

    # -------------------------------------------------------------------------
    # State: awaiting_course_selection
    # -------------------------------------------------------------------------
    if current_state == "awaiting_course_selection":
        school = next((s for s in SCHOOLS_DATA if s["id"] == saved_school_id), None)
        matched_prog = detect_program_under_school(msg, school)

        if matched_prog:
            sch = school or SCHOOLS_DATA[0]
            spec = detect_specialization(msg, matched_prog)
            fee_card = build_detailed_fee_card(matched_prog, sch, saved_year, spec)

            tuition_fmt = fee_card["tuition"]["formatted_annual"]
            sem_fmt = fee_card["tuition"]["formatted_semester"]
            one_time_fmt = fee_card["formatted_one_time_total"]
            annual_other_fmt = fee_card["formatted_annual_other"]

            reply_text = (
                f"Here is the complete verified fee structure for **{matched_prog['name']}** ({sch['short_name']}) "
                f"for Academic Year **{saved_year}**:\n\n"
                f"• **Tuition Fee**: {tuition_fmt} per year ({sem_fmt} per semester)\n"
                f"• **One-Time Charges**: {one_time_fmt} (Enrolment ₹5,000 + Application ₹1,100)\n"
                f"• **Annual Academic Charges**: {annual_other_fmt} (Other fee ₹15,000 + Exam fee ₹5,000)\n"
                f"• **Hostel Accommodation**: ₹1,15,000 – ₹1,35,000/year (Includes central mess dining; AC & Non-AC 3/4 sharing)\n"
                f"• **Transport Fee**: ₹30,000/year (Tri-cities bus routes)\n\n"
                f"Would you like to calculate your merit scholarship (up to 40% waiver) or check hostel options?"
            )

            follow_up_chips = [
                "Calculate scholarship for my marks",
                "Hostel room options",
                "Placement records for this course",
                "Change school / programme",
            ]

            return {
                "text": reply_text,
                "cards": [fee_card],
                "suggestions": follow_up_chips,
                "new_state": {
                    "fee_flow_state": "completed",
                    "fee_flow_school": sch["id"],
                    "fee_flow_prog": matched_prog["key"],
                    "fee_flow_year": saved_year,
                },
            }

        # User might have typed another school
        new_school = detect_school(msg)
        if new_school and new_school["id"] != saved_school_id:
            prog_card = build_course_selection_card(new_school)
            all_p = new_school["programs"].get("ug", []) + new_school["programs"].get("pg", [])
            chips = [p["name"] for p in all_p[:5]] + ["Change School"]
            return {
                "text": (
                    f"Switched to **{new_school['display_name']}**! "
                    f"Here are the available programmes for Academic Year **{saved_year}**:"
                ),
                "cards": [prog_card],
                "suggestions": chips,
                "new_state": {
                    "fee_flow_state": "awaiting_course_selection",
                    "fee_flow_school": new_school["id"],
                    "fee_flow_prog": None,
                    "fee_flow_year": saved_year,
                },
            }

        # Otherwise re-prompt with the current school's course card
        if school:
            return {
                "text": f"Please select one of the programmes offered under **{school['display_name']}** below, or type your preferred degree:",
                "cards": [build_course_selection_card(school)],
                "suggestions": [p["name"] for p in (school["programs"].get("ug", []) + school["programs"].get("pg", []))[:5]],
                "new_state": conv_state,
            }

    # -------------------------------------------------------------------------
    # State: completed (Handling follow-ups on the same course)
    # -------------------------------------------------------------------------
    if current_state == "completed":
        # Follow-up: Hostel specific query
        if any(k in low for k in ("hostel", "accommodation", "room", "mess", "food")):
            school = next((s for s in SCHOOLS_DATA if s["id"] == saved_school_id), SCHOOLS_DATA[0])
            prog_dict = fees.load_data()["programs"].get(saved_prog_key or "btech_cse", {})
            prog_name = prog_dict.get("name", "B.Tech CSE")

            return {
                "text": (
                    f"Here are the detailed residential hostel charges at SR University:\n\n"
                    f"**Room & Living Fees (Annual)**:\n"
                    f"• **AC, 3-Sharing**: ₹1,35,000/year\n"
                    f"• **AC, 4-Sharing**: ₹1,25,000/year\n"
                    f"• **Non-AC, 3-Sharing**: ₹1,25,000/year\n"
                    f"• **Non-AC, 4-Sharing**: ₹1,15,000/year\n\n"
                    f"**Dining & Security**:\n"
                    f"• Nutritious, hygienic multi-cuisine mess food is included, served in the 4,000-seat central dining complex.\n"
                    f"• 24/7 biometric security, resident wardens, and medical dispensary on campus.\n\n"
                    f"**Deposits & Utilities**:\n"
                    f"• Caution Deposit (Refundable): ₹5,000\n"
                    f"• Laundry Service: ₹5,000/year\n"
                    f"• Electricity Security: ₹10,000 (AC) / ₹5,000 (Non-AC)"
                ),
                "cards": [],
                "suggestions": [
                    "Calculate scholarship for my marks",
                    "Total fee including hostel",
                    "Change school / programme",
                ],
                "new_state": conv_state,
            }

        # Follow-up: Total fee query
        if any(k in low for k in ("total", "total cost", "total fee", "overall")):
            fee_data = fees.load_data()
            prog_dict = fee_data["programs"].get(saved_prog_key or "btech_cse", {})
            tuition = prog_dict.get("tuition_per_year", 340000)
            duration = prog_dict.get("duration_years", 4)
            one_time = 6100
            annual_other = 20000
            hostel_min = 115000

            y1_day_scholar = tuition + one_time + annual_other
            y1_hosteller = y1_day_scholar + hostel_min + 15000  # deposits + laundry

            return {
                "text": (
                    f"Here is the estimated total cost breakdown for **{prog_dict.get('name', 'B.Tech CSE')}**:\n\n"
                    f"• **Year 1 (Day Scholar)**: **{fees.inr(y1_day_scholar)}** (Tuition: {fees.inr(tuition)} + One-time: ₹6,100 + Annual Academic: ₹20,000)\n"
                    f"• **Year 1 (With Non-AC 4-sharing Hostel)**: **{fees.inr(y1_hosteller)}** (Includes room, dining, laundry & security deposits)\n"
                    f"• **Full {duration}-Year Programme Tuition**: **{fees.inr(tuition * duration)}** (before merit scholarships)\n\n"
                    f"Would you like to calculate your scholarship based on your 10+2 marks or entrance rank?"
                ),
                "cards": [],
                "suggestions": [
                    "Calculate scholarship for my marks",
                    "Explore hostel facilities",
                    "Change school / programme",
                ],
                "new_state": conv_state,
            }

        # If user wants to change school / course
        if any(k in low for k in ("change", "another", "different", "other course", "other program")):
            return {
                "text": f"Sure{', ' + user_name if user_name else ''}! Which school or programme would you like to explore next?",
                "cards": [build_school_selection_card()],
                "suggestions": [s["display_name"] for s in SCHOOLS_DATA],
                "new_state": {
                    "fee_flow_state": "awaiting_school_selection",
                    "fee_flow_school": None,
                    "fee_flow_prog": None,
                    "fee_flow_year": saved_year,
                },
            }

    return None
