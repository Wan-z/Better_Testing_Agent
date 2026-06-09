"""End-to-end tests for the orchestrator (`hta.agent.HypothesisTestingAgent`)."""

from __future__ import annotations

import pandas as pd
import pytest

from hta.agent import HypothesisTestingAgent
from hta.models.design import (
    Confounder,
    MeasurementType,
    StudyDesign,
    StudyDesignType,
    VariableRole,
)
from hta.models.report import Report
from hta.models.test import StatisticalTest


def _two_group_df() -> pd.DataFrame:
    a = [10.2, 11.4, 9.1, 12.3, 10.8, 11.0, 13.1, 9.6, 10.5, 12.0, 10.1, 11.7]
    b = [20.2, 21.4, 19.1, 22.3, 20.8, 21.0, 23.1, 19.6, 20.5, 22.0, 20.3, 21.6]
    return pd.DataFrame({"arm": ["A"] * len(a) + ["B"] * len(b), "score": a + b})


def test_two_group_pipeline_populated() -> None:
    rep = HypothesisTestingAgent().run(_two_group_df(), "does score differ by arm?",
                                       "score", group_variable="arm")
    assert isinstance(rep, Report)
    assert rep.test_result.test_used == StatisticalTest.WELCH_T
    assert rep.data_profile.variables and rep.study_design is not None
    assert rep.plain_language_summary and rep.methods_text
    assert rep.test_result.is_significant is True


def test_association_parabola() -> None:
    n = 120
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    df = pd.DataFrame({"x": xs, "y": [x * x for x in xs]})
    rep = HypothesisTestingAgent().run(df, "is y associated with x?", "y",
                                       predictor_variable="x")
    assert rep.test_result.test_used == StatisticalTest.MAXBET


def test_categorical_association() -> None:
    df = pd.DataFrame({"treat": (["A"] * 9 + ["B"] * 9) * 2,
                       "cured": (["yes", "no", "yes"] * 6) + (["no", "no", "yes"] * 6)})
    rep = HypothesisTestingAgent().run(df, "is cure related to treatment?", "cured",
                                       group_variable="treat")
    assert rep.test_result.test_used in (StatisticalTest.CHI_SQUARED, StatisticalTest.FISHER_EXACT)


def test_accepts_list_of_dicts() -> None:
    rows = [{"arm": "A", "score": v} for v in (1.0, 2.0, 3.0, 4.0, 5.0)] + \
           [{"arm": "B", "score": v} for v in (8.0, 9.0, 10.0, 11.0, 12.0)]
    rep = HypothesisTestingAgent().run(rows, "q", "score", group_variable="arm")
    assert isinstance(rep, Report)


def test_invalid_outcome_raises() -> None:
    with pytest.raises(ValueError):
        HypothesisTestingAgent().run(_two_group_df(), "q", "nonexistent_column")


def test_unselectable_raises() -> None:
    df = pd.DataFrame({"score": [float(i) for i in range(20)],
                       "label": ["x", "y"] * 10})
    with pytest.raises(ValueError):
        HypothesisTestingAgent().run(df, "q", "score")  # no group, no numeric partner


def test_confounder_adjustment_changes_the_result() -> None:
    """The headline §5.3 behaviour: a confounder that drives both variables produces an
    adjusted estimate, and the report flags that the adjustment happened."""
    z = [float(i % 20) for i in range(80)]
    df = pd.DataFrame({"x": [zi + (i % 3) * 0.5 for i, zi in enumerate(z)],
                       "y": [zi + (i % 5) * 0.4 for i, zi in enumerate(z)], "z": z})
    design = StudyDesign(
        design_type=StudyDesignType.OBSERVATIONAL,
        measurement_type=MeasurementType.BETWEEN_SUBJECTS, is_randomized=False,
        confounders=[Confounder(name="z", role=VariableRole.CONFOUNDER, is_measured=True,
                                adjustment_recommended=True, rationale="confounds both")])
    rep = HypothesisTestingAgent().run(df, "is y associated with x?", "y",
                                       predictor_variable="x", design=design)
    assert any("Adjusted for z" in n for n in rep.test_result.notes)
    assert any(c.severity.value == "INFO" and "Adjusted for the confounder z" in c.message
               for c in rep.caveats)
