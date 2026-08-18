"""Developer — REAL implementation. Owner: Member 3.

The Developer is called MULTIPLE times: first to write v1, then again after
the Reviewer or Tester sends feedback (the collaboration loop worth marks).
Output is strict JSON `{"files": {"path": "content", ...}}`, parsed with
json.loads (one retry on a parse failure), then syntax-checked before being
handed back to the supervisor.
"""
import json
import re

from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry
from src.tools.code_exec import syntax_check

AGENT = "developer"

SYSTEM_PROMPT = """You are a senior Python developer on an AI software team.
Given a requirements specification and an architecture document, implement
the project as working Python files.

Respond with ONLY strict JSON of the form:
{"files": {"path/to/file.py": "<full file content>", ...}}

Rules:
- No prose, no markdown code fences — the response must be valid JSON and
  nothing else.
- Include a test file under tests/ or test_*.py using pytest.
- Keep the implementation self-contained (standard library + the framework
  named in the architecture doc only).
- If given "reviewer feedback" or a "failing test report", fix ONLY the
  reported issues — do not rewrite unrelated code."""


def _extract_json(text: str) -> str:
    """Strip markdown code fences if the model added them anyway."""
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    return fence.group(1) if fence else text


def _parse_files(text: str) -> dict:
    payload = json.loads(_extract_json(text))
    files = payload["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("'files' must be a non-empty object")
    return files


def _generate_files(agent_name: str, user_prompt: str) -> tuple[dict, dict]:
    """Call the LLM and parse its JSON response, retrying once on failure."""
    text, usage = call_llm(agent_name, SYSTEM_PROMPT, user_prompt)
    try:
        return _parse_files(text), usage
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        log_entry(agent_name, "WARNING", f"Developer JSON parse failed, retrying once: {error}")
        retry_prompt = (
            user_prompt
            + f"\n\nYour previous response was not valid JSON ({error}). "
            "Respond again with ONLY the JSON object, no other text."
        )
        text2, usage2 = call_llm(agent_name, SYSTEM_PROMPT, retry_prompt)
        files = _parse_files(text2)  # let a second failure raise — supervisor logs it
        merged_usage = {
            AGENT: {
                "input_tokens": usage.get(AGENT, {}).get("input_tokens", 0)
                + usage2.get(AGENT, {}).get("input_tokens", 0),
                "output_tokens": usage.get(AGENT, {}).get("output_tokens", 0)
                + usage2.get(AGENT, {}).get("output_tokens", 0),
                "cost_usd": usage.get(AGENT, {}).get("cost_usd", 0)
                + usage2.get(AGENT, {}).get("cost_usd", 0),
            }
        }
        return files, merged_usage


def developer_node(state: ProjectState) -> dict:
    revision = state.get("revision_count", 0)
    review_rework = bool(state.get("review_feedback")) and not state.get("review_approved", False)
    test_rework = bool(state.get("test_report")) and not state.get("tests_passed", False)
    is_rework = review_rework or test_rework

    if config.MOCK_MODE:
        files = canned_outputs.CODE_V2 if is_rework else canned_outputs.CODE_V1
        usage = {}
        note = (
            f"Rework round {revision + 1}: fixed all issues from the code review (mock mode)."
            if is_rework
            else "Implemented v1 from the architecture (mock mode)."
        )
    else:
        user_prompt = (
            f"Requirements:\n{state.get('requirements_doc', '')}\n\n"
            f"Architecture:\n{state.get('architecture_doc', '')}"
        )
        if review_rework:
            user_prompt += f"\n\nReviewer feedback to fix:\n{state['review_feedback']}"
        if test_rework:
            user_prompt += f"\n\nFailing test report to fix:\n{state['test_report']}"

        files, usage = _generate_files(AGENT, user_prompt)
        errors = syntax_check(files)
        if errors:
            log_entry(AGENT, "WARNING", f"Syntax errors in generated code, retrying once: {errors}")
            retry_prompt = user_prompt + "\n\nYour code had syntax errors:\n" + "\n".join(errors)
            files, extra_usage = _generate_files(AGENT, retry_prompt)
            for key in ("input_tokens", "output_tokens", "cost_usd"):
                usage.setdefault(AGENT, {})[key] = usage.get(AGENT, {}).get(
                    key, 0
                ) + extra_usage.get(AGENT, {}).get(key, 0)

        note = (
            f"Rework round {revision + 1}: fixed the reported issues ({len(files)} files)."
            if is_rework
            else f"Implemented v1 from the architecture ({len(files)} files)."
        )

    return {
        "code_files": files,
        # Rework resets review + tests so the Reviewer/Tester run again:
        "review_feedback": "",
        "review_approved": False,
        "test_report": "",
        "tests_passed": False,
        "revision_count": revision + (1 if is_rework else 0),
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
