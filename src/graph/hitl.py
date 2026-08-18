"""Human-in-the-loop approval node. Owner: Member 1.

Uses langgraph's interrupt(): the graph PAUSES here (state saved in the
checkpointer) until the UI/CLI resumes it with a Command(resume=...) whose
value is {"action": "approve"} or {"action": "reject", "feedback": "..."}.

On reject, the requirements doc is cleared and the human's feedback is put
into state, so the supervisor sends the Requirements Analyst back to work —
a human->agent collaboration loop.

TODO(Member 1): add a second approval gate before deployment (copy this
node, gate on "deployment" in approvals) + a global pause/retry control.
"""
from langgraph.types import interrupt

from src.agents.base import msg
from src.graph.state import HUMAN, ProjectState
from src.observability.logging_setup import log_entry

NODE = "human_approval"


def human_approval_node(state: ProjectState) -> dict:
    decision = interrupt(
        {
            "stage": "requirements",
            "question": "Approve the requirements document?",
            "document": state.get("requirements_doc", ""),
        }
    )
    # Accept either a dict or a bare string ("approve") for CLI convenience.
    if isinstance(decision, dict):
        action = decision.get("action", "approve")
        feedback = decision.get("feedback", "")
    else:
        action = str(decision)
        feedback = ""

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
