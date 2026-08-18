"""Developer — STUB (canned output). Owner: Member 3.

The Developer is called MULTIPLE times: first to write v1, then again after
the Reviewer or Tester sends feedback (the collaboration loop worth marks).

TODO(Member 3): implement for real:
  1. SYSTEM_PROMPT: senior Python developer; input = requirements_doc +
     architecture_doc + (review_feedback or test_report if present); output =
     STRICT JSON {"files": {"path": "content", ...}} — parse with json.loads,
     retry once on parse failure.
  2. On rework (state has review_feedback / failing test_report), instruct
     the model to fix ONLY the reported issues.
  3. Use src/tools/code_exec.py to syntax-check files before returning.
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "developer"


def developer_node(state: ProjectState) -> dict:
    revision = state.get("revision_count", 0)
    review_rework = bool(state.get("review_feedback")) and not state.get("review_approved", False)
    test_rework = bool(state.get("test_report")) and not state.get("tests_passed", False)
    is_rework = review_rework or test_rework

    if is_rework:
        files = canned_outputs.CODE_V2
        note = f"Rework round {revision + 1}: fixed all issues from the code review."
        to_agent = "reviewer"
    else:
        files = canned_outputs.CODE_V1
        note = "Implemented v1 from the architecture (2 files)."
        to_agent = "supervisor"

    return {
        "code_files": files,
        # Rework resets review + tests so the Reviewer/Tester run again:
        "review_feedback": "",
        "review_approved": False,
        "test_report": "",
        "tests_passed": False,
        "revision_count": revision + (1 if is_rework else 0),
        "agent_messages": [msg(AGENT, to_agent, note)],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 3"))],
        "token_usage": {},
    }
