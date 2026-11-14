import pytest

from app.services.agent_service import (
    ALLOWED_TOOLS,
    MAX_AGENT_STEPS,
    AgentRoute,
    decide_route,
    validate_tool_call,
)


def test_agent_policy_routes_only_explicit_calculations():
    decision = decide_route("Calculate my B.Tech CSE fee for 2026-27")
    assert decision.route == AgentRoute.FINANCE
    assert decision.tool == "finance_estimate"
    assert decision.tool in ALLOWED_TOOLS

    assert decide_route("What is the fee structure?").route == AgentRoute.NORMAL


def test_agent_policy_limits_tools_and_steps():
    validate_tool_call("finance_estimate", MAX_AGENT_STEPS)
    with pytest.raises(ValueError):
        validate_tool_call("delete_database", 1)
    with pytest.raises(ValueError):
        validate_tool_call("finance_estimate", MAX_AGENT_STEPS + 1)
