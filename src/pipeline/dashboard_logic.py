"""Chart, narrative, and view-building logic for the static dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from pipeline.config import BUDGET_YEAR, appropriations_path, revenues_path
from pipeline.glance import build_glance_payload, collapse_duplicate_keys, log_glance_build

SRC_ROOT = Path(__file__).resolve().parents[1]
APPROPRIATIONS_PATH = appropriations_path()
REVENUES_PATH = revenues_path()

ALL_FUNDS = "All funds"
ALL_DEPARTMENTS = "All departments"
CORPORATE = "Corporate Fund"
TOP_N = 12

INK = "#1c1917"
MUTED = "#736c64"
BLUE = "#41B6E6"
WHITE = "#FFFFFF"
RED = "#E4002B"
LAKE = BLUE
SAND = WHITE
UP = BLUE
DOWN = RED
GRID = "#e6e1dd"
FONT = "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"

# Blue is money raised in Chicago. Red is money from other governments or transfers.
GROUP_COLORS = {
    "Local Tax": BLUE,
    "Local Non-Tax Revenue": "rgba(65, 182, 230, 0.45)",
    "Intergovernmental Revenue": RED,
    "Proceeds and Transfers In": "rgba(228, 0, 43, 0.55)",
}

PURPOSE_ORDER = [
    "People and benefits",
    "Help for residents",
    "Contracts and outside services",
    "Aldermanic expenses",
    "Lawsuits and claims",
    "Buildings, vehicles, and equipment",
    "Debt",
    "Reserves",
    "Other city costs",
]

PLOT_CONFIG = {
    "responsive": True,
    "displaylogo": False,
    "displayModeBar": False,
}


def load_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [path.name for path in (APPROPRIATIONS_PATH, REVENUES_PATH) if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            f"Missing {joined} in {SRC_ROOT / 'data'}. "
            "Open START_HERE.html, then run: python3 run.py --refresh"
        )

    appropriations = pd.read_csv(APPROPRIATIONS_PATH)
    revenues = pd.read_csv(REVENUES_PATH)
    for frame in (appropriations, revenues):
        text_columns = frame.select_dtypes(include=["object"]).columns
        frame[text_columns] = frame[text_columns].apply(lambda series: series.str.replace(r"\s+", " ", regex=True).str.strip())

    appropriations["ordinance_amount"] = pd.to_numeric(appropriations["ordinance_amount"], errors="coerce").fillna(0.0)
    appropriations["recommended_amount"] = pd.to_numeric(appropriations["recommended_amount"], errors="coerce").fillna(0.0)
    appropriations = collapse_duplicate_keys(appropriations)
    appropriations["delta_amount"] = appropriations["ordinance_amount"] - appropriations["recommended_amount"]
    appropriations["purpose"] = appropriations["account_name"].map(spending_purpose)
    revenues["estimated_revenue"] = pd.to_numeric(revenues["estimated_revenue"], errors="coerce").fillna(0.0)
    return appropriations, revenues


def spending_purpose(account_name: str) -> str:
    """Group ordinance account names into a short list a reader can scan."""
    name = str(account_name).lower()
    if "reserve" in name:
        return "Reserves"
    if any(word in name for word in ("bond", "interest on", "term note", "loan")):
        return "Debt"
    if any(
        word in name
        for word in (
            "salary",
            "wage",
            "overtime",
            "payroll",
            "personnel service",
            "fringe",
            "pension",
            "annuity",
            "duty availability",
            "holiday",
            "uniform allowance",
            "trainee",
            "specialty pay",
            "furlough",
            "social security",
            "hmo",
            "dental",
            "eligible employees",
            "medicare",
            "compensatory",
            "workers' compensation",
            "workers compensation",
            "injured on duty",
        )
    ):
        return "People and benefits"
    if "aldermanic expense" in name:
        return "Aldermanic expenses"
    if any(word in name for word in ("judgment", "tort", "outside counsel")):
        return "Lawsuits and claims"
    if any(
        word in name
        for word in (
            "construction of",
            "purchase of vehicles",
            "machinery",
            "furniture",
            "hardware",
            "vehicles",
        )
    ):
        return "Buildings, vehicles, and equipment"
    if any(
        word in name
        for word in (
            "delegate agenc",
            "homeless",
            "youth",
            "violence",
            "mentoring",
            "workforce",
            "rebate",
            "cultural programming",
            "library books",
            "gender based",
            "reproductive",
        )
    ):
        return "Help for residents"
    if any(
        word in name
        for word in (
            "professional",
            "technical service",
            "software",
            "information technology",
            "it maintenance",
            "it development",
            "waste disposal",
            "maintenance",
            "repair",
            "contract",
        )
    ):
        return "Contracts and outside services"
    return "Other city costs"


def money(value: float) -> str:
    """Plain amount, without a dollar sign.

    Taipy runs MathJax on text, and a sentence with two "$" characters is
    treated as a formula. Dollar signs are added only on the single-number tiles.
    """
    sign = "-" if value < 0 else ""
    amount = abs(float(value))
    if amount >= 1_000_000_000:
        return f"{sign}{amount / 1_000_000_000:.2f} billion"
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        shown = f"{millions:.0f}" if millions >= 100 else f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"{sign}{shown} million"
    return f"{sign}{amount:,.0f}"


def money_change(value: float) -> str:
    if value > 0:
        return "+" + money(value)
    return money(value)


def money_tile(value: float, *, signed: bool = False) -> str:
    """One dollar sign, for a tile that contains only this amount."""
    text = money_change(value) if signed else money(value)
    if text.startswith("+"):
        return "+$" + text[1:]
    if text.startswith("-"):
        return "-$" + text[1:]
    return "$" + text


def percent_phrase(delta: float, base: float) -> str:
    if base == 0:
        return "no recommendation to compare"
    return f"{delta / base * 100:+.1f}%"


def short_label(name: str, limit: int = 36) -> str:
    text = " ".join(str(name).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def choose_scale(values: pd.Series) -> tuple[float, str]:
    peak = float(values.abs().max()) if len(values) else 0.0
    if peak >= 1_000_000_000:
        return 1_000_000_000, "Billion dollars"
    if peak >= 1_000_000:
        return 1_000_000, "Million dollars"
    return 1.0, "Dollars"


def base_layout(x_title: str) -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=13),
        margin=dict(l=8, r=18, t=36, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=12, color=MUTED)),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=12, color=MUTED)),
            gridcolor=GRID,
            zerolinecolor="#cfc6b8",
            tickfont=dict(size=12, color=MUTED),
            separatethousands=True,
        ),
        yaxis=dict(automargin=True, title="", tickfont=dict(size=12, color=INK)),
        hoverlabel=dict(font_family=FONT, font_size=13),
        dragmode=False,
    )


def empty_figure(message: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=24, r=24, t=24, b=24),
        annotations=[
            dict(
                text=message,
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                font=dict(family=FONT, size=15, color=MUTED),
            )
        ],
    )
    return figure


def chart_comparison(frame: pd.DataFrame, label_column: str) -> go.Figure:
    """Grouped bars: mayor's recommendation and the adopted ordinance."""
    if frame.empty:
        return empty_figure("Nothing to show for this mix of fund and department.")

    plotted = frame.sort_values("adopted", ascending=True)
    scale, unit = choose_scale(pd.concat([plotted["adopted"], plotted["recommended"]]))
    total = float(frame["adopted"].sum()) or 1.0
    labels = [short_label(name, 32) for name in plotted[label_column]]
    share = plotted["adopted"] / total * 100
    figure = go.Figure()
    figure.add_bar(
        y=labels,
        x=plotted["recommended"] / scale,
        name="Mayor's recommendation",
        orientation="h",
        marker=dict(color=WHITE, line=dict(color=BLUE, width=1.5)),
        customdata=list(zip(plotted[label_column], plotted["recommended"], share)),
        hovertemplate=(
            "%{customdata[0]}<br>Mayor's recommendation: %{customdata[1]:$,.0f}<extra></extra>"
        ),
    )
    figure.add_bar(
        y=labels,
        x=plotted["adopted"] / scale,
        name="Adopted by City Council",
        orientation="h",
        marker_color=BLUE,
        customdata=list(zip(plotted[label_column], plotted["adopted"], share)),
        hovertemplate=(
            "%{customdata[0]}<br>Adopted: %{customdata[1]:$,.0f}"
            "<br>%{customdata[2]:.1f}% of this view<extra></extra>"
        ),
    )
    figure.update_layout(barmode="group", bargap=0.28, bargroupgap=0.08, **base_layout(unit))
    figure.update_traces(marker_line_width=0, selector=dict(name="Adopted by City Council"))
    return figure


