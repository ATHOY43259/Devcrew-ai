"""Wires the LangGraph workflow. Owner: Member 1.

Topology (hub-and-spoke):
    START -> supervisor -> (one of 7 agents | 3 human approval gates | END)
    every agent -> supervisor

Checkpointing is SQLite-backed (checkpoints.sqlite in the repo root) so runs
survive app restarts — the UI/CLI can resume a thread_id across processes.
"""
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.agents.architect import architect_node
from src.agents.developer import developer_node
from src.agents.devops import devops_node
from src.agents.doc_writer import doc_writer_node
from src.agents.requirements_analyst import requirements_analyst_node
from src.agents.reviewer import reviewer_node
from src.agents.tester import tester_node
from src.graph.hitl import deployment_approval_node, human_approval_node, modification_approval_node
from src.graph.state import AGENT_ORDER, ProjectState
from src.graph.supervisor import (
    DEPLOYMENT_APPROVAL,
    FINISH,
    HUMAN_APPROVAL,
    MODIFICATION_APPROVAL,
    route_from_supervisor,
    supervisor_node,
)

DB_PATH = Path(__file__).resolve().parents[2] / "checkpoints.sqlite"

AGENT_NODES = {
    "requirements_analyst": requirements_analyst_node,
    "architect": architect_node,
    "developer": developer_node,
    "reviewer": reviewer_node,
    "tester": tester_node,
    "doc_writer": doc_writer_node,
    "devops": devops_node,
}
assert list(AGENT_NODES) == AGENT_ORDER, "Keep AGENT_NODES in sync with state.AGENT_ORDER"


def _checkpointer() -> SqliteSaver:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)


def build_graph():
    graph = StateGraph(ProjectState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node(HUMAN_APPROVAL, human_approval_node)
    graph.add_node(DEPLOYMENT_APPROVAL, deployment_approval_node)
    graph.add_node(MODIFICATION_APPROVAL, modification_approval_node)
    for name, node in AGENT_NODES.items():
        graph.add_node(name, node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            **{name: name for name in AGENT_NODES},
            HUMAN_APPROVAL: HUMAN_APPROVAL,
            DEPLOYMENT_APPROVAL: DEPLOYMENT_APPROVAL,
            MODIFICATION_APPROVAL: MODIFICATION_APPROVAL,
            FINISH: END,
        },
    )
    # Hub-and-spoke: every worker reports back to the supervisor.
    for name in AGENT_NODES:
        graph.add_edge(name, "supervisor")
    graph.add_edge(HUMAN_APPROVAL, "supervisor")
    graph.add_edge(DEPLOYMENT_APPROVAL, "supervisor")
    graph.add_edge(MODIFICATION_APPROVAL, "supervisor")

    return graph.compile(checkpointer=_checkpointer())


@lru_cache(maxsize=1)
def get_app():
    """Compiled graph singleton (cached across Streamlit reruns)."""
    return build_graph()


def get_history(thread_id: str) -> list:
    """All checkpoints for a thread, newest first — powers retry/rewind UI."""
    config = {"configurable": {"thread_id": thread_id}}
    return list(get_app().get_state_history(config))


def retry_last_step(thread_id: str) -> Iterator[dict]:
    """Re-run the last completed node from the checkpoint taken just before
    it ran (LangGraph "time travel"). Useful when a node failed or produced
    a bad result and you want to retry it without restarting the whole run.
    Raises RuntimeError if there is no earlier checkpoint to rewind to."""
    history = get_history(thread_id)
    for snapshot in history[1:]:  # [0] is the current state; look further back
        if snapshot.next:  # this checkpoint still had a pending node -> rewind here
            return get_app().stream(None, snapshot.config, stream_mode="updates")
    raise RuntimeError(f"No earlier checkpoint to retry from for thread {thread_id}")


def resume(thread_id: str, decision: dict) -> Iterator[dict]:
    """Resume a paused (interrupted) run with a human decision."""
    config = {"configurable": {"thread_id": thread_id}}
    return get_app().stream(Command(resume=decision), config, stream_mode="updates")
