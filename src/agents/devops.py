"""DevOps / Deployment Engineer — STUB (canned output). Owner: Member 3.

TODO(Member 3): implement for real: generate Dockerfile + CI workflow from
architecture_doc and code_files via call_llm; validate the Dockerfile with a
lint pass; optionally add a docker-compose.yml.
"""
from src.agents.base import msg, stub_notice
from src.graph.state import ProjectState
from src.mock import canned_outputs
from src.observability.logging_setup import log_entry

AGENT = "devops"


def devops_node(state: ProjectState) -> dict:
    return {
        "deployment_files": canned_outputs.DEPLOYMENT_FILES,
        "agent_messages": [msg(AGENT, "supervisor", "Dockerfile + GitHub Actions CI ready.")],
        "logs": [log_entry(AGENT, "INFO", stub_notice(AGENT, "Member 3"))],
        "token_usage": {},
    }
