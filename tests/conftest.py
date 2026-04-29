"""Shared pytest fixtures for the HTA test suite."""

from __future__ import annotations

import pytest

from hta.models.data import DataProfile, DistributionStats, NormalityTest, Variable, VariableType
from hta.models.design import (
    CausalGraph,
    Confounder,
    MeasurementType,
    StudyDesign,
    StudyDesignType,
    VariableRole,
)
from hta.models.report import Caveat, CaveatSeverity, PlotSpec, Report
from hta.models.test import AssumptionCheck, AssumptionStatus, EffectSize, StatisticalTest, TestResult


@pytest.fixture
def distribution_stats() -> DistributionStats:
    return DistributionStats(
        mean=5.0, std=1.5, median=5.0, iqr=2.0,
        skewness=0.1, kurtosis=-0.2, min=1.0, max=9.0,
    )


@pytest.fixture
def normality_test() -> NormalityTest:
    return NormalityTest(name="Shapiro-Wilk", statistic=0.98, p_value=0.32, is_normal=True)


@pytest.fixture
def continuous_variable(distribution_stats: DistributionStats, normality_test: NormalityTest) -> Variable:
    return Variable(
        name="blood_pressure",
        variable_type=VariableType.CONTINUOUS,
        n_observations=100,
        n_missing=2,
        distribution_stats=distribution_stats,
        normality=normality_test,
    )


@pytest.fixture
def categorical_variable() -> Variable:
    return Variable(
        name="treatment_group",
        variable_type=VariableType.CATEGORICAL,
        n_observations=100,
        n_missing=0,
        unique_values=["control", "treatment_a", "treatment_b"],
    )


@pytest.fixture
def binary_variable() -> Variable:
    return Variable(
        name="recovered",
        variable_type=VariableType.BINARY,
        n_observations=100,
        n_missing=1,
        unique_values=["yes", "no"],
    )


@pytest.fixture
def data_profile(continuous_variable: Variable, categorical_variable: Variable) -> DataProfile:
    return DataProfile(
        variables=[continuous_variable, categorical_variable],
        n_groups=2,
        group_variable="treatment_group",
        outcome_variable="blood_pressure",
        notes=["2 missing values in blood_pressure"],
    )


@pytest.fixture
def confounder() -> Confounder:
    return Confounder(
        name="age",
        role=VariableRole.CONFOUNDER,
        is_measured=True,
        adjustment_recommended=True,
        rationale="Age affects both treatment assignment and blood pressure.",
    )


@pytest.fixture
def study_design(confounder: Confounder) -> StudyDesign:
    return StudyDesign(
        design_type=StudyDesignType.EXPERIMENTAL,
        measurement_type=MeasurementType.BETWEEN_SUBJECTS,
        is_randomized=True,
        confounders=[confounder],
        notes=["Randomised controlled trial"],
    )


@pytest.fixture
def causal_graph() -> CausalGraph:
    return CausalGraph(
        nodes=["treatment", "blood_pressure", "age"],
        edges=[("treatment", "blood_pressure"), ("age", "blood_pressure"), ("age", "treatment")],
        adjustment_set=["age"],
        warnings=[],
    )


@pytest.fixture
def assumption_check() -> AssumptionCheck:
    return AssumptionCheck(
        assumption_name="Normality",
        status=AssumptionStatus.MET,
        test_used="Shapiro-Wilk",
        statistic=0.98,
        p_value=0.32,
        note="Distribution does not significantly deviate from normality.",
    )


@pytest.fixture
def effect_size() -> EffectSize:
    return EffectSize(
        measure_name="Cohen's d",
        value=0.52,
        interpretation="medium",
        ci_lower=0.21,
        ci_upper=0.83,
    )


@pytest.fixture
def test_result(assumption_check: AssumptionCheck, effect_size: EffectSize) -> TestResult:
    return TestResult(
        test_used=StatisticalTest.INDEPENDENT_T,
        statistic=3.14,
        p_value=0.002,
        degrees_of_freedom=98.0,
        effect_size=effect_size,
        assumption_checks=[assumption_check],
        confidence_interval=(0.5, 2.1),
        is_significant=True,
        power=0.85,
        notes=["Equal variances assumed (Levene p=0.45)."],
    )


@pytest.fixture
def caveat() -> Caveat:
    return Caveat(
        severity=CaveatSeverity.WARNING,
        message="p-value is marginal (0.03).",
        recommendation="Replicate with a larger sample before drawing strong conclusions.",
    )


@pytest.fixture
def plot_spec() -> PlotSpec:
    return PlotSpec(
        plot_type="boxplot",
        data={"control": [1.0, 2.0, 3.0], "treatment": [4.0, 5.0, 6.0]},
        title="Blood pressure by group",
        x_label="Group",
        y_label="Blood pressure (mmHg)",
    )


@pytest.fixture
def report(
    data_profile: DataProfile,
    study_design: StudyDesign,
    test_result: TestResult,
    caveat: Caveat,
    plot_spec: PlotSpec,
) -> Report:
    return Report(
        data_profile=data_profile,
        study_design=study_design,
        test_result=test_result,
        plain_language_summary=(
            "The treatment group had significantly lower blood pressure than the control group "
            "(p=0.002). The effect was medium in size (Cohen's d=0.52)."
        ),
        caveats=[caveat],
        plots=[plot_spec],
        methods_text=(
            "An independent-samples t-test was used to compare blood pressure between "
            "treatment and control groups. Normality was confirmed via Shapiro-Wilk. "
            "Effect size was estimated as Cohen's d with 95% CI via bootstrapping."
        ),
    )
