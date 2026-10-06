# Mutual Fund Analysis Data Dictionary

## Conventions and provenance

- **Raw source** refers to the Day 1 file in `data/raw/`; **cleaned source** is
  its counterpart in `data/processed/` and the SQLite `src_*` table.
- Types below describe the cleaned CSV/Pandas meaning (`INTEGER`, `REAL`,
  `TEXT`, or `DATETIME`). CSV dates are serialized as ISO `YYYY-MM-DD`;
  SQLite stores them as ISO-compatible text/datetime values. SQLite uses
  `INTEGER`, `REAL`, and `TEXT` affinities.
- `NA` means the source file is authoritative for the value and no unsupported
  inference is made.

## Cleaned source datasets

### `fund_master` — `01_fund_master.csv` (40 rows)

Source: `01_fund_master.csv`; loaded to `src_fund_master`.

| Column | Type | Business definition |
|---|---|---|
| `amfi_code` | INTEGER | AMFI scheme identifier; natural key for a scheme. |
| `fund_house` | TEXT | Asset management company / fund house. |
| `scheme_name` | TEXT | Scheme and plan display name. |
| `category` | TEXT | Broad scheme category, e.g. Equity or Debt. |
| `sub_category` | TEXT | Scheme investment sub-category. |
| `plan` | TEXT | Plan type, e.g. Direct or Regular. |
| `launch_date` | DATETIME | Scheme launch date. |
| `benchmark` | TEXT | Scheme benchmark index name. |
| `expense_ratio_pct` | REAL | Expense ratio in percentage points (e.g. 0.66 means 0.66%). |
| `exit_load_pct` | REAL | Exit load in percentage points. |
| `min_sip_amount` | INTEGER | Minimum SIP contribution in INR. |
| `min_lumpsum_amount` | INTEGER | Minimum lump-sum investment in INR. |
| `fund_manager` | TEXT | Named scheme manager in the source. |
| `risk_category` | TEXT | Source risk category/grade. |
| `sebi_category_code` | TEXT | Source SEBI category code. |

### `nav_history` — `02_nav_history.csv` (46,000 source rows; 64,320 cleaned rows)

Source: `02_nav_history.csv`; loaded to `src_nav_history`. Rows are sorted by
scheme and date, deduplicated on `(amfi_code, date)`, filtered to positive NAV,
then reindexed to every calendar day within each scheme's own observed date
range. Missing holiday/weekend dates carry the last available NAV forward;
this creates 18,320 additional calendar-day rows.

| Column | Type | Business definition |
|---|---|---|
| `amfi_code` | INTEGER | AMFI scheme identifier; joins to fund master. |
| `date` | DATETIME | NAV observation date, including forward-filled calendar days. |
| `nav` | REAL | Net asset value; cleaned value is strictly positive. |

### `aum_by_fund_house` — `03_aum_by_fund_house.csv` (90 rows)

Source: `03_aum_by_fund_house.csv`; loaded to `src_aum_by_fund_house`.

| Column | Type | Business definition |
|---|---|---|
| `date` | DATETIME | Fund-house AUM reporting date. |
| `fund_house` | TEXT | Asset management company / fund house. |
| `aum_lakh_crore` | REAL | Fund-house assets under management in lakh crore INR. |
| `aum_crore` | INTEGER | Fund-house assets under management in crore INR. |
| `num_schemes` | INTEGER | Number of schemes reported for the fund house. |

### `monthly_sip_inflows` — `04_monthly_sip_inflows.csv` (48 rows)

Source: `04_monthly_sip_inflows.csv`; loaded to `src_monthly_sip_inflows`.
Twelve missing `yoy_growth_pct` entries for Jan–Dec 2022 are retained because
the source has no prior-year comparison period.

| Column | Type | Business definition |
|---|---|---|
| `month` | TEXT (`YYYY-MM`) | Reporting month. |
| `sip_inflow_crore` | INTEGER | Monthly SIP contribution inflows in crore INR. |
| `active_sip_accounts_crore` | REAL | Active SIP accounts in crore. |
| `new_sip_accounts_lakh` | REAL | New SIP accounts in lakh. |
| `sip_aum_lakh_crore` | REAL | SIP AUM in lakh crore INR. |
| `yoy_growth_pct` | REAL | Source year-over-year SIP inflow growth percentage; null where unavailable. |

### `category_inflows` — `05_category_inflows.csv` (144 rows)

Source: `05_category_inflows.csv`; loaded to `src_category_inflows`.

| Column | Type | Business definition |
|---|---|---|
| `month` | TEXT (`YYYY-MM`) | Reporting month. |
| `category` | TEXT | Fund category as reported. |
| `net_inflow_crore` | REAL | Monthly category net inflow in crore INR. |

