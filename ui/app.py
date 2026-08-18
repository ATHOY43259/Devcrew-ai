"""DevCrew AI — Streamlit dashboard shell. Owner: Member 4.

Run from the repo root:  streamlit run ui/app.py

Every rubric UI item has a tab or control below: live incremental trace
(st.status), token/cost charts, human-in-the-loop approve/reject, a
checkpoint-backed pause/retry control (Member 1's get_history /
retry_last_step), and colored agent status cards.
"""
import io
import sys
import uuid
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command  # noqa: E402

from src import config  # noqa: E402
from src.graph.build_graph import get_app, get_history, retry_last_step  # noqa: E402
from src.graph.state import AGENT_ORDER  # noqa: E402
from src.observability.token_tracker import totals  # noqa: E402

st.set_page_config(page_title="DevCrew AI", page_icon=":hammer_and_wrench:", layout="wide")

# ----------------------------------------------------------------- session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
    st.session_state.events = []          # raw stream events, for the trace tab
    st.session_state.pending = None       # interrupt payload awaiting a human

app = get_app()

NON_ARTIFACT_KEYS = ("agent_messages", "logs", "token_usage")


def graph_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def current_state() -> dict:
    if not st.session_state.thread_id:
        return {}
    snapshot = app.get_state(graph_config())
    return snapshot.values if snapshot else {}


def _consume(stream, status=None) -> None:
    """Drain a graph stream into session state, writing each step live into
    `status` (an st.status container) as it arrives."""
    for event in stream:
        st.session_state.events.append(event)
        for node, update in event.items():
            if node == "__interrupt__":
                st.session_state.pending = event["__interrupt__"][0].value
                if status:
                    status.write("Paused — waiting for human input.")
            elif status:
                keys = ", ".join(k for k in (update or {}) if k not in NON_ARTIFACT_KEYS) or "-"
                status.write(f"**{node}** wrote: `{keys}`")


def advance(payload) -> None:
    """Stream the graph until it finishes or pauses for a human, updating
    the UI live as each agent reports back (Streamlit's st.status flushes
    incrementally within a single run)."""
    st.session_state.pending = None
    with st.status("Agents working...", expanded=True) as status:
        _consume(app.stream(payload, graph_config(), stream_mode="updates"), status)
        if st.session_state.pending:
            status.update(label="Waiting for human approval", state="error")
        else:
            status.update(label="Done", state="complete")


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
    if st.button("Run pipeline", type="primary", width='stretch'):
        start_run(request)
        st.rerun()
    if st.button("Reset", width='stretch'):
        st.session_state.thread_id = None
        st.session_state.events = []
        st.session_state.pending = None
        st.rerun()

    st.divider()
    st.subheader("Human-in-the-loop")
    if st.session_state.pending:
        st.warning(st.session_state.pending.get("question", "Approval needed"))
        if st.button("Approve", type="primary", width='stretch'):
            advance(Command(resume={"action": "approve"}))
            st.rerun()
        feedback = st.text_input("Feedback if rejecting")
        if st.button("Reject with feedback", width='stretch'):
            advance(Command(resume={"action": "reject", "feedback": feedback}))
            st.rerun()
    else:
        st.caption("No approval pending. The graph pauses here when an agent needs you.")

    if st.session_state.thread_id:
        st.divider()
        st.subheader("Checkpoints")
        history = get_history(st.session_state.thread_id)
        st.caption(f"{len(history)} checkpoint(s) saved for this run (SQLite-backed).")
        if st.button("Retry last step", width='stretch',
                      help="Re-runs the last pending node from its checkpoint, "
                           "useful if an agent failed or produced a bad result."):
            try:
                with st.status("Retrying last step...", expanded=True) as status:
                    _consume(retry_last_step(st.session_state.thread_id), status)
                    status.update(label="Retry complete", state="complete")
            except RuntimeError as error:
                st.error(str(error))
            st.rerun()

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
        with col.container(border=True):
            st.caption(agent.replace("_", " ").title())
            if done:
                st.markdown(":green[**done**]")
            elif agent == next_agent:
                st.markdown(":blue[**next**]")
            else:
                st.markdown(":gray[waiting]")
    if state.get("supervisor_plan"):
        st.info(f"Supervisor: {state['supervisor_plan']}")
    approvals = state.get("approvals", [])
    if approvals:
        st.caption(f"Human approvals granted so far: {', '.join(approvals)}")

with tabs[1]:
    st.subheader("Live execution trace")
    st.caption("Populated live while the pipeline runs (see the sidebar's "
               "'Agents working...' status panel), and replayed here after each rerun.")
    if not st.session_state.events:
        st.caption("Run the pipeline to see each graph step here.")
    for i, event in enumerate(st.session_state.events):
        for node, update in event.items():
            if node == "__interrupt__":
                st.warning(f"step {i}: paused — waiting for human input")
            else:
                keys = ", ".join(k for k in (update or {}) if k not in NON_ARTIFACT_KEYS) or "-"
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
        df = pd.DataFrame(
            [{"agent": agent, **vals} for agent, vals in usage.items()]
        ).set_index("agent")
        st.dataframe(df, width='stretch')
        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("Tokens by agent")
            st.bar_chart(df[["input_tokens", "output_tokens"]])
        with col_b:
            st.caption("Estimated cost by agent (USD)")
            st.bar_chart(df[["cost_usd"]])
    else:
        st.caption("No token usage yet (mock mode costs $0). "
                   "Run with MOCK_MODE=0 and an API key to see real numbers.")
    st.metric("Run total", f"${run_totals['cost_usd']:.4f}")

with tabs[5]:
    st.subheader("Execution logs & errors")
    logs = state.get("logs", [])
    level = st.selectbox("Level filter", ["ALL", "INFO", "WARNING", "ERROR"])
    shown = [l for l in logs if level == "ALL" or l["level"] == level]
    st.dataframe(shown, width='stretch')
    errors = [l for l in logs if l["level"] == "ERROR"]
    if errors:
        st.error(f"{len(errors)} error(s) this run — see rows above.")
    st.caption("Also written to logs/run.log (human-readable) and "
               "logs/run_<start time>.jsonl (JSON Lines, one file per app run).")

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
    st.markdown("**Long-term memory** — vector knowledge base (Chroma, local embeddings):")
    try:
        from src.memory.knowledge_base import all_documents
        docs = all_documents()
        if docs:
            for doc in docs:
                st.json(doc)
        else:
            st.caption("Empty — the knowledge base fills up as agents run in live mode "
                       "(mock mode doesn't call the LLM, so it never writes to it).")
    except Exception as error:  # noqa: BLE001 — surface KB errors without crashing the dashboard
        st.caption(f"Knowledge base unavailable: {error}")

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
