"""Build the fee and scholarship pages of the handbook from the fee file.

The handbook used to carry hand-typed fee facts that had drifted away from the official fee card
(wrong PG fees and slabs, special concessions that do not exist). These pages are now GENERATED
from backend/app/sru_agent/fees_2027_28.json, so the knowledge base, the chat and the calculator
all say the same thing. Run through `python scripts/export_fee_config.py`.
"""
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.sru_agent import fees  # noqa: E402

HANDBOOK_DIRS = [BACKEND / "data" / "handbook", BACKEND.parent / "data" / "handbook"]
FEE_PAGE = "08_admissions_fees_scholarships_and_eligibility.md"
FACTS_PAGE = "09_verified_sru_facts.md"
BEGIN, END = "<!-- FEES:BEGIN (generated from fees_2027_28.json, do not edit by hand) -->", "<!-- FEES:END -->"
_EXAMS = (("state_board", "Intermediate / State Board %"), ("cbse", "CBSE / ICSE %"),
          ("jee_percentile", "JEE Main percentile"), ("eapcet_rank", "TG / AP EAPCET rank"),
          ("ib", "IB Diploma score (out of 45)"))


def _rng(kind, slab):
    return fees._range_text(kind, slab)


def _slab_rows(data, set_name):
    slab_set = data["slab_sets"][set_name]
    percents = sorted({s["percent"] for table in slab_set.values() for s in table})
    rows = []
    for pct in percents:
        cells = []
        for kind, _label in _EXAMS:
            hit = [s for s in slab_set.get(kind, []) if s["percent"] == pct]
            cells.append(_rng(kind, hit[0]) if hit else "not applicable")
        rows.append((pct, cells))
    return percents, rows


def _program_table(data, level):
    programs = [(k, p) for k, p in data["programs"].items() if p.get("level", "ug") == level]
    percents = sorted({s["percent"] for t in data["slab_sets"][level].values() for s in t})
    head = ("| Program | Standard fee per year | " + " | ".join(f"With {p}% scholarship" for p in percents)
            + " | Increase every year (same for all students) | Duration |")
    lines = [head, "|---|---:|" + "---:|" * len(percents) + "---:|---|"]
    for _key, p in programs:
        fee = p["tuition_per_year"]
        cells = " | ".join(fees.inr(round(fee * (100 - pct) / 100)) for pct in percents)
        years = f"{p['duration_years']} years" if p.get("duration_years") else "ask Admissions"
        lines.append(f"| **{p['name']}** | **{fees.inr(fee)}** | {cells} | {fees.inr(p['yearly_increase'])} | {years} |")
    return "\n".join(lines)


def _slab_table(data, level):
    _percents, rows = _slab_rows(data, level)
    used = [(i, label) for i, (kind, label) in enumerate(_EXAMS) if data["slab_sets"][level].get(kind)]
    if level == "pg":
        used = [(0, "Qualifying degree %")]
    lines = ["| Scholarship on tuition | " + " | ".join(label for _i, label in used) + " |",
             "|---:|" + "---|" * len(used)]
    for pct, cells in rows:
        lines.append(f"| **{pct}%** | " + " | ".join(cells[i] for i, _l in used) + " |")
    return "\n".join(lines)


def _concessions(data):
    lines = ["| No. | Category | Concession per year |", "|---:|---|---:|"]
    for i, c in enumerate(data["special_concessions"], 1):
        lines.append(f"| {i} | {c['label']} | {fees.inr(c['amount'])} |")
    return "\n".join(lines)