### `industry_folio_count` — `06_industry_folio_count.csv` (21 rows)

Source: `06_industry_folio_count.csv`; loaded to `src_industry_folio_count`.

| Column | Type | Business definition |
|---|---|---|
| `month` | TEXT (`YYYY-MM`) | Reporting month. |
| `total_folios_crore` | REAL | Industry total folios in crore. |
| `equity_folios_crore` | REAL | Equity folios in crore. |
| `debt_folios_crore` | REAL | Debt folios in crore. |
| `hybrid_folios_crore` | REAL | Hybrid folios in crore. |
| `others_folios_crore` | REAL | Other-category folios in crore. |

### `scheme_performance` — `07_scheme_performance.csv` (40 rows)

Source: `07_scheme_performance.csv`; loaded to `src_scheme_performance`.
Thirteen numeric performance fields are parsed and validated. `expense_ratio_pct`
is checked against the requested 0.1%–2.5% range (observed 0.55%–1.64%).
Three unusually high risk-adjusted-ratio rows are flagged in `anomaly_flags`;
they are preserved, not silently altered.

| Column | Type | Business definition |
|---|---|---|
| `amfi_code` | INTEGER | AMFI scheme identifier. |
| `scheme_name` | TEXT | Scheme display name. |
| `fund_house` | TEXT | Asset management company / fund house. |
| `category` | TEXT | Source performance category. |
| `plan` | TEXT | Plan type. |
| `return_1yr_pct` | REAL | One-year scheme return, percentage points. |
| `return_3yr_pct` | REAL | Three-year scheme return, percentage points. |
| `return_5yr_pct` | REAL | Five-year scheme return, percentage points. |
| `benchmark_3yr_pct` | REAL | Three-year benchmark return, percentage points. |
| `alpha` | REAL | Source risk-adjusted excess-return metric. |
| `beta` | REAL | Source market-sensitivity metric. |
| `sharpe_ratio` | REAL | Source Sharpe risk-adjusted return ratio. |
| `sortino_ratio` | REAL | Source Sortino downside-risk-adjusted return ratio. |
| `std_dev_ann_pct` | REAL | Annualized standard deviation, percentage points. |
| `max_drawdown_pct` | REAL | Maximum drawdown, percentage points (normally negative). |
| `aum_crore` | INTEGER | Scheme AUM in crore INR. |
| `expense_ratio_pct` | REAL | Scheme expense ratio in percentage points. |
| `morningstar_rating` | INTEGER | Source star rating. |
| `risk_grade` | TEXT | Source risk grade. |
| `anomaly_flags` | TEXT | Pipe-separated checks; blank means not flagged. Sharpe or Sortino above 3 is flagged for review. |

### `investor_transactions` — `08_investor_transactions.csv` (32,778 rows)

Source: `08_investor_transactions.csv`; loaded to `src_investor_transactions`.
Transaction types are standardized to `SIP`, `Lumpsum`, or `Redemption`;
KYC statuses are standardized to `Verified` or `Pending`. Non-numeric or
non-positive amounts are excluded; none required exclusion in this dataset.

| Column | Type | Business definition |
|---|---|---|
| `investor_id` | TEXT | Source investor identifier. |
| `transaction_date` | DATETIME | Transaction date, parsed and stored as ISO date. |
| `amfi_code` | INTEGER | AMFI scheme identifier. |
| `transaction_type` | TEXT | Standardized SIP, Lumpsum, or Redemption transaction. |
| `amount_inr` | INTEGER | Positive transaction amount in INR. |
| `state` | TEXT | Investor state. |
| `city` | TEXT | Investor city. |
| `city_tier` | TEXT | Source city-tier classification. |
| `age_group` | TEXT | Source investor age band. |
| `gender` | TEXT | Source gender classification. |
| `annual_income_lakh` | REAL | Source annual income in lakh INR. |
| `payment_mode` | TEXT | Source payment method. |
| `kyc_status` | TEXT | Standardized `Verified` or `Pending` status. |

### `portfolio_holdings` — `09_portfolio_holdings.csv` (322 rows)

Source: `09_portfolio_holdings.csv`; loaded to `src_portfolio_holdings`.

| Column | Type | Business definition |
|---|---|---|
| `amfi_code` | INTEGER | AMFI scheme identifier. |
| `stock_symbol` | TEXT | Portfolio security ticker/symbol. |
| `stock_name` | TEXT | Portfolio security name. |
| `sector` | TEXT | Source industry sector. |
| `weight_pct` | REAL | Portfolio weight in percentage points. |
| `market_value_cr` | REAL | Holding market value in crore INR. |
| `current_price_inr` | REAL | Source current security price in INR. |
| `portfolio_date` | DATETIME | Holdings snapshot date. |

