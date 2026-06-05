# HTA Playground

A tiny, **pure-stdlib** web app to try your own data and prompts against the agent's
logic — no install, no build step, no API key.

```bash
PYTHONPATH=src python playground/app.py            # http://localhost:8000
PYTHONPATH=src python playground/app.py 8090       # choose a port
```

(You can also just run `python playground/app.py` — the app puts `src/` on the path
itself.)

Then open the URL, and either click a **sample** link (stars / gene / overdose) or:

1. Paste a CSV (with a header row).
2. Type your question / hypothesis.
3. Name the **outcome** column, and optionally a **group** column (for a comparison)
   or a **predictor** column (for an association).
4. **Analyse**.

## What it computes

- **Data profile** — variable type (continuous / ordinal / binary / categorical /
  count / identifier), summary stats, and normality *severity* (`NONE`/`MILD`/`STRONG`,
  per `TECHNICAL_REPORT.md` §6.1).
- **Recommended test** — the deterministic §6.2 decision tree (Welch by default, rank
  methods for ordinal / small-N strong-skew, χ²/Fisher by expected counts, Poisson/NegBin
  for counts), with a plain-language rationale and caveats.
- **BET dependence screen** — the *real* engine (`src/hta/bet_screen.py`) over every
  numeric pair: form, direction, BET *z* and adjusted *p*, and a **nonlinear-only** flag
  for pairs that Pearson/Spearman miss. For a chosen continuous pair it also draws the
  **dependence region** (where the points concentrate).

## What it does **not** do

- No LLM calls (the design-dialogue step is mocked away).
- Group comparisons (t / ANOVA / χ²) are **recommended, not executed** — the Step-6
  executor isn't built yet. Correlations and the BET test *are* actually computed.

It is a demo layer over the real BET engine, not the gated Step 3–8 pipeline.
