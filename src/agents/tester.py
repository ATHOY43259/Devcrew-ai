"""QA / Test Engineer — REAL implementation. Owner: Member 3.

Writes the Developer's generated files to an isolated temp directory and
runs pytest in a subprocess (real tool usage, not an LLM call) — this agent
never invokes an LLM, so it costs nothing even in live mode.
"""
from src import config
from src.agents.base import msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry
from src.tools.code_exec import run_pytest, write_files

AGENT = "tester"


def tester_node(state: ProjectState) -> dict:
    if config.MOCK_MODE:
        report, passed = canned_outputs.TEST_REPORT, True
        note = "4/4 tests passed, coverage OK — verdict PASS (mock mode)."
    else:
        code_files = state.get("code_files", {})
        project_dir = write_files(code_files)
        passed, output = run_pytest(project_dir)
        report = output or "pytest produced no output."
        note = f"Tests {'PASSED' if passed else 'FAILED'} — verdict {'PASS' if passed else 'FAIL'}."

    return {
        "test_report": report,
        "tests_passed": passed,
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO" if passed else "WARNING", note)],
        "token_usage": {},
    }
