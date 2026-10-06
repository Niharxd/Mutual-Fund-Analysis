"""Advanced risk, investor-cohort, SIP-continuity, and concentration analytics."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
ANNUAL_RISK_FREE_RATE = 0.065
TRADING_DAYS_PER_YEAR = 252
VAR_CONFIDENCE = 0.95
MIN_SIP_TRANSACTIONS = 6
AT_RISK_GAP_DAYS = 35
KEY_FUND_CODES = {
    "119551": "SBI Bluechip",
    "120503": "ICICI Bluechip",
    "118632": "Nippon Large Cap",
    "119092": "Axis Bluechip",
    "120841": "Kotak Bluechip",
}
RISK_GRADES = {
    "Low": ("Low",),
    "Moderate": ("Moderate",),
    "High": ("Moderately High", "High", "Very High"),
}


def read_sources() -> dict[str, pd.DataFrame]:
    """Read source data; use unfilled raw NAV observations for return analytics."""
    nav_path = RAW / "02_nav_history.csv"
    if not nav_path.exists():
        raise FileNotFoundError(f"Original observed NAV source is required: {nav_path}")
    return {
        "nav": pd.read_csv(nav_path, parse_dates=["date"], dtype={"amfi_code": str}),
        "funds": pd.read_csv(PROCESSED / "01_fund_master.csv", dtype={"amfi_code": str}),
        "performance": pd.read_csv(PROCESSED / "07_scheme_performance.csv", dtype={"amfi_code": str}),
        "transactions": pd.read_csv(
            PROCESSED / "08_investor_transactions.csv",
            parse_dates=["transaction_date"],
            dtype={"amfi_code": str},
        ),
        "holdings": pd.read_csv(PROCESSED / "09_portfolio_holdings.csv", dtype={"amfi_code": str}),
    }


def daily_returns(nav: pd.DataFrame) -> pd.DataFrame:
    """Calculate observed-NAV percentage returns without forward-filled dates."""
    ordered = nav.sort_values(["amfi_code", "date"]).copy()
    ordered["daily_return"] = ordered.groupby("amfi_code", sort=False)["nav"].pct_change()
    returns = ordered.dropna(subset=["daily_return"])
    if (returns["nav"] <= 0).any():
        raise ValueError("NAV values must be positive to calculate percentage returns.")
    return returns


def calculate_var_cvar(returns: pd.DataFrame) -> pd.DataFrame:
    """Calculate empirical daily VaR and lower-tail CVaR for each scheme."""
    threshold = 1.0 - VAR_CONFIDENCE
    rows: list[dict[str, object]] = []
    for code, group in returns.groupby("amfi_code", sort=True):
        values = group["daily_return"].dropna()
        var = float(values.quantile(threshold))
        tail = values.loc[values.le(var)]
        rows.append(
            {
                "amfi_code": code,
                "var_confidence_pct": VAR_CONFIDENCE * 100,
                "var_95_daily_return_pct": var * 100,
                "cvar_95_daily_return_pct": float(tail.mean()) * 100,
                "observations": len(values),
                "tail_observations": len(tail),
                "start_date": group["date"].min().date().isoformat(),
                "end_date": group["date"].max().date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def calculate_rolling_sharpe(
    returns: pd.DataFrame,
    fund_codes: dict[str, str] = KEY_FUND_CODES,
    window: int = 90,
) -> pd.DataFrame:
    """Calculate the requested rolling Sharpe proxy for selected funds."""
    selected = returns.loc[returns["amfi_code"].isin(fund_codes)].copy()
    output: list[pd.DataFrame] = []
    for code, group in selected.groupby("amfi_code", sort=False):
        group = group.sort_values("date").copy()
        rolling_mean = group["daily_return"].rolling(window, min_periods=window).mean()
        rolling_std = group["daily_return"].rolling(window, min_periods=window).std()
        group["rolling_sharpe_90d"] = (
            rolling_mean.div(rolling_std.where(rolling_std.ne(0))) * TRADING_DAYS_PER_YEAR**0.5
        )
        group["fund_label"] = fund_codes[code]
        output.append(group)
    if not output:
        raise ValueError("None of the requested key fund codes were found in observed NAV data.")
    return pd.concat(output, ignore_index=True)


def plot_rolling_sharpe(rolling: pd.DataFrame, destination: Path) -> Path:
    """Write a styled rolling-Sharpe time-series plot."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 7))
    palette = ["#2855A6", "#17A398", "#E59A32", "#7A63B5", "#D45D5D"]
    for color, (label, group) in zip(palette, rolling.groupby("fund_label", sort=False)):
        ax.plot(group["date"], group["rolling_sharpe_90d"], label=label, color=color, linewidth=1.6)
    ax.axhline(0, color="#667085", linewidth=0.8, alpha=0.7)
    ax.set_title("90-day rolling Sharpe ratio · five large-cap schemes", loc="left", fontsize=16, weight="bold")
    ax.set_ylabel("Rolling Sharpe (annualised)")
    ax.set_xlabel("")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(destination, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return destination


def investor_cohorts(transactions: pd.DataFrame, funds: pd.DataFrame) -> pd.DataFrame:
    """Summarize investors by first transaction year and SIP-fund preference."""
    tx = transactions.copy()
    tx["transaction_type"] = tx["transaction_type"].str.strip().str.casefold()
    first_year = tx.groupby("investor_id")["transaction_date"].min().dt.year.rename("cohort_year")
    tx = tx.join(first_year, on="investor_id")
    investment_tx = tx.loc[tx["transaction_type"].isin(["sip", "lumpsum"])]
    investors_by_cohort = tx[["investor_id", "cohort_year"]].drop_duplicates()

    totals = investment_tx.groupby("cohort_year").agg(
        total_invested_inr=("amount_inr", "sum"),
        investment_transactions=("amount_inr", "size"),
    )
    sip_tx = tx.loc[tx["transaction_type"].eq("sip")]
    avg_sip = sip_tx.groupby("cohort_year")["amount_inr"].mean().rename("avg_sip_amount_inr")
    cohort_size = investors_by_cohort.groupby("cohort_year")["investor_id"].nunique().rename("investor_count")

    preference = sip_tx.groupby(["cohort_year", "amfi_code"]).size().rename("sip_transaction_count").reset_index()
    preference = preference.merge(
        funds[["amfi_code", "scheme_name"]].drop_duplicates("amfi_code"),
        on="amfi_code",
        how="left",
    )
    preference = preference.sort_values(
        ["cohort_year", "sip_transaction_count", "scheme_name", "amfi_code"],
        ascending=[True, False, True, True],
    ).drop_duplicates("cohort_year")
    preference = preference.set_index("cohort_year")[["scheme_name", "amfi_code", "sip_transaction_count"]]

    cohort = pd.concat([cohort_size, avg_sip, totals], axis=1).join(preference, how="left").reset_index()
    return cohort.sort_values("cohort_year").rename(columns={"scheme_name": "top_sip_fund"})


def sip_continuity(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure investor SIP gaps; at-risk means mean inter-SIP gap exceeds 35 days."""
    sip = transactions.loc[
        transactions["transaction_type"].str.strip().str.casefold().eq("sip"),
        ["investor_id", "transaction_date"],
    ].copy()
    sip = sip.sort_values(["investor_id", "transaction_date"])
    counts = sip.groupby("investor_id").size()
    eligible_ids = counts.loc[counts.ge(MIN_SIP_TRANSACTIONS)].index
    eligible = sip.loc[sip["investor_id"].isin(eligible_ids)].copy()
    eligible["gap_days"] = eligible.groupby("investor_id")["transaction_date"].diff().dt.days
    profile = eligible.groupby("investor_id").agg(
        sip_transaction_count=("transaction_date", "size"),
        first_sip_date=("transaction_date", "min"),
        last_sip_date=("transaction_date", "max"),
        avg_gap_days=("gap_days", "mean"),
        max_gap_days=("gap_days", "max"),
    )
    profile["continuity_status"] = profile["avg_gap_days"].gt(AT_RISK_GAP_DAYS).map(
        {True: "At-risk", False: "Continuing"}
    )
    profile = profile.reset_index().sort_values(["continuity_status", "avg_gap_days"], ascending=[True, False])
    summary = pd.DataFrame(
        [
            {
                "eligible_investors_6plus_sips": len(profile),
                "at_risk_investors_avg_gap_over_35d": int(profile["continuity_status"].eq("At-risk").sum()),
                "continuing_investors": int(profile["continuity_status"].eq("Continuing").sum()),
                "continuity_rate_pct": (
                    100 * profile["continuity_status"].eq("Continuing").mean() if not profile.empty else float("nan")
                ),
                "at_risk_rule": "mean interval between consecutive SIP transactions > 35 days",
            }
        ]
    )
    return profile, summary


def sector_hhi(holdings: pd.DataFrame, funds: pd.DataFrame) -> pd.DataFrame:
    """Compute sector-weight HHI across every equity scheme in the fund master."""
    equity_codes = funds.loc[funds["category"].str.casefold().eq("equity"), "amfi_code"].drop_duplicates()
    equity_funds = funds.loc[funds["amfi_code"].isin(equity_codes), ["amfi_code", "scheme_name", "fund_house", "category"]]
    equity_holdings = holdings.loc[holdings["amfi_code"].isin(equity_codes)].copy()
    equity_holdings["weight_pct"] = pd.to_numeric(equity_holdings["weight_pct"], errors="coerce")
    valid_holdings = equity_holdings.dropna(subset=["weight_pct", "sector"])
    sector_weights = valid_holdings.groupby(["amfi_code", "sector"], as_index=False).agg(
        sector_weight_pct=("weight_pct", "sum")
    )
    scores = sector_weights.groupby("amfi_code").agg(
        hhi=("sector_weight_pct", lambda weights: float(weights.pow(2).sum())),
        sector_count=("sector", "size"),
    )
    coverage = valid_holdings.groupby("amfi_code").agg(
        holdings_count=("weight_pct", "size"),
        disclosed_weight_pct=("weight_pct", "sum"),
    )
    scores = scores.join(coverage)
    result = equity_funds.merge(scores, on="amfi_code", how="left")
    result["holdings_count"] = result["holdings_count"].fillna(0).astype(int)
    result["sector_count"] = result["sector_count"].fillna(0).astype(int)
    result["coverage_status"] = result["hhi"].notna().map({True: "Holdings available", False: "No holdings rows"})
    return result.sort_values("hhi", ascending=False, na_position="last").reset_index(drop=True)


def sharpe_by_scheme(returns: pd.DataFrame, performance: pd.DataFrame) -> pd.DataFrame:
    """Annualized daily-return Sharpe using a 6.5% annual risk-free-rate proxy."""
    observations = returns.groupby("amfi_code")["daily_return"].agg(["mean", "std", "count"])
    observations["sharpe_ratio_daily"] = (
        observations["mean"].sub(ANNUAL_RISK_FREE_RATE / TRADING_DAYS_PER_YEAR)
        .div(observations["std"].where(observations["std"].ne(0)))
        * TRADING_DAYS_PER_YEAR**0.5
    )
    sharpe = observations.reset_index().rename(
        columns={"count": "return_observations", "std": "daily_return_std", "mean": "daily_return_mean"}
    )
    details = performance[["amfi_code", "scheme_name", "risk_grade"]].drop_duplicates("amfi_code")
    return sharpe.merge(details, on="amfi_code", how="left")


def recommend_funds(risk_appetite: str, sharpe: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    """Return up to three highest-Sharpe schemes for the selected risk appetite."""
    normalized = risk_appetite.strip().title()
    if normalized not in RISK_GRADES:
        allowed = ", ".join(RISK_GRADES)
        raise ValueError(f"Risk appetite must be one of: {allowed}.")
    recommended = sharpe.loc[sharpe["risk_grade"].isin(RISK_GRADES[normalized])].copy()
    return recommended.sort_values(
        ["sharpe_ratio_daily", "scheme_name"], ascending=[False, True], na_position="last"
    ).head(limit).reset_index(drop=True)


def run_all() -> dict[str, pd.DataFrame]:
    """Compute all advanced analytic outputs and export the requested artifacts."""
    sources = read_sources()
    returns = daily_returns(sources["nav"])
    var_report = calculate_var_cvar(returns).merge(
        sources["performance"][["amfi_code", "scheme_name", "risk_grade"]].drop_duplicates("amfi_code"),
        on="amfi_code",
        how="left",
    )
    var_report = var_report[
        [
            "amfi_code",
            "scheme_name",
            "risk_grade",
            "var_confidence_pct",
            "var_95_daily_return_pct",
            "cvar_95_daily_return_pct",
            "observations",
            "tail_observations",
            "start_date",
            "end_date",
        ]
    ].sort_values("var_95_daily_return_pct")
    rolling = calculate_rolling_sharpe(returns)
    cohorts = investor_cohorts(sources["transactions"], sources["funds"])
    continuity, continuity_summary = sip_continuity(sources["transactions"])
    hhi = sector_hhi(sources["holdings"], sources["funds"])
    sharpe = sharpe_by_scheme(returns, sources["performance"])

    REPORTS.mkdir(parents=True, exist_ok=True)
    var_report.to_csv(REPORTS / "var_cvar_report.csv", index=False)
    plot_rolling_sharpe(rolling, REPORTS / "rolling_sharpe_chart.png")
    return {
        "returns": returns,
        "var_cvar": var_report,
        "rolling_sharpe": rolling,
        "cohorts": cohorts,
        "sip_continuity": continuity,
        "sip_continuity_summary": continuity_summary,
        "sector_hhi": hhi,
        "sharpe": sharpe,
    }
