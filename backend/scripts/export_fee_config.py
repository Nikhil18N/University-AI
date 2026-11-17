"""Write the calculator's bundled copy of the fee table.

    cd backend && python scripts/export_fee_config.py

The website's Fee & Scholarship Calculator loads its numbers from the backend
(/api/v1/agent/fee-config). So that it can draw instantly, even while the backend is
waking up, the same data is also bundled into the frontend as
frontend/src/data/feeConfig.json. That file is GENERATED from
backend/app/sru_agent/fees_2027_28.json by this script: never edit it by hand.
After changing a fee, run this script, then `pytest` (a test fails if you forget).
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.sru_agent import fees  # noqa: E402

TARGET = BACKEND.parent / "frontend" / "src" / "data" / "feeConfig.json"
# Answers from the backend calculation for many scores. The frontend check (npm run test:calc)
# recomputes each one in the browser code and must get exactly the same rupees.
CASES_TARGET = BACKEND.parent / "frontend" / "scripts" / "feeCases.json"

_SCORES = (
    {}, {"percent": 55}, {"percent": 62}, {"percent": 67.5}, {"percent": 75}, {"percent": 85},
    {"percent": 93, "board": "cbse"}, {"percent": 99},
    {"eapcet_rank": 1500}, {"eapcet_rank": 9000}, {"eapcet_rank": 45000},
    {"jee_percentile": 92.4}, {"ib_score": 36},
)


def render() -> str:
    return json.dumps(fees.fee_config(), ensure_ascii=False, indent=2) + "\n"


def render_cases() -> str:
    keep = ("scholarship_percent", "tuition_first_year", "tuition_first_year_after_scholarship",
            "per_semester_after_scholarship", "saving_first_year", "total_per_semester",
            "sem1_total_payable", "first_year_total_payable", "full_course_total")
    cases = []
    for program in fees.load_data()["programs"]:
        for i, score in enumerate(_SCORES):
            hostel = ("none", "non_ac_4", "ac_3")[i % 3]
            result = fees.calculate_fee(program, hostel=hostel, **score)
            if result.get("status") != "ok":
                continue
            cases.append({"program": program, "hostel": hostel, **score,
                          "expect": {k: result.get(k) for k in keep},
                          "years": [y["after_scholarship"] for y in result.get("year_by_year", [])]})
    return json.dumps(cases, ensure_ascii=False, indent=0) + "\n"


if __name__ == "__main__":
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding="utf-8")
    CASES_TARGET.parent.mkdir(parents=True, exist_ok=True)
    CASES_TARGET.write_text(render_cases(), encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(BACKEND.parent)} ({len(fees.fee_config()['programs'])} programs)")
    print(f"Wrote {CASES_TARGET.relative_to(BACKEND.parent)} ({len(json.loads(render_cases()))} checked answers)")
