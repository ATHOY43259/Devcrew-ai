"""Documentation Writer — STUB (canned output). Owner: Member 2.

TODO(Member 2): implement for real, following requirements_analyst.py:
  input = requirements_doc + architecture_doc + code_files; output = user
  guide + API reference in Markdown. Pull extra context from the vector
  knowledge base (RAG) instead of stuffing everything into one prompt.
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "doc_writer"


def doc_writer_node(state: ProjectState) -> dict:
    return {
        "documentation": canned_outputs.DOCUMENTATION,
        "agent_messages": [msg(AGENT, "supervisor", "User guide + API reference written.")],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 2"))],
        "token_usage": {},
    }
