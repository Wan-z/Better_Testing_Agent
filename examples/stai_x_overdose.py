"""Example 3 — BET dependence screen on the STAI-X 2026 overdose dataset.

Demonstrates the BET pairwise screen as an EDA step before modelling:

  * Which covariates are associated with each overdose category?
  * Which relationships are nonlinear — invisible to Pearson / Spearman?
  * What dependence *form* suggests useful feature engineering?

Competition: https://www.kaggle.com/competitions/stai-x-challenge-2026

Data layout expected (default: data/ relative to this file's grandparent):

    train/
      covariates.csv          — panel covariates keyed on (period_id, jurisdiction)
      dose_sys_train.csv      — overdose ED rates (training target)

Override via environment variable STAI_DATA_DIR or by passing --data-dir on the
command line.

Run:
    PYTHONPATH=src python examples/stai_x_overdose.py
    PYTHONPATH=src python examples/stai_x_overdose.py --data-dir /path/to/data
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NUMERIC_COVS = [
    "unemployment_rate",
    "labor_force",
    "temp_avg_f",
    "precip_in",
    "gtrends_overdose",
    "gtrends_fentanyl",
    "gtrends_naloxone",
    "gtrends_opioid",
    "gtrends_methamphetamine",
]

CATEGORIES = ["all_drugs", "all_opioids", "all_stimulants"]

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "stai_x_2026"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_covariates(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    covs: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            covs[(row["period_id"], row["jurisdiction"])] = row
    return covs


def load_targets(path: Path, category: str) -> dict[tuple[str, str], float]:
    targets: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["overdose_category"] != category:
                continue
            val = row.get("rate_per_10000_ed_visits", "")
            if val and val.lower() not in ("nan", ""):
                targets[(row["period_id"], row["jurisdiction"])] = float(val)
    return targets


def build_columns(
    covs: dict[tuple[str, str], dict[str, str]],
    targets: dict[tuple[str, str], float],
    category: str,
) -> dict[str, list[float]]:
    rate_col = f"rate_{category}"
    columns: dict[str, list[float]] = {c: [] for c in NUMERIC_COVS}
    columns[rate_col] = []
    skipped = 0
    for key, rate in targets.items():
        if key not in covs:
            skipped += 1
            continue
        row = covs[key]
        try:
            parsed = {c: float(row[c]) for c in NUMERIC_COVS}
        except (ValueError, KeyError):
            skipped += 1
            continue
        for c in NUMERIC_COVS:
            columns[c].append(parsed[c])
        columns[rate_col].append(rate)
    return columns


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_region(positive_region: list[tuple[int, int]], grid_size: int) -> str:
    """ASCII picture of the dominant BID's positive region (V up, U right)."""
    cells = set(positive_region)
    lines = []
    for row in range(grid_size - 1, -1, -1):
        lines.append("".join("█" if (row, col) in cells else "·"
                             for col in range(grid_size)))
    return "\n".join(lines)