def chart_purpose(frame: pd.DataFrame) -> go.Figure:
    if frame.empty:
        return empty_figure("No spending lines in this view.")

    plotted = frame.sort_values("adopted", ascending=True)
    scale, unit = choose_scale(plotted["adopted"])
    total = float(frame["adopted"].sum()) or 1.0
    share = plotted["adopted"] / total * 100
    figure = go.Figure()
    figure.add_bar(
        y=plotted["purpose"],
        x=plotted["adopted"] / scale,
        orientation="h",
        marker_color=BLUE,
        customdata=list(zip(plotted["adopted"], share)),
        hovertemplate="%{y}<br>%{customdata[0]:$,.0f}<br>%{customdata[1]:.1f}% of this view<extra></extra>",
        showlegend=False,
    )
    figure.update_layout(**base_layout(unit))
    figure.update_traces(marker_line_width=0)
    return figure


def chart_change(frame: pd.DataFrame, label_column: str) -> go.Figure:
    changed = frame[frame["delta"] != 0]
    if changed.empty:
        return empty_figure("Council left this one alone. It matches the mayor's draft.")

    rising = changed[changed["delta"] > 0].nlargest(8, "delta")
    falling = changed[changed["delta"] < 0].nsmallest(8, "delta")
    plotted = pd.concat([falling, rising]).drop_duplicates(subset=[label_column]).sort_values("delta")
    scale, unit = choose_scale(plotted["delta"])
    colors = [UP if value > 0 else DOWN for value in plotted["delta"]]
    figure = go.Figure()
    figure.add_bar(
        y=[short_label(name, 34) for name in plotted[label_column]],
        x=plotted["delta"] / scale,
        orientation="h",
        marker_color=colors,
        customdata=list(zip(plotted[label_column], plotted["delta"])),
        hovertemplate="%{customdata[0]}<br>Council change: %{customdata[1]:+$,.0f}<extra></extra>",
        showlegend=False,
    )
    layout = base_layout(f"Change from the recommendation, {unit.lower()}")
    layout["xaxis"]["zeroline"] = True
    layout["xaxis"]["zerolinewidth"] = 1
    figure.update_layout(**layout)
    figure.update_traces(marker_line_width=0)
    return figure


