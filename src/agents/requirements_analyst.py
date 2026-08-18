"""Requirements Analyst — REAL implementation (the reference example).

Owner: Member 2. This is the fully-implemented example agent: copy this
structure for architect.py and doc_writer.py.

Researches the domain with the web-search tool before writing the SRS, and
stores the SRS in the vector knowledge base for later RAG retrieval.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry
from src.tools.web_search import web_search

AGENT = "requirements_analyst"

SYSTEM_PROMPT = """You are the Requirements Analyst on an AI software team.
Turn the user's project request into a concise Software Requirements
Specification in Markdown with exactly these sections:
# Software Requirements Specification — <project name>
## Functional requirements  (FR1..FRn, testable statements)
## Non-functional requirements  (NFR1..NFRn)
## User stories  (3-5, "As a ..., I can ... so that ...")
Keep it under 400 words. Be specific enough that a developer and a tester
can work from it without asking questions."""


def requirements_analyst_node(state: ProjectState) -> dict:
    request = state.get("project_request", "")
    human_feedback = state.get("human_feedback", "")

    if config.MOCK_MODE:
        doc = canned_outputs.REQUIREMENTS_DOC
        usage = {}
        note = "SRS drafted (mock mode)."
    else:
        research = web_search(request, max_results=3)
        research_block = (
            "\n\nRelevant research:\n"
            + "\n".join(f"- {r['title']}: {r['snippet']}" for r in research)
            if research
            else ""
        )
        user_prompt = f"Project request:\n{request}{research_block}"
        if human_feedback:
            user_prompt += (
                f"\n\nThe human rejected the previous draft with this feedback — "
                f"revise accordingly:\n{human_feedback}"
            )
        doc, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
        note = "SRS drafted from the project request."
        if human_feedback:
            note = "SRS revised using the human's feedback."

        from src.memory.knowledge_base import add_document

        try:
            add_document("requirements_doc", doc, {"agent": AGENT})
        except Exception as error:  # noqa: BLE001 — RAG storage is best-effort
            log_entry(AGENT, "WARNING", f"Could not store the SRS in the knowledge base: {error}")

    return {
        "requirements_doc": doc,
        "human_feedback": "",  # consumed
        "agent_messages": [msg(AGENT, "supervisor", f"{note} Ready for human approval.")],
        "logs": [log_entry(AGENT, "INFO", note)],
        "token_usage": usage,
    }
