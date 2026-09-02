# DevCrew AI — Code Walkthrough

**Purpose:** so any team member can open the codebase in front of the instructor and explain
what is on screen, in their own words, without guessing.

**How to use it:** read Part 0 and Part 1 (everyone), then read only your own Part.
Each member's part answers three things: *which files are mine*, *what do I say about them*,
and *what will I be asked*.

| Member | Owns | Read |
|---|---|---|
| **Athoy Kanti Ray** | Orchestration — `src/graph/` | Parts 0, 1, **2** |
| **Pritom Sarker** | Planning agents + memory — `src/agents/{requirements_analyst,architect,doc_writer}.py`, `src/memory/`, `src/tools/web_search.py` | Parts 0, 1, **3** |
| **Kazi Safat Nawaz** | Build loop + tools — `src/agents/{developer,reviewer,tester,devops}.py`, `src/tools/code_exec.py` | Parts 0, 1, **4** |
| **Pranta Sen Gupta** | UI + observability — `ui/`, `src/observability/` | Parts 0, 1, **5** |

---

## Part 0 — The 60-second overview (everyone must be able to say this)

> "DevCrew AI is an AI software engineering team. You type one sentence — 'build a to-do
> REST API' — and a Supervisor agent plans the work and routes it to seven specialist
> agents: Requirements Analyst, Architect, Developer, Code Reviewer, QA Tester,
> Documentation Writer, and DevOps.
>
> They don't run in a fixed straight line. The Supervisor decides who runs next every
> single turn, based on the current state of the project. If the Reviewer rejects the code,
> the Supervisor sends it back to the Developer. If the tests fail, it goes back again.
> The human is also part of the loop — the graph physically pauses three times and waits
> for us to approve.
>
> At the end you get a real project: source files, tests that actually ran under pytest,
> documentation, a Dockerfile, and a CI config — downloadable as a zip."

**The one-line technical answer:** *"It's a LangGraph state machine in a hub-and-spoke
topology, with a supervisor node doing conditional routing over a shared typed state."*

---

## Part 1 — The one idea that explains everything

If the instructor understands these two things, everything else follows.

### Idea 1: There is one shared state object, and it is the memory

Every agent is a **plain Python function** with the same shape:

```python
def some_agent_node(state: ProjectState) -> dict:
    ...
    return {"the_key_i_own": value, "agent_messages": [...], "logs": [...]}
```

It receives the whole project state, and returns **only the keys it owns**. LangGraph merges
that return value into the shared state. Agents never call each other directly and never
import each other — they communicate *through the state*. That is our agent-to-agent
communication channel.

Defined in `src/graph/state.py` as `ProjectState`. Three special fields use **reducers**
(merge rules) instead of overwriting:

| Field | Reducer | Meaning |
|---|---|---|
| `agent_messages` | `operator.add` | append-only — the full conversation history |
| `logs` | `operator.add` | append-only — every log line of the run |
| `token_usage` | `merge_usage` (custom) | sums input tokens / output tokens / USD per agent |

> Say it like this: *"An agent returns a partial dict. LangGraph merges it. Lists are
> append-only, so nothing overwrites another agent's history."*

### Idea 2: Hub-and-spoke, not a pipeline

```
START → supervisor → (one of: 7 agents | 3 approval gates | END)
        every node → back to supervisor
```

The Supervisor runs **between every single step**. That's what makes it a supervisor
architecture instead of a hardcoded pipeline: nothing is pre-scheduled, the route is
recomputed from the state each turn. Wired in `src/graph/build_graph.py`.

---

## Part 2 — Athoy: Orchestration (`src/graph/`)

**You own:** `state.py`, `supervisor.py`, `hitl.py`, `build_graph.py`
**You are the person who answers "how does the whole thing actually work".**

### 2.1 `state.py` — the contract

`ProjectState` is a `TypedDict` holding everything: the request, every artifact
(`requirements_doc`, `architecture_doc`, `code_files`, `review_feedback`, `test_report`,
`documentation`, `deployment_files`), loop counters, approvals, messages, logs, tokens.

**Say:** *"This is the frozen contract. All four of us agreed on it on day one and then built
in parallel against it. That's why we had almost no merge conflicts."*

### 2.2 `supervisor.py` — the brain (the most important file to show)

Three layers, in this order:

**a) `decide(state) -> (next_node, reason, overrides)`** — a **pure function**. No LLM, no
side effects, fully unit-testable. It's a priority ladder of "what is missing?":

