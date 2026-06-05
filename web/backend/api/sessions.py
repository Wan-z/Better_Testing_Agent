"""Session endpoints: upload CSV, set variables, GET session state."""

from __future__ import annotations

import io
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from web.backend.schemas import SessionResponse, UploadResponse, VariablesPayload
from web.backend.storage.local import LocalStorage

# Make the statistical engine (`hta`, under src/) and `playground` importable for the
# function-level imports used in the profiler below.
_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

router = APIRouter()
store = LocalStorage()


_NUMERIC_TYPES = ("CONTINUOUS", "ORDINAL", "COUNT")


def _infer_types(df: pd.DataFrame) -> dict[str, str]:
    """Full VariableType inference via the engine's profiler (CONTINUOUS/ORDINAL/
    BINARY/CATEGORICAL/COUNT/IDENTIFIER), replacing the old 4-type heuristic."""
    from playground.pipeline import profile_column

    return {
        col: profile_column(col, df[col].astype(str).tolist()).var_type
        for col in df.columns
    }


def _build_profile(df: pd.DataFrame, outcome: str | None, group: str | None) -> dict[str, Any]:
    """Build a DataProfile dict: engine type inference + scipy normality + the BET
    pairwise nonlinear-dependence screen (DataProfile.nonlinear_dependencies)."""
    from scipy import stats as scipy_stats

    from hta.bet_screen import pairwise_screen
    from playground.pipeline import profile_column

    cols = {col: profile_column(col, df[col].astype(str).tolist()) for col in df.columns}
    variables = []

    for col in df.columns:
        vtype = cols[col].var_type
        n_obs = int(df[col].notna().sum())
        n_miss = int(df[col].isna().sum())
        var: dict[str, Any] = {
            "name": col,
            "variable_type": vtype,
            "n_observations": n_obs,
            "n_missing": n_miss,
        }

        if vtype in _NUMERIC_TYPES and pd.api.types.is_numeric_dtype(df[col]):
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
            if vtype in ("CONTINUOUS", "ORDINAL") and len(series) >= 3:
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
        elif vtype in ("BINARY", "CATEGORICAL"):
            var["unique_values"] = [str(v) for v in df[col].dropna().unique().tolist()][:20]

        variables.append(var)

    # BET pairwise nonlinear-dependence screen over the numeric columns (EDA stage).
    numeric_names = [c for c in df.columns if cols[c].var_type in _NUMERIC_TYPES]
    nonlinear: list[dict[str, Any]] = []
    bet_note = None
    if len(numeric_names) >= 2:
        aligned = df[numeric_names].apply(pd.to_numeric, errors="coerce").dropna()
        if len(aligned) >= 8:
            numeric_columns = {c: [float(v) for v in aligned[c].tolist()] for c in numeric_names}
            screen = pairwise_screen(numeric_columns, max_pairs=60, seed=0)
            for f in screen.findings:
                nonlinear.append({
                    "x": f.x, "y": f.y, "n": f.n,
                    "bet_statistic_s": f.bet_statistic_s,
                    "bet_z": round(f.bet_z, 4), "p_value": f.p_value, "bid": f.bid,
                    "form": f.form, "direction": f.direction,
                    "pearson_r": round(f.pearson_r, 4),
                    "spearman_rho": round(f.spearman_rho, 4),
                    "nonlinear_only": f.nonlinear_only, "significant": f.significant,
                })
            n_sig = sum(1 for f in nonlinear if f["significant"])
            n_nl = sum(1 for f in nonlinear if f["nonlinear_only"])
            if n_sig:
                nl_phrase = f", {n_nl} nonlinear-only" if n_nl else ""
                bet_note = (f"BET screen: {n_sig} dependent pair(s) found{nl_phrase} "
                            f"across {len(numeric_names)} numeric columns.")

    notes = []
    for col in df.columns:
        pct_miss = df[col].isna().mean() * 100
        if pct_miss > 5:
            notes.append(f"{col}: {pct_miss:.1f}% missing values")
    if bet_note:
        notes.append(bet_note)

    return {
        "variables": variables,
        "n_groups": int(df[group].nunique()) if group and group in df.columns else None,
        "group_variable": group,
        "outcome_variable": outcome,
        "notes": notes,
        "nonlinear_dependencies": nonlinear,
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

    def _load(name: str) -> Any:
        return json.loads(store.read(session_id, name)) if store.exists(session_id, name) else None

    meta = store.get_metadata(session_id)
    profile = _load("profile.json")
    design = _load("design.json")
    report = _load("report.json")

    return SessionResponse(
        session_id=session_id,
        status=meta["status"],
        profile=profile,
        design=design,
        report=report,
    )
