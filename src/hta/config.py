"""Central configuration for HTA — loads credentials from the shared secrets file.

Secrets are stored outside any repo at ~/.config/trading-agents/secrets.env,
following the same convention used across the trading-agent suite.
No credentials are read from environment variables injected by CI or .env
files in the project directory; the shared file is the single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Shared secrets across all agents — stored outside any project/repo directory
_env_path = Path.home() / ".config" / "trading-agents" / "secrets.env"
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
