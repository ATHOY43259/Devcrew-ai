"""Documentation Writer — REAL implementation. Owner: Member 2.

Pulls extra context from the vector knowledge base (RAG) instead of
stuffing the full architecture doc into the prompt every time — a small but
real demonstration of retrieval-augmented generation.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "doc_writer"

SYSTEM_PROMPT = """You are the Documentation Writer on an AI software team.
Given the requirements, architecture, and final code files, write end-user
documentation.

Respond in Markdown with exactly these sections:
# <project name> — User Guide
## Setup  (install + run commands)
## Endpoints or usage  (one entry per public endpoint/function)
## Running tests

Keep it accurate to the actual code files given — do not invent endpoints
that are not implemented."""


def _format_code(code_files: dict) -> str:
    return "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in code_files.items())


def doc_writer_node(state: ProjectState) -> dict:
    human_feedback = state.get("human_feedback", "")

    if config.MOCK_MODE:
        doc = canned_outputs.DOCUMENTATION
        usage = {}
        note = "User guide + API reference written (mock mode)."
    else:
        from src.memory.knowledge_base import search

        try:
            retrieved = search(state.get("architecture_doc", "")[:200], k=2)
        except Exception as error:  # noqa: BLE001 — RAG retrieval is best-effort
            log_entry(AGENT, "WARNING", f"Knowledge base search failed: {error}")
            retrieved = []
        rag_block = (
            "\n\nAdditional context from the knowledge base:\n"
            + "\n".join(f"- {chunk['text'][:200]}" for chunk in retrieved)
            if retrieved
            else ""
        )
        user_prompt = (
            f"Requirements:\n{state.get('requirements_doc', '')}\n\n"
            f"Architecture:\n{state.get('architecture_doc', '')}\n\n"
            f"Code files:\n{_format_code(state.get('code_files', {}))}"
            f"{rag_block}"
        )
        if human_feedback:
            user_prompt += (
                f"\n\nThe human rejected the previous draft before deployment with this "
                f"feedback — revise accordingly:\n{human_feedback}"
            )
        doc, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        note = (
            "User guide revised using the human's feedback."
            if human_feedback
            else "User guide written from the final code and architecture."
        )

    return {
        "documentation": doc,
        "human_feedback": "",  # consumed
        "agent_messages": [msg(AGENT, "supervisor", note)],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
