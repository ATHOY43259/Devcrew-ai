"""Web search tool — REAL implementation. Owner: Member 2.

Uses ddgs (no API key needed, fits the project's zero-cost demo
philosophy) — the package formerly published as duckduckgo-search, which
is deprecated and silently returns zero results against DuckDuckGo's
current backend. Every call is logged for observability; a failed search
(network down, package missing, rate limited) degrades to an empty result
list instead of crashing the pipeline — research is a nice-to-have, not a
hard dependency for any agent.
"""
from typing import Dict, List

from src.observability.logging_setup import log_entry

AGENT = "web_search"


def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Return [{"title": ..., "url": ..., "snippet": ...}, ...]."""
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("href", item.get("link", "")),
                "snippet": item.get("body", item.get("snippet", "")),
            }
            for item in raw
        ]
        log_entry(AGENT, "INFO", f"web_search({query!r}) -> {len(results)} result(s).")
        return results
    except Exception as error:  # noqa: BLE001 — search is best-effort
        log_entry(AGENT, "WARNING", f"web_search({query!r}) failed: {error}")
        return []
