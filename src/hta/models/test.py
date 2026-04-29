"""Pydantic models for statistical test selection, assumption checking, and results."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StatisticalTest(str, Enum):
    """Enumeration of all statistical tests the agent can select and execute."""

    INDEPENDENT_T = "INDEPENDENT_T"
    PAIRED_T = "PAIRED_T"
    WELCH_T = "WELCH_T"
    ONE_WAY_ANOVA = "ONE_WAY_ANOVA"
    KRUSKAL_WALLIS = "KRUSKAL_WALLIS"
    MANN_WHITNEY_U = "MANN_WHITNEY_U"
    WILCOXON_SIGNED_RANK = "WILCOXON_SIGNED_RANK"
    CHI_SQUARED = "CHI_SQUARED"
    FISHER_EXACT = "FISHER_EXACT"
    MCNEMAR = "MCNEMAR"
    PEARSON_CORRELATION = "PEARSON_CORRELATION"
    SPEARMAN_CORRELATION = "SPEARMAN_CORRELATION"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    LOGISTIC_REGRESSION = "LOGISTIC_REGRESSION"


class AssumptionStatus(str, Enum):
    """Outcome of checking a statistical assumption."""

    MET = "MET"
    VIOLATED = "VIOLATED"
    UNTESTABLE = "UNTESTABLE"
    MARGINAL = "MARGINAL"


class AssumptionCheck(BaseModel):
    """Result of checking a single statistical assumption."""

    assumption_name: str
    status: AssumptionStatus
    test_used: Optional[str] = None
    statistic: Optional[float] = None
    p_value: Optional[float] = None
    note: str


class EffectSize(BaseModel):
    """Standardised effect size estimate with confidence interval.

    measure_name examples: "Cohen's d", "Cramér's V", "rank-biserial r",
    "eta-squared", "odds ratio".
    interpretation follows Cohen (1988) conventions where applicable.
    """

    measure_name: str
    value: float
    interpretation: str  # e.g. "small", "medium", "large"
    ci_lower: float
    ci_upper: float


class TestResult(BaseModel):
    """Complete output of a statistical test, including effect size and assumption checks.

    is_significant uses a fixed alpha of 0.05; downstream consumers may apply
    their own threshold.
    """

    test_used: StatisticalTest
    statistic: float
    p_value: float
    degrees_of_freedom: Optional[float] = None
    effect_size: EffectSize
    assumption_checks: list[AssumptionCheck] = Field(default_factory=list)
    confidence_interval: tuple[float, float]
    is_significant: bool  # p_value < 0.05
    power: Optional[float] = None
    notes: list[str] = Field(default_factory=list)
