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

# Upper bound on pairs screened by the BET EDA (the p-values are Bonferroni-corrected
# across them). High enough to fully cover wide dependence-screen datasets — e.g. 100
# columns → 4 950 pairs — while still bounding pathological widths.
_MAX_SCREEN_PAIRS = 5000

# Cap on how many screened pairs are echoed into the profile payload. All significant
# pairs are always kept; this only bounds the strongest non-significant extras so the
# stored/transferred profile stays small (a 100-column screen has ~5 000 findings).
_MAX_REPORTED_FINDINGS = 50


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


def _network_plotspec(net: Any) -> dict[str, Any]:
    """A 'bet_network' PlotSpec dict (data half) for the dependence-network graph."""
    cap = " (top edges shown)" if net.capped else ""
    title = (f"Nonlinear dependence network — {len(net.edges)} link(s), "
             f"{len(net.nodes)} variable(s){cap}")
    return {
        "plot_type": "bet_network",
        "title": title,
        "x_label": "", "y_label": "",
        "data": {
            "nodes": [
                {"name": nm, "x": round(net.positions[nm][0], 4),
                 "y": round(net.positions[nm][1], 4), "degree": net.degrees[nm]}
                for nm in net.nodes
            ],
            "edges": [
                {"x": x, "y": y, "form": form, "bet_z": round(z, 3)}
                for x, y, form, z in net.edges
            ],
            "capped": net.capped,
        },
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
    from hta.bet_screen import (
        SUBTYPE_SUGGESTIVE_FORMS,
        dependence_network,
        interaction_plot,
    )
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

    # Headline overview: the Xiang-style dependence network (variables = nodes,
    # significant nonlinear pairs = edges coloured by binary interaction). Prepended so it
    # is the first tab in the EDA viewer.
    net = dependence_network(screen.findings, seed=0)
    if net.edges:
        net_spec = _network_plotspec(net)
        net_spec["plotly_json"] = plotspec_to_plotly(net_spec)
        eda_plots.insert(0, net_spec)

    subtype = any(f.form in SUBTYPE_SUGGESTIVE_FORMS for f in chosen)
    summary: dict[str, Any] = {
        "n_pairs_screened": len(screen.findings),
        "n_pairs_total": screen.n_pairs,
        "n_significant": screen.n_significant,
        "n_nonlinear_only": screen.n_nonlinear_only,
        "subtype_suggestive": subtype,
        "n_network_edges": net.n_significant_edges,
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
    """Build a DataProfile dict via the canonical engine profiler (type inference + scipy
    normality + the BET pairwise nonlinear-dependence screen), then attach the web's
    Xiang-style EDA plots from the *same* screen context (so the screen runs only once)."""
    from hta.modules.profiler import profile_with_screen

    profile_model, ctx = profile_with_screen(
        df, outcome, group,
        max_screen_pairs=_MAX_SCREEN_PAIRS, max_reported_findings=_MAX_REPORTED_FINDINGS)
    profile = profile_model.model_dump(mode="json")

    if ctx is not None:
        eda_plots, eda_summary = _eda_plots_and_summary(
            df, ctx.cols, ctx.aligned, ctx.numeric_columns, ctx.screen, group)
        profile["eda_plots"] = eda_plots
        profile["eda_summary"] = eda_summary
    return profile


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


@router.patch("/sessions/{session_id}/design")
async def set_design(session_id: str, payload: dict[str, Any]) -> dict[str, str]:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")
    store.write_json(session_id, "design.json", payload)
    store.set_status(session_id, "DESIGNED")
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
