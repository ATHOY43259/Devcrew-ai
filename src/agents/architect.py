"""Software Architect — STUB (canned output). Owner: Member 2.

TODO(Member 2): implement for real, following requirements_analyst.py:
  1. SYSTEM_PROMPT: senior architect; input = requirements_doc; output =
     Markdown with tech stack, components, API design table, and a Mermaid
     component diagram.
  2. Replace the canned block below with call_llm(...) when not MOCK_MODE.
  3. Store the architecture doc in the vector knowledge base so later
     agents can retrieve it (RAG rubric item).
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "architect"


def architect_node(state: ProjectState) -> dict:
    doc = canned_outputs.ARCHITECTURE_DOC
    return {
        "architecture_doc": doc,
        "agent_messages": [
            msg(AGENT, "supervisor", "Architecture ready: Flask + in-memory store, 3 components.")
        ],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 2"))],
        "token_usage": {},
    }
