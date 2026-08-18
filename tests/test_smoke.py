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


def test_max_revisions_bailout_does_not_loop_forever():
    """Regression test: hitting MAX_REVISIONS with the review/test loop
    still failing must NOT route the supervisor back into the same
    "still not approved/passed" check forever. Reported live: doc_writer
    ran in an unbroken loop for 90+ seconds, never reaching FINISH."""
    base = {
        "requirements_doc": "x", "approvals": ["requirements"],
        "architecture_doc": "x", "code_files": {"a.py": "1"},
        "review_feedback": "still bad", "review_approved": False,
        "revision_count": 2,  # == MAX_REVISIONS default
    }

    # First bailout: past the review gate, WITH an override the caller
    # must apply — the override is what prevents the loop.
    next_node, _, overrides = decide(base)
    assert next_node == "tester"
    assert overrides == {"review_bypassed": True}

    # Simulate applying that override, then Tester running and STILL
    # failing — the classic loop trigger. Must NOT route back to "tester"
    # or re-declare the same review bailout again.
    state_after_tester = {
        **base, **overrides,
        "test_report": "still failing", "tests_passed": False,
    }
    next_node2, _, overrides2 = decide(state_after_tester)
    assert next_node2 == "doc_writer", f"expected to proceed past QA, got {next_node2!r} (would loop)"
    assert overrides2 == {"tests_bypassed": True}

    # Simulate applying THAT override too, then doc_writer having run.
    # This must move on to deployment approval / FINISH, not loop again.
    state_after_docs = {
        **state_after_tester, **overrides2,
        "documentation": "docs", "approvals": ["requirements", "deployment"],
        "deployment_files": {"Dockerfile": "x"},
    }
    next_node3, _, _ = decide(state_after_docs)
    assert next_node3 == "FINISH", f"expected FINISH, got {next_node3!r} (still stuck)"


def test_modification_loop_after_finish():
    """A finished project can take a follow-up modification request on the
    same thread: Developer -> Reviewer -> Tester run again, then a NEW
    approval gate pauses before re-finishing. Rejecting it with feedback
    starts another round instead of ending the loop."""
    app = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    payload = {"project_request": "Build a to-do list REST API"}
    for _ in range(5):
        events = list(app.stream(payload, config, stream_mode="updates"))
        if not any("__interrupt__" in e for e in events):
            break
        payload = Command(resume={"action": "approve"})
    state = app.get_state(config).values
    assert state["final_report"]

    mod_payload = {
        "modification_request": "add a favorite feature",
        "modification_pending": True,
        "modification_approved": False,
        "review_feedback": "",
        "review_approved": False,
        "test_report": "",
        "tests_passed": False,
        "final_report": "",
    }
    # Round 1: reject with feedback -> must loop back for another round.
    events = list(app.stream(mod_payload, config, stream_mode="updates"))
    assert any("__interrupt__" in e for e in events)
    interrupt_value = next(e["__interrupt__"][0].value for e in events if "__interrupt__" in e)
    assert interrupt_value["stage"] == "modification"

    events = list(app.stream(
        Command(resume={"action": "reject", "feedback": "also add a due date"}),
        config, stream_mode="updates",
    ))
    assert any("__interrupt__" in e for e in events), "rejecting should pause at the gate again, not finish"

    # Round 2: approve -> pipeline re-finishes.
    events = list(app.stream(Command(resume={"action": "approve"}), config, stream_mode="updates"))
    assert not any("__interrupt__" in e for e in events)

    state = app.get_state(config).values
    assert state["final_report"], "final report missing after the modification was approved"
    assert state["modification_request"] == "", "modification_request should be consumed on approval"
    assert state["approvals"].count("modification") == 1, "only the FINAL approval should count"
