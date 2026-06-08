# Award C Submission — BET Nonlinear Dependence Screen

> **GitHub repository:** https://github.com/zhengwu/Better_Testing_Agent
> **Relevant file:** `src/hta/bet_screen.py`
> **Demo script:** `examples/stai_x_overdose.py`

---

## What it is

A pure-Python, **zero-dependency** implementation of the **Binary Expansion Testing (BET)** framework for detecting and characterizing statistical dependence between pairs of continuous variables — including nonlinear dependence that Pearson correlation and Spearman's ρ completely miss.

The module (`src/hta/bet_screen.py`) is a drop-in EDA skill: give it a dictionary of numeric columns, and it returns a ranked table of every pair, the *form* of each relationship (monotone, sinusoidal, parabolic, checkerboard, complex), and actionable feature-engineering hints.

**References:**
- Zhang, K. (2019). *BET on Independence.* JASA 114(528), 1620–1637.
- Xiang, S., Zhang, W., et al. (2023). *Pairwise Nonlinear Dependence Analysis of Genomic Data.* Annals of Applied Statistics 17(4).

---

## Why it's useful for this competition

Standard EDA screens covariates with Pearson r or Spearman ρ. Both measure *linear/monotone* association. On the STAI-X training data, this misses **9–11 pairs per category** where real structure exists but both coefficients are below 0.10.

The two most actionable examples:

| Finding | Category | Pearson r | Spearman ρ | BET z | Form |
|---|---|---|---|---|---|
| `unemployment_rate` × `rate_all_stimulants` | stimulants | **0.007** | 0.099 | **5.76** | PARABOLIC |
| `temp_avg_f` × `rate_all_stimulants` | stimulants | 0.082 | 0.098 | **4.34** | MONOTONE |
| `labor_force` × `gtrends_fentanyl` | all categories | -0.027 | 0.045 | **4.87** | CHECKERBOARD |

A correlation screen would drop `unemployment_rate` as a predictor for stimulants — BET says it has a real parabolic signal (z = 5.76, p < 0.0001). The checkerboard pattern on `labor_force × gtrends_fentanyl` suggests a latent state-size subgroup that interacts with fentanyl search behavior.

Beyond covariate screening, BET also reveals that `gtrends_fentanyl` and `gtrends_naloxone` have **sinusoidal** (not monotone) relationships with overdose rates — a spline or quadratic encoding captures more signal than a raw linear term.

---

## How to use it

**Requirements:** Python ≥ 3.9, no third-party packages needed (`math`, `random`, `dataclasses` only).

```python
import sys
sys.path.insert(0, "src")   # or pip install -e .

from hta.bet_screen import pairwise_screen

# columns: dict mapping column name -> list[float]
columns = {
    "unemployment_rate": [...],
    "gtrends_overdose":  [...],
    "rate_all_drugs":    [...],
    # ...
}

result = pairwise_screen(columns, alpha=0.05)

print(f"Significant pairs: {result.n_significant} / {result.n_pairs}")
print(f"Nonlinear-only (missed by Pearson/Spearman): {result.n_nonlinear_only}")

for p in result.findings:
    if p.significant:
        print(f"{p.x} × {p.y}: form={p.form}, z={p.bet_z:.2f}, p={p.p_value:.4f}")
        if p.nonlinear_only:
            print(f"  ← NONLINEAR ONLY: Pearson r={p.pearson_r:.3f}, consider {p.form.lower()} encoding")
```

**For a single pair with full regional interpretation:**

```python
from hta.bet_screen import maxbet_twostage

res = maxbet_twostage(x, y, d_max=4)
print(f"p = {res.p_value:.4f}, form = {res.form}, BID = {res.bid}")
print(res.region_description)  # "Excess points concentrate in N of M copula cells..."
```

**Run the full competition demo:**

```bash
git clone https://github.com/zhengwu/Better_Testing_Agent.git
cd Better_Testing_Agent
PYTHONPATH=src python examples/stai_x_overdose.py --data-dir /path/to/stai-x-data
```

---

## What the screen returns

Each `PairDependence` result includes:

| Field | Meaning |
|---|---|
| `bet_z` | Test statistic — larger = stronger dependence |
| `p_value` | Two-sided, Bonferroni-corrected across all BIDs and all pairs |
| `form` | `MONOTONE / LINEAR / SINUSOIDAL / PARABOLIC / CHECKERBOARD / COMPLEX` |
| `direction` | `increasing / decreasing / none` |
| `pearson_r` | For comparison with BET |
| `spearman_rho` | For comparison with BET |
| `nonlinear_only` | `True` when BET-significant but `|r| < 0.10` and `|ρ| < 0.10` |
| `positive_region` | Copula grid cells where excess points concentrate |
| `region_description` | One-line human summary |

The `ScreenResult` also produces a ranked `findings` list and `notes` that flag nonlinear-only pairs with a suggestion to investigate latent subgroups.

---

## How it works (30-second sketch)

1. **Copula transform** — each variable is mapped to its empirical rank / n, making the test marginal-free and robust to outliers.
2. **Binary expansion to depth 2** — each copula value's first 2 bits place it in one of 4 bins; products of the sign-coded bits across both variables define 9 "binary interaction designs" (BIDs) — checkerboard-like regions of the unit square.
3. **Symmetry statistic** — for each BID, S = Σ (±1 per point) counts whether points concentrate in the positive or negative region. Under independence, S ≈ 0 and Z = |S|/√n is standard normal.
4. **Max BET** — take the BID with the largest |S|; Bonferroni-adjust across the 9 BIDs and (for `pairwise_screen`) across all tested pairs.
5. **Form taxonomy** — the winning BID maps to a named dependence form, which directly suggests the right feature transformation.

The module is pure standard library, so it runs anywhere Python runs with no install friction.

---

## Results on STAI-X training data (summary)

| Category | n | Sig. pairs / 45 | NL-only pairs | Headline finding |
|---|---|---|---|---|
| `all_drugs` | 3,696 | 44 | 7 | `gtrends_fentanyl` → SINUSOIDAL vs rate |
| `all_opioids` | 3,696 | 44 | 7 | same pattern as all_drugs |
| `all_stimulants` | 3,696 | 44 | **9** | `unemployment_rate` PARABOLIC vs stimulant rate (r ≈ 0!) |

Full output with ASCII copula grids: run `examples/stai_x_overdose.py`.
