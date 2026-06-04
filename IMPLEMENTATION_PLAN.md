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
| 1 | Normality as hard binary gate | **Treat as a graded `NONE`/`MILD`/`STRONG` signal, never a binary gate.** The selector consumes severity via `prefer_rank_based(outcome_type, n_min, nonnormality)`: `ORDINAL` and a `STRONG` departure at small N go rank-based; `n_min ≥ LARGE_N` (default 30) goes parametric by the CLT. See Step 5 selector logic and TECHNICAL_REPORT §6.1. |
| 2 | KS / formal normality test invalid at N > 2000 | **Drop the formal normality test above N = 2000.** Shapiro–Wilk corroborates severity at N ≤ 2000; above 2000 no formal test is run (one-sample KS vs *estimated* parameters needs Lilliefors and flags essentially every real dataset). Severity above 2000 comes from skew/kurtosis magnitude alone. See §6.1. |
| 3 | Welch vs Student via Levene pretest | **Welch is the unconditional default** for between-subjects continuous comparisons — `WELCH_T` (2 groups) and `WELCH_ANOVA` (3+ groups), with no variance pretest. The equal-variance forms (`INDEPENDENT_T`, `ONE_WAY_ANOVA`) are reachable only via an explicit `force_student` override and are otherwise never returned by the selector in v0.1.0. |
| 4 | Observed (post-hoc) power | **Never compute observed power.** Report *sensitivity power* only: the minimum detectable effect at the observed N and α=0.05, using `statsmodels.stats.power`. The `power < 0.80` caveat triggers when MDE > 0.5 (large effect only). |
| 5 | LINEAR/LOGISTIC_REGRESSION in enum but not in tree | **Keep in enum** (removing would break JSON round-trips). Marked reserved/non-selectable in `test.py`. Selector never returns them in v0.1.0. Executor raises `NotImplementedError` if called. Document as "planned for v0.2.0". |
| 6 | FISHER_EXACT / odds ratio for R×C tables | **Split selection by expected counts and effect size by table shape.** Selector: `min_expected ≥ 5` → `CHI_SQUARED`, else `FISHER_EXACT` (2×2 exact; R×C uses the Fisher–Freeman–Halton generalisation). Executor reports effect size by `table_shape`: 2×2 → odds ratio (+ φ; a 2×2 χ² also reports OR); R×C → Cramér's V. |
| 7 | ANOVA / Kruskal post-hoc policy | **Always run post-hoc, Holm-adjusted, recorded on `TestResult`.** `WELCH_ANOVA` → Games–Howell (no equal-variance assumption); `ONE_WAY_ANOVA` → Tukey HSD (pingouin); `KRUSKAL_WALLIS` → Dunn's test (scikit-posthocs). "No correction" is never a silent default. |
| 8 | Secrets path coupling | **Resolved.** `config.py` loads from `.env` at the project root. No external path dependency. |

---

## Step 1b — Model updates for the reconciled tree ✅ DONE (commit `41ca304`)

**Goal:** Extend `StatisticalTest` enum so the code matches the §6 decision tree; update tests.  
**Blocked by:** nothing (Step 1 is done)  
**Files touched:** `src/hta/models/test.py`, `tests/test_models.py`

> **Status:** Completed by the decision-tree reconcile commit. The members actually added differ from the original BET-only sketch: the tree returns `WELCH_ANOVA` and the BET-family `MAXBET`/`BEAST`, so those three were added (no single-depth `BET` member — it is not reachable from the tree). The conftest BET fixtures were not added and are not required by the tree.

### Tasks

- [x] **`src/hta/models/test.py`** — Three members added so the enum matches the tree:
  ```python
  WELCH_ANOVA = "WELCH_ANOVA"  # default for 3+ group between-subjects continuous
  MAXBET      = "MAXBET"       # nonlinear independence (BET); default BET-family choice
  BEAST       = "BEAST"        # data-adaptive BET variant; reserved for explicit override
  ```
  `INDEPENDENT_T` / `ONE_WAY_ANOVA` annotated as explicit-override-only; `LINEAR_REGRESSION` / `LOGISTIC_REGRESSION` annotated reserved (non-selectable in v0.1.0).

- [x] **`tests/test_models.py`** — Enum-count assertion updated 14 → 17; `EXPECTED` value set updated to the 17-member set.

**Gate:** `pytest tests/test_models.py` → passing with the 17-member enum. ✅

---

## Step 1c — Healthcare data-form model extensions ✅ DONE

