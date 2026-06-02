"""Session endpoints: upload CSV, set variables, GET session state."""

from __future__ import annotations

import io
import json
import uuid
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

from web.backend.schemas import UploadResponse, VariablesPayload, SessionResponse
from web.backend.storage.local import LocalStorage

router = APIRouter()
store = LocalStorage()


def _infer_types(df: pd.DataFrame) -> dict[str, str]:
    types: dict[str, str] = {}
    for col in df.columns:
        n_unique = df[col].nunique()
        if df[col].dtype == object:
            types[col] = "BINARY" if n_unique <= 2 else "CATEGORICAL"
        elif n_unique <= 2:
            types[col] = "BINARY"
        elif n_unique <= 10 and str(df[col].dtype).startswith("int"):
            types[col] = "ORDINAL"
        else:
            types[col] = "CONTINUOUS"
    return types


def _build_profile(df: pd.DataFrame, outcome: str | None, group: str | None) -> dict[str, Any]:
    """Build a DataProfile dict directly from a DataFrame (no HTA profiler module needed yet)."""
    from scipy import stats as scipy_stats

    variables = []
    inferred = _infer_types(df)

    for col in df.columns:
        vtype = inferred[col]
        n_obs = int(df[col].notna().sum())
        n_miss = int(df[col].isna().sum())
        var: dict[str, Any] = {
            "name": col,
            "variable_type": vtype,
            "n_observations": n_obs,
            "n_missing": n_miss,
        }

        if vtype in ("CONTINUOUS", "ORDINAL"):
            series = df[col].dropna().astype(float)
            var["distribution_stats"] = {
                "mean": round(float(series.mean()), 4),
                "std": round(float(series.std()), 4),
                "median": round(float(series.median()), 4),
                "iqr": round(float(series.quantile(0.75) - series.quantile(0.25)), 4),
                "skewness": round(float(series.skew()), 4),
                "kurtosis": round(float(series.kurtosis()), 4),
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
            }
            if len(series) >= 3:
                if len(series) <= 2000:
                    stat, p = scipy_stats.shapiro(series)
                    var["normality"] = {
                        "name": "Shapiro-Wilk",
                        "statistic": round(float(stat), 4),
                        "p_value": round(float(p), 4),
                        "is_normal": float(p) > 0.05,
                    }
                else:
                    result = scipy_stats.anderson(series, dist="norm")
                    cv_5pct = float(result.critical_values[2])
                    stat = float(result.statistic)
                    var["normality"] = {
                        "name": "Anderson-Darling",
                        "statistic": round(stat, 4),
                        "p_value": None,
                        "is_normal": stat < cv_5pct,
                    }
        else:
            var["unique_values"] = [str(v) for v in df[col].dropna().unique().tolist()]

        variables.append(var)

    notes = []
    for col in df.columns:
        pct_miss = df[col].isna().mean() * 100
        if pct_miss > 5:
            notes.append(f"{col}: {pct_miss:.1f}% missing values")

    return {
        "variables": variables,
        "n_groups": int(df[group].nunique()) if group and group in df.columns else None,
        "group_variable": group,
        "outcome_variable": outcome,
        "notes": notes,
    }


@router.post("/sessions", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    session_id = str(uuid.uuid4())
    store.init_session(session_id)
    store.write(session_id, "data.csv", raw)

    inferred = _infer_types(df)
    preview = df.head(10).fillna("").to_dict(orient="records")

    store.write_json(session_id, "preview.json", {
        "columns": df.columns.tolist(),
        "inferred_types": inferred,
        "preview": preview,
    })
    store.set_status(session_id, "PROFILED")

    return UploadResponse(
        session_id=session_id,
        status="PROFILED",
        columns=df.columns.tolist(),
        inferred_types=inferred,
        preview=preview,
    )


@router.patch("/sessions/{session_id}/variables")
async def set_variables(session_id: str, payload: VariablesPayload) -> dict[str, str]:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")

    raw_csv = store.read(session_id, "data.csv")
    df = pd.read_csv(io.BytesIO(raw_csv))
    profile = _build_profile(df, payload.outcome_variable, payload.group_variable)

    store.write_json(session_id, "variables.json", payload.model_dump())
    store.write_json(session_id, "profile.json", profile)
    store.set_status(session_id, "PROFILED")

    return {"status": "ok"}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")

    meta = store.get_metadata(session_id)
    profile = json.loads(store.read(session_id, "profile.json")) if store.exists(session_id, "profile.json") else None
    design = json.loads(store.read(session_id, "design.json")) if store.exists(session_id, "design.json") else None
    report = json.loads(store.read(session_id, "report.json")) if store.exists(session_id, "report.json") else None

    return SessionResponse(
        session_id=session_id,
        status=meta["status"],
        profile=profile,
        design=design,
        report=report,
    )
