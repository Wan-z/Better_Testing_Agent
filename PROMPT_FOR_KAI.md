# Integration task: connect the statistical engine to the web backend

## Background

This repo has two independent layers that are not yet connected:

**Layer 1 — statistical engine** (your work):
- `src/hta/bet_screen.py` — BET nonlinear independence engine (pure Python, no numpy/scipy)
- `src/hta/models/` — Pydantic models: `DataProfile`, `StudyDesign`, `TestResult`, `Report`, `PlotSpec`, etc.
- `playground/pipeline.py` — working profiler + test-selector logic (uses the BET engine)

**Layer 2 — web backend** (stub, not yet real):
- `web/backend/api/sessions.py` — CSV upload + variable selection (has its own inline profiler that ignores `bet_screen` and the new `VariableType` variants)
- `web/backend/api/run.py` — **always returns `STUB_REPORT`** regardless of the uploaded data
- `web/backend/api/dialogue.py` — LLM dialogue (already working, do not touch)
- `web/backend/api/export.py` — HTML export (already working, do not touch)
- `web/backend/plots.py` — `plotspec_to_plotly(spec)` converts a PlotSpec dict to Plotly JSON (already working)
- `web/backend/storage/local.py` — file-based session storage; key methods: `read(session_id, filename)`, `write_json(session_id, filename, data)`, `exists(session_id, filename)`, `set_status(session_id, status)`

**The task**: replace the stub in `run.py` with a real pipeline, and upgrade the profiler in `sessions.py` to use the engine from `playground/pipeline.py` and `bet_screen.py`.

---

## What each session directory contains (after a full user flow)

```
web/data/sessions/{uuid}/
  metadata.json       # {"status": "RUNNING"|"COMPLETE", "dialogue_turn": N, ...}
  data.csv            # raw uploaded CSV (bytes)
  preview.json        # {"columns": [...], "inferred_types": {...}, "preview": [...]}
  variables.json      # {"outcome_variable": "score", "group_variable": "treatment", "hypothesis": "..."}
  profile.json        # DataProfile dict (written by set_variables endpoint)
  design.json         # StudyDesign dict (written by dialogue endpoint when LLM captures design)
  report.json         # Report dict (written by run endpoint — currently the stub)
```

All files are plain JSON dicts (not Pydantic — use `.model_dump()` to write, `Model(**data)` to read).

---

## Task 1 — Upgrade the profiler in `sessions.py`

**File**: `web/backend/api/sessions.py`

The `_build_profile()` and `_infer_types()` functions are inline and incomplete. Replace them with a version that:

1. **Uses `playground/pipeline.py::profile_column`** for type inference per column. This correctly detects `COUNT`, `IDENTIFIER`, `ORDINAL`, `BINARY`, `CATEGORICAL`, `CONTINUOUS` — the full `VariableType` enum in `src/hta/models/data.py`. The current inline version only knows 4 types and misses COUNT and IDENTIFIER.

2. **Runs `hta.bet_screen.pairwise_screen`** over all numeric column pairs to populate `DataProfile.nonlinear_dependencies`. Call it as:
   ```python
   from hta.bet_screen import pairwise_screen
   # columns: dict[str, list[float]] — only CONTINUOUS/ORDINAL/COUNT columns
   findings = pairwise_screen(numeric_columns, max_pairs=60, seed=0)
   # returns list[PairwiseDependence] — each has: x, y, n, bet_statistic_s, bet_z,
   # p_value, bid, form, direction, pearson_r, spearman_rho, nonlinear_only, significant
   ```
   Map each `PairwiseDependence` to a `DependenceFinding` dict using `src/hta/models/data.py`.

3. Keep using scipy for the formal normality tests (Shapiro-Wilk / Anderson-Darling) — those stay.

4. The output must still be a plain dict matching `DataProfile` shape so the existing Jinja2 HTML template and frontend continue to work unchanged.

**Important**: `profile_column` in `playground/pipeline.py` operates on `list[str]` (raw CSV strings). The pandas DataFrame has already parsed the CSV. Either pass `df[col].astype(str).tolist()` to reuse it, or replicate the type-inference logic directly — whichever is cleaner.

