"""Tests for the engine reporter (`hta.modules.reporter`).

Covers caveat generation (observational, unadjusted confounder, marginal p, BET nonlinear),
the plot specs emitted per analysis shape, and the assembled `Report` text.
"""

from __future__ import annotations

import pandas as pd

from hta.models.data import DataProfile, Variable, VariableType
from hta.models.design import (
    Confounder,
    MeasurementType,
    StudyDesign,
    StudyDesignType,
    VariableRole,
)
from hta.models.report import Report
from hta.models.test import (
    AssumptionCheck,
    AssumptionStatus,
    EffectSize,
    StatisticalTest,
    TestResult,
)
from hta.modules.executor import execute
from hta.modules.profiler import build_data_profile
from hta.modules.reporter import build_report
from hta.modules.selector import Selection


def _design(design_type: StudyDesignType = StudyDesignType.EXPERIMENTAL,
            confounders: list[Confounder] | None = None) -> StudyDesign:
    return StudyDesign(design_type=design_type, measurement_type=MeasurementType.BETWEEN_SUBJECTS,
                       is_randomized=True, confounders=confounders or [])


def _profile(outcome: str) -> DataProfile:
    return DataProfile(variables=[Variable(name=outcome, variable_type=VariableType.CONTINUOUS,
                                           n_observations=10, n_missing=0)],
                       outcome_variable=outcome)


def _result(p_value: float, value: float = 0.5) -> TestResult:
    return TestResult(
        test_used="WELCH_T", statistic=2.0, p_value=p_value, degrees_of_freedom=8.0,
        effect_size=EffectSize(measure_name="Cohen's d", value=value, interpretation="medium",
                               ci_lower=value - 0.2, ci_upper=value + 0.2),
        assumption_checks=[AssumptionCheck(assumption_name="Normality",
                                           status=AssumptionStatus.MET, note="ok")],
        confidence_interval=(value - 0.2, value + 0.2), is_significant=p_value < 0.05)


def _two_group_df() -> pd.DataFrame:
    a = [10.2, 11.4, 9.1, 12.3, 10.8, 11.0, 13.1, 9.6, 10.5, 12.0]
    b = [20.2, 21.4, 19.1, 22.3, 20.8, 21.0, 23.1, 19.6, 20.5, 22.0]
    return pd.DataFrame({"arm": ["A"] * 10 + ["B"] * 10, "score": a + b})


def test_returns_report_with_text() -> None:
    df = _two_group_df()
    rep = build_report(_profile("score"), _design(), _result(0.001), None, df,
                       "score", "arm", None, "does score differ?")
    assert isinstance(rep, Report)
    assert rep.plain_language_summary and rep.methods_text
    assert "Welch T" in rep.plain_language_summary


def test_observational_caveat() -> None:
    rep = build_report(_profile("score"), _design(StudyDesignType.OBSERVATIONAL),
                       _result(0.001), None, _two_group_df(), "score", "arm", None, "q")
    assert any("Observational" in c.message for c in rep.caveats)


def test_unadjusted_confounder_caveat() -> None:
    conf = Confounder(name="age", role=VariableRole.CONFOUNDER, is_measured=True,
                      adjustment_recommended=True, rationale="age affects both")
    rep = build_report(_profile("score"), _design(confounders=[conf]), _result(0.001), None,
                       _two_group_df(), "score", "arm", None, "q")
    assert any("age" in c.message and c.severity.value == "WARNING" for c in rep.caveats)


def test_marginal_p_caveat() -> None:
    rep = build_report(_profile("score"), _design(), _result(0.048), None, _two_group_df(),
                       "score", "arm", None, "q")
    assert any("Marginal" in c.message for c in rep.caveats)


def test_group_plots() -> None:
    rep = build_report(_profile("score"), _design(), _result(0.001), None, _two_group_df(),
                       "score", "arm", None, "q")
    kinds = {p.plot_type for p in rep.plots}
    assert "boxplot" in kinds and "qqplot" in kinds


def test_predictor_plots_and_bet_caveat() -> None:
    n = 80
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    df = pd.DataFrame({"x": xs, "y": [x * x for x in xs]})
    profile = build_data_profile(df, "y", None)
    result = execute("MAXBET", df, "y", None, "x")
    sel = Selection("MAXBET", "nonlinear")
    rep = build_report(profile, _design(), result, sel, df, "y", None, "x", "assoc?")
    kinds = {p.plot_type for p in rep.plots}
    assert "scatter" in kinds and "qqplot" in kinds
    # The parabola is a flagged nonlinear dependence on the outcome → a BET caveat.
    assert any("BET" in c.message for c in rep.caveats)


def test_adjusted_confounder_caveat_is_info() -> None:
    df = pd.DataFrame({"y": [float(i) for i in range(20)],
                       "x": [float(i % 7) for i in range(20)],
                       "z": [float(i % 5) for i in range(20)]})
    conf = Confounder(name="z", role=VariableRole.CONFOUNDER, is_measured=True,
                      adjustment_recommended=True, rationale="confounds both")
    rep = build_report(_profile("y"), _design(confounders=[conf]), _result(0.01), None,
                       df, "y", None, "x", "q")
    assert any(c.severity.value == "INFO" and "Adjusted for the confounder z" in c.message
               for c in rep.caveats)


