"""Chicago Data Portal dataset IDs and file paths.

When a new budget year is published:
1. Add it to YEARS and DATASETS_BY_YEAR, and set BUDGET_YEAR if it should open first.
2. Optionally add official Overview totals in published_glance.py so the
   glance page can show the published net figure.
3. Run: python3 run.py --refresh

Find current datasets at https://data.cityofchicago.org/
"""

from __future__ import annotations

import os
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_ROOT.parent
DATA_DIR = SRC_ROOT / "data"

BUDGET_YEAR = os.getenv("BUDGET_YEAR", "2026")
YEARS = ("2024", "2025", "2026")

# One ordinance, one recommendation, and one revenue dataset per fiscal year.
DATASETS_BY_YEAR: dict[str, dict[str, str]] = {
    "2024": {
        "ordinance_appropriations": "x394-e874",
        "recommended_appropriations": "rrdf-6mjk",
        "ordinance_revenue": "rmi8-cugu",
    },
    "2025": {
        "ordinance_appropriations": "t59y-fr3k",
        "recommended_appropriations": "miyk-k49p",
        "ordinance_revenue": "e5cq-t86i",
    },
    "2026": {
        "ordinance_appropriations": os.getenv("SOCRATA_DATASET_ORDINANCE_APPROPRIATIONS", "6694-f78c"),
        "recommended_appropriations": os.getenv("SOCRATA_DATASET_RECOMMENDED_APPROPRIATIONS", "axxr-vais"),
        "ordinance_revenue": os.getenv("SOCRATA_DATASET_ORDINANCE_REVENUE", "nydj-5nax"),
    },
}


def datasets_for(year: str | None = None) -> dict[str, str]:
    key = str(year or BUDGET_YEAR)
    try:
        return DATASETS_BY_YEAR[key]
    except KeyError as exc:
        known = ", ".join(DATASETS_BY_YEAR)
        raise ValueError(f"No Data Portal datasets configured for FY {key}. Known years: {known}.") from exc


# Backward-compatible alias for the default budget year.
DATASETS = datasets_for(BUDGET_YEAR)

MERGE_KEYS = ["fund_code", "department_code", "account_code"]
MONEY_COLS = ["ordinance_amount", "recommended_amount", "delta_amount", "estimated_revenue"]
SOCRATA_DOMAIN = "data.cityofchicago.org"


def appropriations_path(year: str | None = None) -> Path:
    y = year or BUDGET_YEAR
    return DATA_DIR / f"budget_appropriations_comparison_{y}.csv"


def revenues_path(year: str | None = None) -> Path:
    y = year or BUDGET_YEAR
    return DATA_DIR / f"budget_revenues_{y}.csv"