**Goal:** Make the models cover every data form, with healthcare forms first-class
(TECHNICAL_REPORT §6.5–§6.7).
**Files touched:** `src/hta/models/data.py`, `src/hta/models/test.py`, `src/hta/models/design.py`, `tests/test_models.py`

### Tasks

- [x] **`VariableType`** — add `COUNT`, `TIME_TO_EVENT`, `DATETIME`, `GEOSPATIAL`, `IDENTIFIER`
  (4 → 9). COUNT/TIME_TO_EVENT are analysis levels; DATETIME/GEOSPATIAL/IDENTIFIER are
  structural roles the profiler tags so the data is mapped/derived/excluded, not mis-analysed.
- [x] **`StatisticalTest`** — add selectable `POISSON_REGRESSION`,
  `NEGATIVE_BINOMIAL_REGRESSION`, `LOG_RANK`, `COX_REGRESSION`, `ROC_AUC`; reserve
  `LINEAR_MIXED_MODEL`, `GENERALIZED_ESTIMATING_EQUATIONS` (17 → 24).
- [x] **`StudyDesign.reporting_standard: Optional[str]`** — CONSORT/STROBE/STARD/TRIPOD/PRISMA,
  derived from the design (EQUATOR mapping, §6.6).
- [x] **`EffectSize`** docstring — add IRR / hazard ratio / risk ratio / AUC (ratio-scale CIs).
- [x] **`tests/test_models.py`** — VariableType count 4 → 9; StatisticalTest count 17 → 24;
  add COUNT/TIME_TO_EVENT variable construction, Cox(HR)/NegBin(IRR) `TestResult` cases, and a
  `reporting_standard` round-trip.

**Gate:** `pytest tests/test_models.py` → passing with the 9-member `VariableType` and
24-member `StatisticalTest`.

---

## Step 1d — EDA dependence models ✅ DONE

**Goal:** Carry the BET exploratory-dependence findings (Xiang et al. 2023, *Ann. Appl. Stat.* 17(4), DOI 10.1214/23-AOAS1745; preprint arXiv:2202.09880) through the models.
**Files touched:** `src/hta/models/data.py`, `src/hta/models/design.py`, `tests/test_models.py`

- [x] **`DependenceForm`** enum (LINEAR, MONOTONE, PARABOLIC, SINUSOIDAL, CHECKERBOARD,
  COMPLEX, INDEPENDENT) + **`DependenceFinding`** model (x, y, n, S, bet_z, p_value, bid,
  form, direction, pearson_r, spearman_rho, nonlinear_only, significant).
- [x] **`DataProfile.nonlinear_dependencies: list[DependenceFinding]`**.
- [x] **`StudyDesign.subgroup_variables: list[str]`** (stratify / effect-modifier vars).
- [x] **`tests/test_models.py`** — `DependenceForm` enum, `DependenceFinding` round-trip,
  profile/design defaults.

**Gate:** `pytest tests/test_models.py` → passing.

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

Healthcare-aware (TECHNICAL_REPORT §6.5). Structural roles are checked first so IDs, dates,
and coordinates are not mis-typed as numbers; then the statistical forms:

1. Unique (or near-unique) value per row, **or** name matches an id pattern
   (`id`, `_id`, `uuid`, `mrn`, `fips`, `geoid`) with high cardinality → `IDENTIFIER`
2. Parseable as date/time (pandas `to_datetime` succeeds on a sample) → `DATETIME`
3. Latitude/longitude column or areal id (name matches `lat`, `lon`/`lng`, `fips`,
   `geoid`, `tract`, `county`+coordinates present) → `GEOSPATIAL`
4. Non-numeric dtype or ≤ 2 unique values that are strings → `BINARY`
5. Exactly 2 unique numeric values → `BINARY`
6. Non-negative integers with many distinct values (not a bounded small scale) **and**
   a count signal (name like `count`/`n_`/`visits`/`events`, or a paired exposure/offset
   column such as `population`/`person_years`) → `COUNT`
7. Duration/elapsed-time column paired with an event/censoring indicator (0/1) → `TIME_TO_EVENT`
8. Non-numeric with > 2 unique values → `CATEGORICAL`
9. Numeric, ≤ 10 unique integer values → `ORDINAL`
10. Everything else → `CONTINUOUS`

`COUNT` vs `ORDINAL` (small integers) and `TIME_TO_EVENT` (needs an event-indicator
companion) are the ambiguous cases; the profiler records its best guess and DesignDialogue
(Step 4) confirms or overrides it. `GEOSPATIAL`/`DATETIME`/`IDENTIFIER` are never selected as
the outcome — they drive maps, derivations, or exclusion.

### Normality severity (graded, not a binary gate)

