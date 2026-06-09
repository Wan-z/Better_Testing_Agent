# HTA Benchmark Cases

**Status:** Step-8 statistician-review deliverable
**Reproduce:** `PYTHONPATH=src python examples/benchmark_cases.py`

A deterministic battery of 20 synthetic scenarios run end-to-end through
`HypothesisTestingAgent`. Each row records the **test the selector chose** and the **key
result** the executor produced — the reference values for regression checking and for
statistician audit. All data is synthetic and seeded, so the table is reproducible; the
generating script is [`examples/benchmark_cases.py`](examples/benchmark_cases.py).

## Results

| # | Scenario | Selected test | Statistic | p | Effect size |
|---|---|---|---|---|---|
| 1 | Two groups, continuous, separated (RCT) | `WELCH_T` | −24.700 | <0.001 | Cohen's d = −9.336 (large) |
| 2 | Two groups, small N, strong skew | `MANN_WHITNEY_U` | 11.000 | <0.001 | rank-biserial r = 0.847 (large) |
| 3 | Before/after, within-subjects | `PAIRED_T` | 12.693 | <0.001 | Cohen's d_z = 2.317 (large) |
| 4 | Ordinal outcome, two groups | `MANN_WHITNEY_U` | 128.000 | 0.049 | rank-biserial r = 0.360 (medium) |
| 5 | Three groups, continuous | `WELCH_ANOVA` | 121.764 | <0.001 | η² = 0.856 (large) |
| 6 | Three groups, ordinal | `KRUSKAL_WALLIS` | 13.507 | 0.001 | rank η² = 0.202 (large) |
| 7 | Weak linear association | `PEARSON_CORRELATION` | 0.296 | 0.022 | Pearson's r = 0.296 (small) |
| 8 | Monotone (curved) association | `SPEARMAN_CORRELATION` | 1.000 | <0.001 | Spearman's ρ = 1.000 (large) |
| 9 | Parabolic (nonlinear-only) | `MAXBET` | 12.175 | <0.001 | BET symmetry = 0.963 (large) |
| 10 | 2×2 contingency, large expected | `CHI_SQUARED` | 6.416 | 0.011 | Cramér's V = 0.401 (medium) |
| 11 | 2×2 contingency, small expected | `FISHER_EXACT` | 0.111 | 0.486 | odds ratio = 0.111 |
| 12 | R×C, small expected (Freeman–Halton) | `FISHER_EXACT` | 18.000 | <0.001 | Cramér's V = 0.500 (large) |
| 13 | Paired binary | `MCNEMAR` | 10.000 | 0.424 | OR (discordant) = 1.500 |
| 14 | Count, low dispersion | `POISSON_REGRESSION` | 0.841 | 0.401 | IRR = 1.002 |
| 15 | Count, overdispersed | `NEGATIVE_BINOMIAL_REGRESSION` | 0.712 | 0.476 | IRR = 1.018 |
| 16 | Survival, two arms | `LOG_RANK` | 8.521 | 0.004 | hazard ratio = 0.444 |
| 17 | Survival with covariate | `COX_REGRESSION` | 1.456 | 0.146 | hazard ratio = 1.017 |
| 18 | Diagnostic discrimination | `ROC_AUC` | 0.820 | <0.001 | AUC = 0.820 (large) |
| 19 | Confounded association | `SPEARMAN_CORRELATION` | 0.993 | <0.001 | Spearman's ρ = 0.993 (large) |
| 20 | Ecological (county-level) | `SPEARMAN_CORRELATION` | −0.987 | <0.001 | Spearman's ρ = −0.987 (large) |

## Notable extras (beyond the primary statistic)

These are produced on the same runs and are the point of several cases:

- **#5 / #6 (omnibus):** a Holm-adjusted post-hoc table is recorded on the result —
  Games–Howell for Welch ANOVA, Dunn for Kruskal–Wallis.
- **#9 (MaxBET):** the parabola has Pearson r ≈ 0 yet BET rejects independence — the
  nonlinear-only signal a correlation screen misses; the dependence region is reported.
- **#10 (2×2 χ²):** the result also reports the odds ratio and φ; the effect-size CI is a real
  bootstrap interval (not the degenerate point it used to be).
- **#16 (log-rank):** Kaplan–Meier median survival per arm is reported alongside the
  hazard ratio (HR = 0.44 → treated arm has lower hazard).
- **#17 (Cox):** the scaled-Schoenfeld proportional-hazards check is recorded (MET here).
- **#18 (ROC):** sensitivity ≈ 0.76 and specificity ≈ 0.76 at the Youden-optimal threshold;
  the AUC CI is a 1000-sample bootstrap.
- **#19 (confounding):** the elicited confounder `z` drives both variables — the raw
  Spearman ρ = 0.99 collapses to an **adjusted partial ρ ≈ 0.00 (p ≈ 0.99)**, and the report
  flags that the adjustment happened.
- **#20 (ecological):** fires the H1–H3 caveats (ecological fallacy, MAUP, spatial
  autocorrelation) and sets `reporting_standard = STROBE`.

## Known limitation for review

For **ratio effect measures** (odds ratio, hazard ratio, incidence-rate ratio) the
`interpretation` label is computed with correlation-calibrated thresholds, so a value near the
null of 1.0 (e.g. #14, IRR = 1.002) can read as "large". The numeric estimate, CI, and p-value
are correct; only the qualitative word is mis-scaled for ratios. A ratio-aware interpretation
(distance from 1.0) is an open item — see `STATISTICIAN_REVIEW.md`.