```python
if not state.get("requirements_doc"):
    return "requirements_analyst", "No requirements yet — starting with the SRS.", {}
if "requirements" not in state.get("approvals", []):
    return HUMAN_APPROVAL, "SRS drafted — pausing for human approval (HITL).", {}
if not state.get("architecture_doc"):
    return "architect", "Requirements approved — designing the architecture.", {}
...
```

Note it returns a **`reason` string** — that's what the UI shows as the supervisor's plan.
The routing is explainable, not a black box.

**b) `route()`** — in live mode it *also* asks the LLM to pick the next agent, then compares:

- LLM agrees with `decide()` → proceed
- LLM disagrees → log a WARNING and **use the deterministic answer**

**Say:** *"We have LLM-assisted planning, but the state machine is the safety net. You can see
it in the logs: `LLM routing pick 'architect' disagreed with the state machine
('human_approval') — using the deterministic decision`. We deliberately do not let the LLM
skip a human approval gate."*

That single sentence is one of the strongest things you can say in the whole demo — it shows
you thought about reliability, not just wiring an LLM up.

**c) `supervisor_node()`** — calls `route()`, writes `next_agent` + `supervisor_plan` into
state, logs the transition, and at the end composes `final_report`.

**The bug worth telling them about (`review_bypassed` / `tests_bypassed`):**
after `MAX_REVISIONS` (2) failed rounds the supervisor gives up and moves on. Originally it
moved on *without* recording that it had given up — so the next turn saw the same unmet
condition and routed to the same place again: an **infinite loop**, confirmed in the server
log repeating 13+ times. Fix: `decide()` now returns a third value, `overrides`, and the
bailout branch sets `{"review_bypassed": True}`. The final report still honestly says
*"NOT APPROVED (bypassed after max revisions)"* instead of faking success.
There is a regression test for it in `tests/test_smoke.py`.

### 2.3 `hitl.py` — human-in-the-loop (three gates)

| Node | Gate | Reject behaviour |
|---|---|---|
| `human_approval_node` | approve the requirements (SRS) | clears `requirements_doc` + stores feedback → Analyst rewrites it |
| `deployment_approval_node` | approve before deployment files are made | sends feedback back to the Doc Writer |
| `modification_approval_node` | approve a change requested *after* the project finished | feedback becomes the new modification request → loop runs again |

Mechanism, in two lines:

```python
decision = interrupt({"stage": ..., "question": ..., "document": ...})   # graph PAUSES here
# ... UI later resumes with Command(resume={"action": "approve"})
```

**Say:** *"`interrupt()` suspends the graph and the checkpointer saves the state to SQLite.
The process can literally be killed and restarted — we resume the same `thread_id` and it
continues from that exact point."*

### 2.4 `build_graph.py` — the wiring

11 nodes (supervisor + 7 agents + 3 gates), `add_conditional_edges` from the supervisor
mapping node names to themselves and `FINISH → END`, and an edge from every node back to
the supervisor. Compiled with **`SqliteSaver`** on `checkpoints.sqlite`, so runs survive an
app restart. Also exposes `get_history()`, `retry_last_step()`, `resume()` — that's what the
UI's **Retry last step** button calls.

**Likely questions for Athoy**

- *Why LangGraph and not CrewAI/AutoGen?* → "We needed cyclic graphs (review loops), typed
  shared state, and built-in pause/resume with checkpointing. LangGraph gives all three
  natively; the others are more conversation-oriented."
- *Is the supervisor an LLM or if-else?* → "Both, on purpose. LLM proposes, state machine
  disposes. Show the disagreement warning in the logs."
- *Where is memory?* → "Short-term is `ProjectState` + the SQLite checkpointer; long-term is
  the Chroma vector store — Pritom's part."

---

## Part 3 — Pritom: Planning agents + memory (`requirements_analyst`, `architect`, `doc_writer`, `src/memory/`, `src/tools/web_search.py`)

**You own the "understanding and knowledge" half of the system.**

### 3.1 `requirements_analyst.py` — the reference agent (show this one)

Flow: **web search → LLM → save to vector memory**.

```python
results = web_search(request, max_results=3)     # real external tool
# ... research block appended to the prompt
doc, usage = call_llm(AGENT, SYSTEM_PROMPT, user_prompt)
add_document("requirements_doc", doc, {"agent": AGENT})   # long-term memory
```

Output: a Markdown SRS with Functional Requirements (FR1…), Non-Functional Requirements
(NFR1…), and 3–5 user stories, under 400 words.

