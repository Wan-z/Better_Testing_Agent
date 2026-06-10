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

from web.backend.config import (  # noqa: E402
    DRY_RUN, LLM_PROVIDER,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
)


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


def enrich_prose_with_llm(report: dict[str, Any]) -> dict[str, Any]:
    """Replace the deterministic report prose with a live LLM-generated version.

    Calls the configured LLM provider to rewrite `plain_language_summary` and
    `methods_text`. Falls back silently to the deterministic text on any error so
    the pipeline is never blocked by an LLM failure. No-ops in dry-run mode.
    """
    if DRY_RUN:
        return report

    tr = report.get("test_result", {})
    es = tr.get("effect_size", {})

    def _fmt(v: Any, decimals: int = 3) -> str:
        try:
            return f"{float(v):.{decimals}g}"
        except (TypeError, ValueError):
            return str(v)

    prompt = (
        f"A statistical test ({str(tr.get('test_used', '?')).replace('_', ' ')}) produced:\n"
        f"  p = {_fmt(tr.get('p_value'))},  "
        f"{es.get('measure_name', 'effect')} = {_fmt(es.get('value'))} "
        f"({es.get('interpretation', '')}, "
        f"95% CI [{_fmt(es.get('ci_lower'))}, {_fmt(es.get('ci_upper'))}]).\n"
        f"  Significant at α = 0.05: {'yes' if tr.get('is_significant') else 'no'}.\n\n"
        f"Existing plain-language summary (deterministic):\n{report.get('plain_language_summary', '')}\n\n"
        f"Existing methods text (deterministic):\n{report.get('methods_text', '')}\n\n"
        "Rewrite both for a research paper. Return ONLY valid JSON with keys "
        '"plain" (2–3 sentences, non-statistician audience, lead with the key finding) '
        'and "methods" (3–5 sentences, passive voice, journal style). '
        "No markdown, no extra keys."
    )

    try:
        if LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)
            msg = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text
        else:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=30.0)
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=600,
            )
            raw = resp.choices[0].message.content or ""

        import json as _json
        # Strip optional code-fence wrappers that some models emit.
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = _json.loads(clean)
        if parsed.get("plain"):
            report["plain_language_summary"] = parsed["plain"]
        if parsed.get("methods"):
            report["methods_text"] = parsed["methods"]
    except Exception:
        pass  # Deterministic text is already in the report — do not surface LLM errors.

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
