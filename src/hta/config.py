"""Central configuration for HTA — loads credentials from the project .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load from .env at the project root (two levels up from this file: src/hta/config.py)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

# === LLM provider — "anthropic" or "openai" ===
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

# === Anthropic ===
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str   = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# === OpenAI / Azure OpenAI ===
OPENAI_API_KEY: str  = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = (
    os.getenv("AZURE_OPENAI_ENDPOINT")
    or os.getenv("OPENAI_BASE_URL")
    or "https://api.openai.com/v1"
)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# === Statistical defaults ===
DEFAULT_ALPHA: float = float(os.getenv("HTA_DEFAULT_ALPHA", "0.05"))
DEFAULT_DRY_RUN: bool = os.getenv("HTA_DEFAULT_DRY_RUN", "true").lower() == "true"

# === Token budget ===
MAX_TOKENS: int = 28192
