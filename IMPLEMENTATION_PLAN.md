# HTA Implementation Plan

**Status:** Ready to implement  
**Based on:** TECHNICAL_REPORT.md v0.1.0-dev (last updated 2026-06-01)  
**Prerequisite complete:** Step 1 — models + tests (68 passing)

Each step is gated: do not start Step N+1 until Step N tests pass and the gate check below it is satisfied.

---

## Pre-flight: Open design decisions resolved

Before coding begins, these open questions from §10b of the technical report are resolved here so implementers don't re-litigate them mid-step.

| # | Issue | Resolution |
|---|---|---|
| 1 | Normality as hard binary gate | **Treat as soft signal.** Selector uses normality *plus* skewness magnitude and sample size. See Step 5 selector logic. |
| 2 | KS test invalid at N > 2000 | **Use Anderson–Darling** (scipy `anderson`) for N > 2000 instead of KS. Threshold: use the 5% critical value from the returned table. |
| 3 | Welch vs Student via Levene pretest | **Welch is the default** for all between-subjects continuous comparisons. `INDEPENDENT_T` (Student's) is reserved for explicit user override and will not be returned by the selector in v0.1.0. |
| 4 | Observed (post-hoc) power | **Never compute observed power.** Report *sensitivity power* only: the minimum detectable effect at the observed N and α=0.05, using `statsmodels.stats.power`. The `power < 0.80` caveat triggers when MDE > 0.5 (large effect only). |
| 5 | LINEAR/LOGISTIC_REGRESSION in enum but not in tree | **Keep in enum** (removing would break JSON round-trips). Selector never returns them in v0.1.0. Executor raises `NotImplementedError` if called. Document as "planned for v0.2.0". |
| 6 | FISHER_EXACT / odds ratio for R×C tables | **Add 2×2 vs R×C split.** Selector checks contingency table shape; R×C → CHI_SQUARED with Cramér's V; 2×2 only → FISHER_EXACT with odds ratio. |
| 7 | ANOVA / Kruskal post-hoc policy | **Always run post-hoc.** ANOVA → Tukey HSD (pingouin); Kruskal–Wallis → Dunn's test with Holm correction (scikit-posthocs). Results stored in `TestResult.notes`. |
| 8 | Secrets path coupling | **Resolved.** `config.py` loads from `.env` at the project root. No external path dependency. |

---

## Step 1b — Model updates for BET

**Goal:** Extend `StatisticalTest` enum with three BET variants; update tests.  
**Blocked by:** nothing (Step 1 is done)  
**Files touched:** `src/hta/models/test.py`, `tests/test_models.py`, `tests/conftest.py`

### Tasks

- [ ] **`src/hta/models/test.py`** — Add three members after `SPEARMAN_CORRELATION`:
  ```python
  BET    = "BET"     # single-depth Binary Expansion Test (rarely used directly)
  MAXBET = "MAXBET"  # depth-adaptive MaxBET — default for nonlinear independence testing
  BEAST  = "BEAST"   # adaptive-weighted BEAST — most robust, unknown dependence structure
  ```

- [ ] **`tests/test_models.py`** — Update the enum-count assertion from 14 → 17. Add three test cases:
  - `TestResult` constructed with `test_used=StatisticalTest.MAXBET`, `effect_size.measure_name="BET symmetry statistic"`, `degrees_of_freedom=None`.
  - JSON round-trip for the MAXBET `TestResult`.
  - Enum membership: `assert StatisticalTest.BEAST in StatisticalTest`.

- [ ] **`tests/conftest.py`** — Add `bet_effect_size` and `bet_test_result` fixtures to mirror the existing `effect_size` / `test_result` fixtures but with BET-specific field values.

**Gate:** `pytest tests/test_models.py` → 71+ passing, 0 failing.

---

## Step 2 — Event bus

**Goal:** `src/hta/bus.py` — synchronous pub/sub with exception isolation.  
**Files created:** `src/hta/bus.py`, `tests/test_bus.py`

### `bus.py` — public API

```python
EVENT_DATA_PROFILED  = "data.profiled"
EVENT_DESIGN_CAPTURED = "design.captured"
EVENT_GRAPH_BUILT    = "causal.graph_built"
EVENT_TEST_SELECTED  = "test.selected"
EVENT_TEST_EXECUTED  = "test.executed"
EVENT_REPORT_READY   = "report.ready"

class EventBus:
    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None: ...
    def unsubscribe(self, event: str, handler: Callable[[Any], None]) -> None: ...
    def publish(self, event: str, payload: Any) -> None: ...

bus: EventBus  # module-level singleton
```

### Implementation rules

- `publish` calls all registered handlers for `event` in subscription order.
- If a handler raises, log the exception (`logging.exception`) and continue to the next handler — do not reraise.
- `unsubscribe` is a no-op if the handler is not registered (no exception).
- The module-level `bus` is a plain `EventBus()` instance — no lazy init, no locks (single-threaded).

### `tests/test_bus.py` — required cases

| Test | Description |
|---|---|
| `test_subscribe_and_publish` | Handler called once with correct payload |
| `test_multiple_handlers` | Two handlers both called in order |
| `test_unsubscribe` | Handler not called after unsubscribe |
| `test_exception_isolation` | Bad handler does not prevent second handler from running |
| `test_unknown_event_publish` | Publishing to event with no subscribers is a no-op |
| `test_event_constants` | All 6 `EVENT_*` constants are non-empty strings |

**Gate:** `pytest tests/test_bus.py` → 6 passing, 0 failing.

---

## Step 3 — Data profiler

**Goal:** `src/hta/modules/profiler.py` → produces and publishes `DataProfile`.  
**Files created:** `src/hta/modules/profiler.py`, `tests/test_profiler.py`

### `profiler.py` — public API

```python
class DataProfiler:
    def __init__(self, bus: EventBus) -> None: ...
    def profile(
        self,
        data: pd.DataFrame | list[dict] | str | dict[str, list],
        outcome_variable: str | None = None,
        group_variable: str | None = None,
    ) -> DataProfile: ...
```

`profile()` publishes `EVENT_DATA_PROFILED` and returns the `DataProfile`.

### Variable type inference rules (in priority order)

1. Non-numeric dtype or ≤ 2 unique values that are strings → `BINARY`
2. Exactly 2 unique numeric values → `BINARY`
3. Non-numeric with > 2 unique values → `CATEGORICAL`
4. Numeric, ≤ 10 unique integer values → `ORDINAL`
5. Everything else → `CONTINUOUS`

### Normality testing

| N | Test | Implementation |
|---|---|---|
| ≤ 2000 | Shapiro–Wilk | `scipy.stats.shapiro` |
| > 2000 | Anderson–Darling | `scipy.stats.anderson`; `is_normal = statistic < cv[2]` (5% critical value, index 2) |

`NormalityTest.name` = `"Shapiro-Wilk"` or `"Anderson-Darling"` respectively.  
Only computed for `CONTINUOUS` and `ORDINAL` variables.

### Data quality notes (appended to `DataProfile.notes`)

| Condition | Note string |
|---|---|
| Missing > 5% for any variable | `"{name}: {pct:.1f}% missing values"` |
| Variable is constant (std == 0) | `"{name}: constant variable (zero variance)"` |
| Any `\|Z\| > 3.5` | `"{name}: {k} outlier(s) detected (\|Z\| > 3.5)"` |

### `tests/test_profiler.py` — required cases

| Test | Description |
|---|---|
| `test_normal_continuous` | Known-normal data → `is_normal=True`, correct stats |
| `test_skewed_continuous` | Log-normal data → `is_normal=False` |
| `test_binary_detection` | Two-value column → `BINARY` |
| `test_categorical_detection` | String column → `CATEGORICAL` |
| `test_ordinal_detection` | Integer 1–5 column → `ORDINAL` |
| `test_missing_data_note` | >5% NaN → note added |
| `test_constant_variable_note` | All-same column → note added |
| `test_outlier_note` | Z > 3.5 value → note added |
| `test_group_level_stats` | Group variable → per-group normality |
| `test_large_n_anderson_darling` | N=2500 → Anderson–Darling used |
| `test_input_formats` | list-of-dicts and dict-of-lists accepted |
| `test_publishes_event` | `EVENT_DATA_PROFILED` fired with correct payload |
| `test_csv_string_input` | CSV string parsed correctly |

**Gate:** `pytest tests/test_profiler.py` → 13 passing, 0 failing.

---

## Step 4 — Study design dialogue and causal module

**Goal:** `dialogue.py` (GPT-5.4 multi-turn) + `causal.py` (DAG + adjustment set).  
**Files created:** `src/hta/modules/dialogue.py`, `src/hta/modules/causal.py`, `tests/test_dialogue.py`, `tests/test_causal.py`

### `dialogue.py` — public API

```python
class DesignDialogue:
    def __init__(self, bus: EventBus, dry_run: bool = True) -> None: ...
    def run(self, profile: DataProfile, hypothesis: str) -> StudyDesign: ...
```

- `dry_run=True`: returns a hard-coded `StudyDesign` without any API call.
- `dry_run=False`: multi-turn GPT-5.4 loop; terminates when `capture_study_design` tool is called.
- Implements all 7 dialogue rules from §7.2 (including Rule 7: relationship-form question).
- `StudyDesign.notes` must contain `"nonlinear"` or `"complex"` when the user answers that way to Rule 7.

#### GPT-5.4 tool definition

```python
CAPTURE_TOOL = {
    "type": "function",
    "function": {
        "name": "capture_study_design",
        "description": "Record the fully-elicited study design.",
        "parameters": {
            "type": "object",
            "properties": {
                "design_type": {"type": "string", "enum": ["EXPERIMENTAL", "OBSERVATIONAL", "QUASI_EXPERIMENTAL"]},
                "measurement_type": {"type": "string", "enum": ["BETWEEN_SUBJECTS", "WITHIN_SUBJECTS", "MIXED"]},
                "is_randomized": {"type": "boolean"},
                "relationship_form": {"type": "string", "enum": ["linear", "monotone", "nonlinear", "unknown"]},
                "confounder_names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["design_type", "measurement_type", "is_randomized"],
        },
    },
}
```

### `causal.py` — public API

```python
class CausalAnalyser:
    def __init__(self, bus: EventBus) -> None: ...
    def analyse(self, profile: DataProfile, design: StudyDesign) -> CausalGraph: ...
```

- Builds `CausalGraph` from `design.confounders`.
- Adjustment set = all `Confounder` entries where `adjustment_recommended=True` and `is_measured=True`.
- Warning added when any `adjustment_recommended=True` confounder has `is_measured=False`.
- Publishes `EVENT_GRAPH_BUILT`.

### `tests/test_dialogue.py` — required cases

| Test | Description |
|---|---|
| `test_dry_run_returns_study_design` | Returns `StudyDesign` without API call |
| `test_dry_run_nonlinear_note` | dry-run variant with nonlinear note in `notes` |
| `test_rule7_note_populated` | `StudyDesign.notes` contains `"nonlinear"` when appropriate |

### `tests/test_causal.py` — required cases

| Test | Description |
|---|---|
| `test_adjustment_set_measured` | Measured confounders in adjustment set |
| `test_unmeasured_confounder_warning` | Unmeasured + adjustment_recommended → warning |
| `test_no_confounders` | Empty confounder list → empty adjustment set, no warning |
| `test_publishes_event` | `EVENT_GRAPH_BUILT` fired with correct payload |
| `test_edges_built_from_confounders` | Edges represent confounder → outcome and confounder → exposure |

**Gate:** `pytest tests/test_dialogue.py tests/test_causal.py` → all passing.

---

## Step 5 — Test selector

**Goal:** `src/hta/modules/selector.py` — purely deterministic decision tree.  
**Files created:** `src/hta/modules/selector.py`, `tests/test_selector.py`

### `selector.py` — public API

```python
class TestSelector:
    def __init__(self, bus: EventBus) -> None: ...
    def select(self, profile: DataProfile, design: StudyDesign) -> StatisticalTest: ...
    def get_selection_rationale(
        self, test: StatisticalTest, profile: DataProfile, design: StudyDesign
    ) -> str: ...
```

`select()` publishes `EVENT_TEST_SELECTED` and returns the enum value.

### Decision tree (full, incorporating all resolutions)

```
outcome_var = profile.outcome_variable
outcome = profile.variables[outcome_var].variable_type

if outcome is CONTINUOUS:
    n_groups = profile.n_groups or 1

    if n_groups == 1 and there is a continuous predictor:
        # Correlation / independence path
        relationship = "nonlinear" if ("nonlinear" in design.notes or "complex" in design.notes) else
                       "linear"    if "linear" in design.notes else
                       "monotone"                                    # default
        if relationship == "nonlinear":
            → MAXBET   # BEAST is in the enum but not selectable in v0.1.0
        elif relationship == "linear" and outcome_is_normal and predictor_is_normal:
            → PEARSON_CORRELATION
        else:
            → SPEARMAN_CORRELATION

    elif n_groups == 2:
        if design.measurement_type in (WITHIN_SUBJECTS, MIXED):
            → PAIRED_T      if outcome_is_normal
            → WILCOXON_SIGNED_RANK  otherwise
        else:  # BETWEEN_SUBJECTS
            → WELCH_T       if outcome_is_normal      # Welch is always the default (resolution #3)
            → MANN_WHITNEY_U  otherwise

    elif n_groups >= 3:
        → ONE_WAY_ANOVA   if outcome_is_normal
        → KRUSKAL_WALLIS  otherwise

if outcome is BINARY or CATEGORICAL:
    if design has a paired/within-subjects binary outcome:
        → MCNEMAR
    else:
        if 2×2 contingency table:
            if all expected cell counts ≥ 5:   → CHI_SQUARED
            else:                               → FISHER_EXACT
        else (R×C table):
            → CHI_SQUARED   (with Cramér's V effect size)
```

**Normality helper** (`_is_normal(var: Variable) -> bool`):  
`is_normal = True` only when all of:
- `var.normality.is_normal is True`
- `abs(var.distribution_stats.skewness) < 2.0`
- `abs(var.distribution_stats.kurtosis) < 7.0`
- `var.n_observations >= 20`

This is the "soft signal" resolution of design review note #1.

### `tests/test_selector.py` — required cases

One test per test type + edge cases:

| Test | Profile / Design setup | Expected result |
|---|---|---|
| `test_select_welch_t` | 2 groups, normal, between | `WELCH_T` |
| `test_select_mann_whitney` | 2 groups, non-normal, between | `MANN_WHITNEY_U` |
| `test_select_paired_t` | 2 groups, normal, within | `PAIRED_T` |
| `test_select_wilcoxon` | 2 groups, non-normal, within | `WILCOXON_SIGNED_RANK` |
| `test_select_anova` | 3 groups, normal | `ONE_WAY_ANOVA` |
| `test_select_kruskal` | 3 groups, non-normal | `KRUSKAL_WALLIS` |
| `test_select_pearson` | 1 group, 2 continuous, linear note, both normal | `PEARSON_CORRELATION` |
| `test_select_spearman` | 1 group, 2 continuous, monotone, non-normal | `SPEARMAN_CORRELATION` |
| `test_select_maxbet` | 1 group, 2 continuous, nonlinear note | `MAXBET` |
| `test_select_chi_squared_2x2` | 2 categorical, expected counts ≥ 5 | `CHI_SQUARED` |
| `test_select_fisher_exact` | 2×2 categorical, small expected counts | `FISHER_EXACT` |
| `test_select_chi_squared_rxc` | 3×4 categorical table | `CHI_SQUARED` |
| `test_select_mcnemar` | Paired binary | `MCNEMAR` |
| `test_normality_soft_signal` | `is_normal=True` but skewness=3.0 → treated as non-normal | `MANN_WHITNEY_U` |
| `test_rationale_string` | Any test → `get_selection_rationale` returns non-empty string |
| `test_publishes_event` | `EVENT_TEST_SELECTED` fired with correct payload |

**Gate:** `pytest tests/test_selector.py` → 16 passing, 0 failing.  
> **Statistician review checkpoint** — Statistician A signs off on the full decision tree before Step 6 begins.

---

## Step 6 — Test executor

**Goal:** `src/hta/modules/executor.py` — runs the selected test, returns `TestResult`.  
**Files created:** `src/hta/modules/executor.py`, `tests/test_executor.py`  
**New dependency:** `rpy2` (add to `pyproject.toml` `[project.dependencies]`); `scikit-posthocs` (for Dunn's test)

### `executor.py` — public API

```python
class TestExecutor:
    def __init__(self, bus: EventBus) -> None: ...
    def execute(
        self,
        data: pd.DataFrame,
        test: StatisticalTest,
        outcome_var: str,
        group_var: str | None,
        design: StudyDesign,
    ) -> TestResult: ...
```

`execute()` publishes `EVENT_TEST_EXECUTED` and returns `TestResult`.

### Per-test implementation

| Test | Library | Effect size | Assumption checks |
|---|---|---|---|
| `WELCH_T` | `scipy.stats.ttest_ind(equal_var=False)` | Cohen's d (pooled SD); bootstrap 95% CI (n=1000) | Normality (Shapiro-Wilk), min N ≥ 5 per group |
| `INDEPENDENT_T` | `scipy.stats.ttest_ind(equal_var=True)` | Cohen's d | Normality, equal variances (Levene) |
| `PAIRED_T` | `scipy.stats.ttest_rel` | Cohen's d_z (within-subject SD) | Normality of differences |
| `MANN_WHITNEY_U` | `scipy.stats.mannwhitneyu` | Rank-biserial r = `(2U)/(n₁n₂) − 1`; bootstrap CI | Min N ≥ 5 per group |
| `WILCOXON_SIGNED_RANK` | `scipy.stats.wilcoxon` | Matched-pairs rank-biserial r; bootstrap CI | N ≥ 10 pairs |
| `ONE_WAY_ANOVA` | `scipy.stats.f_oneway` | η² = SS_between/SS_total; ω² = (SS_b − df_b·MS_w)/(SS_t + MS_w) | Normality per group, Levene; post-hoc: Tukey HSD (`pingouin.pairwise_tukey`) |
| `KRUSKAL_WALLIS` | `scipy.stats.kruskal` | ε² = (H − k + 1)/(n − k); bootstrap CI | Min N ≥ 5 per group; post-hoc: Dunn's test + Holm (`scikit_posthocs.posthoc_dunn`) |
| `CHI_SQUARED` | `scipy.stats.chi2_contingency` | Cramér's V = `√(χ²/(n·min(r−1,c−1)))`; bootstrap CI | Expected cell count ≥ 5 (flag VIOLATED if any < 5) |
| `FISHER_EXACT` | `scipy.stats.fisher_exact` | Odds ratio; 95% CI via Baptista–Pike method | 2×2 only (raise `ValueError` if not) |
| `MCNEMAR` | `statsmodels.stats.contingency_tables.mcnemar` | Odds ratio of discordant pairs; bootstrap CI | Paired structure, ≥ 25 discordant pairs |
| `PEARSON_CORRELATION` | `scipy.stats.pearsonr` | r is its own effect size; Fisher's z 95% CI | Bivariate normality (Shapiro-Wilk on both) |
| `SPEARMAN_CORRELATION` | `scipy.stats.spearmanr` | ρ is its own effect size; bootstrap CI (n=1000) | Continuity (no ties > 5%) |
| `MAXBET` | `rpy2` → R `BET::MaxBET` | BET symmetry statistic + depth; normalised MI as supplementary | Continuity, N ≥ 20, depth ≤ ⌊log₂(N)⌋ |
| `BEAST` | not selectable in v0.1.0 (enum reserved for v0.2.0) | — | — |
| `BET` | not selectable in v0.1.0 (enum reserved for v0.2.0) | — | — |
| `LINEAR_REGRESSION` | — | — | Raises `NotImplementedError("planned for v0.2.0")` |
| `LOGISTIC_REGRESSION` | — | — | Raises `NotImplementedError("planned for v0.2.0")` |

### Power reporting

Never compute observed power. For each test, compute *sensitivity power* = the minimum detectable effect size (Cohen's d, f, or w) achievable at the observed N with α=0.05 and power=0.80, using `statsmodels.stats.power`. Store in `TestResult.notes` as:  
`"Sensitivity: minimum detectable Cohen's d = {mde:.2f} at N={n}, α=0.05, power=0.80"`

### rpy2 BET wrapper

```python
def _run_rbet(
    x: list[float], y: list[float],
    variant: str = "MaxBET",   # "MaxBET" | "BEAST" | "BET"
    max_depth: int = 8,
) -> dict[str, float]:
    """Bridge to R BET package. Raises ImportError if rpy2 or BET not installed."""
    rpy2 = pytest.importorskip("rpy2")   # graceful skip in tests
    ...
```

`max_depth` is automatically capped at `floor(log2(n))`.

### `tests/test_executor.py` — required cases

| Test | Description |
|---|---|
| `test_welch_t_known` | Verified against R `t.test(var.equal=FALSE)` output |
| `test_mann_whitney_known` | Verified against R `wilcox.test` |
| `test_paired_t_known` | Verified against R `t.test(paired=TRUE)` |
| `test_wilcoxon_known` | Verified against R `wilcox.test(paired=TRUE)` |
| `test_anova_known` | Verified against R `aov` + `TukeyHSD` |
| `test_kruskal_known` | Verified against R `kruskal.test` + Dunn |
| `test_chi_squared_known` | Verified against R `chisq.test` |
| `test_fisher_exact_known` | Verified against R `fisher.test` |
| `test_mcnemar_known` | Verified against R `mcnemar.test` |
| `test_pearson_known` | Verified against R `cor.test(method="pearson")` |
| `test_spearman_known` | Verified against R `cor.test(method="spearman")` |
| `test_maxbet_known` | `pytest.mark.skipif(no rpy2)` — verified against R `BET::MaxBET` |
| `test_assumption_violations_flagged` | Non-normal data → `AssumptionStatus.VIOLATED` in checks |
| `test_posthoc_in_notes` | ANOVA result → Tukey table string in `TestResult.notes` |
| `test_sensitivity_power_in_notes` | WELCH_T result → sensitivity MDE in `TestResult.notes` |
| `test_linear_regression_not_implemented` | Raises `NotImplementedError` |
| `test_publishes_event` | `EVENT_TEST_EXECUTED` fired with correct payload |

**Gate:** `pytest tests/test_executor.py` → 17 passing (BET test may be skipped if R absent), 0 failing.

---

## Step 7 — Reporter

**Goal:** `src/hta/modules/reporter.py` — assembles `Report` from upstream outputs.  
**Files created:** `src/hta/modules/reporter.py`, `tests/test_reporter.py`

### `reporter.py` — public API

```python
class Reporter:
    def __init__(self, bus: EventBus, dry_run: bool = True) -> None: ...
    def report(
        self,
        profile: DataProfile,
        design: StudyDesign,
        result: TestResult,
    ) -> Report: ...
```

`report()` publishes `EVENT_REPORT_READY` and returns the `Report`.

### Caveat generation rules (deterministic, in evaluation order)

| # | Severity | Condition | Message template |
|---|---|---|---|
| 1 | `CRITICAL` | Any `assumption_checks` has `status == VIOLATED` | `"Assumption violated: {assumption_name}. {note}"` |
| 2 | `WARNING` | `"minimum detectable"` in notes and MDE > 0.5 | `"Underpowered study: minimum detectable effect = {mde:.2f} (large). Consider increasing N."` |
| 3 | `WARNING` | `0.01 ≤ p_value ≤ 0.05` | `"Marginal result (p={p:.3f}). Replicate before drawing strong conclusions."` |
| 4 | `WARNING` | Effect size small by convention and `is_significant` | `"Statistically significant but effect is small ({measure}={value:.2f}). Consider practical significance."` |
| 5 | `INFO` | `n_groups ≥ 3` | `"Multiple groups tested. Post-hoc results are in the notes; consider family-wise error."` |
| 6 | `INFO` | `design.design_type == OBSERVATIONAL` | `"Observational study: avoid causal language in the summary."` |

### Plot specs to generate

| Test type | Plots |
|---|---|
| Two-group comparison | Boxplot (groups × outcome), QQ-plot per group |
| Correlation / BET | Scatter (x vs y) |
| 3+ groups | Boxplot (all groups), QQ-plot per group |
| Categorical | Stacked bar (counts), mosaic optional |

### GPT-5.4 calls (`dry_run=False` only)

- **`plain_language_summary`**: 2–3 sentences; audience = non-statistician; must not use causal language if `design_type == OBSERVATIONAL`.
- **`methods_text`**: One paragraph; APA-style; include test name, assumption checks, effect size, and CI.

Dry-run stubs:
```python
plain_language_summary = "DRY RUN: summary not generated."
methods_text = "DRY RUN: methods text not generated."
```

### `tests/test_reporter.py` — required cases

| Test | Description |
|---|---|
| `test_caveat_critical_assumption_violated` | Violated assumption → CRITICAL caveat |
| `test_caveat_underpowered` | MDE note in result → WARNING caveat |
| `test_caveat_marginal_p` | p=0.03 → WARNING caveat |
| `test_caveat_small_effect` | Small Cohen's d + significant → WARNING caveat |
| `test_caveat_multiple_groups` | n_groups=3 → INFO caveat |
| `test_caveat_observational` | OBSERVATIONAL design → INFO caveat |
| `test_plot_spec_two_group` | Two-group result → boxplot + QQ specs |
| `test_plot_spec_correlation` | Correlation result → scatter spec |
| `test_dry_run_stubs` | dry_run=True → stub strings in summary and methods |
| `test_publishes_event` | `EVENT_REPORT_READY` fired with correct payload |

**Gate:** `pytest tests/test_reporter.py` → 10 passing, 0 failing.

---

## Step 8 — Agent orchestration, CLI, and examples

**Goal:** Wire all modules into `agent.py`, expose via `cli.py`, write three example scripts.  
**Files created:** `src/hta/agent.py`, `src/hta/cli.py`, `examples/two_group_comparison.py`, `examples/categorical_association.py`, `examples/paired_before_after.py`, `tests/test_agent.py`

### `agent.py` — public API

```python
class HypothesisTestingAgent:
    def __init__(self, dry_run: bool = True) -> None: ...
    def run(
        self,
        data: pd.DataFrame | list[dict] | str | dict[str, list],
        hypothesis: str,
        outcome_variable: str,
        group_variable: str | None = None,
    ) -> Report: ...
```

Wires modules in order:
1. `DataProfiler.profile(data, outcome_variable, group_variable)`
2. `DesignDialogue.run(profile, hypothesis)`
3. `CausalAnalyser.analyse(profile, design)`
4. `TestSelector.select(profile, design)`
5. `TestExecutor.execute(data_df, test, outcome_variable, group_variable, design)`
6. `Reporter.report(profile, design, result)`

All modules share the same `EventBus` instance.

### `cli.py` — Typer commands

```
hta run --data PATH --hypothesis TEXT --outcome TEXT [--group TEXT] [--dry-run]
hta version
```

Output rendered with **Rich**:
- Panel: test name, statistic, p-value (green if significant, red if not), effect size, CI.
- Table: assumption checks (colour-coded by status).
- Table: caveats (colour-coded by severity).
- Footer: plain-language summary.

### Example scripts (all run with `--dry-run`)

| File | Scenario | Test expected |
|---|---|---|
| `two_group_comparison.py` | RCT, blood pressure, 2 groups | `WELCH_T` |
| `categorical_association.py` | Survey, treatment × recovery, 2×2 table | `CHI_SQUARED` or `FISHER_EXACT` |
| `paired_before_after.py` | Before/after intervention, within-subjects | `PAIRED_T` or `WILCOXON_SIGNED_RANK` |

### `tests/test_agent.py` — required cases

| Test | Description |
|---|---|
| `test_end_to_end_dry_run` | Full pipeline dry-run → `Report` fully populated |
| `test_report_has_all_fields` | No field is None except optional ones |
| `test_event_bus_fires_all_events` | All 6 events fired in order |

**Gate:** `pytest` (full suite) → ≥ 80% coverage, 0 failing, `mypy src/hta` clean, `ruff check src/` clean.

---

## Post-implementation: statistician review package

Once all 8 steps pass:

1. Create `STATISTICIAN_REVIEW.md` — every decision point with file:line reference.
2. Create `BENCHMARK_CASES.md` — 20 test cases with known inputs and expected outputs.
3. Run all three example scripts; save terminal output to `examples/OUTPUT_EXAMPLES.md`.
4. Tag commit `v0.1.0-statistician-review`.

---

## Coverage and quality gates (final)

```bash
pytest --cov=src/hta --cov-report=term-missing   # ≥ 80% line coverage
mypy src/hta                                       # 0 errors
ruff check src/                                    # 0 errors
```

---

## Dependency additions (to `pyproject.toml`)

Add to `[project.dependencies]`:
- `rpy2>=3.5.0`
- `scikit-posthocs>=0.9.0`

Add to `[project.optional-dependencies].dev`:
- No new dev-only additions needed.

---

*Last updated: 2026-06-01. Ready for review before implementation begins.*