The profiler emits a **severity** signal `nonnormality ∈ {NONE, MILD, STRONG}`, derived from robust descriptors (skew / excess kurtosis), per §6.1 of the technical report. There is **no formal normality test above N = 2000** — a one-sample KS / Shapiro test against *estimated* parameters is statistically invalid there and flags essentially every real dataset, so it is uninformative for selection.

| N | Corroboration | Severity source |
|---|---|---|
| ≤ 2000 | Shapiro–Wilk (`scipy.stats.shapiro`) corroborates | skew/kurtosis magnitude, corroborated by Shapiro–Wilk |
| > 2000 | none — no formal test run | skew/kurtosis magnitude **alone** |

Severity thresholds (proposed defaults, pending Statistician A sign-off):

| Severity | Condition |
|---|---|
| `NONE`   | \|skew\| < 1 and \|excess kurtosis\| < 2 |
| `MILD`   | \|skew\| ∈ [1, 2) or \|excess kurtosis\| ∈ [2, 7) |
| `STRONG` | \|skew\| ≥ 2 or \|excess kurtosis\| ≥ 7 (Kim 2013) |

`NormalityTest.name` = `"Shapiro-Wilk"` when a formal test is run (N ≤ 2000); `None`/`"none (N>2000)"` otherwise. The graded `nonnormality` severity (not a bare `is_normal` boolean) is what the selector consumes. Only computed for `CONTINUOUS` and `ORDINAL` variables.

### Data quality notes (appended to `DataProfile.notes`)

| Condition | Note string |
|---|---|
| Missing > 5% for any variable | `"{name}: {pct:.1f}% missing values"` |
| Variable is constant (std == 0) | `"{name}: constant variable (zero variance)"` |
| Any `\|Z\| > 3.5` | `"{name}: {k} outlier(s) detected (\|Z\| > 3.5)"` |

### `tests/test_profiler.py` — required cases

| Test | Description |
|---|---|
| `test_normal_continuous` | Known-normal data (N ≤ 2000) → Shapiro–Wilk `is_normal=True`, `nonnormality=NONE`, correct stats |
| `test_skewed_continuous` | Log-normal data → `nonnormality=STRONG` (\|skew\| ≥ 2) |
| `test_binary_detection` | Two-value column → `BINARY` |
| `test_categorical_detection` | String column → `CATEGORICAL` |
| `test_ordinal_detection` | Integer 1–5 column → `ORDINAL` |
| `test_count_detection` | Non-negative integer counts with a `population` offset → `COUNT` |
| `test_time_to_event_detection` | Duration column + 0/1 event indicator → `TIME_TO_EVENT` |
| `test_identifier_detection` | Unique-per-row id / FIPS column → `IDENTIFIER` (excluded from analysis) |
| `test_datetime_detection` | Parseable date column → `DATETIME` |
| `test_geospatial_detection` | `latitude`/`longitude` columns → `GEOSPATIAL` |
| `test_count_not_misread_as_ordinal` | Wide-range non-negative integer counts → `COUNT`, not `ORDINAL` |
| `test_missing_data_note` | >5% NaN → note added |
| `test_constant_variable_note` | All-same column → note added |
| `test_outlier_note` | Z > 3.5 value → note added |
| `test_group_level_stats` | Group variable → per-group severity |
| `test_severity_grading` | NONE/MILD/STRONG assigned correctly from skew/kurtosis thresholds |
| `test_large_n_no_formal_test` | N=2500 → no Shapiro–Wilk run; severity from skew/kurtosis alone |
| `test_input_formats` | list-of-dicts and dict-of-lists accepted |
| `test_publishes_event` | `EVENT_DATA_PROFILED` fired with correct payload |
| `test_csv_string_input` | CSV string parsed correctly |

**Gate:** `pytest tests/test_profiler.py` → 20 passing, 0 failing.

> The profiler also runs the **BET EDA screen** (Step 3a) and attaches the ranked
> `DependenceFinding`s to `DataProfile.nonlinear_dependencies`, plus a tie/zero-inflation
> data-quality note when jittering was needed.

---

## Step 3a — BET exploratory dependence screen ✅ DONE (engine + tests)

**Goal:** Implement the pairwise nonlinear-dependence EDA of **Xiang et al. (2023), *Ann.
Appl. Stat.* 17(4), DOI 10.1214/23-AOAS1745** (preprint arXiv:2202.09880) as the
profiler's discovery stage.
**Files created:** `src/hta/bet_screen.py`, `tests/test_bet_screen.py`

### `bet_screen.py` — public API

