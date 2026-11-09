"""Structured facts service — fetches ground-truth university figures from DB or verified registry."""

import logging
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structured_fact import StructuredFact

logger = logging.getLogger(__name__)

# Fallback verified structured ground truth (2026-27)
# Used when DB is starting or for instantaneous lookups
VERIFIED_FACTS_REGISTRY: list[dict[str, Any]] = [
    # ---- FEES: B.Tech CSE ----
    {
        "category": "fee",
        "program": "B.Tech CSE",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 147500.0,
        "currency": "INR",
        "formatted_value": "₹1,47,500 per semester (₹2,95,000 per year)",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "B.Tech CSE",
        "key_attribute": "admission_enrollment_fee",
        "numeric_value": 30000.0,
        "currency": "INR",
        "formatted_value": "₹30,000 (one-time first year: ₹25,000 admission + ₹5,000 enrollment)",
        "frequency": "one_time",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "B.Tech CSE",
        "key_attribute": "total_tuition_4_year",
        "numeric_value": 1180000.0,
        "currency": "INR",
        "formatted_value": "₹11,80,000 for 4 years (8 semesters × ₹1,47,500)",
        "frequency": "4_years",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "B.Tech CSE",
        "key_attribute": "total_fee_4_year_with_admission",
        "numeric_value": 1210000.0,
        "currency": "INR",
        "formatted_value": "₹12,10,000 total (₹11,80,000 tuition + ₹30,000 one-time admission/enrollment)",
        "frequency": "4_years",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    # ---- FEES: B.Tech ECE ----
    {
        "category": "fee",
        "program": "B.Tech ECE",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 120000.0,
        "currency": "INR",
        "formatted_value": "₹1,20,000 per semester (₹2,40,000 per year)",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    # ---- FEES: B.Tech Mechanical / Civil / EEE ----
    {
        "category": "fee",
        "program": "B.Tech Mechanical",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 100000.0,
        "currency": "INR",
        "formatted_value": "₹1,00,000 per semester (₹2,00,000 per year)",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "B.Tech Civil",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 100000.0,
        "currency": "INR",
        "formatted_value": "₹1,00,000 per semester (₹2,00,000 per year)",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "B.Tech EEE",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 100000.0,
        "currency": "INR",
        "formatted_value": "₹1,00,000 per semester (₹2,00,000 per year)",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    # ---- FEES: Management ----
    {
        "category": "fee",
        "program": "BBA",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 90000.0,
        "currency": "INR",
        "formatted_value": "₹90,000 per semester",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    {
        "category": "fee",
        "program": "MBA",
        "key_attribute": "tuition_fee_sem",
        "numeric_value": 150000.0,
        "currency": "INR",
        "formatted_value": "₹1,50,000 per semester",
        "frequency": "per_semester",
        "source_doc": "SRU Official Fee Schedule 2026-27",
    },
    # ---- FEES: Hostels & Transport ----
    {
        "category": "fee",
        "program": "Hostel Girls AC",
        "key_attribute": "annual_fee",
        "numeric_value": 125000.0,
        "currency": "INR",
        "formatted_value": "₹1,25,000 to ₹1,35,000 per year (includes 4 meals daily, Wi-Fi, laundry)",
        "frequency": "per_year",
        "source_doc": "SRU Hostel Regulations 2026-27",
    },
    {
        "category": "fee",
        "program": "Hostel Boys Non-AC",
        "key_attribute": "annual_fee",
        "numeric_value": 85000.0,
        "currency": "INR",
        "formatted_value": "₹85,000 to ₹95,000 per year (includes 4 meals daily, Wi-Fi, laundry)",
        "frequency": "per_year",
        "source_doc": "SRU Hostel Regulations 2026-27",
    },
    {
        "category": "fee",
        "program": "Hostel Boys AC",
        "key_attribute": "annual_fee",
        "numeric_value": 120000.0,
        "currency": "INR",
        "formatted_value": "₹1,20,000 to ₹1,35,000 per year (includes 4 meals daily, Wi-Fi, laundry)",
        "frequency": "per_year",
        "source_doc": "SRU Hostel Regulations 2026-27",
    },
    {
        "category": "fee",
        "program": "Transport",
        "key_attribute": "annual_bus_fee",
        "numeric_value": 22000.0,
        "currency": "INR",
        "formatted_value": "₹22,000 to ₹30,000 per year (tri-cities bus routes)",
        "frequency": "per_year",
        "source_doc": "SRU Transport Department 2026-27",
    },
    # ---- CUTOFFS & ELIGIBILITY ----
    {
        "category": "cutoff",
        "program": "B.Tech",
        "key_attribute": "minimum_eligibility_pcm",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in 10+2 / Intermediate MPC (500 out of 1000 marks)",
        "frequency": "minimum_cutoff",
        "source_doc": "SRU Admissions Regulations 2026-27",
    },
    {
        "category": "cutoff",
        "program": "BBA",
        "key_attribute": "minimum_eligibility",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in 10+2 / Intermediate in any stream",
        "frequency": "minimum_cutoff",
        "source_doc": "SRU Admissions Regulations 2026-27",
    },
    {
        "category": "cutoff",
        "program": "MBA",
        "key_attribute": "minimum_eligibility",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in Bachelor's Degree",
        "frequency": "minimum_cutoff",
        "source_doc": "SRU Admissions Regulations 2026-27",
    },
    # ---- SCHOLARSHIPS ----
    {
        "category": "scholarship",
        "program": "B.Tech",
        "key_attribute": "merit_scholarship_slabs",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "10% to 50% tuition fee waiver based on 12th/Inter board marks or entrance ranks",
        "frequency": "merit_waiver",
        "source_doc": "SRU Merit Scholarship Scheme 2026-27",
    },
    # ---- PLACEMENTS ----
    {
        "category": "placement",
        "program": "University Overall",
        "key_attribute": "average_package",
        "numeric_value": 6.0,
        "currency": "LPA",
        "formatted_value": "6 LPA average package (graduating batch)",
        "frequency": "annual_ctc",
        "source_doc": "Centre for Student Services & Placements (CSSP) Report 2025-26",
    },
    {
        "category": "placement",
        "program": "University Overall",
        "key_attribute": "highest_package",
        "numeric_value": 51.0,
        "currency": "LPA",
        "formatted_value": "51 LPA highest package from Microsoft",
        "frequency": "highest_ctc",
        "source_doc": "Centre for Student Services & Placements (CSSP) Report 2025-26",
    },
    # ---- RANKINGS & ACCREDITATION ----
    {
        "category": "ranking",
        "program": "Engineering",
        "key_attribute": "nirf_ranking",
        "numeric_value": 91.0,
        "currency": None,
        "formatted_value": "91st in NIRF Engineering 2025 rankings",
        "frequency": "national_rank",
        "source_doc": "National Institutional Ranking Framework (NIRF) 2025",
    },
    {
        "category": "accreditation",
        "program": "B.Tech Programs",
        "key_attribute": "nba_accreditation",
        "numeric_value": None,
        "currency": None,
        "formatted_value": "Tier-I NBA Accreditation for CSE, ECE, EEE, ME, CE",
        "frequency": "tier_1",
        "source_doc": "National Board of Accreditation (NBA)",
    },
]


def get_structured_facts_text(
    query: str,
    program_hint: str | None = None,
) -> str:
    """Format matching structured facts as clean text for insertion into prompt B3."""
    q_lower = query.lower()
    selected: list[dict[str, Any]] = []

    # Category matching
    want_fees = any(k in q_lower for k in ["fee", "fees", "cost", "tuition", "instalment", "installment", "hidden"])
    want_cutoff = any(k in q_lower for k in ["cutoff", "cut-off", "eligibility", "eligible", "minimum", "percent", "marks", "pcm"])
    want_placement = any(k in q_lower for k in ["placement", "package", "lpa", "salary", "recruiter", "company", "companies"])
    want_scholarship = any(k in q_lower for k in ["scholarship", "waiver", "discount"])
    want_ranking = any(k in q_lower for k in ["nirf", "naac", "nba", "rank", "ranking", "accredit"])

    # Program matching
    is_cse = "cse" in q_lower or "computer" in q_lower or (program_hint and "cse" in program_hint.lower())
    is_mech = "mech" in q_lower or (program_hint and "mech" in program_hint.lower())
    is_bba = "bba" in q_lower or (program_hint and "bba" in program_hint.lower())
    is_mba = "mba" in q_lower or (program_hint and "mba" in program_hint.lower())
    is_hostel = "hostel" in q_lower or "room" in q_lower or "mess" in q_lower
    is_transport = "transport" in q_lower or "bus" in q_lower

    for fact in VERIFIED_FACTS_REGISTRY:
        cat = fact["category"]
        prog = fact["program"].lower()

        # If user asks for fees, filter by relevant program if identifiable
        if want_fees and cat == "fee":
            if is_cse and "cse" in prog:
                selected.append(fact)
            elif is_mech and "mech" in prog:
                selected.append(fact)
            elif is_bba and "bba" in prog:
                selected.append(fact)
            elif is_mba and "mba" in prog:
                selected.append(fact)
            elif is_hostel and "hostel" in prog:
                selected.append(fact)
            elif is_transport and "transport" in prog:
                selected.append(fact)
            elif not (is_cse or is_mech or is_bba or is_mba or is_hostel or is_transport):
                # Provide benchmark B.Tech CSE & BBA fees
                if "cse" in prog or "bba" in prog:
                    selected.append(fact)

        elif want_cutoff and cat == "cutoff":
            selected.append(fact)
        elif want_scholarship and cat == "scholarship":
            selected.append(fact)
        elif want_placement and cat == "placement":
            selected.append(fact)
        elif want_ranking and (cat == "ranking" or cat == "accreditation"):
            selected.append(fact)

    if not selected:
        # Default fallback facts if generic
        selected = [f for f in VERIFIED_FACTS_REGISTRY if f["key_attribute"] in ("tuition_fee_sem", "minimum_eligibility_pcm", "average_package")]

    lines = []
    for f in selected:
        lines.append(f"- [{f['program']}] {f['key_attribute']}: {f['formatted_value']} (Source: {f['source_doc']})")

    return "\n".join(lines)


def get_all_grounded_numbers() -> set[str]:
    """Return all verified numbers, amounts, and percentages from the registry for validator whitelisting."""
    whitelist = set()
    for f in VERIFIED_FACTS_REGISTRY:
        val = f.get("formatted_value", "")
        # Extract currency amounts
        for m in re.finditer(r"₹[\d,]+", val):
            whitelist.add(m.group(0))
            whitelist.add(m.group(0).replace("₹", "").replace(",", ""))
        # Extract percentages
        for m in re.finditer(r"\b\d+%", val):
            whitelist.add(m.group(0))
            whitelist.add(m.group(0).replace("%", ""))
        # Extract LPAs
        for m in re.finditer(r"\b\d+\s*LPA\b", val, re.I):
            whitelist.add(m.group(0).upper())
        # Standalone numbers
        if f.get("numeric_value") is not None:
            num = f["numeric_value"]
            if num == int(num):
                whitelist.add(str(int(num)))
            else:
                whitelist.add(str(num))

    # Add standard constants
    whitelist.update({
        "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%",
        "50", "60", "500", "1000", "6", "51", "91", "91st", "2025", "2026", "2027",
        "₹1,47,500", "₹1,20,000", "₹1,00,000", "₹90,000", "₹1,50,000",
        "₹11,80,000", "₹12,10,000", "₹25,000", "₹5,000", "₹30,000", "₹15,000",
        "₹1,25,000", "₹1,35,000", "₹85,000", "₹95,000", "₹22,000",
        "147500", "120000", "100000", "90000", "150000", "1180000", "1210000", "30000",
        "6 LPA", "51 LPA",
    })
    return whitelist
