"""Central configuration. Reads .env once; import from here, never call os.getenv elsewhere."""
import os

from dotenv import load_dotenv

load_dotenv()

MOCK_MODE: bool = os.getenv("MOCK_MODE", "1") == "1"
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_REVISIONS: int = int(os.getenv("MAX_REVISIONS", "2"))

# USD per 1M tokens — used by the token/cost tracker (rubric: token usage & cost estimation)
PRICE_PER_1M_INPUT: float = float(os.getenv("PRICE_PER_1M_INPUT", "0.15"))
PRICE_PER_1M_OUTPUT: float = float(os.getenv("PRICE_PER_1M_OUTPUT", "0.60"))

# If no key is configured, force mock mode so the app never crashes at import time.
if not OPENAI_API_KEY:
    MOCK_MODE = True
