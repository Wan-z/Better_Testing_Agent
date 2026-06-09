# Hypothesis Testing Agent — Technical Report

**Version:** 0.1.0-dev  
**Date:** 2026-04-29  
**Status:** Core pipeline implemented (profiler → selector → executor → reporter) with CLI + web; statistician review and the dialogue/causal stages pending  
**Authors:** Development team + three statistician co-investigators (review pending)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Design Principles](#2-design-principles)
3. [System Architecture](#3-system-architecture)
4. [Data Models](#4-data-models)
5. [Module Specifications](#5-module-specifications)
6. [Statistical Decision Logic](#6-statistical-decision-logic)
7. [GPT-5.4 / Azure OpenAI Integration](#7-gpt-54--azure-openai-integration)
8. [Development Standards](#8-development-standards)
9. [Completed Work](#9-completed-work)
10. [Planned Work](#10-planned-work)
11. [Definition of Done](#11-definition-of-done)
12. [Environment Setup](#12-environment-setup)

---

## 1. Project Overview

The **Hypothesis Testing Agent (HTA)** is an AI-powered statistical reasoning system designed to act as a rigorous methodological collaborator for researchers. Its distinguishing characteristic is that it reasons about *study design and causal structure first*, before selecting or executing any statistical test.

**General-purpose, healthcare-specialized.** HTA accepts any tabular dataset and the classical decision tree (§6.2) handles continuous, ordinal, and categorical outcomes in any domain. On top of that generality it is *specialized for healthcare and epidemiology*: the data forms that dominate clinical work — event **counts/rates**, **time-to-event** data with censoring, and **diagnostic-accuracy** evaluation — are first-class (§6.5), reported with the clinically meaningful effect measures a reviewer expects (incidence-rate ratios, hazard ratios, risk ratios, NNT, AUC — §6.6), tied to the relevant reporting guideline (CONSORT/STROBE/STARD/TRIPOD/PRISMA), and guarded by a healthcare caveat catalog (ecological fallacy, MAUP, spatial autocorrelation, non-proportional hazards, informative censoring, prevalence-dependence — §6.7). The NC county overdose / clinic-access example (`data/overdose_ed_visits.csv`) exercises this path end-to-end.

### Goals

- Prevent common misuse of statistical tests (e.g., applying a t-test to non-normal data, ignoring confounders in observational studies).
- Produce reproducible, well-documented analyses with appropriate effect sizes, power analyses, and methodological caveats.
- Generate methods-section prose and plain-language summaries suitable for research papers.
- Provide statistician co-investigators with a codebase they can audit, validate, and extend.

### Intended Users

| User type | How they interact |
|---|---|
| Researchers | Via CLI (`hta run`) or Python API |
| Statistician co-investigators | Code review, benchmark validation, decision-tree refinement |
| Developers | Module extensions, new test implementations |

---

## 2. Design Principles

These principles were established at project inception and apply to every line of code.

| Principle | Rationale |
|---|---|
| **Shared data models as lingua franca** | Every module reads/writes the same Pydantic v2 models. No ad-hoc dicts passed between components. |
| **Direct linear pipeline** | The pipeline is a strictly linear call chain (profile → design → select → execute → report) wired by `agent.py`. v0.1.0 deliberately omits the originally-planned synchronous event bus: the chain is linear, so a bus added indirection without the swappability the CLI/web callers actually use (see §10b #9). Modules exchange only the shared Pydantic models and do not import one another. |
| **Deterministic test selection** | The statistical decision tree uses no LLM inference. Statisticians can read, audit, and revise it as plain Python logic. |
| **Dry-run by default** | Any function that calls an external API accepts `dry_run: bool = True`. Tests never make real API calls. |
| **Type annotations everywhere** | All public functions are fully typed. `mypy --strict` is run in CI. |
| **No hardcoded secrets** | All credentials and endpoints are loaded from `.env` via `python-dotenv`. |
| **Tests before proceeding** | Each step is gated on passing pytest tests before the next step begins. |

---

## 3. System Architecture

### Pipeline Overview

```
User input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     HypothesisTestingAgent                   │
│                        (agent.py)                            │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐  │
│  │DataProfile│──▶│StudyDesign│──▶│Statistical│──▶│TestResult│  │
│  │(profiler) │   │(dialogue) │   │Test enum  │   │(executor)│  │
│  └──────────┘   └──────────┘   │(selector) │   └────┬────┘  │
│                                 └──────────┘        │        │
│                                                     ▼        │
│                                               ┌──────────┐   │
│                                               │  Report  │   │
│                                               │(reporter)│   │
│                                               └──────────┘   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
CLI output (Rich) / Python Report object
```

### Pipeline stages

In v0.1.0 `agent.py` wires the modules directly in a linear chain (the originally-planned
event bus was dropped — see §2 and §10b #9). Each stage produces one shared Pydantic model
that the next stage consumes:

| Stage | Output model | Module |
|---|---|---|
| Profile (+ BET screen) | `DataProfile` | `modules/profiler.py` |
| Study design | `StudyDesign` | `modules/dialogue.py` — *planned*; v0.1.0 uses a default design |
| Causal graph | `CausalGraph` | `modules/causal.py` — adjustment set + adjusted estimate (partial corr / ANCOVA) ✅ |
| Select test | `StatisticalTest` (via `Selection`) | `modules/selector.py` |
| Execute | `TestResult` | `modules/executor.py` |
| Report | `Report` | `modules/reporter.py` |

### Repository Layout

```
Better_Testing_Agent/
├── README.md
├── TECHNICAL_REPORT.md       # This document
├── IMPLEMENTATION_PLAN.md
├── pyproject.toml            # declares the `hta = hta.cli:app` console entry point
├── src/
│   └── hta/
│       ├── __init__.py
│       ├── config.py         # Credentials + defaults                            ✅
│       ├── bet_screen.py     # BET pairwise nonlinear-dependence engine          ✅
│       ├── models/           # Shared Pydantic models (data/design/test/report)  ✅
│       ├── modules/
│       │   ├── profiler.py   # Type inference + normality + BET → DataProfile    ✅
│       │   ├── selector.py   # §6.2 decision tree → Selection                    ✅
│       │   ├── executor.py   # Statistical test execution → TestResult           ✅
│       │   ├── reporter.py   # Caveats + plot specs + text → Report              ✅
│       │   ├── dialogue.py   # Study-design dialogue                       (planned)
│       │   └── causal.py     # Causal graph / adjustment set               (planned)
│       ├── agent.py          # Linear orchestrator — no event bus (§2)           ✅
│       └── cli.py            # `hta run` (Typer + Rich)                          ✅
├── tests/                    # test_{models,bet_screen,examples,playground}      ✅
│                             #  + test_{profiler,selector,executor,reporter,agent,cli}  ✅
├── playground/               # Zero-dependency demo; pipeline.py re-exports the engine
├── examples/                 # Runnable BET analyses (stars, gene-pair, STAI-X)
└── web/                      # FastAPI + React app; backend delegates to src/hta
```

*Not yet created: `modules/dialogue.py`, `modules/causal.py`, and the Step-8 review
deliverables `STATISTICIAN_REVIEW.md` / `BENCHMARK_CASES.md`.*

---

## 4. Data Models

All shared data structures are defined in `src/hta/models/` as **Pydantic v2** models. These are the single source of truth for every inter-module data exchange. Statistician co-investigators should focus their review here.

### 4.1 Data models (`models/data.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `VariableType` | Enum: measurement level / structural role | `CONTINUOUS`, `ORDINAL`, `CATEGORICAL`, `BINARY`, `COUNT`, `TIME_TO_EVENT`, `DATETIME`, `GEOSPATIAL`, `IDENTIFIER` (see §6.5) |
| `DistributionStats` | Descriptive statistics | mean, std, median, IQR, skewness, kurtosis, min, max |
| `NormalityTest` | Formal normality test result | name, statistic, p_value, `is_normal` (p > 0.05) |
| `Variable` | Single variable profile | name, type, n, n_missing, distribution_stats, normality, unique_values |
| `DependenceForm` | Enum: BET dependence shape | `LINEAR`, `MONOTONE`, `PARABOLIC`, `SINUSOIDAL`, `CHECKERBOARD`, `COMPLEX`, `INDEPENDENT` (§5.1a) |
| `DependenceFinding` | One BET-screened pair | x, y, bet_z, p_value, bid, form, direction, pearson_r, spearman_rho, nonlinear_only |
| `DataProfile` | Full dataset profile | variables, n_groups, group_var, outcome_var, notes, nonlinear_dependencies (BET EDA) |

### 4.2 Design models (`models/design.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `StudyDesignType` | Enum | `EXPERIMENTAL`, `OBSERVATIONAL`, `QUASI_EXPERIMENTAL` |
| `MeasurementType` | Enum | `BETWEEN_SUBJECTS`, `WITHIN_SUBJECTS`, `MIXED` |
| `VariableRole` | Enum: causal role | `CONFOUNDER`, `COLLIDER`, `MEDIATOR`, `EFFECT_MODIFIER`, `COVARIATE` |
| `Confounder` | One causal variable | name, role, is_measured, adjustment_recommended, rationale |
| `StudyDesign` | Captured study design | design_type, measurement_type, is_randomized, confounders, notes, subgroup_variables (stratify/effect-modifier — §5.1a/§7.2), reporting_standard (§6.6) |
| `CausalGraph` | DAG structure | nodes, edges (ordered pairs), adjustment_set, warnings |

### 4.3 Test models (`models/test.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `StatisticalTest` | Enum: 24 tests (4 reserved for v0.2.0) | classical (§6.2) + healthcare: `POISSON_REGRESSION`, `NEGATIVE_BINOMIAL_REGRESSION`, `LOG_RANK`, `COX_REGRESSION`, `ROC_AUC` (§6.5); reserved `LINEAR_REGRESSION`, `LOGISTIC_REGRESSION`, `LINEAR_MIXED_MODEL`, `GENERALIZED_ESTIMATING_EQUATIONS` |
| `AssumptionStatus` | Enum | `MET`, `VIOLATED`, `UNTESTABLE`, `MARGINAL` |
| `AssumptionCheck` | One assumption result | name, status, test_used, statistic, p_value, note |
| `EffectSize` | Effect size with CI | measure_name, value, interpretation, ci_lower, ci_upper |
| `TestResult` | Complete test output | test_used, statistic, p_value, df, effect_size, assumption_checks, CI, is_significant, power |

### 4.4 Report models (`models/report.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `CaveatSeverity` | Enum | `INFO`, `WARNING`, `CRITICAL` |
| `Caveat` | Methodological concern | severity, message, recommendation |
| `PlotSpec` | Declarative plot spec | plot_type, data (dict), title, x_label, y_label |
| `Report` | Final analysis report | data_profile, study_design, test_result, plain_language_summary, caveats, plots, methods_text |

### Model relationships

```
DataProfile ──────────────────────────────────┐
  └── list[Variable]                           │
        └── DistributionStats                  │
        └── NormalityTest                      ├──▶ Report
                                               │
StudyDesign ──────────────────────────────────┤
  └── list[Confounder]                         │
                                               │
TestResult ───────────────────────────────────┘
  └── EffectSize
  └── list[AssumptionCheck]
```

---

## 5. Module Specifications

### 5.1 DataProfiler (`modules/profiler.py`) — Step 3

**Inputs:** raw data (DataFrame, list of dicts, CSV string, or dict of lists)  
**Outputs:** `DataProfile` (published as `EVENT_DATA_PROFILED`)

Responsibilities:
- Infer variable type (healthcare-aware, §6.5): structural roles (IDENTIFIER, DATETIME, GEOSPATIAL) first; then BINARY, COUNT, TIME_TO_EVENT, CATEGORICAL, ORDINAL, CONTINUOUS
- Normality *severity* (§6.1): Shapiro-Wilk corroboration at N ≤ 2000; skew/kurtosis magnitude above that
- Compute all `DistributionStats` fields
- Flag data quality issues: >5% missingness, constant variables, outliers (|Z| > 3.5), and **tie / zero-inflation severity** (matters for the copula-based dependence screen below)
- Group-level statistics when a group variable is specified
- **Exploratory dependence screen (BET)** — see §5.1a: scan numeric pairs for dependence (especially nonlinear), label its form, and flag nonlinear-only pairs

#### 5.1a Exploratory dependence analysis — BET pairwise screen

Building on the BET framework of **Zhang, K. (2019), "BET on Independence," *Journal of the
American Statistical Association* 114(528), 1620–1637, DOI
[10.1080/01621459.2018.1537921](https://doi.org/10.1080/01621459.2018.1537921)** — which
introduced binary expansion statistics (BEStat), the Max BET procedure, and the binary
interaction design (BID) reparameterization — and following its genomic application **Xiang,
Zhang, Liu, Hoadley, Perou, Zhang & Marron (2023), "Pairwise Nonlinear Dependence Analysis of
Genomic Data," *The Annals of Applied Statistics* 17(4), DOI
[10.1214/23-AOAS1745](https://doi.org/10.1214/23-AOAS1745)** (preprint arXiv:2202.09880),
the profiler runs a deterministic EDA pass over the
CONTINUOUS/COUNT/ORDINAL columns *before* any test is selected, implemented in
`hta/bet_screen.py` (pure-stdlib, no R/numpy needed for the depth-2 screen):

1. **Copula transform** — each variable is mapped to the empirical copula on (0, 1] by
   rank, making the analysis marginal-free and outlier-robust.
2. **Tie / discreteness handling** — piled-up values (zeros, imputed values, detection
   limits — pervasive in healthcare data) break BET's continuity assumption, so tied
   observations are **jittered** by a tiny deterministic amount before ranking (Xiang et al.
   2023 §3.1). The tie fraction is recorded as a data-quality note.
3. **MaxBET at depth d = 2** — for every pair, the nine Binary Interaction Designs (BIDs)
   are scored by their symmetry statistic `S`; the strongest |S| is taken, Bonferroni-adjusted
   across the 9 BIDs and across all screened pairs (a two-level adjustment: across BIDs, then
   across pairs).
4. **Form + direction** — the dominant BID labels the *form* of dependence
   (`DependenceForm`: MONOTONE, PARABOLIC, SINUSOIDAL/"W"-bimodal, CHECKERBOARD, LINEAR,
   COMPLEX) and the sign of `S` gives the direction. This interpretability is BET's advantage
   over a single correlation coefficient.
5. **Nonlinear-only flag** — a pair that is BET-significant while |Pearson| and |Spearman|
   are both small is flagged `nonlinear_only`. This is BET's headline finding: much real
   dependence is invisible to linear methods.

Each pair becomes a `DependenceFinding` on `DataProfile.nonlinear_dependencies` (ranked by
BET `Z`). These feed two downstream consumers: the **dialogue** (a nonlinear/mixture-type
finding triggers the subgroup question, §7.2 Rule 8) and the **selector** (the dominant form
becomes the `relationship` prior, §6.2). Mixture-type forms (CHECKERBOARD/SINUSOIDAL/
PARABOLIC) are *subtype-driven* patterns (the §8 TCGA finding) — the EDA's signal that latent
subgroups may explain the dependence.

**Two capabilities carried over from Zhang (2019).** The engine exposes both BET workflows the
2019 paper demonstrates on real data:

1. **Two-stage Max BET over depths** (`maxbet_twostage`, default `d_max = 4`, §4.5): a focused,
   confirmatory independence test for a single pair that searches depths *d* = 1..d_max with a
   second-level Bonferroni across depths, instead of the fixed depth-2 screen. It adapts the
   resolution to the data — catching dependence (e.g. a higher-depth band) that the depth-2
   screen misses.
2. **Dependency-region interpretation** (`cross_region`; `PairDependence.positive_region` /
   `region_description`): on rejection, the dominant cross interaction's positive/negative cells
   on the 2^d × 2^d copula grid show *where* the dependence lives. This is BET's signature
   advantage over a single p-value, and feeds a `PlotSpec` (a shaded copula heat-cell overlay).

Under the empirical copula (unknown margins) the symmetry statistic's exact null is
hypergeometric — `(Ŝ + n)/4 ∼ Hypergeometric(n, n/2, n/2)` (Zhang 2019, Thm 4.2), so
`Var(Ŝ) = n²/(n−1) ≈ n` — and we use the large-*n* normal approximation `Z = |S|/√n` (Kou &
Ying 1996), exact to the finite-population correction.

Two worked examples reproduce the paper's analyses (synthetic data, deterministic) and double as
regression tests (`tests/test_examples.py`):

| Example | Paper §  | What it shows |
|---|---|---|
| `examples/stars_independence.py` | §7 (stars) | Two-stage Max BET rejects independence (Pearson r ≈ −0.07 sees nothing) and its region draws the "Milky-Way band" — detection **and** interpretation. |
| `examples/gene_pair_subtype.py` | §8 (TCGA)  | A depth-2 screen flags a nonlinear gene pair created by a **subtype mixture**; the subtype label explains it (contextual view), and the pair jointly classifies the subtype better than either gene alone (§8.3). Mirrors the agent's Rule-8 / subgroup path. |

### 5.2 DesignDialogue (`modules/dialogue.py`) — Step 4

**Inputs:** `DataProfile`, free-text hypothesis description  
**Outputs:** `StudyDesign` (published as `EVENT_DESIGN_CAPTURED`)

Responsibilities:
- Multi-turn dialogue with the user, powered by **GPT-5.4 via Azure OpenAI**
- Enforces a structured protocol (see §7.1)
- **Surfaces the BET EDA findings** (top nonlinear pairs + their form) as context, and when a
  nonlinear / mixture-type dependence is present asks whether known **subgroups/subtypes**
  (e.g. disease subtype, sex, site) explain it — captured as `StudyDesign.subgroup_variables`
  (§7.2 Rule 8). This operationalises the paper's "explain nonlinear dependence by subtype"
  step and fills the effect-modification gap.
- Terminates when the model calls the `capture_study_design` tool with enough information
- Returns a pre-defined `StudyDesign` in `dry_run=True` mode

### 5.3 CausalAnalyser (`modules/causal.py`) — Step 4

**Inputs:** `DataProfile`, `StudyDesign`  
**Outputs:** `CausalGraph` (published as `EVENT_GRAPH_BUILT`)

Responsibilities:
- Build a directed acyclic graph (DAG) from user-provided confounder information
- Identify the minimal adjustment set needed for an unconfounded estimate
- Warn when unmeasured confounders are present

### 5.4 TestSelector (`modules/selector.py`) — Step 5

**Inputs:** `DataProfile`, `StudyDesign`  
**Outputs:** `StatisticalTest` enum value (published as `EVENT_TEST_SELECTED`)

Responsibilities:
- Purely deterministic decision tree — **no LLM calls**
- Returns the appropriate test based on outcome type, number of groups, measurement type, and normality
- **Sources the `relationship` signal from the BET EDA** (`DataProfile.nonlinear_dependencies`)
  for the outcome/predictor pair — the dominant `DependenceForm` maps to linear/monotone/
  nonlinear (§6.2), so a nonlinear shape routes to MaxBET even if the user said "linear"
- **Stratified / contextual routing**: when `StudyDesign.subgroup_variables` is non-empty (a
  subtype-driven pattern was identified), selects the per-stratum test and records that a
  within-subgroup (contextual) analysis is run — mirroring the paper's four breast-cancer
  contexts. A formal interaction model is reserved for v0.2.0
- Provides a human-readable `get_selection_rationale()` explaining the choice
- Statistician Reviewer A will validate this decision tree

### 5.5 TestExecutor (`modules/executor.py`) — Step 6

**Inputs:** `pd.DataFrame`, `StatisticalTest`, group/outcome variable names, `StudyDesign`  
**Outputs:** `TestResult` (published as `EVENT_TEST_EXECUTED`)

Responsibilities:
- Executes the selected test using scipy, pingouin, or statsmodels
- Executes BET/MaxBET/BEAST via the **rpy2** bridge to the R `BET` package (v0.5.4+); see §6 and §12 for setup
- Computes appropriate effect size with 95% CI (see §6 for per-test details)
- Runs and records all relevant assumption checks before the main test
- Reports *sensitivity power* only — the minimum detectable effect at the observed N (α = 0.05, target power = 0.80) via `statsmodels.stats.power`; **never** observed/post-hoc power, which is a deterministic function of the p-value and adds no information (§5.6.1 caveat, resolves issue #4)

### 5.6 Reporter (`modules/reporter.py`) — Step 7

**Inputs:** `DataProfile`, `StudyDesign`, `TestResult`  
**Outputs:** `Report` (published as `EVENT_REPORT_READY`)

Responsibilities:
- Deterministic caveat generation (6 rules, see §5.6.1)
- Declarative plot specification generation (no rendering — just `PlotSpec` objects)
- **GPT-5.4** calls for `plain_language_summary` and `methods_text` (dry-run returns stubs)

#### 5.6.1 Caveat generation rules

| Severity | Condition |
|---|---|
| `CRITICAL` | Any `AssumptionCheck` has `status == VIOLATED` |
| `WARNING` | Sensitivity power weak — minimum detectable effect > 0.5 (only a large effect is detectable at the observed N) |
| `WARNING` | `0.01 ≤ p_value ≤ 0.05` (marginal result) |
| `WARNING` | Effect size is small (Cohen's d < 0.2 or Cramér's V < 0.1) and result is significant |
| `INFO` | Multiple groups tested without multiple-comparison correction |
| `INFO` | Study is observational (flag potential for causal language misuse) |

---

## 6. Statistical Decision Logic

The test-selection decision tree, implemented in `selector.py`. This is the primary artefact for statistician review. It is **purely deterministic** and treats every distributional property as a *graded signal*, never as a binary significance gate (§6.1). All numeric thresholds below are proposed defaults pending sign-off by Statistician A.

### 6.1 Distributional policy (supersedes the old "normality gate")

`DataProfiler` supplies signals; the selector consumes them as **data, not as yes/no switches**:

- `outcome_type` ∈ {CONTINUOUS, ORDINAL, BINARY, CATEGORICAL}
- `n_groups`, `measurement` ∈ {BETWEEN, WITHIN (paired/repeated)}, `n_min` — smallest per-group (or per-pair) sample size
- `relationship` ∈ {LINEAR, MONOTONE, NONLINEAR} — correlation analyses only. **Primary source: the BET EDA** — the dominant `DependenceForm` of the outcome/predictor pair in `DataProfile.nonlinear_dependencies` (§5.1a) maps via `relationship_form()` (LINEAR→linear, MONOTONE→monotone, PARABOLIC/SINUSOIDAL/CHECKERBOARD/COMPLEX→nonlinear). Falls back to `StudyDesign.notes` (DesignDialogue rule 7) if the pair was not screened
- `table_shape` ∈ {TWO_BY_TWO, RxC} and `min_expected` (smallest expected cell count) — categorical outcomes only
- `nonnormality` ∈ {NONE, MILD, STRONG} — *severity*, derived from robust descriptors and corroborated by Shapiro–Wilk **only at N ≤ 2 000**. Above N = 2 000 no formal normality test is run — the previous one-sample KS-vs-estimated-parameters path is statistically invalid (it needs Lilliefors) and flags essentially every real dataset, so it is uninformative for selection (resolves correctness issue #2). Severity at large N is judged from skew/kurtosis magnitude alone:
  - `NONE`: |skew| < 1 and |excess kurtosis| < 2
  - `MILD`: |skew| ∈ [1, 2) or |excess kurtosis| ∈ [2, 7)
  - `STRONG`: |skew| ≥ 2 or |excess kurtosis| ≥ 7 (Kim 2013)
- `force_student` — explicit user override (default `False`) requesting the equal-variance Student's t / pooled ANOVA.

Two consequences encode the agreed policy:

1. **Welch by default, no variance pretest.** For between-subjects continuous comparisons the selector never runs Levene to choose between Student's and Welch's t. Welch's t (and Welch's ANOVA for 3+ groups) is the unconditional default; the equal-variance form is reachable only via `force_student` (resolves correctness issue #3).
2. **Normality is a soft signal**, not a gate. Parametric-vs-rank is decided by:

```python
def prefer_rank_based(outcome_type, n_min, nonnormality) -> bool:
    if outcome_type == ORDINAL:        # scale of measurement, not a normality question
        return True
    if n_min >= LARGE_N:               # default LARGE_N = 30 — CLT: the mean is ~normal
        return False
    return nonnormality == STRONG      # at small N, only a *strong* departure switches
```

This replaces the fragile `is_normal = (p > 0.05)` switch: small samples no longer default to a parametric test merely because a low-power normality test failed to reject, and large samples are not forced onto rank methods because a high-power test flagged a trivial departure (resolves correctness issue #1).

### 6.2 Decision tree

The selector first **dispatches on the outcome's data form** so healthcare outcomes
(counts/rates, time-to-event, diagnostic discrimination) are routed to the right family
instead of being coerced into a mean comparison. The healthcare branches are specified in
§6.5; the classical continuous/categorical tree below is the fall-through.

```
# === Dispatch on outcome data form (healthcare-aware — see §6.5) ===
if outcome_type == COUNT:             → count / rate model     (§6.5a — Poisson / NegBin, IRR)
elif outcome_type == TIME_TO_EVENT:   → survival model         (§6.5b — log-rank / Cox, HR)
elif diagnostic_evaluation:           → diagnostic accuracy    (§6.5c — ROC / AUC, DeLong)
# GEOSPATIAL / DATETIME / IDENTIFIER are never outcomes (used for mapping, derivation, or
# excluded). Otherwise fall through to the classical tree:

# === CONTINUOUS or ORDINAL outcome ===
if outcome_type in (CONTINUOUS, ORDINAL):

    if n_groups == 2:
        if measurement == WITHIN:                       # paired / repeated measures
            → WILCOXON_SIGNED_RANK  if prefer_rank_based(...)  else  PAIRED_T
        else:                                           # between-subjects
            if prefer_rank_based(...):  → MANN_WHITNEY_U
            elif force_student:         → INDEPENDENT_T      # explicit override only
            else:                       → WELCH_T            # DEFAULT — no variance pretest

    elif n_groups >= 3:                                 # between-subjects omnibus
        if prefer_rank_based(...):  → KRUSKAL_WALLIS         # post-hoc: Dunn + Holm
        elif force_student:         → ONE_WAY_ANOVA          # pooled; post-hoc: Tukey HSD
        else:                       → WELCH_ANOVA            # DEFAULT; post-hoc: Games–Howell

    else:                                               # no grouping var → association of two cont./ord. vars
        if relationship == NONLINEAR:                              → MAXBET (default) / BEAST (override)
        elif relationship == MONOTONE or outcome_type == ORDINAL:  → SPEARMAN_CORRELATION
        else:                                                      # LINEAR expected
            if n_min < LARGE_N and nonnormality == STRONG:         → SPEARMAN_CORRELATION
            else:                                                  → PEARSON_CORRELATION

# === BINARY or CATEGORICAL outcome ===
if outcome_type in (BINARY, CATEGORICAL):
    if measurement == WITHIN and table_shape == TWO_BY_TWO:        → MCNEMAR        # paired binary
    elif min_expected >= 5:                                        → CHI_SQUARED
    else:                                                          → FISHER_EXACT   # 2×2: exact;
                                                                                    # R×C: Fisher–Freeman–Halton
```

### 6.3 Omnibus follow-up and multiple comparisons (resolves scope issue #7)

A 3+ group omnibus result is never reported alone; the planned follow-up and correction family are fixed by the chosen omnibus test and recorded on the `TestResult`:

- `WELCH_ANOVA` → Games–Howell post-hoc (does not assume equal variances), Holm-adjusted.
- `ONE_WAY_ANOVA` → Tukey HSD.
- `KRUSKAL_WALLIS` → Dunn's test, Holm-adjusted.

"No correction applied" is no longer a silent default — it would have to be an explicit, recorded choice.

### 6.4 Categorical effect size by table shape (resolves scope issue #6)

Fisher's odds ratio is defined only for 2×2 tables, but the tree reaches `CHI_SQUARED`/`FISHER_EXACT` for general R×C tables too. The executor therefore branches on `table_shape`:

- **2×2** → odds ratio (plus φ). A 2×2 `CHI_SQUARED` also reports the odds ratio.
- **R×C** → Cramér's V (the odds ratio is undefined; Fisher's exact uses the Fisher–Freeman–Halton generalisation).

### 6.5 Healthcare specialization & data-form coverage

HTA is **general** — it accepts any tabular dataset and the classical tree (§6.2) handles
continuous, ordinal, and categorical outcomes regardless of domain. It is **specialized for
healthcare**: the data forms that dominate clinical and epidemiological work — event
counts/rates, time-to-event with censoring, and diagnostic discrimination — are recognised
by the profiler and routed to the methods that those data actually require, with the
clinically meaningful effect measures (§6.6) and the domain caveats (§6.7) attached.

#### Data-form taxonomy (how each form is detected and routed)

| `VariableType` | Detection signal | As outcome → | As exposure/covariate |
|---|---|---|---|
| `CONTINUOUS` | numeric, many distinct values | §6.2 mean/correlation tree | covariate |
| `ORDINAL` | ordered categories / small integer scale | rank-based (§6.2) | ordinal predictor |
| `CATEGORICAL` | unordered labels, >2 levels | χ²/Fisher (§6.2/§6.4) | grouping/strata |
| `BINARY` | exactly 2 levels | χ²/Fisher; risk/odds (§6.6) | grouping |
| `COUNT` | non-negative integers; often an exposure/offset column (`population`, `person_years`) | §6.5a Poisson/NegBin | predictor |
| `TIME_TO_EVENT` | duration column **+** an event/censoring indicator | §6.5b log-rank/Cox | — |
| `DATETIME` | parseable dates/timestamps | derive duration or time series; not tested directly | time index |
| `GEOSPATIAL` | lat/long pair or areal id (FIPS/region) | never an outcome; drives maps + spatial caveats (§6.7) | strata |
| `IDENTIFIER` | unique key per row / high-cardinality id | excluded from testing | excluded |

#### 6.5a Count & rate outcomes (incidence)

Counts (ED visits, hospitalisations, deaths), optionally per an exposure (person-time or
population — supplied as a **rate offset** `log(exposure)`), are **not** means and must not be
analysed with t-tests. The agent models them and reports an **incidence-rate ratio (IRR)**:

```
overdispersed = variance(count) > mean(count)        # check on the (conditional) counts
if overdispersed:  → NEGATIVE_BINOMIAL_REGRESSION    # DEFAULT when overdispersed (the usual case)
else:              → POISSON_REGRESSION              # only when variance ≈ mean
```

- Overdispersion (variance > mean) is the rule, not the exception, in real count data; an
  unadjusted Poisson fit then gives anti-conservative standard errors, so negative binomial
  is the safe default whenever overdispersion is detected.
- A rate offset (`log(person_time)` / `log(population)`) converts counts to rates so the
  coefficient is an IRR.
- *County-level overdose ED counts with a `population` offset are the canonical example.*

#### 6.5b Time-to-event (survival) outcomes

A `TIME_TO_EVENT` column paired with an event indicator (1 = event, 0 = censored) triggers
the survival family. Right-censoring is handled natively — it must not be dropped or treated
as the event time.

```
if covariate_adjustment_needed or continuous_exposure:  → COX_REGRESSION   # hazard ratio
else:                                                    → LOG_RANK         # group comparison
# Kaplan–Meier curves + median survival are always reported descriptively alongside.
```

- Workflow: KM curves to visualise → log-rank for an unadjusted group comparison → Cox when
  covariate adjustment / a continuous exposure / a hazard-ratio estimate is needed.
- The **proportional-hazards (PH) assumption** is checked (scaled Schoenfeld residuals); a
  violation is recorded as an `AssumptionCheck` and a §6.7 caveat.

#### 6.5c Diagnostic-accuracy evaluation

When the question is "how well does this marker/score discriminate disease?" (a continuous or
ordinal `index` against a `BINARY` reference standard), the agent runs `ROC_AUC`:

- Reports **AUC** with a DeLong 95% CI, plus the sensitivity/specificity/likelihood-ratio
  pair at the chosen (or Youden-optimal) threshold.
- Comparing two markers' AUCs uses the **DeLong test**.
- Sens/spec are prevalence-independent; predictive values are not — PPV/NPV are reported only
  with the operating prevalence stated (§6.7).

#### Clustered / longitudinal data (reserved for v0.2.0)

Patients nested in hospitals, or repeated measures over time, violate independence. The enum
reserves `LINEAR_MIXED_MODEL` (subject-level random effects) and
`GENERALIZED_ESTIMATING_EQUATIONS` (population-averaged, marginal) for this. In v0.1.0 the
selector does **not** return them; instead, when a clustering/`IDENTIFIER` key or repeated
`subject_id` is detected, it records a `WARNING` caveat that naive tests understate standard
errors and a mixed/GEE model is indicated.

### 6.6 Clinical effect measures, significance, and reporting standards

**Effect measures are clinical, not just standardized.** Every result carries the measure a
clinician expects, with a confidence interval (ratios on the ratio scale):

| Outcome / test | Primary measure | Also reported |
|---|---|---|
| Binary (2 groups) | Risk ratio (RR) — cohort/RCT; Odds ratio (OR) — case-control | Absolute risk difference (ARD), **NNT/NNH = 1/ARD** |
| Count / rate | Incidence-rate ratio (IRR) | rate difference |
| Time-to-event | Hazard ratio (HR) | median-survival difference |
| Diagnostic | AUC | sensitivity, specificity, LR+ / LR− |

- **Report absolute alongside relative.** A large relative reduction can be clinically trivial
  when the baseline risk is low (large NNT); RR/OR/HR/IRR are therefore always paired with an
  absolute measure so the reader can judge magnitude.
- **OR vs RR.** The odds ratio approximates the risk ratio only for rare outcomes; for common
  outcomes the OR exaggerates the effect, so RR is preferred whenever the design supports it.

**Statistical vs clinical significance.** A significant *p* answers "is there an effect?",
not "does it matter?". The reporter compares the effect (and CI) against a **minimal clinically
important difference (MCID)** when one is supplied, and otherwise emits an `INFO` caveat that
statistical significance ≠ clinical importance (§6.7).

**Reporting-standard mapping (EQUATOR).** The captured design selects the guideline whose
checklist the methods text should follow; it is stored in `StudyDesign.reporting_standard`:

| Design | Guideline |
|---|---|
| Randomised controlled trial | **CONSORT** |
| Observational (cohort / case-control / cross-sectional, incl. ecological) | **STROBE** |
| Diagnostic-accuracy study | **STARD** |
| Prediction / prognostic model | **TRIPOD** |
| Systematic review / meta-analysis | **PRISMA** |

### 6.7 Healthcare caveat catalog (deterministic, appended by the reporter)

These fire in addition to the general caveats (§5.6.1). Each is keyed off the data form,
design, or an assumption result, so they are reproducible rather than LLM-invented.

| # | Severity | Trigger | Caveat |
|---|---|---|---|
| H1 | WARNING | Outcome is an areal/county rate (`GEOSPATIAL` strata) | **Ecological fallacy** — a relationship between area averages need not hold for individuals. |
| H2 | INFO | Aggregated areal units | **MAUP** — associations can change with the choice/scale of the areal units. |
| H3 | WARNING | Areal data with neighbours | **Spatial autocorrelation** understates standard errors (Moran's I diagnostic); consider spatial/cluster-robust inference. |
| H4 | INFO | `POISSON_REGRESSION` selected | Verify variance ≈ mean; if overdispersed, prefer negative binomial. |
| H5 | WARNING | PH assumption check VIOLATED (Cox/log-rank) | **Non-proportional hazards** — a single HR is misleading; consider time-varying effects or RMST. |
| H6 | INFO | Any survival analysis | Censoring assumed non-informative; verify dropout is unrelated to prognosis. |
| H7 | WARNING | RR/OR/HR/IRR significant but absolute effect small / NNT large | Statistically significant but small absolute benefit — judge against the MCID. |
| H8 | INFO | Diagnostic (PPV/NPV reported) | Predictive values depend on prevalence; state the operating prevalence. |
| H9 | WARNING | Clustering / repeated-measures key detected | Observations are not independent — naive tests understate SEs; a mixed/GEE model is indicated (v0.2.0). |

### Sources

Count/rate & overdispersion: Regression analyses of counts and rates (Poisson / overdispersed
Poisson / negative binomial); negative binomial for overdispersed count data. Survival:
Kaplan–Meier, log-rank, and Cox PH basic concepts (PMC10357905). Diagnostic accuracy: ROC/AUC,
sensitivity/specificity, likelihood ratios, DeLong comparison; STARD. Reporting guidelines:
CONSORT / STROBE / STARD / TRIPOD / PRISMA (EQUATOR network). Clinical significance: RR / OR /
HR / ARR / NNT and MCID. Spatial pitfalls: ecological fallacy, modifiable areal unit problem,
spatial autocorrelation (Moran's I). Clustered/longitudinal: mixed-effects models vs GEE. URLs
are listed in the implementation chat log and the README references.

### Effect size implementations

| Test | Effect size | Method |
|---|---|---|
| INDEPENDENT_T | Cohen's d | Pooled SD; CI via bootstrapping |
| WELCH_T | Cohen's d | Pooled SD; CI via bootstrapping |
| PAIRED_T | Cohen's d_z | Within-subject SD |
| MANN_WHITNEY_U | Rank-biserial r | `(2U)/(n₁n₂) − 1` |
| WILCOXON_SIGNED_RANK | Matched-pairs rank-biserial r | Cliff's delta variant |
| ONE_WAY_ANOVA | η² and ω² | SS decomposition |
| WELCH_ANOVA | η² and ω² | From Welch-adjusted SS; equal variances not assumed |
| KRUSKAL_WALLIS | ε² | `(H − k + 1) / (n − k)` |
| CHI_SQUARED | Cramér's V (R×C); + odds ratio if 2×2 | `√(χ² / (n · min(r−1, c−1)))` — note grouping of the denominator |
| FISHER_EXACT | Odds ratio if 2×2; Cramér's V if R×C | OR from the 2×2 table; V for the Fisher–Freeman–Halton case |
| PEARSON_CORRELATION | r (is its own effect size) | Fisher's z CI |
| SPEARMAN_CORRELATION | ρ (is its own effect size) | Bootstrap CI |
| POISSON_REGRESSION | Incidence-rate ratio (IRR) | exp(β); Wald CI on the log scale, back-transformed |
| NEGATIVE_BINOMIAL_REGRESSION | Incidence-rate ratio (IRR) | exp(β) with dispersion parameter; CI back-transformed from log scale |
| LOG_RANK | Hazard ratio (from the test) + median-survival difference | HR via the Mantel–Haenszel estimate; KM medians per group |
| COX_REGRESSION | Hazard ratio (HR) | exp(β); CI back-transformed from the log scale |
| ROC_AUC | Area under the ROC curve (AUC) | DeLong CI; DeLong test to compare two AUCs |
| BET / MAXBET / BEAST | BET symmetry statistic + depth | No standardised effect size; report maximum symmetry statistic, depth at which significance was found, and normalised mutual information as a supplementary measure |

### BET (Binary Expansion Testing) — methodology note

BET was developed by Kai Zhang (UNC Chapel Hill) in *"BET on Independence,"* **Journal of the American Statistical Association 114(528), 1620–1637 (2019), DOI [10.1080/01621459.2018.1537921](https://doi.org/10.1080/01621459.2018.1537921)**. Its application to pairwise nonlinear-dependence exploratory analysis — the basis for the EDA screen in §5.1a — is Xiang, Zhang, Liu, Hoadley, Perou, Zhang & Marron (2023), *"Pairwise Nonlinear Dependence Analysis of Genomic Data,"* The Annals of Applied Statistics 17(4), DOI [10.1214/23-AOAS1745](https://doi.org/10.1214/23-AOAS1745) (preprint arXiv:2202.09880). BET is the appropriate choice when the user suspects any form of statistical dependence between two continuous variables that is not necessarily linear or monotone.

**Two implementations in this codebase.** (1) A pure-Python engine (`src/hta/bet_screen.py`, §5.1a) powers the profiler's EDA screen (depth 2) and the two-stage confirmatory test (`maxbet_twostage`, `d_max = 4` per Zhang 2019 §4.5) — no R/numpy needed. (2) The R `BET` bridge described below is the executor path (Step 6), used for the confirmatory run with the normalised-MI supplement; its `max.depth` default differs because it is the R package's own convention.

**Algorithm:**
1. Rank-transform both variables to [0, 1] via the empirical CDF (producing the empirical copula).
2. Binary-expand each observation to depth *d* — i.e., extract the first *d* bits of its binary representation.
3. Compute cross-product symmetry statistics for all binary digit pairs via the Hadamard transform. These are complete sufficient statistics for any form of dependence in the copula.
4. **Max BET** is the test: take the maximum absolute symmetry statistic over all cross interactions (and, in the two-stage form, over depths *d* = 1..d_max), then Bonferroni-adjust across those cross interactions and depths. Each symmetry statistic's null is binomial (known margins) or hypergeometric (unknown margins, empirical copula), with the large-*n* normal approximation. (The aggregate sum-of-squares of all symmetry statistics recovers the classical χ² statistic, but Max BET deliberately uses the *maximum* — it is more powerful against sparse, few-interaction dependence and yields the interpretable region.)

**Variants:**

| Enum value | R function | When to use |
|---|---|---|
| `BET` | `BET(x, y, depth=d)` | Fixed depth; rarely preferred |
| `MAXBET` | `MaxBET(x, y, max.depth=8)` | **Default.** Adapts depth automatically; recommended for most analyses |
| `BEAST` | `BEAST(x, y)` | Data-adaptive weights; most robust when dependence structure is entirely unknown |

**Selection trigger:** `StudyDesign.notes` contains `"nonlinear"` or `"complex"` (populated by DesignDialogue rule 7).

**Assumptions:**
- Both variables must be continuous (no ties; discrete data requires continuity correction).
- No normality assumption.
- No monotonicity assumption.
- Default `max.depth = 8` is appropriate for N ≥ 50; for very small samples (N < 30) use `max.depth = 4`.

**Assumption checks to record in `AssumptionCheck`:**

| Check | Method | Flag as |
|---|---|---|
| Continuity | Both variables have no ties | `VIOLATED` if ties > 5% |
| Minimum sample size | N ≥ 20 per variable | `VIOLATED` if not met |
| Depth adequacy | `max.depth` ≤ ⌊log₂(N)⌋ | `WARNING` if exceeded |

**Implementation:** Executed via **rpy2** bridge to the R `BET` package. See §12 for installation. The executor calls `MaxBET` by default; `BEAST` is used when the selector flag `use_beast=True` is set (reserved for a future user override).

```python
import rpy2.robjects as ro
from rpy2.robjects.packages import importr

_BET = importr("BET")

def run_maxbet(x: list[float], y: list[float], max_depth: int = 8) -> dict[str, float]:
    result = _BET.MaxBET(ro.FloatVector(x), ro.FloatVector(y), max_depth)
    return {
        "statistic": float(result.rx2("statistic")[0]),
        "p_value":   float(result.rx2("p.value")[0]),
        "depth":     float(result.rx2("depth")[0]),
    }
```

**Future work:** A pure-numpy reimplementation would remove the R dependency and improve portability. The Hadamard-transform approach maps directly to numpy operations and is feasible for v0.2.0.

---

## 7. GPT-5.4 / Azure OpenAI Integration

GPT-5.4 (served via the UNC Azure OpenAI endpoint) is used in exactly two modules. All other logic is fully deterministic. The OpenAI Python SDK (`openai>=1.0.0`) is used as the client.

### 7.1 Credentials and configuration

Credentials are loaded at import time from a `.env` file at the **project root** (i.e., the same directory as `pyproject.toml`). This file is listed in `.gitignore` and never committed.

`src/hta/config.py`:

```python
from pathlib import Path
from dotenv import load_dotenv

# Two levels up from src/hta/config.py → project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_BASE_URL   = os.getenv("AZURE_OPENAI_BASE_URL", "https://azureaiapi.cloud.unc.edu/openai/v1/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")
MAX_TOKENS              = 28192
```

No credentials are hardcoded in the repository. The `.env` file is the single source of truth for this project.

### 7.2 DesignDialogue protocol

The system prompt given to GPT-5.4 enforces the following dialogue rules:

1. Always ask about observational vs. experimental design first.
2. Always ask about independence of observations.
3. If there are multiple variables, always ask which could be confounders.
4. Ask about matching or repeated measures if the user mentions "before/after" or "matched".
5. Never ask more than 3 questions per turn.
6. Stop when `StudyDesign` can be fully populated — signal completion by calling the `capture_study_design` tool.

**Tool use:** The dialogue module defines a `capture_study_design` function tool in the OpenAI tool-calling format. When GPT-5.4 calls this tool, the module extracts the structured `StudyDesign` from the tool arguments and terminates the loop.

Rule 7 (added for BET support): When the user's hypothesis involves association or dependence between two continuous variables, ask: *"Do you expect the relationship to be linear, monotone, or potentially nonlinear/complex?"* The answer is stored in `StudyDesign.notes` and used by the selector to choose between Pearson, Spearman, and BET (see §6). The BET EDA screen (§5.1a) pre-fills the likely answer from the data, so the question is framed as a confirmation.

Rule 8 (added for the EDA subgroup step, Xiang et al. 2023, *Ann. Appl. Stat.* 17(4), DOI 10.1214/23-AOAS1745): When the BET screen flags the
outcome/predictor pair as **nonlinear** — especially a mixture-type form (CHECKERBOARD,
SINUSOIDAL/"W"-bimodal, or PARABOLIC), or a `nonlinear_only` pair — present that finding and
ask: *"This pattern is often produced by a mix of subgroups. Are there known subgroups or
subtypes in your data (e.g. disease subtype, sex, site) that might drive it?"* Named subgroups
are stored in `StudyDesign.subgroup_variables`; the selector then runs the analysis **within
each subgroup** (contextual analysis) and the report compares the strata. This is how the
paper explains TCGA nonlinear gene dependence by breast-cancer subtype, and it gives the agent
a concrete effect-modification / heterogeneity step.

### 7.3 Reporter text generation

Two GPT-5.4 API calls are made in the reporter:

| Call | Output field | Audience |
|---|---|---|
| Summarise result in plain language | `plain_language_summary` (2–3 sentences) | Non-statistician readers |
| Write a methods paragraph | `methods_text` | Research paper methods section |

Both calls are skipped in `dry_run=True` mode; stub text is returned instead.

---

## 8. Development Standards

These constraints apply to every step without exception.

| Standard | Detail |
|---|---|
| **Type annotations** | All functions fully typed; `mypy --strict` must pass |
| **Pydantic v2** | All shared data structures use `BaseModel`; no raw dicts between modules |
| **Docstrings** | Every public function has a docstring explaining intent, not implementation |
| **Dry-run parameter** | Any external API call accepts `dry_run: bool = True` |
| **No hardcoded secrets** | Credentials loaded from `.env` at the project root via `src/hta/config.py`; `.env` is git-ignored and never committed |
| **Shared-model boundary** | Modules exchange only the shared Pydantic models; `agent.py` wires them in a linear chain (no event bus in v0.1.0) |
| **Tests gate progress** | Step N+1 does not start until Step N tests pass |
| **Coverage target** | ≥ 80% line coverage across `src/hta/` |
| **Linting** | `ruff check src/` must pass with no errors |

---

## 9. Completed Work

### Step 1 — Repository scaffold and shared data models ✅

**Date completed:** 2026-04-29

**What was built:**

| File | Contents |
|---|---|
| `pyproject.toml` | Project config, all dependencies, mypy/ruff/pytest settings |
| `.gitignore` | Python + venv + macOS ignores |
| `.env.example` | Environment variable template |
| `README.md` | Install, test, and run instructions |
| `src/hta/__init__.py` | Package root with version |
| `src/hta/models/data.py` | `VariableType`, `DistributionStats`, `NormalityTest`, `Variable`, `DataProfile` |
| `src/hta/models/design.py` | `StudyDesignType`, `MeasurementType`, `VariableRole`, `Confounder`, `StudyDesign`, `CausalGraph` |
| `src/hta/models/test.py` | `StatisticalTest` (14 members at Step 1; 24 now — see §4.3), `AssumptionStatus`, `AssumptionCheck`, `EffectSize`, `TestResult` |
| `src/hta/models/report.py` | `CaveatSeverity`, `Caveat`, `PlotSpec`, `Report` |
| `src/hta/models/__init__.py` | Re-exports all models |
| `tests/conftest.py` | Shared fixtures for all model types |
| `tests/test_models.py` | 68 tests across 4 categories (see below) |

**Test results:**

```
68 passed, 0 failed
Coverage: 100% on all model files (154 statements)
```

**Test categories:**
- *Enum completeness* (9 tests): all enum members present and counted correctly
- *Valid construction* (36 tests): every model constructed with realistic values including nested models up to `Report`
- *Validation rejection* (9 tests): `pytest.raises(ValidationError)` for wrong types and missing required fields
- *JSON round-trip* (14 tests): `model_dump_json()` → `model_validate_json()` preserves all fields for every model

**Key design decisions made in this step:**
- `NormalityTest.is_normal` is a stored field (not computed) — the profiler sets it; the threshold (p > 0.05) is applied there, not in the model
- `TestResult.confidence_interval` is `tuple[float, float]` — serialises as a JSON array but Pydantic v2 coerces back to tuple on deserialisation
- `CausalGraph.edges` is `list[tuple[str, str]]` — same tuple serialisation behaviour
- `report.py` imports from sibling model files (within `models/`) — this is the only cross-file import in the entire codebase and is intentional

---

### Steps 2–8 — Pipeline, CLI, and web integration ✅ (consolidated)

**What was built:** the gated Step-2…8 plan was implemented as a single consolidated engine
rather than module-by-module behind an event bus. `src/hta/modules/` now contains
`profiler.py`, `selector.py`, `executor.py`, and `reporter.py` (each returning the shared
Pydantic models); `agent.py` orchestrates them in a linear chain; and `cli.py` exposes
`hta run`. The web backend and the zero-dependency playground both delegate to this engine.

**Deltas from the original plan:**
- **No event bus** (Step 2) — the linear pipeline is wired directly by `agent.py` (§2, §10b #9).
- **Dialogue stage not yet wired into the orchestrator** (Step 4) — it runs in the web layer
  (`web/backend/api/dialogue.py`) and `agent.py` uses a default observational design. The
  **causal stage is built** (`modules/causal.py`): elicited confounders now produce an
  adjusted estimate (partial correlation for associations, ANCOVA for continuous group
  comparisons) and accurate per-confounder caveats — they change the reported number.
- **Executor coverage:** the two-sample t-tests, Mann–Whitney, paired t / Wilcoxon, one-way and
  Welch ANOVA, Kruskal–Wallis, χ²/Fisher/McNemar, Pearson/Spearman, the pure-Python MaxBET, and
  Poisson / negative-binomial. Survival (log-rank/Cox), ROC/AUC, and the reserved regressions
  are in the enum but return an UNTESTABLE result (not yet wired). MaxBET uses the pure-Python
  `bet_screen` engine, not the rpy2 → R bridge originally specified.
- **Sensitivity power** (§5.5, two-sample t) and **post-hoc localisation** (§6.3 —
  Games–Howell / Tukey / Dunn, via pingouin + scikit-posthocs) are emitted; the χ²/Kruskal
  effect sizes now carry real bootstrap CIs and the R×C Fisher test uses a Freeman–Halton
  permutation. The **H1–H9 healthcare caveat catalog** (§6.7) and the survival/diagnostic
  executor branches are still not wired.

**Test results:** 164 passing; **90% line coverage** on `src/hta`; `ruff check src/` and
`mypy --strict src/hta` both clean. New suites: `test_{profiler,selector,executor,reporter,
agent,cli}.py`, alongside the existing `test_{models,bet_screen,examples,playground}.py`.

---

## 10. Planned Work

> **Status (v0.1.0):** Steps 2–8 are implemented in consolidated form — see §9. The per-step
> specifications below are retained as the design of record. The **event bus (Step 2)** was
> intentionally dropped; the **dialogue/causal stages (Step 4)** and the Step-8 review
> deliverables (`STATISTICIAN_REVIEW.md`, `BENCHMARK_CASES.md`) are the main outstanding items.
> Read the step text below as the spec, not a live to-do list, except where §9 flags something
> still pending.

Steps are executed in order. Each step is blocked until the previous step's tests pass and are confirmed complete.

### Step 2 — Event bus

**Goal:** Implement `src/hta/bus.py` with `subscribe`, `publish`, `unsubscribe`.

Key requirements:
- Synchronous pub/sub; handlers called in subscription order
- Exception in one handler must not stop remaining handlers (log and continue)
- Define all 6 canonical event name constants (`EVENT_DATA_PROFILED`, etc.)

**Deliverable:** `tests/test_bus.py` — subscription, multiple handlers, unsubscription, exception isolation.

---

### Step 3 — Data profiler

**Goal:** `src/hta/modules/profiler.py` → `DataProfile`

Key requirements:
- Accept DataFrame, list of dicts, CSV string, or dict of lists
- Infer variable types by the healthcare-aware rules in §5.1 / §6.5
- Normality *severity* — graded `NONE`/`MILD`/`STRONG` (§6.1), not a binary gate: Shapiro–Wilk corroborates at N ≤ 2000; above N = 2000 no formal test is run (the KS-vs-estimated-parameters path was dropped) and severity comes from skew/kurtosis magnitude alone
- Data quality notes: missingness >5%, constant variables, outliers |Z| > 3.5

**Deliverable:** `tests/test_profiler.py` — normal/skewed distributions, categorical detection, missing data, grouped profiling.

---

### Step 4 — Study design dialogue and causal module

**Goal:** `src/hta/modules/dialogue.py` and `src/hta/modules/causal.py`

Key requirements:
- Dialogue: multi-turn GPT-5.4 (Azure OpenAI) interaction; tool-call termination via `capture_study_design`
- Causal: DAG construction from confounder list; adjustment set identification
- Both modules: `dry_run=True` returns pre-defined output without API calls

**Deliverable:** `tests/test_dialogue.py`, `tests/test_causal.py`.

---

### Step 5 — Test selector

**Goal:** `src/hta/modules/selector.py` — purely deterministic decision tree

Key requirements:
- Implements the full decision tree in §6 exactly
- `get_selection_rationale(test, profile, design) -> str`
- Subscribes to `EVENT_DESIGN_CAPTURED`; publishes `EVENT_TEST_SELECTED`

**Deliverable:** `tests/test_selector.py` — one test per test type; edge cases for borderline normality and unequal group sizes; three BET-path cases (linear → Pearson, monotone → Spearman, nonlinear → MaxBET).

> **Statistician review checkpoint:** Statistician A will validate the decision tree at this step, including the BET selection trigger.

---

### Step 6 — Test executor

**Goal:** `src/hta/modules/executor.py` — runs the selected test and returns `TestResult`

Key requirements:
- Implements every selectable test + effect-size combination in §6 — no longer just the original 11: now also `WELCH_ANOVA`, the count (`POISSON_REGRESSION` / `NEGATIVE_BINOMIAL_REGRESSION`), survival (`LOG_RANK` / `COX_REGRESSION`), and diagnostic (`ROC_AUC`) families, plus the BET `MAXBET` / `BEAST` bridge
- Implements BET/MaxBET/BEAST via rpy2 bridge (see §6 BET methodology note); `rpy2` added as a runtime dependency in `pyproject.toml`
- Assumption checks before the main test (normality, variance homogeneity, sample size adequacy; continuity and depth-adequacy checks for BET)
- Uses scipy, pingouin, and/or statsmodels for non-BET tests

**Deliverable:** `tests/test_executor.py` — known datasets verified against reference outputs (R or textbook); BET tests cross-validated against direct R `BET::MaxBET` output.

---

### Step 7 — Reporter

**Goal:** `src/hta/modules/reporter.py` — assembles `Report` from upstream outputs

Key requirements:
- All deterministic caveat rules implemented — the 6 general rules (§5.6.1) plus the healthcare caveat catalog H1–H9 (§6.7)
- Generates `PlotSpec` objects for distribution, box plots, QQ-plots, scatter
- GPT-5.4 (Azure OpenAI) calls for `plain_language_summary` and `methods_text`

**Deliverable:** `tests/test_reporter.py` — all 6 caveat rules, dry-run report assembly.

---

### Step 8 — Agent orchestration, CLI, and examples

**Goal:** `src/hta/agent.py`, `src/hta/cli.py`, and three example scripts

Key requirements:
- `HypothesisTestingAgent.run()` executes the full pipeline
- CLI via Typer: `hta run --data ... --hypothesis ... --group ... --outcome ...`
- Rich terminal output: panel for test result, colour-coded p-value, caveat table
- Three example scripts (two-group comparison, categorical association, paired before/after)

**Deliverable:** `tests/test_agent.py` — end-to-end dry-run returns a fully populated `Report`.

---

### Post-implementation: Statistician review package

Once all 8 steps are complete, prepare for statistician review:

1. **`STATISTICIAN_REVIEW.md`** — every statistical decision point in the code, with file path and line number
2. **`BENCHMARK_CASES.md`** — 20 test cases (input → expected test, p-value, effect size interpretation)
3. **`examples/OUTPUT_EXAMPLES.md`** — terminal output of all three example scripts

Tag the commit `v0.1.0-statistician-review` and distribute to co-investigators.

---

## 10b. Design Review Notes (2026-05-29)

These are open methodological questions raised during design review. They are flagged here (rather than silently changed) because several touch decisions the statistician co-investigators should rule on before Step 5/6 implementation. They are ordered roughly by severity.

### Correctness issues to resolve before implementation

1. **Normality-test-gated test selection is fragile in both directions.** `NormalityTest.is_normal = (p > 0.05)` is used as a hard switch (e.g. `if normal → INDEPENDENT_T else MANN_WHITNEY_U`). Significance tests for normality have low power at small N (so non-normal data passes) and reject trivial, harmless departures at large N (so usable data fails). The "test the assumption, then pick the test" pattern also inflates the overall Type I error rate because the second test is conditioned on the first. Recommendation: treat normality as one input among several (sample size, magnitude of skew/kurtosis, robustness of the candidate test) rather than a binary gate, and/or prefer rank-based or robust methods by default. Statistician A should sign off on the policy. **→ Resolved in §6.1 (`prefer_rank_based`); the NONE/MILD/STRONG thresholds and `LARGE_N` default await Statistician A sign-off.**

2. **KS branch for N > 2000 is statistically invalid as specified.** A one-sample Kolmogorov–Smirnov test comparing data to a normal distribution whose mean and SD are *estimated from that same data* does not have the standard KS null distribution — it requires the Lilliefors correction. As written (§5.1, §10 Step 3), the N > 2000 path would produce anti-conservative p-values. Also, at N > 2000 essentially any real dataset will be flagged non-normal, making the test nearly useless for selection. Recommendation: drop the formal test at large N in favor of effect-magnitude heuristics, or use Lilliefors/Anderson–Darling explicitly. **→ Resolved in §6.1: no formal normality test is run above N = 2 000; severity there comes from skew/kurtosis magnitude.**

3. **Welch vs. Student via a variance pretest (Levene) repeats the same pretest problem.** Current §6 logic chooses Student's t when variances are "equal." The modern recommendation is to use Welch's t unconditionally for between-subjects continuous comparisons — it is nearly as powerful under equal variances and far safer under unequal variances, with no pretest. Recommendation: consider making `WELCH_T` the default and reserving `INDEPENDENT_T` for an explicit user override. **→ Resolved in §6.1/§6.2: `WELCH_T` (and `WELCH_ANOVA` for 3+ groups) is the default with no variance pretest; the equal-variance forms require `force_student`.**

4. **"Report power when computable" risks reporting observed (post-hoc) power.** Observed power is a deterministic monotone function of the p-value and adds no information; APA and most methodologists discourage it. Recommendation: report *a priori* or *sensitivity* power (minimum detectable effect at the observed N) instead, and never compute power from the observed effect size. The `WARNING: power < 0.80` caveat (§5.6.1) should be re-specified accordingly. **→ Resolved in §5.5 / §5.6.1: only *sensitivity power* (minimum detectable effect at the observed N, α = 0.05, power = 0.80) is reported; observed power is never computed, and the underpowered caveat now triggers when the minimum detectable effect > 0.5 (large-effect-only).**

### Scope / consistency gaps

5. **`LINEAR_REGRESSION` and `LOGISTIC_REGRESSION` are in the `StatisticalTest` enum (14 members) but absent from the decision tree (§6) and the effect-size table (which lists 11).** Either remove them from the enum for v0.1.0 or add their selection rules, assumption checks, and effect sizes. As-is, the selector can never return them, which will confuse reviewers. **→ Partially addressed: both are now explicitly commented as reserved/non-selectable in `test.py`, and the BET-family members the tree actually returns (`WELCH_ANOVA`, `MAXBET`, `BEAST`) have been added so the enum matches §6. Final remove-vs-implement call for the regressions still pending.**

6. **`FISHER_EXACT` / odds-ratio effect size is only defined for 2×2 tables, but the tree branches on "two categorical variables" generically.** For R×C tables, Fisher's exact generalizes but the odds ratio does not; Cramér's V is the appropriate effect size. The selector and executor need an explicit 2×2-vs-R×C distinction. **→ Resolved in §6.4: the executor branches on `table_shape` (2×2 → odds ratio; R×C → Cramér's V via Fisher–Freeman–Halton).**

7. **ANOVA / Kruskal–Wallis omnibus results need a post-hoc and correction policy.** Multiple comparisons are currently only an `INFO` caveat. For 3+ groups the report should specify the planned follow-up (e.g. Tukey HSD, Dunn's test) and the family-wise or FDR correction, or explicitly state that none is performed and why. **→ Resolved in §6.3: Games–Howell (Welch ANOVA) / Tukey HSD (pooled ANOVA) / Dunn (Kruskal–Wallis), Holm-adjusted, recorded on the `TestResult`.**

### Architecture / configuration

8. **The secrets path coupling has been resolved.** `config.py` now loads from `.env` at the project root (§7.1, §12). The previous cross-project dependency on `~/.config/trading-agents/secrets.env` has been removed. ✅

9. **Event bus may be heavier than the linear pipeline needs (low priority).** The pipeline is strictly linear (profile → design → select → execute → report). Synchronous pub/sub is defensible for swappability/mocking, but reviewers may ask why a direct call chain wasn't used. Worth a one-line justification in §2 or §3 so the choice reads as deliberate, not incidental.

### Minor

10. `MAX_TOKENS = 28192` (§7.1) is an unusual value — confirm it is intentional and within the deployment's limit.
11. Header reads "Step 1 of 8 complete," but `config.py` is marked "added ✅" outside the numbered steps. Fold config into a numbered step (or note it as Step 0) so the step ledger stays authoritative.

---

## 11. Definition of Done

The project is ready for statistician review when all boxes below are checked:

- [ ] All 8 steps complete with passing tests
- [ ] `pytest --cov=src/hta` shows ≥ 80% coverage
- [ ] `mypy src/hta` passes with no errors
- [ ] `ruff check src/` passes with no errors
- [ ] All three example scripts run successfully in dry-run mode
- [ ] `STATISTICIAN_REVIEW.md` documents every statistical decision
- [ ] `BENCHMARK_CASES.md` contains 20 validated test cases
- [ ] `README.md` is up to date

---

## 12. Environment Setup

### Prerequisites

Create a `.env` file at the project root (same directory as `pyproject.toml`) with:

```
AZURE_OPENAI_API_KEY=<your key>
AZURE_OPENAI_BASE_URL=https://azureaiapi.cloud.unc.edu/openai/v1/
AZURE_OPENAI_DEPLOYMENT=gpt-5.4
```

`.env` is listed in `.gitignore` — it will never be committed. `src/hta/config.py` loads it automatically at import time.

### R and BET package (required for BET/MaxBET/BEAST tests)

The BET executor uses rpy2 to call the R `BET` package. R must be installed separately from the Python environment.

```bash
# 1. Install R (macOS — via Homebrew)
brew install r

# 2. Install the BET package from within R
R -e "install.packages('BET', repos='https://cloud.r-project.org')"

# 3. Install rpy2 into the Python environment (added to pyproject.toml [project.dependencies])
pip install rpy2
```

To verify the bridge works:

```bash
python3 -c "from rpy2.robjects.packages import importr; importr('BET'); print('BET OK')"
```

If R is not installed, BET tests will be skipped (`pytest.importorskip("rpy2")`); all other tests continue to pass.

### First-time setup

```bash
# Option A: conda (recommended — matches development environment)
conda create -n hta python=3.11
conda activate hta
pip install -e ".[dev]"

# Option B: venv
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Running the test suite

```bash
pytest                           # all tests with coverage
pytest tests/test_models.py -v   # Step 1 tests only
pytest --cov=src/hta --cov-report=html  # HTML coverage report
```

### Code quality checks

```bash
ruff check src/       # linting
mypy src/hta          # type checking
```

### CLI (dry-run, no API key required)

```bash
hta run --dry-run
hta run --data data.csv --hypothesis "Group A < Group B" --group group --outcome score
```

---

*This document is updated at the end of each completed step. Last updated 2026-06-09: (Phase 2) post-hoc localisation (Games–Howell / Tukey / Dunn via pingouin + scikit-posthocs), real bootstrap CIs for the χ²/Kruskal effect sizes, an R×C Fisher (Freeman–Halton) permutation test, and a true Welch ANOVA replacing the mislabelled Alexander–Govern; (Phase 3) the causal stage — `modules/causal.py` builds the adjustment set and the executor produces a confounder-adjusted estimate (partial correlation / ANCOVA), so elicited confounders now change the reported result. Earlier 2026-06-08: implemented the Step-2…8 pipeline as a consolidated, bus-free engine in `src/hta/modules/` (profiler / selector / executor / reporter) with `agent.py` orchestrator and `cli.py` (`hta run`); the web backend and the zero-dependency playground now delegate to this single engine; added engine test suites (164 tests, 90% coverage on `src/hta`; `ruff check src/` and `mypy --strict src/hta` clean); §2/§3/§8–§10 updated to drop the event bus and reflect the built pipeline. Earlier 2026-06-04: (1) reconciled the test-selector decision tree to the stated policy — Welch's t / Welch's ANOVA as unconditional defaults with no Levene pretest, normality as a graded NONE/MILD/STRONG signal, no formal normality test above N=2000 (§6.1–§6.4); (2) general data-form coverage specialized for healthcare — `VariableType` 4→9 (COUNT, TIME_TO_EVENT, DATETIME, GEOSPATIAL, IDENTIFIER), `StatisticalTest` 17→24 (Poisson/negative-binomial, log-rank/Cox, ROC-AUC selectable; mixed-model/GEE reserved), `StudyDesign.reporting_standard`, healthcare branches and caveat catalog (§6.5–§6.7); (3) BET pairwise nonlinear-dependence EDA screen as the profiler's discovery stage (§5.1a) with `DependenceForm`/`DependenceFinding` models, citing Xiang et al. (2023), Ann. Appl. Stat. 17(4), DOI 10.1214/23-AOAS1745; (4) synthetic NC overdose/clinic-access demo dataset and clinic-density heatmap renderer. Earlier 2026-06-01: BET/MaxBET/BEAST integration and §4.3 enum count 14→17. Earlier 2026-05-29: §10b Design Review Notes and Cramér's V fix.*