```python
def empirical_copula(values: list[float], rng: random.Random) -> list[float]: ...
def maxbet(x: list[float], y: list[float], alpha=0.05, seed=0) -> PairDependence: ...
def pairwise_screen(columns: dict[str, list[float]], alpha=0.05,
                    max_pairs: int | None = None, seed=0) -> ScreenResult: ...
def relationship_form(form: str) -> str:  # -> "linear" | "monotone" | "nonlinear"
```

- [x] Empirical-copula transform with **tie jitter** (deterministic, seeded) — handles
  zero-inflation / imputed values that break BET's continuity assumption.
- [x] Depth-2 MaxBET over the 9 BIDs; symmetry statistic `S`, `Z = |S|/√n`, two-level
  Bonferroni (across BIDs and across screened pairs).
- [x] Dominant-BID → `DependenceForm` + direction (sign of `S`); `nonlinear_only` flag when
  BET-significant but |Pearson| and |Spearman| are both < 0.10.
- [x] Pure standard library (no numpy/scipy/R) so the depth-2 screen runs anywhere; the
  profiler wraps `PairDependence` into `DependenceFinding` models.

### `tests/test_bet_screen.py` — required cases (all passing)

| Test | Description |
|---|---|
| `test_monotone_increasing` | linear data → MONOTONE/LINEAR, increasing, Pearson high |
| `test_monotone_decreasing_direction` | negative slope → direction `decreasing` |
| `test_parabola_is_nonlinear_only` | y=x² → significant, Pearson≈0, `nonlinear_only`, nonlinear form |
| `test_independence_not_significant` | independent → not significant, INDEPENDENT |
| `test_tie_jitter_no_crash_and_valid_copula` | 50% tied zeros → valid distinct copula |
| `test_pairwise_screen_ranks_and_flags` | screen sorts by Z; flags the nonlinear-only pair |
| `test_z_matches_statistic` | `Z == |S|/√n` |

**Gate:** `pytest tests/test_bet_screen.py` → 7 passing, 0 failing. *(Verified with a stdlib
runner — the engine has no third-party deps.)*

