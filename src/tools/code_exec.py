"""Sandboxed code execution tool. Owner: Member 3.

SECURITY: generated code is NEVER exec()'d in-process. It is always written
to a fresh temp directory and run in a subprocess with a timeout, isolated
from the app's own process and working directory.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

PYTEST_TIMEOUT_SECONDS = 60


def write_files(files: Dict[str, str]) -> Path:
    """Dump generated code into a fresh temp directory and return its path."""
    project_dir = Path(tempfile.mkdtemp(prefix="devcrew_"))
    for rel_path, content in files.items():
        target = project_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return project_dir


def run_pytest(project_dir: Path) -> Tuple[bool, str]:
    """Run pytest in `project_dir` as an isolated subprocess. Returns
    (passed, combined stdout+stderr). Never raises on test failure — only on
    a hard timeout, which is reported as a failed run instead of crashing."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        return False, f"pytest timed out after {PYTEST_TIMEOUT_SECONDS}s\n{output}"


def syntax_check(files: Dict[str, str]) -> List[str]:
    """Compile every .py file and return a list of "path: error" strings for
    any that fail to parse. Empty list means all files are syntactically valid."""
    errors: List[str] = []
    for path, content in files.items():
        if not path.endswith(".py"):
            continue
        try:
            compile(content, path, "exec")
        except SyntaxError as error:
            errors.append(f"{path}: {error.msg} (line {error.lineno})")
    return errors
