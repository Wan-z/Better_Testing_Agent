"""Example 1 — Are the bright stars uniformly scattered across the sky?

A reproduction *in spirit* of §7 of

    Zhang, K. (2019). "BET on Independence." JASA 114(528), 1620–1637.

The paper takes the galactic coordinates of the 256 brightest stars and tests
whether longitude and latitude are independent (which they would be if stars were
uniformly scattered on the celestial sphere). Because the uniform density on the
sphere is proportional to cos(latitude), the right copula coordinates are

    X = longitude          Y = sin(latitude).

On the paper's real data, classical tests are weak or uninterpretable (Pearson r = −0.07,
p = 0.26; distance correlation p = 0.10; Hoeffding's D p = 0.06; KNN-MI p = 0.02 but with
no picture of *what* the dependence is), while the two-stage empirical Max BET rejects
independence (p ≈ 0.02) **and** its strongest cross interaction draws the Milky-Way band —
BET both detects and explains.

⚠️ SYNTHETIC DATA. We do not ship the HIPPARCOS catalogue. The 256 points below are
*simulated*: a majority lie along a wavy "galactic plane" band and the rest are a uniform
background — for demonstration only, not astrometry. The synthetic band is deliberately
cleaner than the real sky, so the printed BET p-value is far smaller than the paper's 0.02
(the Pearson r ≈ −0.07 and the dominant A1A2B1 interaction still match the paper).

Run me:  PYTHONPATH=src python examples/stars_independence.py
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from hta.bet_screen import maxbet_twostage

N_STARS = 256
N_BAND = 168                       # ~2/3 of bright stars trace the galactic plane
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "bright_stars.csv"


def generate(seed: int = 2019) -> list[tuple[float, float]]:
    """Deterministic synthetic (longitude_deg, sin_latitude) for 256 'stars'.

    Pure standard library + fixed seed, so the committed CSV is reproducible.
    """
    import random

    rng = random.Random(seed)
    rows: list[tuple[float, float]] = []
    for i in range(N_STARS):
        lon = rng.uniform(0.0, 360.0)
        if i < N_BAND:
            # The galactic plane appears as a cosine band in (longitude, sin b)
            # space. Averaged over a full turn of longitude a cosine has ~zero
            # correlation with it, yet the dependence is strong — exactly the trap
            # that defeats Pearson/Hoeffding but not BET.
            center = 0.45 * math.cos(math.radians(lon))
            sin_lat = center + rng.gauss(0.0, 0.06)
            sin_lat = max(-1.0, min(1.0, sin_lat))
        else:
            sin_lat = rng.uniform(-1.0, 1.0)   # uniform background
        rows.append((lon, sin_lat))
    return rows


def write_csv(rows: list[tuple[float, float]], path: Path = DATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["star_id", "longitude_deg", "sin_latitude"])
        for i, (lon, sin_lat) in enumerate(rows, start=1):
            w.writerow([i, f"{lon:.4f}", f"{sin_lat:.4f}"])


def render_region(positive_region: list[tuple[int, int]], grid_size: int) -> str:
    """ASCII picture of the dominant cross interaction's region (V up, U right)."""
    cells = set(positive_region)
    lines = []
    for row in range(grid_size - 1, -1, -1):          # row 0 = bottom
        lines.append("".join("█" if (row, col) in cells else "·"
                             for col in range(grid_size)))
    return "\n".join(lines)


def analyze(rows: list[tuple[float, float]]) -> None:
    lon = [r[0] for r in rows]
    sin_lat = [r[1] for r in rows]
    res = maxbet_twostage(lon, sin_lat, seed=7)

    print(f"N = {len(rows)} bright stars (synthetic)")
    print(f"  Pearson r(longitude, sin lat) = {res.pearson_r:+.3f}   "
          f"Spearman = {res.spearman_rho:+.3f}   "
          "→ linear tests see almost nothing")
    verdict = "REJECT independence" if res.significant else "fail to reject"
    print(f"  Two-stage Max BET (d ≤ 4): {verdict}  "
          f"p = {res.p_value:.4g}  z = {res.bet_z:.2f}")
    print(f"  Strongest cross interaction: {res.bid} at depth {res.depth}  "
          f"({res.form}, {res.direction})")
    print(f"  {res.region_description}")
    print("  Where the dependence lives (the 'Milky-Way band'):")
    print("\n".join("    " + ln
                    for ln in render_region(res.positive_region, res.grid_size).splitlines()))
    print("\n  BET both DETECTS the dependence and SHOWS it — the band is the "
          "interpretation the classical p-values cannot give.")


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    except (AttributeError, ValueError):
        pass
    data = generate()
    write_csv(data)
    print(f"Wrote {DATA_PATH.relative_to(DATA_PATH.parents[2])}\n")
    analyze(data)
