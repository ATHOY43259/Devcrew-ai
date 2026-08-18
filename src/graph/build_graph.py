"""Wires the LangGraph workflow. Owner: Member 1.

Topology (hub-and-spoke):
    START -> supervisor -> (one of 7 agents | human_approval | END)
    every agent -> supervisor

TODO(Member 1): swap InMemorySaver for SqliteSaver so runs survive app
restarts (langgraph-checkpoint-sqlite), and expose a retry entrypoint that
re-runs the last node from the checkpoint.
"""
from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.architect import architect_node
from src.agents.developer import developer_node
from src.agents.devops import devops_node
from src.agents.doc_writer import doc_writer_node
from src.agents.requirements_analyst import requirements_analyst_node
from src.agents.reviewer import reviewer_node
from src.agents.tester import tester_node
from src.graph.hitl import human_approval_node
from src.graph.state import AGENT_ORDER, ProjectState
from src.graph.supervisor import FINISH, HUMAN_APPROVAL, route_from_supervisor, supervisor_node

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


def build_graph():
    graph = StateGraph(ProjectState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node(HUMAN_APPROVAL, human_approval_node)
    for name, node in AGENT_NODES.items():
        graph.add_node(name, node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {**{name: name for name in AGENT_NODES}, HUMAN_APPROVAL: HUMAN_APPROVAL, FINISH: END},
    )
    # Hub-and-spoke: every worker reports back to the supervisor.
    for name in AGENT_NODES:
        graph.add_edge(name, "supervisor")
    graph.add_edge(HUMAN_APPROVAL, "supervisor")

    return graph.compile(checkpointer=InMemorySaver())


@lru_cache(maxsize=1)
def get_app():
    """Compiled graph singleton (cached across Streamlit reruns)."""
    return build_graph()
