"""Web search tool — STUB. Owner: Member 2.

TODO(Member 2): implement with Tavily (tavily-python, free tier) or
duckduckgo-search. Keep this exact signature — the Requirements Analyst and
Architect call it. Log every call with log_entry(...) for observability.
"""
from typing import List, Dict


def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Return [{"title": ..., "url": ..., "snippet": ...}, ...]."""
    raise NotImplementedError("Member 2: implement web_search (Tavily or DuckDuckGo).")
