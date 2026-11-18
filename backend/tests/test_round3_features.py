"""Round 3 (v3.0.0): the November 2026 admissions brief.

1 fee enquiries collect the missing details first; 2 follow-up chips match the question;
3 faculty profiles from sru.edu.in/faculty; 4-5 strengths and formatting rules in the prompt;
7 campus visits are never booked or confirmed. (6, the widget, is tested in the browser; 8, speed,
in test_round3_speed.py.)
"""
import json
import uuid

import pytest
from google.genai import types

from app.sru_agent import faculty, fee_intake, followups, memory, tools
from app.sru_agent.agent import run_agent
from app.sru_agent.prompt import build_system_prompt


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class Recorder:
    def __init__(self, script=None):
        self.script, self.requests, self.prompts = list(script or []), [], []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        self.prompts.append(config.system_instruction or "")
        return self.script.pop(0) if self.script else _text("OK.")


async def _run(message, session, client=None, conversation_id=None):
    events = [e async for e in run_agent(message, session, conversation_id, client=client or Recorder())]
    return events[-1]


# ------------------------------------------------------------------ 1. fees ----
def _walk(messages, profile=None):
    state, out = None, []
    for m in messages:
        r = fee_intake.decide(m, profile or {}, state)
        out.append(r)
        state = r.get("state") if r else None
    return out


def test_fee_question_without_a_course_asks_for_it():
    r = fee_intake.decide("what is the fee?", {}, None)
    assert r["action"] == "ask" and "Which programme" in r["text"] and "B.Tech CSE" in r["chips"]


def test_generic_btech_fee_lists_branches_then_asks():
    r = fee_intake.decide("btech fees", {}, None)
    assert r["action"] == "ask" and "depend on the branch" in r["text"] and "₹3,40,000" in r["text"]


def test_course_without_marks_gives_the_standard_fee_and_asks_everything_once():
    ask, calc = _walk(["cse fee", "State board 85%"])
    assert ask["action"] == "ask"
    for item in ("₹3,40,000 per year", "board", "JEE Main percentile or TG / AP EAPCET rank", "sru.edu.in/fee-scholarship"):
        assert item in ask["text"], item
    assert calc["action"] == "calculate"
    assert calc["args"] == {"program": "btech_cse", "percent": 85.0, "board": "state_board"}


def test_board_is_asked_only_when_it_changes_the_scholarship():
    # 96%: State Board 30%, CBSE 40% -> must ask
    r = fee_intake.decide("cse fees for 96%", {}, None)
    assert r["action"] == "ask" and "30% for Telangana / AP State Board and 40% for CBSE / ICSE" in r["text"]
    # 85%: 25% either way -> no board question (the entrance question comes instead)
    r = fee_intake.decide("cse fee with 85%", {}, None)
    assert "Which board" not in r["text"] and "JEE Main or TG / AP EAPCET" in r["text"]


def test_entrance_question_is_asked_once_and_no_means_no():
    ask, calc = _walk(["cse fee with 85%", "no entrance exam"])
    assert ask["action"] == "ask" and calc["action"] == "calculate"
    assert calc["args"] == {"program": "btech_cse", "percent": 85.0}
    ask, calc = _walk(["cse fee with 85%", "12000"])
    assert calc["args"]["eapcet_rank"] == 12000


def test_ib_student_is_asked_for_points():
    ask1, ask2, calc = _walk(["calculate my fee for ECE", "IB", "32"])
    assert "IB Diploma score" in ask2["text"] and calc["args"]["ib_score"] == 32


def test_only_a_rank_asks_for_board_marks_and_skip_works():
    ask, calc = _walk(["scholarship for 60k rank in cse", "Skip, use my rank"])
    assert "Intermediate / 12th marks" in ask["text"]
    assert calc["action"] == "calculate" and calc["args"] == {"program": "btech_cse", "eapcet_rank": 60000}


def test_pg_asks_for_degree_percentage_and_no_board():
    ask, calc = _walk(["MBA fee", "72"])
    assert "qualifying degree" in ask["text"] and "board" not in ask["text"].lower().split("degree")[0]
    assert calc["args"] == {"program": "mba", "percent": 72.0}


def test_known_details_are_not_asked_again():
    r = fee_intake.decide("what are the fees for cse", {"percent": 88, "board": "state_board",
                                                         "eapcet_rank": 30000}, None)
    assert r["action"] == "calculate"


