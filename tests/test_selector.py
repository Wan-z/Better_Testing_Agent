"""Tests for the deterministic test selector (`hta.modules.selector`).

Covers the §6.2 decision tree: the rank-vs-parametric rule, two/three-group dispatch, the
count and categorical branches, and the BET-driven association path (parabola → MaxBET).
"""

from __future__ import annotations

from hta.modules.profiler import profile_column
from hta.modules.selector import Selection, prefer_rank_based, select


def _cols(raw: dict[str, list[str]]) -> dict[str, object]:
    return {h: profile_column(h, raw[h]) for h in raw}


def _select(raw: dict[str, list[str]], outcome: str, group: str | None,
            predictor: str | None, prompt: str = "q") -> Selection:
    return select(_cols(raw), outcome, group, predictor, prompt, raw)


# ── distributional policy ─────────────────────────────────────────────────────

def test_prefer_rank_based() -> None:
    assert prefer_rank_based("ORDINAL", 5, "NONE") is True       # scale of measurement
    assert prefer_rank_based("CONTINUOUS", 50, "STRONG") is False  # CLT overrides
    assert prefer_rank_based("CONTINUOUS", 10, "STRONG") is True
    assert prefer_rank_based("CONTINUOUS", 10, "MILD") is False


# ── two-group continuous ──────────────────────────────────────────────────────

def test_welch_default_large_n() -> None:
    raw = {"y": [f"{(i % 7) + i * 0.13:.3f}" for i in range(60)],
           "arm": (["A"] * 30) + (["B"] * 30)}
    assert _select(raw, "y", "arm", None).test == "WELCH_T"


def test_mann_whitney_small_n_strong_skew() -> None:
    skewed = ([f"{1.0 + 0.1 * i:.2f}" for i in range(11)]) + ["40.0"]
    raw = {"y": skewed + skewed, "arm": (["A"] * 12) + (["B"] * 12)}
    cols = _cols(raw)
    assert cols["y"].var_type == "CONTINUOUS"
    assert select(cols, "y", "arm", None, "q", raw).test == "MANN_WHITNEY_U"


def test_paired_t_within_prompt() -> None:
    raw = {"y": [f"{(i % 7) + i * 0.13:.3f}" for i in range(60)],
           "arm": (["pre"] * 30) + (["post"] * 30)}
    assert _select(raw, "y", "arm", None, "before and after intervention").test == "PAIRED_T"


def test_ordinal_two_group_is_rank() -> None:
    raw = {"grade": [str((i % 5) + 1) for i in range(40)],
           "arm": (["A"] * 20) + (["B"] * 20)}
    assert _select(raw, "grade", "arm", None).test == "MANN_WHITNEY_U"


def test_wilcoxon_ordinal_within() -> None:
    raw = {"grade": [str((i % 5) + 1) for i in range(40)],
           "arm": (["pre"] * 20) + (["post"] * 20)}
    assert _select(raw, "grade", "arm", None, "matched before/after").test == "WILCOXON_SIGNED_RANK"


# ── three-group ───────────────────────────────────────────────────────────────

def test_welch_anova_three_groups() -> None:
    raw = {"y": [f"{(i % 7) + i * 0.11:.3f}" for i in range(90)],
           "arm": (["A"] * 30) + (["B"] * 30) + (["C"] * 30)}
    sel = _select(raw, "y", "arm", None)
    assert sel.test == "WELCH_ANOVA"
    assert any("post-hoc" in c for c in sel.caveats)


def test_kruskal_three_groups_ordinal() -> None:
    raw = {"grade": [str((i % 5) + 1) for i in range(60)],
           "arm": (["A"] * 20) + (["B"] * 20) + (["C"] * 20)}
    assert _select(raw, "grade", "arm", None).test == "KRUSKAL_WALLIS"


# ── count outcomes ────────────────────────────────────────────────────────────

def test_count_poisson_low_dispersion() -> None:
    raw = {"events": [str(20 + (i % 16)) for i in range(60)]}
    cols = _cols(raw)
    assert cols["events"].var_type == "COUNT"
    assert select(cols, "events", None, None, "q", raw).test == "POISSON_REGRESSION"


def test_count_negbin_overdispersed() -> None:
    pattern = [0, 0, 1, 2, 30, 40, 0, 1, 50, 2, 3, 0, 60, 1, 45, 0, 2, 70, 5, 0]
    raw = {"events": [str(v) for v in pattern * 3]}
    cols = _cols(raw)
    assert cols["events"].var_type == "COUNT"
    assert select(cols, "events", None, None, "q", raw).test == "NEGATIVE_BINOMIAL_REGRESSION"


# ── categorical ───────────────────────────────────────────────────────────────

def test_chi_squared_large_expected() -> None:
    raw = {"out": (["x"] * 30) + (["y"] * 30),
           "treat": ((["A"] * 15 + ["B"] * 15) * 2)}
    assert _select(raw, "out", "treat", None).test == "CHI_SQUARED"


def test_fisher_small_expected() -> None:
    raw = {"out": ["x", "x", "y", "y", "x", "y", "x", "y"],
           "treat": ["A", "B", "A", "B", "A", "A", "B", "B"]}
    assert _select(raw, "out", "treat", None).test == "FISHER_EXACT"


def test_mcnemar_within_2x2() -> None:
    raw = {"after": (["+"] * 20) + (["-"] * 20),
           "before": (["+"] * 10 + ["-"] * 10) * 2}
    assert _select(raw, "after", "before", None, "paired before/after").test == "MCNEMAR"


# ── association (BET path) ────────────────────────────────────────────────────

def test_association_parabola_is_maxbet() -> None:
    n = 160
    xs = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]
    raw = {"x": [f"{x:.4f}" for x in xs], "y": [f"{x * x:.4f}" for x in xs]}
    sel = _select(raw, "y", None, "x", "is y associated with x?")
    assert sel.test == "MAXBET"
    assert "BET" in sel.computed and sel.region


def test_association_linear_is_correlation() -> None:
    n = 60
    raw = {"x": [f"{i:.3f}" for i in range(n)],
           "y": [f"{2.0 * i + (i % 3):.3f}" for i in range(n)]}
    assert _select(raw, "y", None, "x").test in ("PEARSON_CORRELATION", "SPEARMAN_CORRELATION")


# ── degenerate ────────────────────────────────────────────────────────────────

def test_no_second_variable_continuous_is_unresolved() -> None:
    raw = {"y": [f"{i * 0.5:.2f}" for i in range(30)]}
    assert _select(raw, "y", None, None).test == "—"


def test_no_second_variable_categorical_hint() -> None:
    raw = {"c": (["x"] * 10) + (["y"] * 10) + (["z"] * 10)}
    assert _select(raw, "c", None, None).test == "CHI_SQUARED"
