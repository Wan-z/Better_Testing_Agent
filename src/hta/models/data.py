"""Pydantic models for dataset profiling: variables, distributions, normality."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    """Statistical measurement level of a variable."""

    CONTINUOUS = "CONTINUOUS"
    ORDINAL = "ORDINAL"
    CATEGORICAL = "CATEGORICAL"
    BINARY = "BINARY"


class DistributionStats(BaseModel):
    """Descriptive statistics for a numeric variable."""

    mean: float
    std: float
    median: float
    iqr: float
    skewness: float
    kurtosis: float
    min: float
    max: float


class NormalityTest(BaseModel):
    """Result of a formal normality test (Shapiro-Wilk or Kolmogorov-Smirnov).

    is_normal is True when p_value > 0.05 (fail to reject H0 of normality).
    """

    name: str
    statistic: float
    p_value: float
    is_normal: bool


class Variable(BaseModel):
    """Complete profile of a single variable in the dataset."""

    name: str
    variable_type: VariableType
    n_observations: int
    n_missing: int
    distribution_stats: Optional[DistributionStats] = None
    normality: Optional[NormalityTest] = None
    unique_values: Optional[list[str]] = None  # populated for CATEGORICAL and BINARY


class DataProfile(BaseModel):
    """Complete characterisation of the input dataset, produced by the profiler."""

    variables: list[Variable]
    n_groups: Optional[int] = None
    group_variable: Optional[str] = None
    outcome_variable: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
