# Hypothesis Testing Agent (HTA)

An AI-powered statistical reasoning system that acts as a rigorous collaborator for researchers.
HTA reasons about study design and causal structure before selecting and executing the right
statistical test, then produces a comprehensive report with effect sizes, assumption checks,
caveats, and a methods text ready to paste into a manuscript.

## How it works

```
Upload CSV → Select variables → Design dialogue (LLM) → Statistical test → Report
```

A conversational LLM elicits study design information (experimental vs observational,
measurement type, confounders, relationship form). This drives test selection. The full
pipeline streams results in real time and exports a self-contained HTML report.

## Pipeline architecture

```
DataProfiler → DesignDialogue → TestSelector → TestExecutor → Reporter
     ↓               ↓               ↓              ↓            ↓
DataProfile    StudyDesign    StatisticalTest   TestResult    Report
```

All modules share Pydantic models (`src/hta/models/`) as a lingua franca.

## Supported tests

| Test | Conditions |
|------|-----------|
| Welch's t-test | Continuous outcome, 2 independent groups (default) |
| Mann–Whitney U | Non-normal / ordinal, 2 groups |
| Paired t-test | Within-subjects, continuous |
| Wilcoxon signed-rank | Within-subjects, non-normal |
| Welch's ANOVA | Continuous, ≥ 3 groups (default; no equal-variance assumption) |
| One-way ANOVA | Continuous, ≥ 3 groups (equal-variance, explicit override) |
| Kruskal–Wallis | Non-parametric, ≥ 3 groups |
| Chi-squared | Categorical × categorical (expected ≥ 5) |
| Fisher's exact | 2×2 contingency (expected < 5) |
| McNemar | Paired binary |
| Pearson correlation | Linear, bivariate continuous |
| Spearman correlation | Monotone / ordinal |
| MaxBET | Nonlinear independence (nonparametric) |
| Poisson regression | Count / rate outcome (incidence-rate ratio) |
| Negative binomial regression | Overdispersed count / rate outcome (IRR) |
| Log-rank test | Time-to-event, group comparison |
| Cox proportional hazards | Time-to-event, covariate-adjusted (hazard ratio) |
| ROC / AUC | Diagnostic accuracy (DeLong CI; DeLong test to compare AUCs) |

*Reserved for v0.2.0:* linear/logistic regression, linear mixed models and GEE
(clustered / longitudinal data).

## Data forms & healthcare specialization

HTA is **general** — it profiles any tabular dataset and routes continuous, ordinal,
and categorical outcomes through the classical decision tree regardless of domain. On
top of that it is **specialized for healthcare and epidemiology**: the data forms that
dominate clinical work are first-class, not coerced into mean comparisons.

| Data form (`VariableType`) | How it's handled |
|------|-----------|
| Continuous / Ordinal / Categorical / Binary | Classical tree (t / ANOVA / correlation / χ² …) |
| **Count / rate** (`COUNT`) | Poisson or negative-binomial regression with a rate offset → **incidence-rate ratio** |
| **Time-to-event** (`TIME_TO_EVENT`) | Kaplan–Meier + log-rank / Cox, censoring-aware → **hazard ratio** |
| **Geospatial** (`GEOSPATIAL`) | Drives maps/heatmaps; flags ecological fallacy, MAUP, spatial autocorrelation |
| **Datetime / Identifier** | Used to derive durations / excluded from testing — never mis-analysed as numbers |

Healthcare results carry the effect measures a reviewer expects (RR, OR, HR, IRR, NNT, AUC),
note statistical-vs-clinical significance (MCID), map the design to a reporting guideline
(CONSORT / STROBE / STARD / TRIPOD / PRISMA), and add domain caveats (ecological fallacy,
non-proportional hazards, informative censoring, prevalence-dependence). See
[`TECHNICAL_REPORT.md` §6.5–§6.7](TECHNICAL_REPORT.md).

### Exploratory dependence analysis (BET)

