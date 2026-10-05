"""Inspect the supplied mutual-fund CSV files and run basic data-quality checks."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
FUND_MASTER_NAME = "fund_master"
NAV_HISTORY_NAME = "nav_history"

ATTRIBUTE_ALIASES = {
    "fund houses": ("fundhouse", "fundhousename", "amc", "amcname"),
    "categories": ("category", "fundcategory", "schemecategory"),
    "sub-categories": ("subcategory", "fundsubcategory", "schemesubcategory"),
    "risk grades": ("riskgrade", "riskrating", "riskcategory", "risk"),
}
SCHEME_CODE_ALIASES = ("scheme_code", "amfi_code", "amficode", "code")


def normalized_column_name(column: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(column).casefold())


def find_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> Any | None:
    normalized_aliases = {normalized_column_name(alias) for alias in aliases}
    return next(
        (column for column in frame.columns if normalized_column_name(column) in normalized_aliases),
        None,
    )


def normalized_codes(values: pd.Series) -> set[str]:
    codes: set[str] = set()
    for value in values.dropna():
        code = str(value).strip()
        if not code:
            continue
        if re.fullmatch(r"\d+\.0+", code):
            code = code[: code.index(".")]
        codes.add(code)
    return codes


def dataset_key(stem: str) -> str:
    return re.sub(r"^\d+[_-]*", "", stem.casefold())


def data_quality_anomalies(frame: pd.DataFrame) -> list[str]:
    anomalies: list[str] = []
    missing_cells = int(frame.isna().sum().sum())
    if missing_cells:
        anomalies.append(f"{missing_cells} missing cell(s)")
    duplicate_rows = int(frame.duplicated().sum())
    if duplicate_rows:
        anomalies.append(f"{duplicate_rows} duplicate row(s)")
    duplicate_columns = frame.columns[frame.columns.duplicated()].tolist()
    if duplicate_columns:
        anomalies.append(f"duplicate column name(s): {duplicate_columns}")
    if frame.empty:
        anomalies.append("no data rows")
    return anomalies


def print_fund_master_attributes(frame: pd.DataFrame) -> None:
    print("\nFund master dimensions:", frame.shape)
    for label, aliases in ATTRIBUTE_ALIASES.items():
        column = find_column(frame, aliases)
        if column is None:
            print(f"{label}: column not found (checked aliases: {', '.join(aliases)})")
            continue
        values = sorted(frame[column].dropna().astype(str).unique().tolist())
        print(f"{label} ({column}, {len(values)} unique): {values}")


def print_scheme_code_observations(codes: set[str]) -> None:
    lengths = Counter(map(len, codes))
    numeric_codes = [int(code) for code in codes if code.isdigit()]
    print("\nAMFI scheme-code observations:")
    print(f"Unique non-empty codes: {len(codes)}")
    if numeric_codes:
        print(f"Numeric code range: {min(numeric_codes)}–{max(numeric_codes)}")
    print(f"Code lengths: {dict(sorted(lengths.items()))}")
    print(
        "Interpretation: treat each scheme code as a lookup identifier; "
        "the observed prefixes/lengths are descriptive, not decoded fields."
    )


def validate_scheme_codes(
    fund_master: pd.DataFrame | None, nav_history: pd.DataFrame | None
) -> None:
    print("\nAMFI code validation (fund_master against nav_history):")
    if fund_master is None or nav_history is None:
        print("Not run: both fund_master and nav_history CSVs are required.")
        return

    fund_code_column = find_column(fund_master, SCHEME_CODE_ALIASES)
    nav_code_column = find_column(nav_history, SCHEME_CODE_ALIASES)
    if fund_code_column is None or nav_code_column is None:
        print(
            "Not run: scheme-code column not found in both files "
            f"(fund_master={fund_code_column!r}, nav_history={nav_code_column!r})."
        )
        return

    fund_codes = normalized_codes(fund_master[fund_code_column])
    nav_codes = normalized_codes(nav_history[nav_code_column])
    absent_codes = sorted(fund_codes - nav_codes)
    extra_nav_codes = sorted(nav_codes - fund_codes)
    print(f"fund_master unique codes: {len(fund_codes)}")
    print(f"nav_history unique codes: {len(nav_codes)}")
    print(f"fund_master codes absent from nav_history: {len(absent_codes)}")
    if absent_codes:
        print("Absent codes:", absent_codes)
    else:
        print("All fund_master codes are present in nav_history.")
    if extra_nav_codes:
        print(f"nav_history-only codes: {len(extra_nav_codes)}")
        print("Example nav_history-only codes:", extra_nav_codes[:20])


def inspect_csv_directory(raw_dir: Path) -> None:
    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(
            f"No CSV datasets found in {raw_dir}. Place the supplied CSV files there "
            "and rerun data_ingestion.py."
        )

    print(f"Found {len(csv_paths)} CSV file(s) in {raw_dir}")
    loaded: dict[str, pd.DataFrame] = {}
    anomaly_count = 0
    for csv_path in csv_paths:
        frame = pd.read_csv(csv_path)
        loaded[dataset_key(csv_path.stem)] = frame

        print(f"\n{'=' * 80}\n{csv_path.name}")
        print("Shape:", frame.shape)
        print("Dtypes:\n", frame.dtypes.to_string())
        print("Head:\n", frame.head().to_string(index=False))
        anomalies = data_quality_anomalies(frame)
        if anomalies:
            anomaly_count += len(anomalies)
            print("Anomalies:", "; ".join(anomalies))
        else:
            print("Anomalies: none detected by basic checks")

    fund_master = loaded.get(FUND_MASTER_NAME)
    nav_history = loaded.get(NAV_HISTORY_NAME)
    if fund_master is not None:
        print_fund_master_attributes(fund_master)

    if fund_master is not None:
        code_column = find_column(fund_master, SCHEME_CODE_ALIASES)
        if code_column is not None:
            print_scheme_code_observations(normalized_codes(fund_master[code_column]))
        else:
            print("\nAMFI scheme-code observations: no scheme-code column found in fund_master.")

    validate_scheme_codes(fund_master, nav_history)
    print("\nData quality summary:")
    print(f"CSV files inspected: {len(csv_paths)}")
    print(f"Basic anomaly flags: {anomaly_count}")
    if fund_master is None or nav_history is None:
        print("AMFI cross-file code validation: incomplete; required file(s) were not found.")
    else:
        print("AMFI cross-file code validation: see comparison above.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"Directory containing the supplied CSV files (default: {DEFAULT_RAW_DIR})",
    )
    args = parser.parse_args()
    inspect_csv_directory(args.raw_dir)


if __name__ == "__main__":
    main()
