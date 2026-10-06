"""Risk-appetite fund recommender based on observed NAV history."""

from __future__ import annotations

import argparse

from analytics.advanced_analytics import daily_returns, read_sources, recommend_funds, sharpe_by_scheme


def main() -> None:
    """Compute risk-adjusted fund recommendations for a selected risk appetite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--risk-appetite",
        choices=["Low", "Moderate", "High"],
        help="Risk appetite. If omitted, prompt interactively.",
    )
    args = parser.parse_args()
    appetite = args.risk_appetite or input("Risk appetite (Low / Moderate / High): ").strip()

    sources = read_sources()
    observed_returns = daily_returns(sources["nav"])
    sharpe = sharpe_by_scheme(observed_returns, sources["performance"])
    recommendations = recommend_funds(appetite, sharpe)
    print(f"\nTop funds for {appetite.title()} risk appetite")
    print(recommendations[["scheme_name", "risk_grade", "sharpe_ratio_daily", "return_observations"]].to_string(index=False))


if __name__ == "__main__":
    main()
