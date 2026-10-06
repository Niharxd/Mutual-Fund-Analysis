"""Clean the Day 1 CSVs, load source tables and a SQLite star schema."""

from __future__ import annotations

import argparse
import re
import sqlite3
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, event, text


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DATABASE_PATH = ROOT / "bluestock_mf.db"
SCHEMA_PATH = ROOT / "schema.sql"

DATE_COLUMNS = ("date", "transaction_date", "portfolio_date", "launch_date")
PERFORMANCE_NUMERIC_COLUMNS = (
    "return_1yr_pct",
    "return_3yr_pct",
    "return_5yr_pct",
    "benchmark_3yr_pct",
    "alpha",
    "beta",
    "sharpe_ratio",
    "sortino_ratio",
    "std_dev_ann_pct",
    "max_drawdown_pct",
    "aum_crore",
    "expense_ratio_pct",
    "morningstar_rating",
)
TRANSACTION_TYPES = {
    "sip": "SIP",
    "systematicinvestmentplan": "SIP",
    "lumpsum": "Lumpsum",
    "lump sum": "Lumpsum",
    "onetime": "Lumpsum",
    "onetimeinvestment": "Lumpsum",
    "redemption": "Redemption",
    "redeem": "Redemption",
}
KYC_STATUSES = {
    "verified": "Verified",
    "approved": "Verified",
    "pending": "Pending",
}
DATE_KEY = "date_key"
FUND_KEY = "amfi_code"


def parse_date_column(values: pd.Series, column_name: str) -> pd.Series:
    """Parse a date series and raise with examples if any non-null value is invalid."""
    parsed = pd.to_datetime(values, format="mixed", errors="coerce")
    invalid = values.notna() & parsed.isna()
    if invalid.any():
        examples = values.loc[invalid].astype(str).unique()[:10].tolist()
        raise ValueError(f"Unparseable {column_name} values: {examples}")
    return parsed


def normalize_token(value: Any) -> str:
    """Normalize text for matching transaction and KYC categories."""
    return re.sub(r"[^a-z0-9 ]", "", str(value).strip().casefold())


