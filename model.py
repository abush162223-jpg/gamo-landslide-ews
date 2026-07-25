"""
Gamo Zone Landslide Early Warning - sample model
--------------------------------------------------
Combines CONSTANT engineering/susceptibility parameters (slope, soil,
geology - surveyed once) with DAILY rainfall (changes every day) to
produce a daily landslide risk nowcast per site.

In a real deployment:
  - engineering_parameters.csv stays fixed until a new field survey.
  - rainfall would be pulled daily from CHIRPS/IMERG instead of being
    randomly generated here.
  - this script would be triggered every day by GitHub Actions
    (see .github/workflows/daily_update.yml) and results.json would be
    committed back to the repo, which the dashboard reads.

For this demo, rainfall is simulated for 30 days so you can see the
whole pipeline (constant params + daily rain -> daily risk) working
end to end without needing live data access.
"""

import csv
import json
import random
from datetime import date, timedelta

random.seed(7)

SITES_FILE = "data/engineering_parameters.csv"
RAINFALL_FILE = "data/rainfall_sample_30day.csv"
OUTPUT_FILE = "results.json"
NUM_DAYS = 30
ANTECEDENT_WINDOW = 3  # days of prior rain that matter for saturation


def load_sites():
    with open(SITES_FILE, newline="") as f:
        return list(csv.DictReader(f))


def simulate_rainfall(sites, num_days):
    """Simulate daily rainfall (mm) per site, with one storm cluster."""
    start = date.today() - timedelta(days=num_days - 1)
    rows = []
    storm_start = random.randint(12, 18)  # a wet spell mid-period
    for i in range(num_days):
        d = start + timedelta(days=i)
        in_storm = storm_start <= i <= storm_start + 4
        for s in sites:
            base = random.uniform(0, 8)
            storm_boost = random.uniform(20, 55) if in_storm else 0
            rain = round(base + storm_boost, 1)
            rows.append({"date": d.isoformat(), "site_id": s["site_id"], "rainfall_mm": rain})
    with open(RAINFALL_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "site_id", "rainfall_mm"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def risk_level(score):
    if score >= 0.75:
        return "Very High"
    if score >= 0.55:
        return "High"
    if score >= 0.35:
        return "Medium"
    return "Low"


def run_model(sites, rainfall_rows):
    by_site = {}
    for r in rainfall_rows:
        by_site.setdefault(r["site_id"], []).append(r)
    for site_id in by_site:
        by_site[site_id].sort(key=lambda r: r["date"])

    results = []
    for s in sites:
        susceptibility = float(s["susceptibility_score"])
        records = by_site[s["site_id"]]
        for i, rec in enumerate(records):
            window = records[max(0, i - ANTECEDENT_WINDOW + 1): i + 1]
            antecedent_rain = sum(float(w["rainfall_mm"]) for w in window)
            # normalize antecedent rainfall against a 150mm/3-day saturation reference
            rain_factor = min(antecedent_rain / 150.0, 1.0)
            risk_score = round(0.5 * susceptibility + 0.5 * rain_factor * susceptibility * 1.3, 3)
            risk_score = min(risk_score, 1.0)
            results.append({
                "date": rec["date"],
                "site_id": s["site_id"],
                "site_name": s["site_name"],
                "lat": float(s["latitude"]),
                "lon": float(s["longitude"]),
                "susceptibility": susceptibility,
                "today_rainfall_mm": float(rec["rainfall_mm"]),
                "antecedent_3day_mm": round(antecedent_rain, 1),
                "risk_score": risk_score,
                "risk_level": risk_level(risk_score),
            })
    return results


def main():
    sites = load_sites()
    rainfall_rows = simulate_rainfall(sites, NUM_DAYS)
    results = run_model(sites, rainfall_rows)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {len(results)} records for {len(sites)} sites over {NUM_DAYS} days to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
