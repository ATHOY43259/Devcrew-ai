"""Code Reviewer — STUB (canned output). Owner: Member 3.

In mock mode the reviewer REJECTS round 1 and APPROVES round 2 so every demo
visibly shows the Reviewer <-> Developer collaboration loop.

TODO(Member 3): implement for real:
  1. SYSTEM_PROMPT: strict senior reviewer; input = requirements_doc +
     code_files; output must START with "APPROVED" or "CHANGES REQUESTED"
     followed by a numbered issue list (parse the first line to set
     review_approved).
  2. Check: correctness vs requirements, error handling, input validation,
     missing tests, security smells.
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "reviewer"


def reviewer_node(state: ProjectState) -> dict:
    if state.get("revision_count", 0) == 0:
        feedback, approved = canned_outputs.REVIEW_ROUND_1, False
        note = "Review round 1: CHANGES REQUESTED (3 issues) — sent back to Developer."
        to_agent = "developer"
    else:
        feedback, approved = canned_outputs.REVIEW_ROUND_2, True
        note = "Review round 2: APPROVED — handing over to QA."
        to_agent = "tester"

    return {
        "review_feedback": feedback,
        "review_approved": approved,
        "agent_messages": [msg(AGENT, to_agent, note)],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 3"))],
        "token_usage": {},
    }