def _sig_star(p: float) -> str:
    if p < 0.001: return "***"
    if p < 0.01:  return "** "
    if p < 0.05:  return "*  "
    return "   "


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_category(
    covs: dict[tuple[str, str], dict[str, str]],
    targets: dict[tuple[str, str], float],
    category: str,
) -> None:
    from hta.bet_screen import pairwise_screen

    rate_col = f"rate_{category}"
    columns = build_columns(covs, targets, category)
    n = len(columns[rate_col])
    if n == 0:
        print(f"  No complete rows for {category}.")
        return

    result = pairwise_screen(columns, alpha=0.05)

    print(f"\n{'='*65}")
    print(f"  {category.upper()}   n={n}   pairs={result.n_pairs}   "
          f"significant={result.n_significant}   nonlinear-only={result.n_nonlinear_only}")
    print(f"{'='*65}")

    # --- Covariates vs rate ------------------------------------------------
    print(f"\n  {'Covariate':<28} {'BET z':>6}  {'p':>8}  {'Pearson r':>9}  "
          f"{'Spearman':>8}  Form")
    print(f"  {'-'*28} {'-'*6}  {'-'*8}  {'-'*9}  {'-'*8}  {'-'*12}")
    rate_pairs = sorted(
        [p for p in result.findings if rate_col in (p.x, p.y)],
        key=lambda p: p.bet_z, reverse=True,
    )
    for p in rate_pairs:
        other = p.y if p.x == rate_col else p.x
        stars = _sig_star(p.p_value) if p.significant else "   "
        nl = " ◄ NL-only" if p.nonlinear_only else ""
        print(f"  {stars}{other:<28} {p.bet_z:6.2f}  {p.p_value:8.4f}  "
              f"{p.pearson_r:+9.3f}  {p.spearman_rho:+8.3f}  {p.form}{nl}")

    # --- Nonlinear-only pairs: where BET finds signal Pearson/Spearman miss -
    nl_pairs = [p for p in result.findings if p.nonlinear_only]
    if nl_pairs:
        print(f"\n  --- {len(nl_pairs)} nonlinear-only pair(s): "
              "real structure invisible to Pearson/Spearman ---")
        for p in nl_pairs:
            print(f"\n  {p.x}  ×  {p.y}")
            print(f"    form={p.form}  direction={p.direction}  "
                  f"z={p.bet_z:.2f}  p={p.p_value:.4f}")
            print(f"    Pearson r={p.pearson_r:.3f}   Spearman ρ={p.spearman_rho:.3f}  "
                  f"(both < 0.10 — linear screens would drop this)")
            print(f"    BID={p.bid}   {p.region_description}")
            if p.positive_region:
                grid = render_region(p.positive_region, p.grid_size)
                for line in grid.splitlines():
                    print(f"      {line}  ← copula grid (U→ V↑, █ = excess points)")

    # --- Modelling takeaways -----------------------------------------------
    print(f"\n  --- Feature engineering hints ---")
    for p in rate_pairs:
        if not p.significant:
            continue
        other = p.y if p.x == rate_col else p.x
        if p.nonlinear_only:
            hint = f"add quadratic/binned {other} term (linear coeff ≈ 0, real signal is {p.form.lower()})"
        elif p.form == "SINUSOIDAL":
            hint = f"consider {other}² or spline — {p.form.lower()} shape (Pearson r={p.pearson_r:+.2f} underestimates signal)"
        elif p.form == "PARABOLIC":
            hint = f"add {other}² term — parabolic relationship detected"
        elif p.form == "CHECKERBOARD":
            hint = f"interaction term with {other} — checkerboard pattern suggests latent subgroups"
        else:
            hint = f"linear/monotone — standard encoding adequate"
        print(f"  • {other:<30} {hint}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BET EDA screen on STAI-X 2026 data")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Path to the folder containing train/ (default: data/stai_x_2026/)")
    args = parser.parse_args(argv)

    import os
    data_dir = args.data_dir or Path(os.environ.get("STAI_DATA_DIR", DEFAULT_DATA_DIR))
    cov_path = data_dir / "train" / "covariates.csv"
    target_path = data_dir / "train" / "dose_sys_train.csv"

    for p in (cov_path, target_path):
        if not p.exists():
            sys.exit(f"File not found: {p}\n"
                     f"Pass --data-dir or set STAI_DATA_DIR to the folder containing train/.")

    print("BET Pairwise Dependence Screen — STAI-X Challenge 2026")
    print(f"Data: {data_dir}")
    print("\nReference: Zhang (2019) 'BET on Independence', JASA 114(528).")
    print("           Xiang et al. (2023) 'Pairwise Nonlinear Dependence Analysis', AoAS 17(4).")

    covs = load_covariates(cov_path)
    for category in CATEGORIES:
        targets = load_targets(target_path, category)
        analyze_category(covs, targets, category)

    print("\n\nKey: *** p<0.001  ** p<0.01  * p<0.05  (Bonferroni across pairs and BIDs)")
    print("     NL-only = BET-significant but |Pearson| < 0.10 and |Spearman| < 0.10")
    print("     Forms: MONOTONE  SINUSOIDAL  PARABOLIC  CHECKERBOARD  COMPLEX")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
