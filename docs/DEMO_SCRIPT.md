# DevCrew AI — Live Demo Script & Instructor Q&A Prep

Target length: **10 minutes of demo + 5 minutes of questions.**
Everyone speaks. The instructor grades individual understanding, so no one member
should narrate the whole thing.

**Speaking order:** Athoy Kanti Ray (opening, the run, both approval gates, close) →
Pritom Sarker (planning agents, web search, memory) → Kazi Safat Nawaz (the review loop,
the Tester, sandboxed execution) → Pranta Sen Gupta (observability tour, final report).

---

## Part A — Setup checklist (do this 15 minutes before, not during)

- [ ] **Do a full practice run** and leave a *finished* project on screen in a second
      browser tab. If the live run misbehaves, you switch tabs and keep talking.
- [ ] `.env` → set the API key, `MOCK_MODE=0`. Confirm quota is not exhausted.
- [ ] Delete `checkpoints.sqlite`, `logs/`, and any `generated_*` folders so the demo
      starts clean.
- [ ] Start the dashboard **before** the class starts:
      `.venv\Scripts\streamlit.exe run ui/app.py`
- [ ] Open these tabs in this order: **dashboard (localhost:8501)** · **VS Code with the repo
      open** · **the GitHub repo page** · the finished backup run.
- [ ] In VS Code, pre-open these 4 files as tabs so you never search during the demo:
      `src/graph/supervisor.py` · `src/graph/hitl.py` · `src/agents/tester.py` ·
      `src/agents/developer.py`
- [ ] VS Code: zoom text to ~150% (`Ctrl` + `+` a few times). Projectors are unforgiving.
- [ ] Know your **panic switch**: `MOCK_MODE=1` runs the whole pipeline instantly, offline,
      for free. If wifi or the API dies, say *"switching to our offline mock mode, which we
      built exactly for this"* — that reads as engineering foresight, not failure.
- [ ] Pick a demo request that is **small and visual**. Recommended:
      *"Build a to-do list REST API with Flask"* (fast, tests pass, easy to explain).

---

## Part B — The run of show

### 0. Opening — 30 seconds (Athoy)

> "Our project is DevCrew AI: a multi-agent software engineering team. One sentence of input,
> and a Supervisor coordinates seven specialist agents to produce a working, reviewed, tested,
> documented, deployable project. I'll show the architecture first, then we'll run it live."

Show `docs/architecture.png` (or the slide). Point at three things only:
the **Supervisor in the middle**, the **7 agents**, the **3 human gates**.

### 1. Start the run — 1 minute (Athoy)

Type the request in the sidebar → click **Run pipeline**.

While it runs, talk over it — don't watch silently:

> "The Supervisor is deciding who runs next after every step. Nothing here is a fixed
> pipeline. Right now it routed to the Requirements Analyst, and you can see the reason it
> gave for that decision."

### 2. Human-in-the-loop gate #1 — 1 minute (Athoy)

It pauses. **Don't approve immediately** — this is a graded feature, so show it:

> "The graph has physically paused. `interrupt()` suspended execution and the state is saved
> to SQLite. It will wait indefinitely. I could kill this process and resume the same thread
> tomorrow."

**Do the reject once** — type feedback like *"add a requirement for input validation"* →
**Reject with feedback**. Watch the Analyst rerun.

> "That's a human-to-agent feedback loop: my comment goes into the Analyst's prompt and it
> rewrites the document."

Then **Approve**.

### 3. Planning agents — 1 minute (Pritom)

Open the **Communications** tab.

> "This is agent-to-agent communication. They never call each other directly — they write to
> a shared state object and the Supervisor routes. Every message is timestamped here."

Then, from the **Logs** tab, point at a real `web_search(...)` line:

> "The Analyst does a real DuckDuckGo search before writing the spec, and the spec is embedded
> into a Chroma vector store — I'll show that in the Memory tab shortly."

### 4. The collaboration loop — 2 minutes (Kazi) ← **the highest-value moment**

Watch for the Reviewer. When it says CHANGES REQUESTED:

> "The Reviewer just rejected the Developer's code and the Supervisor is sending it back.
> This is the loop that makes it a team instead of a chain — the Developer only fixes the
> reported issues, then it's reviewed again."

Then, when the Tester runs — open `src/agents/tester.py` in VS Code:

> "Notice this agent makes **no LLM call at all**. It writes the generated files to a temp
> directory and runs pytest in a subprocess. `tests_passed` is a real exit code, not a
> model's opinion. If it fails, the Supervisor routes back to the Developer with the report."