> **Note on the full d>2 / cross-all-pairs paper pipeline:** the v0.1.0 screen uses depth
> d=2 (the paper's recommended resolution) and the pure-Python symmetry statistic. The R
> `BET::MaxBET` path (Step 6 executor) remains the route for confirmatory BET with the
> normalised-MI supplement; the EDA screen here is for fast discovery + interpretation.

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
- Implements all 8 dialogue rules from §7.2 (Rule 7: relationship-form, pre-filled from the BET
  EDA; Rule 8: subgroup elicitation when the BET screen flags a nonlinear / mixture-type pair).
- `StudyDesign.notes` must contain `"nonlinear"` or `"complex"` when the user answers that way to Rule 7.
- When Rule 8 fires and the user names subgroups, populate `StudyDesign.subgroup_variables`.

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
                "subgroup_variables": {"type": "array", "items": {"type": "string"},
                    "description": "Subgroups/subtypes that may drive a nonlinear/mixture pattern (Rule 8)."},
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
| `test_rule8_subgroup_captured` | BET nonlinear/mixture finding → `subgroup_variables` populated from the dialogue |

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

`select()` publishes `EVENT_TEST_SELECTED` and returns the enum value. The tree is **purely deterministic** and mirrors TECHNICAL_REPORT §6.2 (+ §6.5 healthcare dispatch) exactly. Every distributional property is consumed as a *graded signal*, never as a binary significance gate.

### Healthcare dispatch (runs first — mirrors §6.5)

Before the classical tree, `select()` dispatches on the outcome's data form so healthcare
outcomes go to the right family:

```python
if outcome_type == COUNT:
    → NEGATIVE_BINOMIAL_REGRESSION  if overdispersed (var > mean)  else  POISSON_REGRESSION
elif outcome_type == TIME_TO_EVENT:
    → COX_REGRESSION  if (covariate adjustment or continuous exposure)  else  LOG_RANK
elif design.is_diagnostic_accuracy:      # continuous/ordinal index vs BINARY reference
    → ROC_AUC
# else: fall through to the classical CONTINUOUS/ORDINAL/BINARY/CATEGORICAL tree below.
```

`overdispersed`, the event-indicator column, the rate offset, and the diagnostic flag come
from the profiler + DesignDialogue. Clustering / repeated-measures keys do **not** select a
mixed/GEE model in v0.1.0 — they set a caveat (Step 7, H9).

### Signals consumed (from `profile` and `design`)

- `outcome_type` ∈ {CONTINUOUS, ORDINAL, BINARY, CATEGORICAL, COUNT, TIME_TO_EVENT}
- `n_groups`; `measurement` ∈ {BETWEEN, WITHIN} (paired/repeated → WITHIN; MIXED treated as WITHIN here)
- `n_min` — smallest per-group (or per-pair) sample size
- `relationship` ∈ {LINEAR, MONOTONE, NONLINEAR} — correlation path only. **Primary source: the BET EDA** — `relationship_form(dominant DependenceForm)` for the outcome/predictor pair in `profile.nonlinear_dependencies`; falls back to `StudyDesign.notes` (rule 7) then default LINEAR
- `subgroup_variables` (from `StudyDesign`) — when non-empty, run the chosen test **within each subgroup** (contextual analysis) and record it; full interaction model reserved for v0.2.0
- `table_shape` ∈ {TWO_BY_TWO, RxC} and `min_expected` (smallest expected cell count) — categorical outcomes only
- `nonnormality` ∈ {NONE, MILD, STRONG} — severity from the profiler (§6.1 / Step 3)
- `force_student` — explicit user override (default `False`)

### Normality helper (`prefer_rank_based`)

Replaces the old binary `_is_normal` gate. `LARGE_N` default = 30 (proposed, pending Statistician A sign-off):

```python
def prefer_rank_based(outcome_type, n_min, nonnormality) -> bool:
    if outcome_type == ORDINAL:   # scale of measurement, not a normality question
        return True
    if n_min >= LARGE_N:          # CLT: the sampling distribution of the mean is ~normal
        return False
    return nonnormality == STRONG # at small N, only a *strong* departure switches to rank-based
```

### Decision tree (full, mirrors §6.2)

```
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

`BEAST` is in the enum but selectable only via explicit override; `INDEPENDENT_T` / `ONE_WAY_ANOVA` are reachable only via `force_student`.

### `tests/test_selector.py` — required cases

One test per test type + edge cases:

| Test | Profile / Design setup | Expected result |
|---|---|---|
| `test_select_welch_t` | 2 groups, between, `nonnormality=NONE`, large N | `WELCH_T` |
| `test_select_independent_t_override` | 2 groups, between, `force_student=True` | `INDEPENDENT_T` |
| `test_select_mann_whitney` | 2 groups, between, small N, `nonnormality=STRONG` | `MANN_WHITNEY_U` |
| `test_select_paired_t` | 2 groups, within, `nonnormality=NONE` | `PAIRED_T` |
| `test_select_wilcoxon` | 2 groups, within, small N, `nonnormality=STRONG` | `WILCOXON_SIGNED_RANK` |
| `test_select_welch_anova` | 3 groups, between, parametric | `WELCH_ANOVA` |
| `test_select_one_way_anova_override` | 3 groups, between, `force_student=True` | `ONE_WAY_ANOVA` |
| `test_select_kruskal` | 3 groups, small N, `nonnormality=STRONG` | `KRUSKAL_WALLIS` |
| `test_select_pearson` | 1 group, 2 continuous, linear note, `nonnormality=NONE` | `PEARSON_CORRELATION` |
| `test_select_spearman_monotone` | 1 group, 2 continuous, monotone note | `SPEARMAN_CORRELATION` |
| `test_select_spearman_ordinal` | 1 group, ordinal outcome (no grouping) | `SPEARMAN_CORRELATION` |
| `test_select_maxbet` | 1 group, 2 continuous, nonlinear note | `MAXBET` |
| `test_relationship_from_bet_overrides_notes` | BET dominant form PARABOLIC for the pair, even if notes say "linear" → nonlinear path | `MAXBET` |
| `test_stratified_when_subgroup` | `subgroup_variables` non-empty → per-stratum test selected + contextual-analysis rationale | per-stratum test |
| `test_select_chi_squared_2x2` | 2 categorical, `min_expected ≥ 5` | `CHI_SQUARED` |
| `test_select_fisher_exact` | 2×2 categorical, `min_expected < 5` | `FISHER_EXACT` |
| `test_select_chi_squared_rxc` | 3×4 categorical table, `min_expected ≥ 5` | `CHI_SQUARED` |
| `test_select_mcnemar` | Paired binary, 2×2 within | `MCNEMAR` |
| `test_ordinal_prefers_rank` | Ordinal outcome, 2 groups → `prefer_rank_based` True regardless of severity | `MANN_WHITNEY_U` |
| `test_large_n_overrides_strong_departure` | 2 groups, between, `nonnormality=STRONG` but `n_min ≥ LARGE_N` → CLT → parametric | `WELCH_T` |
| `test_small_n_mild_stays_parametric` | 2 groups, between, small N, `nonnormality=MILD` (not STRONG) | `WELCH_T` |
| `test_select_poisson` | COUNT outcome, variance ≈ mean (not overdispersed) | `POISSON_REGRESSION` |
| `test_select_negative_binomial` | COUNT outcome, overdispersed (var > mean) | `NEGATIVE_BINOMIAL_REGRESSION` |
| `test_select_logrank` | TIME_TO_EVENT outcome, group comparison, no covariates | `LOG_RANK` |
| `test_select_cox` | TIME_TO_EVENT outcome, covariate adjustment / continuous exposure | `COX_REGRESSION` |
| `test_select_roc_auc` | Continuous index vs BINARY reference (diagnostic) | `ROC_AUC` |
| `test_count_dispatch_precedes_continuous` | COUNT outcome never routed to a t-test/ANOVA | not `WELCH_T` |
| `test_rationale_string` | Any test → `get_selection_rationale` returns non-empty string | non-empty string |
| `test_publishes_event` | `EVENT_TEST_SELECTED` fired with correct payload | event payload |

**Gate:** `pytest tests/test_selector.py` → 29 passing, 0 failing.  
> **Statistician review checkpoint** — Statistician A signs off on the full decision tree before Step 6 begins.

---

## Step 6 — Test executor

**Goal:** `src/hta/modules/executor.py` — runs the selected test, returns `TestResult`.  
**Files created:** `src/hta/modules/executor.py`, `tests/test_executor.py`  
**New dependency:** `rpy2` (add to `pyproject.toml` `[project.dependencies]`); `scikit-posthocs` (Dunn's test); `lifelines` (survival: log-rank, Cox); `scikit-learn` (ROC/AUC). `statsmodels` (already present) covers Poisson / negative-binomial GLMs.

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
| `WELCH_T` | `scipy.stats.ttest_ind(equal_var=False)` | Cohen's d (pooled SD); bootstrap 95% CI (n=1000) | Normality (Shapiro-Wilk, diagnostic), min N ≥ 5 per group. **No Levene** — Welch never assumes equal variances. |
| `INDEPENDENT_T` | `scipy.stats.ttest_ind(equal_var=True)` (override only) | Cohen's d | Normality, equal variances (Levene) — relevant only because this is the explicit equal-variance override |
| `PAIRED_T` | `scipy.stats.ttest_rel` | Cohen's d_z (within-subject SD) | Normality of differences |
| `MANN_WHITNEY_U` | `scipy.stats.mannwhitneyu` | Rank-biserial r = `(2U)/(n₁n₂) − 1`; bootstrap CI | Min N ≥ 5 per group |
| `WILCOXON_SIGNED_RANK` | `scipy.stats.wilcoxon` | Matched-pairs rank-biserial r; bootstrap CI | N ≥ 10 pairs |
| `WELCH_ANOVA` | `pingouin.welch_anova` | η² and ω² (from Welch-adjusted SS; equal variances **not** assumed) | Normality per group (diagnostic); **no Levene**. Post-hoc: Games–Howell (`pingouin.pairwise_gameshowell`), Holm-adjusted |
| `ONE_WAY_ANOVA` | `scipy.stats.f_oneway` (override only) | η² = SS_between/SS_total; ω² = (SS_b − df_b·MS_w)/(SS_t + MS_w) | Normality per group, equal variances (Levene); post-hoc: Tukey HSD (`pingouin.pairwise_tukey`) |
| `KRUSKAL_WALLIS` | `scipy.stats.kruskal` | ε² = (H − k + 1)/(n − k); bootstrap CI | Min N ≥ 5 per group; post-hoc: Dunn's test + Holm (`scikit_posthocs.posthoc_dunn`) |
| `CHI_SQUARED` | `scipy.stats.chi2_contingency` | **By `table_shape`:** R×C → Cramér's V = `√(χ²/(n·min(r−1,c−1)))`; 2×2 → Cramér's V **plus** odds ratio (and φ). Bootstrap CI | Expected cell count ≥ 5 (flag VIOLATED if any < 5) |
| `FISHER_EXACT` | `scipy.stats.fisher_exact` (2×2); `scipy.stats.fisher_exact`/R Fisher–Freeman–Halton (R×C) | **By `table_shape`:** 2×2 → odds ratio, 95% CI via Baptista–Pike; R×C → Cramér's V (OR undefined) | No expected-count floor needed; R×C uses the Fisher–Freeman–Halton generalisation |
| `MCNEMAR` | `statsmodels.stats.contingency_tables.mcnemar` | Odds ratio of discordant pairs; bootstrap CI | Paired structure, ≥ 25 discordant pairs |
| `PEARSON_CORRELATION` | `scipy.stats.pearsonr` | r is its own effect size; Fisher's z 95% CI | Bivariate normality (Shapiro-Wilk on both, diagnostic) |
| `SPEARMAN_CORRELATION` | `scipy.stats.spearmanr` | ρ is its own effect size; bootstrap CI (n=1000) | Continuity (no ties > 5%) |
| `POISSON_REGRESSION` | `statsmodels` GLM (Poisson family) with `log(exposure)` offset | Incidence-rate ratio = exp(β); Wald CI back-transformed | Variance ≈ mean (overdispersion check — flag if var ≫ mean → recommend NegBin) |
| `NEGATIVE_BINOMIAL_REGRESSION` | `statsmodels` GLM (NegBin) / `NegativeBinomial`, with offset | IRR = exp(β); CI back-transformed | Estimate dispersion α; counts non-negative integers |
| `LOG_RANK` | `lifelines.statistics.logrank_test` | Mantel–Haenszel hazard ratio + KM median per group | Non-informative censoring; PH (note if curves cross) |
| `COX_REGRESSION` | `lifelines.CoxPHFitter` | Hazard ratio = exp(β); CI back-transformed | PH via scaled Schoenfeld residuals (`check_assumptions`); flag VIOLATED |
| `ROC_AUC` | `sklearn.metrics.roc_auc_score` + DeLong | AUC; DeLong 95% CI; DeLong test to compare two AUCs | Binary reference standard; report sens/spec/LR at chosen threshold |
| `MAXBET` | `rpy2` → R `BET::MaxBET` | BET symmetry statistic + depth; normalised MI as supplementary | Continuity, N ≥ 20, depth ≤ ⌊log₂(N)⌋ |
| `BEAST` | `rpy2` → R `BET::BEAST` (reachable via explicit override only) | BET symmetry statistic + depth; normalised MI as supplementary | Continuity, N ≥ 20, depth ≤ ⌊log₂(N)⌋ |
| `LINEAR_REGRESSION` | — | — | Raises `NotImplementedError("planned for v0.2.0")` |
| `LOGISTIC_REGRESSION` | — | — | Raises `NotImplementedError("planned for v0.2.0")` |
| `LINEAR_MIXED_MODEL` / `GENERALIZED_ESTIMATING_EQUATIONS` | — | — | Raises `NotImplementedError("clustered/longitudinal — planned for v0.2.0")` |

> No single-depth `BET` member exists in the enum (it is not reachable from the §6 tree). The BET family is `MAXBET` (default) and `BEAST` (override).

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
| `test_welch_anova_known` | Verified against R `oneway.test(var.equal=FALSE)` + Games–Howell |
| `test_anova_known` | Verified against R `aov` + `TukeyHSD` (`force_student` override path) |
| `test_kruskal_known` | Verified against R `kruskal.test` + Dunn |
| `test_chi_squared_rxc_known` | R×C: verified against R `chisq.test`; effect size = Cramér's V |
| `test_chi_squared_2x2_odds_ratio` | 2×2 χ²: reports Cramér's V **and** odds ratio (+ φ) |
| `test_fisher_exact_2x2_known` | 2×2: verified against R `fisher.test`; effect size = odds ratio |
| `test_fisher_rxc_cramers_v` | R×C: Fisher–Freeman–Halton path; effect size = Cramér's V (OR undefined) |
| `test_mcnemar_known` | Verified against R `mcnemar.test` |
| `test_pearson_known` | Verified against R `cor.test(method="pearson")` |
| `test_spearman_known` | Verified against R `cor.test(method="spearman")` |
| `test_maxbet_known` | `pytest.mark.skipif(no rpy2)` — verified against R `BET::MaxBET` |
| `test_poisson_irr_known` | Counts + offset → IRR verified against R `glm(family=poisson)` |
| `test_negative_binomial_overdispersed` | Overdispersed counts → NegBin IRR; α dispersion estimated |
| `test_logrank_known` | Verified against R `survival::survdiff`; HR + KM medians |
| `test_cox_hr_known` | Verified against R `survival::coxph`; HR; PH check recorded |
| `test_ph_violation_flagged` | Crossing hazards → PH `AssumptionStatus.VIOLATED` |
| `test_roc_auc_known` | AUC + DeLong CI verified against R `pROC::roc` / `ci.auc` |
| `test_assumption_violations_flagged` | Non-normal data → `AssumptionStatus.VIOLATED` in checks |
| `test_posthoc_in_notes` | `WELCH_ANOVA` result → Games–Howell (Holm) table string in `TestResult.notes` |
| `test_sensitivity_power_in_notes` | WELCH_T result → sensitivity MDE in `TestResult.notes` |
| `test_linear_regression_not_implemented` | Raises `NotImplementedError` |
| `test_mixed_model_not_implemented` | `LINEAR_MIXED_MODEL` / GEE raise `NotImplementedError` |
| `test_publishes_event` | `EVENT_TEST_EXECUTED` fired with correct payload |

**Gate:** `pytest tests/test_executor.py` → 26 passing (BET/MaxBET test may be skipped if R absent), 0 failing.

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

### Healthcare caveat catalog (appended after the general rules — mirrors §6.7)

Keyed off data form / design / assumption result, so they are reproducible (not LLM-invented):

| # | Severity | Trigger | Message |
|---|---|---|---|
| H1 | `WARNING` | Outcome is an areal/region rate (`GEOSPATIAL` strata) | Ecological fallacy — area-level association need not hold for individuals. |
| H2 | `INFO` | Aggregated areal units | MAUP — associations can shift with the choice/scale of areal units. |
| H3 | `WARNING` | Areal data with neighbours | Spatial autocorrelation understates SEs (Moran's I); consider spatial/cluster-robust inference. |
| H4 | `INFO` | `POISSON_REGRESSION` selected | Verify variance ≈ mean; prefer negative binomial if overdispersed. |
| H5 | `WARNING` | PH check VIOLATED (Cox/log-rank) | Non-proportional hazards — a single HR is misleading; consider time-varying effects or RMST. |
| H6 | `INFO` | Any survival analysis | Censoring assumed non-informative; verify dropout is unrelated to prognosis. |
| H7 | `WARNING` | Ratio measure significant but absolute effect small / NNT large | Significant but small absolute benefit — judge against the MCID. |
| H8 | `INFO` | Diagnostic with PPV/NPV | Predictive values depend on prevalence; state the operating prevalence. |
| H9 | `WARNING` | Clustering / repeated-measures key detected | Non-independent observations — naive tests understate SEs; mixed/GEE indicated (v0.2.0). |

### Reporting standard

Set `report.study_design.reporting_standard` from the design (EQUATOR, §6.6): RCT → CONSORT;
observational → STROBE; diagnostic → STARD; prediction model → TRIPOD; systematic review →
PRISMA. The `methods_text` should follow that guideline's checklist and name it.

### Plot specs to generate

| Test type | Plots |
|---|---|
| Two-group comparison | Boxplot (groups × outcome), QQ-plot per group |
| Correlation / BET | Scatter (x vs y) |
| 3+ groups | Boxplot (all groups), QQ-plot per group |
| Categorical | Stacked bar (counts), mosaic optional |
| Count / rate | Bar of rates (+ offset), residual check for overdispersion |
| Time-to-event | Kaplan–Meier survival curves per group (step plot) |
| Diagnostic | ROC curve (with AUC) |
| Geospatial outcome/exposure | Heatmap / choropleth of the areal field |

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
| `test_caveat_ecological_fallacy` | GEOSPATIAL areal-rate outcome → H1 WARNING caveat |
| `test_caveat_ph_violation` | Cox result with PH VIOLATED → H5 WARNING caveat |
| `test_caveat_nnt_large` | Significant ratio + large NNT → H7 WARNING caveat |
| `test_reporting_standard_observational` | OBSERVATIONAL → `reporting_standard == "STROBE"` |
| `test_reporting_standard_rct` | Randomised → `reporting_standard == "CONSORT"` |
| `test_plot_spec_survival_km` | TIME_TO_EVENT result → Kaplan–Meier curve spec |
| `test_plot_spec_geospatial_heatmap` | GEOSPATIAL field → heatmap/choropleth spec |
| `test_dry_run_stubs` | dry_run=True → stub strings in summary and methods |
| `test_publishes_event` | `EVENT_REPORT_READY` fired with correct payload |

**Gate:** `pytest tests/test_reporter.py` → 17 passing, 0 failing.

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
- `rpy2>=3.5.0` (BET / MaxBET / BEAST)
- `scikit-posthocs>=0.9.0` (Dunn's test)
- `lifelines>=0.27` (survival: log-rank, Cox PH, Kaplan–Meier)
- `scikit-learn>=1.3` (ROC / AUC for diagnostic accuracy)
- (`statsmodels` — already present — covers Poisson / negative-binomial GLMs)

Add to `[project.optional-dependencies].dev`:
- No new dev-only additions needed.

---

*Last updated: 2026-06-04. Healthcare data-form coverage (Step 1c + §6.5–§6.7) added; ready for review before implementation continues.*
