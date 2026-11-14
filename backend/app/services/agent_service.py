"""Bounded agent policy and allowlisted tool routing."""

from dataclasses import dataclass
from enum import StrEnum

from app.services.finance_service import is_finance_calculation_query


class AgentRoute(StrEnum):
    NORMAL = "normal"
    FINANCE = "finance"


MAX_AGENT_STEPS = 3
ALLOWED_TOOLS = frozenset({"finance_estimate"})


@dataclass(frozen=True)
class AgentDecision:
    route: AgentRoute
    tool: str | None = None
    reason: str = ""


def decide_route(message: str) -> AgentDecision:
    """Choose a bounded route using deterministic policy checks."""
    if is_finance_calculation_query(message):
        return AgentDecision(
            route=AgentRoute.FINANCE,
            tool="finance_estimate",
            reason="explicit finance calculation intent",
        )
    return AgentDecision(route=AgentRoute.NORMAL, reason="no approved agent tool matched")


def validate_tool_call(tool: str, step: int) -> None:
    """Reject tools and execution depth outside the agent policy."""
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Tool is not allowlisted: {tool}")
    if step < 1 or step > MAX_AGENT_STEPS:
        raise ValueError(f"Agent step must be between 1 and {MAX_AGENT_STEPS}")
