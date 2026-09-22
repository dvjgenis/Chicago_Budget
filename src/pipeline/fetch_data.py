"""Download budget ordinance data from the Chicago Data Portal."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sodapy import Socrata

from pipeline.config import (
    BUDGET_YEAR,
    DATA_DIR,
    DATASETS,
    MERGE_KEYS,
    MONEY_COLS,
    PROJECT_ROOT,
    SOCRATA_DOMAIN,
    appropriations_path,
    revenues_path,
)
from pipeline.glance import collapse_duplicate_keys, unique_on_keys

load_dotenv(PROJECT_ROOT / ".env")


def data_paths() -> tuple[Path, Path]:
    return appropriations_path(), revenues_path()


def _credentials() -> tuple[str | None, str | None, str | None]:
    return (
        os.getenv("SOCRATA_APP_TOKEN"),
        os.getenv("SOCRATA_USERNAME"),
        os.getenv("SOCRATA_PASSWORD"),
    )


def missing_credentials() -> list[str]:
    labels = {
        "SOCRATA_APP_TOKEN": "SOCRATA_APP_TOKEN",
        "SOCRATA_USERNAME": "SOCRATA_USERNAME",
        "SOCRATA_PASSWORD": "SOCRATA_PASSWORD",
    }
    missing = []
    for key, label in labels.items():
        if not os.getenv(key):
            missing.append(label)
    return missing


def get_client() -> Socrata:
    app_token, username, password = _credentials()
    missing = missing_credentials()
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Missing {joined} in .env. Copy .env.example to .env and add your Chicago Data Portal credentials."
        )
    return Socrata(
        SOCRATA_DOMAIN,
        app_token=app_token,
        username=username,
        password=password,
        timeout=120,
    )


def fetch_all_records(client: Socrata, dataset_id: str, limit: int = 50_000) -> pd.DataFrame:
    offset = 0
    records: list[dict] = []
    while True:
        batch = client.get(dataset_id, limit=limit, offset=offset, order=":id")
        if not batch:
            break
        records.extend(batch)
        offset += limit
    return pd.DataFrame.from_records(records)


def _parse_money(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"[\$,]", "", regex=True)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    if len(text_cols):
        df = df.copy()
        df[text_cols] = df[text_cols].apply(lambda s: s.str.strip())
    return df


def clean_appropriations(df: pd.DataFrame, *, is_recommendation: bool = False) -> pd.DataFrame:
    amt_candidates = [
        c for c in df.columns if any(k in c.lower() for k in ("amount", "ordinance", "recommendation"))
    ]
    if not amt_candidates:
        raise ValueError(f"No amount column found in {list(df.columns)}")
    amt_col = amt_candidates[0]
    target_amt_col = "recommended_amount" if is_recommendation else "ordinance_amount"

    df = df.rename(
        columns={
            "fund_description": "fund_name",
            "department_number": "department_code",
            "department_description": "department_name",
            "appropriation_account": "account_code",
            "appropriation_account_description": "account_name",
            amt_col: target_amt_col,
        }
    )
    df[target_amt_col] = _parse_money(df[target_amt_col])
    df["department_code"] = pd.to_numeric(df["department_code"], errors="coerce").fillna(0).astype(int)
    df = _strip_strings(df)

    keep = [
        c
        for c in [*MERGE_KEYS, "fund_name", "department_name", "account_name", target_amt_col]
        if c in df.columns
    ]
    return df[keep]


def clean_revenues(df: pd.DataFrame) -> pd.DataFrame:
    df["estimated_revenue"] = _parse_money(df["estimated_revenue"])
    return _strip_strings(df)


def merge_appropriations(enacted: pd.DataFrame, recommended: pd.DataFrame) -> pd.DataFrame:
    enacted = unique_on_keys(enacted, "ordinance_amount")
    recommended = unique_on_keys(recommended, "recommended_amount")
    merged = pd.merge(enacted, recommended, on=MERGE_KEYS, how="outer", suffixes=("_enacted", "_recommended"))
    for base in ("fund_name", "department_name", "account_name"):
        enacted_col, rec_col = f"{base}_enacted", f"{base}_recommended"
        if enacted_col in merged.columns and rec_col in merged.columns:
            merged[base] = merged[enacted_col].combine_first(merged[rec_col])
            merged.drop(columns=[enacted_col, rec_col], inplace=True)

    merged["recommended_amount"] = merged["recommended_amount"].fillna(0.0)
    merged["ordinance_amount"] = merged["ordinance_amount"].fillna(0.0)
    merged["delta_amount"] = merged["ordinance_amount"] - merged["recommended_amount"]
    merged["pct_change"] = (
        merged["delta_amount"] / merged["recommended_amount"].replace(0, pd.NA) * 100
    ).fillna(0.0)
    return collapse_duplicate_keys(merged)


def _normalize_money_columns(appropriations: pd.DataFrame, revenues: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    for col in MONEY_COLS:
        if col in appropriations.columns:
            appropriations[col] = pd.to_numeric(appropriations[col], errors="coerce").fillna(0.0)
        if col in revenues.columns:
            revenues[col] = pd.to_numeric(revenues[col], errors="coerce").fillna(0.0)
    return appropriations, revenues


def refresh_datasets(*, year: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch fresh data from Socrata, save CSV/Parquet under data/, and return frames."""
    DATA_DIR.mkdir(exist_ok=True)
    appro_path = appropriations_path(year)
    rev_path = revenues_path(year)

    client = get_client()
    try:
        raw_enacted = fetch_all_records(client, DATASETS["ordinance_appropriations"])
        raw_rec = fetch_all_records(client, DATASETS["recommended_appropriations"])
        raw_rev = fetch_all_records(client, DATASETS["ordinance_revenue"])
    finally:
        client.close()

    clean_enacted = clean_appropriations(raw_enacted, is_recommendation=False)
    clean_rec = clean_appropriations(raw_rec, is_recommendation=True)
    appropriations = merge_appropriations(clean_enacted, clean_rec)
    revenues = clean_revenues(raw_rev)
    appropriations, revenues = _normalize_money_columns(appropriations, revenues)

    appropriations.to_csv(appro_path, index=False)
    appropriations.to_parquet(appro_path.with_suffix(".parquet"), index=False)
    revenues.to_csv(rev_path, index=False)
    revenues.to_parquet(rev_path.with_suffix(".parquet"), index=False)
    return appropriations, revenues


def load_cached_datasets(*, year: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    appro_path = appropriations_path(year)
    rev_path = revenues_path(year)
    if not appro_path.exists() or not rev_path.exists():
        raise FileNotFoundError(
            f"Missing cached files in {DATA_DIR}. Run from project root: python3 run.py --refresh"
        )
    appropriations = pd.read_csv(appro_path)
    revenues = pd.read_csv(rev_path)
    appropriations, revenues = _normalize_money_columns(appropriations, revenues)
    return collapse_duplicate_keys(appropriations), revenues


if __name__ == "__main__":
    print(f"Refreshing FY {BUDGET_YEAR} budget data from {SOCRATA_DOMAIN}…")
    appro, rev = refresh_datasets()
    print(f"Saved {len(appro):,} appropriation rows and {len(rev):,} revenue rows to {DATA_DIR}/")