def chart_revenue(frame: pd.DataFrame) -> go.Figure:
    if frame.empty or float(frame["estimated_revenue"].sum()) == 0:
        return empty_figure("This fund has no revenue estimate on file. Grant funds often work that way.")

    totals = (
        frame.groupby(["revenue_group_type", "revenue_category"], as_index=False)["estimated_revenue"]
        .sum()
        .sort_values("estimated_revenue", ascending=True)
    )
    scale, unit = choose_scale(totals["estimated_revenue"])
    grand = float(totals["estimated_revenue"].sum()) or 1.0
    figure = go.Figure()
    for group, color in GROUP_COLORS.items():
        subset = totals[totals["revenue_group_type"] == group]
        if subset.empty:
            continue
        figure.add_bar(
            y=[short_label(name, 34) for name in subset["revenue_category"]],
            x=subset["estimated_revenue"] / scale,
            name=group,
            orientation="h",
            marker_color=color,
            customdata=list(zip(subset["revenue_category"], subset["estimated_revenue"], subset["estimated_revenue"] / grand * 100)),
            hovertemplate=(
                "%{customdata[0]}<br>%{customdata[1]:$,.0f}<br>%{customdata[2]:.1f}% of estimated revenue<extra></extra>"
            ),
        )
    other = totals[~totals["revenue_group_type"].isin(GROUP_COLORS)]
    if not other.empty:
        figure.add_bar(
            y=[short_label(name, 34) for name in other["revenue_category"]],
            x=other["estimated_revenue"] / scale,
            name="Other",
            orientation="h",
            marker_color=BLUE,
            customdata=list(zip(other["revenue_category"], other["estimated_revenue"])),
            hovertemplate="%{customdata[0]}<br>%{customdata[1]:$,.0f}<extra></extra>",
        )
    figure.update_layout(barmode="relative", **base_layout(unit))
    figure.update_traces(marker_line_width=0)
    return figure