It also consumes `human_feedback`: if the human rejected the SRS at the approval gate, that
feedback is injected into the prompt and the Analyst rewrites it. **That is a human→agent
collaboration loop**, and it is worth demonstrating live.

### 3.2 `architect.py` — classify first, then design

The Architect's first job is to decide **STATIC FRONTEND vs FULL-STACK**, and it writes that
decision into a `## Project type` section of the architecture document. Everything
downstream reads it.

**Why this exists (good story to tell):** earlier, asking for "an HTML and CSS e-commerce
dashboard" produced a Python backend with `server.py` and `database.py` — because the
prompts unconditionally demanded a backend. Now the Architect classifies first, and the
Developer and Reviewer both obey that classification. It's a real bug we found by testing
against the live API and fixed.

### 3.3 `src/tools/web_search.py`

Uses **`ddgs`** (DuckDuckGo; the older `duckduckgo-search` package is deprecated and
silently returns zero results — we hit that and switched). No API key needed.

```python
def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    # -> [{"title": ..., "url": ..., "snippet": ...}, ...]
```

**Fails soft:** network down / rate-limited / package missing → logs a WARNING and returns
`[]` instead of crashing the pipeline. You can point at a real WARNING line in the logs.

### 3.4 `src/memory/knowledge_base.py` — the long-term memory (RAG)

- **Chroma**, `PersistentClient` on disk at `./memory_store`, collection `devcrew_kb`
- Embeddings: Chroma's **built-in local ONNX MiniLM** — deliberately *not* OpenAI
  embeddings, so memory works with **no API key and no cost**
- `_chunk()`: 800 characters with 100-character overlap
- API: `add_document(doc_id, text, metadata)`, `search(query, k=3)`, `all_documents()`

`all_documents()` is what the UI's **Memory** tab renders, so you can show the instructor the
actual stored chunks.

**Say:** *"Two kinds of memory. Short-term is the shared state, checkpointed to SQLite, scoped
to one run. Long-term is the Chroma vector store, which persists on disk across runs and is
retrieved by semantic similarity."*

**Likely questions for Pritom**

- *Is this real RAG?* → "Yes: chunk, embed, persist, retrieve by similarity, feed into the
  prompt. Local embeddings rather than an API."
- *What if search returns nothing?* → "It degrades to an empty list and the agent still
  writes the SRS from the request alone. Nothing crashes."
- *Why 800/100 chunking?* → "Big enough to keep a requirement intact, overlap so a
  requirement split across a boundary is still retrievable."

---

## Part 4 — Kazi: Build agents + execution tools (`developer`, `reviewer`, `tester`, `devops`, `src/tools/code_exec.py`)

**You own the loop that makes this a *team* instead of a chain.**

### 4.1 `developer.py` — the most engineered file in the repo

The LLM returns **strict JSON**: `{"files": {"path": "content", ...}}`. Then four defensive
layers run before that code is accepted:

