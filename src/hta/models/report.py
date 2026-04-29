"""Pydantic models for the final analysis report: caveats, plot specs, and the Report."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from hta.models.data import DataProfile
from hta.models.design import StudyDesign
from hta.models.test import TestResult


class CaveatSeverity(str, Enum):
    """Urgency level of a methodological caveat."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Caveat(BaseModel):
    """A methodological concern flagged for the reader, with a recommended action."""

    severity: CaveatSeverity
    message: str
    recommendation: str


class PlotSpec(BaseModel):
    """Declarative specification for a plot; actual rendering is handled separately.

    data holds the raw values needed to produce the plot (e.g. group arrays,
    x/y vectors). plot_type examples: "histogram", "boxplot", "scatter", "qqplot".
    """

    plot_type: str
    data: dict[str, Any]
    title: str
    x_label: str
    y_label: str


class Report(BaseModel):
    """Complete analysis report assembled by the reporter module.

    methods_text is auto-generated prose suitable for inclusion in a
    research paper methods section.
    plain_language_summary is written for a non-statistician reader.
    """

    data_profile: DataProfile
    study_design: StudyDesign
    test_result: TestResult
    plain_language_summary: str
    caveats: list[Caveat] = Field(default_factory=list)
    plots: list[PlotSpec] = Field(default_factory=list)
    methods_text: str
