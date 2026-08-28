"""Release Notes / Changelog Agent — NEW agent, not yet wired into the graph.

Runs after DevOps, once code + deployment files exist. Turns the
requirements doc, the shipped code, and the deployment setup into a short
human-readable CHANGELOG-style release note, so every run produces something
a reviewer or stakeholder can skim without reading the raw diffs.

Integration note for whoever owns src/graph/ (see CLAUDE.md — state.py is a
frozen contract, changed only via a PR the whole team approves):
  1. Add `release_notes: str` to ProjectState in src/graph/state.py.
  2. Add "release_notes" to AGENT_ORDER (after "devops") in the same file.
  3. Register the node in src/graph/build_graph.py:
       from src.agents.release_notes import release_notes_node
       AGENT_NODES["release_notes"] = release_notes_node
  4. Add a routing case in src/graph/supervisor.py::decide() so the
     supervisor calls "release_notes" after "devops" finishes, before FINISH.
This file works standalone today — see tests/test_release_notes.py, which
calls release_notes_node() directly with a fake state dict and needs no
graph wiring to pass.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "release_notes"

SYSTEM_PROMPT = """You are the Release Manager on an AI software team.
Given the requirements doc, the code files, and the deployment files for a
finished project, write short, human-readable release notes in Markdown
with exactly these sections:
# Release Notes — <project name> v1.0.0
## Summary  (1-2 sentences)
## Added  (bullet list of shipped functionality, derived from the requirements)
## Fixed  (bullet list — mention rework if the review/test loop caught issues; otherwise omit this section)
## Deployment  (how it's containerized / how CI runs)
## Known limitations  (bullet list, be honest and specific)
Keep it under 300 words. Do not invent features that aren't in the
requirements or code."""


def _format_code(code_files: dict) -> str:
    return "\n".join(f"- {path}" for path in sorted(code_files or {}))


def release_notes_node(state: ProjectState) -> dict:
    if config.MOCK_MODE:
        notes = canned_outputs.RELEASE_NOTES
        usage = {}
        note = "Release notes drafted (mock mode)."
    else:
        user_prompt = (
            f"Requirements:\n{state.get('requirements_doc', '')}\n\n"
            f"Files shipped:\n{_format_code(state.get('code_files', {}))}\n\n"
            f"Deployment files:\n{_format_code(state.get('deployment_files', {}))}\n\n"
            f"Rework rounds during development: {state.get('revision_count', 0)}"
        )
        notes, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        note = "Release notes drafted from the finished project."

    return {
        "release_notes": notes,
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
