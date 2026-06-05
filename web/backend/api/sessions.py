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

# Upper bound on pairs screened by the BET EDA (the p-values are Bonferroni-corrected
# across them). High enough to fully cover wide dependence-screen datasets — e.g. 100
# columns → 4 950 pairs — while still bounding pathological widths.
_MAX_SCREEN_PAIRS = 5000


def _is_unnamed_index(name: object) -> bool:
    """True for a pandas auto-named blank-header column (a CSV row index). Such a column
    is an artefact, not a variable, so it must be kept out of the pairwise screen."""
    s = str(name).strip()
    return s == "" or s.startswith("Unnamed:")


def _infer_types(df: pd.DataFrame) -> dict[str, str]:
    """Full VariableType inference via the engine's profiler (CONTINUOUS/ORDINAL/
    BINARY/CATEGORICAL/COUNT/IDENTIFIER), replacing the old 4-type heuristic."""
    from playground.pipeline import profile_column

    return {
        col: profile_column(col, df[col].astype(str).tolist()).var_type
        for col in df.columns
    }


def _interaction_plotspec(
    ip: Any, *, color_by: str = "interaction",
    labels: list[str] | None = None, label_col: str | None = None,
) -> dict[str, Any]:
    """A 'bet_interaction' PlotSpec dict (the data half; plotly_json is added later)."""
    if color_by == "label":
        title = f"{ip.x_name} × {ip.y_name} — coloured by {label_col}"
    elif ip.significant:
        title = f"{ip.x_name} × {ip.y_name} — {ip.form.title()} (z = {ip.bet_z:.1f})"
    else:
        title = f"{ip.x_name} × {ip.y_name} — strongest pair (n.s.)"
    data: dict[str, Any] = {
        "u": [round(c, 6) for c in ip.u],
        "v": [round(c, 6) for c in ip.v],
        "grid_size": ip.grid_size,
        "region_z": ip.region_grid,
        "color_by": color_by,
        "bid": ip.bid, "form": ip.form, "bet_z": round(ip.bet_z, 4), "depth": ip.depth,
    }
    if color_by == "label":
        data["labels"] = list(labels or [])
    else:
        data["point_sign"] = list(ip.point_sign)
    return {
        "plot_type": "bet_interaction",
        "title": title,
        "x_label": f"{ip.x_name} (copula rank)",
        "y_label": f"{ip.y_name} (copula rank)",
        "data": data,
    }


def _eda_text(n_screened: int, n_sig: int, n_nl: int, chosen: list[Any],
              subtype_suggestive: bool) -> str:
    """Plain-language EDA summary shown to the user at the Review step."""
    if not n_sig:
        return (f"BET screened {n_screened} variable pair(s); none showed significant "
                "nonlinear dependence after multiple-testing correction. The most "
                "dependent pair is shown for reference.")
    top = chosen[0]
    lead = (f"BET screened {n_screened} variable pair(s) and found {n_sig} with "
            "significant dependence")
    if n_nl:
        lead += f", {n_nl} of them invisible to Pearson/Spearman correlation"
    lead += "."
    strongest = (f" The strongest is {top.x} × {top.y} "
                 f"({top.form.lower()}, z = {top.bet_z:.1f}).")
    how = (" Each point is coloured by which side of the dominant binary interaction it "
           "falls on; clusters of one colour within the grid cells reveal latent "
           "subgroups — the heterogeneity that creates the nonlinear pattern.")
    tail = (" These mixture-type shapes often come from an unmodelled subgroup; a "
            "within-subgroup analysis may be warranted." if subtype_suggestive else "")
    return lead + strongest + how + tail


