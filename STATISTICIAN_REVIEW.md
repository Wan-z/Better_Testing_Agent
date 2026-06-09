# HTA Statistician Review

**Status:** Step-8 review deliverable — the statistical decision points for expert audit.
**Scope:** v0.1.0 engine in [`src/hta/`](src/hta). Companion: [`BENCHMARK_CASES.md`](BENCHMARK_CASES.md)
(20 reproducible reference results), and [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md) for the
methodology rationale (§ references below point there).

Every decision is **deterministic** — no LLM is involved in profiling, test selection,
execution, or caveat generation. Line references are to the current source.

---

## 1. Distributional policy (§6.1)

| Decision | Choice | Where |
|---|---|---|
| Normality as a graded signal, not a gate | severity `NONE`/`MILD`/`STRONG` from \|skew\| / \|excess kurtosis\| (Kim 2013 thresholds) | [`profiler.py:87`](src/hta/modules/profiler.py) (`severity`) |
| No formal normality test above N = 2000 | Shapiro–Wilk only at N ≤ 2000; above it, severity from skew/kurtosis alone (KS-vs-estimated-params is invalid) | [`profiler.py:43`](src/hta/modules/profiler.py) (`_FORMAL_NORMALITY_MAX_N`), assembly in `profile_with_screen` |
| Parametric-vs-rank rule | `prefer_rank_based`: ORDINAL → rank; `n_min ≥ LARGE_N` → parametric (CLT); else rank only on a STRONG departure | [`selector.py:28`](src/hta/modules/selector.py) |
| `LARGE_N = 30` | proposed CLT threshold — **awaiting sign-off** | [`selector.py:25`](src/hta/modules/selector.py) |
| Per-group (not pooled) severity for comparisons | a pooled bimodal column looks non-normal exactly when groups differ — the wrong signal | [`selector.py:72`](src/hta/modules/selector.py) (`_group_severity`) |

## 2. Test-selection tree (§6.2, §6.5) — `selector.py::select` ([`:89`](src/hta/modules/selector.py))

Dispatch order: **count → survival → diagnostic → grouped comparison → association → categorical.**

| Outcome / design | Selected test | Where |
|---|---|---|
| Count (overdispersed: var > 1.3·mean) | `NEGATIVE_BINOMIAL_REGRESSION`, else `POISSON_REGRESSION` | [`selector.py:100`](src/hta/modules/selector.py) |
| Time-to-event + 0/1 event indicator, covariate | `COX_REGRESSION` | [`selector.py:110`](src/hta/modules/selector.py) |
| Time-to-event + event indicator, group | `LOG_RANK` | [`selector.py:117`](src/hta/modules/selector.py) |
| Binary outcome + continuous index | `ROC_AUC` | [`selector.py:171`](src/hta/modules/selector.py) |
| 2 groups, between | `MANN_WHITNEY_U` (rank) / `WELCH_T` (default, **no Levene pretest**) | [`selector.py:145`](src/hta/modules/selector.py) |
| 2 groups, within | `WILCOXON_SIGNED_RANK` / `PAIRED_T` | [`selector.py:142`](src/hta/modules/selector.py) |
| ≥3 groups | `KRUSKAL_WALLIS` / `WELCH_ANOVA` (default) | [`selector.py:148`](src/hta/modules/selector.py) |
| Two continuous/ordinal vars | BET-driven: nonlinear → `MAXBET`, monotone/ordinal → `SPEARMAN`, else `PEARSON` | [`selector.py:251`](src/hta/modules/selector.py) (`_association`) |
| Categorical × categorical | within 2×2 → `MCNEMAR`; min expected ≥5 → `CHI_SQUARED`; else `FISHER_EXACT` | [`selector.py:189`](src/hta/modules/selector.py) (`_categorical`) |

`INDEPENDENT_T` / `ONE_WAY_ANOVA` (pooled variance) are reachable only via an explicit
`force_student`-style override and are never returned by the tree in v0.1.0.

## 3. Execution, effect sizes, and CIs (§6.6) — `executor.py`

