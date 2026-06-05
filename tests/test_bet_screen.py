"""Tests for the BET pairwise-dependence EDA engine (src/hta/bet_screen.py).

Pure standard library — no numpy/scipy/pydantic — so these run anywhere. The key
behaviours verified mirror the paper's claims: BET catches nonlinear dependence
that Pearson/Spearman miss, labels its form, and stays quiet under independence.
"""

from __future__ import annotations

import math
import random

from hta.bet_screen import (
    DEFAULT_ALPHA,
    LINEAR_NULL_THRESHOLD,
    cross_region,
    empirical_copula,
    interaction_plot,
    maxbet,
    maxbet_twostage,
    pairwise_screen,
    relationship_form,
)


def _rng(seed: int = 7) -> random.Random:
    return random.Random(seed)


def test_monotone_increasing() -> None:
    rng = _rng()
    x = [rng.uniform(-3, 3) for _ in range(400)]
    y = [xi + rng.gauss(0, 0.3) for xi in x]
    res = maxbet(x, y, seed=1)
    assert res.significant
    assert res.form in ("MONOTONE", "LINEAR")
    assert res.direction == "increasing"
    assert res.pearson_r > 0.8
    assert not res.nonlinear_only


def test_monotone_decreasing_direction() -> None:
    rng = _rng(11)
    x = [rng.uniform(-3, 3) for _ in range(400)]
    y = [-2.0 * xi + rng.gauss(0, 0.3) for xi in x]
    res = maxbet(x, y, seed=2)
    assert res.significant
    assert res.direction == "decreasing"


def test_parabola_is_nonlinear_only() -> None:
    # y = x^2: strong dependence, but Pearson/Spearman ~ 0 (the paper's headline).
    rng = _rng(3)
    x = [rng.uniform(-1, 1) for _ in range(500)]
    y = [xi * xi + rng.gauss(0, 0.02) for xi in x]
    res = maxbet(x, y, seed=3)
    assert res.significant
    assert abs(res.pearson_r) < LINEAR_NULL_THRESHOLD
    assert res.nonlinear_only
    # The dominant form must be a genuinely nonlinear one, not monotone/linear.
    assert res.form in ("PARABOLIC", "SINUSOIDAL", "CHECKERBOARD", "COMPLEX")
    assert relationship_form(res.form) == "nonlinear"


def test_independence_not_significant() -> None:
    rng = _rng(5)
    x = [rng.gauss(0, 1) for _ in range(400)]
    y = [rng.gauss(0, 1) for _ in range(400)]
    res = maxbet(x, y, seed=5)
    assert not res.significant
    assert res.form == "INDEPENDENT"
    assert not res.nonlinear_only


def test_tie_jitter_no_crash_and_valid_copula() -> None:
    # Heavy ties (zero-inflation / imputed values) must not break the copula.
    rng = _rng(9)
    x = [0.0] * 200 + [rng.uniform(1, 5) for _ in range(200)]
    u = empirical_copula(x, rng)
    assert len(u) == len(x)
    assert all(0.0 < val <= 1.0 for val in u)
    # ranks are strictly distinct after jitter -> 400 distinct copula values
    assert len(set(u)) == len(x)


def test_pairwise_screen_ranks_and_flags() -> None:
    rng = _rng(2)
    n = 400
    t = [rng.uniform(-1, 1) for _ in range(n)]
    cols = {
        "linear_y":   [2 * ti + rng.gauss(0, 0.2) for ti in t],   # vs t: monotone
        "parabola_y": [ti * ti + rng.gauss(0, 0.02) for ti in t],  # vs t: nonlinear-only
        "noise":      [rng.gauss(0, 1) for _ in range(n)],          # independent
        "t":          t,
    }
    res = pairwise_screen(cols, seed=0)
    assert res.n_pairs == 6
    # findings sorted by BET strength descending
    zs = [f.bet_z for f in res.findings]
    assert zs == sorted(zs, reverse=True)
    # the parabola/t pair should be flagged nonlinear-only
    para = next(f for f in res.findings
                if {f.x, f.y} == {"parabola_y", "t"})
    assert para.significant
    assert para.nonlinear_only
    assert res.n_nonlinear_only >= 1


def test_pairwise_screen_matches_per_pair_maxbet() -> None:
    # The optimised (precomputed) screen must produce exactly what calling maxbet on each
    # pair would, plus the screen-level Bonferroni correction across the pairs.
    rng = _rng(8)
    n = 140
    t = [rng.uniform(-1, 1) for _ in range(n)]
    cols = {
        "lin": [2 * ti + rng.gauss(0, 0.2) for ti in t],
        "para": [ti * ti + rng.gauss(0, 0.02) for ti in t],
        "noise": [rng.gauss(0, 1) for _ in range(n)],
        "t": t,
    }
    res = pairwise_screen(cols, seed=0)
    names = list(cols)
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]
    npairs = len(pairs)
    by_key = {frozenset((f.x, f.y)): f for f in res.findings}
    for xa, yb in pairs:
        mb = maxbet(cols[xa], cols[yb], seed=0)
        f = by_key[frozenset((xa, yb))]
        assert f.bid == mb.bid
        assert f.bet_statistic_s == mb.bet_statistic_s
        assert math.isclose(f.bet_z, mb.bet_z, rel_tol=1e-9)
        assert math.isclose(f.pearson_r, mb.pearson_r, rel_tol=1e-7, abs_tol=1e-12)
        assert math.isclose(f.spearman_rho, mb.spearman_rho, rel_tol=1e-7, abs_tol=1e-12)
        assert math.isclose(f.p_value, min(1.0, mb.p_value * npairs), rel_tol=1e-9)
        assert f.significant == (f.p_value < DEFAULT_ALPHA)


