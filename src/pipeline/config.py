"""Chicago Data Portal dataset IDs and file paths.

When a new budget year is published:
1. Update BUDGET_YEAR and the dataset IDs below.
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

# FY 2026 ordinance datasets (update these when the city publishes a new year)
DATASETS = {
    "ordinance_appropriations": os.getenv(
        "SOCRATA_DATASET_ORDINANCE_APPROPRIATIONS",
        "6694-f78c",
    ),
    "recommended_appropriations": os.getenv(
        "SOCRATA_DATASET_RECOMMENDED_APPROPRIATIONS",
        "axxr-vais",
    ),
    "ordinance_revenue": os.getenv(
        "SOCRATA_DATASET_ORDINANCE_REVENUE",
        "nydj-5nax",
    ),
}

MERGE_KEYS = ["fund_code", "department_code", "account_code"]
MONEY_COLS = ["ordinance_amount", "recommended_amount", "delta_amount", "estimated_revenue"]
SOCRATA_DOMAIN = "data.cityofchicago.org"


def appropriations_path(year: str | None = None) -> Path:
    y = year or BUDGET_YEAR
    return DATA_DIR / f"budget_appropriations_comparison_{y}.csv"


def revenues_path(year: str | None = None) -> Path:
    y = year or BUDGET_YEAR
    return DATA_DIR / f"budget_revenues_{y}.csv"
