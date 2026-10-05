# Day 1 data quality summary

## Supplied source datasets

All 10 CSVs from `Datasets/` were copied to `data/raw/` and profiled with
`data_ingestion.py`. Shape, dtype, and the first five records for each file
were printed. The schemas are:

| File | Shape |
|---|---:|
| `01_fund_master.csv` | 40 x 15 |
| `02_nav_history.csv` | 46,000 x 3 |
| `03_aum_by_fund_house.csv` | 90 x 5 |
| `04_monthly_sip_inflows.csv` | 48 x 6 |
| `05_category_inflows.csv` | 144 x 3 |
| `06_industry_folio_count.csv` | 21 x 6 |
| `07_scheme_performance.csv` | 40 x 19 |
| `08_investor_transactions.csv` | 32,778 x 13 |
| `09_portfolio_holdings.csv` | 322 x 8 |
| `10_benchmark_indices.csv` | 8,050 x 3 |

One anomaly was flagged: `04_monthly_sip_inflows.csv` has 12 null values in
`yoy_growth_pct`, for every month from 2022-01 through 2022-12. Other basic
checks found no missing cells, duplicate rows, or empty files in the supplied
CSV datasets.

## Fund master

- Fund houses (10): Aditya Birla Sun Life MF, Axis Mutual Fund, DSP Mutual
  Fund, HDFC Mutual Fund, ICICI Prudential MF, Kotak Mahindra MF, Mirae Asset
  MF, Nippon India MF, SBI Mutual Fund, UTI Mutual Fund.
- Categories: Debt, Equity.
- Sub-categories (12): ELSS, Flexi Cap, Gilt, Index, Index/ETF, Large & Mid
  Cap, Large Cap, Liquid, Mid Cap, Short Duration, Small Cap, Value.
- Risk grades: High, Low, Moderate, Moderately High, Very High.

## AMFI scheme-code validation

Both the fund master and NAV history have 40 unique AMFI codes. All 40
fund-master codes occur in NAV history; there are no missing master codes.
The observed codes are six-digit numeric identifiers ranging from 100016 to
149324. The data supports treating them as opaque lookup identifiers; their
numeric format alone does not demonstrate that their digits encode the fund
house, category, or other scheme attributes.

## Live MFAPI NAV fetch

`live_nav_fetch.py` fetched six intended large-cap schemes, saving raw NAV CSVs
to `data/raw/live_nav/`. MFAPI metadata was verified for each code:

| Scheme | Code | NAV records |
|---|---:|---:|
| HDFC Large Cap Fund - Direct Plan - Growth Option | 119018 | 3,385 |
| SBI Large Cap Fund - Direct Plan - Growth | 119598 | 3,393 |
| ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund) - Direct Plan - Growth | 120586 | 3,384 |
| Nippon India Large Cap Fund - Direct Plan - Growth Option | 118632 | 3,384 |
| Axis Large Cap Fund - Direct Plan - Growth Option | 120465 | 3,393 |
| Kotak Large Cap Fund - Direct Plan - Growth | 120152 | 3,383 |

The five other codes from the initial request (125497, 119551, 120503, 119092,
120841) were also queried and their returned NAV CSVs are retained in
`data/raw/live_nav/`. MFAPI identified those codes as different schemes than
the originally supplied labels. The fetch script uses the user-approved,
verified codes above; each output CSV stores the API scheme name and requested
label separately.