---

## Task 2 — Replace the stub run pipeline in `run.py`

**File**: `web/backend/api/run.py`

Currently `_run_dry_run` always yields `STUB_REPORT`. Replace `_run_live` (create it) with a real async generator that:

### Step A — Load session data
```python
import io, json
import pandas as pd

profile = json.loads(store.read(session_id, "profile.json"))
design  = json.loads(store.read(session_id, "design.json"))
variables = json.loads(store.read(session_id, "variables.json"))
raw_csv = store.read(session_id, "data.csv")
df = pd.read_csv(io.BytesIO(raw_csv))
outcome = variables.get("outcome_variable")
group   = variables.get("group_variable")
hypothesis = variables.get("hypothesis", "")
```

### Step B — Select test (stream progress event first)
```python
yield _sse({"type": "progress", "stage": "selecting_test", "message": "Selecting statistical test…"})
```

Use `playground/pipeline.py::select()` to pick the test:
```python
import sys; sys.path.insert(0, "src")
from playground.pipeline import profile_column, select, Column
# build cols dict and raw dict from df
cols: dict[str, Column] = {c: profile_column(c, df[c].astype(str).tolist()) for c in df.columns}
raw: dict[str, list[str]] = {c: df[c].astype(str).tolist() for c in df.columns}
selection = select(cols, outcome, group, None, hypothesis, raw)
# selection.test  → e.g. "WELCH_T", "MAXBET", "SPEARMAN_CORRELATION", etc.
# selection.rationale → string
# selection.caveats → list[str]
# selection.computed → dict[str, str] (for association tests: Pearson r, Spearman ρ, BET)
```

### Step C — Execute the test
```python
yield _sse({"type": "progress", "stage": "executing_test", "message": f"Running {selection.test}…"})
```

Build a new module **`web/backend/executor.py`** with a function:
```python
def execute(
    test_name: str,
    df: pd.DataFrame,
    outcome: str,
    group: str | None,
    design: dict,
    selection,   # playground.pipeline.Selection
) -> dict:       # TestResult shape
```

Implement at minimum the following tests using `scipy.stats` and `statsmodels`:

| `test_name` | Implementation |
|-------------|----------------|
| `WELCH_T` | `scipy.stats.ttest_ind(a, b, equal_var=False)` → Cohen's d with bootstrap 95% CI |
| `MANN_WHITNEY_U` | `scipy.stats.mannwhitneyu(a, b, alternative='two-sided')` → rank-biserial r |
| `PAIRED_T` | `scipy.stats.ttest_rel(a, b)` → Cohen's d |
| `WILCOXON_SIGNED_RANK` | `scipy.stats.wilcoxon(a, b)` → rank-biserial r |
| `WELCH_ANOVA` | `scipy.stats.alexandergovern(*groups)` → eta-squared |
| `ONE_WAY_ANOVA` | `scipy.stats.f_oneway(*groups)` → eta-squared |
| `KRUSKAL_WALLIS` | `scipy.stats.kruskal(*groups)` → eta-squared (rank-based) |
| `CHI_SQUARED` | `scipy.stats.chi2_contingency(table)` → Cramér's V |
| `FISHER_EXACT` | `scipy.stats.fisher_exact(table)` → odds ratio |
| `MCNEMAR` | `statsmodels.stats.contingency_tables.mcnemar(table)` → odds ratio |
| `PEARSON_CORRELATION` | `scipy.stats.pearsonr(x, y)` → r with Fisher-z 95% CI |
| `SPEARMAN_CORRELATION` | `scipy.stats.spearmanr(x, y)` → ρ with bootstrap 95% CI |
| `MAXBET` | `hta.bet_screen.maxbet(x, y)` → BET z-statistic, p-value; effect = bet_z/sqrt(n) |
| `POISSON_REGRESSION` | `statsmodels.formula.api.glm` with `Poisson()` family → IRR |
| `NEGATIVE_BINOMIAL_REGRESSION` | `statsmodels.formula.api.glm` with `NegativeBinomial()` → IRR |

