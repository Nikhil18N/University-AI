from app.services.agent_service import AgentRoute, AgentDecision


def test_agent_decision_contains_auditable_route_details():
    decision = AgentDecision(
        route=AgentRoute.FINANCE,
        tool="finance_estimate",
        reason="explicit finance calculation intent",
    )
    assert decision.route.value == "finance"
    assert decision.tool == "finance_estimate"
    assert decision.reason
