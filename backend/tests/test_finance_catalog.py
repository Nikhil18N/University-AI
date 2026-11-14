from decimal import Decimal

from app.schemas.finance import FinanceCatalog, ScholarshipRule


def test_scholarship_rule_schema_supports_versioned_ranges():
    catalog = FinanceCatalog(
        scholarship_rules=[
            ScholarshipRule(
                name="Academic Scholarship",
                academic_year="2026-27",
                minimum_score_percent=Decimal("90"),
                maximum_score_percent=Decimal("100"),
                percent=Decimal("20"),
                source="official-scholarship-policy-2026",
            )
        ]
    )
    assert catalog.scholarship_rules[0].percent == Decimal("20")
