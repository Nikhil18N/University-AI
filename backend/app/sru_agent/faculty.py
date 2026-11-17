"""Faculty directory search (official profiles from https://sru.edu.in/faculty/).

The data file faculty_directory.json is built by scripts/build_faculty_directory.py. Search is
plain code (no AI call): by name, by role (dean, head of department), by department or school,
and by research topic or subject.
"""
import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

_FILE = Path(__file__).with_name("faculty_directory.json")
DIRECTORY_URL = "https://sru.edu.in/faculty/"

# Words students use -> the department or school names on the faculty pages.
_DEPARTMENTS = [
    (r"\b(?:cse|cs|computer\s*science|computers?|it|information\s*technology|ai\s*ml|aiml|ai|artificial\s*intelligence|"
     r"data\s*science|cyber\s*security|machine\s*learning|software)\b", "Computer Science & Artificial Intelligence"),
    (r"\b(?:ece|electronics(?:\s*and\s*communication)?|communication\s*engineering|vlsi)\b",
     "Electronics & Communication Engineering"),
    (r"\b(?:eee|electrical(?:\s*and\s*electronics)?)\b", "Electrical & Electronics Engineering"),
    (r"\b(?:mech|mechanical)\b", "Mechanical Engineering"),
    (r"\b(?:civil)\b", "Civil Engineering"),
    (r"\b(?:maths?|mathematics|statistics)\b", "Mathematics"),
    (r"\b(?:physics)\b", "Physics"),
    (r"\b(?:chemistry)\b", "Chemistry"),
    (r"\b(?:english|communication\s*skills)\b", "English"),
    (r"\b(?:biotech|biotechnology)\b", "Biotechnology"),
    (r"\b(?:mba|bba|b\.?com|business|management|commerce|astra)\b", "Astra School of Business"),
    (r"\b(?:agri|agriculture|agricultural|b\.?\s*sc\s*(?:\(?\s*hons\.?\s*\)?\s*)?ag\w*|horticulture)\b",
     "School of Agriculture"),
    (r"\b(?:engineering\s+school|school\s+of\s+engineering)\b", "School of Engineering"),
    (r"\b(?:sciences?\s*(?:and|&)\s*humanities)\b", "School of Sciences & Humanities"),
]
_FACULTY_WORDS = re.compile(
    r"\b(?:faculty|faculties|professors?|prof|lecturers?|teachers?|teaching\s+staff|staff|hod|h\.o\.d|"
    r"heads?\s+of\b|dean|deans|mentor|who\s+teach(?:es)?|research(?:ers?)?\s+(?:on|in)|"
    r"ph\.?\s?d\s+(?:holders?|faculty|guides?|supervisors?))\b", re.IGNORECASE)
_STOP = set("the a an of in on at for to and or is are who what which with about sru sr university faculty "
            "faculties professor professors teacher teachers teach teaches teaching staff department dept school "
            "me tell list show give any there do does have has their your our dr mr ms mrs please research "
            "researching doing work works working expert experts specialist specialists many how much best good "
            "senior name names head hod dean deans qualified qualification experience experienced areas area "
            "all list named called".split())
# Words that only name a department (not a research topic).
_UNIT_ONLY = set("cse cs it ece eee mech mechanical civil maths math mathematics physics chemistry english biotech "
                 "biotechnology mba bba bcom com business management commerce astra agri agriculture agricultural "
                 "computer computers science sciences electronics electrical communication engineering information "
                 "technology humanities btech tech".split())


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"faculty": [], "count": 0, "collected_on": ""}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).strip()


def _name_key(name: str) -> str:
    return " ".join(w for w in _norm(name).split() if w not in ("dr", "prof", "mr", "ms", "mrs"))


_TITLE_NAME = re.compile(r"\b(?:dr|prof|professor)\.?\s+[A-Za-z]{3,}|\bwho\s+heads?\b", re.IGNORECASE)


def is_faculty_question(message: str) -> bool:
    return bool(_FACULTY_WORDS.search(message or "") or _TITLE_NAME.search(message or ""))


def _units(text: str) -> list[str]:
    found = []
    for pattern, unit in _DEPARTMENTS:
        if re.search(pattern, text or "", re.IGNORECASE) and unit not in found:
            found.append(unit)
    return found


