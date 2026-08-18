"""Central configuration. Reads .env once; import from here, never call os.getenv elsewhere."""
import os

from dotenv import load_dotenv

load_dotenv()

MOCK_MODE: bool = os.getenv("MOCK_MODE", "1") == "1"

# LLM_PROVIDER selects which chat model call_llm() (src/agents/base.py) uses.
# "openai" (default) or "gemini" — Gemini has a free tier (aistudio.google.com)
# with no billing setup required, unlike OpenAI's pay-as-you-go API.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

ACTIVE_MODEL: str = GEMINI_MODEL if LLM_PROVIDER == "gemini" else OPENAI_MODEL
_ACTIVE_API_KEY: str = GEMINI_API_KEY if LLM_PROVIDER == "gemini" else OPENAI_API_KEY

MAX_REVISIONS: int = int(os.getenv("MAX_REVISIONS", "2"))

# USD per 1M tokens — used by the token/cost tracker (rubric: token usage & cost estimation)
PRICE_PER_1M_INPUT: float = float(os.getenv("PRICE_PER_1M_INPUT", "0.15"))
PRICE_PER_1M_OUTPUT: float = float(os.getenv("PRICE_PER_1M_OUTPUT", "0.60"))

# If no key is configured for the selected provider, force mock mode so the
# app never crashes at import time.
if not _ACTIVE_API_KEY:
    MOCK_MODE = True
