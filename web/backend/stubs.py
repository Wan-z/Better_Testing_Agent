"""Stub pipeline outputs used when running in dry-run mode (no API key set).

These mirror the mock data from the frontend so the full round-trip is
testable without any LLM or R dependency.
"""

from __future__ import annotations

from typing import Any

STUB_REPORT: dict[str, Any] = {
    "data_profile": {
        "variables": [
            {
                "name": "blood_pressure",
                "variable_type": "CONTINUOUS",
                "n_observations": 100,
                "n_missing": 2,
                "distribution_stats": {
                    "mean": 128.4, "std": 14.2, "median": 127.0, "iqr": 18.5,
                    "skewness": 0.31, "kurtosis": -0.12, "min": 95.0, "max": 172.0,
                },
                "normality": {
                    "name": "Shapiro-Wilk", "statistic": 0.982,
                    "p_value": 0.21, "is_normal": True,
                },
            },
            {
                "name": "group",
                "variable_type": "CATEGORICAL",
                "n_observations": 100,
                "n_missing": 0,
                "unique_values": ["control", "treatment"],
            },
        ],
        "n_groups": 2,
        "group_variable": "group",
        "outcome_variable": "blood_pressure",
        "notes": ["2 missing values in blood_pressure (2.0%)"],
    },
    "study_design": {
        "design_type": "EXPERIMENTAL",
        "measurement_type": "BETWEEN_SUBJECTS",
        "is_randomized": True,
        "confounders": [
            {
                "name": "age", "role": "CONFOUNDER", "is_measured": True,
                "adjustment_recommended": True,
                "rationale": "Age affects both treatment assignment and blood pressure.",
            }
        ],
        "notes": ["Randomised controlled trial"],
    },
    "test_result": {
        "test_used": "WELCH_T",
        "statistic": 3.14,
        "p_value": 0.002,
        "degrees_of_freedom": 97.3,
        "effect_size": {
            "measure_name": "Cohen's d",
            "value": 0.63,
            "interpretation": "medium",
            "ci_lower": 0.22,
            "ci_upper": 1.04,
        },
        "assumption_checks": [
            {
                "assumption_name": "Normality (outcome)",
                "status": "MET",
                "test_used": "Shapiro-Wilk",
                "statistic": 0.982,
                "p_value": 0.21,
                "note": "Distribution does not significantly deviate from normality.",
            },
            {
                "assumption_name": "Minimum sample size",
                "status": "MET",
                "note": "Both groups have N ≥ 5.",
            },
            {
                "assumption_name": "Independence of observations",
                "status": "UNTESTABLE",
                "note": "Assumed based on study design (between-subjects RCT).",
            },
        ],
        "confidence_interval": [2.8, 12.4],
        "is_significant": True,
        "notes": [
            "Sensitivity: minimum detectable Cohen's d = 0.28 at N=100, α=0.05, power=0.80",
        ],
    },
    "plain_language_summary": (
        "Participants in the treatment group had significantly lower blood pressure than "
        "those in the control group (p = 0.002). The effect was medium in size "
        "(Cohen's d = 0.63, 95% CI [0.22, 1.04]), suggesting a clinically meaningful reduction."
    ),
    "caveats": [
        {
            "severity": "WARNING",
            "message": "Age was identified as a confounder but not adjusted for in this analysis.",
            "recommendation": "Consider ANCOVA with age as a covariate to improve precision.",
        },
        {
            "severity": "INFO",
            "message": "Observational confounding possible despite randomisation.",
            "recommendation": "Report baseline balance table in your manuscript.",
        },
    ],
    "plots": [
        {
            "plot_type": "boxplot",
            "title": "Blood pressure by group",
            "x_label": "Group",
            "y_label": "Blood pressure (mmHg)",
            "data": {
                "Control":   [120, 125, 130, 132, 118, 140, 135, 128, 122, 138,
                              115, 142, 127, 133, 119, 136, 124, 131, 126, 141],
                "Treatment": [108, 112, 105, 118, 102, 115, 110, 107, 114, 109,
                              103, 116, 111, 106, 113, 108, 104, 117, 110, 112],
            },
        },
        {
            "plot_type": "qqplot",
            "title": "Q-Q plot — blood pressure (control)",
            "x_label": "Theoretical quantiles",
            "y_label": "Sample quantiles",
            "data": {
                "theoretical": [-2.1, -1.5, -1.1, -0.8, -0.5, -0.3, 0, 0.3, 0.5, 0.8, 1.1, 1.5, 2.1],
                "sample":      [115, 118, 120, 122, 124, 126, 128, 130, 132, 135, 138, 140, 142],
            },
        },
    ],
    "methods_text": (
        "An independent-samples Welch's t-test was used to compare blood pressure between "
        "treatment and control groups, as this test does not assume equal variances. "
        "Normality was assessed using the Shapiro-Wilk test (W = 0.982, p = .21) and "
        "confirmed for both groups. The effect size was estimated as Cohen's d with 95% "
        "confidence intervals computed via bootstrapping (n = 1,000 resamples). "
        "Statistical significance was evaluated at α = .05."
    ),
}

STUB_DIALOGUE_TURNS = [
    (
        "Thank you. A few quick questions to understand your study design:\n\n"
        "1. Was this an experimental study (with random assignment to treatment/control) "
        "or an observational study?\n"
        "2. Are the measurements independent between participants (i.e., no repeated "
        "measures or matched pairs)?\n"
        "3. Are there any variables you think might confound the relationship — for "
        "example, age, sex, or baseline health status?"
    ),
    (
        "Understood — a randomised controlled trial with between-subjects measurements, "
        "and age as a potential confounder. That gives me everything I need.\n\n"
        "One last question: do you expect the relationship between treatment and blood "
        "pressure to be straightforward (linear/monotone), or do you suspect a more "
        "complex or nonlinear pattern?"
    ),
]

STUB_STUDY_DESIGN = {
    "design_type": "EXPERIMENTAL",
    "measurement_type": "BETWEEN_SUBJECTS",
    "is_randomized": True,
    "confounders": [
        {
            "name": "age", "role": "CONFOUNDER", "is_measured": True,
            "adjustment_recommended": True,
            "rationale": "Age affects both treatment assignment and blood pressure.",
        }
    ],
    "notes": ["Randomised controlled trial"],
}