def _in_unit(person: dict, unit: str) -> bool:
    return unit in (person.get("department"), person.get("school"))


def _leads(person: dict, kind: str) -> bool:
    """Is this person a Dean / Head (not an Associate or Assistant Dean)? Uses the role line on the
    profile and the designation ('Professor, Dean, Astra School of Business')."""
    parts = [person.get("role") or ""] + (person.get("designation") or "").split(",")
    return any(re.match(rf"\s*{kind}\b", part, re.IGNORECASE) for part in parts)


def _topic_words(query: str) -> list[str]:
    return [w for w in _norm(query).split() if len(w) > 1 and w not in _STOP and w not in _UNIT_ONLY]


def _brief(p: dict, detail: bool = False) -> dict:
    out = {"name": p["name"], "position": p["role"] or p["designation"], "department": p["department"],
           "school": p["school"], "qualification": p["qualification"],
           "experience_years": p["experience_years"], "research_areas": p["research_areas"][:160],
           "profile_url": p["profile_url"]}
    if p["role"] and p["designation"] and p["designation"] not in p["role"]:
        out["designation"] = p["designation"]
    if detail:
        out.update({"subjects": p["subjects"], "education": p["education"], "supervision": p["supervision"],
                    "about": p["about"]})
    return {k: v for k, v in out.items() if v not in (None, "")}


def _by_name(query: str):
    """People whose name matches the query well (exact words, or a close spelling)."""
    q = _name_key(query)
    words = [w for w in q.split() if len(w) > 2 and w not in _STOP]
    if not words:
        return []
    scored = []
    for p in _data()["faculty"]:
        key = _name_key(p["name"])
        parts = key.split()
        hits = sum(1 for w in words if w in parts or any(
            difflib.SequenceMatcher(None, w, part).ratio() >= 0.84 for part in parts if len(part) > 2))
        if hits:
            scored.append((hits / max(len(parts), 1) + hits, p))
    scored.sort(key=lambda t: -t[0])
    if not scored:
        return []
    best = scored[0][0]
    return [p for s, p in scored if s >= best - 0.01][:5]


def _school_of(unit: str) -> str:
    """The school a department belongs to (from the directory itself)."""
    for p in _data()["faculty"]:
        if p["department"] == unit:
            return p["school"]
    return unit


def _by_topic(query: str, people: list, limit: int = 6):
    words = [w for w in _norm(query).split() if (len(w) > 2 or w in ("ai", "ml", "iot")) and w not in _STOP]
    if not words:
        return []
    scored = []
    for p in people:
        hay = " " + _norm(" ".join([p["research_areas"], p["interests"], p["subjects"]])) + " "
        score = sum(hay.count(f" {w}") for w in words)
        if len(words) > 1 and " ".join(words) in hay:
            score += 3  # the whole phrase ("machine learning"), not just one of its words
        if score:
            scored.append((score, p["experience_years"] or 0, p))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [p for _s, _e, p in scored[:limit]]


