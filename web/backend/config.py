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

# Azure OpenAI — AZURE_OPENAI_ENDPOINT takes priority over AZURE_OPENAI_BASE_URL
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_BASE_URL: str = (
    os.getenv("AZURE_OPENAI_ENDPOINT")
    or os.getenv("AZURE_OPENAI_BASE_URL")
    or "https://azureaiapi.cloud.unc.edu"
)
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

# DRY_RUN: explicit env flag wins; falls back to "no key → dry run"
_dry_run_flag = os.getenv("HTA_DEFAULT_DRY_RUN", "").lower()
DRY_RUN: bool = (
    _dry_run_flag == "true"
    if _dry_run_flag in ("true", "false")
    else AZURE_OPENAI_API_KEY == ""
)
