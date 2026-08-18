"""Make the repo root importable in tests + force mock mode for CI."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("MOCK_MODE", "1")

# Ad-hoc "run the pipeline and dump the files locally to look at" demos land
# in generated_*_preview/ at the repo root (gitignored). Their test files
# import from their own root (e.g. `from app import create_app`), which
# collides with this project's own package layout — never collect them.
collect_ignore_glob = ["generated_*_preview"]
