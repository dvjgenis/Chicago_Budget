#!/usr/bin/env python3
"""Build the standalone dashboard.html from cached data in data/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import BUDGET_YEAR
from pipeline.dashboard_logic import build_site_payload, initialize_from_disk

SRC_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_ROOT.parent
OUTPUT_PATH = PROJECT_ROOT / "dashboard.html"

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chicago Budget __BUDGET_YEAR__</title>
  <meta name="description" content="Chicago's __BUDGET_YEAR__ budget: the official all-funds map, then the adopted ordinance — who gets what, what changed, and where the money comes from.">
  <meta name="theme-color" content="#41b6e6">
  <meta property="og:title" content="Chicago Budget __BUDGET_YEAR__">
  <meta property="og:description" content="Chicago's __BUDGET_YEAR__ budget: the official all-funds map, then the adopted ordinance.">
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%2341b6e6'/%3E%3Crect x='2' y='9' width='3' height='5' fill='%23082f5b'/%3E%3Crect x='6.5' y='5' width='3' height='9' fill='%23082f5b'/%3E%3Crect x='11' y='3' width='3' height='11' fill='%23e4002b'/%3E%3C/svg%3E">
  <link rel="stylesheet" href="src/app.css">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" defer></script>
  <script src="src/glance.js" defer></script>
  <script src="src/dashboard.js" defer></script>
</head>
<body data-page="glance" data-booting="true">
  <div class="boot" id="boot" role="status">
    <p class="boot-kicker">City of Chicago</p>
    <p class="boot-title" id="boot-title">Opening the __BUDGET_YEAR__ budget</p>
    <p class="boot-hint" id="boot-hint">The ordinance file is large. Hang on a moment.</p>
  </div>
  <div class="page">
    <nav class="float-bar">
      <div class="float-brand">
        <p class="kicker" id="mast-kicker">Chicago budget · __BUDGET_YEAR__</p>
        <p class="mast-aside" id="mast-aside">Official all-funds map</p>
      </div>
      <div class="nav-tools">
        <div class="page-switch" role="tablist" aria-label="Dashboard pages">
          <a href="#glance" data-page-link="glance" role="tab">At a glance</a>
          <a href="#explore" data-page-link="explore" role="tab">Ordinance</a>
        </div>
        <button type="button" class="jump-btn" id="jump-open">Jump to…</button>
      </div>
      <div class="controls" id="explore-controls">
        <div class="field">
          <label class="field-label" for="fund-select">Which fund?</label>
          <select id="fund-select" class="chooser"></select>
        </div>
        <div class="field">
          <label class="field-label" for="department-select">Whose budget?</label>
          <select id="department-select" class="chooser"></select>
        </div>
      </div>
    </nav>

    <div id="page-glance">
      <header class="masthead">
        <h1 id="glance-headline">Chicago budget</h1>
        <p class="lede" id="glance-lede">Three things to notice, then the river. Click a takeaway or a bar — the rest of the budget fades so one path is obvious.</p>
        <div class="flag-rule" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
      </header>

      <section class="insights" id="glance-insights" aria-label="Things to notice"></section>

      <section class="panel wide glance-panel">
        <div class="sankey-toolbar">
          <div>
            <p class="ui-caps">Allocation</p>
            <h2 class="section-title">Follow the money</h2>
            <p class="section-caption" id="glance-caption"></p>
          </div>
          <div class="chip-row" id="glance-filters" role="group" aria-label="Focus the map"></div>
        </div>
        <p class="takeaway" id="glance-takeaway">Click a takeaway or a bar. Esc clears the focus. 1 and 2 switch pages.</p>
        <button class="glance-reset" id="glance-reset" type="button" hidden>Show the full budget</button>
        <div class="sankey-frame" id="sankey"></div>
        <div class="mobile-list" id="glance-mobile"></div>
        <div class="tooltip" id="glance-tooltip" role="tooltip"></div>
        <div class="glance-detail" id="glance-detail"></div>
      </section>

      <section class="panel wide glance-panel" id="glance-yoy-panel" hidden>
        <p class="ui-caps" id="glance-yoy-kicker">Year to year</p>
        <h2 class="section-title" id="glance-yoy-title">What grew, what shrank</h2>
        <p class="section-caption" id="glance-yoy-caption"></p>
        <div id="glance-yoy"></div>
      </section>
    </div>

    <div id="page-explore" hidden>
    <header class="masthead">
      <h1>Where does the money go?</h1>
      <p class="lede">Every year the mayor writes a budget. City Council votes on it. This page is that vote — who gets what, what changed, and where the money is supposed to come from.</p>
      <div class="flag-rule" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
    </header>

    <section class="how">
      <p class="ui-caps">How to read this</p>
      <ol class="steps">
        <li><strong>Which pile of money?</strong> Start with the Corporate Fund. That pays for police, fire, streets, and most city offices.</li>
        <li><strong>Whose budget?</strong> Leave it on all departments for the big picture, or pick one office to zoom in.</li>
        <li><strong>What changed?</strong> A white bar is what the mayor asked for. Blue is what Council passed. Red is a cut.</li>
      </ol>
    </section>

    <p class="scope" id="scope-line"></p>

    <section class="story-block">
      <p class="ui-caps">So what happened?</p>
      <p class="story" id="story"></p>
      <p class="story-context" id="scope-note"></p>
    </section>

    <section class="kpis">
      <article class="kpi hero">
        <p class="kpi-label">How much got passed?</p>
        <p class="hero-value" id="adopted-label"></p>
        <p class="kpi-hint">The ordinance — the number that became law</p>
      </article>
      <article class="kpi">
        <p class="kpi-label">What did the mayor ask for?</p>
        <p class="kpi-value" id="recommended-label"></p>
        <p class="kpi-hint">The first draft, before the vote</p>
      </article>
      <article class="kpi">
        <p class="kpi-label">Did Council add or cut?</p>
        <p class="kpi-value" id="delta-label"></p>
        <p class="kpi-hint" id="delta-hint"></p>
      </article>
      <article class="kpi">
        <p class="kpi-label">What's coming in?</p>
        <p class="kpi-value" id="revenue-label"></p>
        <p class="kpi-hint" id="revenue-hint"></p>
      </article>
    </section>

    <section class="split">
      <article class="panel">
        <p class="ui-caps">01</p>
        <h2 class="section-title" id="left-title"></h2>
        <p class="section-caption" id="left-caption"></p>
        <div class="chart-frame chart-frame-tall" id="left-chart"></div>
        <p class="callout hidden" id="finance-note"></p>
      </article>
      <article class="panel">
        <p class="ui-caps">02</p>
        <h2 class="section-title" id="purpose-title"></h2>
        <p class="section-caption" id="purpose-caption"></p>
        <div class="chart-frame chart-frame-tall" id="purpose-chart"></div>
      </article>
    </section>

    <section class="panel wide">
      <p class="ui-caps">03</p>
      <h2 class="section-title" id="change-title"></h2>
      <p class="section-caption" id="change-caption"></p>
      <div class="chart-frame chart-frame-medium" id="change-chart"></div>
    </section>

    <section class="panel wide">
      <p class="ui-caps">04</p>
      <h2 class="section-title" id="revenue-title"></h2>
      <p class="section-caption" id="revenue-caption"></p>
      <div class="chart-frame chart-frame-medium" id="revenue-chart"></div>
    </section>

    <section class="panel wide">
      <p class="ui-caps">05</p>
      <h2 class="section-title" id="table-title"></h2>
      <p class="section-caption" id="table-caption"></p>
      <div class="table-toolbar">
        <label class="field-label" for="table-filter">Filter lines</label>
        <input id="table-filter" class="table-filter" type="search" placeholder="Try overtime, homeless, salaries…" autocomplete="off">
      </div>
      <div class="table-shell">
        <table class="budget-table" id="line-table">
          <thead>
            <tr>
              <th>Fund</th>
              <th>Department</th>
              <th>Account</th>
              <th class="num">Mayor's rec.</th>
              <th class="num">Adopted</th>
              <th class="num">Change</th>
            </tr>
          </thead>
          <tbody id="line-table-body"></tbody>
        </table>
      </div>
      <p class="table-footnote" id="table-footnote"></p>
    </section>
    </div>

    <div class="jump" id="jump" hidden>
      <div class="jump-card" role="dialog" aria-modal="true" aria-labelledby="jump-title">
        <p class="ui-caps" id="jump-title">Jump to a department</p>
        <input id="jump-input" class="table-filter" type="search" placeholder="Police, library, housing…" autocomplete="off">
        <ul class="jump-list" id="jump-list"></ul>
        <p class="note">Type a name. Enter opens the first match on the ordinance page.</p>
      </div>
    </div>

    <footer class="colophon">
      <p class="ui-caps">A couple of things to keep in mind</p>
      <p id="colophon-text"></p>
      <p id="colophon-sources"></p>
      <p>Shortcuts: <kbd>1</kbd> glance · <kbd>2</kbd> ordinance · <kbd>J</kbd> jump · <kbd>Esc</kbd> clear.</p>
      <p class="build-note">Built __BUILD_STAMP__. To refresh data for a new year, run <code>python3 run.py --refresh</code> (see README.md).</p>
    </footer>
  </div>

  <noscript>
    <p style="max-width:40rem;margin:2rem auto;padding:1rem 1.25rem;border-radius:1rem;background:#fff3cd;color:#1c1917;">
      This dashboard needs JavaScript for filters and charts. Please enable JavaScript in your browser.
    </p>
  </noscript>

  <script id="budget-data" type="application/json">__BUDGET_DATA__</script>
</body>
</html>
"""


def build_dashboard(*, verbose: bool = True) -> Path:
    if verbose:
        print("Loading cached budget data…")
    initialize_from_disk()
    if verbose:
        print("Building views…")
    payload = build_site_payload(progress=verbose)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = (
        DASHBOARD_HTML.replace("__BUDGET_YEAR__", str(BUDGET_YEAR))
        .replace("__BUILD_STAMP__", stamp)
        .replace("__BUDGET_DATA__", json.dumps(payload, separators=(",", ":")))
    )
    if verbose:
        print("Writing dashboard.html…")
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    out = build_dashboard(verbose=True)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"Done — {out.name} ({size_mb:.1f} MB)")
