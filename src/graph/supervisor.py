"""Supervisor / Project Manager. Owner: Member 1.

Hub of the hub-and-spoke graph: every agent returns here, and the supervisor
decides who runs next. The starter version is a deterministic state machine
(reliable for demos); the reasoning is written into supervisor_plan and the
logs so the UI can display WHY each routing decision was made.

TODO(Member 1): upgrade to LLM-based planning ("planning and reasoning"
rubric item): give the model a summary of the state + the list of valid next
agents, let it pick and justify; KEEP decide() as the safety fallback if the
LLM answer is not a valid agent name.
"""
from src import config
from src.agents.base import msg
from src.graph.state import ProjectState
from src.observability.logging_setup import log_entry

AGENT = "supervisor"
FINISH = "FINISH"
HUMAN_APPROVAL = "human_approval"


def decide(state: ProjectState) -> tuple[str, str]:
    """Return (next_node, reason). Pure function — unit-test me."""
    max_rev = config.MAX_REVISIONS

    if not state.get("requirements_doc"):
        return "requirements_analyst", "No requirements yet — starting with the SRS."
    if "requirements" not in state.get("approvals", []):
        return HUMAN_APPROVAL, "SRS drafted — pausing for human approval (HITL)."
    if not state.get("architecture_doc"):
        return "architect", "Requirements approved — designing the architecture."
    if not state.get("code_files"):
        return "developer", "Architecture ready — implementing the code."

    if not state.get("review_approved"):
        if state.get("review_feedback"):
            if state.get("revision_count", 0) < max_rev:
                return "developer", "Reviewer requested changes — sending back to the Developer."
            return "tester", f"Max revisions ({max_rev}) reached — proceeding to QA with known issues."
        return "reviewer", "Code written — requesting code review."

    if not state.get("tests_passed"):
        if state.get("test_report"):
            if state.get("revision_count", 0) < max_rev:
                return "developer", "Tests failed — sending the report back to the Developer."
            return "doc_writer", f"Max revisions ({max_rev}) reached — proceeding with failing tests flagged."
        return "tester", "Review approved — running QA."

    if not state.get("documentation"):
        return "doc_writer", "QA passed — writing the documentation."
    if not state.get("deployment_files"):
        return "devops", "Docs done — preparing deployment."
    return FINISH, "All phases complete — composing the final report."


def _final_report(state: ProjectState) -> str:
    files = "\n".join(f"- `{p}`" for p in sorted(state.get("code_files", {})))
    deploy = "\n".join(f"- `{p}`" for p in sorted(state.get("deployment_files", {})))
    usage = state.get("token_usage", {})
    return f"""# Final Delivery Report

**Project request:** {state.get('project_request', '')}

**Pipeline:** requirements -> human approval -> architecture -> code ->
review ({state.get('revision_count', 0)} rework round(s)) -> QA
({'PASS' if state.get('tests_passed') else 'FAIL'}) -> docs -> deployment.

## Deliverables
### Code files
{files}
### Deployment files
{deploy}

## Quality gates
- Code review: {"APPROVED" if state.get('review_approved') else "NOT APPROVED"}
- Tests: {"PASSED" if state.get('tests_passed') else "FAILED"}
- Human approvals: {", ".join(state.get('approvals', [])) or "none"}

## Agents involved
{len(set(m['from_agent'] for m in state.get('agent_messages', [])))} agents exchanged {len(state.get('agent_messages', []))} messages.
Token usage by agent: {usage or "mock mode — zero cost"}
"""


def supervisor_node(state: ProjectState) -> dict:
    next_node, reason = decide(state)
    update: dict = {
        "next_agent": next_node,
        "supervisor_plan": reason,
        "agent_messages": [msg(AGENT, next_node if next_node != FINISH else "user", reason)],
        "logs": [log_entry(AGENT, "INFO", f"route -> {next_node}: {reason}")],
    }
    if next_node == FINISH:
        update["final_report"] = _final_report(state)
    return update


def route_from_supervisor(state: ProjectState) -> str:
    """Conditional-edge selector: reads the decision made in supervisor_node."""
    return state.get("next_agent", FINISH)
