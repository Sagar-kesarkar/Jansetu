#!/usr/bin/env python3
"""Build the infrastructure-index and investment-plan reference tables.

Provenance, stated plainly because the hackathon rules require real or
realistic data and judges are entitled to ask which is which:

  districts.csv        REAL. District names, Census 2011 population and
                       literacy. Latitude/longitude are district centroids.
                       Internet penetration and the deprivation index are
                       realistic estimates in the range reported by TRAI
                       subscriber data and the NITI Aayog SDG India Index.

  infra_indices.csv    DERIVED, deterministic. Coverage per district per
                       category, generated from the deprivation index so that
                       poorer districts show genuinely worse coverage. This is
                       the shape the real data has; swap in the live figures
                       from the sources listed in docs/DATA_SOURCES.md and
                       nothing downstream changes.

  investment_plans.csv DERIVED, deterministic. Current allocation per district
                       per category, deliberately correlated with *low*
                       deprivation — richer districts historically absorb more
                       scheme money. That is the misallocation the platform is
                       built to surface, so the seed data has to contain it or
                       the demo proves nothing.

Deterministic on purpose: a fixed seed means every teammate and every judge
sees identical numbers, so a screenshot in the deck matches the live demo.

Determinism is *per district*, not per run, and that distinction is load-bearing.
The first version drew from one shared generator walked in file order, so
appending a district to `districts.csv` shifted every draw after it and silently
rewrote the allocation figures for all 24 districts that were already there.
Constraint 4 of this project says extending coverage means adding rows and
nothing else; a generator whose output depends on how many neighbours a district
has does not honour that. Each (table, district) pair now seeds its own
generator from the district's LGD code, so a row added today cannot move a number
computed yesterday.

Usage:  python data/scripts/build_reference.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
REFERENCE = DATA_DIR / "reference"

SEED = 20260822


def _rng(table: str, code: str) -> random.Random:
    """One generator per district per table, keyed on the LGD code.

    Seeding from a string is deterministic in CPython — the seed is hashed to an
    integer — so this reproduces identically on every machine, which is the only
    property the deck relies on.
    """
    return random.Random(f"{SEED}:{table}:{code}")

# Category -> (baseline national coverage %, how strongly deprivation hurts it)
CATEGORY_PROFILE: dict[str, tuple[float, float]] = {
    "WATER_SUPPLY": (72.0, 45.0),
    "SANITATION": (78.0, 40.0),
    "ROADS": (81.0, 35.0),
    "ELECTRICITY": (94.0, 18.0),
    "HEALTH": (66.0, 42.0),
    "EDUCATION": (74.0, 30.0),
    "DIGITAL": (58.0, 55.0),
    "HOUSING": (69.0, 38.0),
    "IRRIGATION": (49.0, 40.0),
    "TRANSPORT": (61.0, 44.0),
}


def read_districts() -> list[dict]:
    with (REFERENCE / "districts.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_infra(districts: list[dict]) -> list[dict]:
    rows = []
    for d in districts:
        rng = _rng("infra", d["code"])
        dep = float(d["deprivation_index"])
        for category, (base, sensitivity) in CATEGORY_PROFILE.items():
            coverage = base - sensitivity * dep + rng.uniform(-6.0, 6.0)
            rows.append({
                "district_code": d["code"],
                "category": category,
                "coverage_pct": round(max(2.0, min(99.5, coverage)), 1),
            })
    return rows


def build_investment(districts: list[dict]) -> list[dict]:
    """Allocation per capita is *inversely* related to deprivation — the
    regressive pattern the platform exists to detect."""
    schemes = {
        "WATER_SUPPLY": "Jal Jeevan Mission", "SANITATION": "Swachh Bharat Mission (G)",
        "ROADS": "PMGSY", "ELECTRICITY": "RDSS", "HEALTH": "Ayushman Bharat HWC",
        "EDUCATION": "Samagra Shiksha", "DIGITAL": "BharatNet", "HOUSING": "PMAY-G",
        "IRRIGATION": "PMKSY", "TRANSPORT": "State transport",
    }
    rows = []
    for d in districts:
        rng = _rng("investment", d["code"])
        dep = float(d["deprivation_index"])
        population = int(d["population"])
        for category, scheme in schemes.items():
            # ₹ per capita: 90 in the best-off districts down to ~25 in the worst
            per_capita = (90.0 - 65.0 * dep) * rng.uniform(0.8, 1.2)
            allocated_lakh = max(5.0, per_capita * population / 100_000)
            rows.append({
                "district_code": d["code"],
                "category": category,
                "scheme": scheme,
                "allocated_inr_lakh": round(allocated_lakh, 2),
                "fiscal_year": "2026-27",
            })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows):>5} rows -> {path.relative_to(DATA_DIR.parent)}")


def main() -> None:
    districts = read_districts()
    print(f"read {len(districts)} districts across "
          f"{len({d['state'] for d in districts})} states")
    write_csv(REFERENCE / "infra_indices.csv", build_infra(districts))
    write_csv(REFERENCE / "investment_plans.csv", build_investment(districts))


if __name__ == "__main__":
    main()
