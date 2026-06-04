"""Stub pipeline outputs used when running in dry-run mode (no API key set).

These mirror the mock data from the frontend so the full round-trip is
testable without any LLM or R dependency.

The dry-run demo analyses a *synthetic* North Carolina county dataset
(``data/overdose_ed_visits.csv``, produced by ``data/generate_dataset.py``):
the question is whether the density of opioid-use-disorder (OUD) treatment
clinics is associated with the nonfatal overdose emergency-department (ED) visit
rate across the state's 100 counties. All values here are derived directly from
that simulated CSV — they are NOT real surveillance statistics.
"""

from __future__ import annotations

from typing import Any

# Clinic density (OUD treatment clinics per 100k) for each county — the predictor.
_CLINIC_DENSITY = [
    0.07, 0.0, 0.0, 1.21, 0.5, 0.59, 5.17, 1.31, 2.57, 0.79, 3.73, 0.31, 5.82,
    1.88, 1.62, 12.94, 0.97, 2.99, 3.44, 3.47, 0.36, 0.0, 1.42, 3.89, 1.94, 0.0,
    2.95, 4.19, 0.58, 8.38, 3.38, 6.08, 0.0, 9.0, 0.0, 2.78, 1.61, 0.04, 0.38,
    1.21, 0.0, 1.06, 2.43, 1.3, 1.0, 2.27, 0.0, 3.32, 3.57, 0.0, 3.22, 4.23,
    2.33, 2.89, 0.0, 0.0, 10.24, 10.29, 0.84, 3.01, 0.0, 6.49, 0.38, 0.56, 6.32,
    1.49, 0.0, 0.35, 1.81, 3.22, 9.01, 0.0, 7.17, 1.27, 5.01, 1.1, 0.0, 2.86,
    3.98, 0.0, 8.28, 7.7, 0.73, 9.96, 0.34, 1.79, 2.91, 0.0, 0.01, 7.65, 0.0,
    1.99, 0.0, 0.0, 3.06, 10.96, 0.0, 0.0, 1.9, 0.0,
]
# Nonfatal overdose ED visit rate (per 100k) for each county — the outcome.
_OD_RATE = [
    218.6, 193.3, 250.3, 166.0, 184.2, 249.7, 122.1, 185.1, 311.3, 247.0, 174.7,
    259.4, 132.6, 192.9, 202.9, 84.4, 251.3, 275.9, 182.3, 214.7, 301.8, 213.7,
    204.6, 189.2, 204.5, 245.4, 182.1, 151.9, 224.4, 94.8, 202.5, 171.1, 250.6,
    82.9, 306.0, 176.9, 173.4, 199.4, 206.5, 325.3, 353.1, 174.7, 199.9, 222.0,
    259.3, 257.5, 230.7, 211.4, 170.3, 192.8, 201.0, 186.6, 268.8, 223.7, 252.5,
    173.2, 137.0, 104.6, 240.1, 141.9, 262.1, 176.5, 246.3, 270.7, 161.0, 198.4,
    177.7, 232.8, 162.7, 164.7, 162.5, 317.9, 116.3, 186.1, 179.9, 190.2, 220.1,
    209.2, 181.9, 224.6, 106.2, 111.9, 226.7, 95.3, 247.7, 184.9, 147.3, 208.8,
    170.6, 140.1, 210.5, 158.5, 283.5, 372.0, 239.6, 80.6, 222.4, 183.8, 196.2,
    225.1,
]
# Kernel-smoothed clinic-density field on a lat/long grid (for the heatmap).
_HEAT_LON = [-83.692, -83.077, -82.462, -81.846, -81.231, -80.615, -80.0,
             -79.385, -78.769, -78.154, -77.538, -76.923, -76.308]
_HEAT_LAT = [34.159, 34.478, 34.797, 35.116, 35.434, 35.753, 36.072, 36.391]
_HEAT_Z = [
    [0.32, 0.5, 0.83, 1.44, 2.44, 2.8, 1.92, 1.28, 1.46, 2.09, 2.28, 1.38, 0.64],
    [0.34, 0.67, 1.23, 2.06, 3.15, 3.56, 2.61, 1.82, 1.85, 2.3, 2.33, 1.44, 0.77],
    [0.36, 0.85, 1.64, 2.6, 3.72, 4.31, 3.56, 2.75, 2.59, 2.7, 2.36, 1.41, 0.84],
    [0.4, 1.01, 1.95, 2.95, 4.01, 4.91, 4.75, 4.2, 3.83, 3.34, 2.36, 1.25, 0.78],
    [0.44, 1.15, 2.15, 3.08, 4.02, 5.28, 6.06, 5.97, 5.43, 4.12, 2.28, 1.0, 0.61],
    [0.51, 1.24, 2.21, 3.01, 3.8, 5.4, 7.2, 7.56, 6.88, 4.75, 2.13, 0.76, 0.41],
    [0.6, 1.28, 2.14, 2.75, 3.4, 5.3, 7.88, 8.51, 7.83, 5.06, 1.95, 0.62, 0.28],
    [0.69, 1.27, 1.95, 2.37, 2.92, 5.05, 8.04, 8.82, 8.27, 5.1, 1.78, 0.53, 0.2],
]

