"""Human-in-the-loop approval nodes. Owner: Member 1.

Uses langgraph's interrupt(): the graph PAUSES here (state saved in the
checkpointer) until the UI/CLI resumes it with a Command(resume=...) whose
value is {"action": "approve"} or {"action": "reject", "feedback": "..."}.

Two gates:
- human_approval_node: before the Architect starts (approve the SRS). On
  reject, requirements_doc is cleared so the Requirements Analyst reruns.
- deployment_approval_node: before DevOps starts (approve deployment). On
  reject, documentation is cleared so the Doc Writer reruns with feedback.

Both are human->agent collaboration loops, the same pattern as
Reviewer->Developer and Tester->Developer.
"""
from langgraph.types import interrupt

from src.agents.base import msg
from src.graph.state import HUMAN, ProjectState
from src.observability.logging_setup import log_entry

NODE = "human_approval"
DEPLOYMENT_NODE = "deployment_approval"


def _resolve(decision) -> tuple[str, str]:
    """Accept either a dict or a bare string ("approve") for CLI convenience."""
    if isinstance(decision, dict):
        return decision.get("action", "approve"), decision.get("feedback", "")
    return str(decision), ""


def human_approval_node(state: ProjectState) -> dict:
    decision = interrupt(
        {
            "stage": "requirements",
            "question": "Approve the requirements document?",
            "document": state.get("requirements_doc", ""),
        }
    )
    action, feedback = _resolve(decision)

    if action == "approve":
        return {
            "approvals": ["requirements"],
            "agent_messages": [msg(HUMAN, "supervisor", "Requirements APPROVED.")],
            "logs": [log_entry(NODE, "INFO", "Human approved the requirements.")],
        }

    return {
        "requirements_doc": "",  # cleared -> supervisor re-runs the analyst
        "human_feedback": feedback or "Please revise the requirements.",
        "agent_messages": [
            msg(HUMAN, "requirements_analyst", f"Requirements REJECTED: {feedback or 'revise'}")
        ],
        "logs": [log_entry(NODE, "WARNING", f"Human rejected the requirements: {feedback}")],
    }


def deployment_approval_node(state: ProjectState) -> dict:
    decision = interrupt(
        {
            "stage": "deployment",
            "question": "Approve deployment (generate Dockerfile + CI workflow)?",
            "document": state.get("documentation", ""),
        }
    )
    action, feedback = _resolve(decision)

    if action == "approve":
        return {
            "approvals": ["deployment"],
            "agent_messages": [msg(HUMAN, "supervisor", "Deployment APPROVED.")],
            "logs": [log_entry(DEPLOYMENT_NODE, "INFO", "Human approved deployment.")],
        }

    return {
        "documentation": "",  # cleared -> supervisor re-runs the doc writer
        "human_feedback": feedback or "Please revise the documentation before deployment.",
        "agent_messages": [
            msg(HUMAN, "doc_writer", f"Deployment REJECTED: {feedback or 'revise the docs'}")
        ],
        "logs": [log_entry(DEPLOYMENT_NODE, "WARNING", f"Human rejected deployment: {feedback}")],
    }
