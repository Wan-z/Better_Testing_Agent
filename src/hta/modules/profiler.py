"""DataProfiler — variable-type inference, normality severity, and the BET screen.

Two layers live here:

* a compact, **pure-stdlib** profiler (`profile_column`, `severity`, `_moments`) that
  infers a column's `VariableType` and graded normality departure (TECHNICAL_REPORT
  §6.1 / §6.5) from `list[str]` cells — no numpy/scipy/pandas, so the playground and
  the test selector can import it with zero third-party dependencies; and
* `build_data_profile(...)`, which assembles a full Pydantic `DataProfile` (descriptive
  stats, formal normality at N ≤ 2000, and the BET pairwise nonlinear-dependence screen)
  from a pandas DataFrame. Its scipy / pandas / `bet_screen` imports are deferred to call
  time so importing this module stays stdlib-only.

This is the single source of truth for profiling; the web backend and the playground
both call into it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import pandas as pd

    from hta.models.data import DataProfile, DependenceFinding

_ID_RE = re.compile(r"(^id$|_id$|uuid|mrn|fips|geoid)", re.IGNORECASE)
_COUNT_RE = re.compile(r"(count|n_|num_|visits|events|cases|deaths)", re.IGNORECASE)
# A duration / time-to-event column name (paired with an event indicator → survival analysis).
_TTE_RE = re.compile(r"(surviv|duration|follow.?up|time.?to|_tte|^tte$|^time$|_time$|_days$|"
                     r"_months$|days.to|months.to)", re.IGNORECASE)
# A right-censoring / event indicator column name (a 0/1 companion to a duration column).
EVENT_NAME_RE = re.compile(r"(event|status|death|dead|died|censor|relapse|recur|progress|"
                           r"observed)", re.IGNORECASE)
_MISSING = {"", "na", "nan", "null", "none", "."}

# Formal normality test is run only at or below this N (TECHNICAL_REPORT §6.1): above it a
# one-sample test against estimated parameters is invalid and flags essentially everything,
# so severity comes from skew/kurtosis magnitude alone.
_FORMAL_NORMALITY_MAX_N = 2000

_NUMERIC_TYPES = ("CONTINUOUS", "ORDINAL", "COUNT")


# ── column profile (pure stdlib) ──────────────────────────────────────────────

@dataclass
class Column:
    name: str
    var_type: str                 # CONTINUOUS / ORDINAL / BINARY / CATEGORICAL / COUNT / IDENTIFIER
    n: int
    n_missing: int
    numeric: list[float] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    mean: float | None = None
    sd: float | None = None
    skew: float | None = None
    kurtosis: float | None = None     # excess kurtosis
    nonnormality: str | None = None   # NONE / MILD / STRONG (CONTINUOUS/ORDINAL only)
    notes: list[str] = field(default_factory=list)


def _to_float(s: str) -> float | None:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _moments(xs: list[float]) -> tuple[float, float, float, float]:
    """mean, sample sd, skew, excess kurtosis (population-style, guarded)."""
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    sd = math.sqrt(var)
    if sd == 0:
        return mean, 0.0, 0.0, 0.0
    skew = sum(((x - mean) / sd) ** 3 for x in xs) / n
    kurt = sum(((x - mean) / sd) ** 4 for x in xs) / n - 3.0
    sample_sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    return mean, sample_sd, skew, kurt


def severity(skew: float, kurt: float) -> str:
    """Graded normality departure from skew/excess-kurtosis (§6.1 thresholds)."""
    if abs(skew) >= 2 or abs(kurt) >= 7:
        return "STRONG"
    if abs(skew) >= 1 or abs(kurt) >= 2:
        return "MILD"
    return "NONE"


def profile_column(name: str, raw: list[str]) -> Column:
    present = [v for v in raw if v.strip().lower() not in _MISSING]
    n_missing = len(raw) - len(present)
    nums = [_to_float(v) for v in present]
    all_numeric = nums and all(x is not None for x in nums)
    uniq = sorted(set(present))

    col = Column(name=name, var_type="CATEGORICAL", n=len(present), n_missing=n_missing)

    if _ID_RE.search(name) and len(uniq) > 0.9 * max(1, len(present)):
        col.var_type = "IDENTIFIER"
        col.categories = uniq[:12]
        return col

    if all_numeric:
        vals = [x for x in nums if x is not None]
        col.numeric = vals
        ints = all(abs(x - round(x)) < 1e-9 for x in vals)
        n_uniq = len(set(vals))
        if n_uniq <= 2:
            col.var_type = "BINARY"
            col.categories = [str(u) for u in sorted(set(vals))]
            return col
        if all(x >= 0 for x in vals) and n_uniq > 8 and _TTE_RE.search(name):
            col.var_type = "TIME_TO_EVENT"          # duration; survival needs an event companion
        elif ints and all(x >= 0 for x in vals) and (_COUNT_RE.search(name) and n_uniq > 10):
            col.var_type = "COUNT"
        elif ints and n_uniq <= 10:
            col.var_type = "ORDINAL"
        else:
            col.var_type = "CONTINUOUS"
        mean, sd, sk, ku = _moments(vals)
        col.mean, col.sd, col.skew, col.kurtosis = mean, sd, sk, ku
        if col.var_type in ("CONTINUOUS", "ORDINAL", "TIME_TO_EVENT"):
            col.nonnormality = severity(sk, ku)
        if sd == 0:
            col.notes.append("constant (zero variance)")
        else:
            n_out = sum(1 for x in vals if abs((x - mean) / sd) > 3.5)
            if n_out:
                col.notes.append(f"{n_out} outlier(s) detected (|Z| > 3.5)")
    else:
        col.categories = uniq[:12]
        col.var_type = "BINARY" if len(uniq) == 2 else "CATEGORICAL"

    if n_missing and len(raw):
        pct = 100.0 * n_missing / len(raw)
        if pct > 5:
            col.notes.append(f"{pct:.0f}% missing")
    return col


# ── full DataProfile assembly (pandas + scipy + BET screen) ───────────────────

# Upper bound on pairs screened by the BET EDA (p-values are Bonferroni-corrected across
# them). High enough to cover wide dependence-screen datasets (100 columns → 4 950 pairs)
# while still bounding pathological widths.
_MAX_SCREEN_PAIRS = 5000

# Cap on how many screened pairs are echoed into the profile payload. All significant pairs
# are always kept; this only bounds the strongest non-significant extras so the stored profile
# stays small (a 100-column screen has ~5 000 findings).
_MAX_REPORTED_FINDINGS = 50


def _is_unnamed_index(name: object) -> bool:
    """True for a pandas auto-named blank-header column (a CSV row index) — an artefact,
    not a variable, so it must be kept out of the pairwise screen."""
    s = str(name).strip()
    return s == "" or s.startswith("Unnamed:")


def build_data_profile(
    df: "pd.DataFrame",
    outcome: Optional[str],
    group: Optional[str],
    *,
    run_screen: bool = True,
    max_screen_pairs: int = _MAX_SCREEN_PAIRS,
    max_reported_findings: int = _MAX_REPORTED_FINDINGS,
    seed: int = 0,
) -> DataProfile:
    """Assemble a `DataProfile`: engine type inference + descriptive stats + formal
    normality (Shapiro-Wilk at N ≤ 2000; none above, per §6.1) + the BET pairwise
    nonlinear-dependence screen (`DataProfile.nonlinear_dependencies`).

    Presentation-only EDA plots (`eda_plots`/`eda_summary`) are left empty here — those
    are attached by the web layer, which owns Plotly rendering.
    """
    return profile_with_screen(
        df, outcome, group, run_screen=run_screen, max_screen_pairs=max_screen_pairs,
        max_reported_findings=max_reported_findings, seed=seed,
    )[0]


@dataclass
class ScreenContext:
    """The one-shot BET screen, so a caller can build both the profile's
    `nonlinear_dependencies` and (in the web layer) the EDA plots without re-screening."""

    cols: dict[str, Column]
    numeric_names: list[str]
    aligned: Any                  # pandas DataFrame of the aligned numeric columns
    numeric_columns: dict[str, list[float]]
    screen: Any                   # bet_screen.ScreenResult


def profile_with_screen(
    df: "pd.DataFrame",
    outcome: Optional[str],
    group: Optional[str],
    *,
    run_screen: bool = True,
    max_screen_pairs: int = _MAX_SCREEN_PAIRS,
    max_reported_findings: int = _MAX_REPORTED_FINDINGS,
    seed: int = 0,
) -> tuple["DataProfile", Optional[ScreenContext]]:
    """Assemble the `DataProfile` and return the BET screen context alongside it (or None
    when there are too few numeric columns/rows to screen). The screen runs exactly once;
    the web layer reuses the returned context to build its EDA plots."""
    import pandas as pd
    from scipy import stats as scipy_stats

    from hta.models.data import (
        DataProfile,
        DistributionStats,
        NormalityTest,
        Variable,
        VariableType,
    )

    # astype(str) on float64 columns leaves NaN as float objects in newer pandas;
    # apply(str) uses Python's str() which correctly converts float('nan') → 'nan'.
    cols = {col: profile_column(col, df[col].apply(str).tolist()) for col in df.columns}
    variables: list[Variable] = []

    for col in df.columns:
        vtype = cols[col].var_type
        n_obs = int(df[col].notna().sum())
        n_miss = int(df[col].isna().sum())
        dist: Optional[DistributionStats] = None
        normality: Optional[NormalityTest] = None
        unique_values: Optional[list[str]] = None

        if vtype in _NUMERIC_TYPES and pd.api.types.is_numeric_dtype(df[col]):
            series = df[col].dropna().astype(float)
            dist = DistributionStats(
                mean=round(float(series.mean()), 4),
                std=round(float(series.std()), 4),
                median=round(float(series.median()), 4),
                iqr=round(float(series.quantile(0.75) - series.quantile(0.25)), 4),
                skewness=round(float(series.skew()), 4),
                kurtosis=round(float(series.kurtosis()), 4),
                min=round(float(series.min()), 4),
                max=round(float(series.max()), 4),
            )
            # Formal normality only at N ≤ 2000 (§6.1); above that severity is judged from
            # skew/kurtosis alone (already in `dist`), so no formal test is attached.
            if (vtype in ("CONTINUOUS", "ORDINAL") and 3 <= len(series)
                    <= _FORMAL_NORMALITY_MAX_N):
                stat, p = scipy_stats.shapiro(series)
                normality = NormalityTest(
                    name="Shapiro-Wilk",
                    statistic=round(float(stat), 4),
                    p_value=round(float(p), 4),
                    is_normal=float(p) > 0.05,
                )
        elif vtype in ("BINARY", "CATEGORICAL"):
            unique_values = [str(v) for v in df[col].dropna().unique().tolist()][:20]

        variables.append(Variable(
            name=col,
            variable_type=VariableType(vtype),
            n_observations=n_obs,
            n_missing=n_miss,
            distribution_stats=dist,
            normality=normality,
            unique_values=unique_values,
        ))

    ctx = _run_screen(df, cols, max_screen_pairs, seed) if run_screen else None
    findings, bet_note = _findings_from_screen(ctx, max_reported_findings)

    notes: list[str] = []
    for col in df.columns:
        pct_miss = df[col].isna().mean() * 100
        if pct_miss > 5:
            notes.append(f"{col}: {pct_miss:.1f}% missing values")
    if bet_note:
        notes.append(bet_note)

    profile = DataProfile(
        variables=variables,
        n_groups=int(df[group].nunique()) if group and group in df.columns else None,
        group_variable=group,
        outcome_variable=outcome,
        notes=notes,
        nonlinear_dependencies=findings,
    )
    return profile, ctx


def _run_screen(
    df: "pd.DataFrame", cols: dict[str, Column], max_screen_pairs: int, seed: int,
) -> Optional[ScreenContext]:
    """Run the BET pairwise nonlinear-dependence screen over the numeric columns once."""
    import pandas as pd

    from hta.bet_screen import pairwise_screen

    numeric_names = [c for c in df.columns
                     if cols[c].var_type in _NUMERIC_TYPES and not _is_unnamed_index(c)]
    if len(numeric_names) < 2:
        return None
    aligned = df[numeric_names].apply(pd.to_numeric, errors="coerce").dropna()
    if len(aligned) < 8:
        return None
    numeric_columns = {c: [float(v) for v in aligned[c].tolist()] for c in numeric_names}
    screen = pairwise_screen(numeric_columns, max_pairs=max_screen_pairs, seed=seed)
    return ScreenContext(cols, numeric_names, aligned, numeric_columns, screen)


def _findings_from_screen(
    ctx: Optional[ScreenContext], max_reported_findings: int,
) -> tuple[list["DependenceFinding"], Optional[str]]:
    """Convert the screen's strongest pairs into ranked `DependenceFinding`s + a note."""
    if ctx is None:
        return [], None
    from hta.models.data import DependenceFinding

    screen = ctx.screen
    # Keep all significant pairs plus the strongest remaining ones (findings are already
    # sorted by BET strength) so the profile payload stays small.
    sig_findings = [f for f in screen.findings if f.significant]
    extra = [f for f in screen.findings if not f.significant]
    reported = sig_findings + extra[: max(0, max_reported_findings - len(sig_findings))]

    findings = [DependenceFinding(
        x=f.x, y=f.y, n=f.n, bet_statistic_s=f.bet_statistic_s,
        bet_z=round(f.bet_z, 4), p_value=f.p_value, bid=f.bid, form=f.form,
        direction=f.direction, pearson_r=round(f.pearson_r, 4),
        spearman_rho=round(f.spearman_rho, 4), nonlinear_only=f.nonlinear_only,
        significant=f.significant,
    ) for f in reported]

    n_sig = sum(1 for f in findings if f.significant)
    note: Optional[str] = None
    if n_sig:
        n_nl = sum(1 for f in findings if f.nonlinear_only)
        nl_phrase = f", {n_nl} nonlinear-only" if n_nl else ""
        note = (f"BET screen: {n_sig} dependent pair(s) found{nl_phrase} "
                f"across {len(ctx.numeric_names)} numeric columns.")
    return findings, note


# Names re-exported through `playground/pipeline.py` for backward compatibility.
__all__ = [
    "Column", "profile_column", "severity", "build_data_profile", "profile_with_screen",
    "ScreenContext", "_to_float", "_moments", "_MISSING",
]
