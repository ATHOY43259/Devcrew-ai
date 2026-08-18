"""Smoke tests: the whole mock pipeline must run end-to-end.

Run with:  pytest -q
(conftest.py forces MOCK_MODE=1, so no API key is needed.)
"""
import uuid

from langgraph.types import Command

from src.graph.build_graph import build_graph
from src.graph.state import AGENT_ORDER
from src.graph.supervisor import decide


def run_to_completion(app, request: str, decision: dict):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    payload = {"project_request": request}
    for _ in range(5):  # allow several interrupt/resume cycles
        events = list(app.stream(payload, config, stream_mode="updates"))
        if not any("__interrupt__" in e for e in events):
            break
        payload = Command(resume=decision)
    return app.get_state(config).values


def test_mock_pipeline_completes_with_all_agents():
    app = build_graph()
    state = run_to_completion(app, "Build a to-do list REST API", {"action": "approve"})

    assert state["final_report"], "final report missing"
    assert state["review_approved"] is True
    assert state["tests_passed"] is True
    assert state["revision_count"] >= 1, "review->developer rework loop did not happen"
    assert state["code_files"] and state["deployment_files"]

    spoke = {m["from_agent"] for m in state["agent_messages"]}
    for agent in AGENT_ORDER:
        assert agent in spoke, f"{agent} never sent a message"


def test_reject_sends_analyst_back_to_work():
    app = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    events = list(app.stream({"project_request": "x"}, config, stream_mode="updates"))
    assert any("__interrupt__" in e for e in events)

    # Reject once -> analyst must run again and pause for approval again.
    events = list(
        app.stream(
            Command(resume={"action": "reject", "feedback": "add security requirements"}),
            config,
            stream_mode="updates",
        )
    )
    assert any("__interrupt__" in e for e in events), "expected a second approval pause"

    state = app.get_state(config).values
    analyst_runs = [m for m in state["agent_messages"] if m["from_agent"] == "requirements_analyst"]
    assert len(analyst_runs) >= 2, "analyst did not rerun after rejection"


def test_supervisor_decide_ordering():
    assert decide({})[0] == "requirements_analyst"
    assert decide({"requirements_doc": "x"})[0] == "human_approval"
    assert decide({"requirements_doc": "x", "approvals": ["requirements"]})[0] == "architect"
