"""Build the glance-page payload from ordinance files, plus optional official totals.

A new budget year works without editing JavaScript. Set BUDGET_YEAR, refresh
the CSVs, and optionally add official Overview numbers in published_glance.py.
If those official numbers are missing, the river is built from the ordinance.
"""

from __future__ import annotations

import pandas as pd

from pipeline.classifications import (
    fund_meta,
    fund_type_id,
    service_id,
    service_meta,
)
from pipeline.config import BUDGET_YEAR, DATASETS, MERGE_KEYS, SOCRATA_DOMAIN, appropriations_path
from pipeline.published_glance import published_for

DEFAULT_POPULATION = 2_746_388


def collapse_duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    """One row per fund / department / account.

    The portal files sometimes repeat a key. Merging before collapsing
    multiplies those rows. Max amount keeps the largest listed line
    instead of summing copies.
    """
    if df.empty:
        return df
    keys = [k for k in MERGE_KEYS if k in df.columns]
    if not keys or not df.duplicated(keys).any():
        return df

    name_cols = [c for c in ("fund_name", "department_name", "account_name") if c in df.columns]
    money_cols = [c for c in ("ordinance_amount", "recommended_amount") if c in df.columns]
    agg = {c: "last" for c in name_cols}
    agg.update({c: "max" for c in money_cols})
    out = df.groupby(keys, as_index=False).agg(agg)
    if "ordinance_amount" in out.columns and "recommended_amount" in out.columns:
        out["delta_amount"] = out["ordinance_amount"] - out["recommended_amount"]
        pct = out["delta_amount"] / out["recommended_amount"].replace(0, pd.NA) * 100
        out["pct_change"] = pd.to_numeric(pct, errors="coerce").fillna(0.0)
    return out


def unique_on_keys(df: pd.DataFrame, amount_col: str) -> pd.DataFrame:
    keys = [k for k in MERGE_KEYS if k in df.columns]
    if not keys or not df.duplicated(keys).any():
        return df
    return df.sort_values(amount_col).drop_duplicates(keys, keep="last")


def _money_words(n: float) -> str:
    sign = "-" if n < 0 else ""
    abs_n = abs(n)
    if abs_n >= 1e9:
        value = abs_n / 1e9
        text = f"{value:.1f}".replace(".0", "")
        return f"{sign}${text} billion"
    if abs_n >= 1e6:
        return f"{sign}${abs_n / 1e6:.0f} million"
    return f"{sign}${abs_n:,.0f}"


def _money_short(n: float) -> str:
    sign = "-" if n < 0 else ""
    abs_n = abs(n)
    if abs_n >= 1e9:
        return f"{sign}${abs_n / 1e9:.2f}B"
    if abs_n >= 1e6:
        return f"{sign}${abs_n / 1e6:.0f}M"
    return f"{sign}${abs_n:,.0f}"