STUB_REPORT: dict[str, Any] = {
    "data_profile": {
        "variables": [
            {
                "name": "nonfatal_overdose_ed_rate_per_100k",
                "variable_type": "CONTINUOUS",
                "n_observations": 100,
                "n_missing": 0,
                "distribution_stats": {
                    "mean": 202.6, "std": 57.41, "median": 199.65, "iqr": 67.05,
                    "skewness": 0.268, "kurtosis": 0.504, "min": 80.6, "max": 372.0,
                },
                "normality": {
                    "name": "Shapiro-Wilk", "statistic": 0.991,
                    "p_value": 0.76, "is_normal": True,
                },
            },
            {
                "name": "clinic_density_per_100k",
                "variable_type": "CONTINUOUS",
                "n_observations": 100,
                "n_missing": 0,
                "distribution_stats": {
                    "mean": 2.58, "std": 3.03, "median": 1.55, "iqr": 3.38,
                    "skewness": 1.463, "kurtosis": 1.52, "min": 0.0, "max": 12.94,
                },
                "normality": {
                    "name": "Shapiro-Wilk", "statistic": 0.842,
                    "p_value": 0.0001, "is_normal": False,
                },
            },
        ],
        "n_groups": None,
        "group_variable": None,
        "outcome_variable": "nonfatal_overdose_ed_rate_per_100k",
        "notes": [
            "100 NC counties; 0 missing values.",
            "clinic_density_per_100k is right-skewed (skew = 1.46) — a rank-based "
            "correlation is preferred over Pearson's.",
            "Synthetic demonstration data — not real surveillance statistics.",
        ],
    },
    "study_design": {
        "design_type": "OBSERVATIONAL",
        "measurement_type": "BETWEEN_SUBJECTS",
        "is_randomized": False,
        "confounders": [
            {
                "name": "pct_rural", "role": "CONFOUNDER", "is_measured": True,
                "adjustment_recommended": True,
                "rationale": "Rurality drives both lower clinic density and higher "
                             "overdose burden, confounding the association.",
            },
            {
                "name": "median_household_income", "role": "CONFOUNDER",
                "is_measured": True, "adjustment_recommended": True,
                "rationale": "Income relates to both healthcare access (clinic siting) "
                             "and overdose risk.",
            },
        ],
        "notes": [
            "County-level ecological analysis (unit = county, N = 100).",
            "Monotone relationship expected between clinic density and overdose ED rate.",
            "Observational — clinics may locate where overdose burden is already high "
            "(reverse causation).",
        ],
    },
    "test_result": {
        "test_used": "SPEARMAN_CORRELATION",
        "statistic": -0.667,
        "p_value": 3.1e-11,
        "degrees_of_freedom": None,
        "effect_size": {
            "measure_name": "Spearman's ρ",
            "value": -0.667,
            "interpretation": "large",
            "ci_lower": -0.766,
            "ci_upper": -0.538,
        },
        "assumption_checks": [
            {
                "assumption_name": "Monotonicity",
                "status": "MET",
                "note": "A monotone (rank) relationship is the estimand; no linearity "
                        "or normality is assumed.",
            },
            {
                "assumption_name": "Continuity / limited ties",
                "status": "MET",
                "note": "Both variables are continuous with < 5% tied ranks.",
            },
            {
                "assumption_name": "Independence of observations",
                "status": "UNTESTABLE",
                "note": "County rates may be spatially autocorrelated; the independence "
                        "assumption should be treated with caution.",
            },
        ],
        "confidence_interval": [-0.766, -0.538],
        "is_significant": True,
        "notes": [
            "Sensitivity: at N=100, α=0.05, power=0.80 the minimum detectable |ρ| ≈ 0.28; "
            "the observed association is well above this threshold.",
        ],
    },
    "plain_language_summary": (
        "Across North Carolina's 100 counties, those with a higher density of "
        "opioid-use-disorder treatment clinics tended to have lower nonfatal overdose "
        "ED visit rates. The association was strong and statistically significant "
        "(Spearman's ρ = −0.67, 95% CI [−0.77, −0.54], p < 0.001). Because this is an "
        "observational, county-level analysis, the result describes an association — "
        "not evidence that adding clinics causes fewer overdoses."
    ),
    "caveats": [
        {
            "severity": "WARNING",
            "message": "County-level (ecological) correlation: a relationship between "
                       "county averages need not hold for individuals (ecological fallacy).",
            "recommendation": "Avoid individual-level claims; use person-level data to "
                              "make person-level inferences.",
        },
        {
            "severity": "WARNING",
            "message": "Rurality and median income were identified as confounders but a "
                       "bivariate correlation does not adjust for them.",
            "recommendation": "Estimate a partial Spearman correlation adjusting for "
                              "pct_rural and income, or fit a regression model.",
        },
        {
            "severity": "INFO",
            "message": "Observational design: avoid causal language in the write-up.",
            "recommendation": "Frame findings as associations; clinics may also locate "
                              "where overdose burden is high (reverse causation).",
        },
        {
            "severity": "INFO",
            "message": "County observations may be spatially autocorrelated, which can "
                       "understate standard errors.",
            "recommendation": "Consider spatial models or cluster-robust inference.",
        },
    ],
    "plots": [
        {
            "plot_type": "scatter",
            "title": "Clinic density vs nonfatal overdose ED rate (NC counties)",
            "x_label": "OUD treatment clinics per 100k",
            "y_label": "Nonfatal overdose ED visits per 100k",
            "data": {"x": _CLINIC_DENSITY, "y": _OD_RATE},
        },
        {
            "plot_type": "heatmap",
            "title": "Clinic-density heatmap — NC (kernel-smoothed)",
            "x_label": "Longitude",
            "y_label": "Latitude",
            "data": {
                "x": _HEAT_LON,
                "y": _HEAT_LAT,
                "z": _HEAT_Z,
                "colorscale": "YlOrRd",
                "colorbar_title": "Clinics per 100k",
            },
        },
    ],
    "methods_text": (
        "County-level nonfatal overdose ED visit rates (per 100,000) were related to the "
        "density of OUD treatment clinics (per 100,000) across North Carolina's 100 "
        "counties using Spearman's rank-order correlation, chosen because clinic density "
        "was right-skewed and the expected relationship was monotone rather than strictly "
        "linear. The correlation was ρ = −0.67 (95% CI [−0.77, −0.54] via the Fisher "
        "z-transform), p < .001. As an observational, ecological analysis no causal "
        "interpretation is made, and county-level confounders (rurality, median household "
        "income) were not adjusted in this bivariate estimate. Significance was evaluated "
        "at α = .05."
    ),
}

