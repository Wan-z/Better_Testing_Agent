"""Reporter — assembles the final `Report` from the upstream pipeline outputs.

`build_report(profile, design, result, selection, df, outcome, group, predictor, hypothesis)`
returns a Pydantic `Report` (data profile, study design, test result, plain-language summary,
deterministic caveats, plot specs, methods text). Plot specs are declarative `PlotSpec`
objects — Plotly rendering and the presentation-only BET EDA plots are added by the web layer.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd
from scipy import stats

from hta.models.data import DataProfile
from hta.models.design import CausalGraph, StudyDesign, StudyDesignType
from hta.models.report import Caveat, CaveatSeverity, PlotSpec, Report
from hta.models.test import TestResult
from hta.modules.causal import CausalAnalyser, usable_adjustment_covariates


def _num_series(df: pd.DataFrame, col: str) -> list[float]:
    return [float(v) for v in pd.to_numeric(df[col], errors="coerce").dropna().tolist()]


def _boxplot(df: pd.DataFrame, outcome: str, group: str) -> Optional[PlotSpec]:
    sub = df[[outcome, group]].copy()
    sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
    sub = sub.dropna()
    data: dict[str, list[float]] = {}
    for label, g in sub.groupby(group, sort=True):
        data[str(label)] = [float(v) for v in g[outcome].tolist()]
    if len(data) < 2:
        return None
    return PlotSpec(plot_type="boxplot", title=f"{outcome} by {group}",
                    x_label=group, y_label=outcome, data=dict(data))


def _scatter(df: pd.DataFrame, outcome: str, predictor: str) -> Optional[PlotSpec]:
    sub = df[[predictor, outcome]].copy()
    sub[predictor] = pd.to_numeric(sub[predictor], errors="coerce")
    sub[outcome] = pd.to_numeric(sub[outcome], errors="coerce")
    sub = sub.dropna()
    if len(sub) < 2:
        return None
    return PlotSpec(
        plot_type="scatter", title=f"{outcome} vs {predictor}",
        x_label=predictor, y_label=outcome,
        data={"x": [float(v) for v in sub[predictor].tolist()],
              "y": [float(v) for v in sub[outcome].tolist()]})


def _qqplot(df: pd.DataFrame, outcome: str) -> Optional[PlotSpec]:
    vals = _num_series(df, outcome)
    n = len(vals)
    if n < 3:
        return None
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) or 1.0
    sample = sorted((v - mean) / sd for v in vals)
    theoretical = [float(stats.norm.ppf((i + 0.5) / n)) for i in range(n)]
    return PlotSpec(
        plot_type="qqplot", title=f"Normal Q–Q plot — {outcome}",
        x_label="Theoretical quantiles", y_label="Standardized sample quantiles",
        data={"theoretical": theoretical, "sample": sample})


def _build_caveats(profile: DataProfile, design: StudyDesign, result: TestResult,
                   selection: Any, outcome: str, group: Optional[str],
                   predictor: Optional[str], df: pd.DataFrame,
                   graph: CausalGraph) -> list[Caveat]:
    caveats: list[Caveat] = []

    for c in (getattr(selection, "caveats", None) or []):
        caveats.append(Caveat(severity=CaveatSeverity.WARNING, message=c,
                              recommendation="Account for this in interpretation or modelling."))

    # Confounders (§5.3): report whether each recommended confounder was actually adjusted for.
    exclude = {x for x in (outcome, group, predictor) if x}
    usable = set(usable_adjustment_covariates(design, df, exclude))
    for conf in design.confounders:
        if not conf.adjustment_recommended or conf.name in exclude:
            continue
        if conf.name in usable:
            caveats.append(Caveat(
                severity=CaveatSeverity.INFO,
                message=(f"Adjusted for the confounder {conf.name} — see the adjusted "
                         "estimate in the result notes."),
                recommendation="Compare the adjusted and unadjusted estimates before concluding."))
        elif conf.is_measured:
            caveats.append(Caveat(
                severity=CaveatSeverity.WARNING,
                message=(f"{conf.name} is a recommended confounder that could not be used for "
                         "adjustment (non-numeric or absent from the data)."),
                recommendation=(f"Provide {conf.name} as a numeric column, or fit a model "
                                "that includes it.")))
        # Unmeasured recommended confounders are reported via the causal graph's warnings below.
    for warning in graph.warnings:
        caveats.append(Caveat(
            severity=CaveatSeverity.WARNING, message=warning,
            recommendation=("Unmeasured confounding cannot be removed by adjustment; "
                            "interpret any causal claim with caution.")))

    targets = {outcome, group, predictor} - {None}
    flagged = [f for f in profile.nonlinear_dependencies
               if f.significant and (f.x in targets or f.y in targets)]
    for f in flagged[:3]:
        kind = ("nonlinear (invisible to correlation)" if f.nonlinear_only
                else f.form.value.lower())
        caveats.append(Caveat(
            severity=CaveatSeverity.INFO,
            message=(f"BET flagged a {kind} dependence between {f.x} and {f.y} "
                     f"(z = {f.bet_z:.2f})."),
            recommendation="Consider whether a latent subgroup/subtype drives this pattern."))

    p = result.p_value
    if 0.04 <= p <= 0.06:
        caveats.append(Caveat(
            severity=CaveatSeverity.INFO,
            message=f"Marginal result (p = {p:.3f}) — close to the α = 0.05 threshold.",
            recommendation="Interpret with caution and consider replication."))

    if design.design_type == StudyDesignType.OBSERVATIONAL:
        caveats.append(Caveat(
            severity=CaveatSeverity.INFO,
            message="Observational design — associations do not establish causation.",
            recommendation="Avoid causal language; consider unmeasured confounding."))
    return caveats


def _normality_method(profile: DataProfile, outcome: str) -> str:
    for v in profile.variables:
        if v.name == outcome and v.normality:
            return v.normality.name
    return "Shapiro–Wilk"


def build_report(
    profile: DataProfile,
    design: StudyDesign,
    result: TestResult,
    selection: Any,
    df: pd.DataFrame,
    outcome: str,
    group: Optional[str],
    predictor: Optional[str],
    hypothesis: str,
    graph: Optional[CausalGraph] = None,
) -> Report:
    graph = graph if graph is not None else CausalAnalyser().analyse(profile, design)
    es = result.effect_size
    sig = "statistically significant" if result.is_significant else "not statistically significant"
    test_label = result.test_used.value.replace("_", " ").title()
    question = hypothesis or "the stated question"

    plain = (
        f"The analysis used {test_label} to test the hypothesis: {question}. "
        f"The result was {sig} (p = {result.p_value:.3f}). "
        f"The effect size was {es.measure_name} = {es.value:.2f} "
        f"({es.interpretation}; 95% CI [{es.ci_lower:.2f}, {es.ci_upper:.2f}])."
    )

    norm_method = _normality_method(profile, outcome)
    rationale = getattr(selection, "rationale", "") or ""
    why = rationale.rstrip(".").lower() or "it matched the data and design"
    methods = (
        f"{test_label} was selected because {why}. "
        f"Normality was assessed with the {norm_method} test on the relevant distribution(s). "
        f"The effect size ({es.measure_name}) is reported with a 95% confidence interval "
        f"(analytic where available, otherwise a 1000-sample bootstrap). "
        f"Significance was evaluated at α = 0.05."
    )

    plots: list[PlotSpec] = []
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

    caveats = _build_caveats(profile, design, result, selection, outcome, group, predictor,
                             df, graph)
    return Report(
        data_profile=profile,
        study_design=design,
        test_result=result,
        plain_language_summary=plain,
        caveats=caveats,
        plots=plots,
        methods_text=methods,
    )