Before any test is chosen, the profiler runs a **Binary Expansion Testing** screen
(`src/hta/bet_screen.py`) over the numeric columns, following
[Xiang, Zhang, Liu, Hoadley, Perou, Zhang & Marron (2023), *Ann. Appl. Stat.* 17(4), DOI 10.1214/23-AOAS1745](https://projecteuclid.org/journals/annals-of-applied-statistics/volume-17/issue-4/Pairwise-nonlinear-dependence-analysis-of-genomic-data/10.1214/23-AOAS1745.full) (preprint [arXiv:2202.09880](https://arxiv.org/abs/2202.09880)). For
every pair it copula-transforms the data (jittering ties / zero-inflation), runs depth-2
MaxBET, and reports the **form** of dependence (monotone, parabolic, "W"-bimodal,
checkerboard, linear) with its direction — flagging **nonlinear-only** pairs that Pearson and
Spearman miss. Mixture-type forms prompt the dialogue to ask which **subgroups/subtypes** drive
the pattern (captured for stratified analysis), and the dominant form becomes the selector's
relationship prior. This is the agent's effect-modification / heterogeneity step.

## Requirements

- Python ≥ 3.11
- Node.js ≥ 20 (web frontend only)
- Azure OpenAI access (GPT-5.4 endpoint)

## Installation

```bash
git clone git@github.com:zhengwu/Better_Testing_Agent.git
cd Better_Testing_Agent

# Conda environment (recommended)
conda create -n hta python=3.11 && conda activate hta

# Core + dev tools
pip install -e ".[dev]"

# Web backend (FastAPI, Jinja2, …)
pip install -e ".[web]"

# Frontend
cd web/frontend && npm install
```

## Configuration

Create a `.env` file in the project root:

```bash
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-5.4

# Optional overrides
HTA_DEFAULT_DRY_RUN=false   # true = use stub data, no API calls
HTA_SESSION_TTL_DAYS=7
HTA_LOG_LEVEL=INFO
```

`HTA_DEFAULT_DRY_RUN=true` runs the full pipeline with realistic stub data — no API key needed.

## Running the web app

```bash
# Terminal 1 — FastAPI backend (port 8000)
uvicorn web.backend.main:app --port 8000 --reload

# Terminal 2 — Vite dev server (port 5173, proxies /api → backend)
cd web/frontend && npm run dev
```

Open **http://localhost:5173** in your browser.

To export a report: click **Download Report (HTML)** on the results page. The file is
self-contained (inline CSS + Plotly CDN) and prints cleanly to PDF.

## Docker (production)

```bash
cd web
docker compose up --build
# → frontend at :80, backend at :8000
```

## Running tests

```bash
pytest                          # all tests with coverage
pytest tests/test_models.py -v  # models only
```

## Code quality

```bash
ruff check src/        # linting
mypy src/hta           # type checking
```

## Project layout

```
src/hta/
  models/           Shared Pydantic data models
  bus.py            Pub/sub event bus
  bet_screen.py     BET pairwise nonlinear-dependence EDA engine (pure stdlib)
  modules/          DataProfiler, DesignDialogue, TestSelector, TestExecutor, Reporter
  agent.py          Top-level orchestrator
  cli.py            Typer CLI
web/
  backend/
    api/            FastAPI routers (sessions, dialogue, run, export)
    storage/        StorageBackend protocol + LocalStorage implementation
    templates/      Jinja2 HTML report template
    main.py         FastAPI app entry point
  frontend/
    src/
      api/          client.ts — real fetch/SSE calls; mock.ts — stub data
      components/   Wizard steps, Results view, Landing, About
      hooks/        useSession — all session state + streaming logic
      types/        TypeScript types mirroring Pydantic models
  docker-compose.yml
  Dockerfile.backend / Dockerfile.frontend
data/               Example dataset + generator (see data/README.md)
tests/              pytest test suite
TECHNICAL_REPORT.md Statistical methodology and design decisions
IMPLEMENTATION_PLAN.md Step-by-step build guide
```

## Example dataset

[`data/overdose_ed_visits.csv`](data/README.md) is a **synthetic** NC county dataset
(100 counties) for demonstrating the agent on a public-health question: *is OUD treatment
clinic density associated with the nonfatal overdose ED visit rate?* It drives the dry-run
web demo, which selects **Spearman's correlation** (ρ ≈ −0.67) and renders a
**clinic-density heatmap** alongside the scatter plot. Values are simulated for
demonstration only — not real surveillance data. Regenerate with
`python data/generate_dataset.py`.

## Design decisions

Key choices are documented in [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md):

- **Welch's t-test / Welch's ANOVA as unconditional defaults** — no equal-variance pre-test
- **No formal normality test above N = 2 000** — Shapiro-Wilk corroborates below that; above it, severity comes from skew/kurtosis magnitude (a one-sample KS/Shapiro vs estimated parameters is invalid there)
- **Normality as a graded signal** (`NONE`/`MILD`/`STRONG`) — informs but does not gate test selection
- **MaxBET** for nonlinear independence testing (BEAST reachable via explicit override)
- **Always-on post-hoc, Holm-adjusted** — Games–Howell (Welch ANOVA) / Tukey HSD (pooled ANOVA) / Dunn (Kruskal–Wallis)
- **Effect sizes with bootstrap CIs** on every result

## Contributing

1. All public functions must have type annotations.
2. Every module gets a corresponding `tests/test_<module>.py`.
3. Run `ruff check` and `mypy` before opening a PR.
4. Statistical decision points go in `TECHNICAL_REPORT.md`.