### `benchmark_indices` — `10_benchmark_indices.csv` (8,050 rows)

Source: `10_benchmark_indices.csv`; loaded to `src_benchmark_indices`.

| Column | Type | Business definition |
|---|---|---|
| `date` | DATETIME | Benchmark index observation date. |
| `index_name` | TEXT | Benchmark/index name. |
| `close_value` | REAL | Closing index level. |

## SQLite star schema

The six dimensional/fact tables are defined in `schema.sql`. The source
snapshots above are additionally loaded into `src_<dataset>` tables to preserve
all 10 cleaned datasets. `day2_etl.py` verifies every source table against its
cleaned CSV row count and checks SQLite foreign-key integrity.

| Table | Column | Type | Definition / source |
|---|---|---|---|
| `dim_fund` | `amfi_code` | INTEGER | Primary key; `fund_master.amfi_code`. |
| `dim_fund` | `fund_house`, `scheme_name`, `category`, `sub_category`, `plan`, `launch_date`, `benchmark`, `expense_ratio_pct`, `exit_load_pct`, `min_sip_amount`, `min_lumpsum_amount`, `fund_manager`, `risk_category`, `sebi_category_code` | Same as corresponding `fund_master` columns | Descriptive fund attributes; definitions and types are in the fund master dictionary above. |
| `dim_date` | `date_key` | INTEGER | Primary key; calendar date as `YYYYMMDD`. |
| `dim_date` | `full_date` | TEXT | Unique ISO date. |
| `dim_date` | `year`, `quarter`, `month`, `day` | INTEGER | Calendar parts of `full_date`. |
| `dim_date` | `month_name`, `day_of_week` | TEXT | English calendar labels. |
| `dim_date` | `is_weekend` | INTEGER | 1 for Saturday/Sunday, otherwise 0. |
| `fact_nav` | `amfi_code` | INTEGER | Fund foreign key to `dim_fund`. |
| `fact_nav` | `date_key` | INTEGER | Date foreign key to `dim_date`. |
| `fact_nav` | `nav` | REAL | Positive daily NAV from cleaned `nav_history`. Composite primary key is `(amfi_code, date_key)`. |
| `fact_transactions` | `transaction_id` | INTEGER | Generated fact-table row key; not a source transaction identifier. |
| `fact_transactions` | `investor_id`, `transaction_type`, `amount_inr`, `state`, `city`, `city_tier`, `age_group`, `gender`, `annual_income_lakh`, `payment_mode`, `kyc_status` | Same as corresponding `investor_transactions` columns | Cleaned transaction attributes; definitions and types are in the transaction dictionary above. |
| `fact_transactions` | `amfi_code` | INTEGER | Foreign key to `dim_fund`. |
| `fact_transactions` | `date_key` | INTEGER | Transaction date foreign key to `dim_date`. |
| `fact_performance` | `amfi_code` | INTEGER | Primary key and foreign key to `dim_fund`. |
| `fact_performance` | `return_1yr_pct`, `return_3yr_pct`, `return_5yr_pct`, `benchmark_3yr_pct`, `alpha`, `beta`, `sharpe_ratio`, `sortino_ratio`, `std_dev_ann_pct`, `max_drawdown_pct`, `aum_crore`, `expense_ratio_pct`, `morningstar_rating`, `anomaly_flags` | Same as corresponding `scheme_performance` columns | Scheme snapshot metrics and quality flags; definitions and types are in the performance dictionary above. No as-of date is fabricated because none is present in the source. |
| `fact_aum` | `date_key` | INTEGER | Reporting date foreign key to `dim_date`. |
| `fact_aum` | `fund_house` | TEXT | Fund-house label (degenerate dimension; no fund-house dimension was requested or supplied). |
| `fact_aum` | `aum_lakh_crore`, `aum_crore`, `num_schemes` | Same as corresponding `aum_by_fund_house` columns | Reported fund-house AUM and scheme count. Composite primary key is `(date_key, fund_house)`. |

### Relationships and grain

- `dim_fund` 1-to-many `fact_nav`, `fact_transactions`, and
  `fact_performance`.
- `dim_date` 1-to-many `fact_nav`, `fact_transactions`, and `fact_aum`.
- `fact_nav` grain: one fund per calendar date; weekend/holiday NAVs are
  carried forward from the latest preceding observation.
- `fact_transactions` grain: one source transaction row. Its integer
  `transaction_id` is generated during load.
- `fact_performance` grain: one source performance snapshot per fund; the
  source supplies no performance as-of date.
- `fact_aum` grain: one fund house per reporting date. This measure is
  fund-house-level, not scheme-level; scheme-level AUM comes from
  `fact_performance`.
