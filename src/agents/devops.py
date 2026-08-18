"""DevOps / Deployment Engineer — REAL implementation. Owner: Member 3.

Generates a Dockerfile and a GitHub Actions CI workflow from the architecture
doc and the final code files. Output is strict JSON, same convention as the
Developer agent, so it reuses the same parsing helper.
"""
from src import config
from src.agents.base import call_llm, msg
from src.agents.developer import _parse_files
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "devops"

SYSTEM_PROMPT = """You are a DevOps engineer on an AI software team.
Given an architecture document and a project's code files, produce
deployment files: a Dockerfile and a GitHub Actions CI workflow that
installs dependencies and runs the test suite.

Respond with ONLY strict JSON of the form:
{"files": {"Dockerfile": "<content>", ".github/workflows/ci.yml": "<content>"}}
No prose, no markdown code fences — the response must be valid JSON and
nothing else."""


def _format_code(code_files: dict) -> str:
    return "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in code_files.items())


def devops_node(state: ProjectState) -> dict:
    if config.MOCK_MODE:
        deployment_files = canned_outputs.DEPLOYMENT_FILES
        usage = {}
        note = "Dockerfile + GitHub Actions CI ready (mock mode)."
    else:
        user_prompt = (
            f"Architecture:\n{state.get('architecture_doc', '')}\n\n"
            f"Code files:\n{_format_code(state.get('code_files', {}))}"
        )
        text, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        try:
            deployment_files = _parse_files(text)
        except (ValueError, KeyError) as error:
            log_entry(AGENT, "WARNING", f"DevOps JSON parse failed, retrying once: {error}")
            text2, usage2 = call_llm(
                AGENT, SYSTEM_PROMPT, user_prompt + "\n\nRespond again with ONLY the JSON object."
            )
            deployment_files = _parse_files(text2)
            for key in ("input_tokens", "output_tokens", "cost_usd"):
                usage.setdefault(AGENT, {})[key] = usage.get(AGENT, {}).get(
                    key, 0
                ) + usage2.get(AGENT, {}).get(key, 0)
        note = f"Deployment files ready ({len(deployment_files)} files)."

    return {
        "deployment_files": deployment_files,
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