For each test return a dict matching `TestResult` in `src/hta/models/test.py`:
```python
{
    "test_used": test_name,         # StatisticalTest enum value
    "statistic": float,
    "p_value": float,
    "degrees_of_freedom": float | None,
    "effect_size": {
        "measure_name": str,        # e.g. "Cohen's d", "Cramér's V", "rank-biserial r"
        "value": float,
        "interpretation": str,      # "small" / "medium" / "large" (Cohen 1988 thresholds)
        "ci_lower": float,
        "ci_upper": float,
    },
    "assumption_checks": [...],     # list of AssumptionCheck dicts
    "confidence_interval": [lower, upper],   # 95% CI on the primary estimate
    "is_significant": bool,         # p_value < 0.05
    "power": float | None,
    "notes": [str],
}
```

For tests not in that table (LOG_RANK, COX_REGRESSION, ROC_AUC), return a `TestResult` with `statistic=0`, `p_value=1`, `is_significant=False`, and a note saying "not yet implemented — use dry-run stub".

**Assumption checks** to include per test family:
- Welch/paired/ANOVA: normality (use profile's `normality.is_normal`), sample size ≥ 5 per group, independence (UNTESTABLE if between-subjects)
- Mann-Whitney/Wilcoxon/Kruskal: sample size ≥ 5, independence
- Chi-squared: all expected counts ≥ 5 (compute from contingency table)
- Fisher: 2×2 check (UNTESTABLE), expected counts < 5
- Correlation: linearity (use BET result from `selection.computed`), sample size
- MaxBET: sample size ≥ 8

**Effect size interpretation thresholds** (Cohen 1988):
- Cohen's d: small=0.2, medium=0.5, large=0.8
- Cramér's V: small=0.1, medium=0.3, large=0.5
- rank-biserial r / Pearson r / Spearman ρ: small=0.1, medium=0.3, large=0.5
- eta-squared: small=0.01, medium=0.06, large=0.14

### Step D — Generate report (stream progress event)
```python
yield _sse({"type": "progress", "stage": "generating_report", "message": "Generating report…"})
```

Build a new function **`web/backend/reporter.py::build_report`** with signature:
```python
def build_report(
    profile: dict,
    design: dict,
    test_result: dict,
    selection,           # playground.pipeline.Selection
    df: pd.DataFrame,
    outcome: str,
    group: str | None,
    hypothesis: str,
) -> dict:               # Report shape
```

It should produce:

**`plots`** — list of PlotSpec dicts. At minimum:
- If group comparison: boxplot of outcome by group. Key: `{"plot_type": "boxplot", "title": "...", "x_label": group, "y_label": outcome, "data": {group_name: [values], ...}}`
- If continuous×continuous association: scatter plot of outcome vs predictor. Key: `{"plot_type": "scatter", "title": "...", "x_label": predictor, "y_label": outcome, "data": {"x": [...], "y": [...]}}`
- Q-Q plot of outcome column: `{"plot_type": "qqplot", ...}` using scipy theoretical quantiles

`web/backend/plots.py::plotspec_to_plotly(spec)` already handles boxplot, histogram, scatter, qqplot — pass the raw PlotSpec dict to it in `run.py` before sending the SSE result.

**`caveats`** — list of Caveat dicts. Sources:
- `selection.caveats` → severity "WARNING"
- Confounders in design that have `adjustment_recommended=True` and are not in the model → severity "WARNING"
- If `nonlinear_dependencies` in profile contains pairs involving outcome/group that are significant → severity "INFO"
- If `p_value` between 0.04 and 0.06 → severity "INFO", "marginal result — interpret with caution"

**`plain_language_summary`** — 2–3 sentence template string:
```python
sig = "statistically significant" if test_result["is_significant"] else "not statistically significant"
es = test_result["effect_size"]
summary = (
    f"The analysis used {test_result['test_used'].replace('_', ' ').title()} to test "
    f"the hypothesis: {hypothesis}. "
    f"The result was {sig} (p = {test_result['p_value']:.3f}). "
    f"The effect size was {es['measure_name']} = {es['value']:.2f} "
    f"({es['interpretation']}; 95% CI [{es['ci_lower']:.2f}, {es['ci_upper']:.2f}])."
)
```

**`methods_text`** — 2–3 sentence template covering: test name, why it was chosen (`selection.rationale`), normality assessment method (Shapiro-Wilk / Anderson-Darling from profile), effect size measure and CI method.

### Step E — Save and stream result

```python
report = {
    "data_profile": profile,
    "study_design": design,
    "test_result": test_result,
    "plain_language_summary": ...,
    "caveats": [...],
    "plots": [...],        # PlotSpec dicts WITHOUT plotly_json yet
    "methods_text": ...,
}
# Enrich plots
for plot in report["plots"]:
    plot["plotly_json"] = plotspec_to_plotly(plot)

store.write_json(session_id, "report.json", report)
store.set_status(session_id, "COMPLETE")
yield _sse({"type": "result", "report": report})
```

### Step F — Wire into the router

In `run.py`, update `run_analysis` to call `_run_live` when not in DRY_RUN:
```python
from web.backend.config import DRY_RUN

@router.post("/sessions/{session_id}/run")
async def run_analysis(session_id: str) -> StreamingResponse:
    if not store.exists(session_id, "metadata.json"):
        raise HTTPException(status_code=404, detail="Session not found.")
    store.set_status(session_id, "RUNNING")
    generator = _run_dry_run(session_id) if DRY_RUN else _run_live(session_id)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

---

## Files to create

| File | Purpose |
|------|---------|
| `web/backend/executor.py` | `execute(test_name, df, outcome, group, design, selection) -> dict` |
| `web/backend/reporter.py` | `build_report(profile, design, test_result, selection, df, outcome, group, hypothesis) -> dict` |

## Files to modify

| File | Change |
|------|--------|
| `web/backend/api/sessions.py` | Upgrade `_build_profile` to use `playground.pipeline.profile_column` + BET screen |
| `web/backend/api/run.py` | Add `_run_live`, wire `DRY_RUN` branch |

## Files to leave untouched

`web/backend/api/dialogue.py`, `web/backend/api/export.py`, `web/backend/plots.py`, `web/backend/main.py`, `web/backend/storage/`, `web/backend/templates/`, all of `web/frontend/`, all of `src/hta/`, `playground/`.

---

## Constraints and conventions

- `web/backend/` uses **pandas + scipy + statsmodels** (already installed via `pip install -e ".[web]"`). Do not add new dependencies.
- All session I/O goes through `LocalStorage` — do not open files directly.
- The BET engine (`src/hta/bet_screen.py`) is pure Python with no external imports — it's safe to import anywhere.
- `playground/pipeline.py` is pure stdlib — also safe to import anywhere.
- Keep the `_run_dry_run` path intact and unchanged (used when `DRY_RUN=True`).
- The HTML template (`web/backend/templates/report.html.j2`) and the frontend (`web/frontend/`) must continue to work without changes — the report JSON structure must remain compatible.
- Do not add `async` to `executor.py` or `reporter.py` — call them from the `async` generator in `run.py` directly (they're CPU-bound and fast enough).
- Bootstrap CIs: use `n_bootstrap=1000` with `random.seed(42)` (no numpy — use `random.choices`).

---

## Verification

After implementing, run:
```bash
# Unit tests must still pass
pytest tests/ -q --override-ini="addopts="

# Manual end-to-end: start the backend and test with the included datasets
uvicorn web.backend.main:app --port 8000 --reload

# Upload and run through curl (dry-run off)
SESSION=$(curl -s -X POST http://localhost:8000/api/sessions \
  -F "file=@data/bright_stars.csv" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

curl -s -X PATCH "http://localhost:8000/api/sessions/$SESSION/variables" \
  -H "Content-Type: application/json" \
  -d '{"outcome_variable":"sin_latitude","group_variable":null,"hypothesis":"Stars are uniformly distributed"}'

# Skip dialogue — write a stub design directly for testing
curl -sN -X POST "http://localhost:8000/api/sessions/$SESSION/run" | grep '"type"'
# Should see: selecting_test → executing_test → generating_report → result
# The result report should have test_used != "WELCH_T" (stub) — likely PEARSON or MAXBET
```