STUB_DIALOGUE_TURNS = [
    (
        "Thanks — a county-level look at clinic access and overdose ED visits. "
        "A few questions to pin down the design:\n\n"
        "1. Is this an observational analysis of existing county records (rather than "
        "an experiment where clinic placement was randomised)?\n"
        "2. What is the unit of analysis — each row is one county, correct?\n"
        "3. Which county characteristics might confound the clinic-density / overdose "
        "relationship — for example rurality, median income, or unemployment?"
    ),
    (
        "Understood — an observational, county-level (ecological) analysis with rurality "
        "and income as likely confounders.\n\n"
        "One last question: do you expect the relationship between clinic density and the "
        "overdose ED rate to be straight-line (linear), simply monotone (consistently up "
        "or down without being a straight line), or possibly nonlinear?"
    ),
]

STUB_STUDY_DESIGN = {
    "design_type": "OBSERVATIONAL",
    "measurement_type": "BETWEEN_SUBJECTS",
    "is_randomized": False,
    "confounders": [
        {
            "name": "pct_rural", "role": "CONFOUNDER", "is_measured": True,
            "adjustment_recommended": True,
            "rationale": "Rurality drives both lower clinic density and higher overdose "
                         "burden.",
        },
        {
            "name": "median_household_income", "role": "CONFOUNDER", "is_measured": True,
            "adjustment_recommended": True,
            "rationale": "Income relates to both healthcare access and overdose risk.",
        },
    ],
    "notes": [
        "County-level ecological analysis (unit = county, N = 100).",
        "Monotone relationship expected.",
    ],
}
