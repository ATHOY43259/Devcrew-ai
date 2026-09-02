# DevCrew AI — Multi-Agent Software Engineering Team

A supervisor-led AI workforce that turns a plain-English project request into
requirements, architecture, **reviewed and tested code**, documentation, and
deployment files — with a live Streamlit dashboard and human-in-the-loop
approval. Built with **LangGraph** for the *Interactive Multi-Agent AI
System* assignment.

**Live demo:** https://devcrew-ai.streamlit.app/

![Architecture](docs/architecture.png)

## Team

| Member | Name | GitHub | Module |
|---|---|---|---|
| Member 1 | Athoy Kanti Ray | [@ATHOY43259](https://github.com/ATHOY43259) | Orchestration: supervisor, graph, HITL, checkpoints (`src/graph/`) |
| Member 2 | Pritom Sarker | _add username_ | Planning agents + RAG memory (`requirements_analyst`, `architect`, `doc_writer`, `src/memory/`, web search) |
| Member 3 | Kazi Safat Nawaz | _add username_ | Build-loop agents + tools (`developer`, `reviewer`, `tester`, `devops`, `src/tools/`) |
| Member 4 | Pranta Sen Gupta | _add username_ | UI + observability (`ui/`, `src/observability/`) |

## Quick start

```bash
git clone <this repo> && cd devcrew-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Mock mode (default, no API key, $0):** runs the whole pipeline on canned
outputs — including one full Reviewer -> Developer rework loop — so you can
demo the system and develop the UI for free.

```bash
streamlit run ui/app.py          # dashboard at http://localhost:8501
python run_cli.py                # or in the terminal
python -m pytest -q              # smoke tests
```

**Live mode:** put your key in `.env`, set `MOCK_MODE=0`, and run the same
commands. All 7 agents, the LLM-assisted supervisor, the Chroma RAG memory,
and web search are fully implemented — live mode runs the real pipeline
end to end, not just the Requirements Analyst.

## What the dashboard shows

Agent workflow status, live execution trace, agent-to-agent communication
history, the LangGraph execution graph, token usage + estimated API cost,
execution logs and errors (also on disk in `logs/run.log`), a memory viewer
(shared state + vector knowledge base), human-in-the-loop approve/reject
controls, and the final report with a downloadable zip of the generated
project.

## The seven agents

| Agent | Role | Notable |
|---|---|---|
| Requirements Analyst | writes the SRS from the request | does a real web search first, stores the spec in the vector KB |
| Software Architect | tech stack, components, API design | classifies STATIC FRONTEND vs FULL-STACK before designing |
| Developer | writes the code files | JSON, syntax and CSS validators with one automatic retry |
| Code Reviewer | approves or rejects the code | verdict parsed from the first line; rejection loops back |
| QA / Tester | verifies the code | **makes no LLM call** — runs real pytest in a subprocess |
| Documentation Writer | user guide + API reference | works from the final code and architecture |
| DevOps Engineer | Dockerfile + CI workflow | packaged only after a human approves deployment |

All seven are coordinated by the **Supervisor** (`src/graph/supervisor.py`),
which re-decides the route from the shared state after every step.

## How it maps to the rubric

| Rubric item | Where |
|---|---|
| Multi-agent architecture (20) | Supervisor + 7 agents, hub-and-spoke LangGraph (`src/graph/build_graph.py`, `docs/architecture.md`) |
| Agent collaboration (15) | Reviewer->Developer and Tester->Developer rework loops; three Human->Agent loops (requirements, pre-deployment, post-finish modification); `agent_messages` history |
| User interface (15) | `ui/app.py` — 8-view Streamlit dashboard + HITL sidebar |
| Tool integration (10) | web search (`src/tools/web_search.py`), sandboxed pytest runner (`src/tools/code_exec.py`), OpenAI or Gemini API (`LLM_PROVIDER` in `.env`) |
| Memory (10) | shared `ProjectState` + SQLite checkpointer (short-term), Chroma vector KB (`src/memory/`) (long-term) |
| Logging & observability (10) | `src/observability/` — state logs, `logs/run.log`, per-run JSONL, per-agent token/cost tracking |
| Innovation (10) | mock-mode demo fallback, mechanical CSS/syntax validators, max-revision guardrails with honest bypass reporting, post-finish modification loop |

## Repository layout

```
src/graph/          state contract, supervisor, HITL, graph wiring
src/agents/         one file per agent (see base.py for the pattern)
src/tools/          web search, sandboxed code execution
src/memory/         Chroma vector knowledge base (RAG)
src/observability/  logging + token/cost tracking
src/mock/           canned outputs for mock mode
ui/app.py           Streamlit dashboard
tests/              smoke tests (run in mock mode)
docs/               architecture diagram, code walkthrough, demo script, slides
run_cli.py          terminal runner
```

## Documentation

| File | What it is |
|---|---|
| `docs/architecture.md` | architecture write-up + Mermaid source for the diagram |
| `docs/CODE_WALKTHROUGH.md` | per-member walkthrough of every module and how data flows |
| `docs/DEMO_SCRIPT.md` | live demo run of show + prepared answers to likely questions |
| `docs/DevCrew_AI_Presentation.pptx` | presentation slides |
| `CLAUDE.md` | team conventions and module ownership |

## Development workflow

Branch `feat/<module>` -> commit small -> PR -> teammate review -> merge.
Everyone commits with their own GitHub identity. `CLAUDE.md` holds the
conventions that our Claude Code sessions (and humans) follow; run
`python -m pytest -q` before every commit.
