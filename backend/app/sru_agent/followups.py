"""Follow-up suggestion chips for the agent: about what the student just asked, not generic.

The topic comes first from the tool that answered (a fee calculation, a faculty search ...), then
from whole words in the student's message. The answer text is NOT used to pick the topic: most
answers end with an offer such as "shall I calculate your fee?", which used to turn every chip
row into fee chips. Every chip is a question SRU Buddy can answer, and a chip that repeats what
the student just asked is dropped.
"""
import re

from . import fees

# (topic, pattern on the student's message), checked in order; the first match wins.
_TOPICS = [
    ("visit", r"\b(?:visit|visiting|campus\s+tour|come\s+to\s+(?:the\s+)?campus)\b"),
    ("faculty", r"\b(?:faculty|faculties|professors?|lecturers?|teachers?|hod|dean|deans|head\s+of)\b"),
    ("concessions", r"\b(?:concessions?|sibling|defen[cs]e|single\s+parent|orphan|sports\s+quota|girl\s+child|"
                    r"special\s+category)\b"),
    ("transport", r"\b(?:bus|buses|transport|transportation|commute|route|routes)\b"),
    ("hostel", r"\b(?:hostels?|mess|warden|curfew|in-?time|room\s+(?:type|sharing)|ac\s+room|non-?ac)\b"),
    ("compare", r"\b(?:vs|versus|compare|comparison|difference\s+between|better\s+than)\b"),
    ("scholarship", r"\b(?:scholarships?|waiver|merit)\b"),
    ("fee", r"\b(?:fee|fees|fess|tuition|cost|how\s+much|per\s+sem\w*)\b"),
    ("eligibility", r"\b(?:eligib\w*|cut-?off|minimum\s+marks|can\s+i\s+(?:join|get|apply))\b"),
    ("apply", r"\b(?:apply|application|admission\s+process|how\s+to\s+join|last\s+date|deadline|counselling)\b"),
    ("documents", r"\b(?:documents?|certificates?|tc|marksheet)\b"),
    ("placements", r"\b(?:placements?|package|lpa|ctc|recruiters?|jobs?|internships?|salary|career)\b"),
    ("international", r"\b(?:international|abroad|foreign|2\s*\+\s*2|exchange|overseas)\b"),
    ("research", r"\b(?:research|patents?|startups?|srix|nest|incubat\w*|innovation)\b"),
    ("academics", r"\b(?:attendance|detention|exams?|grading|cgpa|gpa|credits?|minors?|honou?rs|syllabus|"
                  r"curriculum|subjects?)\b"),
    ("about", r"\b(?:rank|ranking|rankings|nirf|naac|nba|accredit\w*|ugc|why\s+sru|why\s+choose|about\s+sru|"
              r"reputation|good\s+university|is\s+sru\s+good|recogni[sz]ed|valid)\b"),
    ("campus", r"\b(?:campus|library|labs?|sports|gym|wifi|facilities|infrastructure|canteen)\b"),
    ("programs", r"\b(?:courses?|programmes?|programs?|branches?|speciali[sz]ations?|b\.?\s?tech|mba|bba|b\.?des|"
                 r"agriculture)\b"),
]
_TOOL_TOPIC = {"calculate_fee": "fee_personal", "share_fee_estimate": "fee_personal",
               "check_eligibility": "eligibility", "get_program_info": "programs", "compare_programs": "compare",
               "get_special_concessions": "concessions", "find_faculty": "faculty",
               "request_counsellor_callback": "after_request", "request_campus_visit_callback": "after_request",
               "get_university_videos": "campus"}


def _short_program(profile: dict) -> str | None:
    key = fees.find_program(str((profile or {}).get("program_interest") or ""))
    if not key:
        return None
    return fees.load_data()["programs"][key]["name"].split(" (")[0]


def _short_dept(name: str) -> str:
    return (name.replace("Computer Science & Artificial Intelligence", "CSE & AI")
            .replace("Electronics & Communication Engineering", "ECE")
            .replace("Electrical & Electronics Engineering", "EEE").replace(" Engineering", "")
            .replace("Astra School of Business", "the business school").replace("School of ", ""))