def department_totals(frame: pd.DataFrame) -> pd.DataFrame:
    totals = (
        frame.groupby("department_name", as_index=False)[["ordinance_amount", "recommended_amount", "delta_amount"]]
        .sum()
        .rename(
            columns={
                "department_name": "department",
                "ordinance_amount": "adopted",
                "recommended_amount": "recommended",
                "delta_amount": "delta",
            }
        )
    )
    return totals.sort_values("adopted", ascending=False)


def account_totals(frame: pd.DataFrame) -> pd.DataFrame:
    totals = (
        frame.groupby("account_name", as_index=False)[["ordinance_amount", "recommended_amount", "delta_amount"]]
        .sum()
        .rename(
            columns={
                "account_name": "account",
                "ordinance_amount": "adopted",
                "recommended_amount": "recommended",
                "delta_amount": "delta",
            }
        )
    )
    return totals.sort_values("adopted", ascending=False)


def purpose_totals(frame: pd.DataFrame) -> pd.DataFrame:
    totals = (
        frame.groupby("purpose", as_index=False)["ordinance_amount"]
        .sum()
        .rename(columns={"ordinance_amount": "adopted"})
    )
    totals["purpose"] = pd.Categorical(totals["purpose"], categories=PURPOSE_ORDER, ordered=True)
    return totals[totals["adopted"] > 0].sort_values("adopted", ascending=False)


def line_item_table(frame: pd.DataFrame, department: str) -> tuple[pd.DataFrame, str]:
    rows = frame.copy()
    rows["Account"] = rows["account_name"]
    rows["Fund"] = rows["fund_name"]
    rows["Department"] = rows["department_name"]
    rows["Recommended"] = rows["recommended_amount"].round(0)
    rows["Adopted"] = rows["ordinance_amount"].round(0)
    rows["change"] = rows["delta_amount"].round(0)
    rows = rows.sort_values("Adopted", ascending=False)
    keep = ["Fund", "Department", "Account", "Recommended", "Adopted", "change"]

    if department == ALL_DEPARTMENTS and len(rows) > 200:
        shown = rows.head(200)
        caption = (
            f"These are the 200 biggest lines of {len(rows):,} in this view. "
            "Pick a department if you want every line. Type a word like overtime or homeless in the filter row."
        )
    else:
        shown = rows
        caption = (
            f"{len(shown):,} ordinance lines in this view. "
            "Type a word in the filter row — overtime, salaries, homeless — and the table will narrow."
        )
    return shown[keep].reset_index(drop=True), caption


def departments_for(fund: str) -> list[str]:
    frame = APPROPRIATIONS if fund == ALL_FUNDS else APPROPRIATIONS[APPROPRIATIONS["fund_name"] == fund]
    names = frame.groupby("department_name")["ordinance_amount"].sum().sort_values(ascending=False).index.tolist()
    return [ALL_DEPARTMENTS, *names]


