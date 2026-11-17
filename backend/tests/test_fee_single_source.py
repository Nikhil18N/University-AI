"""One fee file feeds the agent, the calculator API and the fee cards. These tests fail if any
of them starts carrying its own numbers again, or if the fee file drifts from the official
circular (backend/data/handbook/08_admissions_fees_scholarships_and_eligibility.md)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.sru_agent import fees
from app.sru_agent.router import router


@pytest.fixture(scope="module")
def api():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# Base tuition per year and yearly increase, copied from the official circular.
CIRCULAR = {
    "btech_cse": (340000, 9000), "btech_ai_robotics": (400000, 12000), "btech_ece": (270000, 8000),
    "btech_mech": (200000, 6000), "btech_civil": (200000, 6000), "btech_eee": (200000, 6000),
    "btech_iep": (340000, 10000), "bdes": (210000, 6000), "bsc_agri": (200000, 6000),
    "bba": (150000, 4000), "bba_specialised": (200000, 6000), "bca": (150000, 4000),
    "bsc_cs": (150000, 4000), "bcom": (100000, 3000), "mba": (300000, 9000), "mca": (150000, 4000),
    "mtech": (100000, 3000), "msc": (100000, 3000), "mba_agri": (200000, 6000),
}


def test_fee_file_matches_the_official_circular():
    data = fees.load_data()
    for key, (tuition, increase) in CIRCULAR.items():
        prog = data["programs"][key]
        assert (prog["tuition_per_year"], prog["yearly_increase"]) == (tuition, increase), key
    assert data["hostel_per_year"] == {"non_ac_4": 115000, "non_ac_3": 125000, "ac_4": 125000, "ac_3": 135000}
    assert data["one_time"] == {"enrollment_fee": 5000, "application_fee": 1100}
    assert data["yearly_other"] == {"other_fee": 15000, "exam_fee": 5000}
    assert data["transport_per_year"] == 30000


@pytest.mark.parametrize("score, expected", [
    ({"percent": 59.9}, 0), ({"percent": 60}, 10), ({"percent": 65}, 15), ({"percent": 70}, 20),
    ({"percent": 80}, 25), ({"percent": 92}, 30), ({"percent": 98}, 40),
    ({"percent": 90, "board": "cbse"}, 30), ({"percent": 95, "board": "cbse"}, 40),
    ({"eapcet_rank": 2000}, 40), ({"eapcet_rank": 2001}, 30), ({"eapcet_rank": 8000}, 30),
    ({"eapcet_rank": 9000}, 25), ({"eapcet_rank": 20000}, 25), ({"eapcet_rank": 20001}, 0),
    ({"jee_percentile": 55}, 10), ({"jee_percentile": 92}, 30), ({"jee_percentile": 95}, 40),
])
def test_merit_scholarship_slabs(score, expected):
    assert fees.calculate_fee("cse", **score)["scholarship_percent"] == expected


def test_best_of_marks_and_rank_is_used():
    fee = fees.calculate_fee("cse", percent=72, eapcet_rank=1500)
    assert fee["scholarship_percent"] == 40 and "eapcet rank 1500" in fee["scholarship_basis"]
    assert fee["scholarship_basis_text"] == "EAPCET rank 1,500"
    # each score is reported by itself, so "what do I get on my rank alone?" has an answer
    assert fee["scores_considered"] == [{"score": "Intermediate 72%", "scholarship_percent": 20},
                                        {"score": "EAPCET rank 1,500", "scholarship_percent": 40}]


def test_calculator_api_and_agent_tool_give_the_same_numbers(api):
    body = {"program": "btech_cse", "percent": 85, "hostel": "ac_4"}
    from_api = api.post("/api/v1/agent/calculate", json=body).json()
    from_tool = fees.calculate_fee(**body)
    for key in ("scholarship_percent", "tuition_first_year_after_scholarship", "sem1_total_payable",
                "total_per_semester", "first_year_total_payable"):
        assert from_api[key] == from_tool[key], key
    assert from_api["sem1_total_payable"] == "₹2,05,000" and from_api["total_per_semester"] == "₹2,00,000"


def test_calculator_api_understands_an_eapcet_rank(api):
    """The 16 Nov blocker: rank 9000 must give 25%, whatever the board selector says."""
    fee = api.post("/api/v1/agent/calculate",
                   json={"program": "btech_cse", "eapcet_rank": 9000, "board": "state_board"}).json()
    assert fee["scholarship_percent"] == 25 and fee["tuition_first_year_after_scholarship"] == "₹2,55,000"
    ib = api.post("/api/v1/agent/calculate", json={"program": "btech_cse", "ib_score": 40}).json()
    assert ib["scholarship_percent"] == 40


def test_fee_config_gives_the_calculator_everything_it_needs(api):
    cfg = api.get("/api/v1/agent/fee-config").json()
    assert cfg["status"] == "ok" and cfg["academic_year"] == "2027-28"
    data = fees.load_data()
    assert {p["id"] for p in cfg["programs"]} == set(data["programs"])
    cse = next(p for p in cfg["programs"] if p["id"] == "btech_cse")
    assert cse["tuition_per_year"] == 340000
    assert [e["key"] for e in cse["exams"]] == ["state_board", "cbse", "jee_percentile", "eapcet_rank", "ib"]
    assert [s["scholarship_percent"] for s in cse["slabs"]] == [10, 15, 20, 25, 30, 40]
    slab_25 = next(s for s in cse["slabs"] if s["scholarship_percent"] == 25)
    assert slab_25["payable_per_semester"] == 127500 and "8,001" in slab_25["ranges"]["eapcet_rank"]
    mba = next(p for p in cfg["programs"] if p["id"] == "mba")
    assert [e["key"] for e in mba["exams"]] == ["state_board"]  # PG: qualifying-degree % only
    assert cfg["hostel_per_year"] == data["hostel_per_year"]


def test_fee_cards_are_built_from_the_fee_file():
    from app.services.card_service import ADMISSION_FEE_CARD, HOSTEL_FEE_CARD, TRANSPORT_FEE_CARD
    data = fees.load_data()
    assert [i["amount"] for i in HOSTEL_FEE_CARD["items"]] == [
        fees.inr(data["hostel_per_year"][k]) for k in ("non_ac_4", "non_ac_3", "ac_4", "ac_3")]
    assert TRANSPORT_FEE_CARD["items"][0]["amount"] == "₹30,000"
    amounts = [i["amount"] for i in ADMISSION_FEE_CARD["items"]]
    assert amounts == ["₹5,000", "₹1,100"]
    # figures that were in the old hand-typed cards but not in the circular
    import json
    everything = json.dumps([ADMISSION_FEE_CARD, HOSTEL_FEE_CARD, TRANSPORT_FEE_CARD], ensure_ascii=False)
    for wrong in ("₹25,000", "₹85,000", "₹95,000", "₹22,000"):
        assert wrong not in everything


def test_placeholder_admin_key_is_refused_outside_debug(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from app.api.v1 import deps
    from app.config import settings

    monkeypatch.setattr(settings, "ADMIN_API_KEY", "change-me-in-production")
    monkeypatch.setattr(settings, "APP_DEBUG", False)
    with pytest.raises(HTTPException) as err:
        asyncio.run(deps.verify_admin_key("change-me-in-production"))
    assert err.value.status_code == 503

    monkeypatch.setattr(settings, "ADMIN_API_KEY", "a-real-long-secret")
    assert asyncio.run(deps.verify_admin_key("a-real-long-secret")) == "a-real-long-secret"
    with pytest.raises(HTTPException) as err:
        asyncio.run(deps.verify_admin_key("wrong"))
    assert err.value.status_code == 403


def test_cancel_lead_marks_do_not_contact():
    import asyncio
    import uuid
    from types import SimpleNamespace
    from app.services import lead_service

    lead = SimpleNamespace(id=uuid.uuid4(), status="new", metadata_={"request_type": "callback", "consent": True})

    class FakeDb:
        async def get(self, model, lead_id):
            return lead if lead_id == lead.id else None

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    assert asyncio.run(lead_service.cancel_lead(FakeDb(), uuid.uuid4())) is None
    out = asyncio.run(lead_service.cancel_lead(FakeDb(), lead.id, "changed my mind"))
    assert out.status == "do_not_contact"
    assert out.metadata_["consent"] is False and out.metadata_["cancel_reason"] == "changed my mind"
    assert out.metadata_["request_type"] == "callback" and "cancelled_at" in out.metadata_


def test_bundled_calculator_snapshot_is_up_to_date():
    """frontend/src/data/feeConfig.json must be regenerated whenever the fee file changes."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "export_fee_config.py"
    spec = importlib.util.spec_from_file_location("export_fee_config", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not module.TARGET.exists():
        pytest.skip("frontend is not present next to the backend")
    assert module.TARGET.read_text(encoding="utf-8") == module.render(), (
        "Fee data changed: run `python scripts/export_fee_config.py` and rebuild the frontend")
    assert module.CASES_TARGET.read_text(encoding="utf-8") == module.render_cases(), (
        "Fee data changed: run `python scripts/export_fee_config.py`, then `npm run test:calc` in frontend/")


def test_yearly_increase_is_flat_irrespective_of_scholarship():
    """Circular: 'Yearly Fee Increase (Irrespective of Schol.)'. 25% on CSE: 2,55,000 then +9,000 a year."""
    fee = fees.calculate_fee("cse", percent=85)
    assert [y["after_scholarship"] for y in fee["year_by_year"]] == [
        "₹2,55,000", "₹2,64,000", "₹2,73,000", "₹2,82,000"]


def test_public_leads_endpoint_is_rate_limited_per_address():
    import asyncio
    from app.sru_agent import memory

    async def burst():
        return [await memory.allow_request("lead:203.0.113.9", limit=3) for _ in range(5)]

    assert asyncio.run(burst()) == [True, True, True, False, False]


def test_expired_in_memory_chats_are_swept():
    import time
    from app.sru_agent import memory

    memory._local["sru:test:expired"] = (time.time() - 5, {"old": True})
    memory._local["sru:test:fresh"] = (time.time() + 500, {"old": False})
    for _ in range(500):
        memory._sweep()
    assert "sru:test:expired" not in memory._local and "sru:test:fresh" in memory._local
