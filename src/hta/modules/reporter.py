"""Reporter — assembles the final `Report` from the upstream pipeline outputs.

`build_report(profile, design, result, selection, df, outcome, group, predictor, hypothesis)`
returns a Pydantic `Report` (data profile, study design, test result, plain-language summary,
deterministic caveats, plot specs, methods text). Plot specs are declarative `PlotSpec`
objects — Plotly rendering and the presentation-only BET EDA plots are added by the web layer.
"""

from __future__ import annotations

import math
import re
from typing import Any, Optional

import pandas as pd
from scipy import stats

from hta.models.data import DataProfile
from hta.models.design import CausalGraph, StudyDesign, StudyDesignType
from hta.models.report import Caveat, CaveatSeverity, PlotSpec, Report
from hta.models.test import AssumptionStatus, StatisticalTest, TestResult
from hta.modules.causal import CausalAnalyser, usable_adjustment_covariates

# Areal / geospatial column names → ecological analysis (the H1–H3 caveat triggers).
_GEO_RE = re.compile(r"(fips|geoid|\blat\b|latitude|\blon\b|\blng\b|longitude|county|tract|"
                     r"census|\bzip\b|zipcode|postal|\bregion\b|\bstate\b|cbsa|\bmsa\b)",
                     re.IGNORECASE)
# A subject/cluster key whose values repeat → unmodelled non-independence (the H9 trigger).
_CLUSTER_RE = re.compile(r"(^id$|_id$|subject|patient|cluster|\bsite\b|hospital|cent(er|re)|"
                         r"household|family|school|provider)", re.IGNORECASE)
# Relative effect measures whose absolute magnitude (and NNT) should be judged separately (H7).
_RATIO_MEASURES = {"odds ratio", "hazard ratio", "incidence-rate ratio", "risk ratio",
                   "odds ratio (discordant)"}


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


def _reporting_standard(design: StudyDesign, result: TestResult) -> Optional[str]:
    """The EQUATOR reporting guideline implied by the design / analysis (§6.6)."""
    if result.test_used == StatisticalTest.ROC_AUC:
        return "STARD"                                    # diagnostic-accuracy study
    if design.design_type == StudyDesignType.EXPERIMENTAL and design.is_randomized:
        return "CONSORT"                                  # randomised controlled trial
    if design.design_type in (StudyDesignType.OBSERVATIONAL,
                              StudyDesignType.QUASI_EXPERIMENTAL):
        return "STROBE"                                   # observational study
    return None


def _healthcare_caveats(result: TestResult, df: pd.DataFrame,
                        exclude: set[str]) -> list[Caveat]:
    """The deterministic H1–H9 healthcare caveat catalog (§6.7), keyed off the data form, the
    chosen test, and the assumption results — reproducible rather than LLM-invented."""
    out: list[Caveat] = []
    test = result.test_used
    measure = result.effect_size.measure_name.lower()

    def add(sev: CaveatSeverity, msg: str, rec: str) -> None:
        out.append(Caveat(severity=sev, message=msg, recommendation=rec))

    # H1–H3 — areal / ecological analysis.
    geo = [str(c) for c in df.columns if _GEO_RE.search(str(c))]
    if geo:
        add(CaveatSeverity.WARNING,
            f"Ecological fallacy: with areal units ({', '.join(geo[:3])}), an area-level "
            "association need not hold for individuals.",
            "Use person-level data to make person-level inferences.")
        add(CaveatSeverity.INFO,
            "Modifiable areal unit problem (MAUP): associations can change with the choice or "
            "scale of the areal units.",
            "Check sensitivity to how the areal units are defined.")
        add(CaveatSeverity.WARNING,
            "Spatial autocorrelation among neighbouring areal units can understate standard "
            "errors (Moran's I).",
            "Consider a spatial or cluster-robust model.")

    # H4 — Poisson overdispersion reminder.
    if test == StatisticalTest.POISSON_REGRESSION:
        add(CaveatSeverity.INFO,
            "Poisson regression assumes the variance equals the mean.",
            "If the counts are overdispersed, prefer negative-binomial regression.")

    # H5–H6 — survival.
    if test in (StatisticalTest.LOG_RANK, StatisticalTest.COX_REGRESSION):
        ph_violated = any(c.assumption_name == "Proportional hazards"
                          and c.status == AssumptionStatus.VIOLATED
                          for c in result.assumption_checks)
        if ph_violated:
            add(CaveatSeverity.WARNING,
                "Non-proportional hazards: a single hazard ratio is misleading when the "
                "proportional-hazards assumption is violated.",
                "Consider time-varying effects or restricted mean survival time (RMST).")
        add(CaveatSeverity.INFO,
            "Survival analysis assumes non-informative censoring.",
            "Verify that censoring / dropout is unrelated to prognosis.")

    # H7 — a significant relative effect whose absolute magnitude is judged separately.
    if result.is_significant and measure in _RATIO_MEASURES:
        add(CaveatSeverity.WARNING,
            f"A statistically significant {result.effect_size.measure_name} is a relative "
            "effect; the absolute benefit (and the NNT) may still be small.",
            "Judge the absolute effect against the minimal clinically important difference (MCID).")

    # H8 — diagnostic predictive values depend on prevalence.
    if test == StatisticalTest.ROC_AUC:
        add(CaveatSeverity.INFO,
            "Sensitivity and specificity are prevalence-independent, but predictive values "
            "(PPV/NPV) depend on the operating prevalence.",
            "State the operating prevalence when reporting PPV/NPV.")

    # H9 — an unmodelled clustering / repeated-measures key (a subject/cluster id that repeats,
    # and is not the variable being analysed).
    clustering = [str(c) for c in df.columns
                  if str(c) not in exclude and _CLUSTER_RE.search(str(c))
                  and bool(df[c].duplicated().any())]
    if clustering:
        add(CaveatSeverity.WARNING,
            f"The key '{clustering[0]}' repeats across rows: observations are not independent "
            "and naive tests understate standard errors.",
            "A mixed-effects or GEE model is indicated (planned for v0.2.0).")
    return out


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
    standard = design.reporting_standard or _reporting_standard(design, result)
    if standard and standard != design.reporting_standard:
        design = design.model_copy(update={"reporting_standard": standard})
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
        + (f" The write-up follows the {standard} reporting guideline." if standard else "")
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

    exclude = {x for x in (outcome, group, predictor) if x}
    caveats = (_build_caveats(profile, design, result, selection, outcome, group, predictor,
                              df, graph)
               + _healthcare_caveats(result, df, exclude))
    return Report(
        data_profile=profile,
        study_design=design,
        test_result=result,
        plain_language_summary=plain,
        caveats=caveats,
        plots=plots,
        methods_text=methods,
    )
