"""Central configuration for HTA — loads credentials from the project .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load from .env at the project root (two levels up from this file: src/hta/config.py)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

# === Azure OpenAI (GPT-5.4, primary LLM) ===
AZURE_OPENAI_API_KEY: str    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_BASE_URL: str   = os.getenv("AZURE_OPENAI_BASE_URL", "https://azureaiapi.cloud.unc.edu/openai/v1/")
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

# === Statistical defaults ===
DEFAULT_ALPHA: float = float(os.getenv("HTA_DEFAULT_ALPHA", "0.05"))
DEFAULT_DRY_RUN: bool = os.getenv("HTA_DEFAULT_DRY_RUN", "true").lower() == "true"

# === Token budget ===
MAX_TOKENS: int = 28192