def test_z_matches_statistic() -> None:
    rng = _rng(1)
    x = [rng.uniform(-2, 2) for _ in range(256)]
    y = [xi + rng.gauss(0, 0.5) for xi in x]
    res = maxbet(x, y, seed=0)
    assert math.isclose(res.bet_z, abs(res.bet_statistic_s) / math.sqrt(res.n), rel_tol=1e-9)


# ── Zhang (2019) additions: regions and two-stage Max BET ─────────────────────

def test_cross_region_partitions_grid() -> None:
    # A cross interaction splits the 2^d × 2^d copula grid into two equal halves
    # (the BID's defining symmetry, Zhang 2019 §3.3 / Fig. 2).
    for d in (1, 2, 3):
        g = 1 << d
        pos, neg = cross_region(tuple(range(1, d + 1)), (1,), d)
        assert len(pos) == len(neg) == g * g // 2
        assert set(pos).isdisjoint(neg)
        assert len(set(pos) | set(neg)) == g * g


def test_maxbet_populates_region_when_significant() -> None:
    rng = _rng(3)
    x = [rng.uniform(-1, 1) for _ in range(500)]
    y = [xi * xi + rng.gauss(0, 0.02) for xi in x]
    res = maxbet(x, y, seed=3)
    assert res.significant
    assert res.positive_region                      # non-empty
    assert len(res.positive_region) == res.grid_size ** 2 // 2
    assert res.region_description                    # human summary present


def test_twostage_detects_nonlinear_band_missed_by_correlation() -> None:
    # A cosine band (the §7 "Milky Way" flavour): strong dependence, ~zero Pearson,
    # and a structure that needs depth > 2 — so the two-stage search is what catches it.
    rng = _rng(4)
    x = [rng.uniform(0, 1) for _ in range(256)]
    y = [0.5 + 0.4 * math.cos(4 * math.pi * xi) + rng.gauss(0, 0.05) for xi in x]
    res = maxbet_twostage(x, y, seed=1)
    assert res.significant
    assert abs(res.pearson_r) < LINEAR_NULL_THRESHOLD
    assert res.depth >= 2
    assert res.positive_region                       # shows where the dependence lives
    assert relationship_form(res.form) in ("nonlinear", "monotone")


def test_twostage_quiet_under_independence() -> None:
    rng = _rng(5)
    x = [rng.gauss(0, 1) for _ in range(300)]
    y = [rng.gauss(0, 1) for _ in range(300)]
    res = maxbet_twostage(x, y, seed=2)
    assert not res.significant
    assert res.form == "INDEPENDENT"
    assert res.positive_region == []


# ── interaction_plot: data for the Xiang-style binary-interaction EDA scatter ──

def test_interaction_plot_matches_maxbet_and_sums_to_s() -> None:
    # The plot's dominant interaction and stats must equal maxbet's (same depth-2
    # search, same seed), and the per-point interaction signs must sum to S.
    rng = _rng(3)
    x = [rng.uniform(-1, 1) for _ in range(500)]
    y = [xi * xi + rng.gauss(0, 0.02) for xi in x]
    ip = interaction_plot(x, y, x_name="x", y_name="y", seed=3)
    mb = maxbet(x, y, seed=3)
    assert ip.bid == mb.bid
    assert ip.form == mb.form
    assert ip.bet_statistic_s == mb.bet_statistic_s
    assert math.isclose(ip.bet_z, mb.bet_z, rel_tol=1e-12)
    assert ip.significant == mb.significant
    assert len(ip.u) == len(ip.v) == len(ip.point_sign) == len(x)
    assert all(s in (-1, 1) for s in ip.point_sign)
    assert sum(ip.point_sign) == ip.bet_statistic_s
    assert all(0.0 < c <= 1.0 for c in ip.u)
    assert all(0.0 < c <= 1.0 for c in ip.v)


def test_interaction_plot_region_grid_is_balanced() -> None:
    rng = _rng(3)
    x = [rng.uniform(-1, 1) for _ in range(300)]
    y = [xi * xi + rng.gauss(0, 0.02) for xi in x]
    ip = interaction_plot(x, y, seed=3)
    assert ip.grid_size == 4 and ip.depth == 2
    assert len(ip.region_grid) == 4 and all(len(row) == 4 for row in ip.region_grid)
    flat = [c for row in ip.region_grid for c in row]
    assert all(c in (-1, 1) for c in flat)
    # A cross interaction splits the 4×4 grid into two equal halves (Zhang 2019 §3.3).
    assert flat.count(1) == flat.count(-1) == 8


def test_interaction_plot_independent_quiet() -> None:
    rng = _rng(5)
    x = [rng.gauss(0, 1) for _ in range(400)]
    y = [rng.gauss(0, 1) for _ in range(400)]
    ip = interaction_plot(x, y, seed=5)
    assert not ip.significant
    assert ip.form == "INDEPENDENT"
    # Plot data stays well-formed even when nothing is detected.
    assert len(ip.point_sign) == 400
    assert sum(ip.point_sign) == ip.bet_statistic_s
