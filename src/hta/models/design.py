"""Pydantic models for study design: design type, measurement, confounders, causal graph."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StudyDesignType(str, Enum):
    """Broad category of research design."""

    EXPERIMENTAL = "EXPERIMENTAL"
    OBSERVATIONAL = "OBSERVATIONAL"
    QUASI_EXPERIMENTAL = "QUASI_EXPERIMENTAL"


class MeasurementType(str, Enum):
    """Relationship between observations across groups."""

    BETWEEN_SUBJECTS = "BETWEEN_SUBJECTS"
    WITHIN_SUBJECTS = "WITHIN_SUBJECTS"
    MIXED = "MIXED"


class VariableRole(str, Enum):
    """Causal role of a variable relative to the exposure-outcome relationship."""

    CONFOUNDER = "CONFOUNDER"
    COLLIDER = "COLLIDER"
    MEDIATOR = "MEDIATOR"
    EFFECT_MODIFIER = "EFFECT_MODIFIER"
    COVARIATE = "COVARIATE"


class Confounder(BaseModel):
    """A variable identified as playing a specific causal role in the analysis."""

    name: str
    role: VariableRole
    is_measured: bool
    adjustment_recommended: bool
    rationale: str


class StudyDesign(BaseModel):
    """Captured study design, produced by the dialogue module after user interaction."""

    design_type: StudyDesignType
    measurement_type: MeasurementType
    is_randomized: bool
    confounders: list[Confounder] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CausalGraph(BaseModel):
    """Directed acyclic graph (DAG) representing causal structure of the study.

    edges are ordered pairs (cause, effect). adjustment_set lists variables
    that must be conditioned on to obtain an unconfounded estimate.
    """

    nodes: list[str]
    edges: list[tuple[str, str]]
    adjustment_set: list[str]
    warnings: list[str] = Field(default_factory=list)
