"""Tests for all shared Pydantic data models.

Covers: valid construction, validation rejection of bad inputs, and JSON round-trip
serialisation/deserialisation for every model.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from hta.models.data import (
    DataProfile,
    DependenceFinding,
    DependenceForm,
    DistributionStats,
    NormalityTest,
    Variable,
    VariableType,
)
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


# ---------------------------------------------------------------------------
# Enum completeness
# ---------------------------------------------------------------------------


class TestVariableTypeEnum:
    def test_all_values_exist(self) -> None:
        assert {t.value for t in VariableType} == {
            "CONTINUOUS", "ORDINAL", "CATEGORICAL", "BINARY",
            "COUNT", "TIME_TO_EVENT", "DATETIME", "GEOSPATIAL", "IDENTIFIER",
        }

    def test_count(self) -> None:
        assert len(VariableType) == 9

    def test_healthcare_data_forms_present(self) -> None:
        # Count/rate and survival outcomes are first-class, not coerced to CONTINUOUS.
        assert VariableType.COUNT == "COUNT"
        assert VariableType.TIME_TO_EVENT == "TIME_TO_EVENT"


class TestDependenceFormEnum:
    def test_all_values_exist(self) -> None:
        assert {f.value for f in DependenceForm} == {
            "LINEAR", "MONOTONE", "PARABOLIC", "SINUSOIDAL",
            "CHECKERBOARD", "COMPLEX", "INDEPENDENT",
        }


class TestStudyDesignTypeEnum:
    def test_all_values_exist(self) -> None:
        assert StudyDesignType.EXPERIMENTAL == "EXPERIMENTAL"
        assert StudyDesignType.OBSERVATIONAL == "OBSERVATIONAL"
        assert StudyDesignType.QUASI_EXPERIMENTAL == "QUASI_EXPERIMENTAL"


class TestMeasurementTypeEnum:
    def test_all_values_exist(self) -> None:
        assert MeasurementType.BETWEEN_SUBJECTS == "BETWEEN_SUBJECTS"
        assert MeasurementType.WITHIN_SUBJECTS == "WITHIN_SUBJECTS"
        assert MeasurementType.MIXED == "MIXED"


class TestVariableRoleEnum:
    def test_all_values_exist(self) -> None:
        roles = {r.value for r in VariableRole}
        assert roles == {"CONFOUNDER", "COLLIDER", "MEDIATOR", "EFFECT_MODIFIER", "COVARIATE"}


class TestStatisticalTestEnum:
    EXPECTED = {
        "INDEPENDENT_T", "PAIRED_T", "WELCH_T", "ONE_WAY_ANOVA", "WELCH_ANOVA",
        "KRUSKAL_WALLIS", "MANN_WHITNEY_U", "WILCOXON_SIGNED_RANK", "CHI_SQUARED",
        "FISHER_EXACT", "MCNEMAR", "PEARSON_CORRELATION", "SPEARMAN_CORRELATION",
        "MAXBET", "BEAST",
        "POISSON_REGRESSION", "NEGATIVE_BINOMIAL_REGRESSION",
        "LOG_RANK", "COX_REGRESSION", "ROC_AUC",
        "LINEAR_REGRESSION", "LOGISTIC_REGRESSION",
        "LINEAR_MIXED_MODEL", "GENERALIZED_ESTIMATING_EQUATIONS",
    }

    def test_all_values_exist(self) -> None:
        assert {t.value for t in StatisticalTest} == self.EXPECTED

    def test_count(self) -> None:
        assert len(StatisticalTest) == 24

    def test_healthcare_tests_present(self) -> None:
        # Count/rate, survival, and diagnostic methods are selectable in v0.1.0.
        for t in ("POISSON_REGRESSION", "NEGATIVE_BINOMIAL_REGRESSION",
                  "LOG_RANK", "COX_REGRESSION", "ROC_AUC"):
            assert t in {m.value for m in StatisticalTest}


class TestAssumptionStatusEnum:
    def test_all_values_exist(self) -> None:
        assert {s.value for s in AssumptionStatus} == {"MET", "VIOLATED", "UNTESTABLE", "MARGINAL"}


class TestCaveatSeverityEnum:
    def test_all_values_exist(self) -> None:
        assert {s.value for s in CaveatSeverity} == {"INFO", "WARNING", "CRITICAL"}


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------


class TestDistributionStats:
    def test_construction(self, distribution_stats: DistributionStats) -> None:
        assert distribution_stats.mean == 5.0
        assert distribution_stats.std == 1.5
        assert distribution_stats.iqr == 2.0

    def test_all_fields_present(self, distribution_stats: DistributionStats) -> None:
        for field in ("mean", "std", "median", "iqr", "skewness", "kurtosis", "min", "max"):
            assert hasattr(distribution_stats, field)


class TestNormalityTest:
    def test_is_normal_true_when_p_above_threshold(self) -> None:
        nt = NormalityTest(name="Shapiro-Wilk", statistic=0.98, p_value=0.10, is_normal=True)
        assert nt.is_normal is True

    def test_is_normal_false_when_p_below_threshold(self) -> None:
        nt = NormalityTest(name="Shapiro-Wilk", statistic=0.85, p_value=0.01, is_normal=False)
        assert nt.is_normal is False

    def test_ks_test_name(self) -> None:
        nt = NormalityTest(name="Kolmogorov-Smirnov", statistic=0.05, p_value=0.40, is_normal=True)
        assert "Kolmogorov" in nt.name


class TestVariable:
    def test_continuous_variable(self, continuous_variable: Variable) -> None:
        assert continuous_variable.variable_type == VariableType.CONTINUOUS
        assert continuous_variable.distribution_stats is not None
        assert continuous_variable.normality is not None

    def test_categorical_variable(self, categorical_variable: Variable) -> None:
        assert categorical_variable.variable_type == VariableType.CATEGORICAL
        assert categorical_variable.unique_values == ["control", "treatment_a", "treatment_b"]

    def test_binary_variable(self, binary_variable: Variable) -> None:
        assert binary_variable.variable_type == VariableType.BINARY
        assert len(binary_variable.unique_values or []) == 2  # type: ignore[arg-type]

    def test_ordinal_variable(self) -> None:
        v = Variable(
            name="pain_scale",
            variable_type=VariableType.ORDINAL,
            n_observations=50,
            n_missing=0,
            unique_values=["1", "2", "3", "4", "5"],
        )
        assert v.variable_type == VariableType.ORDINAL

    def test_count_variable(self) -> None:
        v = Variable(
            name="ed_visits", variable_type=VariableType.COUNT,
            n_observations=120, n_missing=0,
        )
        assert v.variable_type == VariableType.COUNT

    def test_time_to_event_variable(self) -> None:
        v = Variable(
            name="time_to_relapse_days", variable_type=VariableType.TIME_TO_EVENT,
            n_observations=200, n_missing=0,
        )
        assert v.variable_type == VariableType.TIME_TO_EVENT

    def test_optional_fields_default_none(self) -> None:
        v = Variable(
            name="x", variable_type=VariableType.CONTINUOUS, n_observations=10, n_missing=0
        )
        assert v.distribution_stats is None
        assert v.normality is None
        assert v.unique_values is None


class TestDataProfile:
    def test_construction(self, data_profile: DataProfile) -> None:
        assert len(data_profile.variables) == 2
        assert data_profile.n_groups == 2
        assert data_profile.outcome_variable == "blood_pressure"

    def test_notes_list(self, data_profile: DataProfile) -> None:
        assert isinstance(data_profile.notes, list)
        assert len(data_profile.notes) == 1

    def test_empty_notes_default(self) -> None:
        dp = DataProfile(variables=[])
        assert dp.notes == []

    def test_optional_fields_default_none(self) -> None:
        dp = DataProfile(variables=[])
        assert dp.n_groups is None
        assert dp.group_variable is None
        assert dp.outcome_variable is None
        assert dp.nonlinear_dependencies == []


class TestDependenceFinding:
    def _finding(self) -> DependenceFinding:
        return DependenceFinding(
            x="gene_a", y="gene_b", n=500, bet_statistic_s=-312, bet_z=13.95,
            p_value=1e-30, bid="A1A2B1", form=DependenceForm.PARABOLIC,
            direction="decreasing", pearson_r=-0.01, spearman_rho=0.08,
            nonlinear_only=True, significant=True,
        )

    def test_construction(self) -> None:
        f = self._finding()
        assert f.form == DependenceForm.PARABOLIC
        assert f.nonlinear_only is True

    def test_round_trip(self) -> None:
        f = self._finding()
        restored = DependenceFinding.model_validate_json(f.model_dump_json())
        assert restored == f

    def test_carried_on_profile(self) -> None:
        dp = DataProfile(variables=[], nonlinear_dependencies=[self._finding()])
        assert dp.nonlinear_dependencies[0].form == DependenceForm.PARABOLIC


class TestConfounder:
    def test_construction(self, confounder: Confounder) -> None:
        assert confounder.name == "age"
        assert confounder.role == VariableRole.CONFOUNDER
        assert confounder.is_measured is True
        assert confounder.adjustment_recommended is True

    def test_unmeasured_confounder(self) -> None:
        c = Confounder(
            name="socioeconomic_status",
            role=VariableRole.CONFOUNDER,
            is_measured=False,
            adjustment_recommended=False,
            rationale="Not captured in dataset.",
        )
        assert c.is_measured is False


class TestStudyDesign:
    def test_construction(self, study_design: StudyDesign) -> None:
        assert study_design.design_type == StudyDesignType.EXPERIMENTAL
        assert study_design.is_randomized is True
        assert len(study_design.confounders) == 1

    def test_empty_confounders_default(self) -> None:
        sd = StudyDesign(
            design_type=StudyDesignType.OBSERVATIONAL,
            measurement_type=MeasurementType.BETWEEN_SUBJECTS,
            is_randomized=False,
        )
        assert sd.confounders == []
        assert sd.notes == []
        assert sd.reporting_standard is None
        assert sd.subgroup_variables == []

    def test_reporting_standard_round_trip(self) -> None:
        sd = StudyDesign(
            design_type=StudyDesignType.OBSERVATIONAL,
            measurement_type=MeasurementType.BETWEEN_SUBJECTS,
            is_randomized=False,
            reporting_standard="STROBE",
        )
        restored = StudyDesign.model_validate_json(sd.model_dump_json())
        assert restored.reporting_standard == "STROBE"


class TestCausalGraph:
    def test_construction(self, causal_graph: CausalGraph) -> None:
        assert "treatment" in causal_graph.nodes
        assert ("treatment", "blood_pressure") in causal_graph.edges
        assert causal_graph.adjustment_set == ["age"]

    def test_edges_are_tuples(self, causal_graph: CausalGraph) -> None:
        for edge in causal_graph.edges:
            assert len(edge) == 2

    def test_empty_graph(self) -> None:
        g = CausalGraph(nodes=[], edges=[], adjustment_set=[])
        assert g.warnings == []


class TestAssumptionCheck:
    def test_construction(self, assumption_check: AssumptionCheck) -> None:
        assert assumption_check.status == AssumptionStatus.MET
        assert assumption_check.p_value == 0.32

    def test_optional_fields_absent(self) -> None:
        ac = AssumptionCheck(
            assumption_name="Independence",
            status=AssumptionStatus.UNTESTABLE,
            note="Cannot be tested from data alone.",
        )
        assert ac.test_used is None
        assert ac.statistic is None
        assert ac.p_value is None


class TestEffectSize:
    def test_construction(self, effect_size: EffectSize) -> None:
        assert effect_size.measure_name == "Cohen's d"
        assert effect_size.value == 0.52
        assert effect_size.interpretation == "medium"

    def test_cramers_v(self) -> None:
        es = EffectSize(
            measure_name="Cramér's V", value=0.25, interpretation="small",
            ci_lower=0.10, ci_upper=0.40,
        )
        assert es.measure_name == "Cramér's V"


class TestTestResult:
    def test_construction(self, test_result: TestResult) -> None:
        assert test_result.test_used == StatisticalTest.INDEPENDENT_T
        assert test_result.is_significant is True
        assert test_result.confidence_interval == (0.5, 2.1)

    def test_confidence_interval_is_tuple(self, test_result: TestResult) -> None:
        ci = test_result.confidence_interval
        assert len(ci) == 2

    def test_not_significant(self) -> None:
        es = EffectSize(measure_name="Cohen's d", value=0.05, interpretation="negligible",
                        ci_lower=-0.20, ci_upper=0.30)
        tr = TestResult(
            test_used=StatisticalTest.WELCH_T,
            statistic=0.8,
            p_value=0.42,
            effect_size=es,
            confidence_interval=(-1.0, 2.5),
            is_significant=False,
        )
        assert tr.is_significant is False
        assert tr.power is None

    def test_cox_hazard_ratio_result(self) -> None:
        # Survival outcome: effect size is a hazard ratio with a ratio-scale CI.
        es = EffectSize(measure_name="hazard ratio", value=0.62, interpretation="protective",
                        ci_lower=0.45, ci_upper=0.85)
        tr = TestResult(
            test_used=StatisticalTest.COX_REGRESSION,
            statistic=-0.478, p_value=0.003, effect_size=es,
            confidence_interval=(0.45, 0.85), is_significant=True,
            notes=["Proportional-hazards assumption checked via scaled Schoenfeld residuals."],
        )
        restored = TestResult.model_validate_json(tr.model_dump_json())
        assert restored.test_used == StatisticalTest.COX_REGRESSION
        assert restored.effect_size.measure_name == "hazard ratio"

    def test_poisson_incidence_rate_ratio_result(self) -> None:
        # Count/rate outcome: effect size is an incidence-rate ratio.
        es = EffectSize(measure_name="incidence-rate ratio", value=1.34, interpretation="harmful",
                        ci_lower=1.12, ci_upper=1.60)
        tr = TestResult(
            test_used=StatisticalTest.NEGATIVE_BINOMIAL_REGRESSION,
            statistic=3.1, p_value=0.002, effect_size=es,
            confidence_interval=(1.12, 1.60), is_significant=True,
            notes=["Overdispersion detected (variance > mean) — negative binomial used over Poisson."],
        )
        assert tr.effect_size.value == 1.34
        assert tr.test_used == StatisticalTest.NEGATIVE_BINOMIAL_REGRESSION


class TestCaveat:
    def test_construction(self, caveat: Caveat) -> None:
        assert caveat.severity == CaveatSeverity.WARNING

    def test_critical_caveat(self) -> None:
        c = Caveat(
            severity=CaveatSeverity.CRITICAL,
            message="Normality assumption violated.",
            recommendation="Use a non-parametric test.",
        )
        assert c.severity == CaveatSeverity.CRITICAL

    def test_info_caveat(self) -> None:
        c = Caveat(
            severity=CaveatSeverity.INFO,
            message="Observational study.",
            recommendation="Avoid causal language.",
        )
        assert c.severity == CaveatSeverity.INFO


class TestPlotSpec:
    def test_construction(self, plot_spec: PlotSpec) -> None:
        assert plot_spec.plot_type == "boxplot"
        assert "control" in plot_spec.data

    def test_data_dict_arbitrary_values(self) -> None:
        ps = PlotSpec(
            plot_type="scatter",
            data={"x": [1, 2, 3], "y": [4, 5, 6], "label": "group_a"},
            title="Scatter", x_label="X", y_label="Y",
        )
        assert ps.data["label"] == "group_a"


class TestReport:
    def test_construction(self, report: Report) -> None:
        assert report.test_result.is_significant is True
        assert len(report.caveats) == 1
        assert len(report.plots) == 1

    def test_methods_text_non_empty(self, report: Report) -> None:
        assert len(report.methods_text) > 0

    def test_empty_caveats_and_plots(self) -> None:
        ds = DistributionStats(mean=0, std=1, median=0, iqr=1, skewness=0, kurtosis=0, min=-3, max=3)
        var = Variable(name="x", variable_type=VariableType.CONTINUOUS, n_observations=30, n_missing=0,
                       distribution_stats=ds)
        dp = DataProfile(variables=[var])
        sd = StudyDesign(design_type=StudyDesignType.EXPERIMENTAL,
                         measurement_type=MeasurementType.BETWEEN_SUBJECTS, is_randomized=True)
        es = EffectSize(measure_name="Cohen's d", value=0.4, interpretation="small",
                        ci_lower=0.1, ci_upper=0.7)
        tr = TestResult(test_used=StatisticalTest.INDEPENDENT_T, statistic=2.0, p_value=0.05,
                        effect_size=es, confidence_interval=(0.0, 1.0), is_significant=False)
        r = Report(data_profile=dp, study_design=sd, test_result=tr,
                   plain_language_summary="No significant difference.", methods_text="t-test was used.")
        assert r.caveats == []
        assert r.plots == []


# ---------------------------------------------------------------------------
# Validation rejection of invalid inputs
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_variable_type_invalid(self) -> None:
        with pytest.raises(ValidationError):
            Variable.model_validate({
                "name": "x", "variable_type": "INVALID_TYPE",
                "n_observations": 100, "n_missing": 0,
            })

    def test_variable_missing_required_field(self) -> None:
        with pytest.raises(ValidationError):
            Variable.model_validate({"name": "x", "variable_type": "CONTINUOUS"})

    def test_distribution_stats_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            DistributionStats.model_validate({
                "mean": "not_a_number", "std": 1.0, "median": 0.0,
                "iqr": 1.0, "skewness": 0.0, "kurtosis": 0.0, "min": -1.0, "max": 1.0,
            })

    def test_normality_test_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            NormalityTest.model_validate({"name": "Shapiro-Wilk"})

    def test_assumption_status_invalid(self) -> None:
        with pytest.raises(ValidationError):
            AssumptionCheck.model_validate({
                "assumption_name": "Normality", "status": "UNKNOWN", "note": "test",
            })

    def test_statistical_test_invalid(self) -> None:
        with pytest.raises(ValidationError):
            EffectSize.model_validate({
                "measure_name": "d", "value": 0.5, "interpretation": "medium",
                "ci_lower": 0.1, "ci_upper": 0.9,
            })
            TestResult.model_validate({
                "test_used": "NONEXISTENT_TEST", "statistic": 1.0, "p_value": 0.05,
                "effect_size": {}, "confidence_interval": [0.0, 1.0], "is_significant": False,
            })

    def test_caveat_severity_invalid(self) -> None:
        with pytest.raises(ValidationError):
            Caveat.model_validate({
                "severity": "URGENT", "message": "test", "recommendation": "fix it",
            })

    def test_study_design_type_invalid(self) -> None:
        with pytest.raises(ValidationError):
            StudyDesign.model_validate({
                "design_type": "RANDOMIZED", "measurement_type": "BETWEEN_SUBJECTS",
                "is_randomized": True,
            })

    def test_report_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Report.model_validate({"plain_language_summary": "hello"})


# ---------------------------------------------------------------------------
# JSON round-trip serialisation
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    def test_distribution_stats(self, distribution_stats: DistributionStats) -> None:
        json_str = distribution_stats.model_dump_json()
        restored = DistributionStats.model_validate_json(json_str)
        assert restored == distribution_stats

    def test_normality_test(self, normality_test: NormalityTest) -> None:
        json_str = normality_test.model_dump_json()
        restored = NormalityTest.model_validate_json(json_str)
        assert restored == normality_test

    def test_variable(self, continuous_variable: Variable) -> None:
        json_str = continuous_variable.model_dump_json()
        restored = Variable.model_validate_json(json_str)
        assert restored == continuous_variable

    def test_data_profile(self, data_profile: DataProfile) -> None:
        json_str = data_profile.model_dump_json()
        restored = DataProfile.model_validate_json(json_str)
        assert restored == data_profile

    def test_confounder(self, confounder: Confounder) -> None:
        json_str = confounder.model_dump_json()
        restored = Confounder.model_validate_json(json_str)
        assert restored == confounder

    def test_study_design(self, study_design: StudyDesign) -> None:
        json_str = study_design.model_dump_json()
        restored = StudyDesign.model_validate_json(json_str)
        assert restored == study_design

    def test_causal_graph(self, causal_graph: CausalGraph) -> None:
        json_str = causal_graph.model_dump_json()
        restored = CausalGraph.model_validate_json(json_str)
        assert restored.nodes == causal_graph.nodes
        assert restored.adjustment_set == causal_graph.adjustment_set
        # edges round-trip as list[list[str]] in JSON but Pydantic coerces back to tuples
        for orig, rest in zip(causal_graph.edges, restored.edges):
            assert tuple(rest) == orig

    def test_assumption_check(self, assumption_check: AssumptionCheck) -> None:
        json_str = assumption_check.model_dump_json()
        restored = AssumptionCheck.model_validate_json(json_str)
        assert restored == assumption_check

    def test_effect_size(self, effect_size: EffectSize) -> None:
        json_str = effect_size.model_dump_json()
        restored = EffectSize.model_validate_json(json_str)
        assert restored == effect_size

    def test_test_result(self, test_result: TestResult) -> None:
        json_str = test_result.model_dump_json()
        restored = TestResult.model_validate_json(json_str)
        assert restored.test_used == test_result.test_used
        assert restored.is_significant == test_result.is_significant
        assert tuple(restored.confidence_interval) == test_result.confidence_interval

    def test_caveat(self, caveat: Caveat) -> None:
        json_str = caveat.model_dump_json()
        restored = Caveat.model_validate_json(json_str)
        assert restored == caveat

    def test_plot_spec(self, plot_spec: PlotSpec) -> None:
        json_str = plot_spec.model_dump_json()
        restored = PlotSpec.model_validate_json(json_str)
        assert restored.plot_type == plot_spec.plot_type
        assert restored.title == plot_spec.title

    def test_report(self, report: Report) -> None:
        json_str = report.model_dump_json()
        restored = Report.model_validate_json(json_str)
        assert restored.plain_language_summary == report.plain_language_summary
        assert restored.methods_text == report.methods_text
        assert len(restored.caveats) == len(report.caveats)
        assert len(restored.plots) == len(report.plots)
        assert restored.test_result.test_used == report.test_result.test_used

    def test_model_dump_produces_valid_json(self, report: Report) -> None:
        raw = report.model_dump()
        json_str = json.dumps(raw)  # must not raise
        assert isinstance(json_str, str)