def annotate(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["fund_type"] = out["fund_name"].map(fund_type_id)
    out["service"] = out["department_name"].map(service_id)
    return out


def _load_year(year: str) -> pd.DataFrame | None:
    path = appropriations_path(year)
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    frame["ordinance_amount"] = pd.to_numeric(frame.get("ordinance_amount"), errors="coerce").fillna(0.0)
    if "department_name" in frame.columns:
        frame["department_name"] = frame["department_name"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    if "fund_name" in frame.columns:
        frame["fund_name"] = frame["fund_name"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return collapse_duplicate_keys(frame)


def _ipf(seed: pd.DataFrame, row_targets: pd.Series, col_targets: pd.Series, rounds: int = 50) -> pd.DataFrame:
    mat = seed.astype(float).reindex(index=row_targets.index, columns=col_targets.index, fill_value=0.0)
    for i in mat.index:
        for j in mat.columns:
            if mat.loc[i, j] <= 0 and row_targets[i] > 0 and col_targets[j] > 0:
                mat.loc[i, j] = 1.0
    for _ in range(rounds):
        row_sums = mat.sum(axis=1).replace(0, 1.0)
        mat = mat.mul(row_targets / row_sums, axis=0)
        col_sums = mat.sum(axis=0).replace(0, 1.0)
        mat = mat.mul(col_targets / col_sums, axis=1)
    return mat


def _totals_from_frame(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float], pd.DataFrame]:
    seed = (
        df.pivot_table(
            values="ordinance_amount",
            index="fund_type",
            columns="service",
            aggfunc="sum",
            fill_value=0.0,
        )
        if not df.empty
        else pd.DataFrame()
    )
    funds = seed.sum(axis=1).to_dict() if not seed.empty else {}
    services = seed.sum(axis=0).to_dict() if not seed.empty else {}
    return funds, services, seed


def _department_rows(df: pd.DataFrame, published: dict | None) -> dict[str, list]:
    official = (published or {}).get("departments")
    if official:
        rows: dict[str, list] = {}
        for sid, items in official.items():
            rows[sid] = [[name, float(amount), sid != "gfr"] for name, amount in items]
        return rows

    grouped = (
        df.groupby(["service", "department_name"], as_index=False)["ordinance_amount"]
        .sum()
        .sort_values("ordinance_amount", ascending=False)
    )
    rows = {}
    for sid, chunk in grouped.groupby("service"):
        rows[sid] = [[str(name), float(amount), True] for name, amount in chunk[["department_name", "ordinance_amount"]].itertuples(index=False)]
    return rows


def _explore_fund(df: pd.DataFrame, fund_id: str) -> str:
    if fund_id == "corporate":
        return "Corporate Fund"
    names = df.loc[df["fund_type"] == fund_id, "fund_name"]
    if names.empty:
        return "All funds"
    counts = names.value_counts()
    return str(counts.index[0]) if fund_id in {"debt"} else "All funds"


def _by_id(items: list[dict], key: str) -> dict | None:
    return next((item for item in items if item["id"] == key), None)


def _build_takes(
    funds: list[dict],
    services: list[dict],
    yoy: list[dict],
    flows: list[list],
    gross: float,
    prior_year: str | None,
) -> list[dict]:
    takes: list[dict] = []
    if not services or gross <= 0:
        return takes

    top = max(services, key=lambda item: item["value"])
    share = top["value"] / gross
    cents = max(1, round(share * 100))
    if top["id"] == "gfr" and share >= 0.25:
        takes.append({
            "id": "gfr",
            "kicker": "Almost half is not a department" if share >= 0.4 else "The largest pile is not a department",
            "title": f"{_money_short(top['value'])} in citywide bills",
            "body": f"{cents}% of the appropriation sits in {top['name']}. {top['blurb']}",
        })
    else:
        takes.append({
            "id": top["id"],
            "kicker": "The largest pile",
            "title": f"{cents}¢ of every dollar",
            "body": top["blurb"],
        })

    grant = _by_id(funds, "grant")
    if grant and grant["value"] > 0:
        dests = [row for row in flows if row[0] == "grant"]
        if dests:
            dest = max(dests, key=lambda row: row[2])
            dest_svc = _by_id(services, dest[1])
            dest_name = dest_svc["name"] if dest_svc else dest[1]
            takes.append({
                "id": "grant",
                "kicker": "Where grants go",
                "title": f"{_money_short(dest[2])} of {_money_short(grant['value'])} in grants",
                "body": f"Most grant dollars go to {dest_name.lower()} — not operating City Hall. {grant['blurb']}",
            })
        else:
            takes.append({
                "id": "grant",
                "kicker": "From other governments",
                "title": f"{round(grant['value'] / gross * 100)}% is grants",
                "body": grant["blurb"],
            })

    if yoy:
        ranked = sorted(yoy, key=lambda row: abs(row["current"] - row["prior"]), reverse=True)
        used = {take["id"] for take in takes}
        swing = next((row for row in ranked if row["id"] not in used and abs(row["current"] - row["prior"]) >= 1), None)
        if swing:
            delta = swing["current"] - swing["prior"]
            takes.append({
                "id": swing["id"],
                "kicker": "The loudest cut" if delta < 0 else (f"The swing from {prior_year}" if prior_year else "The swing"),
                "title": f"{swing['name']} {_money_short(delta)}" if delta < 0 else f"{swing['name']} +{_money_short(delta)}",
                "body": (
                    f"Compared with {prior_year}, this is the pile that moved the most."
                    if prior_year
                    else "Compared with the prior year, this is the pile that moved the most."
                ),
            })

    seen: set[str] = set()
    unique: list[dict] = []
    for take in takes:
        if take["id"] in seen:
            continue
        seen.add(take["id"])
        unique.append(take)
    for item in sorted(services, key=lambda row: row["value"], reverse=True):
        if len(unique) >= 3:
            break
        if item["id"] in seen:
            continue
        unique.append({
            "id": item["id"],
            "kicker": "Next biggest",
            "title": item["name"],
            "body": item["blurb"],
        })
        seen.add(item["id"])
    return unique[:3]


def _filters(funds: list[dict], services: list[dict]) -> list[dict]:
    chips = [{"id": "all", "label": "Everything"}]
    if any(item.get("group") == "local" for item in funds):
        chips.append({"id": "local", "label": "Local only"})
    if _by_id(funds, "grant"):
        chips.append({"id": "grantTop", "label": "Grants only"})
    if _by_id(services, "gfr"):
        chips.append({"id": "gfr", "label": "City bills"})
    return chips


def _hints(
    funds: list[dict],
    services: list[dict],
    flows: list[list],
    *,
    local: float,
    grant: float,
    net: float,
    transfers: float,
) -> dict[str, str]:
    hints: dict[str, str] = {}
    gfr = _by_id(services, "gfr")
    safety = _by_id(services, "safety")
    infra = _by_id(services, "infra")
    if gfr and safety and infra and gfr["value"] > safety["value"] + infra["value"]:
        hints["gfr"] = (
            "City bills — pensions, debt, health insurance, lawsuits — "
            "are larger than police, fire, and streets put together."
        )
    elif gfr:
        hints["gfr"] = gfr["blurb"]

    grant_item = _by_id(funds, "grant")
    dests = [row for row in flows if row[0] == "grant"]
    if grant_item and dests:
        dest = max(dests, key=lambda row: row[2])
        dest_svc = _by_id(services, dest[1])
        dest_name = dest_svc["name"].lower() if dest_svc else "one function"
        hints["grant"] = f"Most grant dollars go to {dest_name}, not the everyday Corporate Fund."
        hints["grantTop"] = hints["grant"]
    elif grant_item:
        hints["grant"] = grant_item["blurb"]
        hints["grantTop"] = grant_item["blurb"]

    if local and transfers:
        published_local = max(0.0, net - grant)
        hints["local"] = (
            f"Local funds are {_money_short(local)} before transfer deductions. "
            f"After OBM's subtraction they publish {_money_short(published_local)}."
        )
    elif local:
        hints["local"] = f"Local funds are {_money_short(local)} — every non-grant city pot."
    return hints


def _featured_departments(df: pd.DataFrame) -> list[str]:
    if df.empty or "department_name" not in df.columns:
        return []
    skip = {"Finance General", "All departments", ""}
    ranked = (
        df.groupby("department_name", as_index=False)["ordinance_amount"]
        .sum()
        .sort_values("ordinance_amount", ascending=False)
    )
    names = [str(name) for name in ranked["department_name"] if str(name) not in skip]
    return names[:10]


def _aliases(names: list[str]) -> dict[str, str]:
    rules = (
        (("police department",), ("police", "cpd", "cops")),
        (("fire department",), ("fire", "cfd")),
        (("public library",), ("library",)),
        (("department of housing",), ("housing",)),
        (("transportation",), ("cdot", "transportation")),
        (("aviation",), ("aviation", "airport")),
        (("water management",), ("water",)),
        (("streets and sanitation",), ("streets", "sanitation")),
        (("public health",), ("health",)),
        (("family and support",), ("dfss",)),
    )
    aliases: dict[str, str] = {}
    for needles, keys in rules:
        match = next((name for name in names if all(needle in name.lower() for needle in needles)), None)
        if match:
            for key in keys:
                aliases[key] = match
    return aliases


def _yoy_rows(
    fund_values: dict[str, float],
    service_values: dict[str, float],
    funds_meta: dict[str, dict],
    services_meta: dict[str, dict],
    prior_funds: dict[str, float] | None,
    prior_services: dict[str, float] | None,
) -> list[dict]:
    if not prior_funds and not prior_services:
        return []
    rows = []
    for fid, current in fund_values.items():
        prior = (prior_funds or {}).get(fid)
        if prior is None:
            continue
        meta = funds_meta[fid]
        rows.append({
            "id": fid,
            "kind": "fund",
            "name": meta["name"],
            "prior": float(prior),
            "current": float(current),
        })
    for sid, current in service_values.items():
        prior = (prior_services or {}).get(sid)
        if prior is None:
            continue
        meta = services_meta[sid]
        rows.append({
            "id": sid,
            "kind": "service",
            "name": meta["name"],
            "prior": float(prior),
            "current": float(current),
        })
    rows = [row for row in rows if abs(row["current"] - row["prior"]) >= 1]
    rows.sort(key=lambda row: abs(row["current"] - row["prior"]), reverse=True)
    return rows


def build_glance_payload(appropriations: pd.DataFrame, *, year: str | None = None) -> dict:
    year = str(year or BUDGET_YEAR)
    published = published_for(year)
    funds_meta = fund_meta()
    services_meta = service_meta()

    current = annotate(collapse_duplicate_keys(appropriations))
    ordinance_funds, ordinance_services, seed = _totals_from_frame(current)

    if published and published.get("funds") and published.get("services"):
        fund_values = {key: float(value) for key, value in published["funds"].items() if value}
        service_values = {key: float(value) for key, value in published["services"].items() if value}
        row_t = pd.Series(fund_values)
        col_t = pd.Series(service_values)
        fitted = _ipf(seed, row_t, col_t)
        source = "published"
    else:
        fund_values = {key: float(value) for key, value in ordinance_funds.items() if value}
        service_values = {key: float(value) for key, value in ordinance_services.items() if value}
        fitted = seed
        source = "ordinance"

    gross = float(sum(fund_values.values()))
    transfers = float((published or {}).get("transfers") or 0)
    net = float((published or {}).get("net") or (gross - transfers))
    population = int((published or {}).get("population") or DEFAULT_POPULATION)
    local = float(sum(value for key, value in fund_values.items() if funds_meta.get(key, {}).get("group") == "local"))
    grant = float(fund_values.get("grant") or 0)

    funds = []
    for fid, meta in funds_meta.items():
        value = fund_values.get(fid)
        if not value:
            continue
        item = dict(meta)
        item["value"] = value
        item["exploreFund"] = _explore_fund(current, fid)
        funds.append(item)

    services = []
    for sid, meta in services_meta.items():
        value = service_values.get(sid)
        if not value:
            continue
        item = dict(meta)
        item["value"] = value
        services.append(item)

    flows = []
    if not fitted.empty:
        for fid in fitted.index:
            for sid in fitted.columns:
                value = float(fitted.loc[fid, sid])
                if value >= 1:
                    flows.append([fid, sid, round(value)])

    prior_year = str(int(year) - 1) if year.isdigit() else None
    prior_funds = None
    prior_services = None
    if published and published.get("prior"):
        prior_funds = {key: float(value) for key, value in published["prior"].get("funds", {}).items()}
        prior_services = {key: float(value) for key, value in published["prior"].get("services", {}).items()}
    elif prior_year:
        prior_frame = _load_year(prior_year)
        if prior_frame is not None:
            prior_funds, prior_services, _ = _totals_from_frame(annotate(prior_frame))

    yoy = _yoy_rows(fund_values, service_values, funds_meta, services_meta, prior_funds, prior_services)
    takes = _build_takes(funds, services, yoy, flows, gross, prior_year)
    departments = _department_rows(current, published)
    featured = _featured_departments(current)
    aliases = _aliases(featured + [row[0] for rows in departments.values() for row in rows])
    filters = _filters(funds, services)
    hints = _hints(funds, services, flows, local=local, grant=grant, net=net, transfers=transfers)
    per_resident = round(net / population) if population else 0

    unmapped = sorted(
        current.loc[current["service"] == "other", "department_name"].dropna().astype(str).unique().tolist()
    )

    headline = f"The whole {_money_words(net)}"
    if source == "published" and transfers:
        caption = (
            f"Height is money. The drawing is the {_money_words(gross)} appropriation; "
            f"OBM publishes {_money_words(net)} after removing {_money_words(transfers)} counted twice. "
            f"About ${per_resident:,} per resident."
        )
        lede = "Three facts, then a river you can poke. Click a takeaway or a bar — the rest fades, and the story updates underneath."
        colophon = (
            f"At a glance uses the official {year} Budget Overview. Ordinance uses the adopted file from the Data Portal. "
            "An appropriation is permission to spend, not a receipt. Money also moves between funds, and some spending is paid with grants or leftover balances."
        )
    else:
        caption = (
            f"Height is money. Built from the adopted ordinance for {year} "
            f"({_money_words(gross)}). About ${per_resident:,} per resident."
        )
        lede = "Three facts, then a river you can poke. Official Overview totals were not on file for this year, so this map follows the ordinance."
        colophon = (
            f"At a glance is built from the {year} ordinance file. Add official Overview totals in "
            "src/pipeline/published_glance.py if you want the published net figure. "
            "An appropriation is permission to spend, not a receipt."
        )

    overview_url = (published or {}).get("overview_url")
    source_links = []
    if overview_url:
        source_links.append({"label": f"{year} Budget Overview", "href": overview_url})
    source_links.extend([
        {"label": "ordinance appropriations", "href": f"https://{SOCRATA_DOMAIN}/d/{DATASETS['ordinance_appropriations']}"},
        {"label": "recommended appropriations", "href": f"https://{SOCRATA_DOMAIN}/d/{DATASETS['recommended_appropriations']}"},
        {"label": "estimated revenue", "href": f"https://{SOCRATA_DOMAIN}/d/{DATASETS['ordinance_revenue']}"},
    ])

    return {
        "year": year,
        "prior_year": prior_year if yoy else None,
        "source": source,
        "gross": gross,
        "net": net,
        "transfers": transfers,
        "local": local,
        "grant": grant,
        "population": population,
        "headline": headline,
        "lede": lede,
        "caption": caption,
        "colophon": colophon,
        "source_links": source_links,
        "yoy_kicker": f"Since {prior_year}" if prior_year and yoy else "Year to year",
        "yoy_title": "What grew, what shrank" if yoy else "No prior year on file",
        "yoy_caption": (
            "Light is last year, dark is this year. The two loudest moves are marked."
            if yoy
            else f"Drop budget_appropriations_comparison_{prior_year}.csv in src/data, or add prior totals in published_glance.py."
        ),
        "funds": funds,
        "services": services,
        "flows": flows,
        "departments": departments,
        "takes": takes,
        "filters": filters,
        "hints": hints,
        "yoy": yoy,
        "featured_departments": featured,
        "aliases": aliases,
        "boot_title": f"Opening the {year} budget",
        "boot_hint": "The ordinance file is large. Hang on a moment.",
        "kicker": f"Chicago budget · {year}",
        "aside_glance": "Official all-funds map" if source == "published" else "Ordinance all-funds map",
        "aside_explore": "The version City Council passed",
        "gfr_explore_department": "Finance General",
        "unmapped_departments": unmapped,
    }


def log_glance_build(payload: dict, *, verbose: bool = True) -> None:
    if not verbose:
        return
    print(
        f"  glance FY {payload['year']}: {payload['source']} "
        f"gross=${payload['gross']:,.0f} net=${payload['net']:,.0f}"
    )
    if payload["unmapped_departments"]:
        names = ", ".join(payload["unmapped_departments"][:8])
        extra = "…" if len(payload["unmapped_departments"]) > 8 else ""
        print(f"  glance unmapped departments → Other: {names}{extra}")
