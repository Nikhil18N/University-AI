"""Structured facts service — authoritative ground-truth university figures from PostgreSQL database.

Enforces:
1. PostgreSQL table `structured_facts` as the single authoritative source of truth.
2. Fast in-memory cached registry updated at startup and refreshed whenever `facts_version` changes.
3. Full audit trail (`source_url`, `last_updated`, `updated_by`).
4. Validator grounding set synchronization.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structured_fact import StructuredFact
from app.services.cache_service import bump_facts_version

logger = logging.getLogger(__name__)

# In-memory runtime cache for sub-millisecond query access without DB overhead
_runtime_facts_cache: list[dict[str, Any]] = []

# Fallback seed facts used ONLY if DB connection fails on cold boot or before initial seed
_FALLBACK_SEED_FACTS: list[dict[str, Any]] = [
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
        "source_doc": "SRU Transport Circular 2026-27",
    },
    {
        "category": "cutoff",
        "program": "B.Tech",
        "key_attribute": "minimum_eligibility_pcm",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in 10+2 / Intermediate MPC (500 out of 1000 marks)",
        "frequency": "admission_cutoff",
        "source_doc": "SRU Admissions Eligibility Policy 2026-27",
    },
    {
        "category": "cutoff",
        "program": "BBA",
        "key_attribute": "minimum_eligibility",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in 10+2 / Intermediate in any stream",
        "frequency": "admission_cutoff",
        "source_doc": "SRU Admissions Eligibility Policy 2026-27",
    },
    {
        "category": "cutoff",
        "program": "MBA",
        "key_attribute": "minimum_eligibility",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "50% aggregate marks in Bachelor's Degree",
        "frequency": "admission_cutoff",
        "source_doc": "SRU Admissions Eligibility Policy 2026-27",
    },
    {
        "category": "scholarship",
        "program": "B.Tech",
        "key_attribute": "merit_scholarship_slabs",
        "numeric_value": 50.0,
        "currency": None,
        "formatted_value": "10% to 50% tuition fee waiver based on 12th/Inter board marks or entrance ranks",
        "frequency": "merit_slabs",
        "source_doc": "SRU Merit Scholarship Scheme 2026-27",
    },
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

# Aliased for backward compatibility with scripts/seeds
VERIFIED_FACTS_REGISTRY = _FALLBACK_SEED_FACTS


def _row_to_dict(row: StructuredFact) -> dict[str, Any]:
    meta = row.metadata_ or {}
    return {
        "id": str(row.id),
        "category": row.category,
        "program": row.program,
        "key_attribute": row.key_attribute,
        "numeric_value": row.numeric_value,
        "currency": row.currency,
        "formatted_value": row.formatted_value,
        "frequency": row.frequency,
        "academic_year": row.academic_year,
        "source_doc": row.source_doc,
        "notes": row.notes,
        "source_url": meta.get("source_url", "https://sru.edu.in/admissions"),
        "last_updated": meta.get("last_updated"),
        "updated_by": meta.get("updated_by", "system"),
    }


async def refresh_facts_cache_from_db(db: AsyncSession) -> list[dict[str, Any]]:
    """Query PostgreSQL structured_facts table and update the in-memory cache."""
    global _runtime_facts_cache
    try:
        stmt = select(StructuredFact).order_by(StructuredFact.category, StructuredFact.program)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        if rows:
            _runtime_facts_cache = [_row_to_dict(r) for r in rows]
            logger.info("Loaded %d authoritative structured facts from PostgreSQL", len(_runtime_facts_cache))
        else:
            _runtime_facts_cache = list(_FALLBACK_SEED_FACTS)
            logger.warning("PostgreSQL structured_facts table empty; using fallback registry (%d items)", len(_runtime_facts_cache))
    except Exception as exc:
        logger.error("Failed to load structured facts from DB (using fallback): %s", exc)
        if not _runtime_facts_cache:
            _runtime_facts_cache = list(_FALLBACK_SEED_FACTS)
    return _runtime_facts_cache


def get_active_facts() -> list[dict[str, Any]]:
    """Return authoritative structured facts: in-memory DB cache, falling back to seed list."""
    if _runtime_facts_cache:
        return _runtime_facts_cache
    return _FALLBACK_SEED_FACTS


# Canonical statistics with mandatory scope, year, and single canonical wording (T16)
CANONICAL_STATISTICS: dict[str, dict[str, str]] = {
    "average_package": {
        "value": "6 LPA",
        "scope": "university-wide across all graduating disciplines",
        "academic_year": "2023–24 graduating batch",
        "basis": "average CTC",
        "canonical": "For the 2023–24 graduating batch university-wide, the average placement package was 6 LPA.",
    },
    "highest_package": {
        "value": "51 LPA",
        "scope": "university-wide top recruiter drive (Microsoft)",
        "academic_year": "2023–24 batch",
        "basis": "highest CTC (7.5+ CGPA required)",
        "canonical": "The highest package was 51 LPA from Microsoft (eligible for students maintaining a 7.5+ CGPA) for the 2023–24 batch.",
    },
    "nirf_ranking": {
        "value": "91st",
        "scope": "National Institutional Ranking Framework (Engineering)",
        "academic_year": "2025",
        "basis": "Engineering Category rank",
        "canonical": "SR University is ranked 91st in NIRF Engineering (2025).",
    },
}


def get_structured_facts_text(
    query: str,
    program_hint: str | None = None,
) -> str:
    """Format matching structured facts as clean text for insertion into prompt B3."""
    q_lower = query.lower()
    selected: list[dict[str, Any]] = []
    active_facts = get_active_facts()

    # Category matching
    want_fees = any(k in q_lower for k in ["fee", "fees", "cost", "tuition", "instalment", "installment", "hidden"])
    want_cutoff = any(k in q_lower for k in ["cutoff", "cut-off", "eligibility", "eligible", "minimum", "percent", "marks", "pcm"])
    want_placement = any(k in q_lower for k in ["placement", "package", "lpa", "salary", "recruiter", "company", "companies", "fact check", "compare", "better"])
    want_scholarship = any(k in q_lower for k in ["scholarship", "waiver", "discount"])
    want_ranking = any(k in q_lower for k in ["nirf", "naac", "nba", "rank", "ranking", "accredit"])

    # Program matching
    is_cse = "cse" in q_lower or "computer" in q_lower or (program_hint and "cse" in program_hint.lower())
    is_mech = "mech" in q_lower or (program_hint and "mech" in program_hint.lower())
    is_bba = "bba" in q_lower or (program_hint and "bba" in program_hint.lower())
    is_mba = "mba" in q_lower or (program_hint and "mba" in program_hint.lower())
    is_hostel = "hostel" in q_lower or "room" in q_lower or "mess" in q_lower
    is_transport = "transport" in q_lower or "bus" in q_lower

    for fact in active_facts:
        cat = fact["category"]
        prog = fact["program"].lower()

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
        selected = [f for f in active_facts if f["key_attribute"] in ("tuition_fee_sem", "minimum_eligibility_pcm", "average_package")]

    lines = []
    for f in selected:
        key = f.get("key_attribute", "")
        if key in CANONICAL_STATISTICS:
            cstat = CANONICAL_STATISTICS[key]
            lines.append(
                f"- [{f['program']}] {key}: {f['formatted_value']} "
                f"[Scope: {cstat['scope']} | Batch/Year: {cstat['academic_year']} | Basis: {cstat['basis']} | Canonical: \"{cstat['canonical']}\"] "
                f"(Source: {f['source_doc']})"
            )
        else:
            lines.append(f"- [{f['program']}] {f['key_attribute']}: {f['formatted_value']} (Source: {f['source_doc']})")

    return "\n".join(lines)


def get_all_grounded_numbers() -> set[str]:
    """Return all verified numbers, amounts, and percentages from the active facts for validator whitelisting."""
    whitelist = set()
    active_facts = get_active_facts()

    for f in active_facts:
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


async def update_structured_fact(
    db: AsyncSession,
    fact_id: uuid.UUID,
    updates: dict[str, Any],
    editor: str = "admin",
    redis_client: Any = None,
) -> dict[str, Any] | None:
    """Update a structured fact row in PostgreSQL, maintain audit trail, and bump facts_version in Redis."""
    stmt = select(StructuredFact).where(StructuredFact.id == fact_id)
    result = await db.execute(stmt)
    fact = result.scalar_one_or_none()
    if not fact:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    meta = dict(fact.metadata_ or {})
    meta["last_updated"] = now_iso
    meta["updated_by"] = editor
    if "source_url" in updates:
        meta["source_url"] = updates["source_url"]
    fact.metadata_ = meta

    for field in ("formatted_value", "numeric_value", "currency", "frequency", "source_doc", "notes"):
        if field in updates and updates[field] is not None:
            setattr(fact, field, updates[field])

    await db.commit()
    await db.refresh(fact)

    # Invalidate cache
    if redis_client:
        await bump_facts_version(redis_client)

    # Refresh in-memory cache
    await refresh_facts_cache_from_db(db)

    return _row_to_dict(fact)
