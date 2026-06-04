"""Pairwise nonlinear-dependence screening via Binary Expansion Testing (BET).

This implements the exploratory-data-analysis (EDA) workflow of

    Xiang, Zhang, Liu, Hoadley, Perou, Zhang & Marron,
    "Pairwise Nonlinear Dependence Analysis of Genomic Data", arXiv:2202.09880,

adapted as the dependence-discovery stage of the Hypothesis Testing Agent. The
goal is to surface dependence — *especially nonlinear dependence that Pearson /
Spearman miss* — between every pair of numeric variables, label the **form** of
that dependence, and flag when it is driven by structure invisible to linear
methods (a signal that latent subgroups / subtypes may be present).

Method (depth d = 2, the resolution the paper recommends):

1. **Copula transform** — map each variable to the empirical copula on (0, 1] via
   ranks. This is marginal-free and robust to outliers.
2. **Tie handling** — piled-up values (zeros, imputed values, detection limits)
   violate BET's continuity assumption, so tied observations are *jittered* by a
   small deterministic amount before ranking (paper §3.1).
3. **Binary expansion to depth 2** — each copula value falls in one of four
   quarters; its first two bits give A1, A2 (and B1, B2 for the partner). With the
   sign-coded products there are (2^2 − 1)(2^2 − 1) = 9 "cross interactions", the
   nine Binary Interaction Designs (BIDs) of Figure 2.
4. **Symmetry statistics** — for each BID, S = Σ Ȧ·Ḃ (difference of point counts in
   the white vs blue regions). Under independence S ≈ 0 and Z = |S|/√n is ~N(0,1).
5. **MaxBET** — take the BID with the largest |S|; its sign gives the direction and
   its label gives the *form*; Bonferroni-adjust the p-value across the 9 BIDs.

The module is pure standard library (no numpy/scipy) so it is dependency-free and
directly unit-testable; the DataProfiler wraps its output into Pydantic models.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# Significance level used for the per-pair (post-Bonferroni-across-BIDs) decision.
DEFAULT_ALPHA = 0.05
# |r| below which a linear/monotone coefficient is treated as "no linear signal";
# a BET-significant pair under this threshold is flagged as nonlinear-only.
LINEAR_NULL_THRESHOLD = 0.10

# The 9 depth-2 BIDs as (X-interaction, Y-interaction) over {"1", "2", "12"}, where
# "1"/"2" are the first/second binary-expansion bits and "12" their product.
_INTERACTIONS = ("1", "2", "12")
_BIDS = [(a, b) for a in _INTERACTIONS for b in _INTERACTIONS]

# Dominant-BID → human-readable form of dependence. Reflected BID pairs (e.g.
# A1A2B1 / A1B1B2) describe the same shape with the roles of X and Y swapped, so
# they map to the same form (paper §2.2 reflection property).
_BID_FORM = {
    ("1", "1"): "MONOTONE",        # A1B1 — monotone (linear-like) trend
    ("12", "12"): "LINEAR",        # A1A2B1B2 — the near-linear / diagonal BID
    ("12", "1"): "PARABOLIC",      # A1A2B1  ┐ opening parabola
    ("1", "12"): "PARABOLIC",      # A1B1B2  ┘ (reflection)
    ("2", "1"): "SINUSOIDAL",      # A2B1    ┐ "W" / bimodal
    ("1", "2"): "SINUSOIDAL",      # A1B2    ┘ (reflection)
    ("2", "2"): "CHECKERBOARD",    # A2B2 — clustered / mixture (subtype-suggestive)
    ("12", "2"): "COMPLEX",        # A1A2B2  ┐ higher-order asymmetric
    ("2", "12"): "COMPLEX",        # A2B1B2  ┘ (reflection)
}
# Forms whose typical cause is a mixture of latent subpopulations — the paper's
# subtype-driven patterns. Used to prompt the subgroup question in the dialogue.
SUBTYPE_SUGGESTIVE_FORMS = {"CHECKERBOARD", "SINUSOIDAL", "PARABOLIC"}


@dataclass
class PairDependence:
    """BET result for one variable pair, plus the linear-method comparison."""

    x: str
    y: str
    n: int
    bet_statistic_s: int          # symmetry statistic S of the dominant BID (signed)
    bet_z: float                  # |S| / sqrt(n)
    p_value: float                # two-sided, Bonferroni-adjusted across the 9 BIDs
    bid: str                      # dominant BID label, e.g. "A1A2B1"
    form: str                     # DependenceForm: MONOTONE / PARABOLIC / ...
    direction: str                # "increasing" / "decreasing" / "none"
    pearson_r: float
    spearman_rho: float
    nonlinear_only: bool          # BET-significant but |Pearson| and |Spearman| small
    significant: bool


@dataclass
class ScreenResult:
    """Ranked output of a full pairwise screen."""

    findings: list[PairDependence] = field(default_factory=list)
    n_pairs: int = 0
    n_significant: int = 0
    n_nonlinear_only: int = 0
    alpha: float = DEFAULT_ALPHA
    notes: list[str] = field(default_factory=list)


# ── statistics helpers (pure stdlib) ───────────────────────────────────────────

def _norm_sf(z: float) -> float:
    """Upper-tail of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def _ranks_jittered(values: list[float], rng: random.Random) -> list[float]:
    """Strictly-increasing ranks 1..n, breaking ties by deterministic jitter.

    Tied values are spread within a small fraction of the smallest positive gap so
    the empirical copula stays continuous (paper §3.1) without changing the order
    of the distinct values.
    """
    n = len(values)
    distinct = sorted(set(values))
    if len(distinct) > 1:
        gap = min(b - a for a, b in zip(distinct, distinct[1:]))
        eps = gap * 1e-3
    else:
        eps = 1e-6
    jittered = [v + rng.uniform(0.0, eps) for v in values]
    order = sorted(range(n), key=lambda i: jittered[i])
    ranks = [0.0] * n
    for rank, idx in enumerate(order, start=1):
        ranks[idx] = float(rank)
    return ranks