def build_view(fund: str, department: str) -> dict:
    fund = fund if fund in FUND_OPTIONS else CORPORATE
    options = departments_for(fund)
    if department not in options:
        department = ALL_DEPARTMENTS

    spending = APPROPRIATIONS if fund == ALL_FUNDS else APPROPRIATIONS[APPROPRIATIONS["fund_name"] == fund]
    if department != ALL_DEPARTMENTS:
        spending = spending[spending["department_name"] == department]
    revenue = REVENUES if fund == ALL_FUNDS else REVENUES[REVENUES["fund_name"] == fund]

    adopted = float(spending["ordinance_amount"].sum())
    recommended = float(spending["recommended_amount"].sum())
    delta = adopted - recommended
    revenue_total = float(revenue["estimated_revenue"].sum())
    if department == ALL_DEPARTMENTS:
        dept_frame = department_totals(APPROPRIATIONS if fund == ALL_FUNDS else APPROPRIATIONS[APPROPRIATIONS["fund_name"] == fund])
        left = dept_frame.head(TOP_N).rename(columns={"department": "label"})
        left_source = left.rename(columns={"label": "department"})
        left_label = "department"
        left_title = "Who gets the most money?"
        shown = min(TOP_N, len(dept_frame))
        left_caption = (
            f"The {shown} offices with the biggest adopted budgets. "
            "White is what the mayor asked for. Blue is what Council passed. Hover a bar for the exact dollars."
        )
        change_source = dept_frame
        change_label = "department"
        change_title = "What did City Council change?"
        change_caption = (
            "This is the difference between the mayor's draft and the law. "
            "Blue means Council added money. Red means they cut it. "
            "The chart keeps the eight biggest adds and the eight biggest cuts."
        )
    else:
        accounts = account_totals(spending)
        left_source = accounts.head(TOP_N)
        left_label = "account"
        left_title = f"What does {spoken_name(department)} spend on?"
        left_caption = (
            f"The biggest accounts inside {department}. "
            "White is the mayor's ask. Blue is the adopted line."
        )
        change_source = accounts.rename(columns={"account": "department"})
        change_label = "department"
        change_title = f"What did Council change at {spoken_name(department)}?"
        change_caption = (
            "Accounts where the final number is different from the mayor's draft. "
            "Blue was added. Red was cut."
        )

    purposes = purpose_totals(spending)
    reserve_share = 0.0
    if adopted and not purposes.empty:
        reserve_rows = purposes.loc[purposes["purpose"] == "Reserves", "adopted"]
        reserve_share = float(reserve_rows.sum()) / adopted
    purpose_title = "What is the city actually paying for?"
    purpose_caption = (
        "The ordinance uses hundreds of account names. "
        "We grouped them into everyday buckets — people, help for residents, contracts, and so on — so you can read the shape of the budget."
    )
    if reserve_share > 0.2:
        purpose_caption += (
            " A lot of this view is labeled reserves. That is usually grant money set aside as permission to spend later, not cash in a savings account."
        )

    if department == ALL_DEPARTMENTS:
        story = story_for_departments(dept_frame, adopted, recommended, fund)
    else:
        story = story_for_one_department(department, adopted, recommended, delta)

    if fund == ALL_FUNDS:
        scope_note = (
            "You are looking at every fund at once: grants, airports, water, pensions, and the operating budget. "
            "That is why the total looks huge. Switch to Corporate Fund if you want the everyday city budget."
        )
        scope_name = "All funds"
    elif fund == CORPORATE:
        scope_note = (
            "The Corporate Fund is the city's checking account for daily work — police, fire, streets, the library, City Hall. "
            "Airports, water, pensions, and most grants live in other funds."
        )
        scope_name = CORPORATE
    else:
        scope_note = (
            f"This is only the {fund}. "
            "It is one slice of the city, not the whole budget."
        )
        scope_name = fund

    dept_count = spending["department_name"].nunique()
    scope_line = f"Looking at {scope_name} · {dept_count} departments · {len(spending):,} ordinance lines"

    show_finance = department == ALL_DEPARTMENTS and "Finance General" in set(left_source[left_label].head(5))
    finance_note = (
        "Finance General is not an office you can walk into. "
        "It is the city's catch-all for bills that do not belong to one department — pensions, health insurance, lawsuits."
    )

    if revenue_total <= 0:
        revenue_hint = "No income estimate is on file for this fund"
        revenue_caption = (
            "Some funds, especially grants, get permission to spend from an award. "
            "They do not always file a local tax or fee forecast next to that permission."
        )
    elif department != ALL_DEPARTMENTS:
        revenue_hint = "Income for the whole fund, not this office"
        revenue_caption = (
            f"The city expects {scope_name_for(fund)} to take in about {money(revenue_total)} dollars. "
            "That is not this department's piggy bank — revenue is counted at the fund. "
            "Blue is money Chicago collects itself. Red is money from Springfield, Washington, or another city fund."
        )
    else:
        gap = adopted - revenue_total
        direction = "higher" if gap > 0 else "lower"
        revenue_hint = "What this fund hopes to collect"
        revenue_caption = (
            f"The city expects about {money(revenue_total)} dollars to come in. "
            f"The spending permission on this page is {money(abs(gap))} dollars {direction} than that. "
            "That is normal: an appropriation is permission, not a receipt, and money also moves between funds. "
            "Blue is money Chicago collects itself. Red is money from other governments or transfers."
        )

    lines, table_caption = line_item_table(spending, department)
    table_title = "Want to look up a specific line?"
    if fund == ALL_FUNDS:
        revenue_title = "Where does the money come from?"
    else:
        revenue_title = f"Where does the {fund} get its money?"

    return {
        "department_options": options,
        "adopted_label": money_tile(adopted),
        "recommended_label": money_tile(recommended),
        "delta_label": money_tile(delta, signed=True),
        "delta_hint": describe_change(delta, recommended),
        "show_up": delta > 0,
        "show_down": delta < 0,
        "show_flat": delta == 0,
        "revenue_label": money_tile(revenue_total) if revenue_total else "None filed",
        "revenue_hint": revenue_hint,
        "story": story,
        "scope_line": scope_line,
        "scope_note": scope_note,
        "left_title": left_title,
        "left_caption": left_caption,
        "left_figure": left_chart(left_source, left_label),
        "show_finance_note": show_finance,
        "finance_note": finance_note,
        "purpose_title": purpose_title,
        "purpose_caption": purpose_caption,
        "purpose_figure": chart_purpose(purposes),
        "change_title": change_title,
        "change_caption": change_caption,
        "change_figure": chart_change(change_source, change_label),
        "revenue_title": revenue_title,
        "revenue_caption": revenue_caption,
        "revenue_figure": chart_revenue(revenue),
        "line_items": lines,
        "table_title": table_title,
        "table_caption": table_caption,
    }


