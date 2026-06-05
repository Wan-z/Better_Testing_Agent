"""Generate the synthetic NC county overdose / clinic-access dataset.

This produces ``data/overdose_ed_visits.csv`` — a *simulated* county-level dataset
used to demonstrate the Hypothesis Testing Agent on a public-health style question:

    "Is the density of OUD treatment clinics associated with the nonfatal
     overdose emergency-department (ED) visit rate across NC counties?"

IMPORTANT: every value here is SYNTHETIC. County names and FIPS codes are real
(North Carolina's 100 counties, FIPS 37001–37199), but populations, rates,
clinic densities, incomes, and centroid coordinates are simulated for
demonstration only. They are NOT real surveillance data and must not be cited
as such.

The script is pure-stdlib and fully deterministic (fixed seed), so re-running it
reproduces the committed CSV exactly. It also prints derived figures (Spearman
correlation, distribution stats, a kernel-smoothed clinic-density grid) that are
embedded into the web dry-run demo so the demo stays consistent with the CSV.
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

SEED = 42
HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "overdose_ed_visits.csv"

# North Carolina's 100 counties, in alphabetical order. NC county FIPS codes are
# the odd numbers 37001..37199 assigned alphabetically, so index i -> 37001 + 2*i.
COUNTIES = [
    "Alamance", "Alexander", "Alleghany", "Anson", "Ashe", "Avery", "Beaufort",
    "Bertie", "Bladen", "Brunswick", "Buncombe", "Burke", "Cabarrus", "Caldwell",
    "Camden", "Carteret", "Caswell", "Catawba", "Chatham", "Cherokee", "Chowan",
    "Clay", "Cleveland", "Columbus", "Craven", "Cumberland", "Currituck", "Dare",
    "Davidson", "Davie", "Duplin", "Durham", "Edgecombe", "Forsyth", "Franklin",
    "Gaston", "Gates", "Graham", "Granville", "Greene", "Guilford", "Halifax",
    "Harnett", "Haywood", "Henderson", "Hertford", "Hoke", "Hyde", "Iredell",
    "Jackson", "Johnston", "Jones", "Lee", "Lenoir", "Lincoln", "Macon",
    "Madison", "Martin", "McDowell", "Mecklenburg", "Mitchell", "Montgomery",
    "Moore", "Nash", "New Hanover", "Northampton", "Onslow", "Orange", "Pamlico",
    "Pasquotank", "Pender", "Perquimans", "Person", "Pitt", "Polk", "Randolph",
    "Richmond", "Robeson", "Rockingham", "Rowan", "Rutherford", "Sampson",
    "Scotland", "Stanly", "Stokes", "Surry", "Swain", "Transylvania", "Tyrrell",
    "Union", "Vance", "Wake", "Warren", "Washington", "Watauga", "Wayne",
    "Wilkes", "Wilson", "Yadkin", "Yancey",
]
assert len(COUNTIES) == 100

# Approximate NC bounding box (decimal degrees). Synthetic centroids are drawn
# from this box; they do NOT reproduce true county locations.
LAT_MIN, LAT_MAX = 34.0, 36.55
LON_MIN, LON_MAX = -84.0, -76.0

# Synthetic "urban pulls" used to give the clinic-density field realistic spatial
# structure (hotspots in the Piedmont/coast, sparser in the mountains/rural east).
# (lat, lon, weight) — loosely inspired by NC metros but not exact.
URBAN = [
    (35.23, -80.84, 1.00),  # Charlotte
    (35.78, -78.64, 1.00),  # Raleigh
    (36.07, -79.79, 0.70),  # Greensboro
    (36.10, -80.24, 0.60),  # Winston-Salem
    (35.99, -78.90, 0.70),  # Durham
    (35.59, -82.55, 0.45),  # Asheville
    (34.22, -77.95, 0.50),  # Wilmington
]
KERNEL_H = 0.55  # degrees, urban-pull bandwidth


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _urban_proximity(lat: float, lon: float) -> float:
    score = 0.0
    for ula, ulo, w in URBAN:
        d2 = (lat - ula) ** 2 + (lon - ulo) ** 2
        score += w * math.exp(-d2 / (2 * KERNEL_H ** 2))
    return score


def generate_rows() -> list[dict]:
    rng = random.Random(SEED)
    rows = []
    for i, name in enumerate(COUNTIES):
        fips = 37001 + 2 * i
        lat = round(rng.uniform(LAT_MIN, LAT_MAX), 3)
        lon = round(rng.uniform(LON_MIN, LON_MAX), 3)
        urban = _urban_proximity(lat, lon)

        pct_rural = _clip(88 - 44 * urban + rng.gauss(0, 7), 3.0, 99.0)
        income = _clip(40000 + 15000 * urban - 150 * pct_rural + rng.gauss(0, 4000),
                       28000, 98000)
        unemployment = _clip(7.4 - 1.7 * urban + 0.028 * pct_rural + rng.gauss(0, 0.9),
                             2.6, 12.5)
        population = int(_clip(math.exp(9.7 + 1.55 * urban + rng.gauss(0, 0.5)),
                               6000, 1_150_000))
        clinic_density = _clip(1.2 + 6.6 * urban - 0.02 * pct_rural + rng.gauss(0, 1.1),
                               0.0, 19.0)

        # Outcome: nonfatal overdose ED visits per 100k. Higher in rural / low-access
        # counties; lower where clinic density is high. Multiplicative noise gives a
        # right-skewed distribution (so a rank-based correlation is the honest choice).
        base = 118 + 1.25 * pct_rural - 5.6 * clinic_density + 0.55 * unemployment
        rate = _clip(base * math.exp(rng.gauss(0, 0.19)), 35.0, 430.0)

        rows.append({
            "county": name,
            "fips": fips,
            "latitude": lat,
            "longitude": lon,
            "population": population,
            "median_household_income": int(round(income)),
            "pct_rural": round(pct_rural, 1),
            "unemployment_rate": round(unemployment, 1),
            "clinic_density_per_100k": round(clinic_density, 2),
            "nonfatal_overdose_ed_rate_per_100k": round(rate, 1),
        })
    return rows


# ── descriptive / inferential helpers (pure stdlib) ────────────────────────────

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _std(xs: list[float]) -> float:
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _skewness(xs: list[float]) -> float:
    m, s, n = _mean(xs), _std(xs), len(xs)
    return sum(((x - m) / s) ** 3 for x in xs) * n / ((n - 1) * (n - 2))


def _excess_kurtosis(xs: list[float]) -> float:
    m, s, n = _mean(xs), _std(xs), len(xs)
    g2 = sum(((x - m) / s) ** 4 for x in xs) * n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))
    return g2 - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))


def _dist_stats(xs: list[float]) -> dict:
    return {
        "mean": round(_mean(xs), 2),
        "std": round(_std(xs), 2),
        "median": round(_median(xs), 2),
        "iqr": round(_quantile(xs, 0.75) - _quantile(xs, 0.25), 2),
        "skewness": round(_skewness(xs), 3),
        "kurtosis": round(_excess_kurtosis(xs), 3),
        "min": round(min(xs), 2),
        "max": round(max(xs), 2),
    }


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # 1-based average rank for ties
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


def _norm_sf(z: float) -> float:
    """One-sided upper tail of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def _spearman_inference(rho: float, n: int) -> dict:
    # Two-sided p via the large-sample normal approximation z = rho*sqrt(n-1).
    z = abs(rho) * math.sqrt(n - 1)
    p = 2 * _norm_sf(z)
    # 95% CI via Fisher z-transform with the Fieller SE for Spearman's rho.
    zr = math.atanh(rho)
    se = 1.03 / math.sqrt(n - 3)
    lo, hi = math.tanh(zr - 1.96 * se), math.tanh(zr + 1.96 * se)
    return {"rho": round(rho, 3), "p_value": p, "n": n,
            "ci_lower": round(lo, 3), "ci_upper": round(hi, 3)}


