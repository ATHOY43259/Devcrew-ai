"""DevCrew AI — Streamlit dashboard shell. Owner: Member 4.

Run from the repo root:  streamlit run ui/app.py

Every rubric UI item has a tab or control below, working at a basic level.
TODO(Member 4) markers show where to polish:
  - live incremental streaming (st.fragment / st.write_stream)
  - charts for token usage + cost over time
  - pause + retry controls (with Member 1's checkpoint API)
  - nicer agent status cards, colors, icons
"""
import io
import sys
import uuid
import zipfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command  # noqa: E402

from src import config  # noqa: E402
from src.graph.build_graph import get_app  # noqa: E402
from src.graph.state import AGENT_ORDER  # noqa: E402
from src.observability.token_tracker import totals  # noqa: E402

st.set_page_config(page_title="DevCrew AI", page_icon=":hammer_and_wrench:", layout="wide")

# ----------------------------------------------------------------- session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
    st.session_state.events = []          # raw stream events, for the trace tab
    st.session_state.pending = None       # interrupt payload awaiting a human

app = get_app()


def graph_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def current_state() -> dict:
    if not st.session_state.thread_id:
        return {}
    snapshot = app.get_state(graph_config())
    return snapshot.values if snapshot else {}


def advance(payload) -> None:
    """Stream the graph until it finishes or pauses for a human.
    TODO(Member 4): make this incremental so the trace updates live."""
    with st.spinner("Agents working..."):
        st.session_state.pending = None
        for event in app.stream(payload, graph_config(), stream_mode="updates"):
            st.session_state.events.append(event)
            if "__interrupt__" in event:
                st.session_state.pending = event["__interrupt__"][0].value


def start_run(request: str) -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.events = []
    advance({"project_request": request})


# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("DevCrew AI")
    st.caption("Multi-agent software engineering team")
    mode = "MOCK (canned outputs, $0)" if config.MOCK_MODE else f"LIVE — {config.OPENAI_MODEL}"
    st.info(f"Mode: {mode}")

    request = st.text_area(
        "Project request",
        value="Build a to-do list REST API with Flask",
        height=100,
    )
    if st.button("Run pipeline", type="primary", use_container_width=True):
        start_run(request)
        st.rerun()
    if st.button("Reset", use_container_width=True):
        st.session_state.thread_id = None
        st.session_state.events = []
        st.session_state.pending = None
        st.rerun()

    st.divider()
    st.subheader("Human-in-the-loop")
    if st.session_state.pending:
        st.warning(st.session_state.pending.get("question", "Approval needed"))
        if st.button("Approve", type="primary", use_container_width=True):
            advance(Command(resume={"action": "approve"}))
            st.rerun()
        feedback = st.text_input("Feedback if rejecting")
        if st.button("Reject with feedback", use_container_width=True):
            advance(Command(resume={"action": "reject", "feedback": feedback}))
            st.rerun()
    else:
        st.caption("No approval pending. The graph pauses here when an agent needs you.")
        # TODO(Member 4 + Member 1): pause / resume / retry-last-step buttons
        # using the checkpointer history (app.get_state_history).

state = current_state()

# ------------------------------------------------------------- header row
c1, c2, c3, c4, c5 = st.columns(5)
run_totals = totals(state.get("token_usage", {}))
if not st.session_state.thread_id:
    status_text = "idle"
elif st.session_state.pending:
    status_text = "waiting for human"
elif state.get("final_report"):
    status_text = "finished"
else:
    status_text = "running"
c1.metric("Status", status_text)
c2.metric("Messages", len(state.get("agent_messages", [])))
c3.metric("Rework rounds", state.get("revision_count", 0))
c4.metric("Tokens", f"{run_totals['input_tokens'] + run_totals['output_tokens']:,}")
c5.metric("Est. cost (USD)", f"${run_totals['cost_usd']:.4f}")

if st.session_state.pending:
    with st.expander("Document waiting for your approval", expanded=True):
        st.markdown(st.session_state.pending.get("document", ""))

# ------------------------------------------------------------------- tabs
tabs = st.tabs(
    ["Dashboard", "Live trace", "Communications", "Graph", "Tokens & cost",
     "Logs", "Memory", "Final report"]
)

ARTIFACT_OF = {
    "requirements_analyst": "requirements_doc",
    "architect": "architecture_doc",
    "developer": "code_files",
    "reviewer": "review_feedback",
    "tester": "test_report",
    "doc_writer": "documentation",
    "devops": "deployment_files",
}