| Test | Implementation | Effect size / CI | Where |
|---|---|---|---|
| Welch / Student t | `scipy.ttest_ind`; Levene only on the equal-variance override | Cohen's d, bootstrap CI | [`executor.py:454`](src/hta/modules/executor.py) |
| Welch ANOVA | true Welch F via `pingouin.welch_anova`, closed-form fallback (**not** Alexander–Govern) | η², bootstrap CI | [`executor.py:329`](src/hta/modules/executor.py) |
| Post-hoc (Holm) | Games–Howell / Tukey / Dunn, recorded on the result | — | [`executor.py:297`](src/hta/modules/executor.py) (`_posthoc_note`) |
| Kruskal–Wallis | `scipy.kruskal` + Dunn | rank ε²/η², bootstrap CI | [`executor.py:588`](src/hta/modules/executor.py) |
| χ² | `scipy.chi2_contingency` | Cramér's V (bootstrap CI); 2×2 also OR + φ | [`executor.py:612`](src/hta/modules/executor.py), `_or_phi_2x2` [`:423`](src/hta/modules/executor.py) |
| Fisher | 2×2 exact (OR); R×C **Freeman–Halton via fixed-margin permutation** + Cramér's V | | [`executor.py:639`](src/hta/modules/executor.py), `_rxc_fisher_perm` [`:431`](src/hta/modules/executor.py) |
| Pearson / Spearman | `scipy.pearsonr` (Fisher-z CI) / `spearmanr` (bootstrap CI) | | [`executor.py:694`](src/hta/modules/executor.py), [`:710`](src/hta/modules/executor.py) |
| Poisson / NegBin | `statsmodels` GLM with offset | IRR = exp(β), Wald CI back-transformed | [`executor.py:759`](src/hta/modules/executor.py) |
| Log-rank | `lifelines.logrank_test`; HR from a univariate Cox; KM medians per group | hazard ratio | [`executor.py:840`](src/hta/modules/executor.py) |
| Cox PH | `lifelines.CoxPHFitter`; scaled-Schoenfeld PH test → flag VIOLATED | hazard ratio, log-scale CI | [`executor.py:880`](src/hta/modules/executor.py) |
| ROC / AUC | `sklearn.roc_auc_score`; Mann–Whitney-equivalent p; Youden sens/spec | AUC, bootstrap CI | [`executor.py:937`](src/hta/modules/executor.py) |
| Sensitivity power | minimum detectable Cohen's d at observed N (never observed power) | | [`executor.py:147`](src/hta/modules/executor.py) (`_sensitivity_mde_d`) |

Bootstrap CIs use stdlib `random` (seed 42, n = 1000) so they are deterministic.

## 4. Causal adjustment (§5.3) — `causal.py`

| Decision | Choice | Where |
|---|---|---|
| Adjustment set | recommended **and** measured confounders | [`causal.py:48`](src/hta/modules/causal.py) (`CausalAnalyser.analyse`) |
| Usable covariates | recommended + measured + numeric + present, not the outcome/exposure | [`causal.py:86`](src/hta/modules/causal.py) |
| Adjusted estimate | partial correlation (associations) / ANCOVA (continuous group comparisons), via pingouin; recorded on the result | [`executor.py:972`](src/hta/modules/executor.py) (`_adjusted_estimate`) |
| Unmeasured confounder | recorded as a `CausalGraph` warning → WARNING caveat | `causal.py:48`, reporter below |

## 5. Caveats & reporting standard (§5.6.1, §6.6, §6.7) — `reporter.py`

| Decision | Where |
|---|---|
| General caveats (marginal p, observational, BET nonlinear, confounder adjusted/unadjusted) | [`reporter.py:82`](src/hta/modules/reporter.py) (`_build_caveats`) |
| Healthcare catalog H1–H9 (ecological/MAUP/spatial, Poisson, non-proportional hazards, censoring, ratio-vs-absolute, prevalence, clustering) | [`reporter.py:164`](src/hta/modules/reporter.py) (`_healthcare_caveats`) |
| EQUATOR reporting standard (CONSORT / STROBE / STARD) | [`reporter.py:152`](src/hta/modules/reporter.py) (`_reporting_standard`) |

---

## 6. Open items / known limitations for the reviewer

1. **Ratio-measure interpretation.** OR/HR/IRR use the correlation-calibrated small/medium/large
   thresholds, so a value near 1.0 can read as "large" (e.g. `BENCHMARK_CASES.md` #14). Estimate,
   CI, and p are correct; the qualitative word needs a ratio-aware (distance-from-1) scale.
2. **Pending defaults.** `LARGE_N = 30` and the NONE/MILD/STRONG skew/kurtosis cut-points are
   proposed and await Statistician A sign-off.
3. **BET.** MaxBET uses the pure-Python depth-2 / two-stage engine ([`bet_screen.py`](src/hta/bet_screen.py)),
   not the R `BET` package; the normalised-MI supplement is not implemented.
4. **AUC CI** is a bootstrap interval, not the analytic DeLong CI; the DeLong test for comparing
   two AUCs is not implemented.
5. **Log-rank HR** is taken from a univariate Cox fit rather than a separate Mantel–Haenszel
   estimator (same estimand; numerically near-identical).
6. **Dialogue & design.** The study-design dialogue runs in the web layer, not the orchestrator;
   `agent.py` uses a default observational design when none is supplied. Confounder adjustment is
   partial-correlation / ANCOVA (covariate adjustment), not a full multivariable model.
7. **Structural types.** `GEOSPATIAL` / `DATETIME` are not auto-typed by the profiler; the
   ecological caveats (H1–H3) fire on an areal column-**name** heuristic in the reporter. The
   clustering caveat (H9) likewise keys off a subject/cluster-id name with repeats.
8. **`TIME_TO_EVENT` detection** is name-based (duration-like column) and gated on the presence
   of a 0/1 event-indicator companion; with no event column the duration is treated as continuous.
9. **Reserved tests.** `LINEAR_REGRESSION`, `LOGISTIC_REGRESSION`, `LINEAR_MIXED_MODEL`, and
   `GENERALIZED_ESTIMATING_EQUATIONS` are in the enum but not selectable/executable in v0.1.0.

*Generated 2026-06-09 against the v0.1.0 engine. Benchmark values: `BENCHMARK_CASES.md`.*
