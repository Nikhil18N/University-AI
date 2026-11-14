"""Fee, scholarship and eligibility maths. Pure Python, no AI.

The agent is NOT allowed to state a fee from memory. It must call these
functions, which read fees_2027_28.json, so every number is traceable.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("fees_2027_28.json")
HOSTEL_LABELS = {
    "non_ac_4": "Non-AC, 4-sharing", "non_ac_3": "Non-AC, 3-sharing",
    "ac_4": "AC, 4-sharing", "ac_3": "AC, 3-sharing",
}


@lru_cache(maxsize=1)
def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def inr(amount) -> str:
    """Format rupees the Indian way: 340000 -> '₹3,40,000'."""
    n = int(round(amount))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + s


def find_program(text: str):
    """Match free text like 'cse', 'mech', 'B.Tech AI & ML' to a program key."""
    if not text:
        return None
    data = load_data()["programs"]
    t = " " + text.lower().replace(".", "").replace("-", " ") + " "
    if text in data:
        return text
    best = None
    for key, prog in data.items():
        for alias in prog["aliases"]:
            if f" {alias} " in t or t.strip() == alias:
                if best is None or len(alias) > best[0]:
                    best = (len(alias), key)
    return best[1] if best else None


def _match_slab(slabs, value):
    for slab in slabs:
        if slab["min"] <= value <= slab["max"]:
            return slab["percent"]
    return 0


def scholarship_for(program_key, percent=None, board="state_board",
                    eapcet_rank=None, jee_percentile=None) -> dict:
    """Best scholarship across the scores given. Never guesses a missing table."""
    data = load_data()
    slab_set = data["slab_sets"].get(data["programs"][program_key]["slab_set"], {})
    scores = []
    if percent is not None:
        scores.append(("cbse" if board == "cbse" else "state_board", float(percent)))
    if eapcet_rank is not None:
        scores.append(("eapcet_rank", int(eapcet_rank)))
    if jee_percentile is not None:
        scores.append(("jee_percentile", float(jee_percentile)))

    best, basis, missing = 0, None, []
    for kind, value in scores:
        table = slab_set.get(kind) or []
        if not table:
            missing.append(kind)
            continue
        pct = _match_slab(table, value)
        if pct > best:
            best, basis = pct, f"{kind.replace('_', ' ')} {value:g}"
    return {"percent": best, "basis": basis, "not_configured": missing}


def check_eligibility(program: str, percent: float) -> dict:
    key = find_program(program)
    if not key:
        return {"status": "unknown_program", "known_programs": list_programs()["programs"]}
    prog = load_data()["programs"][key]
    eligible = float(percent) >= prog["min_percent"]
    return {
        "status": "ok", "program": prog["name"], "your_percent": float(percent),
        "minimum_percent": prog["min_percent"], "eligible": eligible,
        "requirement": prog["eligibility_note"],
        "advice": None if eligible else
        "Below the published minimum. Do not reject the student: suggest speaking "
        "to the admissions office about options.",
    }


def list_programs() -> dict:
    data = load_data()
    return {"status": "ok", "academic_year": data["academic_year"], "programs": [
        {"key": k, "name": p["name"], "tuition_per_year": inr(p["tuition_per_year"]),
         "minimum_percent": p["min_percent"]} for k, p in data["programs"].items()]}


def calculate_fee(program: str, percent=None, board="state_board", eapcet_rank=None,
                  jee_percentile=None, hostel="none", specialization=False) -> dict:
    """Tuition, scholarship, first-year payable and full-course total for one student."""
    data = load_data()
    key = find_program(program)
    if not key:
        return {"status": "unknown_program", "known_programs": list_programs()["programs"]}
    prog = data["programs"][key]
    sch = scholarship_for(key, percent, board, eapcet_rank, jee_percentile)
    pct = sch["percent"]

    years = prog.get("duration_years")
    base = prog["tuition_per_year"]
    per_year = []
    for y in range(years or 1):
        tuition = base + prog["yearly_increase"] * y
        net = round(tuition * (100 - pct) / 100)
        per_year.append({"year": y + 1, "tuition": inr(tuition), "after_scholarship": inr(net),
                         "per_semester": inr(net / 2), "_net": net})

    one_time = sum(data["one_time"].get(k, 0) for k in ("enrollment_fee",))
    yearly_other = sum(data["yearly_other"].values())
    hostel_fee = data["hostel_per_year"].get(hostel, 0) if hostel and hostel != "none" else 0
    spec = prog.get("specialization_fee_per_year_from_year2", 0) if specialization else 0

    first_year = per_year[0]["_net"] + one_time + yearly_other + hostel_fee
    result = {
        "status": "ok",
        "academic_year": data["academic_year"],
        "source": data["source"],
        "data_status": "verified" if data.get("verified") else
        "UNVERIFIED: tell the student the final fee will be confirmed by the Admissions Office",
        "program": prog["name"],
        "scholarship_percent": pct,
        "scholarship_basis": sch["basis"],
        "tuition_first_year": inr(base),
        "tuition_first_year_after_scholarship": inr(per_year[0]["_net"]),
        "per_semester_after_scholarship": per_year[0]["per_semester"],
        "saving_first_year": inr(base - per_year[0]["_net"]),
        "one_time_enrollment_fee": inr(one_time),
        "other_yearly_fees": inr(yearly_other),
        "hostel": {"type": HOSTEL_LABELS.get(hostel), "per_year": inr(hostel_fee)} if hostel_fee else None,
        "first_year_total_payable": inr(first_year),
        "yearly_increase": inr(prog["yearly_increase"]),
        "not_included": ["transport", "books and personal expenses"] + ([] if hostel_fee else ["hostel"]),
        "notes": [],
    }
    if years:
        total = (sum(p["_net"] for p in per_year) + one_time
                 + (yearly_other + hostel_fee) * years + spec * (years - 1))
        result["duration_years"] = years
        result["year_by_year"] = [{k: v for k, v in p.items() if k != "_net"} for p in per_year]
        result["full_course_total"] = inr(total)
        if spec:
            result["specialization_fee"] = f"{inr(spec)} per year from year 2 (included in total)"
    else:
        result["notes"].append("Course duration is not set in the fee file, so no full-course total.")
    if sch["not_configured"]:
        result["notes"].append(
            "No scholarship table is configured for: " + ", ".join(sch["not_configured"]) +
            ". Do NOT state a scholarship for that score; say the Admissions Office will confirm it.")
    if percent is None and eapcet_rank is None and jee_percentile is None:
        result["notes"].append("No marks or rank given, so no scholarship applied. Ask for marks to personalise.")
    result["notes"].append("Scholarship continuation rules are set by the university.")
    return result
