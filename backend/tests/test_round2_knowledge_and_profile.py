"""Second audit round (17 Nov 2026): knowledge base accuracy, Gemini usage, profile / settings sync.

Problems these tests pin down:
  * the handbook carried fee facts and concession categories that are not on the official fee card
  * the agent's knowledge depended on Gemini embedding calls (empty after a cold start / quota end)
  * "what will I get on my EAMCET rank?" was answered from the Intermediate marks instead
  * a new mobile number given in the chat never reached Settings > My details
  * every greeting and every repeated first question cost a model call
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.genai import types

from app.sru_agent import agent, config, fees, intents, knowledge, memory, tools
from app.sru_agent.agent import run_agent
from app.sru_agent.router import router

BACKEND = Path(__file__).resolve().parent.parent


def _text(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role="model", parts=[types.Part.from_text(text=text)]))])


class Recorder:
    """A fake model that records what it was sent."""

    def __init__(self, script=()):
        self.script, self.requests, self.prompts = list(script), [], []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config):
        self.requests.append(list(contents))
        self.prompts.append(config.system_instruction)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _run(message, session, client=None, conversation_id=None):
    events = [e async for e in run_agent(message, session, conversation_id, client=client or Recorder())]
    return events[-1]


class _ApiError(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code = code


# ------------------------------------------------------------- fee card accuracy ----
def test_fee_file_matches_the_fee_card_pdf():
    d = fees.load_data()
    assert len(d["special_concessions"]) == 19                      # the PDF lists exactly 19
    labels = " ".join(c["label"].lower() for c in d["special_concessions"])
    for invented in ("recommendation", "north east", "covid", "teachers", "partner"):
        assert invented not in labels
    assert {c["amount"] for c in d["special_concessions"]} == {50000, 20000, 15000}
    assert d["hostel_deposits"]["electricity_deposit_ac"] == 10000
    assert d["hostel_deposits"]["electricity_deposit_non_ac"] == 5000
    assert d["programs"]["btech_cse"]["name"].endswith("Robotics and Automation, Quantum AI)")
    # PG slabs on the card: 10/15/20/25/30/40 at 60/65/70/80/92/98
    assert [fees.calculate_fee("mba", percent=p)["scholarship_percent"] for p in (59, 60, 65, 70, 80, 92, 98)] == [
        0, 10, 15, 20, 25, 30, 40]
    assert fees.calculate_fee("mtech")["tuition_first_year"] == "₹1,00,000"
    assert any("NIRF" in r["body"] and "91st" in r["claim"] for r in fees.rankings()["rankings"])


def test_each_score_is_reported_by_itself():
    """Transcript, 17 Nov: rank 40,000 was answered with 'scholarships are based on Inter % not rank'."""
    fee = fees.calculate_fee("cse", percent=85, eapcet_rank=40000)
    assert fee["scholarship_percent"] == 25 and fee["scholarship_basis_text"] == "Intermediate 85%"
    rank = next(s for s in fee["scores_considered"] if s["score"] == "EAPCET rank 40,000")
    assert rank["scholarship_percent"] == 0 and "1 to 20,000" in rank["note"]
    from app.sru_agent.prompt import build_system_prompt
    assert "scores_considered" in build_system_prompt({}) and "only one kind of score" in build_system_prompt({})


def test_ib_overlap_is_flagged_not_guessed():
    fee = fees.calculate_fee("cse", ib_score=36)
    assert fee["scholarship_percent"] == 30 and any("overlap" in n for n in fee["notes"])


# ------------------------------------------------------------------ handbook ----
def test_handbook_fee_pages_are_generated_from_the_fee_file():
    import importlib.util
    spec = importlib.util.spec_from_file_location("handbook_from_fees", BACKEND / "scripts" / "handbook_from_fees.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for directory in mod.HANDBOOK_DIRS:
        if not directory.is_dir():
            continue
        assert (directory / mod.FEE_PAGE).read_text(encoding="utf-8") == mod.render_fee_page(), (
            "run `python scripts/export_fee_config.py`")
        facts = (directory / mod.FACTS_PAGE).read_text(encoding="utf-8")
        assert mod.render_facts_sections() in facts, "run `python scripts/export_fee_config.py`"
        for invented in ("North East Domicile", "COVID Affected", "Girl Child (All female students)",
                         "M.Tech**: **₹1,50,000", "20 Special Category"):
            assert invented not in facts


def test_both_handbook_copies_are_identical():
    a, b = BACKEND / "data" / "handbook", BACKEND.parent / "data" / "handbook"
    if not b.is_dir():
        pytest.skip("single handbook copy")
    names = sorted(p.name for p in a.glob("*.md"))
    assert names == sorted(p.name for p in b.glob("*.md"))
    for name in names:
        assert (a / name).read_bytes() == (b / name).read_bytes(), f"{name} differs between data/ and backend/data/"


@pytest.mark.parametrize("question, must_contain", [
    ("hostel curfew for first years", "In-Time"),
    ("who is the vice chancellor", "Deepak Garg"),
    ("owner of sr university", "Varada Reddy"),
    ("special concession for sibling", "Sibling"),
    ("is ragging there", "Ragging"),
    ("nirf ranking", "91st"),
    ("mtech fee", "M.Tech"),
    ("how to apply for admission", "Register"),
    ("hostel lo food ela untundi", "Dining"),
])
def test_handbook_search_needs_no_ai_call(question, must_contain):
    found = knowledge.search(question, k=3)
    assert found, question
    assert any(must_contain.lower() in (f["title"] + f["text"]).lower() for f in found), question


def test_handbook_search_ignores_chit_chat():
    assert knowledge.search("how are you bro") == []
    assert knowledge.size() > 100


# ----------------------------------------------------------- fewer model calls ----
@pytest.mark.asyncio
async def test_greetings_and_thanks_use_no_model_call():
    for text, expected in (("hi sru_buddy", "Hello"), ("how are you bro", "doing well"), ("thanks", "welcome"),
                           ("who are you?", "AI admissions assistant")):
        client = Recorder()
        done = await _run(text, "r2-smalltalk", client)
        assert client.requests == [] and expected in done["answer"], text
    assert intents.small_talk("hi, what is the cse fee?") is None


@pytest.mark.asyncio
async def test_plain_fee_question_takes_one_model_call():
    client = Recorder([_text("With 85% you get a 25% scholarship: tuition is ₹2,55,000 for 2027-28.")])
    done = await _run("cse fee with 85% in inter, state board, no entrance exam", "r2-onecall", client)
    assert len(client.requests) == 1                               # was 2 or 3
    assert "FEE CALCULATION ALREADY DONE" in client.prompts[0] and "₹2,55,000" in client.prompts[0]
    assert done["tools_used"] == [{"name": "calculate_fee", "status": "ok", "is_action": False}]
    assert [c["type"] for c in done["cards"]][0] == "calculate_fee"
    assert done["cards"][0]["data"]["scholarship_percent"] == 25


@pytest.mark.asyncio
async def test_typed_eamcet_rank_reaches_the_calculation():
    client = Recorder([_text("On your EAPCET rank alone there is no scholarship; your 85% gives 25%.")])
    await memory.update_profile("r2-rank", percent=85, program_interest="btech_cse")
    done = await _run("in emact i got 40000 rank what will be the scholorship", "r2-rank", client)
    sent = client.prompts[0]
    assert "EAPCET rank 40,000" in sent and "1 to 20,000" in sent and "Intermediate 85%" in sent
    assert done["cards"][0]["data"]["scholarship_percent"] == 25


@pytest.mark.asyncio
async def test_handbook_passages_are_given_to_the_model_up_front():
    client = Recorder([_text("First-year students must be in by 8:30 PM.")])
    await _run("what is the hostel in-time for first year students?", "r2-context", client)
    assert len(client.requests) == 1
    assert "HANDBOOK PASSAGES ALREADY FOUND" in client.prompts[0] and "In-Time" in client.prompts[0]


@pytest.mark.asyncio
async def test_repeated_first_question_is_answered_from_the_saved_copy(monkeypatch):
    calls = []

    class Counting(Recorder):
        async def generate_content(self, model, contents, config):
            calls.append(1)
            return _text("SR University is in Warangal, Telangana.")

    ring = agent._KeyRing()
    monkeypatch.setattr(config, "GEMINI_API_KEYS", ["key-A"])
    monkeypatch.setattr(ring, "client", lambda key: Counting())
    monkeypatch.setattr(agent, "_ring", ring)
    answers = []
    for sid in ("r2-cache-1", "r2-cache-2", "r2-cache-3"):
        events = [e async for e in run_agent("Where is SR University located?", sid)]
        answers.append(events[-1]["answer"])
    assert len(calls) == 1 and len(set(answers)) == 1
    # a student we already know something about gets a fresh, personal answer
    await memory.update_profile("r2-cache-4", name="Ravi")
    [e async for e in run_agent("Where is SR University located?", "r2-cache-4")]
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_daily_limit_is_not_retried_and_gets_a_useful_reply(monkeypatch):
    slept = []

    async def no_sleep(seconds):
        slept.append(seconds)

    class DailyLimit(Recorder):
        async def generate_content(self, model, contents, config):
            raise _ApiError(429, "429 RESOURCE_EXHAUSTED: GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    ring = agent._KeyRing()
    monkeypatch.setattr(config, "GEMINI_API_KEYS", ["key-A"])
    monkeypatch.setattr(config, "AGENT_ANSWER_CACHE_SECONDS", 0)
    monkeypatch.setattr(ring, "client", lambda key: DailyLimit())
    monkeypatch.setattr(agent, "_ring", ring)
    monkeypatch.setattr(agent.asyncio, "sleep", no_sleep)
    events = [e async for e in run_agent("tell me about the anti ragging rules", "r2-daily")]
    assert events[-1]["type"] == "done" and "handbook" in events[-1]["answer"]
    assert slept == []                                             # no pointless waiting on a per-day limit
    assert ring.all_resting()
    # the next student is answered at once, without even trying the exhausted key
    events = [e async for e in run_agent("zzz qqq", "r2-daily-2")]
    assert events[-1]["type"] == "done" and "free AI limit" in events[-1]["answer"]


# ------------------------------------------------- profile, number, Settings ----
@pytest.fixture
def lead_store():
    store = {"saved": [], "updated": []}

    async def saver(lead):
        store["saved"].append(lead)
        return {"id": f"lead{len(store['saved']):04d}-aaaa"}

    async def updater(lead_id, name=None, phone=None):
        store["updated"].append((lead_id, name, phone))
        return True

    tools.set_lead_saver(saver)
    tools.set_lead_updater(updater)
    yield store
    tools.set_lead_saver(None)
    tools.set_lead_updater(None)


@pytest.mark.asyncio
async def test_new_number_in_chat_updates_profile_and_saved_request(lead_store):
    sid = "r2-number"
    await _run("please call me, I am Dinesh Kumar 7075545685", sid)
    assert (await memory.get_profile(sid))["phone"] == "7075545685"

    client = Recorder()
    done = await _run("change my number to 9876501234", sid, client)
    assert client.requests == []
    assert done["tools_used"][0] == {"name": "update_contact_details", "status": "updated", "is_action": True}
    assert "ending 1234" in done["answer"] and "lead0001" in done["answer"]
    assert lead_store["updated"] == [("lead0001-aaaa", None, "9876501234")]
    profile = await memory.get_profile(sid)
    assert profile["phone"] == "9876501234" and memory.public_profile(profile)["name"] == "Dinesh Kumar"


@pytest.mark.asyncio
async def test_update_request_without_a_number_asks_for_it(lead_store):
    sid = "r2-number-ask"
    done = await _run("update it in the settings", sid)
    assert "new 10-digit mobile number" in done["answer"] and "My details" in done["answer"]
    done = await _run("9812345678", sid)
    assert done["tools_used"][0]["status"] == "updated" and (await memory.get_profile(sid))["phone"] == "9812345678"


@pytest.mark.asyncio
async def test_stated_number_is_remembered(lead_store):
    client = Recorder([_text("Thanks! May I know your name and the course you are interested in?")])
    await _run("my mobile number is 7075545685", "r2-stated", client)
    assert (await memory.get_profile("r2-stated"))["phone"] == "7075545685"
    assert "phone=7075545685" in client.prompts[0]              # so "what is my number?" can be answered


def test_profile_api_for_the_settings_panel(lead_store):
    app = FastAPI()
    app.include_router(router)
    api = TestClient(app)
    sid = "r2-settings-session"
    assert api.get("/api/v1/agent/profile", params={"session_id": sid}).json()["profile"] == {}
    saved = api.put("/api/v1/agent/profile", json={"session_id": sid, "name": "Sita Devi", "phone": "+91 98765 00011"})
    assert saved.status_code == 200 and saved.json()["profile"] == {"name": "Sita Devi", "phone": "9876500011"}
    assert api.get("/api/v1/agent/profile", params={"session_id": sid}).json()["profile"]["phone"] == "9876500011"
    assert api.put("/api/v1/agent/profile", json={"session_id": sid, "phone": "12345"}).status_code == 422
    assert api.delete("/api/v1/agent/profile", params={"session_id": sid}).json()["profile"] == {}
    assert api.get("/api/v1/agent/profile", params={"session_id": sid}).json()["profile"] == {}


@pytest.mark.asyncio
async def test_profile_and_history_come_back_from_lasting_storage():
    db = {"profile": {"lasting-1": {"name": "Asha", "phone": "9000011111", "percent": 91}}, "saved": []}

    async def load(session_id):
        return db["profile"].get(session_id, {})

    async def save(session_id, profile):
        db["saved"].append((session_id, dict(profile)))

    async def history(session_id, conversation_id):
        return [{"role": "user", "text": "what is the cse fee"}, {"role": "model", "text": "It is ₹3,40,000."}]

    memory.set_profile_store(load, save)
    memory.set_history_loader(history)
    try:
        assert (await memory.get_profile("lasting-1"))["name"] == "Asha"       # not in the cache: read back
        await memory.update_profile("lasting-1", city="Warangal")
        await memory.flush()  # the database copy is written in the background
        assert db["saved"][-1][1]["city"] == "Warangal"
        client = Recorder([_text("Yes, hostel is extra.")])
        await _run("and with hostel?", "lasting-1", client, conversation_id="conv-lasting")
        assert [c.parts[0].text for c in client.requests[0]][:2] == ["what is the cse fee", "It is ₹3,40,000."]
    finally:
        memory.set_profile_store(None, None)
        memory.set_history_loader(None)


def test_number_intents():
    for text in ("change my number", "my new number is 9876543210", "update it in the settings",
                 "my phone number is wrong", "please correct my mobile"):
        assert intents.is_number_update(text), text
    for text in ("what is my mobile number", "call me on 9876543210", "hostel room number"):
        assert not intents.is_number_update(text), text
    assert intents.is_number_statement("my mobile number is 7075545685")


# ------------------------------------------------------------------- videos ----
@pytest.mark.parametrize("request_text, category", [
    ("need a campus tour", "Campus Tour"), ("hostel video", "Hostels"), ("show me placement videos", "Placements"),
    ("video about agriculture", "Agriculture"), ("how is the food in hostel", "Hostels"), ("mba", "MBA"),
])
def test_videos_match_the_topic_without_an_ai_call(request_text, category):
    from app.services.video_service import get_keyword_videos
    videos = get_keyword_videos(request_text, limit=2)
    assert videos and all(category in v["category"] for v in videos), [v["title"] for v in videos]
    assert len({v["url"] for v in videos}) == len(videos)          # never the same video twice


def test_no_video_for_an_unrelated_question():
    from app.services.video_service import get_keyword_videos, get_relevant_videos
    assert get_keyword_videos("what is the fee") == []
    assert get_relevant_videos(user_message="what is the cse fee with 85%") == []


def test_video_catalogue_is_clean():
    from app.services.video_service import load_videos
    videos = load_videos()
    assert len({v["url"] for v in videos}) == len(videos)
    for v in videos:
        assert v["url"].startswith("https://www.youtube.com/") and v["title"].strip() and v["category"].strip()
        assert v["thumbnail_url"].startswith("https://")


@pytest.mark.asyncio
async def test_video_tool_returns_relevant_videos():
    out = await tools.run_tool("get_university_videos", {"topic": "hostel life"}, {"session_id": "r2-video", "profile": {}})
    assert out["status"] == "ok" and all("Hostel" in v["category"] for v in out["videos"])
    out = await tools.run_tool("get_university_videos", {}, {"session_id": "r2-video", "profile": {}})
    assert all("Campus Tour" in v["category"] for v in out["videos"])
