"""Pydantic request/response schemas for the HTA web API."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    session_id: str
    status: str
    columns: list[str]
    inferred_types: dict[str, str]
    preview: list[dict[str, Any]]


class VariablesPayload(BaseModel):
    outcome_variable: str
    group_variable: Optional[str] = None
    hypothesis: str


class DialoguePayload(BaseModel):
    user_message: str


class SessionResponse(BaseModel):
    session_id: str
    status: str
    profile: Optional[dict[str, Any]] = None
    design: Optional[dict[str, Any]] = None
    report: Optional[dict[str, Any]] = None


class BetScreenPayload(BaseModel):
    columns: Optional[list[str]] = None  # None = all numeric columns


class ErrorResponse(BaseModel):
    error: str
    message: str
