"""Prompt service — loads versioned prompts from the prompts/ directory."""

import logging
import re
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Cache loaded prompts in memory
_prompt_cache: dict[str, str] = {}

_FEE_POLICY_QUERY_RE = re.compile(
    r"\b(?:fee|fees|tuition|scholarship|scholarships|waiver|concession|concessions|"
    r"hostel|mess|bus|transport|enrollment|enrolment|exam\s*fee|application\s*fee|"
    r"cost|costs|price|afford|expensive|installment|instalment|semester\s*fee|"
    r"slab|slabs|deposit|refund|pay|payment|charges|discount|net\s*fee)\b|₹",
    re.IGNORECASE,
)

_OMITTED_FEE_POLICY_NOTE = (
    "FEE POLICY: Omitted for this non-fee query. If the student asks for fees, "
    "do not invent figures; refer to the Admissions Office (833 100 3030)."
)


def needs_fee_policy(*texts: str) -> bool:
    """Return True if any text mentions fees, scholarships, hostel/bus charges, or payments."""
    return any(bool(t and _FEE_POLICY_QUERY_RE.search(t)) for t in texts)


def load_prompt(name: str, include_fee_policy: bool = True) -> str:
    """Load a prompt template by name (without extension).

    Prompts are loaded from the prompts/ directory and cached.
    For example: load_prompt("system") loads prompts/system.md
    """
    cache_key = name if include_fee_policy else f"{name}:no_fee"
    if cache_key in _prompt_cache:
        return _prompt_cache[cache_key]

    prompt_path = settings.PROMPTS_DIR / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")

    # Strip the markdown title line (e.g., "# System Prompt\n\n")
    lines = content.strip().split("\n")
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:]).strip()

    # Fee figures are never typed into a prompt: the {{FEE_POLICY}} block is generated from the one fee policy
    # (app/sru_agent/fee_policy_2027_28.json) by the fee engine, so a prompt can never carry an outdated fee.
    if "{{FEE_POLICY}}" in content:
        replacement = fee_policy_block() if include_fee_policy else _OMITTED_FEE_POLICY_NOTE
        content = content.replace("{{FEE_POLICY}}", replacement)
    # The answer layout (how every answer looks in the chat) is written once, in prompts/answer_layout.md.
    if "{{ANSWER_LAYOUT}}" in content and name != "answer_layout":
        content = content.replace("{{ANSWER_LAYOUT}}", load_prompt("answer_layout").strip())

    _prompt_cache[cache_key] = content
    logger.info("Loaded prompt template: %s (fee_policy=%s)", name, include_fee_policy)
    return content


def fee_policy_block() -> str:
    """A compact, generated summary of the 2027-28 fee circular for prompts (figures only, no maths for the model)."""
    from app.sru_agent import fees
    data = fees.load_data()
    i = fees.inr
    lines = [f"FEE POLICY ({data['academic_year']}, {data['source']}). Quote these figures exactly; never compute:"]
    for key, p in data["programs"].items():
        r = fees.calculate_fee(key)
        lines.append(f"- {p['name']}: tuition {i(p['tuition_per_year'])}/yr (+{i(p['yearly_increase'])}/yr from Year 2), "
                     f"min {p['min_percent']:g}%; standard Sem 1 {r['sem1_total_payable']}, Sem 2 {r['sem2_total_payable']}, "
                     f"Year 1 {r['first_year_total_payable']}")
    ch = data["charges"]
    lines.append(f"- Charges: enrollment {i(ch['enrollment_fee']['amount'])} (Sem 1, Year 1); other fee "
                 f"{i(ch['other_fee']['amount'])} (Sem 1 every year); exam fee {i(ch['exam_fee']['amount'])} (Sem 1, Year 1 "
                 f"only); application form {i(ch['application_fee']['amount'])} (separate); specialisation fee "
                 f"{i(ch['specialization_fee']['amount'])}/yr from Year 2 where it applies; bus {i(ch['bus']['amount'])}/yr "
                 f"(optional); Ph.D. {i(ch['phd_fee']['amount'])}/yr; electricity deposit "
                 f"{i(ch['electricity_deposit']['non_ac'])} Non-AC / {i(ch['electricity_deposit']['ac'])} AC (one-time, hostel).")
    h = fees.hostel_per_year()
    lines.append("- Hostel (optional, room with meals, confirmed by the Admissions Office; not on the circular): "
                 + ", ".join(f"{fees.HOSTEL_LABELS[k]} {i(v)}/yr" for k, v in h.items()))
    names = {"state_board": "Inter / PG degree", "cbse": "CBSE/ICSE", "jee_percentile": "JEE Main",
             "eapcet_rank": "EAPCET rank", "ib": "IB"}
    for kind, table in data["slab_sets"]["ug"].items():
        if table:
            lines.append(f"- Merit scholarship (tuition only), {names[kind]}: " + ", ".join(
                f"{fees._range_text(kind, s)} → {s['percent']}%" for s in sorted(table, key=lambda s: s["percent"])))
    lines.append("- Special concessions (per year, verified): " + "; ".join(
        f"{c['label']} {i(c['amount'])}" for c in data["special_concessions"]))
    return "\n".join(lines)


def render_prompt(name: str, include_fee_policy: bool = True, **variables: str) -> str:
    """Load a prompt and fill in {{variable}} placeholders."""
    template = load_prompt(name, include_fee_policy=include_fee_policy)
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def clear_cache() -> None:
    """Clear the prompt cache (useful for testing)."""
    _prompt_cache.clear()
