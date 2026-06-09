"""Thin web adapter over the canonical engine reporter (`hta.modules.reporter`).

Parses the stored dict boundary (profile/design/test_result JSON) into Pydantic models,
calls the engine to build a typed `Report`, then serialises back to a dict and re-attaches
the presentation-only BET EDA plots (which carry `plotly_json` and are not part of the typed
`Report.plots`). The rare "no test could be selected" result cannot populate the strict
`TestResult` enum, so it is reported via a minimal fallback that still surfaces caveats/plots.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# Make the engine (`hta`, under src/) importable.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from hta.models.data import DataProfile  # noqa: E402
from hta.models.design import (  # noqa: E402
    MeasurementType,
    StudyDesign,
    StudyDesignType,
)
from hta.models.test import TestResult  # noqa: E402
from hta.modules.reporter import build_report as _build_report  # noqa: E402


def _default_design() -> StudyDesign:
    return StudyDesign(
        design_type=StudyDesignType.OBSERVATIONAL,
        measurement_type=MeasurementType.BETWEEN_SUBJECTS,
        is_randomized=False,
        notes=["No design dialogue completed; assuming an observational design."],
    )


def _attach_eda(report_dict: dict[str, Any], profile: dict[str, Any]) -> None:
    """Append the web profile's pre-enriched BET EDA plots to the report plots."""
    eda = profile.get("eda_plots") if isinstance(profile, dict) else None
    if eda:
        report_dict["plots"] = list(report_dict.get("plots", [])) + list(eda)


def _degenerate_report(profile: dict[str, Any], design: dict[str, Any],
                       test_result: dict[str, Any], selection: Any,
                       hypothesis: str) -> dict[str, Any]:
    """Minimal report for the case where no valid test was selected (test_used == '—')."""
    caveats = [{"severity": "WARNING", "message": c,
                "recommendation": "Choose a group or predictor variable to form a test."}
               for c in (getattr(selection, "caveats", None) or [])]
    msg = ("No statistical test could be selected for this combination of variables. "
           "Pick a grouping variable (for a comparison) or a predictor (for an association).")
    report = {
        "data_profile": profile,
        "study_design": design,
        "test_result": test_result,
        "plain_language_summary": msg,
        "caveats": caveats,
        "plots": [],
        "methods_text": msg,
    }
    _attach_eda(report, profile)
    return report


def build_report(
    profile: dict[str, Any],
    design: dict[str, Any],
    test_result: dict[str, Any],
    selection: Any,
    df: pd.DataFrame,
    outcome: str,
    group: Optional[str],
    predictor: Optional[str],
    hypothesis: str,
) -> dict[str, Any]:
    """Assemble the report dict the SSE pipeline stores and streams."""
    try:
        result_model = TestResult.model_validate(test_result)
    except Exception:
        return _degenerate_report(profile, design, test_result, selection, hypothesis)

    try:
        design_model = StudyDesign.model_validate(design)
    except Exception:
        design_model = _default_design()
    profile_model = DataProfile.model_validate(profile)

    report = _build_report(profile_model, design_model, result_model, selection, df,
                           outcome, group, predictor, hypothesis)
    report_dict = report.model_dump(mode="json")
    _attach_eda(report_dict, profile)
    return report_dict