def _chips(topic: str, program: str | None, department: str | None) -> list[str]:
    p = program or "B.Tech CSE"
    mine = program or "my course"
    table = {
        "fee_personal": ["Special category concessions", f"Add hostel to my {mine} fee",
                         f"Eligibility for {p}", "How do I apply for 2027-28?", "How is the fee paid each semester?"],
        "fee": ["Scholarship for my marks", "Special category concessions", "Hostel fees", "How do I apply for 2027-28?"],
        "scholarship": ["Scholarship for my marks", "Special category concessions",
                        "Do I keep my scholarship every year?", f"{p} fee after scholarship"],
        "concessions": ["Calculate my fee with scholarship", "Documents for a concession", "How do I apply for 2027-28?",
                        "Talk to a counsellor"],
        "eligibility": [f"{p} fee with my marks", "How do I apply for 2027-28?", "Documents needed for admission",
                        f"Placements for {p}"],
        "programs": [f"{p} fee and scholarship", f"Eligibility for {p}", "Who are the faculty?", f"Placements for {p}"],
        "compare": ["Scholarship for my marks", "Placement record by branch", "Faculty in each department",
                    "How do I apply for 2027-28?"],
        "faculty": ([f"Faculty research areas in {_short_dept(department)}", f"Placements for {p}",
                     "Heads of all departments",
                     "Deans of all schools"] if department else
                    ["Heads of all departments", "Deans of all schools", "Faculty working on AI",
                     "Research centres at SRU"]),
        "placements": ["Top recruiters", "Placement training and internships", f"{p} fee and scholarship",
                       "Why choose SRU?"],
        "hostel": ["Hostel fee (AC / Non-AC)", "Hostel in-time rules", "Mess and food", "Hostel safety and wardens"],
        "transport": ["Bus routes and stops", "Transport fee", "Hostel options", "How to reach the campus"],
        "visit": ["Ask admissions to call me", "How to reach the campus", "Hostel details", "Why choose SRU?"],
        "apply": ["Documents needed for admission", "Application fee", "Scholarship for my marks", "Talk to a counsellor"],
        "documents": ["How do I apply for 2027-28?", "Scholarship for my marks", "Talk to a counsellor"],
        "about": ["Placement record", "Faculty and research", "International partnerships", "Scholarship for my marks"],
        "international": ["2+2 study abroad programme", "Scholarships for international students", "Placement record",
                          "How do I apply for 2027-28?"],
        "research": ["SRiX startup incubator", "Research centres at SRU", "Faculty research areas", "Placement record"],
        "academics": ["Attendance rule", "Exams and grading", "Minors and honours", "Placement record"],
        "campus": ["Watch a campus tour video", "Labs and research centres", "Sports facilities", "Hostel details"],
        "after_request": ["Scholarship for my marks", "Documents needed for admission", "How to reach the campus",
                          "Hostel details"],
        "default": ["Fee and scholarship for my marks", "Placement record", "Why choose SRU?", "Plan a campus visit"],
    }
    return table.get(topic, table["default"])


_STOP = set("the a an of for to and or my is are what how do i me in on at with about sru".split())


def _overlaps(chip: str, message: str) -> bool:
    """Would this chip just repeat the student's own question?"""
    words = [w for w in re.findall(r"[a-z0-9+]+", chip.lower()) if w not in _STOP and len(w) > 2]
    if not words:
        return False
    msg = set(re.findall(r"[a-z0-9+]+", message.lower()))
    return sum(1 for w in words if w in msg) / len(words) >= 0.5


def topic_of(message: str, tools_used: list | None = None) -> str:
    for t in tools_used or []:
        name = t.get("name") if isinstance(t, dict) else t
        if name in _TOOL_TOPIC and (not isinstance(t, dict) or t.get("status") in ("ok", "saved", "calculated")):
            return _TOOL_TOPIC[name]
    for topic, pattern in _TOPICS:
        if re.search(pattern, message or "", re.IGNORECASE):
            return topic
    return "default"


def suggest(message: str, tools_used: list | None = None, profile: dict | None = None,
            department: str | None = None, limit: int = 4) -> list[str]:
    topic = topic_of(message, tools_used)
    if topic == "hostel" and re.search(r"\b(?:fee|fees|cost|how\s+much)\b", message or "", re.IGNORECASE):
        chips = ["Add hostel to my fee", "Hostel in-time rules", "Mess and food", "Hostel safety and wardens"]
    else:
        chips = _chips(topic, _short_program(profile or {}), department)
    picked = [c for c in chips if not _overlaps(c, message or "")]
    return (picked if len(picked) >= 2 else chips)[:limit]
