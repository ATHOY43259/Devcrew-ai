"""Sandboxed code execution tool — STUB. Owner: Member 3.

TODO(Member 3): implement:
  1. write_files(files: dict[str, str]) -> Path: dump generated code into a
     fresh tempfile.mkdtemp() directory (create parent dirs for nested paths).
  2. run_pytest(project_dir: Path) -> tuple[bool, str]: subprocess.run(
     ["python", "-m", "pytest", "-q"], cwd=..., capture_output=True,
     timeout=60); return (returncode == 0, stdout + stderr).
  3. syntax_check(files) -> list[str]: compile() each .py, return error list.
SECURITY: never exec() generated code in-process; always a subprocess with a
timeout, in a temp dir.
"""
from pathlib import Path
from typing import Dict, List, Tuple


def write_files(files: Dict[str, str]) -> Path:
    raise NotImplementedError("Member 3: implement write_files.")


def run_pytest(project_dir: Path) -> Tuple[bool, str]:
    raise NotImplementedError("Member 3: implement run_pytest.")


def syntax_check(files: Dict[str, str]) -> List[str]:
    raise NotImplementedError("Member 3: implement syntax_check.")
