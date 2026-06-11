"""Web-layer configuration — loaded from project-root .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

BACKEND_PORT: int = int(os.getenv("HTA_BACKEND_PORT", "8000"))
ALLOWED_ORIGINS: list[str] = os.getenv(
    "HTA_ALLOWED_ORIGINS", "http://localhost:5173"
).split(",")
STORAGE_BACKEND: str = os.getenv("HTA_STORAGE_BACKEND", "local")
SESSION_TTL_DAYS: int = int(os.getenv("HTA_SESSION_TTL_DAYS", "7"))
DATA_DIR: Path = Path(__file__).parent.parent / "data" / "sessions"

# LLM provider — "anthropic" or "openai"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic").lower()

# Anthropic
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# OpenAI / Azure OpenAI
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Azure OpenAI — when AZURE_OPENAI_ENDPOINT is set, use AzureOpenAI client
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
IS_AZURE_OPENAI: bool = bool(AZURE_OPENAI_ENDPOINT)

# DRY_RUN: explicit env flag wins; falls back to "no key → dry run"
_active_key = ANTHROPIC_API_KEY if LLM_PROVIDER == "anthropic" else OPENAI_API_KEY
_dry_run_flag = os.getenv("HTA_DEFAULT_DRY_RUN", "").lower()
DRY_RUN: bool = (
    _dry_run_flag == "true"
    if _dry_run_flag in ("true", "false")
    else _active_key == ""
)