def empirical_copula(values: list[float], rng: random.Random) -> list[float]:
    """Map values to the empirical copula on (0, 1] via jittered ranks / n."""
    n = len(values)
    ranks = _ranks_jittered(values, rng)
    return [r / n for r in ranks]


def _depth2_signs(u: list[float]) -> tuple[list[int], list[int], list[int]]:
    """Sign-coded depth-2 binary interactions (Ȧ1, Ȧ2, Ȧ1·Ȧ2) for copula values."""
    s1, s2, s12 = [], [], []
    for val in u:
        q = min(3, int(val * 4.0)) if val < 1.0 else 3   # quarter index 0..3
        b1 = q >> 1          # first (high) bit
        b2 = q & 1           # second (low) bit
        a1 = 2 * b1 - 1      # -> {-1, +1}
        a2 = 2 * b2 - 1
        s1.append(a1)
        s2.append(a2)
        s12.append(a1 * a2)
    return s1, s2, s12


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


def _rank_avg(values: list[float]) -> list[float]:
    """Average ranks (ties shared) — for Spearman's rho."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(x: list[float], y: list[float]) -> float:
    return _pearson(_rank_avg(x), _rank_avg(y))


# ── core BET ────────────────────────────────────────────────────────────────

def maxbet(
    x: list[float],
    y: list[float],
    alpha: float = DEFAULT_ALPHA,
    seed: int = 0,
) -> PairDependence:
    """Depth-2 MaxBET for a single pair, with the linear-method comparison."""
    if len(x) != len(y):
        raise ValueError("x and y must have equal length")
    n = len(x)
    rng = random.Random(seed)
    u = empirical_copula(x, rng)
    v = empirical_copula(y, rng)
    xs = dict(zip(_INTERACTIONS, _depth2_signs(u)))
    ys = dict(zip(_INTERACTIONS, _depth2_signs(v)))

    best_s = 0
    best_bid = ("1", "1")
    for a, b in _BIDS:
        sx, sy = xs[a], ys[b]
        s = sum(ax * by for ax, by in zip(sx, sy))
        if abs(s) > abs(best_s):
            best_s = s
            best_bid = (a, b)

    z = abs(best_s) / math.sqrt(n) if n > 0 else 0.0
    p_single = 2.0 * _norm_sf(z)
    p_bonf = min(1.0, p_single * len(_BIDS))   # Bonferroni across the 9 BIDs

    pearson = _pearson(x, y)
    spearman = _spearman(x, y)
    significant = p_bonf < alpha
    nonlinear_only = (
        significant
        and abs(pearson) < LINEAR_NULL_THRESHOLD
        and abs(spearman) < LINEAR_NULL_THRESHOLD
    )
    if best_s > 0:
        direction = "increasing"
    elif best_s < 0:
        direction = "decreasing"
    else:
        direction = "none"

    return PairDependence(
        x="x", y="y", n=n,
        bet_statistic_s=best_s,
        bet_z=z,
        p_value=p_bonf,
        bid=_bid_label(best_bid),
        form=_BID_FORM[best_bid] if significant else "INDEPENDENT",
        direction=direction if significant else "none",
        pearson_r=pearson,
        spearman_rho=spearman,
        nonlinear_only=nonlinear_only,
        significant=significant,
    )


def _bid_label(bid: tuple[str, str]) -> str:
    a, b = bid
    return "A" + "A".join(a) + "B" + "B".join(b)


def relationship_form(form: str) -> str:
    """Map a DependenceForm to the selector's {linear, monotone, nonlinear} signal."""
    if form == "LINEAR":
        return "linear"
    if form == "MONOTONE":
        return "monotone"
    if form in ("PARABOLIC", "SINUSOIDAL", "CHECKERBOARD", "COMPLEX"):
        return "nonlinear"
    return "unknown"


