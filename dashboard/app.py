"""Interactive Streamlit dashboard for the supplied mutual-fund datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
LOGO = ROOT / "dashboard" / "assets" / "bluestock_logo.png"
BLUE = "#2457A7"
NAVY = "#14233B"
TEAL = "#27A6A1"
ORANGE = "#D1792D"
PALETTE = [BLUE, TEAL, ORANGE, "#CC5C5C", "#7868A6", "#76A5AF"]
pio.templates.default = "plotly_white"

st.set_page_config(
    page_title="Bluestock | Mutual Fund Analysis",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(show_spinner="Loading project datasets…")
def load_data() -> dict[str, pd.DataFrame]:
    """Load the processed tables and scorecard for dashboard use."""
    datasets = {
        "funds": pd.read_csv(DATA / "01_fund_master.csv", dtype={"amfi_code": str}),
        "nav": pd.read_csv(DATA / "02_nav_history.csv", dtype={"amfi_code": str}, parse_dates=["date"]),
        "aum": pd.read_csv(DATA / "03_aum_by_fund_house.csv", parse_dates=["date"]),
        "sip": pd.read_csv(DATA / "04_monthly_sip_inflows.csv"),
        "categories": pd.read_csv(DATA / "05_category_inflows.csv"),
        "folios": pd.read_csv(DATA / "06_industry_folio_count.csv"),
        "performance": pd.read_csv(DATA / "07_scheme_performance.csv", dtype={"amfi_code": str}),
        "transactions": pd.read_csv(
            DATA / "08_investor_transactions.csv",
            dtype={"amfi_code": str},
            parse_dates=["transaction_date"],
        ),
        "holdings": pd.read_csv(DATA / "09_portfolio_holdings.csv", dtype={"amfi_code": str}),
        "benchmarks": pd.read_csv(DATA / "10_benchmark_indices.csv", parse_dates=["date"]),
    }
    scorecard_path = REPORTS / "fund_scorecard.csv"
    if scorecard_path.exists():
        datasets["scorecard"] = pd.read_csv(scorecard_path, dtype={"amfi_code": str})
    else:
        datasets["scorecard"] = datasets["performance"].copy()
    for key in ("sip", "categories", "folios"):
        datasets[key]["month_date"] = pd.to_datetime(datasets[key]["month"] + "-01")
    return datasets


def money_cr(value: float) -> str:
    """Format a crore-denominated value for compact dashboard labels."""
    return f"₹{value:,.0f} Cr"


def page_header(title: str, description: str) -> None:
    """Render a page title and concise data-coverage note."""
    st.title(title)
    st.caption(description)


def industry_overview(data: dict[str, pd.DataFrame]) -> None:
    """Render industry AUM, SIP, folio, and AMC snapshot visualizations."""
    page_header(
        "Industry Overview",
        "Latest available industry and AMC source snapshots. These totals are distinct from the 40-scheme performance sample.",
    )
    aum = data["aum"]
    sip = data["sip"].sort_values("month_date")
    folios = data["folios"].sort_values("month_date")
    latest_aum_date = aum["date"].max()
    latest_aum = aum.loc[aum["date"].eq(latest_aum_date)]
    latest_sip = sip.iloc[-1]
    latest_folios = folios.iloc[-1]

    cards = st.columns(4)
    cards[0].metric(
        "Reported AMC AUM",
        f"₹{latest_aum['aum_lakh_crore'].sum():.2f}L Cr",
        latest_aum_date.strftime("%b %Y"),
        help=f"Exact source total: ₹{latest_aum['aum_lakh_crore'].sum():.2f} lakh crore.",
    )
    cards[1].metric(
        "Monthly SIP inflow",
        f"₹{latest_sip['sip_inflow_crore'] / 1000:.0f}K Cr",
        pd.to_datetime(latest_sip["month_date"]).strftime("%b %Y"),
        help=f"Exact source value: {money_cr(float(latest_sip['sip_inflow_crore']))}.",
    )
    cards[2].metric(
        "Industry folios",
        f"{latest_folios['total_folios_crore']:.2f} Cr",
        pd.to_datetime(latest_folios["month_date"]).strftime("%b %Y"),
    )
    cards[3].metric(
        "AMC-reported schemes",
        f"{int(latest_aum['num_schemes'].sum()):,}",
        latest_aum_date.strftime("%b %Y"),
    )

    yearly = aum.assign(year=aum["date"].dt.year).sort_values("date")
    yearly = yearly.groupby(["year", "fund_house"], as_index=False).tail(1)
    left, right = st.columns(2)
    with left:
        trend = aum.groupby("date", as_index=False)["aum_lakh_crore"].sum()
        fig = px.line(trend, x="date", y="aum_lakh_crore", markers=True, title="Industry AUM trend")
        fig.update_traces(line_color=BLUE)
        fig.update_layout(xaxis_title="", yaxis_title="₹ lakh crore")
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.bar(
            yearly,
            x="year",
            y="aum_lakh_crore",
            color="fund_house",
            barmode="group",
            title="AMC AUM by year",
            labels={"year": "Year", "aum_lakh_crore": "₹ lakh crore", "fund_house": "Fund house"},
            color_discrete_sequence=PALETTE,
        )
        st.plotly_chart(fig, width="stretch")

    latest_by_amc = latest_aum.sort_values("aum_lakh_crore", ascending=False)
    st.subheader("Latest AMC snapshot")
    st.plotly_chart(
        px.bar(
            latest_by_amc,
            x="aum_lakh_crore",
            y="fund_house",
            orientation="h",
            color="aum_lakh_crore",
            color_continuous_scale=["#B7D5F3", BLUE],
            title=f"AUM by asset manager · {latest_aum_date:%b %Y}",
            labels={"aum_lakh_crore": "₹ lakh crore", "fund_house": "Fund house"},
        ).update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False),
        width="stretch",
    )


def fund_performance(data: dict[str, pd.DataFrame]) -> None:
    """Render filtered fund returns, scorecard, NAV, and benchmark comparisons."""
    page_header(
        "Fund Performance",
        "Filter the supplied 40-scheme sample, inspect its scorecard, and compare indexed NAV and benchmark levels.",
    )
    master = data["funds"]
    performance = data["performance"].merge(
        master[["amfi_code", "scheme_name", "fund_house", "category", "plan"]],
        on="amfi_code",
        how="left",
        suffixes=("", "_master"),
    )
    # Prefer the canonical master values when duplicate descriptive columns exist.
    for field in ("scheme_name", "fund_house", "category", "plan"):
        master_field = f"{field}_master"
        if master_field in performance:
            performance[field] = performance[master_field].fillna(performance[field])

    house_col, category_col, plan_col = st.columns(3)
    houses = sorted(performance["fund_house"].dropna().unique())
    categories = sorted(performance["category"].dropna().unique())
    plans = sorted(performance["plan"].dropna().unique())
    house = house_col.selectbox("Fund house", ["All"] + houses)
    category = category_col.selectbox("Category", ["All"] + categories)
    plan = plan_col.selectbox("Plan", ["All"] + plans)

    filtered = performance.copy()
    if house != "All":
        filtered = filtered.loc[filtered["fund_house"].eq(house)]
    if category != "All":
        filtered = filtered.loc[filtered["category"].eq(category)]
    if plan != "All":
        filtered = filtered.loc[filtered["plan"].eq(plan)]

    left, right = st.columns(2)
    with left:
        fig = px.scatter(
            filtered,
            x="return_3yr_pct",
            y="std_dev_ann_pct",
            color="category",
            size="aum_crore",
            hover_name="scheme_name",
            hover_data=["fund_house", "plan", "expense_ratio_pct", "sharpe_ratio"],
            size_max=34,
            title="Return vs. volatility",
            labels={"return_3yr_pct": "3-year return (%)", "std_dev_ann_pct": "Annualised standard deviation (%)"},
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        score = data["scorecard"]
        score_filtered = score.merge(
            master[["amfi_code", "scheme_name", "fund_house", "category", "plan"]],
            on="amfi_code",
            how="left",
            suffixes=("", "_master"),
        )
        for field in ("scheme_name", "fund_house", "category", "plan"):
            master_field = f"{field}_master"
            if master_field in score_filtered:
                score_filtered[field] = score_filtered[master_field].fillna(score_filtered[field])
        if house != "All":
            score_filtered = score_filtered.loc[score_filtered["fund_house"].eq(house)]
        if category != "All":
            score_filtered = score_filtered.loc[score_filtered["category"].eq(category)]
        if plan != "All":
            score_filtered = score_filtered.loc[score_filtered["plan"].eq(plan)]
        score_columns = [
            column
            for column in ("scheme_name", "fund_house", "fund_score", "cagr_3yr", "sharpe_ratio", "alpha", "expense_ratio_pct")
            if column in score_filtered.columns
        ]
        if "fund_score" in score_filtered:
            score_filtered = score_filtered.sort_values("fund_score", ascending=False)
        st.subheader("Fund scorecard")
        st.dataframe(score_filtered[score_columns], width="stretch", hide_index=True)

    if filtered.empty:
        st.info("No schemes match the selected filters.")
        return

    options = (
        filtered.sort_values("return_3yr_pct", ascending=False)
        .drop_duplicates("amfi_code")
        .set_index("scheme_name")["amfi_code"]
        .to_dict()
    )
    selected_names = st.multiselect(
        "Schemes for NAV comparison",
        options=list(options),
        default=list(options)[:5],
    )
    selected_codes = [options[name] for name in selected_names]
    if selected_codes:
        nav = data["nav"].loc[data["nav"]["amfi_code"].isin(selected_codes)].copy()
        nav = nav.sort_values("date")
        nav["indexed_value"] = nav["nav"] / nav.groupby("amfi_code")["nav"].transform("first") * 100
        nav = nav.merge(master[["amfi_code", "scheme_name"]], on="amfi_code", how="left")

        if not nav.empty:
            end_date = nav["date"].max()
            start_date = end_date - pd.DateOffset(years=3)
            nav = nav.loc[nav["date"].ge(start_date)]
            benchmark = data["benchmarks"].loc[
                data["benchmarks"]["index_name"].isin(["NIFTY50", "NIFTY100"])
                & data["benchmarks"]["date"].between(start_date, end_date)
            ].copy()
            benchmark = benchmark.sort_values("date")
            benchmark["indexed_value"] = benchmark["close_value"] / benchmark.groupby("index_name")["close_value"].transform("first") * 100

            st.subheader("Indexed NAV and benchmark comparison · latest three years")
            fig = go.Figure()
            for name, group in nav.groupby("scheme_name"):
                fig.add_trace(go.Scatter(x=group["date"], y=group["indexed_value"], mode="lines", name=name))
            for name, group in benchmark.groupby("index_name"):
                fig.add_trace(go.Scatter(x=group["date"], y=group["indexed_value"], mode="lines", name=name, line={"dash": "dash"}))
            fig.update_layout(xaxis_title="", yaxis_title="Indexed level (first observation = 100)", hovermode="x unified")
            st.plotly_chart(fig, width="stretch")


def investor_analytics(data: dict[str, pd.DataFrame]) -> None:
    """Render transaction sample summaries with geographic and demographic filters."""
    page_header(
        "Investor Analytics",
        "Explore the supplied investor transaction records. This sample currently spans January 2024 through May 2025.",
    )
    tx = data["transactions"]
    state_options = sorted(tx["state"].dropna().unique())
    age_options = sorted(tx["age_group"].dropna().unique())
    tier_options = sorted(tx["city_tier"].dropna().unique())
    state_col, age_col, tier_col = st.columns(3)
    states = state_col.multiselect("State", state_options, default=state_options)
    ages = age_col.multiselect("Age group", age_options, default=age_options)
    tiers = tier_col.multiselect("City tier", tier_options, default=tier_options)

    filtered = tx.loc[
        tx["state"].isin(states) & tx["age_group"].isin(ages) & tx["city_tier"].isin(tiers)
    ].copy()
    if filtered.empty:
        st.info("No transactions match the selected filters.")
        return
    sip = filtered.loc[filtered["transaction_type"].str.casefold().eq("sip")].copy()

    total_sip = sip["amount_inr"].sum() / 1e7
    mean_sip = sip["amount_inr"].mean() if not sip.empty else 0.0
    metrics = st.columns(3)
    metrics[0].metric("Filtered transaction records", f"{len(filtered):,}")
    metrics[1].metric("Filtered SIP amount", money_cr(total_sip))
    metrics[2].metric("Average SIP transaction", f"₹{mean_sip:,.0f}")

    left, right = st.columns(2)
    with left:
        by_state = sip.groupby("state", as_index=False)["amount_inr"].sum()
        by_state["amount_crore"] = by_state["amount_inr"] / 1e7
        by_state = by_state.nlargest(15, "amount_crore").sort_values("amount_crore")
        st.plotly_chart(
            px.bar(
                by_state,
                x="amount_crore",
                y="state",
                orientation="h",
                title="SIP amount by state · top 15",
                labels={"amount_crore": "₹ crore", "state": "State"},
                color_discrete_sequence=[BLUE],
            ),
            width="stretch",
        )
    with right:
        split = filtered.groupby("transaction_type", as_index=False)["amount_inr"].sum()
        st.plotly_chart(
            px.pie(split, names="transaction_type", values="amount_inr", hole=0.48, title="Transaction amount mix"),
            width="stretch",
        )

    left, right = st.columns(2)
    with left:
        age_sip = sip.groupby("age_group", as_index=False)["amount_inr"].mean()
        st.plotly_chart(
            px.bar(
                age_sip,
                x="age_group",
                y="amount_inr",
                title="Average SIP amount by age group",
                labels={"amount_inr": "Average amount (₹)", "age_group": "Age group"},
                color_discrete_sequence=[TEAL],
            ),
            width="stretch",
        )
    with right:
        monthly = filtered.assign(month=filtered["transaction_date"].dt.to_period("M").dt.to_timestamp())
        monthly = monthly.groupby(["month", "transaction_type"], as_index=False).size()
        st.plotly_chart(
            px.line(
                monthly,
                x="month",
                y="size",
                color="transaction_type",
                markers=True,
                title="Monthly transaction volume",
                labels={"month": "", "size": "Transactions", "transaction_type": "Type"},
                color_discrete_sequence=PALETTE,
            ),
            width="stretch",
        )


def sip_and_market_trends(data: dict[str, pd.DataFrame]) -> None:
    """Render SIP, NIFTY 50, FY25 category-flow, and folio trends."""
    page_header(
        "SIP & Market Trends",
        "SIP inflows and folios are available through December 2025; category inflow data covers FY2025 only.",
    )
    sip = data["sip"].sort_values("month_date")
    peak = sip.loc[sip["sip_inflow_crore"].idxmax()]
    left, right = st.columns(2)
    with left:
        nifty = data["benchmarks"].loc[data["benchmarks"]["index_name"].eq("NIFTY50")].sort_values("date").copy()
        nifty_monthly = nifty.set_index("date")["close_value"].resample("MS").last().dropna().rename("nifty50")
        sip_market = sip.set_index("month_date")[["sip_inflow_crore"]].join(nifty_monthly, how="inner").reset_index()
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(x=sip_market["month_date"], y=sip_market["sip_inflow_crore"], name="SIP inflow (₹ Cr)", marker_color=BLUE),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=sip_market["month_date"], y=sip_market["nifty50"], name="NIFTY 50", line={"color": ORANGE, "width": 2}),
            secondary_y=True,
        )
        fig.add_annotation(
            x=peak["month_date"],
            y=peak["sip_inflow_crore"],
            text=f"Peak {money_cr(float(peak['sip_inflow_crore']))}",
            showarrow=True,
            arrowhead=2,
            xref="x",
            yref="y",
        )
        fig.update_layout(title="Monthly SIP inflow and NIFTY 50", hovermode="x unified", legend={"orientation": "h"})
        fig.update_yaxes(title_text="SIP inflow (₹ crore)", secondary_y=False)
        fig.update_yaxes(title_text="NIFTY 50 closing level", secondary_y=True)
        st.plotly_chart(fig, width="stretch")

    with right:
        categories = data["categories"].copy()
        pivot = categories.pivot_table(
            index="category", columns="month", values="net_inflow_crore", aggfunc="sum", fill_value=0
        )
        fig = px.imshow(
            pivot,
            aspect="auto",
            color_continuous_scale="YlGnBu",
            labels={"x": "Month", "y": "Category", "color": "Net inflow (₹ Cr)"},
            title="Category net inflows · FY2025",
        )
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        fy25 = categories.loc[categories["month"].between("2024-04", "2025-03")]
        by_category = fy25.groupby("category", as_index=False)["net_inflow_crore"].sum()
        by_category = by_category.nlargest(5, "net_inflow_crore").sort_values("net_inflow_crore")
        st.plotly_chart(
            px.bar(
                by_category,
                x="net_inflow_crore",
                y="category",
                orientation="h",
                title="Top 5 categories by net inflow · FY2025",
                labels={"net_inflow_crore": "₹ crore", "category": "Category"},
                color_discrete_sequence=[TEAL],
            ),
            width="stretch",
        )
    with right:
        folios = data["folios"].sort_values("month_date")
        fig = px.line(
            folios,
            x="month_date",
            y="total_folios_crore",
            markers=True,
            title="Industry folio count",
            labels={"month_date": "", "total_folios_crore": "Folios (crore)"},
        )
        fig.update_traces(line_color=BLUE)
        for milestone in (15, 20, 25):
            close = folios.iloc[(folios["total_folios_crore"] - milestone).abs().argsort()[:1]]
            if not close.empty and close.iloc[0]["total_folios_crore"] >= milestone:
                row = close.iloc[0]
                fig.add_annotation(
                    x=row["month_date"],
                    y=row["total_folios_crore"],
                    text=f"{row['total_folios_crore']:.1f} Cr",
                    showarrow=True,
                    arrowhead=2,
                )
        st.plotly_chart(fig, width="stretch")


def main() -> None:
    """Configure the Streamlit theme and route selection to the dashboard pages."""
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #f7f9fc; }}
        [data-testid="stHeader"] {{ background: rgba(247, 249, 252, 0.88); }}
        .block-container {{ max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3rem; }}
        h1, h2, h3 {{ color: {NAVY}; letter-spacing: -0.025em; }}
        h1 {{ font-size: 2.15rem; }}
        h2 {{ font-size: 1.75rem; }}
        [data-testid="stMetric"] {{
            background: #fff; border: 1px solid #e7edf5; padding: 1rem 1.1rem;
            border-radius: 0.9rem; box-shadow: 0 3px 12px rgba(20, 35, 59, 0.035);
        }}
        [data-testid="stMetricLabel"] {{ color: #58677d; font-size: 0.88rem; }}
        [data-testid="stMetricValue"] {{ color: {NAVY}; font-size: 1.8rem; }}
        [data-testid="stPlotlyChart"] {{
            background: #fff; border: 1px solid #e7edf5; border-radius: 0.9rem;
            padding: 0.6rem; box-shadow: 0 3px 12px rgba(20, 35, 59, 0.035);
        }}
        [data-testid="stSegmentedControl"] {{ margin: 0.5rem 0 1.6rem; }}
        [data-testid="stSegmentedControl"] button {{ font-weight: 600; }}
        [data-testid="stSelectbox"], [data-testid="stMultiSelect"] {{ background: #fff; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    logo_column, title_column = st.columns([0.1, 0.9], vertical_alignment="center")
    with logo_column:
        st.image(str(LOGO), width=82)
    with title_column:
        st.markdown(f"<h1 style='margin:0;color:{NAVY}'>Mutual Fund Analysis</h1>", unsafe_allow_html=True)
        st.caption("Industry trends · fund performance · investor activity")
    page = st.segmented_control(
        "Dashboard page",
        ["Industry Overview", "Fund Performance", "Investor Analytics", "SIP & Market Trends"],
        default="Industry Overview",
        label_visibility="collapsed",
        key="dashboard_page",
    )
    if page is None:
        page = "Industry Overview"
    try:
        data = load_data()
    except FileNotFoundError as exc:
        st.error(f"Required project dataset is missing: {exc.filename}")
        st.stop()

    if page == "Industry Overview":
        industry_overview(data)
    elif page == "Fund Performance":
        fund_performance(data)
    elif page == "Investor Analytics":
        investor_analytics(data)
    else:
        sip_and_market_trends(data)

    st.divider()
    st.caption(
        "Source coverage: industry snapshots through Dec 2025 · transactions Jan 2024–May 2025 · category flows FY2025"
    )


if __name__ == "__main__":
    main()