def search(query: str = "", department: str = "", role: str = "") -> dict:
    """Find faculty. Returns {"status": "ok", ...} with matching people, or "no_results"."""
    data = _data()
    people = data["faculty"]
    if not people:
        return {"status": "not_available", "note": f"The faculty list is not loaded. Point to {DIRECTORY_URL}."}
    text = " ".join(x for x in (query, department, role) if x)
    low = text.lower()
    base = {"source": DIRECTORY_URL, "as_of": data.get("collected_on"),
            "note": "From the official SRU faculty pages. Give the profile link for full details."}

    units = _units(department or query)
    if not units and re.search(r"\b(?:engineering|b\.?\s?tech)\b", department or query or "", re.IGNORECASE):
        units = ["School of Engineering"]
    wants_dean = bool(re.search(r"\bdeans?\b", role or low))
    wants_head = bool(re.search(r"\b(?:hods?|h\.o\.d|heads?)\b", role or low))

    # 1. Dean / head of a department or school
    if wants_dean or wants_head:
        leaders = [p for p in people if (wants_dean and _leads(p, "dean")) or (wants_head and _leads(p, "head"))]
        if units:
            # the Dean of a school leads every department in it
            leaders = [p for p in leaders if any(_in_unit(p, u) or u in p["role"] or u in p["designation"]
                                                 for u in units)
                       or (_leads(p, "dean") and any(_in_unit({"school": p["school"]}, u) or
                                                     _school_of(u) == p["school"] for u in units))]
        # Deans of a school (or Heads of a department) first; deans of a portfolio (Student Welfare,
        # Publications ...) only when no school / department leader matches.
        def _is_unit_leader(p):
            text = f"{p['role']}, {p['designation']}"
            return bool(re.search(r"\b(?:Dean|Head)\s*,\s*(?:School of|Astra|Department of)", text))
        primary = [p for p in leaders if _is_unit_leader(p)]
        portfolio_words = [w for w in _topic_words(query or "") if w not in ("hods", "heads")]
        portfolio = [p for p in leaders if not _is_unit_leader(p) and portfolio_words and
                     all(w in _norm(p["designation"]) for w in portfolio_words)]
        if portfolio and not units:
            primary = portfolio  # "dean of student welfare"
        if primary:
            leaders = primary
        if leaders:
            return {**base, "status": "ok", "kind": "leaders",
                    "faculty": [_brief(p, detail=len(leaders) == 1) for p in leaders[:12]]}

    # 2. A person by name
    named = _by_name(query) if query else []
    if named and not units:
        strong = [p for p in named if all(
            w in _name_key(p["name"]).split() for w in _name_key(query).split()
            if len(w) > 2 and w not in _STOP and not _units(w))]
        named = strong or named
        if len(named) <= 3:
            return {**base, "status": "ok", "kind": "person",
                    "faculty": [_brief(p, detail=True) for p in named]}

    # 3. A topic, optionally inside a department ("who teaches machine learning in CSE")
    pool = [p for p in people if any(_in_unit(p, u) for u in units)] if units else people
    topical = _by_topic(" ".join(_topic_words(query or "")), pool)
    if topical:
        return {**base, "status": "ok", "kind": "topic", "faculty": [_brief(p) for p in topical]}

    # 4. A whole department or school: numbers, leaders and a few senior names
    if units:
        unit = units[0]
        members = [p for p in people if _in_unit(p, unit)]
        if members:
            leaders = [p for p in members if p["role"]]
            senior = sorted([p for p in members if not p["role"]],
                            key=lambda p: (0 if p["designation"].startswith("Professor") else
                                           1 if p["designation"].startswith("Associate") else 2,
                                           -(p["experience_years"] or 0)))
            phd = sum(1 for p in members if p["qualification"].startswith("Ph.D."))
            return {**base, "status": "ok", "kind": "department", "department": unit,
                    "faculty_listed": len(members), "with_phd_listed": phd,
                    "professors": sum(1 for p in members if p["designation"].startswith("Professor")),
                    "associate_professors": sum(1 for p in members if p["designation"].startswith("Associate")),
                    "assistant_professors": sum(1 for p in members if p["designation"].startswith("Assistant")),
                    "leaders": [_brief(p) for p in leaders],
                    "some_senior_faculty": [_brief(p) for p in senior[:6]]}

    if named:
        return {**base, "status": "ok", "kind": "person", "faculty": [_brief(p) for p in named]}
    if not _topic_words(query or ""):
        return {**base, "status": "ok", "kind": "overview", **overview()}  # "tell me about the faculty"
    return {**base, "status": "no_results",
            "note": f"No matching faculty profile. Suggest the official directory {DIRECTORY_URL}."}


def overview() -> dict:
    """Numbers for 'tell me about the faculty' (all schools)."""
    people = _data()["faculty"]
    by_school: dict = {}
    for p in people:
        by_school[p["school"]] = by_school.get(p["school"], 0) + 1
    return {"faculty_listed": len(people), "by_school": by_school,
            "with_phd_listed": sum(1 for p in people if p["qualification"].startswith("Ph.D.")),
            "deans": [_brief(p) for p in people if re.search(r"\bDean\s*,\s*(?:School of|Astra)",
                                                              f"{p['role']}, {p['designation']}")],
            "source": DIRECTORY_URL, "as_of": _data().get("collected_on")}