def test_unmeasured_confounder_caveat_is_warning() -> None:
    df = pd.DataFrame({"y": [float(i) for i in range(20)],
                       "x": [float(i % 7) for i in range(20)]})
    conf = Confounder(name="genetics", role=VariableRole.CONFOUNDER, is_measured=False,
                      adjustment_recommended=True, rationale="latent common cause")
    rep = build_report(_profile("y"), _design(confounders=[conf]), _result(0.01), None,
                       df, "y", None, "x", "q")
    assert any(c.severity.value == "WARNING" and "genetics" in c.message for c in rep.caveats)


# ── Phase 4: H1–H9 healthcare caveats (§6.7) + EQUATOR reporting standard (§6.6) ──

def _hc_result(test_used: StatisticalTest, measure: str, value: float = 1.5,
               p: float = 0.01, checks: list[AssumptionCheck] | None = None) -> TestResult:
    return TestResult(
        test_used=test_used, statistic=2.0, p_value=p, degrees_of_freedom=None,
        effect_size=EffectSize(measure_name=measure, value=value, interpretation="—",
                               ci_lower=value * 0.8, ci_upper=value * 1.2),
        assumption_checks=checks or [], confidence_interval=(value * 0.8, value * 1.2),
        is_significant=p < 0.05)


def _surv_df() -> pd.DataFrame:
    return pd.DataFrame({"t": [float(i) for i in range(12)],
                         "x": [float(i % 4) for i in range(12)], "arm": ["A", "B"] * 6})


def test_reporting_standard_observational_is_strobe() -> None:
    rep = build_report(_profile("score"), _design(StudyDesignType.OBSERVATIONAL), _result(0.01),
                       None, _two_group_df(), "score", "arm", None, "q")
    assert rep.study_design.reporting_standard == "STROBE"


def test_reporting_standard_rct_is_consort() -> None:
    d = StudyDesign(design_type=StudyDesignType.EXPERIMENTAL,
                    measurement_type=MeasurementType.BETWEEN_SUBJECTS, is_randomized=True)
    rep = build_report(_profile("score"), d, _result(0.01), None, _two_group_df(),
                       "score", "arm", None, "q")
    assert rep.study_design.reporting_standard == "CONSORT"


def test_reporting_standard_diagnostic_is_stard() -> None:
    df = pd.DataFrame({"disease": [i % 2 for i in range(20)], "bm": [float(i) for i in range(20)]})
    res = _hc_result(StatisticalTest.ROC_AUC, "AUC", value=0.8, p=0.001)
    rep = build_report(_profile("disease"), _design(), res, None, df, "disease", None, "bm", "q")
    assert rep.study_design.reporting_standard == "STARD"


def test_h1_h3_ecological_caveats() -> None:
    df = pd.DataFrame({"county_fips": [str(i) for i in range(20)],
                       "x": [float(i) for i in range(20)], "y": [float(20 - i) for i in range(20)]})
    rep = build_report(_profile("y"), _design(StudyDesignType.OBSERVATIONAL), _result(0.01), None,
                       df, "y", None, "x", "q")
    msgs = " ".join(c.message for c in rep.caveats)
    assert "Ecological fallacy" in msgs and "MAUP" in msgs and "autocorrelation" in msgs


def test_h4_poisson_caveat() -> None:
    res = _hc_result(StatisticalTest.POISSON_REGRESSION, "incidence-rate ratio", p=0.2)
    rep = build_report(_profile("score"), _design(), res, None, _two_group_df(),
                       "score", "arm", None, "q")
    assert any("variance equals the mean" in c.message for c in rep.caveats)


def test_h5_non_proportional_hazards_caveat() -> None:
    checks = [AssumptionCheck(assumption_name="Proportional hazards",
                              status=AssumptionStatus.VIOLATED, note="crossing curves")]
    res = _hc_result(StatisticalTest.COX_REGRESSION, "hazard ratio", p=0.2, checks=checks)
    rep = build_report(_profile("t"), _design(), res, None, _surv_df(), "t", None, "x", "q")
    assert any("Non-proportional hazards" in c.message for c in rep.caveats)


def test_h6_survival_censoring_caveat() -> None:
    res = _hc_result(StatisticalTest.LOG_RANK, "hazard ratio", p=0.2)
    rep = build_report(_profile("t"), _design(), res, None, _surv_df(), "t", "arm", None, "q")
    assert any("non-informative censoring" in c.message.lower() for c in rep.caveats)


def test_h7_significant_ratio_caveat() -> None:
    res = _hc_result(StatisticalTest.COX_REGRESSION, "hazard ratio", value=2.0, p=0.001)
    rep = build_report(_profile("t"), _design(), res, None, _surv_df(), "t", None, "x", "q")
    assert any("relative effect" in c.message for c in rep.caveats)


def test_h8_diagnostic_prevalence_caveat() -> None:
    df = pd.DataFrame({"d": [i % 2 for i in range(20)], "score": [float(i) for i in range(20)]})
    res = _hc_result(StatisticalTest.ROC_AUC, "AUC", value=0.8, p=0.001)
    rep = build_report(_profile("d"), _design(), res, None, df, "d", None, "score", "q")
    assert any("prevalence" in c.message for c in rep.caveats)


def test_h9_clustering_caveat() -> None:
    df = pd.DataFrame({"patient_id": [f"P{i % 10}" for i in range(20)],
                       "score": [float(i) for i in range(20)], "arm": ["A", "B"] * 10})
    rep = build_report(_profile("score"), _design(), _result(0.01), None, df,
                       "score", "arm", None, "q")
    assert any("not independent" in c.message for c in rep.caveats)
