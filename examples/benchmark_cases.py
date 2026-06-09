"""Benchmark battery for the Hypothesis Testing Agent (Step-8 statistician-review deliverable).

Runs a deterministic set of analyses end-to-end through the agent and prints a Markdown table
of the selected test and its key result for each scenario. These are the reference values
recorded in ``BENCHMARK_CASES.md`` — re-run to regenerate or to check for regressions::

    PYTHONPATH=src python examples/benchmark_cases.py

All data is synthetic and seeded, so the output is reproducible.
"""

from __future__ import annotations

import sys

try:                                            # the report uses ρ, η, α, etc.
    sys.stdout.reconfigure(encoding="utf-8")    # type: ignore[union-attr]
except (AttributeError, ValueError):
    pass

import random
import warnings

warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from hta.agent import HypothesisTestingAgent  # noqa: E402
from hta.models.design import (  # noqa: E402
    Confounder,
    MeasurementType,
    StudyDesign,
    StudyDesignType,
    VariableRole,
)

AGENT = HypothesisTestingAgent()
_ROWS: list[tuple[int, str, str, str, str, str]] = []


def bench(label: str, df: pd.DataFrame, outcome: str, *, group: str | None = None,
          predictor: str | None = None, design: StudyDesign | None = None,
          prompt: str = "benchmark") -> None:
    rep = AGENT.run(df, prompt, outcome, group_variable=group, predictor_variable=predictor,
                    design=design)
    r = rep.test_result
    es = r.effect_size
    p = "<0.001" if r.p_value < 0.001 else f"{r.p_value:.3f}"
    effect = f"{es.measure_name} = {es.value:.3f} ({es.interpretation})"
    _ROWS.append((len(_ROWS) + 1, label, r.test_used.value, f"{r.statistic:.3f}", p, effect))


def _design(dtype: StudyDesignType, randomized: bool = False,
            confounders: list[Confounder] | None = None) -> StudyDesign:
    return StudyDesign(design_type=dtype, measurement_type=MeasurementType.BETWEEN_SUBJECTS,
                       is_randomized=randomized, confounders=confounders or [])


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


# 1 — two independent groups, clearly separated, adequate N → Welch's t (RCT).
_a = [10.2, 11.4, 9.1, 12.3, 10.8, 11.0, 13.1, 9.6, 10.5, 12.0, 10.1, 11.7, 10.9, 11.3]
_b = [20.2, 21.4, 19.1, 22.3, 20.8, 21.0, 23.1, 19.6, 20.5, 22.0, 20.3, 21.6, 20.9, 21.1]
bench("Two groups, continuous, separated (RCT)",
      pd.DataFrame({"arm": ["A"] * len(_a) + ["B"] * len(_b), "bp": _a + _b}), "bp",
      group="arm", design=_design(StudyDesignType.EXPERIMENTAL, randomized=True),
      prompt="does treatment change blood pressure?")

# 2 — two groups, small N, strongly right-skewed → Mann–Whitney U.
_sk = [f"{1.0 + 0.1 * i:.2f}" for i in range(11)] + ["40.0"]
bench("Two groups, small N, strong skew",
      pd.DataFrame({"arm": ["A"] * 12 + ["B"] * 12,
                    "cost": [float(v) for v in _sk] + [float(v) + 3 for v in _sk]}), "cost",
      group="arm")

# 3 — within-subjects before/after → paired t (with realistic within-pair variation).
_pre = [5.0 + (i % 7) * 0.4 for i in range(30)]
_post = [v + 2 + ((i % 5) - 2) * 0.6 for i, v in enumerate(_pre)]
bench("Before/after, within-subjects",
      pd.DataFrame({"phase": ["pre"] * 30 + ["post"] * 30, "score": _pre + _post}),
      "score", group="phase", prompt="paired before and after intervention")

# 4 — ordinal outcome, two groups → Mann–Whitney U.
bench("Ordinal outcome, two groups",
      pd.DataFrame({"arm": ["A"] * 20 + ["B"] * 20,
                    "likert": [(i % 5) + 1 for i in range(20)] + [(i % 5) + 2 for i in range(20)]}),
      "likert", group="arm")

# 5 — three groups, continuous → Welch's ANOVA (+ Games–Howell).
_g = []
for lab, base in (("A", 10.0), ("B", 13.0), ("C", 17.0)):
    _g += [{"arm": lab, "y": base + (i % 6) * 0.7} for i in range(15)]
bench("Three groups, continuous", pd.DataFrame(_g), "y", group="arm")

# 6 — three groups, ordinal → Kruskal–Wallis (+ Dunn).
_k = []
for lab in ("A", "B", "C"):
    _k += [{"arm": lab, "grade": (i % 5) + 1 + ("ABC".index(lab))} for i in range(20)]
bench("Three groups, ordinal", pd.DataFrame(_k), "grade", group="arm")

# 7 — weak, noisy linear association (BET not significant) → Pearson.
_rng7 = _rng(7)
_y7 = [0.15 * i + _rng7.gauss(0.0, 10.0) for i in range(60)]
bench("Weak linear association",
      pd.DataFrame({"x": [float(i) for i in range(60)], "y": _y7}), "y", predictor="x")

# 8 — monotone, curved association → Spearman.
bench("Monotone (curved) association",
      pd.DataFrame({"x": [float(i) for i in range(60)],
                    "y": [float(i) ** 1.6 for i in range(60)]}), "y", predictor="x")