def _density_grid(rows: list[dict], n_lat: int = 8, n_lon: int = 13) -> dict:
    """Kernel-smoothed clinic-density field on a lat/long grid (for the heatmap)."""
    lats = [r["latitude"] for r in rows]
    lons = [r["longitude"] for r in rows]
    dens = [r["clinic_density_per_100k"] for r in rows]
    lat_centers = [round(LAT_MIN + (k + 0.5) * (LAT_MAX - LAT_MIN) / n_lat, 3)
                   for k in range(n_lat)]
    lon_centers = [round(LON_MIN + (k + 0.5) * (LON_MAX - LON_MIN) / n_lon, 3)
                   for k in range(n_lon)]
    h = 0.6
    z = []
    for la in lat_centers:
        row_z = []
        for lo in lon_centers:
            wsum = 0.0
            vsum = 0.0
            for plat, plon, d in zip(lats, lons, dens):
                w = math.exp(-((la - plat) ** 2 + (lo - plon) ** 2) / (2 * h ** 2))
                wsum += w
                vsum += w * d
            row_z.append(round(vsum / wsum, 2) if wsum > 1e-9 else None)
        z.append(row_z)
    return {"x": lon_centers, "y": lat_centers, "z": z}


def main() -> None:
    rows = generate_rows()
    fieldnames = list(rows[0].keys())
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rate = [r["nonfatal_overdose_ed_rate_per_100k"] for r in rows]
    clinic = [r["clinic_density_per_100k"] for r in rows]
    rho = _spearman(clinic, rate)

    derived = {
        "n": len(rows),
        "spearman_clinic_vs_rate": _spearman_inference(rho, len(rows)),
        "stats_rate": _dist_stats(rate),
        "stats_clinic": _dist_stats(clinic),
        "scatter": {"x": clinic, "y": rate},
        "heatmap": _density_grid(rows),
    }
    print(f"Wrote {CSV_PATH} ({len(rows)} counties)")
    print("DERIVED_JSON_BEGIN")
    print(json.dumps(derived))
    print("DERIVED_JSON_END")


if __name__ == "__main__":
    main()
