"""Report assembly for the web backend.

`build_report(...)` returns a plain dict matching `src/hta/models/report.py::Report`:
data_profile, study_design, test_result, plain_language_summary, caveats, plots,
methods_text. Plots are emitted as PlotSpec dicts WITHOUT plotly_json — `api/run.py`
enriches them via `plots.plotspec_to_plotly` before streaming the result.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd
from scipy import stats


def _num_series(df: pd.DataFrame, col: str) -> list[float]:
    return [float(v) for v in pd.to_numeric(df[col], errors="coerce").dropna().tolist()]


def _boxplot(df: pd.DataFrame, outcome: str, group: str) -> Optional[dict[str, Any]]:
    sub = df[[outcome, group]].copy()
    sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
    sub = sub.dropna()
    data: dict[str, list[float]] = {}
    for label, g in sub.groupby(group, sort=True):
        data[str(label)] = [float(v) for v in g[outcome].tolist()]
    if len(data) < 2:
        return None
    return {
        "plot_type": "boxplot",
        "title": f"{outcome} by {group}",
        "x_label": group,
        "y_label": outcome,
        "data": data,
    }


def _scatter(df: pd.DataFrame, outcome: str, predictor: str) -> Optional[dict[str, Any]]:
    sub = df[[predictor, outcome]].copy()
    sub[predictor] = pd.to_numeric(sub[predictor], errors="coerce")
    sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 2:
        return None
    return {
        "plot_type": "scatter",
        "title": f"{outcome} vs {predictor}",
        "x_label": predictor,
        "y_label": outcome,
        "data": {"x": [float(v) for v in sub[predictor].tolist()],
                 "y": [float(v) for v in sub[outcome].tolist()]},
    }


def _qqplot(df: pd.DataFrame, outcome: str) -> Optional[dict[str, Any]]:
    vals = _num_series(df, outcome)
    n = len(vals)
    if n < 3:
        return None
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) or 1.0
    sample = sorted((v - mean) / sd for v in vals)
    theoretical = [float(stats.norm.ppf((i + 0.5) / n)) for i in range(n)]
    return {
        "plot_type": "qqplot",
        "title": f"Normal Q–Q plot — {outcome}",
        "x_label": "Theoretical quantiles",
        "y_label": "Standardized sample quantiles",
        "data": {"theoretical": theoretical, "sample": sample},
    }


def _build_caveats(profile: dict[str, Any], design: dict[str, Any], test_result: dict[str, Any],
                   selection: Any, outcome: str, group: Optional[str],
                   predictor: Optional[str]) -> list[dict[str, Any]]:
    caveats: list[dict[str, Any]] = []

    for c in (getattr(selection, "caveats", None) or []):
        caveats.append({"severity": "WARNING", "message": c,
                        "recommendation": "Account for this in interpretation or modelling."})

    in_model = {x for x in (group, predictor) if x}
    for conf in design.get("confounders", []):
        if conf.get("adjustment_recommended") and conf.get("name") not in in_model:
            caveats.append({
                "severity": "WARNING",
                "message": (f"{conf['name']} ({conf.get('role', 'CONFOUNDER')}) is a "
                            "confounder not included in this bivariate model."),
                "recommendation": (f"Adjust for {conf['name']} (e.g. partial correlation or "
                                   "a regression model) before drawing conclusions."),
            })

    targets = {outcome, group, predictor} - {None}
    flagged = [f for f in profile.get("nonlinear_dependencies", [])
               if f.get("significant") and (f.get("x") in targets or f.get("y") in targets)]
    for f in flagged[:3]:
        kind = ("nonlinear (invisible to correlation)" if f.get("nonlinear_only")
                else f.get("form", "").lower())
        caveats.append({
            "severity": "INFO",
            "message": (f"BET flagged a {kind} dependence between {f['x']} and {f['y']} "
                        f"(z = {f.get('bet_z', 0):.2f})."),
            "recommendation": "Consider whether a latent subgroup/subtype drives this pattern.",
        })

    p = test_result.get("p_value", 1.0)
    if 0.04 <= p <= 0.06:
        caveats.append({
            "severity": "INFO",
            "message": f"Marginal result (p = {p:.3f}) — close to the α = 0.05 threshold.",
            "recommendation": "Interpret with caution and consider replication.",
        })

    if (design.get("design_type") == "OBSERVATIONAL"):
        caveats.append({
            "severity": "INFO",
            "message": "Observational design — associations do not establish causation.",
            "recommendation": "Avoid causal language; consider unmeasured confounding.",
        })
    return caveats


def _normality_method(profile: dict[str, Any], outcome: str) -> str:
    for v in profile.get("variables", []):
        if v.get("name") == outcome and v.get("normality"):
            return str(v["normality"].get("name", "Shapiro–Wilk"))
    return "Shapiro–Wilk"


def build_report(
    profile: dict[str, Any],
    design: dict[str, Any],
    test_result: dict[str, Any],
    selection: Any,
    df: pd.DataFrame,
    outcome: str,
    group: Optional[str],
    predictor: Optional[str],
    hypothesis: str,
) -> dict[str, Any]:
    es = test_result["effect_size"]
    sig = ("statistically significant" if test_result["is_significant"]
           else "not statistically significant")
    test_label = test_result["test_used"].replace("_", " ").title()
    question = hypothesis or "the stated question"

    plain = (
        f"The analysis used {test_label} to test the hypothesis: {question}. "
        f"The result was {sig} (p = {test_result['p_value']:.3f}). "
        f"The effect size was {es['measure_name']} = {es['value']:.2f} "
        f"({es['interpretation']}; 95% CI [{es['ci_lower']:.2f}, {es['ci_upper']:.2f}])."
    )

    norm_method = _normality_method(profile, outcome)
    rationale = getattr(selection, "rationale", "") or ""
    why = rationale.rstrip(".").lower() or "it matched the data and design"
    methods = (
        f"{test_label} was selected because {why}. "
        f"Normality was assessed with the {norm_method} test on the relevant distribution(s). "
        f"The effect size ({es['measure_name']}) is reported with a 95% confidence interval "
        f"(analytic where available, otherwise a 1000-sample bootstrap). "
        f"Significance was evaluated at α = 0.05."
    )

    plots: list[dict[str, Any]] = []
    if group:
        bp = _boxplot(df, outcome, group)
        if bp:
            plots.append(bp)
    elif predictor:
        sc = _scatter(df, outcome, predictor)
        if sc:
            plots.append(sc)
    qq = _qqplot(df, outcome)
    if qq:
        plots.append(qq)

    caveats = _build_caveats(profile, design, test_result, selection, outcome, group, predictor)
    return {
        "data_profile": profile,
        "study_design": design,
        "test_result": test_result,
        "plain_language_summary": plain,
        "caveats": caveats,
        "plots": plots,
        "methods_text": methods,
    }
