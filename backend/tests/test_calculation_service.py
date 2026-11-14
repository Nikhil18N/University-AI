from decimal import Decimal

from app.schemas.finance import FinanceEstimateRequest, FinanceEstimateResponse


def test_finance_calculation_payloads_are_json_serializable():
    request = FinanceEstimateRequest(
        program="B.Tech CSE",
        academic_year="2026-27",
        score_percent=Decimal("92"),
    )
    result = FinanceEstimateResponse(status="insufficient_data")
    assert request.model_dump(mode="json")["score_percent"] == "92"
    assert result.model_dump(mode="json")["status"] == "insufficient_data"
