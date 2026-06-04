"""Pydantic models for dataset profiling: variables, distributions, normality."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    """Measurement level / structural role of a variable.

    The first four are classical statistical measurement levels. The remainder let
    the agent recognise and correctly route the data forms that dominate healthcare
    and epidemiology rather than mis-analysing them as plain continuous numbers:

    - ``COUNT`` — non-negative event counts (optionally per person-time / population),
      e.g. ED visits, hospitalisations. Modelled with Poisson / negative-binomial
      regression and reported as incidence-rate ratios, not means.
    - ``TIME_TO_EVENT`` — survival / duration data, typically with right-censoring
      (paired with an event indicator). Analysed with Kaplan–Meier, log-rank, and
      Cox regression (hazard ratios).
    - ``DATETIME`` — timestamps/dates; used to derive durations or time series, not
      tested directly.
    - ``GEOSPATIAL`` — coordinates or areal units (lat/long, FIPS, region); used for
      mapping/heatmaps and to flag spatial pitfalls (ecological fallacy, MAUP,
      spatial autocorrelation), not used as an analysis outcome.
    - ``IDENTIFIER`` — keys/IDs (record id, MRN); excluded from statistical testing.
    """

    CONTINUOUS = "CONTINUOUS"
    ORDINAL = "ORDINAL"
    CATEGORICAL = "CATEGORICAL"
    BINARY = "BINARY"
    COUNT = "COUNT"
    TIME_TO_EVENT = "TIME_TO_EVENT"
    DATETIME = "DATETIME"
    GEOSPATIAL = "GEOSPATIAL"
    IDENTIFIER = "IDENTIFIER"


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
