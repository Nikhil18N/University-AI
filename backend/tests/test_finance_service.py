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
    assert result.total == Decimal("120000.00")
    assert result.scholarship_amount == Decimal("30000.00")
    assert len(result.sources) == 2


def test_finance_estimate_does_not_invent_missing_rules():
    result = estimate_finance(
        FinanceEstimateRequest(program="Unknown", academic_year="2026-27"),
        {"fee_rules": [], "scholarship_rules": []},
    )

    assert result.status == "insufficient_data"
    assert result.total is None
    assert result.missing_inputs
