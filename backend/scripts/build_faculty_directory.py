"""Turn a faculty list collected from https://sru.edu.in/faculty/ into the file the agent reads.

    python scripts/build_faculty_directory.py data/faculty_raw/sru_faculty_2026-11-17.json

Writes app/sru_agent/faculty_directory.json. Only what the university publishes on its faculty
pages is kept (no e-mail addresses or phone numbers). To refresh the list, collect it again with
scripts/fetch_faculty_directory.py (needs internet access to sru.edu.in) and run this script.
"""
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "sru_agent" / "faculty_directory.json"


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip(" ;,•")
    return re.sub(r"\s*;\s*", "; ", text)


def _qualification(raw: str, education: str) -> str:
    """'D.Sc. Programme • Astra School of Business Ph.D. from X' -> 'Ph.D. from X'."""
    found = re.findall(r"(Ph\.?\s?D\.?|PhD|M\.?\s?Tech|M\.?E\.?|M\.?Sc\.?|MBA|M\.?Phil)\s+from\s+([^•]+?)\s*$", raw or "")
    if found and found[-1][1].strip():
        degree, where = found[-1]
        degree = "Ph.D." if degree.replace(".", "").replace(" ", "").lower() == "phd" else degree
        return f"{degree} from {where.strip()}"
    first = _clean(education).split(";")[0]
    if not first or first.lower().startswith(("no ", "not ")):
        return ""
    return first[:120]


def build(raw_path: str) -> dict:
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    rows = [dict(zip(raw["fields"], r)) for r in raw["rows"]]
    people, seen = [], set()
    for r in rows:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        department = _clean(r["department"]) or ""
        school = _clean(r["school"])
        people.append({
            "name": _clean(r["name"]),
            "role": _clean(r["role"]),                 # e.g. "Head, Department of Physics"
            "designation": _clean(r["designation"]),
            "school": school,
            "department": department or school,
            "qualification": _qualification(r["qualification"], r["education"]),
            "experience_years": int(r["experience_years"]) if str(r["experience_years"]).isdigit() else None,
            "research_areas": _clean(r["research_areas"] or r["research"])[:300],
            "interests": _clean(r["interests"])[:200],
            "subjects": _clean(r["subjects"])[:200],
            "education": _clean(r["education"])[:260],
            "supervision": _clean(r["supervision"])[:120],
            "about": _clean(r["about"])[:450],
            "profile_url": r["url"],
        })
    return {"_README": "Built by scripts/build_faculty_directory.py from the official faculty pages. "
                       "Do not edit by hand; collect again and rebuild.",
            "source": raw.get("source", "https://sru.edu.in/faculty/"),
            "collected_on": (raw.get("collected_at") or "")[:10],
            "count": len(people), "faculty": people}


if __name__ == "__main__":
    data = build(sys.argv[1])
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{data['count']} faculty written to {OUT}")