| Function | Job |
|---|---|
| `_extract_json(text)` | strips ```` ```json ```` fences the model adds |
| `_parse_files(text)` | finds the JSON object, uses `JSONDecoder().raw_decode()` to take **only the first complete value** and ignore trailing prose |
| `syntax_check(files)` | `compile()` every `.py` file → list of syntax errors |
| `_check_frontend_styling(files)` | catches HTML that will render unstyled |

If any check fails → **one retry**, with the specific problem pasted into the prompt.
If the *retry itself* fails to parse → log a WARNING and **ship the original valid files**
instead of crashing (we hit exactly that and fixed it).

**`_check_frontend_styling` is your best "innovation" talking point.** It catches three
distinct real failures:

1. `<link href="style.css">` but no `style.css` was generated → broken link
2. the CSS exists and is linked, but **fewer than 30% of the HTML's class names have a
   matching CSS selector** — HTML uses `.nav-link`, CSS defines `.navbar` → technically
   linked, visually raw
3. no styling of any kind — no link, no `<style>`, no CSS CDN

It skips the coverage check when Tailwind/Bootstrap CDN is used (utility classes can't be
verified locally) and ignores icon-font classes (`fa-*`) since a CDN styles those.

**Say:** *"This is a mechanical check, not the LLM grading itself. That matters — an LLM
asked 'is your CSS correct?' will say yes. Parsing the class names and comparing sets can't
be talked out of it."*

**Three modes of `developer_node`** — same function, behaviour driven by state:

| Mode | Trigger | Behaviour |
|---|---|---|
| First draft | no `code_files` | build from requirements + architecture |
| Rework | `review_feedback` or failing `test_report` | fix **only** the reported issues; resets review/test flags; `revision_count += 1` |
| Modification | `modification_pending` | apply one user-requested change to existing code; does **not** increment `revision_count` |

### 4.2 `reviewer.py`

Strict senior-reviewer prompt; the response's **first line must be `APPROVED` or
`CHANGES REQUESTED`**, and the verdict is parsed mechanically:

```python
approved = feedback.strip().upper().startswith("APPROVED")
```

That boolean is what the Supervisor routes on. It also enforces sandbox rules — and those
rules are conditional on the Architect's STATIC FRONTEND / FULL-STACK classification, so a
legitimate static site is not rejected for "missing a database".

### 4.3 `tester.py` — the agent with **no LLM at all**

```python
project_dir = write_files(code_files)      # real files on disk
passed, output = run_pytest(project_dir)   # real subprocess
```

`tests_passed` is the **pytest exit code**. Not an opinion, not a hallucination.

**Say:** *"The Tester doesn't ask a model whether the code works. It writes the generated
files to a temp directory and runs pytest in a subprocess. The pass/fail that drives the
retry loop is a real exit code."* That is the single most convincing sentence about tool use
in the whole project.

### 4.4 `src/tools/code_exec.py` — the sandbox

- `write_files(files) -> Path` — fresh `tempfile` dir prefixed `devcrew_`, creates parent dirs
- `run_pytest(dir) -> (bool, str)` — `subprocess.run([sys.executable, "-m", "pytest", "-q"])`,
  **60-second timeout**, `TimeoutExpired` handled instead of raised
- `syntax_check(files) -> List[str]` — `compile()` per file

**The security sentence:** *"Generated code is never `exec()`'d in-process. It is always
written to a fresh temp directory and run in a separate subprocess with a timeout."*

### 4.5 The collaboration loops (this is 15 marks — own it)

1. Reviewer → Developer (changes requested)
2. Tester → Developer (tests failed)
3. Human → Requirements Analyst (SRS rejected)
4. Human → Doc Writer (deployment rejected)
5. Human → Developer (post-finish modification)

Guarded by `MAX_REVISIONS = 2` so it can never loop forever.

**Likely questions for Kazi**

- *Is the code actually run?* → "Yes — show the Tester and the pytest output in the report."
- *What if the LLM returns broken JSON?* → "`raw_decode` handles trailing text; one retry;
  then fall back to the last valid version. All three happened in real runs."
- *Is running generated code dangerous?* → "Temp dir, subprocess, 60-second timeout, never
  in-process."

---

## Part 5 — Pranta: UI + observability (`ui/app.py`, `src/observability/`)

**You own everything the instructor actually looks at.** The rubric lists nine required UI
elements; you can point at each one.

### 5.1 `ui/app.py` — structure

Functions: `_set_preset_request`, `_goto`, `graph_config`, `current_state`, `_consume`,
`advance`, `start_run`, `submit_modification`.

**Sidebar:** mode badge (MOCK $0 vs live provider/model) · three quick-start presets ·
request textarea · **Run pipeline** · **Reset** · the HITL **Approve / Reject with feedback**
block · a **Checkpoints** section with **Retry last step**.

**Eight sections** (`st.segmented_control`) mapping to the rubric:

| Section | Rubric item |
|---|---|
| Dashboard | active agents + workflow status |
| Live trace | live agent execution trace |
| Communications | agent communication history |
| Graph | LangGraph execution graph (Mermaid; PNG with source fallback) |
| Tokens & cost | token usage + API cost estimation |
| Logs | execution logs + error reports (filterable by level) |
| Memory | memory viewer — shared state *and* Chroma documents |
| Final report | final output viewer + zip download + modification request |

### 5.2 How the UI drives the graph (know these three lines)

```python
app.stream(payload, graph_config(), stream_mode="updates")   # run / resume
Command(resume={"action": "approve"})                        # HITL answer
st.session_state.pending = event["__interrupt__"][0].value   # graph paused here
```

`advance()` streams events and `_consume()` writes them live into a fixed-height box —
that's the live trace. When an `__interrupt__` arrives, it's stored in `pending`, and the
sidebar renders the Approve/Reject buttons. Approving calls `advance(Command(resume=...))`
on the **same `thread_id`**, so the run continues rather than restarting.

`submit_modification()` reuses that same thread after `FINISH`, resetting the review/test
flags so the Developer→Reviewer→Tester loop runs again for the change.

### 5.3 `src/observability/logging_setup.py` — three destinations

Every `log_entry(agent, level, message)` call writes to all three at once:

1. the graph state `logs` list → the UI Logs tab
2. `logs/run.log` — human-readable, `%(asctime)s | %(levelname)-7s | %(message)s`
3. `logs/run_<RUN_ID>.jsonl` — one JSON object per line, machine-parseable, per process

**Say:** *"Structured logging, three sinks. The JSONL file is per-run so we can diff two runs."*

### 5.4 `src/observability/token_tracker.py`

`usage_delta(agent, response)` reads LangChain's `usage_metadata` (`input_tokens` /
`output_tokens`), multiplies by the per-million prices in `config.py`, and returns a
per-agent delta. The `merge_usage` reducer in `state.py` sums those deltas across the run;
`totals()` produces the header metrics. The Tokens & cost tab shows the per-agent table and
bar charts.

**Likely questions for Pranta**

- *Is the cost real?* → "It's an estimate: real token counts from the provider's response
  metadata × configurable prices in `.env`."
- *Is the trace live or after the fact?* → "Live — we stream `stream_mode='updates'` and write
  each event into the container as it arrives, then replay from session state on rerun."
- *Can you pause?* → Be honest: "The graph pauses automatically at the three approval gates
  and can be resumed or retried from a checkpoint. There is no manual 'freeze mid-agent'
  button — an agent step is a single atomic LLM call, so we pause at gates instead."

---

## Part 6 — One request, end to end (the file-by-file trace)

Useful if the instructor says *"walk me through what happens when I click Run."*

1. `ui/app.py :: start_run()` → new `thread_id` → `advance({"project_request": ...})`
2. `build_graph.py` → `START` → `supervisor`
3. `supervisor.py :: decide()` → no requirements → `"requirements_analyst"`
4. `requirements_analyst.py` → `web_search()` → `call_llm()` → `add_document()` → returns
   `requirements_doc`
5. back to `supervisor` → requirements not approved → `human_approval`
6. `hitl.py :: interrupt()` → **graph pauses**, state saved to `checkpoints.sqlite`
7. UI shows Approve/Reject → `Command(resume={"action": "approve"})`
8. `supervisor` → `architect` → classifies project type
9. `supervisor` → `developer` → JSON → syntax + styling checks → `code_files`
10. `supervisor` → `reviewer` → `CHANGES REQUESTED` → back to `developer` (`revision_count = 1`)
11. `supervisor` → `reviewer` → `APPROVED` → `tester` → real pytest → `tests_passed`
12. `supervisor` → `doc_writer` → `deployment_approval` (pause #2) → `devops`
13. `supervisor` → `FINISH` → `final_report` → UI Final report tab + zip download
14. Optional: modification request → `developer` → `reviewer` → `tester` →
    `modification_approval` (pause #3) → `FINISH` again

---

## Part 7 — Design decisions we can defend

| Decision | Why |
|---|---|
| Deterministic state machine + LLM as advisor | reliability; the LLM must never skip a human gate |
| Reducers on lists, agents return partial dicts | no agent can overwrite another's history |
| Tester runs real pytest instead of asking an LLM | a pass/fail must be a fact, not an opinion |
| Mechanical CSS/syntax validators | an LLM asked to grade itself says "looks good" |
| Local Chroma embeddings | memory works with zero API key and zero cost |
| `MOCK_MODE` | free, instant, offline demo path — and our fallback if wifi dies |
| `MAX_REVISIONS` + bypass flags | loops must terminate, and the report must not lie about it |
| SQLite checkpointer | pause/resume/retry survives a process restart |

---

## Appendix — Repository map

```
src/graph/         state.py  supervisor.py  hitl.py  build_graph.py      (Athoy)
src/agents/        base.py + one file per agent            (Members 2 & 3)
src/tools/         web_search.py (M2)   code_exec.py (M3)
src/memory/        knowledge_base.py — Chroma RAG          (Pritom)
src/observability/ logging_setup.py  token_tracker.py      (Pranta)
src/mock/          canned_outputs.py — MOCK_MODE fallback
ui/app.py          Streamlit dashboard                     (Pranta)
tests/             pytest suite (5 tests, mock mode)
docs/              architecture.md + architecture.png
run_cli.py         terminal runner
```

**Run it:**

```powershell
.venv\Scripts\streamlit.exe run ui/app.py          # dashboard
.venv\Scripts\python.exe run_cli.py --auto-approve # terminal
.venv\Scripts\python.exe -m pytest -q              # tests
```
