"""v4.17.1: people, titles and offices come from evidence, never from a similar name or a shared title word.

Reported: faculty.search returned the Director of the Centre for Experiential Learning for "Rupesh Mitra" and for
"Director of Admissions", because the role written after the name counted as name words and a weak partial match
was returned as the person. The university FAQ names the Senior Director of Admissions and Marketing, but it was
never indexed (Heading-3 questions) and the knowledge search stopped at a weak keyword hit.
"""
import asyncio

import pytest

from app.sru_agent import faculty, tools


def _names(r):
    return [p["name"] for p in r.get("faculty") or []]


@pytest.mark.parametrize("query", ["Director of Admissions", "Who is the director of admissions?",
                                   "admissions director", "Senior Director of Admissions and Marketing",
                                   "Director", "who is the registrar", "placement officer"])
def test_an_office_no_profile_holds_returns_no_person(query):
    r = faculty.search(query)
    assert r["status"] == "no_results" and r["kind"] == "role_not_in_directory" and not r.get("faculty")


def test_a_role_written_after_a_name_is_not_part_of_the_name():
    holder = next(p for p in faculty._data()["faculty"] if "(" in p["name"])
    role_words = holder["name"][holder["name"].index("(") + 1:].rstrip(")").split()
    assert faculty._name_key(holder["name"]).split() == faculty._name_key(holder["name"].split("(")[0]).split()
    r = faculty.search(role_words[0])                      # e.g. "Director" alone
    assert holder["name"] not in _names(r)


def test_a_similar_name_is_a_partial_match_not_the_person():
    r = faculty.search("Rupesh Mitra")
    assert r["match"] == "partial" and "mitra" in r["unmatched_name_words"]
    assert "not the same person" in r["note"].lower() or "different people" in r["note"].lower()


def test_exact_name_with_a_role_it_does_not_hold_is_flagged():
    r = faculty.search("Is Rupesh Mishra the director of admissions?")
    assert r["match"] == "exact" and r["role_check"] and not any(r["role_check"].values())


def test_the_holder_of_a_listed_office_is_found_by_the_office():
    holder = next(p for p in faculty._data()["faculty"] if "Centre for Experiential Learning" in p["designation"])
    r = faculty.search("director of centre for experiential learning")
    assert r["kind"] == "role_holder" and holder["name"] in _names(r)


def test_dean_of_a_portfolio_is_not_answered_with_school_deans():
    r = faculty.search("dean of students")
    school_deans = [p["name"] for p in faculty._data()["faculty"]
                    if p["role"].startswith("Dean, School of")]
    assert not set(_names(r)) & set(school_deans)


def test_school_and_department_leaders_still_work():
    assert faculty.search("head of CSE")["kind"] == "leaders"
    assert faculty.search("dean of cse")["kind"] == "leaders"
    assert faculty.search("who teaches machine learning")["kind"] == "topic"


def test_two_people_with_the_same_surname_are_flagged_as_ambiguous():
    surnames = {}
    for p in faculty._data()["faculty"]:
        last = faculty._name_key(p["name"]).split()[-1]
        surnames.setdefault(last, []).append(p["name"])
    last, people = next((k, v) for k, v in surnames.items() if len(v) in (2, 3) and len(k) > 3)
    r = faculty.search(last)
    assert len(r["faculty"]) >= 2 and r["match"] in ("exact", "ambiguous")
    assert "different people" in r.get("note", "") or "do not pick one" in r.get("note", "")


def test_close_spelling_counts_but_a_different_name_does_not():
    assert faculty.search("Seshikala")["match"] == "exact"                  # one letter missing
    assert "Dr. Randeep Singh" not in _names(faculty.search("Dr Sandeep Ch"))


def test_find_faculty_adds_approved_knowledge_when_the_directory_cannot_settle_it(monkeypatch):
    seen = []

    async def fake_search(q):
        seen.append(q)
        return [{"title": "University FAQ — Leadership",
                 "text": "Q: Who is the Senior Director of Admissions and Marketing?\nA: Dr. X Example."}]
    monkeypatch.setattr(tools, "_knowledge_search", fake_search)
    r = asyncio.run(tools.tool_find_faculty({"query": "Who is the Director of Admissions?"}, {}))
    assert r["kind"] == "role_not_in_directory" and r["approved_knowledge"][0]["title"].endswith("Leadership")
    assert seen == ["Who is the Director of Admissions?"]
    r = asyncio.run(tools.tool_find_faculty({"query": "head of CSE"}, {}))
    assert "approved_knowledge" not in r                                    # settled by the directory


def test_knowledge_search_merges_semantic_and_keyword_evidence():
    from app.main import _merge_evidence
    sem = [{"text": "Q: Who is the Senior Director of Admissions?", "retrieval": "semantic", "distance": 0.29},
           {"text": "Q: Who is the Registrar?", "retrieval": "semantic", "distance": 0.38}]
    lex = [{"text": "Sports & Recreation Facilities: cricket ground", "retrieval": "keyword"},
           {"text": "Q: Who is the Senior Director of Admissions?", "retrieval": "keyword"}]
    out = _merge_evidence(sem, lex)
    assert out[0]["distance"] == 0.29                                       # the strong semantic match first
    assert len(out) == 3                                                    # the same passage only once
    assert any(h["retrieval"] == "keyword" for h in out)                    # keyword evidence still included


