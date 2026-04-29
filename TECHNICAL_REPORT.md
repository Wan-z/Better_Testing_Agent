# Hypothesis Testing Agent — Technical Report

**Version:** 0.1.0-dev  
**Date:** 2026-04-29  
**Status:** Step 1 of 8 complete  
**Authors:** Development team + three statistician co-investigators (review pending)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Design Principles](#2-design-principles)
3. [System Architecture](#3-system-architecture)
4. [Data Models](#4-data-models)
5. [Module Specifications](#5-module-specifications)
6. [Statistical Decision Logic](#6-statistical-decision-logic)
7. [Claude API Integration](#7-claude-api-integration)
8. [Development Standards](#8-development-standards)
9. [Completed Work](#9-completed-work)
10. [Planned Work](#10-planned-work)
11. [Definition of Done](#11-definition-of-done)
12. [Environment Setup](#12-environment-setup)

---

## 1. Project Overview

The **Hypothesis Testing Agent (HTA)** is an AI-powered statistical reasoning system designed to act as a rigorous methodological collaborator for researchers. Its distinguishing characteristic is that it reasons about *study design and causal structure first*, before selecting or executing any statistical test.

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
| **Event bus decoupling** | Modules never import each other. All inter-module communication is via pub/sub events. This allows any module to be swapped or mocked independently. |
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

### Event Flow

All modules communicate via the **EventBus** (`bus.py`). The canonical events and their payloads are:

| Event constant | String name | Payload type | Published by |
|---|---|---|---|
| `EVENT_DATA_PROFILED` | `data.profiled` | `DataProfile` | `DataProfiler` |
| `EVENT_DESIGN_CAPTURED` | `design.captured` | `StudyDesign` | `DesignDialogue` |
| `EVENT_GRAPH_BUILT` | `causal.graph_built` | `CausalGraph` | `CausalAnalyser` |
| `EVENT_TEST_SELECTED` | `test.selected` | `StatisticalTest` | `TestSelector` |
| `EVENT_TEST_EXECUTED` | `test.executed` | `TestResult` | `TestExecutor` |
| `EVENT_REPORT_READY` | `report.ready` | `Report` | `Reporter` |

### Repository Layout

```
hypothesis-testing-agent/
├── .env.example              # Template for environment variables
├── .gitignore
├── README.md
├── TECHNICAL_REPORT.md       # This document
├── STATISTICIAN_REVIEW.md    # Decision points for expert validation (Step 8)
├── BENCHMARK_CASES.md        # 20 test cases for evaluation (Step 8)
├── pyproject.toml
├── src/
│   └── hta/
│       ├── __init__.py
│       ├── models/           # Shared Pydantic data models  ← Step 1 ✅
│       │   ├── data.py
│       │   ├── design.py
│       │   ├── test.py
│       │   └── report.py
│       ├── bus.py            # Event bus                    ← Step 2
│       ├── modules/
│       │   ├── profiler.py   # Data ingestion & profiling   ← Step 3
│       │   ├── dialogue.py   # Study design dialogue        ← Step 4
│       │   ├── causal.py     # Causal graph & confounders   ← Step 4
│       │   ├── selector.py   # Test selection logic         ← Step 5
│       │   ├── executor.py   # Statistical test execution   ← Step 6
│       │   └── reporter.py   # Report assembly              ← Step 7
│       ├── agent.py          # Top-level orchestrator       ← Step 8
│       └── cli.py            # CLI entry point              ← Step 8
├── tests/
│   ├── conftest.py           # Shared fixtures              ← Step 1 ✅
│   ├── test_models.py        # Model tests (68 passing)     ← Step 1 ✅
│   ├── test_bus.py                                          ← Step 2
│   ├── test_profiler.py                                     ← Step 3
│   ├── test_dialogue.py                                     ← Step 4
│   ├── test_selector.py                                     ← Step 5
│   ├── test_executor.py                                     ← Step 6
│   ├── test_reporter.py                                     ← Step 7
│   └── test_agent.py                                        ← Step 8
└── examples/
    ├── two_group_comparison.py                              ← Step 8
    ├── categorical_association.py                           ← Step 8
    └── paired_before_after.py                               ← Step 8
```

---

## 4. Data Models

All shared data structures are defined in `src/hta/models/` as **Pydantic v2** models. These are the single source of truth for every inter-module data exchange. Statistician co-investigators should focus their review here.

### 4.1 Data models (`models/data.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `VariableType` | Enum: measurement level | `CONTINUOUS`, `ORDINAL`, `CATEGORICAL`, `BINARY` |
| `DistributionStats` | Descriptive statistics | mean, std, median, IQR, skewness, kurtosis, min, max |
| `NormalityTest` | Formal normality test result | name, statistic, p_value, `is_normal` (p > 0.05) |
| `Variable` | Single variable profile | name, type, n, n_missing, distribution_stats, normality, unique_values |
| `DataProfile` | Full dataset profile | variables, n_groups, group_var, outcome_var, notes (quality flags) |

### 4.2 Design models (`models/design.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `StudyDesignType` | Enum | `EXPERIMENTAL`, `OBSERVATIONAL`, `QUASI_EXPERIMENTAL` |
| `MeasurementType` | Enum | `BETWEEN_SUBJECTS`, `WITHIN_SUBJECTS`, `MIXED` |
| `VariableRole` | Enum: causal role | `CONFOUNDER`, `COLLIDER`, `MEDIATOR`, `EFFECT_MODIFIER`, `COVARIATE` |
| `Confounder` | One causal variable | name, role, is_measured, adjustment_recommended, rationale |
| `StudyDesign` | Captured study design | design_type, measurement_type, is_randomized, confounders, notes |
| `CausalGraph` | DAG structure | nodes, edges (ordered pairs), adjustment_set, warnings |

### 4.3 Test models (`models/test.py`)

| Model | Purpose | Key fields |
|---|---|---|
| `StatisticalTest` | Enum: 14 tests | see §6 |
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
- Infer variable type: BINARY (2 unique), CATEGORICAL (≤20 unique, non-numeric), ORDINAL (numeric, ≤10 unique), CONTINUOUS (else)
- Normality testing: Shapiro-Wilk for N ≤ 2000; Kolmogorov-Smirnov for N > 2000
- Compute all `DistributionStats` fields
- Flag data quality issues: >5% missingness, constant variables, outliers (|Z| > 3.5)
- Group-level statistics when a group variable is specified

### 5.2 DesignDialogue (`modules/dialogue.py`) — Step 4

**Inputs:** `DataProfile`, free-text hypothesis description  
**Outputs:** `StudyDesign` (published as `EVENT_DESIGN_CAPTURED`)

Responsibilities:
- Multi-turn dialogue with the user, powered by the Claude API
- Enforces a structured protocol (see §7.1)
- Terminates when Claude calls the `capture_study_design` tool with enough information
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
- Provides a human-readable `get_selection_rationale()` explaining the choice
- Statistician Reviewer A will validate this decision tree

### 5.5 TestExecutor (`modules/executor.py`) — Step 6

**Inputs:** `pd.DataFrame`, `StatisticalTest`, group/outcome variable names, `StudyDesign`  
**Outputs:** `TestResult` (published as `EVENT_TEST_EXECUTED`)

Responsibilities:
- Executes the selected test using scipy, pingouin, or statsmodels
- Computes appropriate effect size with 95% CI (see §6 for per-test details)
- Runs and records all relevant assumption checks before the main test
- Reports power when computable

### 5.6 Reporter (`modules/reporter.py`) — Step 7

**Inputs:** `DataProfile`, `StudyDesign`, `TestResult`  
**Outputs:** `Report` (published as `EVENT_REPORT_READY`)

Responsibilities:
- Deterministic caveat generation (6 rules, see §5.6.1)
- Declarative plot specification generation (no rendering — just `PlotSpec` objects)
- Claude API calls for `plain_language_summary` and `methods_text` (dry-run returns stubs)

#### 5.6.1 Caveat generation rules

| Severity | Condition |
|---|---|
| `CRITICAL` | Any `AssumptionCheck` has `status == VIOLATED` |
| `WARNING` | `power < 0.80` when computable |
| `WARNING` | `0.01 ≤ p_value ≤ 0.05` (marginal result) |
| `WARNING` | Effect size is small (Cohen's d < 0.2 or Cramér's V < 0.1) and result is significant |
| `INFO` | Multiple groups tested without multiple-comparison correction |
| `INFO` | Study is observational (flag potential for causal language misuse) |

---

## 6. Statistical Decision Logic

The test selection decision tree (implemented in `selector.py`). This is the primary artefact for statistician review.

```
if outcome is CONTINUOUS:
    if two groups:
        if WITHIN_SUBJECTS or paired:
            if normal  → PAIRED_T
            else       → WILCOXON_SIGNED_RANK
        else (BETWEEN_SUBJECTS):
            if normal and equal variances  → INDEPENDENT_T
            if normal and unequal variances → WELCH_T
            if non-normal                  → MANN_WHITNEY_U
    if 3+ groups:
        if normal  → ONE_WAY_ANOVA
        else       → KRUSKAL_WALLIS
    if continuous predictor (correlation):
        if normal  → PEARSON_CORRELATION
        else       → SPEARMAN_CORRELATION

if outcome is BINARY or CATEGORICAL:
    if two categorical variables:
        if all expected cell counts ≥ 5  → CHI_SQUARED
        else                             → FISHER_EXACT
    if paired binary outcome             → MCNEMAR
```

### Effect size implementations

| Test | Effect size | Method |
|---|---|---|
| INDEPENDENT_T | Cohen's d | Pooled SD; CI via bootstrapping |
| WELCH_T | Cohen's d | Pooled SD; CI via bootstrapping |
| PAIRED_T | Cohen's d_z | Within-subject SD |
| MANN_WHITNEY_U | Rank-biserial r | `(2U)/(n₁n₂) − 1` |
| WILCOXON_SIGNED_RANK | Matched-pairs rank-biserial r | Cliff's delta variant |
| ONE_WAY_ANOVA | η² and ω² | SS decomposition |
| KRUSKAL_WALLIS | ε² | `(H − k + 1) / (n − k)` |
| CHI_SQUARED | Cramér's V | `√(χ²/n·min(r−1,c−1))` |
| FISHER_EXACT | Odds ratio | From contingency table |
| PEARSON_CORRELATION | r (is its own effect size) | Fisher's z CI |
| SPEARMAN_CORRELATION | ρ (is its own effect size) | Bootstrap CI |

---

## 7. Claude API Integration

The Claude API (via the `anthropic` Python SDK) is used in exactly two modules. All other logic is fully deterministic.

### 7.1 DesignDialogue protocol

The system prompt given to Claude enforces the following dialogue rules:

1. Always ask about observational vs. experimental design first.
2. Always ask about independence of observations.
3. If there are multiple variables, always ask which could be confounders.
4. Ask about matching or repeated measures if the user mentions "before/after" or "matched".
5. Never ask more than 3 questions per turn.
6. Stop when `StudyDesign` can be fully populated — signal completion by calling the `capture_study_design` tool.

**Tool use:** The dialogue module defines a `capture_study_design` tool. When Claude calls this tool, the module extracts the structured `StudyDesign` and terminates the loop.

### 7.2 Reporter text generation

Two Claude API calls are made in the reporter:

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
| **No hardcoded secrets** | Credentials loaded from `.env` via `python-dotenv` |
| **Module independence** | No direct imports between modules; only through models + event bus |
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
| `src/hta/models/test.py` | `StatisticalTest` (14 members), `AssumptionStatus`, `AssumptionCheck`, `EffectSize`, `TestResult` |
| `src/hta/models/report.py` | `CaveatSeverity`, `Caveat`, `PlotSpec`, `Report` |
| `src/hta/models/__init__.py` | Re-exports all models |
| `tests/conftest.py` | Shared fixtures for all model types |
| `tests/test_models.py` | 68 tests across 3 categories (see below) |

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

## 10. Planned Work

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
- Infer variable types by the rules in §5.1
- Shapiro-Wilk (N ≤ 2000) or KS test (N > 2000) for normality
- Data quality notes: missingness >5%, constant variables, outliers |Z| > 3.5

**Deliverable:** `tests/test_profiler.py` — normal/skewed distributions, categorical detection, missing data, grouped profiling.

---

### Step 4 — Study design dialogue and causal module

**Goal:** `src/hta/modules/dialogue.py` and `src/hta/modules/causal.py`

Key requirements:
- Dialogue: multi-turn Claude API interaction; tool-call termination
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

**Deliverable:** `tests/test_selector.py` — one test per test type; edge cases for borderline normality and unequal group sizes.

> **Statistician review checkpoint:** Statistician A will validate the decision tree at this step.

---

### Step 6 — Test executor

**Goal:** `src/hta/modules/executor.py` — runs the selected test and returns `TestResult`

Key requirements:
- Implements all 11 test + effect size combinations in §6
- Assumption checks before the main test (normality, variance homogeneity, sample size adequacy)
- Uses scipy, pingouin, and/or statsmodels

**Deliverable:** `tests/test_executor.py` — known datasets verified against reference outputs (R or textbook).

---

### Step 7 — Reporter

**Goal:** `src/hta/modules/reporter.py` — assembles `Report` from upstream outputs

Key requirements:
- All 6 deterministic caveat rules implemented (§5.6.1)
- Generates `PlotSpec` objects for distribution, box plots, QQ-plots, scatter
- Claude API calls for `plain_language_summary` and `methods_text`

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

### First-time setup

```bash
# Option A: conda (recommended — matches development environment)
conda create -n hta python=3.11
conda activate hta
pip install -e ".[dev]"

# Option B: venv
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Copy environment variables
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY
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

*This document is updated at the end of each completed step. Last updated: Step 1.*
