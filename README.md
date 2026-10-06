# Bluestock Mutual Fund Analysis

An end-to-end, local mutual-fund analytics capstone covering source-data validation, ETL, a SQLite analytical model, exploratory analysis, fund performance and risk, investor transaction patterns, and a four-page Streamlit dashboard.

> **Scope:** Results describe the supplied datasets and the schemes they contain. They are historical, sample-bound analyses—not investment advice, a market-wide census, or predictions. The interactive dashboard runs locally. A hosted dashboard URL and a validated native Power BI `.pbix` are not included.

## Project layout

```text
analytics/                 Advanced risk and investor analytics
dashboard/                 Streamlit app and static dashboard exporter
data/raw/                  Ten source CSV datasets
data/processed/            Normalized, analysis-ready CSV datasets
notebooks/                 EDA, performance, and advanced analytics notebooks
reports/                   Charts, tables, dashboard exports, final PDF/PPTX
sql/                       SQL source files and supporting queries
data_ingestion.py          Source profiling and AMFI-code validation
day2_etl.py                Cleaning and SQLite star-schema load
live_nav_fetch.py          Optional MFAPI NAV downloader
recommender.py             Risk-appetite fund recommender CLI
run_pipeline.py            Local pipeline entry point
build_final_deliverables.py Final report and presentation generator
```

## Setup

Python 3.10 or newer is recommended. From PowerShell at the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, invoke the environment's executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the project

### Full local workflow

```powershell
python run_pipeline.py
```

This profiles the ten raw CSVs and AMFI-code coverage, rebuilds processed data and `bluestock_mf.db`, calculates advanced risk/investor outputs, refreshes static dashboard exports, and generates the final PDF and presentation. It does **not** make network requests.

Skip the verbose CSV profile while retaining ETL and downstream validation:

```powershell
python run_pipeline.py --skip-profile
```

The EDA and performance notebooks are available for interactive exploration in `notebooks/`. The performance outputs and scorecard consumed by the dashboard/report are stored under `reports/`; rerun `notebooks/Performance_Analytics.ipynb` when changing the source data and needing refreshed performance outputs.

### Individual commands

```powershell
python data_ingestion.py
python day2_etl.py
python -m analytics.advanced_analytics
python recommender.py --risk-appetite Moderate
python dashboard/build_dashboard.py
python build_final_deliverables.py
streamlit run dashboard/app.py
```

The dashboard opens locally (typically at `http://localhost:8501`). It reads the processed CSVs and generated scorecard from the project tree.

### Optional live NAV fetch

```powershell
python live_nav_fetch.py
```

This contacts `https://api.mfapi.in` and saves fetched histories under `data/raw/live_nav/`. Fetched files are kept separate from the ten canonical source CSVs and are not automatically merged into the analysis history.

## Source datasets

All ten supplied CSVs are expected in `data/raw/`; the ETL writes cleaned copies into `data/processed/`.

| File | Description |
|---|---|
| `01_fund_master.csv` | Scheme identifiers and descriptive fund attributes |
| `02_nav_history.csv` | Observed NAV time series for 40 schemes |
| `03_aum_by_fund_house.csv` | Fund-house AUM snapshots |
| `04_monthly_sip_inflows.csv` | Monthly industry SIP inflows and related measures |
| `05_category_inflows.csv` | Category-level monthly net inflows |
| `06_industry_folio_count.csv` | Monthly industry and category folio counts |
| `07_scheme_performance.csv` | Scheme returns, risk attributes, expenses, and ratings |
| `08_investor_transactions.csv` | Investor transaction sample with dates, amounts, and segments |
| `09_portfolio_holdings.csv` | Scheme holdings with sector weights |
| `10_benchmark_indices.csv` | Dated benchmark/index observations |

See [`data_dictionary.md`](data_dictionary.md), [`schema.sql`](schema.sql), and [`queries.sql`](queries.sql) for field definitions and relational details. Tables are linked by `amfi_code` and date keys where the grain supports those relationships.

## Analytics and interpretation

- **Performance:** observed market-date daily returns, CAGR, Sharpe and Sortino ratios, OLS alpha/beta versus NIFTY100, drawdowns, weighted scorecard, and benchmark tracking error.
- **Advanced risk:** historical 95% daily VaR/CVaR and 90-observation rolling Sharpe; observed raw NAV is used to avoid artificial zero returns from forward-filled calendar dates.
- **Investor analysis:** first-transaction-year cohorts, SIP preference and investment summaries, and a rule-based at-risk flag (six or more SIP rows, with mean interval above 35 days).
- **Concentration:** sector HHI aggregates disclosed holdings by sector before squaring weights.
- **Recommendation utility:** ranks schemes by observed Sharpe within the selected risk-grade mapping. It is an educational screening example, not individualized advice.

Important coverage limitations:

- NAV history runs from January 2022 to May 2026, so a full five-year return lookback is unavailable.
- The 40-scheme performance sample is not the complete Indian mutual-fund universe.
- Category inflows cover FY2025 only; holdings are a single snapshot for 34 schemes.
- Industry snapshots and the investor transaction sample have their own reporting windows. Investor records end in May 2025 and should not be treated as population-representative.
- Calendar-forward-filled NAV is useful for display continuity; use observed NAV dates for return and risk estimates.
- AMFI scheme codes are identifiers, not encoded fund characteristics.

## Key outputs

| Output | Location |
|---|---|
| SQLite database | `bluestock_mf.db` |
| Final report (16 pages) | `reports/Final_Report.pdf` |
| Project presentation (12 slides) | `reports/Bluestock_MF_Presentation.pptx` |
| Fund scorecard and regression results | `reports/fund_scorecard.csv`, `reports/alpha_beta.csv` |
| VaR/CVaR report and rolling Sharpe chart | `reports/var_cvar_report.csv`, `reports/rolling_sharpe_chart.png` |
| Static dashboard PDF and four page PNGs | `reports/Dashboard.pdf`, `reports/dashboard_pages/` |
| EDA charts | `reports/charts/` |

The PDF and presentation are regenerated by `python build_final_deliverables.py` (or by the full pipeline).

## Dashboard status

The supported interactive dashboard is the local Streamlit app:

```powershell
streamlit run dashboard/app.py
```

Static page screenshots and a dashboard PDF are included for sharing. No public deployment has been configured. Power BI project files were not validated successfully in Power BI Desktop, so this repository does not claim to deliver a working native `.pbix`.
