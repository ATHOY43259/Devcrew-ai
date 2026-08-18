"""Code Reviewer — REAL implementation. Owner: Member 3.

The verdict is parsed from the first line of the LLM's response, which must
start with "APPROVED" or "CHANGES REQUESTED" by construction of the prompt.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "reviewer"

SYSTEM_PROMPT = """You are a strict senior code reviewer on an AI software team.
Given a requirements specification and a set of code files, review the code
against the requirements.

Check for: correctness vs. the requirements, missing error handling, missing
input validation, missing tests, obvious security smells (e.g. no input
sanitization, secrets in code, unsafe eval/exec), and sandbox compliance —
the code MUST use only Python's standard library (no Flask/FastAPI/Django/
requests/SQLAlchemy imports) and MUST persist data via `sqlite3` to a real
on-disk database file, never an in-memory dict/list. A pip-installed import
or in-memory "storage" is grounds for CHANGES REQUESTED on its own, since
the test sandbox cannot install packages and in-memory state isn't real
persistence.

Respond in this exact format:
- First line: either "APPROVED" or "CHANGES REQUESTED" (nothing else on that line).
- If CHANGES REQUESTED, follow with a numbered list of concrete, actionable issues.
- If APPROVED, follow with one sentence summarizing why the code meets requirements."""


def _format_code(code_files: dict) -> str:
    return "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in code_files.items())


def reviewer_node(state: ProjectState) -> dict:
    if config.MOCK_MODE:
        if state.get("revision_count", 0) == 0:
            feedback, approved = canned_outputs.REVIEW_ROUND_1, False
            note = "Review round 1: CHANGES REQUESTED (3 issues) — sent back to Developer (mock mode)."
            to_agent = "developer"
        else:
            feedback, approved = canned_outputs.REVIEW_ROUND_2, True
            note = "Review round 2: APPROVED — handing over to QA (mock mode)."
            to_agent = "tester"
        usage = {}
    else:
        user_prompt = (
            f"Requirements:\n{state.get('requirements_doc', '')}\n\n"
            f"Code files:\n{_format_code(state.get('code_files', {}))}"
        )
        feedback, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        approved = feedback.strip().upper().startswith("APPROVED")
        to_agent = "tester" if approved else "developer"
        verdict = "APPROVED" if approved else "CHANGES REQUESTED"
        note = f"Review: {verdict} — {'handing over to QA' if approved else 'sent back to Developer'}."

    return {
        "review_feedback": feedback,
        "review_approved": approved,
        "agent_messages": [msg(AGENT, to_agent, note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
