from app.models.agent_task import PendingAgentTask


def test_pending_agent_task_is_scoped_to_a_conversation_and_session():
    task = PendingAgentTask(
        conversation_id="00000000-0000-0000-0000-000000000001",
        session_id="session-1",
        task_type="finance_estimate",
        original_query="Calculate my fee",
        missing_inputs=["program"],
        status="pending",
    )
    assert task.task_type == "finance_estimate"
    assert task.status == "pending"
    assert task.missing_inputs == ["program"]
