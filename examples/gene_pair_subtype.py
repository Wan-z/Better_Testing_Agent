"""Example 2 — A nonlinear gene pair created by a cancer-subtype mixture.

A reproduction *in spirit* of §8 of

    Zhang, K. (2019). "BET on Independence." JASA 114(528), 1620–1637.

Zhang screens ~5×10⁷ gene pairs in TCGA breast-cancer expression data with Max BET
(depth 2) as an EDA tool, looking for *nonlinear* dependence. The headline pair is
DZIP1 × NAV3: BET rejects independence (z = 6.52) where the nonlinearity turns out
to be a **mixture of subtypes** — basal-like patients form a disjoint cluster with
high DZIP1 and low NAV3. Adding the subtype label explains the nonlinearity, and
(the §8.3 punchline) the two genes *jointly* classify basal-like at ~91% accuracy
versus ~79% / ~76% for either gene alone.

This mirrors the agent's own design: the BET screen flags a subtype-suggestive
nonlinear pair (`SUBTYPE_SUGGESTIVE_FORMS`), the dialogue asks the Rule-8 subgroup
question, and the selector runs a *contextual* (within-subgroup) analysis.

The z-statistic and accuracies quoted above are the paper's real-data figures.

⚠️ SYNTHETIC DATA. These are *simulated* expression values with the same qualitative
structure as the paper's finding — not the TCGA cohort, for demonstration only. The printed
numbers below are close in spirit but not identical to the paper's (e.g. joint ≈90% vs
≈75% / ≈67% for the single genes).

Run me:  PYTHONPATH=src python examples/gene_pair_subtype.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from hta.bet_screen import maxbet

N_OTHER = 205
N_BASAL = 68                       # ~25% basal-like, the aggressive subtype
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "gene_pair_subtype.csv"


def generate(seed: int = 2019) -> list[tuple[float, float, str]]:
    """Deterministic synthetic (DZIP1, NAV3, subtype) rows.

    'other' subtypes carry a mild positive DZIP1→NAV3 trend; 'basal' patients form a
    tight, disjoint high-DZIP1 / low-NAV3 cluster. Pooling the two creates the
    nonlinear pattern BET detects and the subtype label explains.
    """
    import random

    rng = random.Random(seed)
    rows: list[tuple[float, float, str]] = []
    for _ in range(N_OTHER):
        dzip1 = rng.gauss(0.0, 1.0)
        nav3 = 0.7 * dzip1 + rng.gauss(0.0, 0.7)        # within-group positive trend
        rows.append((dzip1, nav3, "other"))
    for _ in range(N_BASAL):
        # Each gene only *partly* separates basal (the means overlap the 'other'
        # tails), but the JOINT location — high DZIP1 *and* low NAV3 at once — is rare
        # in 'other' because of its positive trend. So the pair beats either margin.
        dzip1 = rng.gauss(1.4, 0.70)                    # higher DZIP1 (overlaps tail)
        nav3 = rng.gauss(-1.1, 0.70)                    # lower NAV3 (overlaps tail)
        rows.append((dzip1, nav3, "basal"))
    rng.shuffle(rows)
    return rows


def write_csv(rows: list[tuple[float, float, str]], path: Path = DATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sample_id", "DZIP1", "NAV3", "subtype"])
        for i, (dzip1, nav3, subtype) in enumerate(rows, start=1):
            w.writerow([i, f"{dzip1:.4f}", f"{nav3:.4f}", subtype])


def _standardize(values: list[float]) -> list[float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]


def knn_loo_accuracy(features: list[list[float]], labels: list[str], k: int = 1) -> float:
    """Leave-one-out k-NN accuracy on standardized features (pure stdlib).

    `features` is one row per sample; columns are standardized independently so a
    one-column (single-gene) classifier is compared fairly against the joint one.
    """
    cols = list(zip(*features))
    std_cols = [_standardize(list(c)) for c in cols]
    pts = list(zip(*std_cols))                          # standardized rows
    n = len(pts)
    correct = 0
    for i in range(n):
        dists = sorted(
            (sum((pts[i][d] - pts[j][d]) ** 2 for d in range(len(pts[i]))), j)
            for j in range(n) if j != i
        )
        votes: dict[str, int] = {}
        for _, j in dists[:k]:
            votes[labels[j]] = votes.get(labels[j], 0) + 1
        if max(votes, key=votes.get) == labels[i]:
            correct += 1
    return correct / n


def analyze(rows: list[tuple[float, float, str]]) -> None:
    dzip1 = [r[0] for r in rows]
    nav3 = [r[1] for r in rows]
    subtype = [r[2] for r in rows]

    res = maxbet(dzip1, nav3, seed=11)
    print(f"N = {len(rows)} samples (synthetic)   basal-like: {subtype.count('basal')}")
    print("\n1) BET EDA screen on DZIP1 × NAV3 (depth 2, §8):")
    print(f"   Pearson r = {res.pearson_r:+.3f}   Spearman = {res.spearman_rho:+.3f}")
    verdict = "REJECT independence" if res.significant else "fail to reject"
    print(f"   Max BET: {verdict}  p = {res.p_value:.4g}  z = {res.bet_z:.2f}")
    print(f"   Dominant interaction {res.bid} → form = {res.form}"
          + ("  (nonlinear, invisible to a single correlation)"
             if res.nonlinear_only else ""))

    print("\n2) Contextual (within-subgroup) view — the subtype explains the shape:")
    for grp in ("other", "basal"):
        gx = [d for d, s in zip(dzip1, subtype) if s == grp]
        gy = [v for v, s in zip(nav3, subtype) if s == grp]
        gr = maxbet(gx, gy, seed=11)
        print(f"   {grp:>6}: n={len(gx):3d}  "
              f"mean DZIP1={sum(gx)/len(gx):+.2f}  mean NAV3={sum(gy)/len(gy):+.2f}  "
              f"within-group Pearson={gr.pearson_r:+.2f}")

    print("\n3) Classification of basal-like (1-NN, leave-one-out, §8.3):")
    acc_dzip1 = knn_loo_accuracy([[d] for d in dzip1], subtype)
    acc_nav3 = knn_loo_accuracy([[v] for v in nav3], subtype)
    acc_joint = knn_loo_accuracy([[d, v] for d, v in zip(dzip1, nav3)], subtype)
    print(f"   DZIP1 alone : {acc_dzip1:.1%}")
    print(f"   NAV3  alone : {acc_nav3:.1%}")
    print(f"   joint pair  : {acc_joint:.1%}   ← the BET-discovered pair classifies "
          "better together than either gene alone")


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
