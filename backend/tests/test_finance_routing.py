from app.services.finance_service import (
    build_finance_request,
    is_finance_calculation_query,
)


def test_finance_calculation_query_routes_to_tool():
    assert is_finance_calculation_query(
        "Calculate my B.Tech CSE fee with hostel after scholarship"
    )


def test_ordinary_fee_information_stays_on_normal_path():
    assert not is_finance_calculation_query("What is the fee structure?")


def test_finance_inputs_are_extracted_without_guessing():
    request, missing = build_finance_request(
        "Estimate B.Tech CSE fees for 2026-27 with hostel and 92%"
    )
    assert not missing
    assert request is not None
    assert request.program == "B.Tech CSE"
    assert request.academic_year == "2026-27"
    assert request.score_percent == 92
    assert request.hostel is True


def test_scholarship_calculation_requires_12th_marks():
    request, missing = build_finance_request(
        "Calculate B.Tech CSE fee after scholarship for 2026-27"
    )
    assert request is None
    assert "12th/Intermediate PCM percentage (for example, 85%)" in missing


def test_12th_marks_are_extracted_for_scholarship_calculation():
    request, missing = build_finance_request(
        "Calculate B.Tech CSE scholarship for 2026-27, my 12th marks are 92"
    )
    assert not missing
    assert request is not None
    assert request.score_percent == 92


def test_missing_finance_inputs_are_returned_for_clarification():
    request, missing = build_finance_request("Calculate my scholarship")
    assert request is None
    assert "program (for example, B.Tech CSE)" in missing
    assert "academic year (for example, 2026-27)" in missing
