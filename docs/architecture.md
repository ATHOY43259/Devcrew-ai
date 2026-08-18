# DevCrew AI — Architecture

Hub-and-spoke supervisor pattern in LangGraph: the Supervisor plans and routes;
every specialized agent reports back to it. Five feedback loops make the
collaboration visible: Reviewer -> Developer (code review), Tester -> Developer
(failing tests), Human -> Requirements Analyst (rejected SRS),
Human -> Doc Writer (rejected pre-deployment review), and — after the pipeline
first finishes — an optional Human -> Developer modification loop: submit a
follow-up change request on the same thread, it runs back through
Developer -> Reviewer -> Tester, then pauses at its own approval gate before
re-finishing; rejecting that gate with feedback starts another round instead
of ending it.

```mermaid
flowchart LR
    USER(["User<br/>Streamlit UI"])
    SUP{{"Supervisor<br/>LLM-assisted routing +<br/>deterministic fallback"}}

    subgraph PLAN[" Planning agents "]
        RA["Requirements<br/>Analyst"]
        AR["Software<br/>Architect"]
        DOC["Documentation<br/>Writer"]
    end

    subgraph BUILD[" Build-loop agents "]
        DEV["Developer"]
        REV["Code Reviewer"]
        QA["QA / Tester"]
        OPS["DevOps Engineer"]
    end

    subgraph GATES[" Human-in-the-loop "]
        H1[/"Approve<br/>requirements"/]
        H2[/"Approve<br/>deployment"/]
        H3[/"Approve<br/>modification"/]
    end

    subgraph TOOLS[" Tools "]
        WS[["Web search<br/>(ddgs)"]]
        RAG[["RAG retrieval"]]
        SBX[["Sandboxed code exec<br/>(subprocess + pytest)"]]
    end

    subgraph MEM[" Memory "]
        STATE[("Graph state<br/>(short-term)")]
        CKPT[("SQLite checkpoints<br/>(persistent)")]
        VKB[("Chroma vector KB<br/>(long-term)")]
    end

    subgraph OBS[" Observability "]
        LOGS[("Structured logs<br/>run.log + JSON Lines")]
        COST[("Token usage +<br/>cost tracker")]
    end

    USER -- "project request" --> SUP
    SUP -- "final report" --> USER

    SUP <--> PLAN
    SUP <--> BUILD
    SUP <--> GATES
    PLAN -. "web search + RAG" .-> TOOLS
    BUILD -. "sandboxed exec" .-> TOOLS
    RAG === VKB
    SUP === MEM
    SUP === OBS

    REV -. "changes requested" .-> DEV
    QA -. "failing tests" .-> DEV
    H1 -. "reject + feedback" .-> RA
    H2 -. "reject + feedback" .-> DOC
    H3 -. "reject + feedback: iterate" .-> DEV

    classDef sup fill:#4f46e5,stroke:#312e81,color:#ffffff,font-weight:bold;
    classDef gate fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef agent fill:#ede9fe,stroke:#7c3aed,color:#1e1b4b;
    classDef tool fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef store fill:#e0e7ff,stroke:#4338ca,color:#1e1b4b;
    classDef planBg fill:#faf5ff,stroke:#c4b5fd,color:#4c1d95;
    classDef buildBg fill:#eff6ff,stroke:#93c5fd,color:#1e3a8a;
    classDef gateBg fill:#fffbeb,stroke:#fcd34d,color:#78350f;
    classDef toolBg fill:#f0fdf4,stroke:#86efac,color:#052e16;
    classDef memBg fill:#eef2ff,stroke:#a5b4fc,color:#1e1b4b;
    classDef obsBg fill:#f8fafc,stroke:#cbd5e1,color:#0f172a;

    class SUP sup
    class H1,H2,H3 gate
    class RA,AR,DOC,DEV,REV,QA,OPS agent
    class WS,RAG,SBX tool
    class STATE,CKPT,VKB,LOGS,COST store
    class PLAN planBg
    class BUILD buildBg
    class GATES gateBg
    class TOOLS toolBg
    class MEM memBg
    class OBS obsBg
```

Legend: solid arrows are the Supervisor <-> agent-group hub-and-spoke flow;
dotted arrows are the five feedback/collaboration loops (Reviewer, Tester,
and three HITL gates) plus tool/memory usage.

## Layers

| Layer | Where | Owner |
|---|---|---|
| Orchestration (supervisor, routing, HITL, checkpoints) | `src/graph/` | Member 1 |
| Planning & knowledge agents + RAG memory | `src/agents/` (analyst, architect, doc_writer), `src/memory/` | Member 2 |
| Build-loop agents + execution tools | `src/agents/` (developer, reviewer, tester, devops), `src/tools/` | Member 3 |
| UI + observability | `ui/`, `src/observability/` | Member 4 |

## Shared state (the contract)

`src/graph/state.py` defines `ProjectState` — the single shared memory all
agents read/write. Append-only lists (`agent_messages`, `logs`) power the UI's
communication history and log viewer; the `merge_usage` reducer aggregates
per-agent token cost. The LangGraph checkpointer persists state per thread,
which is what makes pause/resume (HITL `interrupt()`) possible.

## Execution flow (happy path with loops)

1. Supervisor -> Requirements Analyst -> SRS drafted
2. Supervisor -> Human approval (graph pauses; UI Approve/Reject)
3. Supervisor -> Architect -> tech stack + design
4. Supervisor -> Developer -> code v1
5. Supervisor -> Reviewer -> CHANGES REQUESTED -> Developer -> code v2 -> Reviewer -> APPROVED
6. Supervisor -> Tester -> pytest PASS (on FAIL: back to Developer)
7. Supervisor -> Doc Writer -> user guide
8. Supervisor -> Human approval (graph pauses; UI Approve/Reject deployment)
9. Supervisor -> DevOps -> Dockerfile + CI
10. Supervisor -> FINISH -> final report to the UI
11. Optional, any number of times: UI submits a modification request on the
    same thread -> Developer -> Reviewer -> Tester -> Human approval (graph
    pauses; Approve re-finishes, Reject + feedback loops back to step 11)
