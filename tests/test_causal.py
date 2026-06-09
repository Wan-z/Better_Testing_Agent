"""Tests for the causal module (`hta.modules.causal`).

Covers the `CausalGraph` construction (adjustment set, unmeasured-confounder warnings, edges)
and the `usable_adjustment_covariates` filter that decides which confounders can actually be
used to adjust an estimate.
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
from hta.modules.causal import CausalAnalyser, usable_adjustment_covariates


def _profile(outcome: str = "y", group: str | None = "arm") -> DataProfile:
    return DataProfile(
        variables=[Variable(name=outcome, variable_type=VariableType.CONTINUOUS,
                            n_observations=10, n_missing=0)],
        outcome_variable=outcome, group_variable=group)


def _design(confs: list[Confounder]) -> StudyDesign:
    return StudyDesign(design_type=StudyDesignType.OBSERVATIONAL,
                       measurement_type=MeasurementType.BETWEEN_SUBJECTS,
                       is_randomized=False, confounders=confs)


def _conf(name: str, measured: bool = True, recommended: bool = True) -> Confounder:
    return Confounder(name=name, role=VariableRole.CONFOUNDER, is_measured=measured,
                      adjustment_recommended=recommended, rationale="drives both")


def test_adjustment_set_measured() -> None:
    graph = CausalAnalyser().analyse(_profile(), _design([_conf("age"), _conf("sex")]))
    assert set(graph.adjustment_set) == {"age", "sex"}
    assert graph.warnings == []


def test_unmeasured_confounder_warning() -> None:
    graph = CausalAnalyser().analyse(_profile(), _design([_conf("genetics", measured=False)]))
    assert "genetics" not in graph.adjustment_set
    assert any("genetics" in w for w in graph.warnings)


def test_no_confounders() -> None:
    graph = CausalAnalyser().analyse(_profile(), _design([]))
    assert graph.adjustment_set == []
    assert graph.warnings == []


def test_not_recommended_excluded() -> None:
    graph = CausalAnalyser().analyse(_profile(), _design([_conf("age", recommended=False)]))
    assert "age" not in graph.adjustment_set


def test_edges_built_from_confounders() -> None:
    graph = CausalAnalyser().analyse(_profile("y", "arm"), _design([_conf("age")]))
    assert ("age", "y") in graph.edges        # confounder → outcome
    assert ("age", "arm") in graph.edges      # confounder → exposure
    assert ("arm", "y") in graph.edges        # exposure → outcome


def test_usable_covariates_filters_nonnumeric_and_absent() -> None:
    df = pd.DataFrame({"y": [1.0, 2, 3, 4, 5], "age": [10, 20, 30, 40, 50],
                       "site": ["a", "b", "a", "b", "a"]})
    design = _design([_conf("age"), _conf("site"), _conf("income")])  # income absent from df
    assert usable_adjustment_covariates(design, df, exclude={"y"}) == ["age"]


def test_usable_covariates_excludes_outcome_and_unmeasured() -> None:
    df = pd.DataFrame({"y": [1.0, 2, 3, 4, 5], "age": [10, 20, 30, 40, 50]})
    design = _design([_conf("age", measured=False), _conf("y")])  # unmeasured + outcome itself
    assert usable_adjustment_covariates(design, df, exclude={"y"}) == []


def test_usable_covariates_accepts_dict_design() -> None:
    """The web layer passes a plain design dict — the helper must handle it too."""
    df = pd.DataFrame({"y": [1.0, 2, 3, 4, 5], "age": [10, 20, 30, 40, 50]})
    design = {"confounders": [{"name": "age", "is_measured": True,
                               "adjustment_recommended": True}]}
    assert usable_adjustment_covariates(design, df, exclude={"y"}) == ["age"]
