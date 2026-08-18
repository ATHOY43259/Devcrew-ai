"""Shared helpers every agent uses. Read this + requirements_analyst.py to
learn the pattern, then implement your own agent the same way.

The pattern for ONE agent node:
    def my_agent_node(state: ProjectState) -> dict:
        text, usage = call_llm("my_agent", SYSTEM_PROMPT, build_user_prompt(state))
        return {
            "my_artifact_key": text,                      # your keys ONLY
            "agent_messages": [msg("my_agent", "supervisor", "Done: ...")],
            "logs": [log_entry("my_agent", "INFO", "...")],
            "token_usage": usage,
        }
"""
import time
from typing import Dict, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from src import config
from src.graph.state import AgentMessage
from src.observability.logging_setup import log_entry, now_iso
from src.observability.token_tracker import usage_delta

MAX_LLM_RETRIES = 2


def msg(from_agent: str, to_agent: str, content: str) -> AgentMessage:
    """Create one entry for the agent communication history."""
    return AgentMessage(
        from_agent=from_agent, to_agent=to_agent, content=content, timestamp=now_iso()
    )


def call_llm(
    agent_name: str, system_prompt: str, user_prompt: str
) -> Tuple[str, Dict]:
    """One LLM call with retries + token tracking. Returns (text, usage_delta).

    Error handling (rubric requirement): transient failures are retried with
    backoff; a final failure raises RuntimeError, which the supervisor's
    error policy surfaces in the logs instead of crashing the whole app.
    """
    from langchain_openai import ChatOpenAI  # local import: not needed in mock mode

    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0.3)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    last_error: Exception | None = None
    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            response = llm.invoke(messages)
            return response.content, usage_delta(agent_name, response)
        except Exception as error:  # noqa: BLE001 — log and retry any API error
            last_error = error
            log_entry(agent_name, "WARNING", f"LLM call failed (attempt {attempt}): {error}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"{agent_name}: LLM failed after {MAX_LLM_RETRIES} attempts: {last_error}")
