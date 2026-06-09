"""HypothesisTestingAgent — the top-level orchestrator.

Wires the pipeline in order — profile → (study design) → select → execute → report —
sharing the Pydantic models as the lingua franca between stages. The deliberate v0.1.0
simplification is that the pipeline is a direct call chain (no event bus): it is strictly
linear, and a synchronous bus added indirection without buying swappability that the CLI /
web callers use. Each stage lives in `hta.modules.*` and is independently testable.

The study-design dialogue and causal-adjustment stages are not yet wired into this
orchestrator; until they are, `run()` uses a default observational design (or one supplied
by the caller). `dry_run` is accepted for forward compatibility with the LLM prose stage.
"""

from __future__ import annotations

import io
from typing import Any, Optional, Union

import pandas as pd

from hta.models.data import DataProfile
from hta.models.design import MeasurementType, StudyDesign, StudyDesignType
from hta.models.report import Report
from hta.modules.causal import CausalAnalyser
from hta.modules.executor import execute
from hta.modules.profiler import Column, build_data_profile, profile_column
from hta.modules.reporter import build_report
from hta.modules.selector import Selection, select

DataInput = Union[pd.DataFrame, list[dict[str, Any]], str, dict[str, list[Any]]]

_NUMERIC_TYPES = ("CONTINUOUS", "ORDINAL", "COUNT")


def _default_design() -> StudyDesign:
    return StudyDesign(
        design_type=StudyDesignType.OBSERVATIONAL,
        measurement_type=MeasurementType.BETWEEN_SUBJECTS,
        is_randomized=False,
        notes=["No design dialogue completed; assuming an observational, "
               "between-subjects design."],
    )


def _to_frame(data: DataInput) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    if isinstance(data, str):
        return pd.read_csv(io.StringIO(data))
    return pd.DataFrame(data)


def _choose_predictor(df: pd.DataFrame, cols: dict[str, Column], outcome: str,
                      group: Optional[str]) -> Optional[str]:
    """For a no-group correlation analysis, pick the numeric column most BET-dependent
    with the outcome (so the association uses the most interesting partner)."""
    if group:
        return None
    if outcome not in cols or cols[outcome].var_type not in _NUMERIC_TYPES:
        return None
    candidates = [c for c in df.columns
                  if c != outcome and cols[c].var_type in _NUMERIC_TYPES]
    if not candidates:
        return None
    from hta.bet_screen import maxbet
    y = pd.to_numeric(df[outcome], errors="coerce")
    best: Optional[tuple[str, float]] = None
    for c in candidates:
        sub = pd.DataFrame({"x": pd.to_numeric(df[c], errors="coerce"), "y": y}).dropna()
        if len(sub) < 8:
            continue
        try:
            z = maxbet(sub["x"].tolist(), sub["y"].tolist(), seed=0).bet_z
        except Exception:
            z = -1.0
        if best is None or z > best[1]:
            best = (c, z)
    return best[0] if best else candidates[0]


class HypothesisTestingAgent:
    """End-to-end statistical-reasoning pipeline over a tabular dataset."""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def run(
        self,
        data: DataInput,
        hypothesis: str,
        outcome_variable: str,
        group_variable: Optional[str] = None,
        predictor_variable: Optional[str] = None,
        design: Optional[StudyDesign] = None,
    ) -> Report:
        df = _to_frame(data)
        if outcome_variable not in df.columns:
            raise ValueError(f"Outcome variable {outcome_variable!r} is not a column in the data.")

        profile: DataProfile = build_data_profile(df, outcome_variable, group_variable)
        design = design or _default_design()
        graph = CausalAnalyser().analyse(profile, design)   # causal stage (§5.3)

        cols = {c: profile_column(c, df[c].astype(str).tolist()) for c in df.columns}
        raw = {c: df[c].astype(str).tolist() for c in df.columns}
        predictor = predictor_variable or _choose_predictor(df, cols, outcome_variable,
                                                             group_variable)

        selection: Selection = select(cols, outcome_variable, group_variable, predictor,
                                       hypothesis, raw)
        test_name = selection.test
        if test_name in ("—", "", None):
            if predictor:
                test_name = "PEARSON_CORRELATION"
                selection.test = test_name
            else:
                raise ValueError(
                    "Could not select a test — specify a group_variable (for a comparison) "
                    "or a predictor_variable (for an association).")

        result = execute(test_name, df, outcome_variable, group_variable, predictor,
                         design, selection)
        return build_report(profile, design, result, selection, df, outcome_variable,
                            group_variable, predictor, hypothesis, graph=graph)
