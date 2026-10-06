"""Run the reproducible local ETL, advanced analytics, and final export workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_pipeline(profile_sources: bool = True) -> None:
    """Run local pipeline stages without making network requests."""
    from data_ingestion import inspect_csv_directory
    from day2_etl import run as run_etl
    from analytics.advanced_analytics import run_all
    from dashboard.build_dashboard import main as build_dashboard_exports
    from build_final_deliverables import build as build_final_documents

    steps: list[tuple[str, Callable[[], object]]] = []
    if profile_sources:
        steps.append(("Source profiling and AMFI-code validation", lambda: inspect_csv_directory(ROOT / "data" / "raw")))
    steps.extend(
        [
            ("Cleaning and SQLite load", run_etl),
            ("Advanced risk and investor analytics", run_all),
            ("Static dashboard exports", build_dashboard_exports),
            ("Final PDF and presentation", build_final_documents),
        ]
    )
    for index, (label, action) in enumerate(steps, start=1):
        print(f"\n[{index}/{len(steps)}] {label}")
        action()
    print("\nLocal pipeline completed successfully.")


def main() -> None:
    """Parse pipeline options and run the requested local stages."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip the verbose per-CSV profiling step; ETL validation still runs.",
    )
    args = parser.parse_args()
    run_pipeline(profile_sources=not args.skip_profile)


if __name__ == "__main__":
    main()
