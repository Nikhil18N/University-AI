"""Counsellor fee assessment formatting, offline fee text, and fee argument extraction."""

import hashlib
import re

from . import config, eligibility, fee_intake, fees

_FEE_WORDS = re.compile(
    r"\b(?:fee|fees|fess|feez|tuition|cost|schol\w*|waiver|how\s+much|per\s+sem)\b",
    re.IGNORECASE,
)
_SCORE_WORDS = r"(?:eapcet|eamcet|emcet|emact|eamect|eamcent)"
_FEE_KEYS = (
    "program", "academic_year", "scholarship_percent", "scholarship_basis_text", "scores_considered",
    "tuition_first_year", "tuition_first_year_after_scholarship", "per_semester_after_scholarship",
    "one_time_enrollment_fee", "other_fee_per_year", "exam_fee_first_year", "hostel",
    "hostel_options_per_year", "semester_1", "semester_2", "sem1_total_payable", "sem2_total_payable",
    "first_year_total_payable", "full_course_total", "application_fee", "yearly_increase",
    "next_scholarship_slab", "flags", "notes",
)


def _select_variation(options: list[str], seed_str: str) -> str:
    """Deterministically pick a phrasing variation from a seed string."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return options[h % len(options)]


def _offline_fee_text(fee: dict) -> str:
    """Format a fallback fee summary when the LLM is unavailable."""
    elig = fee.get("admission_eligibility") or {}
    if elig.get("status") == "below_minimum":
        return elig["explanation"]
    lines = [f"Here is the official {fee['academic_year']} fee for **{fee['program']}**, as per the Admissions Office:", ""]
    if fee.get("scholarship_percent"):
        lines.append(
            f"- Tuition: {fee['tuition_first_year']} per year. With your {fee['scholarship_percent']}% merit "
            f"scholarship ({fee['scholarship_basis']}) it is **{fee['tuition_first_year_after_scholarship']}** per year."
        )
    else:
        lines.append(f"- Tuition: **{fee['tuition_first_year']}** per year.")
    lines += [
        f"- Semester 1 payable: **{fee['sem1_total_payable']}** (includes the one-time enrollment fee).",
        f"- Each regular semester: **{fee['total_per_semester']}**.",
        "",
        "Hostel is optional and charged separately."
        + (" The scholarship is subject to marksheet verification." if fee.get("scholarship_percent") else ""),
        *(["", elig["explanation"], ""] if elig.get("explanation") else []),
        f"Many students are chatting right now, so this is a quick answer from the fee table. For anything "
        f"else, please ask again in a minute or call {config.ADMISSIONS_PHONE}.",
    ]
    return "\n".join(lines)


def counsellor_verdict(fee_res: dict, details: dict) -> dict:
    """Admission eligibility for the counselling result, from eligibility.py."""
    prog_key = fee_res.get("program_key") or details.get("program")
    raw_m, max_m = details.get("raw_marks"), details.get("max_marks")
    pct = None
    if raw_m and max_m and float(max_m) > 100:
        pct = eligibility.percent_from_marks(raw_m, max_m)
    if pct is None and details.get("percent") is not None:
        pct = float(details["percent"])
    return eligibility.assess(prog_key, pct, details.get("stream"))


def format_counsellor_assessment(fee_res: dict, details: dict) -> str:
    """Format structured scholarship assessment and fee details following admission counsellor standards."""
    is_pg = details.get("level") == "pg"
    stage_lbl = details.get("stage_label") or ""

    num = fee_intake._num
    raw_m = details.get("raw_marks")
    max_m = details.get("max_marks")
    pct = details.get("percent")
    if raw_m and max_m and max_m > 100:
        score_str = f"{num(raw_m)}/{num(max_m)} ({num(pct)}%)"
    elif pct:
        score_str = f"{num(pct)}%"
    elif details.get("ib_score"):
        score_str = f"{details['ib_score']} points (out of 45)"
    else:
        score_str = "Standard Eligibility"

    prog_key = fee_res.get("program_key") or details.get("program") or "btech_cse"
    prog_name = fees.clean_program_name(
        prog_key,
        specialization=details.get("specialization"),
        user_text=details.get("program_raw") or details.get("user_query") or fee_res.get("program") or details.get("program_name"),
    )

    pct_waiver = fee_res.get("scholarship_percent", 0)
    orig_tuition = fee_res.get("tuition_first_year")
    savings = fee_res.get("saving_first_year", "₹0")
    net_tuition = fee_res.get("tuition_first_year_after_scholarship", orig_tuition)

    verdict = counsellor_verdict(fee_res, details)
    if verdict.get("status") == eligibility.BELOW or verdict.get("stream_ok") is False:
        score_text = f"{num(raw_m)} marks out of {num(max_m)}" if (raw_m and max_m and max_m > 100) else None
        return eligibility.explain(verdict, score_text)

    shown_score = f"**{num(pct)}%**" if pct is not None else f"**{score_str}**"
    if raw_m and max_m and max_m > 100 and pct is not None:
        shown_score = f"**{num(pct)}%** ({num(raw_m)}/{num(max_m)})"
    prog_name = fees.short_name(prog_key) if prog_key in fees.load_data()["programs"] else prog_name
    seed = f"{prog_name}{pct}{pct_waiver}"
    if pct_waiver > 0:
        heads = [
            f"With {shown_score}, you get a **{pct_waiver}% scholarship** on {prog_name}.",
            f"{shown_score} puts you in the **{pct_waiver}% scholarship** slab for {prog_name}.",
            f"Good news: {shown_score} qualifies for a **{pct_waiver}% scholarship** on {prog_name}.",
        ]
        tuition = f"Tuition comes to **{net_tuition}/year** instead of {orig_tuition} (you save {savings} a year)."
    else:
        heads = [
            f"With {shown_score}, {prog_name} is at the standard fee (no merit slab applies).",
            f"{shown_score} doesn't reach a merit slab for {prog_name}, so the standard fee applies.",
        ]
        tuition = f"Tuition is **{orig_tuition}/year**."
    lines = [_select_variation(heads, seed), tuition]

    if verdict.get("status") == eligibility.CONFIRM:
        lines.append(
            f"The official sources list different minimum marks for {prog_name}, so please confirm "
            f"eligibility with the Admissions Office ({config.ADMISSIONS_PHONE})."
        )
    elif verdict.get("status") == eligibility.MEETS and not details.get("eligibility_shown"):
        lines.append("You also meet the minimum marks for it.")

    tail = []
    if details.get("is_projected"):
        tail.append(
            f"This is an estimate from your {stage_lbl or 'current'} marks; the final scholarship is "
            f"confirmed with your final marksheet."
        )
    if details.get("uses_entrance") and not details.get("has_entrance_score") and not is_pg:
        tail.append("Have an EAPCET rank or JEE Main percentile? Share it and I'll check if it gives more.")
    if tail:
        lines.append(" ".join(tail))
    return "\n\n".join(lines)


def _fee_args_from_message(message: str, profile: dict):
    """Extract calculate_fee arguments for a plain fee/scholarship question, else return None."""
    low = message.lower()
    if not _FEE_WORDS.search(message) or re.search(r"\b(?:vs|versus|compare|difference|cheaper|concession)\b", low):
        return None
    in_message = fees.find_program(message)
    program = in_message or profile.get("program_interest")
    if not program or not fees.find_program(str(program)):
        return None
    args: dict = {"program": in_message or str(program)}
    m = (
        re.search(r"(?<![\d.])(\d{2}(?:\.\d+)?)\s*(?:%(?!ile)|percent(?!ile))", low)
        or re.search(
            r"\b(?:percent(?:age)?|scored?|got)\s*(?:is|of|=|:|-)?\s*(\d{2}(?:\.\d+)?)(?!\d)(?!,\d)(?!\s*(?:rank|marks|lpa|percentile|%ile))",
            low,
        )
    )
    marks = re.search(r"(?<!\d)(\d{3,4})\s*(?:marks|/\s*1000|out\s+of\s+1000)", low)
    if m and float(m.group(1)) <= 100:
        args["percent"] = float(m.group(1))
    elif marks and int(marks.group(1)) <= 1000:
        args["percent"] = round(int(marks.group(1)) / 10, 2)
    m = re.search(
        rf"\b{_SCORE_WORDS}\b\D{{0,25}}(\d[\d,]{{0,6}})\b|\brank\D{{0,12}}(\d[\d,]{{0,6}})\b"
        rf"|(\d[\d,]{{0,6}})\s*(?:rank|in\s+{_SCORE_WORDS})\b",
        low,
    )
    if m:
        args["eapcet_rank"] = int((m.group(1) or m.group(2) or m.group(3)).replace(",", ""))
    m = re.search(r"\bjee\D{0,25}(\d{1,2}(?:\.\d+)?)\b|(\d{1,2}(?:\.\d+)?)\s*(?:percentile|%ile)", low)
    if m:
        args["jee_percentile"] = float(m.group(1) or m.group(2))
    if re.search(r"\b(?:cbse|icse)\b", low):
        args["board"] = "cbse"
    if "hostel" in low:
        if re.search(r"\bnon[\s-]?ac\b", low):
            kind = "non_ac"
        elif re.search(r"\bac\b|a/c|air[\s-]?condition", low):
            kind = "ac"
        else:
            return None
        sharing = "3" if re.search(r"(?<!\d)3[\s-]?(?:shar|bed|person|member)", low) else "4"
        args["hostel"] = f"{kind}_{sharing}"
    return args
