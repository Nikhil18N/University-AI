"""Source-driven, deterministic fee and scholarship calculation tools."""

from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.finance import (
    FinanceCatalog,
    FinanceEstimateRequest,
    FinanceEstimateResponse,
    FinanceLineItem,
)

_RULES_FILE = Path(__file__).resolve().parent.parent / "data" / "finance_rules.json"
_PAISE = Decimal("0.01")
_FINANCE_TOPIC_RE = re.compile(
    r"\b(fee|fees|tuition|scholarship|payable|cost|total|discount|concession)\b",
    re.IGNORECASE,
)
_CALCULATION_RE = re.compile(
    r"\b(calculate|calculator|estimate|estimated|how much|total|payable|cost|after|net)\b",
    re.IGNORECASE,
)
_PROGRAM_RE = re.compile(
    r"\b((?:b\.?\s*tech|m\.?\s*tech|mba|bba|ph\.?\s*d)(?:\s+[a-z0-9&-]+){0,4})\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(20\d{2}\s*[-/]\s*(?:20)?\d{2})\b")
_SCHOLARSHIP_RE = re.compile(r"\b(scholarship|scholarships|merit|waiver|concession)\b", re.IGNORECASE)
_SCORE_PATTERNS = (
    re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)(?!\w)", re.IGNORECASE),
    re.compile(
        r"\b(?:12th|10\+2|intermediate|inter|pcm|boards?|class\s*12)"
        r"\s*(?:marks?|score|percentage)?\s*(?:is|are|of|:)?\s*"
        r"(\d{1,3}(?:\.\d+)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d{1,3}(?:\.\d+)?)\s*(?:marks?|percentage)?\s*"
        r"(?:in|for)\s*(?:12th|10\+2|intermediate|inter|pcm|boards?|class\s*12)\b",
        re.IGNORECASE,
    ),
)


def is_finance_calculation_query(message: str) -> bool:
    """Return whether a message should use the deterministic finance tool."""
    return bool(_FINANCE_TOPIC_RE.search(message) and _CALCULATION_RE.search(message))


def _extract_score(message: str) -> Decimal | None:
    for pattern in _SCORE_PATTERNS:
        match = pattern.search(message)
        if match:
            return Decimal(match.group(1))
    return None