with tabs[0]:
    st.subheader("Agent workflow status")
    next_agent = state.get("next_agent", "")
    cols = st.columns(len(AGENT_ORDER))
    for col, agent in zip(cols, AGENT_ORDER):
        done = bool(state.get(ARTIFACT_OF[agent]))
        if agent == "developer":
            done = bool(state.get("code_files"))
        icon = "done" if done else ("next" if agent == next_agent else "waiting")
        col.metric(agent.replace("_", " ").title(), icon)
    if state.get("supervisor_plan"):
        st.info(f"Supervisor: {state['supervisor_plan']}")

with tabs[1]:
    st.subheader("Live execution trace")
    if not st.session_state.events:
        st.caption("Run the pipeline to see each graph step here.")
    for i, event in enumerate(st.session_state.events):
        for node, update in event.items():
            if node == "__interrupt__":
                st.warning(f"step {i}: paused — waiting for human input")
            else:
                keys = ", ".join(k for k in (update or {}) if k not in
                                 ("agent_messages", "logs", "token_usage")) or "-"
                st.text(f"step {i:>3}  {node:<22} wrote: {keys}")

with tabs[2]:
    st.subheader("Agent communication history")
    for message in state.get("agent_messages", []):
        st.markdown(
            f"`{message['timestamp']}` **{message['from_agent']}** -> "
            f"**{message['to_agent']}**: {message['content']}"
        )

with tabs[3]:
    st.subheader("Execution graph (LangGraph)")
    mermaid_src = app.get_graph().draw_mermaid()
    try:
        st.image(app.get_graph().draw_mermaid_png())  # needs internet (mermaid.ink)
    except Exception:
        st.caption("PNG rendering unavailable offline — Mermaid source below "
                   "(paste into mermaid.live).")
    st.code(mermaid_src, language="text")

with tabs[4]:
    st.subheader("Token usage & estimated API cost")
    usage = state.get("token_usage", {})
    if usage:
        rows = [
            {"agent": agent, **vals} for agent, vals in usage.items()
        ]
        st.dataframe(rows, use_container_width=True)
    else:
        st.caption("No token usage yet (mock mode costs $0). "
                   "Run with MOCK_MODE=0 and an API key to see real numbers.")
    st.metric("Run total", f"${run_totals['cost_usd']:.4f}")
    # TODO(Member 4): add a per-agent bar chart + cumulative cost line chart.

with tabs[5]:
    st.subheader("Execution logs & errors")
    logs = state.get("logs", [])
    level = st.selectbox("Level filter", ["ALL", "INFO", "WARNING", "ERROR"])
    shown = [l for l in logs if level == "ALL" or l["level"] == level]
    st.dataframe(shown, use_container_width=True)
    errors = [l for l in logs if l["level"] == "ERROR"]
    if errors:
        st.error(f"{len(errors)} error(s) this run — see rows above.")
    st.caption("Also written to logs/run.log on disk.")

with tabs[6]:
    st.subheader("Memory viewer")
    st.markdown("**Short-term memory** — the shared graph state (checkpointed per thread):")
    for key in ("requirements_doc", "architecture_doc", "review_feedback",
                "test_report", "documentation"):
        if state.get(key):
            with st.expander(key):
                st.markdown(state[key])
    if state.get("code_files"):
        with st.expander(f"code_files ({len(state['code_files'])} files)"):
            for path, content in state["code_files"].items():
                st.markdown(f"**`{path}`**")
                st.code(content, language="python")
    st.markdown("**Long-term memory** — vector knowledge base:")
    try:
        from src.memory.knowledge_base import all_documents
        for doc in all_documents():
            st.json(doc)
    except NotImplementedError:
        st.caption("Chroma knowledge base not wired yet — Member 2 implements "
                   "src/memory/knowledge_base.py, then documents appear here.")

with tabs[7]:
    st.subheader("Final report & deliverables")
    if state.get("final_report"):
        st.markdown(state["final_report"])
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            for path, content in {**state.get("code_files", {}),
                                  **state.get("deployment_files", {})}.items():
                bundle.writestr(path, content)
            bundle.writestr("REPORT.md", state["final_report"])
            if state.get("documentation"):
                bundle.writestr("README.md", state["documentation"])
        st.download_button("Download generated project (.zip)", buffer.getvalue(),
                           file_name="generated_project.zip")
    else:
        st.caption("The report appears when the supervisor finishes the pipeline.")
