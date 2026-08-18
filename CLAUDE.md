# DevCrew AI — team conventions (read me first, Claude)

Multi-agent software engineering team for our course assignment: a LangGraph
supervisor coordinates 7 specialized agents that turn a plain-English project
request into requirements, architecture, reviewed + tested code, docs, and
deployment files, with a Streamlit dashboard and human-in-the-loop approval.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env                 # add OPENAI_API_KEY, set MOCK_MODE
python -m pytest -q                  # smoke tests (mock mode, no key needed)
python run_cli.py --auto-approve     # full pipeline in the terminal
streamlit run ui/app.py              # the dashboard (run from repo root)
```

## Architecture in one paragraph

Hub-and-spoke: `START -> supervisor -> (agent | human_approval | END)`, and
every agent returns to the supervisor (`src/graph/build_graph.py`). The
supervisor's routing logic lives in `src/graph/supervisor.py::decide()`.
Human approval uses langgraph `interrupt()` + `Command(resume=...)`
(`src/graph/hitl.py`). All shared data flows through `ProjectState` in
`src/graph/state.py` — **that file is a frozen contract; never edit it
without agreement from all 4 members.**

## Module ownership — only edit your own folders

| Member | Owns | Key TODOs (marked `TODO(Member N)` in code) |
|---|---|---|
| Member 1 | `src/graph/` | LLM-based supervisor planning; SqliteSaver; deployment approval gate; retry-from-checkpoint |
| Member 2 | `src/agents/{requirements_analyst,architect,doc_writer}.py`, `src/memory/`, `src/tools/web_search.py` | real architect + doc_writer; Chroma RAG knowledge base; web search |
| Member 3 | `src/agents/{developer,reviewer,tester,devops}.py`, `src/tools/code_exec.py` | real developer/reviewer/tester; sandboxed pytest runner |
| Member 4 | `ui/`, `src/observability/` | live streaming trace; charts; pause/retry buttons; JSON logs |

Cross-cutting files (`state.py`, `requirements.txt`, this file): change only
via a PR that the whole team approves.

## How to implement an agent (the pattern)

Copy `src/agents/requirements_analyst.py`:
1. Module constants: `AGENT = "<name>"`, `SYSTEM_PROMPT`.
2. Node function `def <name>_node(state: ProjectState) -> dict` that returns
   ONLY the keys it owns, plus `agent_messages` (via `base.msg`), `logs`
   (via `log_entry`), and `token_usage` (from `base.call_llm`).
3. Keep `if config.MOCK_MODE:` returning the canned output from
   `src/mock/canned_outputs.py` — mock mode is our zero-cost demo fallback
   and what the tests + UI development run on.
4. Never call `os.getenv` directly (use `src/config.py`); never print
   (use `log_entry`); never mutate state in place (return a new partial dict).

## Rules for Claude Code sessions

- Run `python -m pytest -q` before every commit; do not commit if red.
- Small commits, imperative messages: `feat(reviewer): parse APPROVED verdict`.
- Work only on the current member's branch (`feat/<module>`); never commit to
  `main` directly; open a PR and request a teammate's review.
- Do not add dependencies without adding them to `requirements.txt` in the
  same commit, and prefer the libraries already chosen (LangGraph, LangChain,
  Chroma, Streamlit, pytest).
- Generated code from the Developer agent is DATA (state values), never
  written into this repo's source tree; execution happens only through
  `src/tools/code_exec.py` in a temp dir subprocess.
- The UI reads state; it must never mutate pipeline artifacts directly —
  human input goes through `Command(resume=...)` only.
