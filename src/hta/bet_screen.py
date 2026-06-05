"""Binary Expansion Testing (BET) for dependence detection and EDA.

The BET framework — binary expansion statistics (BEStat), the binary interaction
design (BID) / Hadamard reparameterization, the symmetry statistics, and the
**Max BET** procedure — is due to

    Zhang, K. (2019). "BET on Independence." Journal of the American Statistical
    Association, 114(528), 1620–1637. DOI: 10.1080/01621459.2018.1537921.

We build on the two real-data analyses in that paper:

  * **§7 (stars):** a *focused, interpretable test of independence*. Two-stage
    empirical Max BET (search depths d = 1..d_max, second-level Bonferroni over
    depths) detects dependence that Pearson (r = −0.07), distance correlation, and
    Hoeffding's D all miss, and — crucially — its strongest cross interaction shows
    *where* the dependence lives (the Milky-Way band). See `maxbet_twostage` and
    `cross_region`.
  * **§8 (TCGA):** a fast *EDA screen* over many pairs at depth d = 2 to surface
    pairs whose nonlinear dependence is created by a **mixture of latent subgroups**
    (cancer subtypes). The discovered nonlinear pair then both explains the
    nonlinearity (via the subgroup label) and improves joint classification. See
    `pairwise_screen` and `SUBTYPE_SUGGESTIVE_FORMS`.

The depth-2 form taxonomy and the genomic-screen framing follow the downstream
application paper:

    Xiang, S., Zhang, W., Liu, S., Hoadley, K. A., Perou, C. M., Zhang, K., & Marron, J. S.
    (2023). "Pairwise Nonlinear Dependence Analysis of Genomic Data."
    The Annals of Applied Statistics, 17(4). DOI: 10.1214/23-AOAS1745.

Method:

1. **Copula transform** — map each variable to the empirical copula on (0, 1] via
   ranks. This is marginal-free and robust to outliers.
2. **Tie handling** — piled-up values (zeros, imputed values, detection limits)
   violate BET's continuity assumption, so tied observations are *jittered* by a
   small deterministic amount before ranking (Xiang et al. 2023 §3.1).
3. **Binary expansion to depth d** — each copula value's first d bits place it in one
   of 2^d bins; the sign-coded products of those bits over both variables give the
   (2^d − 1)(2^d − 1) "cross interactions" (the BIDs of Figure 2). Depth 2 (nine BIDs)
   is the screen default; the two-stage test searches d = 1..d_max.
4. **Symmetry statistics** — for each cross interaction, S = Σ Ȧ·Ḃ counts points in the
   white (+) minus the blue (−) region (Zhang 2019 §3.3). Under independence S ≈ 0.
   With *unknown* margins (the empirical copula), (Ŝ + n)/4 is Hypergeometric(n, n/2,
   n/2) (Thm 4.2), so Var(Ŝ) = n²/(n−1) ≈ n; we use the large-n normal approximation
   (Kou & Ying 1996), Z = |S|/√n, which is exact to the finite-population correction.
5. **Max BET** — take the cross interaction with the largest |S|; its sign gives the
   direction, its region gives the interpretation, and (depth-2) its label gives the
   *form*. Bonferroni-adjust across the cross interactions, and again across depths in
   the two-stage procedure.

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
# Default maximum depth for the two-stage Max BET search (Zhang 2019 §4.5 recommends
# d_max = 4 as a good approximation to the true distribution).
DEFAULT_D_MAX = 4

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
# Forms whose typical cause is a mixture of latent subpopulations — the subtype-driven
# patterns of Zhang (2019) §8. Used to prompt the subgroup question in the dialogue.
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
    # ── interpretation: where the dependence lives (Zhang 2019 §7/§8) ──────────
    depth: int = 2                # binary-expansion depth of the dominant interaction
    grid_size: int = 4            # 2**depth — the copula grid is grid_size × grid_size
    # Cells (row, col) of the copula grid in the dominant interaction's *positive*
    # region, row 0 = bottom (V≈0), col 0 = left (U≈0). Points concentrate here when
    # the symmetry statistic is positive (and in the complementary cells when it is
    # negative). This is the shaded region the agent plots / describes.
    positive_region: list[tuple[int, int]] = field(default_factory=list)
    region_description: str = ""  # short human summary of the dependence region


@dataclass
class ScreenResult:
    """Ranked output of a full pairwise screen."""

    findings: list[PairDependence] = field(default_factory=list)
    n_pairs: int = 0
    n_significant: int = 0
    n_nonlinear_only: int = 0
    alpha: float = DEFAULT_ALPHA
    notes: list[str] = field(default_factory=list)


@dataclass
class InteractionPlot:
    """Everything needed to draw the Xiang-et-al. binary-interaction EDA scatter.

    The plot lives in the empirical-copula unit square (marginal-free rank coordinates,
    Xiang et al. 2023). Each observation is coloured by the sign of the *dominant binary
    interaction* — the BID that Max BET selects as carrying the dependence — so the two
    colours are literally the two halves of that binary interaction. Clusters of one
    colour in particular grid cells are the visual signature of a mixture of latent
    subgroups (the §8 / Xiang heterogeneity story), which is why this is offered as an
    exploratory view "when receiving the data."
    """

    x_name: str
    y_name: str
    n: int
    u: list[float]                    # empirical copula of x, in (0, 1]
    v: list[float]                    # empirical copula of y, in (0, 1]
    point_sign: list[int]             # ±1 per point: sign of the dominant interaction
    region_grid: list[list[int]]      # region_grid[row][col] ∈ {-1, +1}; row 0 = bottom
    grid_size: int                    # 2**depth (the copula grid is grid_size × grid_size)
    depth: int
    bid: str                          # dominant BID label, e.g. "A1A2B1"
    form: str                         # DependenceForm of the dominant interaction
    direction: str                    # "increasing" / "decreasing" / "none"
    bet_statistic_s: int              # symmetry statistic S of the dominant BID (= Σ point_sign)
    bet_z: float
    p_value: float                    # two-sided, Bonferroni-adjusted across the 9 BIDs
    pearson_r: float
    spearman_rho: float
    significant: bool
    nonlinear_only: bool


# ── statistics helpers (pure stdlib) ───────────────────────────────────────────

def _norm_sf(z: float) -> float:
    """Upper-tail of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def _ranks_jittered(values: list[float], rng: random.Random) -> list[float]:
    """Strictly-increasing ranks 1..n, breaking ties by deterministic jitter.

    Tied values are spread within a small fraction of the smallest positive gap so
    the empirical copula stays continuous (Xiang et al. 2023 §3.1) without changing the
    order of the distinct values.
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


# ── general depth-d interactions and dependency regions ───────────────────────

def _bin_index(val: float, d: int) -> int:
    """Index 0..2^d−1 of the bin a copula value falls in at depth d (bit 1 = high)."""
    g = 1 << d
    return min(g - 1, int(val * g)) if val < 1.0 else g - 1


def _nonempty_subsets(d: int) -> list[tuple[int, ...]]:
    """All nonempty subsets of bits {1..d}, as sorted tuples (the BID generators)."""
    return [
        tuple(k for k in range(1, d + 1) if mask & (1 << (k - 1)))
        for mask in range(1, 1 << d)
    ]


def _subset_sign(index: int, subset: tuple[int, ...], d: int) -> int:
    """Sign (±1) of the binary-interaction variable `subset` for bin `index`."""
    s = 1
    for k in subset:
        bit = (index >> (d - k)) & 1   # bit 1 is the high bit
        s *= 2 * bit - 1
    return s


def _interaction_signs(u_vals: list[float], d: int) -> dict[tuple[int, ...], list[int]]:
    """Per-observation ±1 signs for every nonempty bit-subset interaction at depth d."""
    bins = [_bin_index(v, d) for v in u_vals]
    return {
        sub: [_subset_sign(b, sub, d) for b in bins]
        for sub in _nonempty_subsets(d)
    }


def cross_region(
    sa: tuple[int, ...], sb: tuple[int, ...], d: int
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Positive / negative cells of the cross interaction Ȧ_sa·Ḃ_sb on the 2^d grid.

    Returns ``(positive_cells, negative_cells)`` where each cell is ``(row, col)`` with
    row 0 = bottom (V≈0) and col 0 = left (U≈0). The two regions partition the grid
    into equal halves (the BID's defining property, Zhang 2019 §3.3 / Fig. 2).
    """
    g = 1 << d
    pos: list[tuple[int, int]] = []
    neg: list[tuple[int, int]] = []
    for row in range(g):          # V (Y) bin index
        for col in range(g):      # U (X) bin index
            sign = _subset_sign(col, sa, d) * _subset_sign(row, sb, d)
            (pos if sign > 0 else neg).append((row, col))
    return pos, neg


