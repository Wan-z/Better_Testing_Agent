"""CausalAnalyser — turns the captured confounders into a causal graph and an adjustment set.

This is the agent's "reason about causal structure" stage (TECHNICAL_REPORT §5.3). It builds
a `CausalGraph` (nodes; exposure→outcome and confounder→{outcome, exposure} edges; the minimal
adjustment set; and warnings for unmeasured confounders), and exposes
`usable_adjustment_covariates(...)` — the subset of confounders that can *actually* be used to
adjust an estimate (recommended, measured, and present in the data as a usable numeric column).
The executor consumes that subset to produce an adjusted estimate, and the reporter uses it to
turn "X is an unadjusted confounder" into an accurate, per-confounder caveat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

    from hta.models.data import DataProfile
    from hta.models.design import CausalGraph, StudyDesign


def _confounder_records(design: Any) -> list[dict[str, Any]]:
    """Normalise confounders from a `StudyDesign` model *or* a plain dict to a list of dicts,
    so the engine works whether it is called from the typed pipeline or the web's JSON layer."""
    if design is None:
        return []
    confs = design.get("confounders", []) if isinstance(design, dict) else design.confounders
    records: list[dict[str, Any]] = []
    for c in confs or []:
        if isinstance(c, dict):
            records.append(c)
        else:
            role = getattr(c, "role", None)
            records.append({
                "name": c.name,
                "is_measured": c.is_measured,
                "adjustment_recommended": c.adjustment_recommended,
                "rationale": getattr(c, "rationale", ""),
                "role": getattr(role, "value", role) or "CONFOUNDER",
            })
    return records


class CausalAnalyser:
    """Build a `CausalGraph` from a study design's confounders."""

    def analyse(self, profile: "DataProfile", design: "StudyDesign") -> "CausalGraph":
        from hta.models.design import CausalGraph

        outcome = profile.outcome_variable or "outcome"
        exposure = profile.group_variable
        records = _confounder_records(design)

        nodes: list[str] = [outcome]
        if exposure and exposure not in nodes:
            nodes.append(exposure)
        edges: list[tuple[str, str]] = []
        if exposure:
            edges.append((exposure, outcome))

        adjustment_set: list[str] = []
        warnings: list[str] = []
        for c in records:
            name = c.get("name")
            if not name:
                continue
            if name not in nodes:
                nodes.append(name)
            edges.append((name, outcome))            # confounder → outcome
            if exposure:
                edges.append((name, exposure))       # confounder → exposure
            if c.get("adjustment_recommended"):
                if c.get("is_measured"):
                    adjustment_set.append(name)
                else:
                    rationale = str(c.get("rationale", "")).strip()
                    warnings.append(
                        f"Unmeasured confounder '{name}' is recommended for adjustment but was "
                        f"not measured; the estimate may be biased."
                        + (f" {rationale}" if rationale else ""))
        return CausalGraph(nodes=nodes, edges=edges, adjustment_set=adjustment_set,
                           warnings=warnings)


def usable_adjustment_covariates(
    design: Any, df: "pd.DataFrame", exclude: set[str],
) -> list[str]:
    """The confounders that can actually be used to adjust an estimate: recommended for
    adjustment, measured, not the outcome/exposure themselves, and present in the data as a
    usable (numeric, non-constant) covariate."""
    import pandas as pd

    out: list[str] = []
    for c in _confounder_records(design):
        name = c.get("name")
        if not name or name in exclude or name in out:
            continue
        if not c.get("adjustment_recommended") or not c.get("is_measured"):
            continue
        if name not in df.columns:
            continue
        col = pd.to_numeric(df[name], errors="coerce")
        if int(col.notna().sum()) >= 3 and int(col.nunique()) > 1:
            out.append(name)
    return out
