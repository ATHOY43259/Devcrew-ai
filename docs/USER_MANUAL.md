# DevCrew AI — User Manual

This is the end-user guide: how to install, configure, and run DevCrew AI, and
what every part of the dashboard does. For how the code is built, see
[`docs/CODE_WALKTHROUGH.md`](CODE_WALKTHROUGH.md); for the architecture, see
[`docs/architecture.md`](architecture.md).

**Live demo:** https://devcrew-ai.streamlit.app/ (runs in mock mode — no API
key needed, $0 cost).

---

## 1. What it does

DevCrew AI turns a one-sentence project request (e.g. *"Build a to-do list
REST API with Flask"*) into a working, reviewed, tested, documented, and
deployable software project. A supervisor agent routes the request through
seven specialist agents — Requirements Analyst, Architect, Developer,
Reviewer, Tester, Doc Writer, DevOps — looping back to the Developer whenever
the Reviewer or Tester rejects the work, and pausing three times for a human
to approve before continuing.

## 2. Installing it

Requires **Python 3.11+**.

```bash
git clone https://github.com/ATHOY43259/Devcrew-ai.git
cd devcrew-ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Configuring it (`.env`)

| Variable | Default | What it does |
|---|---|---|
| `MOCK_MODE` | `1` | `1` runs the whole pipeline on canned outputs — no API key, $0 cost. `0` calls a real LLM. |
| `LLM_PROVIDER` | `openai` | `openai` or `gemini`. Gemini has a free tier ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) with no billing card required. |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | — | Your key for whichever provider you selected. |
| `OPENAI_MODEL` / `GEMINI_MODEL` | `gpt-4o-mini` / `gemini-flash-lite-latest` | Which model to call. |
| `MAX_REVISIONS` | `2` | Max Developer rework rounds triggered by Reviewer/Tester feedback before the pipeline gives up and reports the failure. |
| `PRICE_PER_1M_INPUT` / `PRICE_PER_1M_OUTPUT` | `0.15` / `0.60` | USD per 1M tokens, used only for the cost estimate in the dashboard — update to match your actual provider/model. |

If no API key is set for the selected provider, the app forces `MOCK_MODE`
back on automatically, so it never crashes on startup.

## 4. Running it

**Dashboard (recommended):**

```bash
streamlit run ui/app.py
```

Opens at `http://localhost:8501`.

**Terminal, no UI:**

```bash
python run_cli.py                              # default demo request, asks for approval interactively
python run_cli.py --auto-approve                # skips all human approval prompts, for quick checks
python run_cli.py "Build a URL shortener API"   # your own request
```

**Tests:**

```bash
python -m pytest -q
```

## 5. Using the dashboard

### 5.1 Sidebar — start a run

- **Mode banner** at the top tells you whether you're in `MOCK` or `LIVE`
  mode, and which provider/model is active in live mode.
- **Quick start** — one-click buttons that fill in a ready-made project
  request, if you don't want to type your own.
- **Project request** — a free-text box for describing what you want built.
- **Run pipeline** — starts a new run on a fresh thread.
- **Reset** — clears the current run from the dashboard (does not delete the
  saved checkpoint; you can still resume it later if you have the thread ID).

### 5.2 Human-in-the-loop

The pipeline pauses at up to three points and waits for you:

1. **Requirements approval** — before the Architect starts, review what the
   Requirements Analyst understood from your request.
2. **Modification approval** — after the project finishes, you can optionally
   ask for a change (see §5.9); it re-enters the loop and pauses again for
   approval on the result.
3. **Deployment approval** — the final gate, before the project is marked
   done and the deployment files are produced.

When paused, the sidebar shows the question being asked and the document to
review. Click **Approve** to continue, or type feedback and click **Reject
with feedback** to send it back for revision.

### 5.3 Checkpoints

Every step is saved to a local SQLite file (`checkpoints.sqlite`), so a run
survives an app restart. Click **Retry last step** to re-run the last pending
node from its checkpoint — useful if an agent failed or produced a bad
result, without restarting the whole pipeline.

### 5.4 Dashboard tab

Colored status cards for each agent (idle / running / done / error), plus
header metrics: overall status, message count, and running token/cost
totals. Click any header metric to jump straight to its detail tab.

### 5.5 Live trace tab

A step-by-step, real-time feed of what's happening as the pipeline runs —
which agent is active, what it's doing, and the supervisor's routing
decision after each step.

### 5.6 Communications tab

The full agent-to-agent message history — every message any agent sent to
another (including the supervisor), in order.

### 5.7 Graph tab

A visualization of the LangGraph execution graph itself: the supervisor at
the center, the seven agents and three human-approval gates around it, and
the routing edges between them.

### 5.8 Tokens & cost tab

Per-agent and running-total token usage (input/output) and the estimated USD
cost, computed from the `PRICE_PER_1M_*` settings in your `.env`.

### 5.9 Logs tab

The raw execution log for the run (also written to `logs/run.log` on disk),
including any errors.

### 5.10 Memory tab

A viewer into the shared long-term knowledge base — the Chroma vector store
that agents read from and write to across the run (e.g. requirements,
architecture decisions) — so you can see exactly what's stored and searchable.

### 5.11 Final report tab

The finished deliverable: a summary report and a **downloadable zip** of the
generated project (source files, tests, docs, deployment files). From here
you can also **submit an optional modification** request, which re-enters
the pipeline and pauses at a fresh approval gate once it's done.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| App won't start / import errors | Confirm you're on Python 3.11+ and ran `pip install -r requirements.txt` inside the activated venv. |
| Pipeline does nothing / instant canned output | You're in mock mode (`MOCK_MODE=1`). Set it to `0` and add a real API key in `.env` for live mode. |
| "unsupported version of sqlite3" on the Memory tab (cloud deploys only) | Already handled for Streamlit Community Cloud via `pysqlite3-binary` — see `requirements.txt` and the shim at the top of `ui/app.py`. Not an issue for local runs. |
| Run seems stuck | Check the sidebar — it's very likely paused at a human-in-the-loop gate waiting for **Approve** / **Reject**. |
| Want to start over | Click **Reset** in the sidebar, or delete `checkpoints.sqlite` for a completely clean slate. |

## 7. Where things are, for reference

```
src/graph/          state contract, supervisor, HITL, graph wiring
src/agents/         one file per agent
src/tools/          web search, sandboxed code execution
src/memory/         Chroma vector knowledge base (RAG)
src/observability/  logging + token/cost tracking
src/mock/           canned outputs for mock mode
ui/app.py           Streamlit dashboard
tests/              smoke tests (run in mock mode)
docs/               this manual + architecture doc + diagram
run_cli.py          terminal runner
```