If asked about safety, add: *"Generated code is never `exec()`'d in-process — temp dir,
subprocess, 60-second timeout."*

### 5. Gate #2 + finish — 30 seconds (Athoy)

Approve the deployment gate.

> "Second gate: nothing gets packaged for deployment without a human approving."

### 6. Observability tour — 2 minutes (Pranta)

Move fast, one sentence each. This is where the UI marks are:

- **Dashboard** — "every agent's status and the Supervisor's current plan"
- **Live trace** — "each graph step and which state keys it wrote"
- **Graph** — "the actual LangGraph topology, rendered from the compiled graph — not a
  drawing we made"
- **Tokens & cost** — "real token counts from the provider's response metadata, priced per
  agent"
- **Logs** — filter to WARNING — "structured logs, also written to `logs/run.log` and a
  per-run JSONL file"
- **Memory** — "short-term shared state on top, and below it the Chroma vector store — our
  long-term memory, persisted on disk across runs"

### 7. Final report + the modification loop — 1.5 minutes (Pranta → Kazi)

Open **Final report**. Show the report, click **download the zip**, open one generated file.

Then the feature to end on:

> "The project is finished — but we can still change it. I'll ask for a modification."

Type e.g. *"add a priority field to each todo"* → **Submit modification**.

> "That reuses the same thread and runs Developer → Reviewer → Tester again for just this
> change, then pauses at a third approval gate. If I reject with feedback, it iterates
> instead of forcing an all-or-nothing choice."

### 8. Close — 30 seconds (Athoy)

> "Supervisor plus seven agents, five collaboration loops, three human gates, real tool use —
> web search, sandboxed pytest, vector RAG — full observability, and it all runs offline in
> mock mode at zero cost. Happy to take questions."

---

## Part C — Question bank

Short spoken answers. Say the first sentence, stop, and let them ask for more.

### Architecture

**Why LangGraph instead of CrewAI or AutoGen?**
> "We needed cycles — the review loop — plus typed shared state and built-in pause/resume.
> LangGraph gives all three natively. CrewAI and AutoGen are more conversation-oriented; our
> problem is a state machine."

**Is your supervisor just if-else statements?**
> "It's both, deliberately. `decide()` is a deterministic state machine, and in live mode the
> LLM also proposes the next agent. If they disagree we log a warning and trust the state
> machine. Here's one in the logs — the LLM tried to skip a human approval gate. We don't let
> it."

**Why hub-and-spoke instead of agents calling each other?**
> "One place makes routing decisions, so the workflow is explainable and testable. `decide()`
> is a pure function with unit tests. If agents called each other directly, no single
> component would know the state of the project."

**How do agents communicate?**
> "Through the shared state. Each returns a partial dict of only the keys it owns; LangGraph
> merges it. Message and log lists are append-only via reducers, so no agent can overwrite
> another's history." *(Show the Communications tab.)*

### Memory

**What are your two kinds of memory?**
> "Short-term is the `ProjectState` object plus the SQLite checkpointer — scoped to one run,
> survives restarts. Long-term is a Chroma vector store on disk, retrieved by semantic
> similarity, and it persists across runs."

**Is this actually RAG?**
> "Yes — chunk at 800 characters with 100 overlap, embed, persist, retrieve by similarity,
> inject into the prompt. We use Chroma's local ONNX embedding model so it needs no API key."

### Tools

**What real tools does it use?**
> "Three. DuckDuckGo web search via `ddgs`; sandboxed code execution that runs pytest in a
> subprocess; and the Chroma vector database. Plus the LLM API itself."

**Does it really run the generated code?**
> "Yes. Files to a temp directory, `pytest -q` in a subprocess with a 60-second timeout, and
> `tests_passed` is the exit code." *(Open `tester.py`.)*

**Isn't running LLM-generated code dangerous?**
> "It's never `exec()`'d in our process. Fresh temp directory, separate subprocess, hard
> timeout. For a course project that's the right boundary; production would use a container."

### Reliability

**What happens if the LLM call fails?**
> "Two retries with backoff, then a `RuntimeError` that the supervisor logs — the app doesn't
> crash. And if the model returns malformed JSON, `raw_decode` takes the first valid object;
> if the retry also fails we ship the last valid version instead of crashing."