def render_fee_page() -> str:
    d = fees.load_data()
    year, hostel, dep = d["academic_year"], d["hostel_per_year"], d["hostel_deposits"]
    other = d["yearly_other"]
    return f"""# SR University: Admissions, Fees & Scholarships ({year})

> **Source:** {d['source']} (two-page official fee card).
> **This page is generated** from `backend/app/sru_agent/fees_2027_28.json`. Do not edit it by hand:
> change the fee file and run `python scripts/export_fee_config.py`.
> **Currency:** Indian Rupees (₹). Tuition is per year; one semester is half of the yearly amount.

---

## 1. Undergraduate (UG) programs: tuition fee per year, {year}

The scholarship percentage is applied to the standard fee. The yearly increase is the same amount
for every student, with or without a scholarship.

{_program_table(d, 'ug')}

### Who gets which UG merit scholarship ({year})

Only ONE scholarship applies: the best one among the student's scores. Scholarships are not added together.
The standard fee (no scholarship) is for Intermediate 55 to 59.9% in B.Tech CSE and ECE, and 50 to 59.9% in other programs.

{_slab_table(d, 'ug')}

- An EAPCET rank above 20,000 does not earn a rank-based scholarship. The student's Intermediate, CBSE/ICSE, JEE or IB score may still earn one.
- {d.get('ib_overlap_note', '')}

---

## 2. Postgraduate (PG) programs: tuition fee per year, {year}

{_program_table(d, 'pg')}

### Who gets which PG merit scholarship ({year})

PG scholarships depend only on the percentage in the qualifying degree. The standard fee is for 50 to 59.9%.

{_slab_table(d, 'pg')}

---

## 3. Other fees and charges ({year})

| Fee | Amount | Notes |
|---|---:|---|
| Enrolment fee | {fees.inr(d['one_time']['enrollment_fee'])} | One-time, at admission |
| Other academic / university charges | {fees.inr(other['other_fee'])} | Every year |
| Examination fee (first year) | {fees.inr(other['exam_fee'])} | As printed on the fee card for the first year |
| Application form fee | {fees.inr(d['one_time']['application_fee'])} | Paid with the application |
| Transportation (university bus) | {fees.inr(d['transport_per_year'])} | Optional. Varies depending on distance; this is the amount printed on the fee card |
| Specialisation fee | ₹30,000 | Every year from the second year onwards, where a specialisation applies |
| Ph.D. fee | {fees.inr(d['phd_fee_per_year'])} | Per year |
| Electricity deposit, Non-AC hostel | {fees.inr(dep['electricity_deposit_non_ac'])} | Hostel students |
| Electricity deposit, AC hostel | {fees.inr(dep['electricity_deposit_ac'])} | Hostel students |

There is no separate "admission fee" on the {year} fee card.

---

## 4. Special category concessions (all courses, per year, {year})

The fee card lists exactly {len(d['special_concessions'])} categories. Each is subject to verification and approval of supporting documents.

{_concessions(d)}

- State-level sports is **not** on the list. Only national-level (₹15,000) and international-level (₹50,000) sports achievers are.
- There is no general concession for "all girl students": the two girl-student categories are "only girl child from Telangana" and "girl students from states other than Telangana".

### Administrative terms printed on the fee card
{chr(10).join('- ' + t for t in d['terms'])}

---

## 5. Hostel accommodation and dining (per year)

Hostel room fees are not printed on the {year} fee card. These amounts are from the university's hostel fee table (also shown on sru.edu.in) and include room and mess.

| Room type | Fee per year | Caution deposit (one-time, refundable) | Laundry per year | Electricity deposit |
|---|---:|---:|---:|---:|
| 4-sharing, Non-AC | {fees.inr(hostel['non_ac_4'])} | {fees.inr(dep['caution_deposit'])} | {fees.inr(dep['laundry_per_year'])} | {fees.inr(dep['electricity_deposit_non_ac'])} |
| 3-sharing, Non-AC | {fees.inr(hostel['non_ac_3'])} | {fees.inr(dep['caution_deposit'])} | {fees.inr(dep['laundry_per_year'])} | {fees.inr(dep['electricity_deposit_non_ac'])} |
| 4-sharing, AC | {fees.inr(hostel['ac_4'])} | {fees.inr(dep['caution_deposit'])} | {fees.inr(dep['laundry_per_year'])} | {fees.inr(dep['electricity_deposit_ac'])} |
| 3-sharing, AC | {fees.inr(hostel['ac_3'])} | {fees.inr(dep['caution_deposit'])} | {fees.inr(dep['laundry_per_year'])} | {fees.inr(dep['electricity_deposit_ac'])} |

- **Dining**: 4 meals a day (breakfast, lunch, evening snacks, dinner), vegetarian and non-vegetarian.
- **Facilities**: 24/7 Wi-Fi, 4,000-seat dining hall, study areas, ambulance on campus, power backup.
- Hostel is optional.

---

## 6. Rankings and accreditations printed on the {year} fee card

{chr(10).join(f"- **{r['body']}**: {r['claim']}." for r in d['rankings'])}

---

## 7. Official admissions contacts

- **Admissions Helpline**: 0870-2818333 / 0870-2818311
- **Direct Admissions Mobile**: +91 8331003030 / +91 8331004040
- **Email**: `admissions@sru.edu.in` / `info@sru.edu.in`
- **Application Portal**: [https://apply.sru.edu.in](https://apply.sru.edu.in)
- **Official Website**: [https://www.sru.edu.in](https://www.sru.edu.in)
- **Campus Address**: SR University, Ananthasagar, Hasanparthy, Warangal, Telangana 506371.

---

## 8. Not on the fee card (ask the Admissions Office)

The list of documents required at admission, the fee refund policy, payment dates and instalment
rules, and scholarship continuation rules are not printed on the {year} fee card. The agent must
say these are confirmed by the Admissions Office rather than state them.
"""