def _token_to_subset(token: str) -> tuple[int, ...]:
    """Depth-2 BID token ('1' / '2' / '12') -> bit subset tuple."""
    return tuple(int(ch) for ch in token)


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

    form = _BID_FORM[best_bid] if significant else "INDEPENDENT"
    sa, sb = _token_to_subset(best_bid[0]), _token_to_subset(best_bid[1])
    pos, neg = cross_region(sa, sb, 2)
    # When S > 0 points pile up in the positive region; when S < 0, in its complement.
    region = pos if best_s >= 0 else neg
    return PairDependence(
        x="x", y="y", n=n,
        bet_statistic_s=best_s,
        bet_z=z,
        p_value=p_bonf,
        bid=_bid_label(best_bid),
        form=form,
        direction=direction if significant else "none",
        pearson_r=pearson,
        spearman_rho=spearman,
        nonlinear_only=nonlinear_only,
        significant=significant,
        depth=2,
        grid_size=4,
        positive_region=region if significant else [],
        region_description=_region_description(form, region, 2) if significant else "",
    )


def _region_description(form: str, region: list[tuple[int, int]], d: int) -> str:
    """One-line summary of where points concentrate, for reports / plot captions."""
    g = 1 << d
    return (
        f"Excess points concentrate in {len(region)} of {g * g} copula cells "
        f"(the {form.lower()} region) at depth {d}."
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


def _subsets_label(sa: tuple[int, ...], sb: tuple[int, ...]) -> str:
    a = "".join(str(k) for k in sa)
    b = "".join(str(k) for k in sb)
    return _bid_label((a, b))


def _classify_form(sa: tuple[int, ...], sb: tuple[int, ...], d: int) -> str:
    """Coarse DependenceForm for a winning cross interaction at any depth."""
    if d == 2:
        ta = "".join(str(k) for k in sa)
        tb = "".join(str(k) for k in sb)
        named = _BID_FORM.get((ta, tb))
        if named:
            return named
    full = tuple(range(1, d + 1))
    if sa == (1,) and sb == (1,):
        return "MONOTONE"
    if sa == full and sb == full:
        return "LINEAR"
    return "COMPLEX"


def maxbet_twostage(
    x: list[float],
    y: list[float],
    alpha: float = DEFAULT_ALPHA,
    d_max: int = DEFAULT_D_MAX,
    seed: int = 0,
) -> PairDependence:
    """Two-stage empirical Max BET over depths d = 1..d_max (Zhang 2019 §4.5, §7).

    A focused, confirmatory test of independence for a single pair. Stage 1 runs
    Max BET at each depth (Bonferroni across that depth's cross interactions);
    stage 2 Bonferroni-adjusts across the d_max depths. The winning interaction's
    `positive_region` shows *where* the dependence is — BET's signature advantage
    over a single p-value (the Milky-Way band in §7). Unlike the fixed depth-2
    `maxbet` screen, this adapts the resolution to the data.
    """
    if len(x) != len(y):
        raise ValueError("x and y must have equal length")
    n = len(x)
    rng = random.Random(seed)
    u = empirical_copula(x, rng)
    v = empirical_copula(y, rng)

    best: tuple[float, int, tuple[int, ...], tuple[int, ...], int, float] | None = None
    for d in range(1, d_max + 1):
        xs = _interaction_signs(u, d)
        ys = _interaction_signs(v, d)
        subsets = _nonempty_subsets(d)
        n_cross = len(subsets) ** 2
        best_s = 0
        best_sa = best_sb = subsets[0]
        for sa in subsets:
            sxa = xs[sa]
            for sb in subsets:
                s = sum(ax * by for ax, by in zip(sxa, ys[sb]))
                if abs(s) > abs(best_s):
                    best_s, best_sa, best_sb = s, sa, sb
        z = abs(best_s) / math.sqrt(n) if n > 0 else 0.0
        p_within = min(1.0, 2.0 * _norm_sf(z) * n_cross)   # Bonferroni across cross interactions
        if best is None or p_within < best[0]:
            best = (p_within, d, best_sa, best_sb, best_s, z)

    assert best is not None                                # d_max ≥ 1, so the loop ran
    p_within, d, sa, sb, best_s, z = best
    p_overall = min(1.0, p_within * d_max)                 # stage-2 Bonferroni across depths
    significant = p_overall < alpha

    pearson = _pearson(x, y)
    spearman = _spearman(x, y)
    nonlinear_only = (
        significant
        and abs(pearson) < LINEAR_NULL_THRESHOLD
        and abs(spearman) < LINEAR_NULL_THRESHOLD
    )
    form = _classify_form(sa, sb, d) if significant else "INDEPENDENT"
    pos, neg = cross_region(sa, sb, d)
    region = pos if best_s >= 0 else neg
    direction = "increasing" if best_s > 0 else "decreasing" if best_s < 0 else "none"

    return PairDependence(
        x="x", y="y", n=n,
        bet_statistic_s=best_s,
        bet_z=z,
        p_value=p_overall,
        bid=_subsets_label(sa, sb),
        form=form,
        direction=direction if significant else "none",
        pearson_r=pearson,
        spearman_rho=spearman,
        nonlinear_only=nonlinear_only,
        significant=significant,
        depth=d,
        grid_size=1 << d,
        positive_region=region if significant else [],
        region_description=_region_description(form, region, d) if significant else "",
    )


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


def interaction_plot(
    x: list[float],
    y: list[float],
    *,
    x_name: str = "x",
    y_name: str = "y",
    alpha: float = DEFAULT_ALPHA,
    seed: int = 0,
) -> InteractionPlot:
    """Build the depth-2 BET binary-interaction plot data for one pair (EDA).

    Runs the same depth-2 Max BET search as :func:`maxbet`, but additionally returns the
    per-point and per-cell signs of the *dominant* binary interaction so the caller can
    render the Xiang-et-al. copula scatter: points coloured by which side of that
    interaction they fall on, over the shaded 2×2-bit (4×4) interaction grid. The
    colouring exposes latent subgroups — the heterogeneity that creates the nonlinearity.

    The returned ``bid``/``form``/``bet_z``/``significant`` match :func:`maxbet` for the
    same ``seed`` (same copula, same argmax), and ``sum(point_sign) == bet_statistic_s``.
    """
    if len(x) != len(y):
        raise ValueError("x and y must have equal length")
    n = len(x)
    rng = random.Random(seed)
    u = empirical_copula(x, rng)
    v = empirical_copula(y, rng)

    # Depth-2 Max BET — identical search to `maxbet`, but we keep the winning
    # (X-interaction, Y-interaction) tokens so we can colour points by the interaction.
    xs = dict(zip(_INTERACTIONS, _depth2_signs(u)))
    ys = dict(zip(_INTERACTIONS, _depth2_signs(v)))
    best_s = 0
    best_bid = ("1", "1")
    for a, b in _BIDS:
        s = sum(ax * by for ax, by in zip(xs[a], ys[b]))
        if abs(s) > abs(best_s):
            best_s, best_bid = s, (a, b)

    z = abs(best_s) / math.sqrt(n) if n > 0 else 0.0
    p_bonf = min(1.0, 2.0 * _norm_sf(z) * len(_BIDS))
    pearson = _pearson(x, y)
    spearman = _spearman(x, y)
    significant = p_bonf < alpha
    nonlinear_only = (
        significant
        and abs(pearson) < LINEAR_NULL_THRESHOLD
        and abs(spearman) < LINEAR_NULL_THRESHOLD
    )
    form = _BID_FORM[best_bid] if significant else "INDEPENDENT"
    direction = "increasing" if best_s > 0 else "decreasing" if best_s < 0 else "none"

    sa, sb = _token_to_subset(best_bid[0]), _token_to_subset(best_bid[1])
    # Per-point sign of the dominant interaction (the two-colour key); this is exactly
    # xs[a]·ys[b] for the winning BID, so its sum is the symmetry statistic S.
    point_sign = [
        _subset_sign(_bin_index(ui, 2), sa, 2) * _subset_sign(_bin_index(vi, 2), sb, 2)
        for ui, vi in zip(u, v)
    ]
    # Per-cell sign on the 4×4 grid (row 0 = bottom, col 0 = left), via `cross_region`.
    pos, neg = cross_region(sa, sb, 2)
    grid_size = 4
    region_grid = [[0] * grid_size for _ in range(grid_size)]
    for r, c in pos:
        region_grid[r][c] = 1
    for r, c in neg:
        region_grid[r][c] = -1

    return InteractionPlot(
        x_name=x_name, y_name=y_name, n=n,
        u=u, v=v, point_sign=point_sign, region_grid=region_grid,
        grid_size=grid_size, depth=2, bid=_bid_label(best_bid),
        form=form, direction=direction if significant else "none",
        bet_statistic_s=best_s, bet_z=z, p_value=p_bonf,
        pearson_r=pearson, spearman_rho=spearman,
        significant=significant, nonlinear_only=nonlinear_only,
    )