def story_for_departments(dept_frame: pd.DataFrame, adopted: float, recommended: float, fund: str) -> str:
    delta = adopted - recommended
    change = percent_phrase(delta, recommended)
    if fund == ALL_FUNDS:
        lead = (
            f"Add every city fund together and you get {money(adopted)} dollars — "
            f"{money_change(delta)} dollars ({change}) from the mayor's first draft."
        )
    elif fund == CORPORATE:
        lead = (
            f"For the everyday city budget, Council passed {money(adopted)} dollars — "
            f"{money_change(delta)} dollars ({change}) from what the mayor asked for."
        )
    else:
        lead = (
            f"In the {fund}, Council passed {money(adopted)} dollars — "
            f"{money_change(delta)} dollars ({change}) from the mayor's draft."
        )

    changed = dept_frame[dept_frame["delta"] != 0]
    if changed.empty:
        return f"{lead} Every department here matches the mayor's number."

    added = changed.loc[changed["delta"].idxmax()]
    cut = changed.loc[changed["delta"].idxmin()]
    extras = []
    if added["delta"] > 0:
        extras.append(f"The biggest add is {added['department']}, {money(added['delta'])} dollars more.")
    if cut["delta"] < 0 and cut["department"] != added["department"]:
        extras.append(f"The biggest cut is {cut['department']}, {money(abs(cut['delta']))} dollars less.")
    return " ".join([lead, *extras])


def story_for_one_department(department: str, adopted: float, recommended: float, delta: float) -> str:
    change = percent_phrase(delta, recommended)
    if recommended == 0:
        return (
            f"Zoomed in on {spoken_name(department)}: Council passed {money(adopted)} dollars. "
            "The mayor's draft for this view was zero, so there is not much to compare."
        )
    share = abs(delta) / recommended
    if share < 0.005:
        return (
            f"Zoomed in on {spoken_name(department)}: Council passed {money(adopted)} dollars. "
            "That is basically the mayor's draft — they barely moved it."
        )
    if delta > 0:
        return (
            f"Zoomed in on {spoken_name(department)}: Council passed {money(adopted)} dollars. "
            f"They added {money(delta)} dollars ({change}) on top of the mayor's ask."
        )
    return (
        f"Zoomed in on {spoken_name(department)}: Council passed {money(adopted)} dollars. "
        f"They trimmed {money(abs(delta))} dollars ({change}) from the mayor's ask."
    )


