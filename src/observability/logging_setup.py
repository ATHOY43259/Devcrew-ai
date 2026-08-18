"""File + console logging. Owner: Member 4.

Every agent action is logged twice:
1. Into the graph state (`logs` key) so the UI can show it live.
2. Into logs/run.log on disk via Python's logging module (grader-visible proof).

TODO(Member 4): upgrade to JSON-lines format and add per-run log files.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.graph.state import LogEntry

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

_logger = logging.getLogger("devcrew")
if not _logger.handlers:  # avoid duplicate handlers on Streamlit reruns
    _logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    _logger.addHandler(file_handler)
    _logger.addHandler(stream_handler)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_entry(agent: str, level: str, message: str) -> LogEntry:
    """Create a state LogEntry AND write it to logs/run.log."""
    _logger.log(getattr(logging, level, logging.INFO), "[%s] %s", agent, message)
    return LogEntry(timestamp=now_iso(), agent=agent, level=level, message=message)
