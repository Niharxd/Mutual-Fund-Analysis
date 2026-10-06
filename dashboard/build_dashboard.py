"""Build source-grounded mutual-fund dashboard exports."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.offsetbox import AnnotationBbox, OffsetImage


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUTPUT = ROOT / "reports"
PAGE_DIR = OUTPUT / "dashboard_pages"
LOGO = ROOT / "dashboard" / "assets" / "bluestock_logo.png"
BLUE = "#2457A7"
NAVY = "#14233B"
TEAL = "#27A6A1"
PALETTE = [BLUE, TEAL, "#F2A541", "#CC5C5C", "#7868A6", "#76A5AF"]


def read_csv(name: str, **kwargs: object) -> pd.DataFrame:
    return pd.read_csv(DATA / name, **kwargs)


def format_axis(ax: plt.Axes, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=NAVY, pad=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)


def save_page(fig: plt.Figure, number: int, title: str, subtitle: str) -> Path:
    fig.suptitle(title, x=0.055, y=0.975, ha="left", fontsize=21, fontweight="bold", color=NAVY)
    fig.text(0.055, 0.938, subtitle, ha="left", fontsize=9, color="#5C6878")
    logo = OffsetImage(plt.imread(LOGO), zoom=0.55)
    fig.add_artist(
        AnnotationBbox(
            logo,
            (0.94, 0.95),
            xycoords="figure fraction",
            frameon=False,
            box_alignment=(0.5, 0.5),
        )
    )
    fig.text(
        0.055,
        0.018,
        "Bluestock Mutual Fund Analysis  |  Source: supplied project datasets  |  Values reflect available sample coverage",
        fontsize=8,
        color="#667085",
    )
    fig.tight_layout(rect=(0.04, 0.05, 0.98, 0.91), h_pad=2.4, w_pad=2.2)
    path = PAGE_DIR / f"page_{number}_{title.lower().replace(' ', '_').replace('&', 'and')}.png"
    fig.savefig(path, dpi=170, facecolor="white", bbox_inches="tight")
    return path


def build_industry_page() -> tuple[plt.Figure, dict[str, float | str]]:
    aum = read_csv("03_aum_by_fund_house.csv", parse_dates=["date"])
    sip = read_csv("04_monthly_sip_inflows.csv")
    folios = read_csv("06_industry_folio_count.csv")
    latest_date = aum["date"].max()
    latest_aum = float(aum.loc[aum["date"].eq(latest_date), "aum_lakh_crore"].sum())
    latest_sip = float(sip.iloc[-1]["sip_inflow_crore"])
    latest_folios = float(folios.iloc[-1]["total_folios_crore"])
    scheme_count = int(aum.loc[aum["date"].eq(latest_date), "num_schemes"].sum())
    kpis: dict[str, float | str] = {
        "aum": latest_aum,
        "sip": latest_sip,
        "folios": latest_folios,
        "schemes": scheme_count,
        "aum_date": latest_date.strftime("%b %Y"),
        "sip_date": str(sip.iloc[-1]["month"]),
        "folio_date": str(folios.iloc[-1]["month"]),
    }

    fig = plt.figure(figsize=(16, 9))
    grid = fig.add_gridspec(3, 4, height_ratios=[0.58, 1, 1])
    cards = [
        (f"₹{latest_aum:.2f}L Cr", f"Latest AUM · {kpis['aum_date']}"),
        (f"₹{latest_sip:,.0f} Cr", f"Monthly SIP · {kpis['sip_date']}"),
        (f"{latest_folios:.2f} Cr", f"Industry folios · {kpis['folio_date']}"),
        (f"{scheme_count:,}", "AMC-reported schemes · latest snapshot"),
    ]
    for i, (value, label) in enumerate(cards):
        ax = fig.add_subplot(grid[0, i])
        ax.set_facecolor("#F2F6FC")
        ax.text(0.05, 0.63, value, transform=ax.transAxes, fontsize=20, fontweight="bold", color=BLUE)
        ax.text(0.05, 0.22, label, transform=ax.transAxes, fontsize=9, color="#5C6878")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    ax = fig.add_subplot(grid[1, :])
    aum_trend = aum.groupby("date", as_index=False)["aum_lakh_crore"].sum()
    ax.plot(aum_trend["date"], aum_trend["aum_lakh_crore"], marker="o", color=BLUE, linewidth=2.5)
    format_axis(ax, "Industry AUM trend (reported snapshots)")
    ax.set_ylabel("₹ lakh crore")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", rotation=20)

    latest = aum.loc[aum["date"].eq(latest_date)].sort_values("aum_lakh_crore", ascending=True)
    ax = fig.add_subplot(grid[2, 0])
    ax.barh(latest["fund_house"], latest["aum_lakh_crore"], color=BLUE)
    format_axis(ax, "Latest AUM by asset manager")
    ax.set_xlabel("₹ lakh crore")

    ax = fig.add_subplot(grid[2, 1])
    counts = latest.sort_values("num_schemes", ascending=True)
    ax.barh(counts["fund_house"], counts["num_schemes"], color=TEAL)
    format_axis(ax, "AMC-reported scheme count")
    ax.set_xlabel("Schemes")
    return fig, kpis


def build_performance_page() -> plt.Figure:
    perf = read_csv("07_scheme_performance.csv")
    score = pd.read_csv(OUTPUT / "fund_scorecard.csv")
    nav = read_csv("02_nav_history.csv", parse_dates=["date"])
    benchmarks = read_csv("10_benchmark_indices.csv", parse_dates=["date"])
    if "scheme_name" not in score.columns:
        master = read_csv("01_fund_master.csv")
        score = score.merge(master[["amfi_code", "scheme_name"]], on="amfi_code", how="left")
    top = score.sort_values("fund_score", ascending=False).head(10)
    top_codes = top["amfi_code"].astype(str).tolist()

    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax = axes[0, 0]
    sns.scatterplot(
        data=perf,
        x="return_3yr_pct",
        y="std_dev_ann_pct",
        hue="category",
        size="aum_crore",
        sizes=(25, 230),
        alpha=0.8,
        ax=ax,
        legend=False,
        palette="deep",
    )
    format_axis(ax, "Three-year return vs annualised volatility")
    ax.set_xlabel("3-year return (%)")
    ax.set_ylabel("Annualised standard deviation (%)")

    ax = axes[0, 1]
    display_top = top.sort_values("fund_score", ascending=True)
    labels = display_top["scheme_name"].fillna(display_top["amfi_code"].astype(str)).str.slice(0, 33)
    ax.barh(labels, display_top["fund_score"], color=TEAL)
    format_axis(ax, "Top 10 funds by composite score")
    ax.set_xlabel("Score (0–100)")

    ax = axes[1, 0]
    daily = nav.loc[nav["amfi_code"].astype(str).isin(top_codes)].copy()
    if not daily.empty:
        daily["indexed_nav"] = daily["nav"] / daily.groupby("amfi_code")["nav"].transform("first") * 100
        for i, (code, grp) in enumerate(daily.groupby("amfi_code")):
            label = top.loc[top["amfi_code"].astype(str).eq(code), "scheme_name"]
            ax.plot(grp["date"], grp["indexed_nav"], linewidth=1.1, alpha=0.8, label=(label.iloc[0][:22] if not label.empty else code), color=PALETTE[i % len(PALETTE)])
    format_axis(ax, "Indexed NAV trend · top scorecard funds")
    ax.set_ylabel("Index (first observation = 100)")
    ax.legend(fontsize=6, ncol=2, frameon=False)

    ax = axes[1, 1]
    benchmark = benchmarks.loc[benchmarks["index_name"].isin(["NIFTY50", "NIFTY100"])].copy()
    for i, (name, grp) in enumerate(benchmark.groupby("index_name")):
        grp = grp.sort_values("date")
        ax.plot(grp["date"], grp["close_value"] / grp["close_value"].iloc[0] * 100, label=name, color=PALETTE[i])
    format_axis(ax, "Benchmark context · indexed market levels")
    ax.set_ylabel("Index (first observation = 100)")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def build_investor_page() -> plt.Figure:
    tx = read_csv("08_investor_transactions.csv", parse_dates=["transaction_date"])
    sip = tx.loc[tx["transaction_type"].str.casefold().eq("sip")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))

    state = sip.groupby("state")["amount_inr"].sum().nlargest(12).sort_values()
    ax = axes[0, 0]
    ax.barh(state.index, state.values / 1e7, color=BLUE)
    format_axis(ax, "SIP amount by state · top 12")
    ax.set_xlabel("₹ crore")

    ax = axes[0, 1]
    split = tx.groupby("transaction_type")["amount_inr"].sum().sort_values(ascending=False)
    ax.pie(split.values, labels=split.index, autopct="%1.0f%%", startangle=90, colors=PALETTE[: len(split)], textprops={"fontsize": 8})
    ax.set_title("Transaction amount mix", loc="left", fontsize=12, fontweight="bold", color=NAVY)

    ax = axes[1, 0]
    order = sip.groupby("age_group")["amount_inr"].median().sort_values().index
    sip["amount_lakh"] = sip["amount_inr"] / 1e5
    sns.boxplot(data=sip, x="age_group", y="amount_lakh", order=order, color="#A9D8D5", showfliers=False, ax=ax)
    format_axis(ax, "SIP amount distribution by investor age")
    ax.set_xlabel("Age group")
    ax.set_ylabel("Transaction amount (₹ lakh)")

    ax = axes[1, 1]
    monthly = tx.set_index("transaction_date").resample("MS").size()
    ax.plot(monthly.index, monthly.values, color=TEAL, linewidth=2)
    format_axis(ax, "Monthly transaction volume")
    ax.set_ylabel("Transaction records")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(axis="x", rotation=25)
    return fig


def build_trends_page() -> plt.Figure:
    sip = read_csv("04_monthly_sip_inflows.csv")
    categories = read_csv("05_category_inflows.csv")
    folios = read_csv("06_industry_folio_count.csv")
    benchmarks = read_csv("10_benchmark_indices.csv", parse_dates=["date"])
    sip["month_date"] = pd.to_datetime(sip["month"])
    categories["month_date"] = pd.to_datetime(categories["month"])
    folios["month_date"] = pd.to_datetime(folios["month"])
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))

    ax = axes[0, 0]
    ax.bar(sip["month_date"], sip["sip_inflow_crore"], width=22, color=BLUE, alpha=0.72, label="SIP inflow")
    nifty = benchmarks.loc[benchmarks["index_name"].eq("NIFTY50")].sort_values("date")
    if not nifty.empty:
        twin = ax.twinx()
        twin.plot(nifty["date"], nifty["close_value"], color="#D1792D", linewidth=1.3, label="NIFTY 50")
        twin.set_ylabel("NIFTY 50 closing level")
        twin.spines["top"].set_visible(False)
    format_axis(ax, "Monthly SIP inflow and NIFTY 50")
    ax.set_ylabel("SIP inflow (₹ crore)")
    peak = sip.loc[sip["sip_inflow_crore"].idxmax()]
    ax.annotate(
        f"Peak ₹{peak['sip_inflow_crore']:,.0f} Cr\n{peak['month']}",
        xy=(peak["month_date"], peak["sip_inflow_crore"]),
        xytext=(-75, -32),
        textcoords="offset points",
        fontsize=8,
        arrowprops={"arrowstyle": "->", "color": NAVY},
    )

    ax = axes[0, 1]
    pivot = categories.pivot_table(index="category", columns="month", values="net_inflow_crore", aggfunc="sum", fill_value=0)
    sns.heatmap(pivot, cmap="YlGnBu", ax=ax, cbar_kws={"label": "Net inflow (₹ crore)"}, linewidths=0.15)
    ax.set_title("Category net inflow heatmap · available months", loc="left", fontsize=12, fontweight="bold", color=NAVY, pad=9)
    ax.set_xlabel("Month")
    ax.set_ylabel("")
    ax.tick_params(axis="x", labelrotation=45, labelsize=6)

    ax = axes[1, 0]
    fy25 = categories.loc[categories["month"].between("2024-04", "2025-03")].groupby("category")["net_inflow_crore"].sum().nlargest(8).sort_values()
    ax.barh(fy25.index, fy25.values, color=TEAL)
    format_axis(ax, "Top categories by net inflow · FY25")
    ax.set_xlabel("₹ crore")

    ax = axes[1, 1]
    ax.plot(folios["month_date"], folios["total_folios_crore"], marker="o", color=BLUE, linewidth=2)
    format_axis(ax, "Industry folio growth")
    ax.set_ylabel("Folio count (crore)")
    ax.annotate(f"{folios.iloc[0]['total_folios_crore']:.2f} Cr", (folios.iloc[0]["month_date"], folios.iloc[0]["total_folios_crore"]), xytext=(5, 10), textcoords="offset points", fontsize=8)
    ax.annotate(f"{folios.iloc[-1]['total_folios_crore']:.2f} Cr", (folios.iloc[-1]["month_date"], folios.iloc[-1]["total_folios_crore"]), xytext=(-42, 10), textcoords="offset points", fontsize=8)
    return fig


def main() -> None:
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    figs: list[tuple[plt.Figure, str, str]] = []

    industry_fig, kpis = build_industry_page()
    figs.append((industry_fig, "Industry Overview", "Latest available source data; industry and AMC-reported measures are not the 40-scheme sample."))
    figs.append((build_performance_page(), "Fund Performance", "40-scheme performance sample; historical NAV coverage starts in January 2022."))
    figs.append((build_investor_page(), "Investor Analytics", "Transaction sample available through May 2025; amounts are based on supplied transaction records."))
    figs.append((build_trends_page(), "SIP & Market Trends", "SIP and folio series extend through December 2025; category inflows cover FY25."))

    image_paths: list[Path] = []
    with PdfPages(OUTPUT / "Dashboard.pdf") as pdf:
        for i, (fig, title, subtitle) in enumerate(figs, start=1):
            image_paths.append(save_page(fig, i, title, subtitle))
            pdf.savefig(fig, facecolor="white", bbox_inches="tight")
            plt.close(fig)

    metadata = [
        "# Dashboard exports",
        "",
        "The PDF and page PNGs use only the supplied cleaned project datasets. KPI cards use the latest available source records; they are not externally estimated industry totals.",
        "The supplied Bluestock logo is included on each exported report page.",
        "",
        f"- Latest reported AMC AUM: ₹{float(kpis['aum']):.2f} lakh crore ({kpis['aum_date']}).",
        f"- Latest monthly SIP inflow: ₹{float(kpis['sip']):,.0f} crore ({kpis['sip_date']}); the source series peak is annotated in the trends page.",
        f"- Latest industry folios: {float(kpis['folios']):.2f} crore ({kpis['folio_date']}).",
        f"- AMC-reported schemes in latest AUM snapshot: {int(kpis['schemes']):,}; this differs from the 40-scheme performance sample.",
        "- Category inflows are available for April 2024–March 2025; investor transaction records end in May 2025.",
        "",
        "The page images and PDF are static exports. Run `streamlit run dashboard/app.py` from the project root to use the interactive dashboard.",
    ]
    (OUTPUT / "dashboard_data_notes.md").write_text("\n".join(metadata) + "\n", encoding="utf-8")
    print(f"Wrote {len(image_paths)} page PNGs and {OUTPUT / 'Dashboard.pdf'}")
    for path in image_paths:
        print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