def test_rerank_lets_the_question_words_decide_between_similar_faq_entries():
    from app.main import _rerank_by_question_words
    hits = [{"question": "Who is the Registrar of SR University?", "text": "The Registrar is Dr. A.", "distance": 0.212},
            {"question": "Who is the Vice Chancellor of SR University?", "text": "The VC is Prof. B.", "distance": 0.219},
            {"question": "Who is the Senior Director of Admissions and Marketing?",
             "text": "Admissions and marketing are led by Dr. C.", "distance": 0.24}]
    out = _rerank_by_question_words("admissions leadership SR University", hits)
    assert out[0]["question"].startswith("Who is the Senior Director of Admissions")


def test_rerank_brings_the_leadership_answer_up_for_who_leads_admissions():
    # distances measured on the index for "Who leads admissions at SRU?": general admissions FAQs sit just ahead
    from app.main import _rerank_by_question_words
    hits = [{"title": "University FAQ — Admissions", "text": "Section: Admission Q: How can I apply for admission?",
             "distance": 0.282},
            {"title": "University FAQ — Admissions", "text": "Section: Admission Q: Is the entrance exam mandatory?",
             "distance": 0.285},
            {"title": "University FAQ — Admissions", "text": "Section: Admission Q: What is the application fee?",
             "distance": 0.287},
            {"title": "University FAQ — Leadership", "text": "Section: Leadership Q: Who is the Senior Director of "
             "Admissions and Marketing? A: Admissions and marketing activities are led by Dr. C.", "distance": 0.293}]
    out = _rerank_by_question_words("Who leads admissions at SRU?", hits)
    assert out[0]["title"] == "University FAQ — Leadership"


# ---------------------------------------------- self-check: people and offices before they are shown ----
@pytest.mark.parametrize("text, kept", [
    ("Admissions and marketing are led by **Dr. Ram Raghotham Rao Deshmukh**, Senior Director of Admissions and "
     "Marketing.", True),
    ("Dr. Rupesh Mishra serves as the **Director of Centre for Experiential Learning**.", True),
    ("No, Dr. Rupesh Mishra is not the Director of Admissions; that is Dr. Ram Raghotham Rao Deshmukh.", True),
    ("SR Innovation Exchange is headed by Col. B. S. Rao, CEO of SRiX.", True),
    ("Yes, Dr. Rupesh Mitra is the Director of Admissions.", False),           # nobody by that name
    ("Dr. Rupesh Mishra is the Director of Admissions at SRU.", False),        # a role no source pairs him with
    ("- **Registrar:** Dr. Invented Person Example", False),
])
def test_people_and_offices_are_checked_against_evidence(text, kept):
    from app.sru_agent.answer_check import check_people, _UNVERIFIED_LINE
    out, problems = check_people(text)
    assert (out == text and not problems) if kept else (_UNVERIFIED_LINE in out and problems)


def test_this_turns_tool_results_count_as_evidence():
    from app.sru_agent.answer_check import check_people
    out, problems = check_people("The new hostel coordinator is Dr. Zed Quorvak.",
                                 evidence=[{"tool": "search_university_info",
                                            "result": {"passages": [{"text": "Hostel coordinator: Dr. Zed Quorvak"}]}}])
    assert not problems


# ------------------------------------------------------------------------- sources that support the answer ----
def test_sources_are_the_evidence_that_supports_the_answer():
    from app.sru_agent.agent import _answer_sources
    evidence = [{"tool": "search_university_info", "result": {"passages": [
        {"title": "University FAQ — Leadership", "text": "Q: Who is the Senior Director of Admissions and Marketing?\n"
         "A: Admissions and marketing activities are led by Dr. Ram Raghotham Rao Deshmukh.",
         "source": {"document_id": "d-1", "section": "Leadership", "page_url": "https://sru.edu.in/about"}},
        {"title": "Sports & Recreation Facilities", "text": "Cricket ground, football ground, basketball court.",
         "source": {"document_id": "d-2"}}]}}]
    answer = ("Admissions and marketing at SR University are led by Dr. Ram Raghotham Rao Deshmukh, Senior "
              "Director of Admissions and Marketing.")
    got = _answer_sources(answer, evidence)
    assert [s["document_id"] for s in got] == ["d-1"]                   # the unrelated passage is not cited
    assert got[0]["page_url"] == "https://sru.edu.in/about" and got[0]["section"] == "Leadership"


def test_no_source_and_no_made_up_link_without_evidence():
    from app.sru_agent.agent import _answer_sources
    assert _answer_sources("SR University is a great place to study engineering.", []) == []
    got = _answer_sources("Dr. Example Person teaches machine learning.",
                          [{"tool": "find_faculty", "result": {"faculty": [{"name": "Dr. Example Person",
                                                                           "research_areas": "machine learning"}]}}])
    assert got and "page_url" not in got[0]                             # no profile link in the data: none


def test_done_event_carries_sources():
    from app.sru_agent.agent import _done
    ev = _done("c-1", "answer", sources=[{"document_id": "d-1", "title": "T"}])
    assert ev["sources"] == [{"document_id": "d-1", "title": "T"}]


def test_a_follow_up_keeps_the_previous_answers_read_only_tools():
    from app.sru_agent import tools
    plain = tools.select_tools_for_message("Are you sure? Please verify that again.", {}, {})
    assert "find_faculty" not in plain
    st = {"last_tools": ["find_faculty", "request_counsellor_callback"]}
    follow_up = tools.select_tools_for_message("Are you sure? Please verify that again.", st, {})
    assert "find_faculty" in follow_up                      # the same evidence can be checked again
    assert "request_counsellor_callback" not in follow_up   # an action is never carried over