def build_finance_request(message: str) -> tuple[FinanceEstimateRequest | None, list[str]]:
    """Extract only explicit finance inputs; missing values become clarification prompts."""
    program_match = _PROGRAM_RE.search(message)
    year_match = _YEAR_RE.search(message)
    score = _extract_score(message)
    missing: list[str] = []
    if not program_match:
        missing.append("program (for example, B.Tech CSE)")
    if not year_match:
        missing.append("academic year (for example, 2026-27)")
    if _SCHOLARSHIP_RE.search(message) and score is None:
        missing.append("12th/Intermediate PCM percentage (for example, 85%)")
    if missing:
        return None, missing

    program = re.split(
        r"\s+(?:fee|fees|tuition|for|with|after|and)\b",
        " ".join(program_match.group(1).split()),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    program = re.sub(
        r"\s+(?:fee|fees|tuition|scholarship|cost|estimate|estimation)$",
        "",
        program,
        flags=re.IGNORECASE,
    )
    academic_year = re.sub(r"\s+", "", year_match.group(1)).replace("/", "-")
    lowered = message.casefold()
    return (
        FinanceEstimateRequest(
            program=program,
            academic_year=academic_year,
            score_percent=score,
            hostel=bool(re.search(r"\b(hostel|accommodation|dorm)\b", lowered)),
            transport=bool(re.search(r"\b(transport|bus)\b", lowered)),
        ),
        [],
    )


def _money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(_PAISE, rounding=ROUND_HALF_UP)


@lru_cache(maxsize=1)
def load_finance_rules() -> dict[str, list[dict[str, Any]]]:
    """Load published rules; an empty catalog is safer than invented amounts."""
    if not _RULES_FILE.exists():
        return {"fee_rules": [], "scholarship_rules": []}
    with _RULES_FILE.open(encoding="utf-8") as file:
        data = json.load(file)
    return {
        "fee_rules": data.get("fee_rules", []),
        "scholarship_rules": data.get("scholarship_rules", []),
    }


def get_finance_catalog() -> FinanceCatalog:
    """Return the validated catalog for admin review."""
    return FinanceCatalog.model_validate(load_finance_rules())


def replace_finance_catalog(catalog: FinanceCatalog) -> FinanceCatalog:
    """Atomically replace rules after admin validation."""
    payload = catalog.model_dump(mode="json")
    temporary_path = _RULES_FILE.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")
    temporary_path.replace(_RULES_FILE)
    load_finance_rules.cache_clear()
    return get_finance_catalog()


def _find_fee_rule(request: FinanceEstimateRequest, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    program = request.program.casefold().strip()
    year = request.academic_year.casefold().strip()
    for rule in rules:
        if (
            str(rule.get("program", "")).casefold() == program
            and str(rule.get("academic_year", "")).casefold() == year
        ):
            return rule
    return None


def _find_scholarship(
    request: FinanceEstimateRequest,
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if request.score_percent is None:
        return None
    candidates = []
    for rule in rules:
        if str(rule.get("academic_year", "")).casefold() != request.academic_year.casefold():
            continue
        minimum = Decimal(str(rule.get("minimum_score_percent", 0)))
        maximum = Decimal(str(rule.get("maximum_score_percent", 100)))
        if minimum <= request.score_percent <= maximum:
            categories = rule.get("categories") or []
            if not categories or (request.category and request.category in categories):
                candidates.append(rule)
    return max(candidates, key=lambda rule: Decimal(str(rule.get("percent", 0))), default=None)


def estimate_finance(
    request: FinanceEstimateRequest,
    catalog: dict[str, list[dict[str, Any]]] | None = None,
) -> FinanceEstimateResponse:
    """Calculate only from published, versioned rules supplied by the catalog."""
    catalog = catalog or load_finance_rules()
    fee_rule = _find_fee_rule(request, catalog.get("fee_rules", []))
    if fee_rule is None:
        return FinanceEstimateResponse(
            status="insufficient_data",
            missing_inputs=[
                f"published fee rule for {request.program} ({request.academic_year})"
            ],
            assumptions=["No amount was inferred because the official fee catalog has no matching rule."],
        )

    source = str(fee_rule.get("source", "official fee schedule"))
    items = [
        FinanceLineItem(
            label="Tuition",
            amount=_money(fee_rule["tuition"]),
            source=source,
        )
    ]
    if request.hostel:
        if fee_rule.get("hostel") is None:
            return FinanceEstimateResponse(
                status="insufficient_data",
                missing_inputs=["hostel charge for the selected program and academic year"],
                sources=[source],
            )
        items.append(FinanceLineItem(label="Hostel", amount=_money(fee_rule["hostel"]), source=source))
    if request.transport:
        if fee_rule.get("transport") is None:
            return FinanceEstimateResponse(
                status="insufficient_data",
                missing_inputs=["transport charge for the selected program and academic year"],
                sources=[source],
            )
        items.append(FinanceLineItem(label="Transport", amount=_money(fee_rule["transport"]), source=source))

    subtotal = sum((item.amount for item in items), Decimal("0"))
    scholarship = _find_scholarship(request, catalog.get("scholarship_rules", []))
    scholarship_amount = Decimal("0")
    scholarship_name = None
    if scholarship:
        scholarship_name = str(scholarship["name"])
        scholarship_amount = _money(subtotal * Decimal(str(scholarship["percent"])) / Decimal("100"))

    return FinanceEstimateResponse(
        status="calculated",
        total=_money(subtotal - scholarship_amount),
        line_items=items,
        scholarship_amount=scholarship_amount or None,
        scholarship_name=scholarship_name,
        sources=list(dict.fromkeys([source] + [str(scholarship["source"])] if scholarship else [source])),
    )
