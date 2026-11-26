from decimal import Decimal

from app.schemas.finance import FinanceEstimateRequest
from app.services.finance_service import estimate_finance


def test_finance_estimate_calculates_published_rules():
    request = FinanceEstimateRequest(
        program="B.Tech CSE",
        academic_year="2026-27",
        score_percent=Decimal("92"),
        hostel=True,
    )
    result = estimate_finance(
        request,
        {
            "fee_rules": [
                {
                    "program": "B.Tech CSE",
                    "academic_year": "2026-27",
                    "tuition": "100000",
                    "hostel": "50000",
                    "source": "official-fee-schedule-2026",
                }
            ],
            "scholarship_rules": [
                {
                    "name": "Academic Scholarship",
                    "academic_year": "2026-27",
                    "minimum_score_percent": "90",
                    "maximum_score_percent": "100",
                    "percent": "20",
                    "source": "official-scholarship-policy-2026",
                }
            ],
        },
    )

    assert result.status == "calculated"
    # 20% scholarship applies strictly to tuition (100,000 -> 20,000), never hostel (50,000)
    assert result.scholarship_amount == Decimal("20000.00")
    assert result.total == Decimal("130000.00")
    assert len(result.sources) == 2


def test_finance_estimate_delegates_to_official_policy_when_no_catalog():
    from app.sru_agent import fees

    request = FinanceEstimateRequest(
        program="B.Tech CSE",
        academic_year="2027-28",
        score_percent=Decimal("95"),
        hostel=True,
        transport=True,
    )
    result = estimate_finance(request)
    official = fees.fee_schedule("btech_cse", 30, hostel="non_ac_4", transport=True)
    y1 = official["years"][0]

    assert result.status == "calculated"
    assert result.scholarship_amount == Decimal(str(y1["scholarship"])).quantize(Decimal("0.01"))
    assert result.total == Decimal(str(y1["total"])).quantize(Decimal("0.01"))


def test_finance_estimate_does_not_invent_missing_rules():
    result = estimate_finance(
        FinanceEstimateRequest(program="Unknown", academic_year="2026-27"),
        {"fee_rules": [], "scholarship_rules": []},
    )

    assert result.status == "insufficient_data"
    assert result.total is None
    assert result.missing_inputs