def test_hostel_payment_and_concession_questions_are_left_to_other_tools():
    for q in ("what is the hostel fee?", "how do I pay the fee?", "sibling concession amount",
              "cse vs ece fee", "application fee"):
        assert fee_intake.decide(q, {}, None) is None, q


@pytest.mark.asyncio
async def test_fee_questions_are_asked_without_a_model_call_then_answered_in_one():
    sid = f"r3-fee-{uuid.uuid4()}"
    client = Recorder([_text("With 85% you get a 25% scholarship.")])
    done = await _run("calculate cse fee", sid, client, "conv-r3-fee")
    assert client.requests == [] and "JEE Main" in done["answer"]
    done = await _run("85% state board, no JEE", sid, client, "conv-r3-fee")
    assert len(client.requests) == 1
    assert "FEE CALCULATION ALREADY DONE" in client.prompts[0] and "sru.edu.in/fee-scholarship" in client.prompts[0]
    assert done["cards"][0]["type"] == "calculate_fee" and done["cards"][0]["data"]["scholarship_percent"] == 25


# ---------------------------------------------------------- 2. follow-ups ----
@pytest.mark.parametrize("message, tools_used, topic", [
    ("What are the library timings?", [], "campus"),          # was hostel chips ('timing')
    ("Is SRU NBA accredited?", [], "about"),                   # was attendance chips ('credit')
    ("cse fee with 85%", [{"name": "calculate_fee", "status": "ok"}], "fee_personal"),
    ("who is the head of cse", [{"name": "find_faculty", "status": "ok"}], "faculty"),
    ("I want to visit campus", [], "visit"),
    ("does sru have tie ups abroad", [], "international"),
])
def test_follow_up_topic_comes_from_the_question(message, tools_used, topic):
    assert followups.topic_of(message, tools_used) == topic


def test_follow_ups_do_not_repeat_the_question_and_use_the_course():
    chips = followups.suggest("cse fee with 85%", [{"name": "calculate_fee", "status": "ok"}],
                              {"program_interest": "cse"})
    assert "Special category concessions" in chips and "Eligibility for B.Tech CSE" in chips
    assert not any("fee breakdown" in c.lower() for c in chips)
    chips = followups.suggest("how is the food in hostel", [], {})
    assert "Mess and food" not in chips


def test_answer_text_no_longer_turns_chips_into_fee_chips():
    # the old service looked at the answer, which nearly always offers a fee calculation
    assert followups.topic_of("tell me about the sports facilities", []) == "campus"


# ------------------------------------------------------------- 3. faculty ----
def test_faculty_directory_is_loaded_from_the_official_pages():
    data = faculty._data()
    assert data["count"] == 340 and data["source"] == "https://sru.edu.in/faculty/"
    assert all(p["profile_url"].startswith("https://sru.edu.in/faculty/") for p in data["faculty"])
    assert not any("@" in str(v) for p in data["faculty"] for v in p.values())  # no e-mail addresses


@pytest.mark.parametrize("question, name", [
    ("Who is the head of the CSE department?", "Dr. Sandeep Ch"),
    ("who is the dean of engineering", "Dr. Md Mujahid Irfan"),
    ("HOD of ECE", "Dr. RAJ KUMAR K"),
    ("dean of business school", "Prof. Damarla Ramesh Babu"),
    ("Tell me about Dr Sheshikala", "Dr. Sheshikala M"),
    ("hod civil", "P Swamy Naga Ratna Giri"),
])
def test_faculty_leaders_and_people_are_found(question, name):
    assert faculty.is_faculty_question(question)
    r = faculty.search(question)
    assert r["status"] == "ok" and r["faculty"][0]["name"] == name


def test_faculty_by_topic_department_and_overview():
    r = faculty.search("who teaches VLSI in ECE")
    assert r["kind"] == "topic" and all(p["department"] == "Electronics & Communication Engineering" for p in r["faculty"])
    r = faculty.search("how many faculty in mechanical")
    assert r["kind"] == "department" and r["faculty_listed"] == 18
    r = faculty.search("tell me about the faculty at sru")
    assert r["kind"] == "overview" and r["faculty_listed"] == 340 and len(r["deans"]) == 5
    assert [p["name"] for p in faculty.search("who are the HODs")["faculty"]][:1] == ["Akhil Chowhan Korra"]


