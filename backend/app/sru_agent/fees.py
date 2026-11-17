"""Fee, scholarship and eligibility maths. Pure Python, no AI.

The agent is NOT allowed to state a fee from memory. It must call these
functions, which read fees_2027_28.json, so every number is traceable.
The Fee & Scholarship Calculator reads the same file through
/api/v1/agent/fee-config and /api/v1/agent/calculate.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("fees_2027_28.json")
HOSTEL_LABELS = {
    "non_ac_4": "Non-AC, 4-sharing", "non_ac_3": "Non-AC, 3-sharing",
    "ac_4": "AC, 4-sharing", "ac_3": "AC, 3-sharing",
}
# score kind -> label shown to students
EXAM_LABELS = {
    "state_board": "State Board (10+2 / Inter) %",
    "cbse": "CBSE / ICSE %",
    "jee_percentile": "JEE Main percentile",
    "eapcet_rank": "TG/AP EAPCET rank",
    "ib": "IB Diploma score",
}
# A degree word in the question limits which programs may match, so that
# "mtech data science" is M.Tech and not B.Tech CSE.
_DEGREE_PREFIXES = {
    "mtech": ("mtech",), "mba": ("mba",), "mca": ("mca",), "msc": ("msc",),
    "bba": ("bba",), "bca": ("bca",), "bsc": ("bsc",), "bcom": ("bcom",),
    "bdes": ("bdes",), "btech": ("btech",),
}
_DEGREE_SPELLINGS = (
    (r"\bb\s?tech\b", "btech"), (r"\bm\s?tech\b", "mtech"), (r"\bb\s?sc\b", "bsc"),
    (r"\bm\s?sc\b", "msc"), (r"\bb\s?com\b", "bcom"), (r"\bb\s?des\b", "bdes"),
)


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


def _normalise(text: str) -> str:
    t = (text or "").lower().replace(".", "")
    t = re.sub(r"[^a-z0-9&+ ]", " ", t)
    for pattern, word in _DEGREE_SPELLINGS:
        t = re.sub(pattern, word, t)
    return " " + re.sub(r"\s+", " ", t).strip() + " "


def find_program(text: str):
    """Match free text like 'cse', 'mech', 'B.Tech AI & ML' to a program key."""
    if not text:
        return None
    programs = load_data()["programs"]
    if text in programs:
        return text
    t = _normalise(text)
    if t.strip() in programs:
        return t.strip()

    degree = next((d for d in _DEGREE_PREFIXES if f" {d} " in t), None)
    allowed = [k for k in programs if not degree or k.startswith(_DEGREE_PREFIXES[degree])]

    best = None
    for key in allowed:
        for alias in programs[key]["aliases"]:
            if f" {alias} " in t and (best is None or len(alias) > best[0]):
                best = (len(alias), key)
    if best:
        return best[1]
    # "mca", "mtech", "bcom" on their own name exactly one program
    if degree and degree in programs:
        return degree
    return None


def _is_generic_btech(text: str) -> bool:
    t = _normalise(text)
    return " btech " in t or " engineering " in t


def _match_slab(slabs, value):
    for slab in slabs:
        if slab["min"] <= value <= slab["max"]:
            return slab["percent"]
    return 0


def _scores(percent=None, board="state_board", eapcet_rank=None, jee_percentile=None, ib_score=None,
            level="ug"):
    scores = []
    if percent is not None:
        # PG scholarships use the percentage in the qualifying degree, whatever the school board was.
        is_cbse = level != "pg" and str(board or "").lower() in ("cbse", "icse")
        scores.append(("cbse" if is_cbse else "state_board", float(percent)))
    if eapcet_rank is not None:
        scores.append(("eapcet_rank", int(eapcet_rank)))
    if jee_percentile is not None:
        scores.append(("jee_percentile", float(jee_percentile)))
    if ib_score is not None:
        scores.append(("ib", float(ib_score)))
    return scores


def _score_text(kind: str, value, level: str = "ug") -> str:
    """'Intermediate 85%', 'EAPCET rank 40,000' ... for showing a score back to the student."""
    if kind == "eapcet_rank":
        return f"EAPCET rank {int(value):,}"
    if kind == "jee_percentile":
        return f"JEE Main {value:g} percentile"
    if kind == "ib":
        return f"IB score {value:g}/45"
    if level == "pg":
        return f"qualifying degree {value:g}%"
    return f"{'CBSE/ICSE' if kind == 'cbse' else 'Intermediate'} {value:g}%"


def _no_slab_reason(kind: str, table: list) -> str:
    """Why a score earned no scholarship, in words a student understands."""
    if kind == "eapcet_rank":
        worst = max(s["max"] for s in table)
        return f"rank-based scholarships cover EAPCET ranks 1 to {int(worst):,} only"
    lowest = min(s["min"] for s in table)
    unit = {"jee_percentile": " percentile", "ib": " (IB score)"}.get(kind, "%")
    return f"merit scholarship starts at {lowest:g}{unit}"


def scholarship_for(program_key, percent=None, board="state_board",
                    eapcet_rank=None, jee_percentile=None, ib_score=None) -> dict:
    """Best scholarship across the scores given, plus what EACH score earns by itself.
    Never guesses a missing table."""
    data = load_data()
    prog = data["programs"][program_key]
    level = prog.get("level", "ug")
    slab_set = data["slab_sets"].get(prog["slab_set"], {})
    best, basis, basis_text, missing, considered = 0, None, None, [], []
    for kind, value in _scores(percent, board, eapcet_rank, jee_percentile, ib_score, level):
        table = slab_set.get(kind) or []
        label = _score_text(kind, value, level)
        if not table:
            missing.append(kind)
            considered.append({"score": label, "scholarship_percent": 0,
                               "note": "this score is not used for scholarships in this program"})
            continue
        pct = _match_slab(table, value)
        entry = {"score": label, "scholarship_percent": pct}
        if not pct:
            entry["note"] = _no_slab_reason(kind, table)
        considered.append(entry)
        if pct > best:
            best, basis, basis_text = pct, f"{kind.replace('_', ' ')} {value:g}", label
    return {"percent": best, "basis": basis, "basis_text": basis_text, "not_configured": missing,
            "considered": considered}


def _exam_label(kind: str, prog: dict) -> str:
    if prog.get("level") == "pg" and kind == "state_board":
        return "Qualifying degree %"
    return EXAM_LABELS[kind]


def _range_text(kind: str, slab: dict) -> str:
    lo, hi = slab["min"], slab["max"]
    if kind == "eapcet_rank":
        return f"{lo:,} – {hi:,}"
    if kind == "ib":
        return f"{lo:g} and above" if hi >= 45 else f"{lo:g} – {hi:g}"
    unit = " %ile" if kind == "jee_percentile" else "%"
    if hi >= 100:
        return f"{lo:g}{unit} and above"
    return f"{lo:g} – {int(hi * 10) / 10:g}{unit}"


def _next_slab(program_key, pct_now, percent=None, board="state_board",
               eapcet_rank=None, jee_percentile=None, ib_score=None):
    """The next higher slab for the score the student gave: what it needs and what it saves."""
    data = load_data()
    prog = data["programs"][program_key]
    slab_set = data["slab_sets"].get(prog["slab_set"], {})
    scores = _scores(percent, board, eapcet_rank, jee_percentile, ib_score, prog.get("level", "ug"))
    if not scores:
        return None
    kind, _value = scores[0]
    higher = sorted((s for s in slab_set.get(kind) or [] if s["percent"] > pct_now),
                    key=lambda s: s["percent"])
    if not higher:
        return None
    nxt = higher[0]
    extra = round(prog["tuition_per_year"] * (nxt["percent"] - pct_now) / 100)
    return {"scholarship_percent": nxt["percent"],
            "requires": f"{_exam_label(kind, prog)}: {_range_text(kind, nxt)}",
            "extra_saving_first_year": inr(extra)}


def check_eligibility(program: str, percent: float) -> dict:
    data = load_data()
    key = find_program(program)
    generic = False
    if not key and _is_generic_btech(program):
        # "btech" with no branch: every B.Tech branch has the same minimum
        key, generic = "btech_mech", True
    if not key:
        return {"status": "unknown_program", "known_programs": list_programs()["programs"]}
    prog = data["programs"][key]
    pct = float(percent)
    eligible = pct >= prog["min_percent"]
    result = {
        "status": "ok",
        "program": "B.Tech (any branch)" if generic else prog["name"],
        "your_percent": pct,
        "minimum_percent": prog["min_percent"], "eligible": eligible,
        "requirement": prog["eligibility_note"],
        "advice": None if eligible else
        "Below the published minimum. Do not reject the student: suggest speaking "
        "to the admissions office about options.",
        "reminder": "Eligible means the student can apply. Admission depends on seat availability "
                    "and document verification. Never promise a seat.",
    }
    band = prog.get("fee_band_min_percent")
    if generic:
        result["note"] = ("For CSE and ECE the fee card lists fees from 55%; "
                          "for 50-54.9% ask the Admissions Office to confirm.")
    elif eligible and band and pct < band:
        result["confirm_with_admissions"] = (
            f"The fee card lists {prog['name']} fees from {band}% marks. For {pct:g}% the "
            f"Admissions Office must confirm admission and the applicable fee.")
    return result


def list_programs() -> dict:
    data = load_data()
    return {"status": "ok", "academic_year": data["academic_year"], "programs": [
        {"key": k, "name": p["name"], "level": p.get("level", "ug"),
         "tuition_per_year": inr(p["tuition_per_year"]),
         "minimum_percent": p["min_percent"]} for k, p in data["programs"].items()]}


def program_info(program: str) -> dict:
    """Eligibility, duration, tuition and scholarship slabs for one program (no student marks needed)."""
    data = load_data()
    key = find_program(program)
    if not key:
        return {"status": "unknown_program", "known_programs": list_programs()["programs"]}
    prog = data["programs"][key]
    slab_set = data["slab_sets"].get(prog["slab_set"], {})
    slabs = {}
    for kind, table in slab_set.items():
        if table:
            slabs[_exam_label(kind, prog)] = [
                f"{_range_text(kind, s)} -> {s['percent']}% scholarship"
                for s in sorted(table, key=lambda s: s["percent"])]
    info = {
        "status": "ok", "academic_year": data["academic_year"], "source": data["source"],
        "program": prog["name"], "level": prog.get("level", "ug"),
        "duration_years": prog.get("duration_years"),
        "minimum_percent": prog["min_percent"],
        "eligibility": prog["eligibility_note"],
        "tuition_per_year": inr(prog["tuition_per_year"]),
        "tuition_per_semester": inr(prog["tuition_per_year"] / 2),
        "yearly_tuition_increase": inr(prog["yearly_increase"]),
        "merit_scholarship_slabs": slabs,
        "reminder": "Admission depends on seat availability and document verification.",
    }
    if prog.get("fee_band_min_percent"):
        info["note"] = (f"The fee card lists fees for this program from "
                        f"{prog['fee_band_min_percent']}% marks; below that, the Admissions Office confirms.")
    if prog.get("duration_years") is None:
        info["duration_note"] = "Course duration is not in the fee file. Do not state one."
    return info


def special_concessions(category: str = "") -> dict:
    """Annual special-category concessions from the circular, optionally filtered by a keyword."""
    data = load_data()
    items = data.get("special_concessions", [])
    ignore = {"state", "level", "student", "students", "from", "any", "the", "and", "for", "child",
              "children", "scholarship", "concession", "discount", "fee", "there"}
    words = [w for w in re.findall(r"[a-z]+", (category or "").lower()) if len(w) > 2 and w not in ignore]
    matched = [c for c in items
               if any(w in c["label"].lower() or w in c["key"] for w in words)] if words else []
    return {
        "status": "ok", "academic_year": data["academic_year"],
        "matching": [{"category": c["label"], "per_year": inr(c["amount"])} for c in matched],
        "all_categories": [{"category": c["label"], "per_year": inr(c["amount"])} for c in items],
        "note": data.get("special_concession_note", ""),
        "instruction": "If 'matching' is empty, say plainly that the category asked about is not in the "
                       "official list, then mention the closest listed categories. Do not ask the student "
                       "for personal hardship details; documents go to the Admissions Office.",
    }


def calculate_fee(program: str, percent=None, board="state_board", eapcet_rank=None,
                  jee_percentile=None, hostel="none", specialization=False,
                  ib_score=None, transport=False) -> dict:
    """Tuition, scholarship, first-year payable and full-course total for one student."""
    data = load_data()
    key = find_program(program)
    if not key:
        return {"status": "unknown_program",
                "ask_student": "Ask which course or branch they mean.",
                "known_programs": list_programs()["programs"]}
    prog = data["programs"][key]
    sch = scholarship_for(key, percent, board, eapcet_rank, jee_percentile, ib_score)
    pct = sch["percent"]

    years = prog.get("duration_years")
    base = prog["tuition_per_year"]
    per_year = []
    # The circular's last column is "Yearly Fee Increase (Irrespective of Schol.)": every student
    # pays the same flat increase each year, so the scholarship applies to the year-1 fee only
    # and the increase is added on top (25% on CSE: 2,55,000 then 2,64,000, not 2,61,750).
    net_first = round(base * (100 - pct) / 100)
    for y in range(years or 1):
        step = prog["yearly_increase"] * y
        net = net_first + step
        per_year.append({"year": y + 1, "tuition": inr(base + step), "after_scholarship": inr(net),
                         "per_semester": inr(net / 2), "_net": net})

    one_time = data["one_time"].get("enrollment_fee", 0)
    yearly_other = sum(data["yearly_other"].values())
    hostel_fee = data["hostel_per_year"].get(hostel, 0) if hostel and hostel != "none" else 0
    transport_fee = data.get("transport_per_year", 0) if transport else 0
    spec = prog.get("specialization_fee_per_year_from_year2", 0) if specialization else 0

    first_year = per_year[0]["_net"] + one_time + yearly_other + hostel_fee + transport_fee

    tuition_sem1 = round(per_year[0]["_net"] / 2)
    other_sem = round(yearly_other / 2)
    has_hostel = hostel_fee > 0
    hostel_sem = round(hostel_fee / 2) if has_hostel else 0
    transport_sem = round(transport_fee / 2)
    regular_sem_total = tuition_sem1 + other_sem + hostel_sem + transport_sem
    sem1_total_payable = regular_sem_total + one_time

    result = {
        "status": "ok",
        "academic_year": data["academic_year"],
        "source": data["source"],
        "data_status": "verified" if data.get("verified") else
        "UNVERIFIED: tell the student the final fee will be confirmed by the Admissions Office",
        "program_key": key,
        "program": prog["name"],
        "scholarship_percent": pct,
        "scholarship_basis": sch["basis"],
        "scholarship_basis_text": sch["basis_text"],
        # What each score earns by itself. The best one is applied; scholarships are not added together.
        "scores_considered": sch["considered"],
        "tuition_first_year": inr(base),
        "tuition_first_year_after_scholarship": inr(per_year[0]["_net"]),
        "per_semester_after_scholarship": per_year[0]["per_semester"],
        "saving_first_year": inr(base - per_year[0]["_net"]),
        "one_time_enrollment_fee": inr(one_time),
        "other_yearly_fees": inr(yearly_other),
        "other_fees_per_semester": inr(other_sem),
        "has_hostel": has_hostel,
        "hostel": {
            "type": HOSTEL_LABELS.get(hostel),
            "per_year": inr(hostel_fee),
            "per_semester": inr(hostel_sem),
        } if has_hostel else None,
        "transport_per_year": inr(transport_fee) if transport_fee else None,
        "total_per_semester": inr(regular_sem_total),
        "sem1_total_payable": inr(sem1_total_payable),
        "per_sem_breakdown": {
            "tuition_per_sem": per_year[0]["per_semester"],
            "other_fees_per_sem": inr(other_sem),
            **({"hostel_per_sem": inr(hostel_sem)} if has_hostel else {}),
            **({"transport_per_sem": inr(transport_sem)} if transport_fee else {}),
            "one_time_enrollment": inr(one_time),
            "regular_sem_total": inr(regular_sem_total),
            "sem1_total_payable": inr(sem1_total_payable),
        },
        "first_year_total_payable": inr(first_year),
        "yearly_increase": inr(prog["yearly_increase"]),
        "not_included": ["books and personal expenses"]
        + ([] if transport_fee else ["transport"]) + ([] if hostel_fee else ["hostel"]),
        "notes": [],
    }

    if years:
        total = (sum(p["_net"] for p in per_year) + one_time
                 + (yearly_other + hostel_fee + transport_fee) * years + spec * (years - 1))
        result["duration_years"] = years
        result["year_by_year"] = [{k: v for k, v in p.items() if k != "_net"} for p in per_year]
        result["full_course_total"] = inr(total)
        if spec:
            result["specialization_fee"] = f"{inr(spec)} per year from year 2 (included in total)"
    else:
        result["notes"].append("Course duration is not set in the fee file, so no full-course total.")

    nxt = _next_slab(key, pct, percent, board, eapcet_rank, jee_percentile, ib_score)
    if nxt:
        result["next_scholarship_slab"] = nxt
    if has_hostel:
        result["hostel_options_per_year"] = {HOSTEL_LABELS[k]: inr(v) for k, v in data["hostel_per_year"].items()}
    if sch["not_configured"]:
        result["notes"].append(
            "No scholarship table is configured for: " + ", ".join(sch["not_configured"]) +
            ". Do NOT state a scholarship for that score; say the Admissions Office will confirm it.")
    given = _scores(percent, board, eapcet_rank, jee_percentile, ib_score)
    if not given:
        result["notes"].append("No marks or rank given, so no scholarship applied. Ask for marks to personalise.")
    elif pct == 0 and not sch["not_configured"]:
        result["notes"].append("This score is outside the merit scholarship slabs, so the standard fee applies. "
                               "Another score (board %, JEE, EAPCET) may still qualify.")
    band = prog.get("fee_band_min_percent")
    if percent is not None and band and float(percent) < band:
        result["notes"].append(f"The fee card lists {prog['name']} fees from {band}% marks; for a lower "
                               f"percentage the Admissions Office must confirm admission and fee.")
    if ib_score is not None and 30 <= float(ib_score) <= 37 and data.get("ib_overlap_note"):
        result["notes"].append(data["ib_overlap_note"])
    result["notes"].append("Scholarship is subject to marksheet verification; continuation rules are set by the university.")
    return result


def rankings() -> dict:
    """Rankings and accreditations exactly as printed on the official fee card."""
    data = load_data()
    return {"status": "ok", "source": data["source"], "rankings": data.get("rankings", [])}


def compare_programs(program_a: str, program_b: str, **score) -> dict:
    """Side-by-side fee summary of two programs for the same student."""
    rows = []
    for name in (program_a, program_b):
        r = calculate_fee(name, **score)
        if r.get("status") != "ok":
            return {"status": "unknown_program", "unknown": name,
                    "known_programs": list_programs()["programs"]}
        rows.append({k: r.get(k) for k in (
            "program", "scholarship_percent", "tuition_first_year",
            "tuition_first_year_after_scholarship", "per_semester_after_scholarship",
            "first_year_total_payable", "yearly_increase", "duration_years", "full_course_total")})
    data = load_data()
    return {"status": "ok", "academic_year": data["academic_year"], "source": data["source"],
            "comparison": rows,
            "instruction": "Compare on fees only. Do not say which branch has better jobs unless a "
                           "search result supports it."}


def fee_config() -> dict:
    """Everything the Fee & Scholarship Calculator needs to draw itself."""
    data = load_data()
    programs = []
    for key, prog in data["programs"].items():
        slab_set = data["slab_sets"].get(prog["slab_set"], {})
        exams = [{"key": k, "label": _exam_label(k, prog)} for k in EXAM_LABELS if slab_set.get(k)]
        percents = sorted({s["percent"] for table in slab_set.values() for s in table})
        slabs = []
        for pct in percents:
            ranges, bounds = {}, {}
            for kind, table in slab_set.items():
                hit = [s for s in table if s["percent"] == pct]
                if hit:
                    ranges[kind] = _range_text(kind, hit[0])       # text to show
                    bounds[kind] = [hit[0]["min"], hit[0]["max"]]  # numbers to match a score against
            slabs.append({"scholarship_percent": pct, "ranges": ranges, "bounds": bounds,
                          "payable_per_semester": round(prog["tuition_per_year"] * (100 - pct) / 200)})
        programs.append({
            "id": key, "name": prog["name"], "level": prog.get("level", "ug"),
            "tuition_per_year": prog["tuition_per_year"],
            "tuition_per_semester": round(prog["tuition_per_year"] / 2),
            "yearly_increase": prog["yearly_increase"],
            "duration_years": prog.get("duration_years"),
            "minimum_percent": prog["min_percent"],
            "eligibility": prog.get("eligibility_note", ""),
            "specialization_fee_per_year_from_year2": prog.get("specialization_fee_per_year_from_year2", 0),
            "exams": exams, "slabs": slabs,
        })
    return {
        "status": "ok", "academic_year": data["academic_year"], "source": data["source"],
        "one_time": data["one_time"], "yearly_other": data["yearly_other"],
        "transport_per_year": data.get("transport_per_year"),
        "hostel_per_year": data["hostel_per_year"], "hostel_labels": HOSTEL_LABELS,
        "hostel_deposits": data.get("hostel_deposits", {}),
        "special_concessions": data.get("special_concessions", []),
        "programs": programs,
    }