# 9 — parabola: strong dependence, ~zero correlation → MaxBET.
_xs = [-1.0 + 2.0 * i / 159 for i in range(160)]
bench("Parabolic (nonlinear-only) association",
      pd.DataFrame({"x": _xs, "y": [v * v for v in _xs]}), "y", predictor="x")

# 10 — 2×2 contingency, large expected counts → chi-squared (+ odds ratio).
bench("2x2 contingency, large expected",
      pd.DataFrame({"treat": ["A"] * 20 + ["B"] * 20,
                    "cured": (["yes"] * 14 + ["no"] * 6) + (["yes"] * 5 + ["no"] * 15)}),
      "cured", group="treat")

# 11 — 2×2 contingency, small expected counts → Fisher's exact.
bench("2x2 contingency, small expected",
      pd.DataFrame({"treat": ["A", "A", "A", "B", "B", "B", "A", "B"],
                    "cured": ["yes", "yes", "no", "no", "no", "yes", "yes", "no"]}),
      "cured", group="treat")

# 12 — R×C contingency → chi-squared, Cramér's V.
_rc = []
for t, dist in (("A", (8, 2, 2)), ("B", (2, 8, 2)), ("C", (2, 2, 8))):
    for out, n in zip(("x", "y", "z"), dist):
        _rc += [{"treat": t, "grade": out}] * n
bench("RxC contingency, small expected (Freeman-Halton)", pd.DataFrame(_rc), "grade",
      group="treat")

# 13 — paired binary (2×2 within) → McNemar.
bench("Paired binary (McNemar)",
      pd.DataFrame({"before": ["+"] * 20 + ["-"] * 20,
                    "after": (["+"] * 10 + ["-"] * 10) + (["+"] * 15 + ["-"] * 5)}),
      "after", group="before", prompt="paired before/after, same subjects")

# 14 — counts, low dispersion → Poisson regression.
bench("Count outcome, low dispersion",
      pd.DataFrame({"events": [20 + (i % 16) for i in range(60)],
                    "exposure": [i * 0.5 + 1 for i in range(60)]}), "events", predictor="exposure")

# 15 — counts, overdispersed → negative-binomial regression.
_od = [0, 0, 1, 2, 30, 40, 0, 1, 50, 2, 3, 0, 60, 1, 45, 0, 2, 70, 5, 0] * 3
bench("Count outcome, overdispersed",
      pd.DataFrame({"events": _od, "exposure": [i * 0.3 + 1 for i in range(len(_od))]}),
      "events", predictor="exposure")

# 16 — two-arm survival with censoring → log-rank (+ hazard ratio).
_rng16 = _rng(0)
_surv = []
for arm, scale in (("control", 9.0), ("treated", 20.0)):
    for _ in range(40):
        _surv.append({"survival_time": round(_rng16.expovariate(1 / scale), 3),
                      "status": 1 if _rng16.random() < 0.85 else 0, "arm": arm})
bench("Survival, two arms (log-rank)", pd.DataFrame(_surv), "survival_time", group="arm",
      prompt="does treatment improve survival?")

# 17 — survival with a continuous covariate → Cox proportional hazards.
_rng17 = _rng(1)
_cox = []
for _ in range(90):
    age = _rng17.uniform(40, 80)
    _cox.append({"fu_time": round(_rng17.expovariate(1 / max(2.0, 30 - 0.25 * (age - 40))), 3),
                 "death": 1 if _rng17.random() < 0.8 else 0, "age": round(age, 1)})
bench("Survival with covariate (Cox)", pd.DataFrame(_cox), "fu_time", predictor="age")

# 18 — diagnostic discrimination → ROC / AUC.
_rng18 = _rng(2)
bench("Diagnostic discrimination (ROC/AUC)",
      pd.DataFrame({"disease": [1 if i < 50 else 0 for i in range(100)],
                    "biomarker": [round(_rng18.gauss(1.5 if i < 50 else 0.0, 1.0), 3)
                                  for i in range(100)]}), "disease", predictor="biomarker")

# 19 — confounded association: a common cause inflates the raw correlation.
_z = [float(i % 20) for i in range(80)]
_conf = Confounder(name="z", role=VariableRole.CONFOUNDER, is_measured=True,
                   adjustment_recommended=True, rationale="common cause of x and y")
bench("Confounded association (adjusted)",
      pd.DataFrame({"x": [zi + (i % 3) * 0.5 for i, zi in enumerate(_z)],
                    "y": [zi + (i % 5) * 0.4 for i, zi in enumerate(_z)], "z": _z}),
      "y", predictor="x", design=_design(StudyDesignType.OBSERVATIONAL, confounders=[_conf]))

# 20 — areal / ecological correlation → triggers the ecological caveats + STROBE.
bench("Ecological (county-level) correlation",
      pd.DataFrame({"county_fips": [str(37000 + i) for i in range(60)],
                    "clinic_density": [i * 0.1 for i in range(60)],
                    "od_rate": [200 - i * 0.5 + (i % 5) for i in range(60)]}),
      "od_rate", predictor="clinic_density")


def main() -> None:
    print("| # | Scenario | Selected test | Statistic | p | Effect size |")
    print("|---|---|---|---|---|---|")
    for n, label, test, stat, p, effect in _ROWS:
        print(f"| {n} | {label} | `{test}` | {stat} | {p} | {effect} |")


if __name__ == "__main__":
    main()
