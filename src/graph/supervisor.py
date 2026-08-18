"""Supervisor / Project Manager. Owner: Member 1.

Hub of the hub-and-spoke graph: every agent returns here, and the supervisor
decides who runs next. `decide()` is a deterministic state machine (reliable
for demos and the safety fallback); in live mode, `route()` additionally
asks an LLM to independently pick the next agent and justify it in plain
English for the dashboard ("planning and reasoning" rubric item). The LLM's
pick is used ONLY if it agrees with `decide()` — decide() is always the
source of truth for what is actually valid, so a bad or malformed LLM
answer can never mis-route the pipeline.
"""
from src import config
from src.agents.base import call_llm, msg
from src.graph.state import AGENT_ORDER, ProjectState
from src.observability.logging_setup import log_entry

AGENT = "supervisor"
FINISH = "FINISH"
HUMAN_APPROVAL = "human_approval"
DEPLOYMENT_APPROVAL = "deployment_approval"

VALID_NEXT_NODES = set(AGENT_ORDER) | {HUMAN_APPROVAL, DEPLOYMENT_APPROVAL, FINISH}

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor / Project Manager of an
AI software engineering team. You are given the current project state and
must decide which team member acts next.

Respond with exactly two lines:
NEXT: <one of: requirements_analyst, human_approval, architect, developer, reviewer, tester, deployment_approval, doc_writer, devops, FINISH>
REASON: <one short sentence explaining why, for a live status dashboard>"""


def decide(state: ProjectState) -> tuple[str, str]:
    """Return (next_node, reason). Pure function — unit-test me. This is the
    single source of truth for pipeline correctness."""
    max_rev = config.MAX_REVISIONS

    if not state.get("requirements_doc"):
        return "requirements_analyst", "No requirements yet — starting with the SRS."
    if "requirements" not in state.get("approvals", []):
        return HUMAN_APPROVAL, "SRS drafted — pausing for human approval (HITL)."
    if not state.get("architecture_doc"):
        return "architect", "Requirements approved — designing the architecture."
    if not state.get("code_files"):
        return "developer", "Architecture ready — implementing the code."

    if not state.get("review_approved"):
        if state.get("review_feedback"):
            if state.get("revision_count", 0) < max_rev:
                return "developer", "Reviewer requested changes — sending back to the Developer."
            return "tester", f"Max revisions ({max_rev}) reached — proceeding to QA with known issues."
        return "reviewer", "Code written — requesting code review."

    if not state.get("tests_passed"):
        if state.get("test_report"):
            if state.get("revision_count", 0) < max_rev:
                return "developer", "Tests failed — sending the report back to the Developer."
            return "doc_writer", f"Max revisions ({max_rev}) reached — proceeding with failing tests flagged."
        return "tester", "Review approved — running QA."

    if not state.get("documentation"):
        return "doc_writer", "QA passed — writing the documentation."
    if "deployment" not in state.get("approvals", []):
        return DEPLOYMENT_APPROVAL, "Docs done — pausing for human approval before deployment (HITL)."
    if not state.get("deployment_files"):
        return "devops", "Deployment approved — preparing deployment files."
    return FINISH, "All phases complete — composing the final report."


def _state_summary(state: ProjectState) -> str:
    return f"""- requirements_doc: {"present" if state.get('requirements_doc') else "missing"}
- approvals: {state.get('approvals', [])}
- architecture_doc: {"present" if state.get('architecture_doc') else "missing"}
- code_files: {len(state.get('code_files', {}))} file(s)
- review_approved: {state.get('review_approved', False)}
- tests_passed: {state.get('tests_passed', False)}
- revision_count: {state.get('revision_count', 0)} (max {config.MAX_REVISIONS})
- documentation: {"present" if state.get('documentation') else "missing"}
- deployment_files: {len(state.get('deployment_files', {}))} file(s)"""


def _parse_llm_routing(text: str) -> tuple[str, str]:
    next_node, reason = "", ""
    for line in text.strip().splitlines():
        if line.upper().startswith("NEXT:"):
            next_node = line.split(":", 1)[1].strip()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return next_node, reason


def route(state: ProjectState) -> tuple[str, str, dict]:
    """Live-mode wrapper around decide(): asks an LLM to independently pick
    the next agent + justify it, but only ever uses that pick if it agrees
    with decide(). Returns (next_node, reason, token_usage)."""
    next_node, reason = decide(state)

    if config.MOCK_MODE:
        return next_node, reason, {}

    prompt = f"Current project state:\n{_state_summary(state)}"
    try:
        text, usage = call_llm(AGENT, SUPERVISOR_SYSTEM_PROMPT, prompt)
        picked, llm_reason = _parse_llm_routing(text)
        if picked == next_node and llm_reason:
            return next_node, llm_reason, usage
        log_entry(
            AGENT,
            "WARNING",
            f"LLM routing pick {picked!r} disagreed with the state machine "
            f"({next_node!r}) — using the deterministic decision.",
        )
        return next_node, reason, usage
    except Exception as error:  # noqa: BLE001 — routing must never crash the pipeline
        log_entry(AGENT, "WARNING", f"LLM routing call failed, using the deterministic decision: {error}")
        return next_node, reason, {}


def _final_report(state: ProjectState) -> str:
    files = "\n".join(f"- `{p}`" for p in sorted(state.get("code_files", {})))
    deploy = "\n".join(f"- `{p}`" for p in sorted(state.get("deployment_files", {})))
    usage = state.get("token_usage", {})
    return f"""# Final Delivery Report

**Project request:** {state.get('project_request', '')}

**Pipeline:** requirements -> human approval -> architecture -> code ->
review ({state.get('revision_count', 0)} rework round(s)) -> QA
({'PASS' if state.get('tests_passed') else 'FAIL'}) -> docs -> human
approval -> deployment.

## Deliverables
### Code files
{files}
### Deployment files
{deploy}

## Quality gates
- Code review: {"APPROVED" if state.get('review_approved') else "NOT APPROVED"}
- Tests: {"PASSED" if state.get('tests_passed') else "FAILED"}
- Human approvals: {", ".join(state.get('approvals', [])) or "none"}

## Agents involved
{len(set(m['from_agent'] for m in state.get('agent_messages', [])))} agents exchanged {len(state.get('agent_messages', []))} messages.
Token usage by agent: {usage or "mock mode — zero cost"}
"""


def supervisor_node(state: ProjectState) -> dict:
    next_node, reason, usage = route(state)
    update: dict = {
        "next_agent": next_node,
        "supervisor_plan": reason,
        "agent_messages": [msg(AGENT, next_node if next_node != FINISH else "user", reason)],
        "logs": [log_entry(AGENT, "INFO", f"route -> {next_node}: {reason}")],
        "token_usage": usage,
    }
    if next_node == FINISH:
        update["final_report"] = _final_report(state)
    return update


def route_from_supervisor(state: ProjectState) -> str:
    """Conditional-edge selector: reads the decision made in supervisor_node."""
    return state.get("next_agent", FINISH)