def describe_change(delta: float, recommended: float) -> str:
    if recommended == 0:
        return "The mayor's draft for this view was zero"
    share = abs(delta) / recommended * 100
    if delta > 0:
        return f"{share:.1f}% more than the mayor asked for"
    if delta < 0:
        return f"{share:.1f}% less than the mayor asked for"
    return "Same as the mayor's draft"


def scope_name_for(fund: str) -> str:
    if fund == ALL_FUNDS:
        return "all funds"
    return fund


def spoken_name(name: str) -> str:
    if name.startswith(("Chicago ", "Department ", "Office ", "Mayor", "Board ", "Civilian ", "City ", "Community ")):
        return "the " + name
    return name


def left_chart(frame: pd.DataFrame, label_column: str) -> go.Figure:
    chart_frame = frame.rename(columns={label_column: "label"})[["label", "adopted", "recommended"]]
    return chart_comparison(chart_frame, "label")


APPROPRIATIONS: pd.DataFrame
REVENUES: pd.DataFrame
FUND_SIZES: pd.Series
FUND_OPTIONS: list[str]


def initialize_from_disk() -> None:
    global APPROPRIATIONS, REVENUES, FUND_SIZES, FUND_OPTIONS
    global APPROPRIATIONS_PATH, REVENUES_PATH
    APPROPRIATIONS_PATH = appropriations_path()
    REVENUES_PATH = revenues_path()
    APPROPRIATIONS, REVENUES = load_tables()
    FUND_SIZES = APPROPRIATIONS.groupby("fund_name")["ordinance_amount"].sum().sort_values(ascending=False)
    FUND_OPTIONS = [ALL_FUNDS, CORPORATE, *[name for name in FUND_SIZES.index if name != CORPORATE]]


def view_key(fund: str, department: str) -> str:
    return f"{fund}|{department}"


def serialize_view(view: dict) -> dict:
    if view["show_up"]:
        delta_trend = "up"
    elif view["show_down"]:
        delta_trend = "down"
    else:
        delta_trend = "flat"

    return {
        "adopted_label": view["adopted_label"],
        "recommended_label": view["recommended_label"],
        "delta_label": view["delta_label"],
        "delta_hint": view["delta_hint"],
        "delta_trend": delta_trend,
        "revenue_label": view["revenue_label"],
        "revenue_hint": view["revenue_hint"],
        "story": view["story"],
        "scope_line": view["scope_line"],
        "scope_note": view["scope_note"],
        "left_title": view["left_title"],
        "left_caption": view["left_caption"],
        "left_figure": json.loads(view["left_figure"].to_json()),
        "show_finance_note": view["show_finance_note"],
        "finance_note": view["finance_note"],
        "purpose_title": view["purpose_title"],
        "purpose_caption": view["purpose_caption"],
        "purpose_figure": json.loads(view["purpose_figure"].to_json()),
        "change_title": view["change_title"],
        "change_caption": view["change_caption"],
        "change_figure": json.loads(view["change_figure"].to_json()),
        "revenue_title": view["revenue_title"],
        "revenue_caption": view["revenue_caption"],
        "revenue_figure": json.loads(view["revenue_figure"].to_json()),
        "line_items": view["line_items"].to_dict(orient="records"),
        "table_title": view["table_title"],
        "table_caption": view["table_caption"],
    }


def build_site_payload(*, progress: bool = False) -> dict:
    departments_by_fund = {fund: departments_for(fund) for fund in FUND_OPTIONS}
    views: dict[str, dict] = {}
    total = sum(len(depts) for depts in departments_by_fund.values())
    done = 0
    for fund in FUND_OPTIONS:
        for department in departments_by_fund[fund]:
            views[view_key(fund, department)] = serialize_view(build_view(fund, department))
            done += 1
            if progress and (done == total or done % 50 == 0):
                print(f"  … {done}/{total} views built")
    glance = build_glance_payload(APPROPRIATIONS, year=BUDGET_YEAR)
    log_glance_build(glance, verbose=progress)
    return {
        "budget_year": BUDGET_YEAR,
        "fund_options": FUND_OPTIONS,
        "departments_by_fund": departments_by_fund,
        "default_fund": CORPORATE,
        "default_department": ALL_DEPARTMENTS,
        "views": views,
        "plot_config": PLOT_CONFIG,
        "glance": glance,
    }
