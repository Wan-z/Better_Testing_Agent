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

# Azure OpenAI — inherited from core hta config
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_BASE_URL: str = os.getenv(
    "AZURE_OPENAI_BASE_URL", "https://azureaiapi.cloud.unc.edu/openai/v1/"
)
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

DRY_RUN: bool = AZURE_OPENAI_API_KEY == ""