def _eda_plots_and_summary(
    df: pd.DataFrame, cols: dict[str, Any], aligned: pd.DataFrame,
    numeric_columns: dict[str, list[float]], screen: Any, group: str | None,
    max_plots: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Xiang-style binary-interaction EDA plots for the top nonlinear pairs.

    Always emits a 2-colour (interaction-sign) plot per chosen pair; when the data has a
    usable categorical column it also emits a label-coloured version of the top pair so
    the user can compare the latent interaction structure against known subgroups.
    """
    from hta.bet_screen import SUBTYPE_SUGGESTIVE_FORMS, interaction_plot
    from web.backend.plots import plotspec_to_plotly

    if not screen.findings:
        return [], None

    sig = [f for f in screen.findings if f.significant]
    chosen = sig[:max_plots] if sig else screen.findings[:1]

    # A categorical column (preferring the chosen group) fully present on the screened
    # rows with 2–8 categories → used to colour the top pair by known subgroup.
    label_col: str | None = None
    label_values: list[str] | None = None
    candidates = ([group] if group else []) + [c for c in df.columns if c not in numeric_columns]
    seen: set[str] = set()
    for c in candidates:
        if not c or c in seen or c not in cols:
            continue
        seen.add(c)
        if cols[c].var_type not in ("BINARY", "CATEGORICAL"):
            continue
        s = df.loc[aligned.index, c]
        if s.isna().any():
            continue
        labs = [str(v) for v in s.tolist()]
        if 2 <= len(set(labs)) <= 8:
            label_col, label_values = c, labs
            break

    eda_plots: list[dict[str, Any]] = []
    for f in chosen:
        ip = interaction_plot(numeric_columns[f.x], numeric_columns[f.y],
                              x_name=f.x, y_name=f.y, seed=0)
        spec = _interaction_plotspec(ip, color_by="interaction")
        spec["plotly_json"] = plotspec_to_plotly(spec)
        eda_plots.append(spec)

    if label_col and label_values is not None:
        top = chosen[0]
        ip = interaction_plot(numeric_columns[top.x], numeric_columns[top.y],
                              x_name=top.x, y_name=top.y, seed=0)
        spec = _interaction_plotspec(ip, color_by="label",
                                     labels=label_values, label_col=label_col)
        spec["plotly_json"] = plotspec_to_plotly(spec)
        eda_plots.append(spec)

    subtype = any(f.form in SUBTYPE_SUGGESTIVE_FORMS for f in chosen)
    summary: dict[str, Any] = {
        "n_pairs_screened": len(screen.findings),
        "n_pairs_total": screen.n_pairs,
        "n_significant": screen.n_significant,
        "n_nonlinear_only": screen.n_nonlinear_only,
        "subtype_suggestive": subtype,
        "label_colored_by": label_col,
        "top_pairs": [
            {"x": f.x, "y": f.y, "form": f.form, "bet_z": round(f.bet_z, 4),
             "bid": f.bid, "nonlinear_only": f.nonlinear_only,
             "significant": f.significant}
            for f in chosen
        ],
        "text": _eda_text(len(screen.findings), screen.n_significant,
                          screen.n_nonlinear_only, chosen, subtype),
    }
    return eda_plots, summary


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
    numeric_names = [c for c in df.columns
                     if cols[c].var_type in _NUMERIC_TYPES and not _is_unnamed_index(c)]
    nonlinear: list[dict[str, Any]] = []
    eda_plots: list[dict[str, Any]] = []
    eda_summary: dict[str, Any] | None = None
    bet_note = None
    if len(numeric_names) >= 2:
        aligned = df[numeric_names].apply(pd.to_numeric, errors="coerce").dropna()
        if len(aligned) >= 8:
            numeric_columns = {c: [float(v) for v in aligned[c].tolist()] for c in numeric_names}
            screen = pairwise_screen(numeric_columns, max_pairs=_MAX_SCREEN_PAIRS, seed=0)
            eda_plots, eda_summary = _eda_plots_and_summary(
                df, cols, aligned, numeric_columns, screen, group)
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
        "eda_plots": eda_plots,
        "eda_summary": eda_summary,
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
