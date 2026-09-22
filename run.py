#!/usr/bin/env python3
"""Build dashboard.html and optionally refresh data from the Chicago Data Portal."""

from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DASHBOARD = ROOT / "dashboard.html"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def install_requirements() -> None:
    requirements = SRC / "requirements.txt"
    if requirements.exists():
        print("Checking Python packages…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements), "-q"])


def refresh_from_api() -> None:
    from pipeline.fetch_data import refresh_datasets

    print("Downloading latest data from the Chicago Data Portal…")
    appro, rev = refresh_datasets()
    print(f"Saved {len(appro):,} appropriation rows and {len(rev):,} revenue rows to src/data/")


def build() -> Path:
    from build_dashboard import build_dashboard

    return build_dashboard(verbose=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and open the Chicago Budget dashboard.",
        epilog="Tip: double-click dashboard.html anytime — no Python needed after it is built.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download fresh data from the API before building (requires .env).",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Download fresh data only; do not rebuild dashboard.html.",
    )
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser after building.")
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.")
        return 1

    install_requirements()

    env_file = ROOT / ".env"
    needs_fetch = args.refresh or args.fetch_only

    if needs_fetch:
        if not env_file.exists():
            print("Cannot refresh: copy .env.example to .env and add your credentials.")
            print("See README.md or START_HERE.html for setup.")
            return 1
        try:
            refresh_from_api()
        except Exception as exc:
            print(f"Refresh failed: {exc}")
            return 1
    elif not env_file.exists() and not DASHBOARD.exists():
        print("No .env file and no dashboard.html yet.")
        print("Either copy .env.example → .env and run with --refresh,")
        print("or ask for a pre-built dashboard.html in the project folder.\n")

    if args.fetch_only:
        print("Fetch complete. Rebuild with: python3 run.py --no-open")
        return 0

    if not any((SRC / "data").glob("budget_*.csv")):
        print("No cached budget files in src/data/.")
        print("Create .env and run: python3 run.py --refresh")
        return 1

    path = build()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Wrote {path.name} ({size_mb:.1f} MB)")

    if not args.no_open:
        uri = path.resolve().as_uri()
        print(f"Opening {uri}")
        webbrowser.open(uri)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