@pytest.mark.asyncio
async def test_faculty_question_is_answered_with_one_model_call_and_a_card():
    client = Recorder([_text("The Head of CSE & AI is Dr. Sandeep Ch.")])
    done = await _run("Who is the head of the CSE department?", f"r3-fac-{uuid.uuid4()}", client)
    assert len(client.requests) == 1 and "FACULTY PROFILES ALREADY FOUND" in client.prompts[0]
    assert "Dr. Sandeep Ch" in client.prompts[0]
    assert [c["type"] for c in done["cards"]][0] == "find_faculty"
    assert any("Faculty research areas" in s or "Heads of all departments" in s for s in done["suggestions"])


# ----------------------------------------------------- 4-5. prompt rules ----
def test_prompt_has_strengths_formatting_and_visit_rules_and_stays_small():
    text = build_system_prompt({})
    for phrase in ("WHY SRU", "7th among private universities", "first private university in Telangana and Andhra",
                   "FORMAT (shape follows content)", "short bullets", "1-2 short paragraphs",
                   "never book, schedule, approve or confirm", "never quote visiting hours", "find_faculty"):
        assert phrase in text, phrase
    assert "9:30 AM" not in text and "book_campus_visit" not in text
    assert len(text) < 9000


# --------------------------------------------------------------- 7. visits ----
@pytest.mark.asyncio
async def test_visit_guidance_never_books_and_gives_the_official_contacts():
    client = Recorder()
    done = await _run("I would like to visit the SR University campus. Whom should I contact?",
                      f"r3-visit-{uuid.uuid4()}", client)
    assert client.requests == []
    for item in ("can't book or confirm", "0870-2818333", "70750 10336", "info@sru.edu.in", "Hasanparthy"):
        assert item in done["answer"], item
    assert "Ask admissions to call me" in done["suggestions"]
    contact = next(c for c in done["cards"] if c["type"] == "get_contact_and_apply_links")
    assert contact["data"]["campus_visit"]["visit_page"] == "https://sru.edu.in/visit-us"


def test_only_the_callback_style_visit_tool_is_offered_to_the_model():
    assert "book_campus_visit" not in tools.TOOLS and "request_campus_visit_callback" in tools.TOOLS


# ------------------------------------------------- faculty refresh script ----
def test_faculty_refresh_script_parses_the_official_page_structure():
    pytest.importorskip("bs4")
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "fetch_faculty", Path(__file__).resolve().parents[1] / "scripts" / "fetch_faculty_directory.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    directory = """<h3>School of Engineering</h3>
      <div class="faculty-card"><a href="https://sru.edu.in/faculty/9-dr-a-b"><h5>Dr. A B</h5></a>
        <div>Professor, Head</div><div>Research Area</div><div>VLSI Design</div></div>"""
    cards = mod.parse_directory(directory)
    assert cards == [{"school": "School of Engineering", "name": "Dr. A B", "designation": "Professor, Head",
                      "research": "VLSI Design", "url": "https://sru.edu.in/faculty/9-dr-a-b"}]
    profile = """<div class="profile-header">Head, Department of Electronics &amp; Communication Engineering
        <h2>Dr. A B</h2> Professor • Department of Electronics &amp; Communication Engineering
        Ph.D. from NIT Warangal Years of Experience 15 Years <a href="mailto:a.b@sru.edu.in">a.b@sru.edu.in</a></div>
      <div id="about">I teach VLSI.<div class="about-faculty-right-meta"><h5>Research Areas</h5>
        <ul><li>VLSI</li><li>Low power design</li></ul></div></div>
      <div id="education"><ul><li>Ph.D. 2015 NIT Warangal</li></ul></div>
      <div id="subjects"><ul><li>→ Digital Design</li></ul></div>"""
    p = mod.parse_profile(profile, "Dr. A B")
    assert p["department"] == "Electronics & Communication Engineering"
    assert p["qualification"] == "Ph.D. from NIT Warangal" and p["experience_years"] == "15"
    assert p["role"] == "Head, Department of Electronics & Communication Engineering"
    assert p["research_areas"] == "VLSI; Low power design" and p["subjects"] == "Digital Design"
    assert "@" not in json.dumps(p)
