"""Make the repo root importable in tests + force mock mode for CI."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("MOCK_MODE", "1")
