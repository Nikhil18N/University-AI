"""Run: pytest -q     (no API key needed)
These numbers match the CURRENT fees_2027_28.json. Update both together."""
from app.sru_agent import fees
from app.sru_agent.tools import clean_phone


def test_cse_92_percent_gets_30_percent():
    r = fees.calculate_fee("cse", percent=92)
    assert r["scholarship_percent"] == 30
    assert r["tuition_first_year"] == "₹3,40,000"
    assert r["tuition_first_year_after_scholarship"] == "₹2,38,000"
    assert r["per_semester_after_scholarship"] == "₹1,19,000"


def test_cse_no_marks_full_course_total():
    r = fees.calculate_fee("B.Tech CSE")
    # tuition 3,40,000 + 3,49,000 + 3,58,000 + 3,67,000 = 14,14,000
    # + enrollment 5,000 + other/exam 20,000 x 4 = 14,99,000
    assert r["full_course_total"] == "₹14,99,000"


def test_mech_75_percent():
    assert fees.calculate_fee("mech", percent=75)["tuition_first_year_after_scholarship"] == "₹1,60,000"


def test_hostel_added_to_first_year():
    r = fees.calculate_fee("ece", percent=50, hostel="ac_3")
    assert r["hostel"]["per_year"] == "₹1,35,000"
    assert r["first_year_total_payable"] == "₹4,30,000"  # 2,70,000 + 5,000 + 20,000 + 1,35,000


def test_eapcet_rank_scholarship():
    # Rank 9,000 falls in 8,001–20,000 slab which gets 25% scholarship
    r = fees.calculate_fee("cse", eapcet_rank=9000)
    assert r["scholarship_percent"] == 25
    assert r["scholarship_basis"] == "eapcet rank 9000"


def test_score_without_table_is_not_guessed():
    # PG has no eapcet_rank configured
    r = fees.calculate_fee("mba", eapcet_rank=500)
    assert r["scholarship_percent"] == 0
    assert any("eapcet_rank" in n for n in r["notes"])


def test_eligibility_58_percent_is_eligible():
    assert fees.check_eligibility("cse", 58)["eligible"] is True
    assert fees.check_eligibility("cse", 45)["eligible"] is False


def test_program_matching_and_unknown():
    assert fees.find_program("btech ai & ml") == "btech_cse"
    assert fees.find_program("wat r d fess for mech") == "btech_mech"
    assert fees.calculate_fee("astrology")["status"] == "unknown_program"


def test_phone_cleaning():
    assert clean_phone("+91 98765 43210") == "9876543210"
    assert clean_phone("09876543210") == "9876543210"
    assert clean_phone("12345") is None
    assert clean_phone("1234567890") is None