**What's the hardest bug you fixed?** ← *rehearse this one, it's your best answer*
> "An infinite loop in the supervisor. After max revisions it gave up and moved on, but never
> recorded that it had given up — so the next turn saw the same unmet condition and routed to
> the same place again. We found it in the server log repeating thirteen times in ninety
> seconds. The fix was to have `decide()` return an `overrides` dict that sets a
> `review_bypassed` flag, and the final report says 'bypassed after max revisions' instead of
> falsely reporting success. There's a regression test for it."

**What stops it looping forever?**
> "`MAX_REVISIONS`, default 2. After that it proceeds and flags the unresolved issues honestly
> in the report."

### UI / observability

**Can you pause execution?** *(be honest)*
> "It pauses automatically at the three approval gates, and from the checkpoints we can resume
> or retry the last step. There's no freeze-mid-agent button — an agent step is one atomic LLM
> call — so we pause at gates instead."

**Is the cost figure real?**
> "It's an estimate from real numbers: token counts come from the provider's response
> metadata, multiplied by per-million prices set in `.env`."

**Is that graph picture generated or drawn?**
> "Generated from the compiled LangGraph object at runtime, so it can't drift from the code."

### The uncomfortable ones

**Did you write this or did AI write it?** ← *answer calmly and honestly*
> "We used AI assistance for parts of the implementation — the assignment is about building an
> AI workforce, so that felt consistent. The design decisions are ours and we can defend every
> one: hub-and-spoke over direct agent calls, deterministic routing over trusting the LLM,
> mechanical validators instead of self-grading, real pytest instead of asking a model.
> Ask me about any file and I'll walk you through it."

Then *invite* the follow-up — it converts suspicion into a chance to show competence.

**Why is this not just a chatbot with prompts?**
> "Three reasons: cyclic control flow with feedback loops, agents with distinct tools and
> responsibilities communicating through shared state, and human gates that suspend and resume
> execution. A chatbot has none of those — it can't reject its own work and retry."

**What would you do with more time?**
> "Parallel agents — docs and deployment don't need to be sequential. Persisting the vector
> memory across projects so the Architect learns from past designs. And a manual pause
> control."

**What doesn't work well?** *(having an honest answer builds credibility)*
> "LLM output is non-deterministic, so occasionally the Developer's JSON is malformed or the
> generated CSS doesn't match the HTML classes. We handle both with mechanical validators and
> a retry, but we can't promise a perfect result on every single run."

---

## Part D — If something breaks

| Problem | Do this, say this |
|---|---|
| API error / quota exhausted | Set `MOCK_MODE=1`, restart. *"Switching to our offline mock mode — we built it as a demo fallback."* |
| Wifi down | Same. Mock mode needs no network. |
| A run hangs > 2 min | Switch to the pre-run backup tab. *"That's a live API call being slow; here's a completed run."* |
| Generated page looks unstyled | *"That's the exact failure our styling validator was built for — let me show you the check."* Open `_check_frontend_styling`. |
| Tests fail in the demo | **Good news, not bad.** *"Perfect — watch the Supervisor route it back to the Developer. That's the loop working."* |
| Streamlit port busy | `streamlit run ui/app.py --server.port 8502` |
| Someone forgets their line | Any member can pick up from the script — everyone should have read Parts A and B. |

---

## Part E — 30-second personal summaries (memorise your own)

**Athoy — Orchestration:** "I built the graph and the supervisor. `decide()` is a pure
function that picks the next agent from the project state; the LLM proposes in parallel and we
log any disagreement. I also built the three human-in-the-loop gates using LangGraph's
`interrupt()`, with a SQLite checkpointer so a paused run survives a restart."

**Pritom — Planning & memory:** "I built the Requirements Analyst, Architect and Doc Writer,
plus the knowledge layer. The Analyst does a real web search before writing the spec, and
everything is embedded into a Chroma vector store with local embeddings — that's our long-term
memory. The Architect classifies the project type first, which stops a static frontend request
being turned into a backend."

**Kazi — Build loop & tools:** "I built the Developer, Reviewer, Tester and DevOps agents
and the sandboxed execution tool. The important part is that quality gates are mechanical: the
Tester runs real pytest in a subprocess, and the Developer's output goes through JSON, syntax
and CSS validators before it's accepted — with one retry carrying the specific error back into
the prompt."

**Pranta — UI & observability:** "I built the Streamlit dashboard and the observability
layer. The trace streams live from the graph, and there are eight views — communications,
LangGraph topology, token cost, filterable logs, memory viewer, and the final report with a zip
download. Logging goes to three places at once: the UI, a human-readable log file, and a
per-run JSONL file."
