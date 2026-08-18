"""QA / Test Engineer — STUB (canned output). Owner: Member 3.

TODO(Member 3): implement for real:
  1. Write the generated code_files to a temp dir with src/tools/code_exec.py
     and RUN pytest in a subprocess (timeout 60 s) — real tool usage, big
     rubric win.
  2. tests_passed = (pytest exit code == 0); test_report = captured output.
  3. On failure, the supervisor routes back to the Developer with the report
     (second collaboration loop).
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "tester"


def tester_node(state: ProjectState) -> dict:
    return {
        "test_report": canned_outputs.TEST_REPORT,
        "tests_passed": True,
        "agent_messages": [msg(AGENT, "supervisor", "4/4 tests passed, coverage OK — verdict PASS.")],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 3"))],
        "token_usage": {},
    }