def clean_nav(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate NAV rows, deduplicate keys, and forward-fill daily calendar gaps."""
    # MFAPI's live_nav_fetch.py uses ``scheme_code``; the Day 1 dataset uses
    # ``amfi_code``. Normalize the live-fetcher name before validation.
    if "amfi_code" not in frame.columns and "scheme_code" in frame.columns:
        frame = frame.rename(columns={"scheme_code": "amfi_code"})
    required = {"amfi_code", "date", "nav"}
    if not required.issubset(frame.columns):
        raise ValueError(f"nav_history is missing columns: {sorted(required - set(frame.columns))}")

    result = frame.copy()
    result["date"] = parse_date_column(result["date"], "nav_history.date")
    result["nav"] = pd.to_numeric(result["nav"], errors="coerce")
    result = result.dropna(subset=["amfi_code", "date", "nav"])
    duplicate_count = int(result.duplicated(["amfi_code", "date"], keep="last").sum())
    result = result.drop_duplicates(["amfi_code", "date"], keep="last")
    invalid_nav_count = int((result["nav"] <= 0).sum())
    result = result.loc[result["nav"] > 0].copy()
    if result.empty:
        raise ValueError("nav_history contains no rows with a positive NAV and valid date.")

    complete_frames: list[pd.DataFrame] = []
    fill_count = 0
    for amfi_code, group in result.groupby("amfi_code", sort=False):
        group = group.sort_values("date").set_index("date")
        calendar = pd.date_range(group.index.min(), group.index.max(), freq="D")
        daily = group.reindex(calendar)
        daily["amfi_code"] = amfi_code
        missing_nav = int(daily["nav"].isna().sum())
        daily["nav"] = daily["nav"].ffill()
        fill_count += missing_nav
        daily.index.name = "date"
        complete_frames.append(daily.reset_index())

    result = pd.concat(complete_frames, ignore_index=True)
    result = result.sort_values(["amfi_code", "date"], kind="stable").reset_index(drop=True)
    if result["nav"].isna().any() or not result["nav"].gt(0).all():
        raise ValueError("NAV calendar completion left missing or non-positive NAV values.")
    print(
        f"nav_history: removed {duplicate_count} duplicate code/date row(s), "
        f"removed {invalid_nav_count} non-positive NAV row(s), "
        f"forward-filled {fill_count} missing calendar-day NAV value(s)."
    )
    return result


def clean_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize transaction fields and discard invalid or non-positive amounts."""
    required = {"transaction_date", "transaction_type", "amount_inr", "kyc_status", "amfi_code"}
    if not required.issubset(frame.columns):
        raise ValueError(
            f"investor_transactions is missing columns: {sorted(required - set(frame.columns))}"
        )

    result = frame.copy()
    result["transaction_date"] = parse_date_column(
        result["transaction_date"], "investor_transactions.transaction_date"
    )
    type_tokens = result["transaction_type"].map(normalize_token)
    mapped_types = type_tokens.map(TRANSACTION_TYPES)
    if mapped_types.isna().any():
        unknown = sorted(result.loc[mapped_types.isna(), "transaction_type"].astype(str).unique())
        raise ValueError(f"Unknown transaction_type value(s): {unknown}")
    result["transaction_type"] = mapped_types

    kyc_tokens = result["kyc_status"].map(normalize_token)
    mapped_kyc = kyc_tokens.map(KYC_STATUSES)
    if mapped_kyc.isna().any():
        unknown = sorted(result.loc[mapped_kyc.isna(), "kyc_status"].astype(str).unique())
        raise ValueError(f"Unknown KYC status value(s): {unknown}")
    result["kyc_status"] = mapped_kyc

    result["amount_inr"] = pd.to_numeric(result["amount_inr"], errors="coerce")
    invalid_amount_count = int(result["amount_inr"].isna().sum() + result["amount_inr"].le(0).sum())
    result = result.loc[result["amount_inr"].gt(0)].copy()
    result["amount_inr"] = result["amount_inr"].astype("int64")
    if result["transaction_date"].isna().any():
        raise ValueError("Transactions contain rows without a parseable transaction date.")
    print(
        f"investor_transactions: removed {invalid_amount_count} row(s) with "
        "missing, non-numeric, or non-positive amount."
    )
    return result.reset_index(drop=True)


def clean_performance(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate numeric performance fields and flag suspicious metric values."""
    required = set(PERFORMANCE_NUMERIC_COLUMNS)
    if not required.issubset(frame.columns):
        raise ValueError(f"scheme_performance is missing numeric columns: {sorted(required - set(frame.columns))}")

    result = frame.copy()
    numeric_errors: dict[str, list[str]] = {}
    for column in PERFORMANCE_NUMERIC_COLUMNS:
        converted = pd.to_numeric(result[column], errors="coerce")
        invalid = result[column].notna() & converted.isna()
        if invalid.any():
            numeric_errors[column] = result.loc[invalid, column].astype(str).unique()[:10].tolist()
        result[column] = converted
    if numeric_errors:
        raise ValueError(f"Non-numeric scheme_performance values: {numeric_errors}")
    if result[list(PERFORMANCE_NUMERIC_COLUMNS)].isna().any().any():
        raise ValueError("scheme_performance contains missing numeric metric values.")

    expense_invalid = ~result["expense_ratio_pct"].between(0.1, 2.5, inclusive="both")
    if expense_invalid.any():
        warnings.warn(
            f"{int(expense_invalid.sum())} expense ratio value(s) fall outside 0.1%-2.5%.",
            stacklevel=2,
        )

    flags: list[str] = []
    for row in result.itertuples(index=False):
        row_flags: list[str] = []
        if row.sharpe_ratio > 3:
            row_flags.append("sharpe_ratio_above_3")
        if row.sortino_ratio > 3:
            row_flags.append("sortino_ratio_above_3")
        if not 0.1 <= row.expense_ratio_pct <= 2.5:
            row_flags.append("expense_ratio_out_of_range")
        flags.append("|".join(row_flags))
    result["anomaly_flags"] = flags
    flagged_count = sum(bool(value) for value in flags)
    print(
        f"scheme_performance: validated {len(PERFORMANCE_NUMERIC_COLUMNS)} numeric columns; "
        f"expense ratios range from {result.expense_ratio_pct.min():.2f}% to "
        f"{result.expense_ratio_pct.max():.2f}%; flagged {flagged_count} row(s)."
    )
    return result


def clean_dataset(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Apply dataset-specific cleaning and date normalization."""
    if name == "nav_history":
        return clean_nav(frame)
    if name == "investor_transactions":
        return clean_transactions(frame)
    if name == "scheme_performance":
        return clean_performance(frame)

    result = frame.copy()
    for column in DATE_COLUMNS:
        if column in result.columns:
            result[column] = parse_date_column(result[column], f"{name}.{column}")
    if "month" in result.columns:
        parsed_month = pd.to_datetime(result["month"], format="%Y-%m", errors="coerce")
        if (result["month"].notna() & parsed_month.isna()).any():
            raise ValueError(f"{name}.month contains invalid YYYY-MM values.")
        result["month"] = parsed_month.dt.strftime("%Y-%m")
    return result


def load_cleaned_datasets(raw_dir: Path, processed_dir: Path) -> dict[str, pd.DataFrame]:
    """Clean the expected ten source CSVs and write processed counterparts."""
    source_paths = sorted(path for path in raw_dir.glob("*.csv") if path.name != ".gitkeep")
    if len(source_paths) != 10:
        raise ValueError(f"Expected the 10 Day 1 CSV files in {raw_dir}; found {len(source_paths)}.")
    processed_dir.mkdir(parents=True, exist_ok=True)
    cleaned: dict[str, pd.DataFrame] = {}
    for source_path in source_paths:
        name = re.sub(r"^\d+[_-]*", "", source_path.stem)
        frame = pd.read_csv(source_path)
        result = clean_dataset(name, frame)
        target_path = processed_dir / source_path.name
        result.to_csv(target_path, index=False, date_format="%Y-%m-%d")
        cleaned[name] = result
        print(f"{source_path.name}: {len(frame):,} source row(s) -> {len(result):,} cleaned row(s)")
    if set(cleaned) != {
        "fund_master",
        "nav_history",
        "aum_by_fund_house",
        "monthly_sip_inflows",
        "category_inflows",
        "industry_folio_count",
        "scheme_performance",
        "investor_transactions",
        "portfolio_holdings",
        "benchmark_indices",
    }:
        raise ValueError(f"Unexpected source dataset names: {sorted(cleaned)}")
    return cleaned


def date_key(values: pd.Series) -> pd.Series:
    """Convert dates to integer YYYYMMDD keys for relational fact tables."""
    parsed = pd.to_datetime(values, errors="raise")
    return parsed.dt.strftime("%Y%m%d").astype("int64")


def build_star_tables(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build date/fund dimensions and fact tables from cleaned source frames."""
    date_values: list[pd.Series] = []
    for frame in data.values():
        for column in (*DATE_COLUMNS, "month"):
            if column not in frame:
                continue
            values = pd.to_datetime(frame[column], errors="coerce")
            date_values.append(values.dropna())
    all_dates = pd.concat(date_values, ignore_index=True)
    if all_dates.empty:
        raise ValueError("No source dates available to construct dim_date.")
    calendar = pd.date_range(all_dates.min().normalize(), all_dates.max().normalize(), freq="D")
    calendar_series = pd.Series(calendar)
    dim_date = pd.DataFrame({"full_date": calendar_series.dt.strftime("%Y-%m-%d")})
    dim_date[DATE_KEY] = calendar_series.dt.strftime("%Y%m%d").astype("int64")
    dim_date["year"] = calendar_series.dt.year
    dim_date["quarter"] = calendar_series.dt.quarter
    dim_date["month"] = calendar_series.dt.month
    dim_date["month_name"] = calendar_series.dt.month_name()
    dim_date["day"] = calendar_series.dt.day
    dim_date["day_of_week"] = calendar_series.dt.day_name()
    dim_date["is_weekend"] = (calendar_series.dt.dayofweek >= 5).astype("int64")
    fund_columns = list(data["fund_master"].columns)
    dim_fund = data["fund_master"].loc[:, fund_columns].drop_duplicates("amfi_code").copy()

    nav = data["nav_history"].copy()
    nav[DATE_KEY] = date_key(nav["date"])
    fact_nav = nav[["amfi_code", DATE_KEY, "nav"]]

    transactions = data["investor_transactions"].copy()
    transactions.insert(0, "transaction_id", range(1, len(transactions) + 1))
    transactions[DATE_KEY] = date_key(transactions["transaction_date"])
    fact_transactions = transactions.drop(columns=["transaction_date"])

    performance = data["scheme_performance"].copy()
    descriptive = {"scheme_name", "fund_house", "category", "plan", "risk_grade"}
    fact_performance = performance.drop(columns=list(descriptive & set(performance.columns)))

    aum = data["aum_by_fund_house"].copy()
    aum[DATE_KEY] = date_key(aum["date"])
    fact_aum = aum.drop(columns=["date"])

    return {
        "dim_fund": dim_fund,
        "dim_date": dim_date,
        "fact_nav": fact_nav,
        "fact_transactions": fact_transactions,
        "fact_performance": fact_performance,
        "fact_aum": fact_aum,
    }


def reset_schema(connection: Any) -> None:
    """Execute the project's SQL schema statements on an open connection."""
    statements = [part.strip() for part in SCHEMA_PATH.read_text(encoding="utf-8").split(";")]
    for statement in statements:
        if statement:
            connection.exec_driver_sql(statement)


def load_database(data: dict[str, pd.DataFrame], database_path: Path) -> None:
    """Load source and star-schema tables, then validate counts and foreign keys."""
    star = build_star_tables(data)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: sqlite3.Connection, _: Any) -> None:
        """Enable SQLite foreign-key checks for every newly opened connection."""
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    source_tables = {f"src_{name}": frame for name, frame in data.items()}
    with engine.begin() as connection:
        reset_schema(connection)
        for table_name, frame in source_tables.items():
            frame.to_sql(table_name, connection, if_exists="replace", index=False)
        for table_name in ("dim_fund", "dim_date", "fact_nav", "fact_transactions", "fact_performance", "fact_aum"):
            star[table_name].to_sql(table_name, connection, if_exists="append", index=False)

        expected_counts = {
            **{name: len(frame) for name, frame in source_tables.items()},
            **{name: len(frame) for name, frame in star.items()},
        }
        actual_counts = {
            name: int(connection.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one())
            for name in expected_counts
        }
        mismatches = {
            name: (expected_counts[name], actual_counts[name])
            for name in expected_counts
            if expected_counts[name] != actual_counts[name]
        }
        foreign_key_errors = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if mismatches or foreign_key_errors:
            raise RuntimeError(
                f"Database load validation failed; row count mismatches={mismatches}, "
                f"foreign key errors={foreign_key_errors[:10]}"
            )
        print("SQLite row-count verification (expected == actual):")
        for name, expected in expected_counts.items():
            print(f"  {name}: {expected:,}")
    engine.dispose()
    print(f"Database created and verified: {database_path}")


def run(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR, database_path: Path = DATABASE_PATH) -> None:
    """Run cleaning, processed-file exports, and the SQLite database load."""
    data = load_cleaned_datasets(raw_dir, processed_dir)
    load_database(data, database_path)


def main() -> None:
    """Parse ETL paths from the command line and run the local pipeline stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    args = parser.parse_args()
    run(args.raw_dir, args.processed_dir, args.database)


if __name__ == "__main__":
    main()