def pairwise_screen(
    columns: dict[str, list[float]],
    alpha: float = DEFAULT_ALPHA,
    max_pairs: int | None = None,
    seed: int = 0,
) -> ScreenResult:
    """Screen every pair of numeric columns; rank by BET strength.

    columns: {name -> values} for the CONTINUOUS/COUNT/ORDINAL columns to scan.
    Family-wise control is Bonferroni across the number of pairs *on top of* the
    per-pair Bonferroni across BIDs (mirroring the paper's two-level adjustment).
    """
    names = list(columns)
    pairs = [(names[i], names[j])
             for i in range(len(names)) for j in range(i + 1, len(names))]
    n_pairs = len(pairs)
    result = ScreenResult(n_pairs=n_pairs, alpha=alpha)
    if max_pairs is not None and n_pairs > max_pairs:
        result.notes.append(
            f"Screen capped at {max_pairs} of {n_pairs} pairs; remaining pairs not tested."
        )
        pairs = pairs[:max_pairs]

    for k, (xa, yb) in enumerate(pairs):
        pd = maxbet(columns[xa], columns[yb], alpha=alpha, seed=seed + k)
        pd.x, pd.y = xa, yb
        # Second-level Bonferroni across the screened pairs.
        pd.p_value = min(1.0, pd.p_value * max(1, len(pairs)))
        pd.significant = pd.p_value < alpha
        if not pd.significant:
            pd.form = "INDEPENDENT"
            pd.direction = "none"
            pd.nonlinear_only = False
        else:
            pd.nonlinear_only = (
                abs(pd.pearson_r) < LINEAR_NULL_THRESHOLD
                and abs(pd.spearman_rho) < LINEAR_NULL_THRESHOLD
            )
        result.findings.append(pd)

    result.findings.sort(key=lambda p: p.bet_z, reverse=True)
    result.n_significant = sum(1 for p in result.findings if p.significant)
    result.n_nonlinear_only = sum(1 for p in result.findings if p.nonlinear_only)
    if result.n_nonlinear_only:
        result.notes.append(
            f"{result.n_nonlinear_only} pair(s) show nonlinear dependence invisible to "
            f"Pearson/Spearman — consider whether latent subgroups drive the pattern."
        )
    return result
