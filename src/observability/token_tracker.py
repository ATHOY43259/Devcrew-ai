"""Token usage + cost estimation. Owner: Member 4.

LangChain chat responses carry `usage_metadata` (input_tokens/output_tokens).
We convert that into a per-agent delta dict; the `merge_usage` reducer in
state.py sums deltas across the whole run. The UI reads state["token_usage"].

TODO(Member 4): add per-model price table and a running cost chart in the UI.
"""
from typing import Dict

from src import config


def usage_delta(agent: str, response) -> Dict[str, Dict[str, float]]:
    """Extract a token/cost delta for `agent` from a LangChain AIMessage."""
    meta = getattr(response, "usage_metadata", None) or {}
    input_tokens = int(meta.get("input_tokens", 0))
    output_tokens = int(meta.get("output_tokens", 0))
    cost = (
        input_tokens / 1_000_000 * config.PRICE_PER_1M_INPUT
        + output_tokens / 1_000_000 * config.PRICE_PER_1M_OUTPUT
    )
    return {
        agent: {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
        }
    }


def totals(token_usage: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Sum per-agent usage into run totals for the UI header metrics."""
    out = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for usage in (token_usage or {}).values():
        for key in out:
            out[key] += usage.get(key, 0)
    out["cost_usd"] = round(out["cost_usd"], 6)
    return out