def render_facts_sections() -> str:
    """Sections 3 and 4 of the verified-facts page."""
    d = fees.load_data()
    year = d["academic_year"]
    ug = [(k, p) for k, p in d["programs"].items() if p.get("level", "ug") == "ug"]
    pg = [(k, p) for k, p in d["programs"].items() if p.get("level") == "pg"]
    line = lambda p: (f"  - **{p['name']}**: **{fees.inr(p['tuition_per_year'])} per year** "
                      f"({fees.inr(p['tuition_per_year'] / 2)} per semester); increases by "
                      f"{fees.inr(p['yearly_increase'])} every year for every student.")
    other = d["yearly_other"]
    groups = {}
    for c in d["special_concessions"]:
        groups.setdefault(c["amount"], []).append(c["label"])
    conc = "\n".join(f"    - **{fees.inr(a)} per year**: " + "; ".join(labels) + "."
                     for a, labels in sorted(groups.items(), reverse=True))
    slabs = lambda level: "\n".join(
        f"    - **{pct}% scholarship**: " + " | ".join(
            f"{label}: {cells[i]}" for i, (kind, label) in enumerate(_EXAMS)
            if d["slab_sets"][level].get(kind)) for pct, cells in _slab_rows(d, level)[1])
    return f"""{BEGIN}
## 3. Tuition Fee Structure ({year})

- **[FACT-ID: FEE-001] [STATUS: VERIFIED] [SOURCE: official {year} fee card, via fees_2027_28.json]**
  - **Scoping rule**: when asked about a fee, state only the fee for the program or item asked about.
  - **Undergraduate programs (tuition per year)**:
{chr(10).join(line(p) for _k, p in ug)}
  - **Postgraduate programs (tuition per year)**:
{chr(10).join(line(p) for _k, p in pg)}
  - **Other fees**: enrolment fee {fees.inr(d['one_time']['enrollment_fee'])} (one-time); other academic / university charges {fees.inr(other['other_fee'])} per year; examination fee (first year) {fees.inr(other['exam_fee'])}; application form fee {fees.inr(d['one_time']['application_fee'])}; transportation {fees.inr(d['transport_per_year'])} per year (varies with distance); specialisation fee ₹30,000 per year from the second year where applicable; Ph.D. fee {fees.inr(d['phd_fee_per_year'])} per year; hostel electricity deposit {fees.inr(d['hostel_deposits']['electricity_deposit_non_ac'])} (Non-AC) / {fees.inr(d['hostel_deposits']['electricity_deposit_ac'])} (AC).
  - There is no separate admission fee on the {year} fee card.

---

## 4. Merit Scholarships & Special Category Concessions ({year})

- **[FACT-ID: FEE-002] [STATUS: VERIFIED] [SOURCE: official {year} fee card, via fees_2027_28.json]**
  - Only the best single scholarship applies; scholarships are never added together. The scholarship is applied to the standard fee and is subject to marksheet verification.
  - **Undergraduate merit scholarship slabs**:
{slabs('ug')}
  - An EAPCET rank above 20,000 earns no rank-based scholarship (the student's board %, JEE or IB score may still earn one).
  - **Postgraduate merit scholarship slabs (percentage in the qualifying degree)**:
{chr(10).join(f"    - **{pct}% scholarship**: {cells[0]}" for pct, cells in _slab_rows(d, 'pg')[1])}
  - **{len(d['special_concessions'])} special category concessions (per year, all courses, subject to document verification)**:
{conc}
  - State-level sports is NOT on the list. There is no concession for "all girl students", North-East domicile, teachers' children, COVID-affected students or partner organisations: those are not on the fee card.
{END}"""


def write_all() -> list:
    """Write both handbook copies. Returns the paths written."""
    written = []
    for directory in HANDBOOK_DIRS:
        if not directory.is_dir():
            continue
        (directory / FEE_PAGE).write_text(render_fee_page(), encoding="utf-8")
        written.append(directory / FEE_PAGE)
        facts = directory / FACTS_PAGE
        if facts.exists():
            text = facts.read_text(encoding="utf-8")
            facts.write_text(replace_facts_sections(text), encoding="utf-8")
            written.append(facts)
    return written


def replace_facts_sections(text: str) -> str:
    block = render_facts_sections()
    if BEGIN in text:
        return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _m: block, text, flags=re.S)
    # first run: replace the old hand-typed sections 3 and 4
    start = text.index("## 3. Tuition Fee Structure")
    end = text.index("## 5. Campus Placements")
    return text[:start] + block + "\n\n---\n\n" + text[end:]
