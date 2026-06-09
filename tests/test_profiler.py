"""Tests for the engine profiler (`hta.modules.profiler`).

Covers the pure-stdlib type inference and severity grading, plus the full `DataProfile`
assembly (descriptive stats, formal normality at N ≤ 2000, and the BET screen) and the
shared one-shot screen context.
"""

from __future__ import annotations

import pandas as pd

from hta.models.data import DataProfile, VariableType
from hta.modules.profiler import (
    build_data_profile,
    profile_column,
    profile_with_screen,
    severity,
)


def test_profile_column_types() -> None:
    assert profile_column("id", [str(i) for i in range(20)]).var_type == "IDENTIFIER"
    assert profile_column("x", [f"{i * 0.7 + 0.1:.2f}" for i in range(20)]).var_type == "CONTINUOUS"
    assert profile_column("flag", (["yes"] * 8) + (["no"] * 8)).var_type == "BINARY"
    assert profile_column("grade", [str(i % 5 + 1) for i in range(20)]).var_type == "ORDINAL"
    assert profile_column("events", [str(20 + (i % 16)) for i in range(40)]).var_type == "COUNT"
    assert profile_column("city", ["NYC", "LA", "SF", "BOS", "LA"]).var_type == "CATEGORICAL"


def test_severity_thresholds() -> None:
    assert severity(0.2, 0.5) == "NONE"
    assert severity(1.4, 0.0) == "MILD"
    assert severity(2.5, 0.0) == "STRONG"
    assert severity(0.0, 8.0) == "STRONG"


def test_missing_flagged() -> None:
    col = profile_column("v", ["1.0", "", "na", "3.0", "4.0", "5.0", "6.0", "7.0"])
    assert col.n_missing == 2
    assert any("missing" in n for n in col.notes)


def test_build_data_profile_shape() -> None:
    n = 80
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    df = pd.DataFrame({"x": xs, "y": [x * x for x in xs], "arm": (["A"] * 40) + (["B"] * 40)})
    profile = build_data_profile(df, "y", "arm")
    assert isinstance(profile, DataProfile)
    assert profile.outcome_variable == "y"
    assert profile.n_groups == 2
    names = {v.name: v for v in profile.variables}
    assert names["x"].variable_type == VariableType.CONTINUOUS
    assert names["x"].distribution_stats is not None
    assert names["x"].normality is not None and names["x"].normality.name == "Shapiro-Wilk"
    # The parabola pair is a nonlinear-only dependence the screen should flag.
    assert any(f.nonlinear_only and f.significant for f in profile.nonlinear_dependencies)


def test_profile_with_screen_returns_context() -> None:
    n = 40
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    df = pd.DataFrame({"x": xs, "y": [x * x for x in xs]})
    profile, ctx = profile_with_screen(df, "y", None)
    assert isinstance(profile, DataProfile)
    assert ctx is not None
    assert set(ctx.numeric_names) == {"x", "y"}
    assert ctx.screen.findings  # at least one screened pair


def test_large_n_skips_formal_normality() -> None:
    # N > 2000: no formal normality test is run (§6.1); severity comes from skew/kurtosis.
    df = pd.DataFrame({"v": [float(i % 97) for i in range(2500)],
                       "arm": [("A" if i % 2 else "B") for i in range(2500)]})
    profile = build_data_profile(df, "v", "arm")
    v = next(x for x in profile.variables if x.name == "v")
    assert v.distribution_stats is not None
    assert v.normality is None


def test_too_few_numeric_columns_no_screen() -> None:
    df = pd.DataFrame({"v": [float(i) for i in range(20)], "arm": ["A", "B"] * 10})
    profile = build_data_profile(df, "v", "arm")
    assert profile.nonlinear_dependencies == []
