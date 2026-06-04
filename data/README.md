# Example dataset — NC county overdose / clinic access

`overdose_ed_visits.csv` is a **synthetic** county-level dataset used to demonstrate
the Hypothesis Testing Agent on a public-health style question:

> *Is the density of opioid-use-disorder (OUD) treatment clinics associated with the
> nonfatal overdose emergency-department (ED) visit rate across North Carolina counties?*

It is generated deterministically by [`generate_dataset.py`](generate_dataset.py)
(pure standard-library Python, fixed seed). Re-running the script reproduces the CSV
byte-for-byte and prints the derived figures embedded in the web dry-run demo.

> ⚠️ **Synthetic data.** County names and FIPS codes are real (NC's 100 counties,
> FIPS 37001–37199, assigned alphabetically). Every measured value — populations,
> rates, clinic densities, incomes, and the centroid coordinates — is **simulated for
> demonstration only**. These are *not* real surveillance statistics and must not be
> cited as such.

## Schema

One row per county (N = 100), no missing values.

| Column | Type | Unit | Role | Notes |
|---|---|---|---|---|
| `county` | categorical | — | id | NC county name |
| `fips` | identifier | — | id | 5-digit county FIPS (37001–37199) |
| `latitude` | continuous | degrees | geo | **Synthetic** centroid (within NC bbox) |
| `longitude` | continuous | degrees | geo | **Synthetic** centroid (within NC bbox) |
| `population` | continuous | persons | covariate | Simulated county population |
| `median_household_income` | continuous | USD | confounder | Higher near urban centers |
| `pct_rural` | continuous | % (0–100) | confounder | Share of population rural |
| `unemployment_rate` | continuous | % | covariate | Simulated |
| `clinic_density_per_100k` | continuous | clinics / 100k | **predictor** | OUD treatment clinics per 100,000; right-skewed |
| `nonfatal_overdose_ed_rate_per_100k` | continuous | visits / 100k | **outcome** | Nonfatal overdose ED visits per 100,000 |

## Intended analysis

- **Primary:** association between `clinic_density_per_100k` (predictor) and
  `nonfatal_overdose_ed_rate_per_100k` (outcome). The relationship is monotone and the
  predictor is right-skewed, so the agent selects **Spearman's rank correlation** rather
  than Pearson's (see `TECHNICAL_REPORT.md §6.2`). The simulated association is strong and
  negative: ρ ≈ **−0.67** (95% CI [−0.77, −0.54], p < 0.001).
- **Imaging:** a **clinic-density heatmap** — a kernel-smoothed field of
  `clinic_density_per_100k` over a latitude/longitude grid, rendered as a Plotly
  `heatmap` plot (Piedmont hotspot, sparser mountains/east).
- **Design context:** observational and *ecological* (unit = county). The demo report
  flags the ecological fallacy, unadjusted confounding (rurality, income), reverse
  causation (clinics may locate where overdose burden is high), and possible spatial
  autocorrelation.

## Regenerating

```bash
python data/generate_dataset.py
```

This rewrites `overdose_ed_visits.csv` and prints a `DERIVED_JSON_BEGIN … END` block
(Spearman result, distribution stats, scatter points, and the smoothed heatmap grid).
Those figures are mirrored in `web/backend/stubs.py` and
`web/frontend/src/api/mock.ts` so the dry-run demo stays consistent with the CSV.
If you change the generator, re-run it and update those two files from the printed block.
