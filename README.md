# Hypothesis Testing Agent (HTA)

An AI-powered statistical reasoning system that acts as a rigorous collaborator for researchers.
It reasons about study design and causal structure before selecting and executing any statistical
test, then produces a comprehensive report with effect sizes, power analysis, and caveats.

## Architecture

```
DataProfiler → DesignDialogue → TestSelector → TestExecutor → Reporter
     ↓               ↓               ↓              ↓            ↓
DataProfile    StudyDesign    StatisticalTest   TestResult    Report
```

All modules communicate via the shared event bus (`src/hta/bus.py`) and the shared Pydantic
models (`src/hta/models/`). No direct imports between modules.

## Requirements

- Python ≥ 3.11
- Access to the shared secrets file at `~/.config/trading-agents/secrets.env`
  (contains `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_DEPLOYMENT`)

The LLM backend is **GPT-5.4 via Azure OpenAI** (UNC endpoint). Credentials are shared
across the trading-agent suite and loaded automatically from the secrets file — no
per-project `.env` setup is required.

## Installation

```bash
git clone git@github.com:zhengwu/Better_Testing_Agent.git
cd Better_Testing_Agent

# Create and activate a virtual environment (conda recommended)
conda create -n hta python=3.11 && conda activate hta

# Install the package with dev dependencies
pip install -e ".[dev]"
```

## Running tests

```bash
pytest                          # run all tests with coverage
pytest tests/test_models.py -v  # run model tests only
```

## Running the CLI (dry-run, no API key needed)

```bash
hta run --dry-run
hta run --data examples/data/bp.csv --hypothesis "Treatment reduces BP" \
        --group group --outcome bp
```

## Code quality

```bash
ruff check src/        # linting
mypy src/hta           # type checking
```

## Project layout

```
src/hta/
  models/     Shared Pydantic data models (lingua franca of the system)
  bus.py      Pub/sub event bus
  modules/    Processing modules (profiler, dialogue, selector, executor, reporter)
  agent.py    Top-level orchestrator
  cli.py      Typer CLI entry point
tests/        pytest test suite
examples/     Runnable example scripts
```

## Contributing

1. All public functions must have type annotations and docstrings.
2. Every module gets a corresponding `tests/test_<module>.py`.
3. Run `ruff check` and `mypy` before opening a PR.
4. Statistical decision points are documented in `STATISTICIAN_REVIEW.md`.
