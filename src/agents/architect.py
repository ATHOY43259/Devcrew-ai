"""Software Architect — REAL implementation. Owner: Member 2.

Follows the requirements_analyst.py pattern: researches the domain with the
web-search tool, drafts the architecture with an LLM call, then stores the
result in the vector knowledge base so later agents (Developer, Doc Writer)
can retrieve it via RAG.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry
from src.tools.web_search import web_search

AGENT = "architect"

SYSTEM_PROMPT = """You are the Software Architect on an AI software team.
Given a Software Requirements Specification, design the system architecture.

Respond in Markdown with exactly these sections:
# Architecture — <project name>
## Tech stack
## Components  (one bullet per module/file, one line each)
## API design  (a Markdown table: Method | Path | Body | Response)
## Diagram
A Mermaid `flowchart TD` component diagram in a fenced code block.

Keep it concrete and implementable — the Developer will build directly from
this document, without asking questions."""


def architect_node(state: ProjectState) -> dict:
    if config.MOCK_MODE:
        doc = canned_outputs.ARCHITECTURE_DOC
        usage = {}
        note = "Architecture ready: Flask + in-memory store, 3 components (mock mode)."
    else:
        requirements = state.get("requirements_doc", "")
        research = web_search(f"best practices architecture {requirements[:120]}", max_results=3)
        research_block = (
            "\n\nRelevant research:\n"
            + "\n".join(f"- {r['title']}: {r['snippet']}" for r in research)
            if research
            else ""
        )
        user_prompt = f"Requirements:\n{requirements}{research_block}"
        doc, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        note = "Architecture drafted from the requirements."

        from src.memory.knowledge_base import add_document

        try:
            add_document("architecture_doc", doc, {"agent": AGENT})
        except Exception as error:  # noqa: BLE001 — RAG storage is best-effort
            log_entry(AGENT, "WARNING", f"Could not store architecture doc in the knowledge base: {error}")

    return {
        "architecture_doc": doc,
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
