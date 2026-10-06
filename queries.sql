-- 1. Top five schemes by reported scheme-level AUM (source: performance snapshot).
SELECT f.amfi_code, f.scheme_name, f.fund_house, p.aum_crore
FROM fact_performance AS p
JOIN dim_fund AS f USING (amfi_code)
ORDER BY p.aum_crore DESC
LIMIT 5;

-- 2. Monthly average NAV across the available schemes and daily observations.
SELECT strftime('%Y-%m', d.full_date) AS month,
       ROUND(AVG(n.nav), 4) AS average_nav,
       COUNT(*) AS scheme_day_observations
FROM fact_nav AS n
JOIN dim_date AS d USING (date_key)
GROUP BY strftime('%Y-%m', d.full_date)
ORDER BY month;

-- 3. Recomputed SIP inflow year-over-year growth; the first available year is NULL.
WITH monthly AS (
    SELECT month, sip_inflow_crore,
           LAG(sip_inflow_crore, 12) OVER (ORDER BY month) AS prior_year_inflow
    FROM src_monthly_sip_inflows
)
SELECT month, sip_inflow_crore, prior_year_inflow,
       ROUND(100.0 * (sip_inflow_crore * 1.0 / NULLIF(prior_year_inflow, 0) - 1), 2)
           AS calculated_yoy_growth_pct
FROM monthly
ORDER BY month;

-- 4. Transaction volume and value by investor state.
SELECT state, COUNT(*) AS transaction_count,
       SUM(amount_inr) AS total_amount_inr,
       ROUND(AVG(amount_inr), 2) AS average_amount_inr
FROM fact_transactions
GROUP BY state
ORDER BY total_amount_inr DESC;

-- 5. Funds with a master-record expense ratio below one percent.
SELECT amfi_code, scheme_name, fund_house, plan, expense_ratio_pct
FROM dim_fund
WHERE expense_ratio_pct < 1.0
ORDER BY expense_ratio_pct, scheme_name;

-- 6. Schemes whose three-year return exceeded their reported benchmark.
SELECT f.scheme_name, f.fund_house, p.return_3yr_pct,
       p.benchmark_3yr_pct, ROUND(p.return_3yr_pct - p.benchmark_3yr_pct, 2) AS excess_return_pct
FROM fact_performance AS p
JOIN dim_fund AS f USING (amfi_code)
WHERE p.return_3yr_pct > p.benchmark_3yr_pct
ORDER BY excess_return_pct DESC;

-- 7. AUM and change from the previous reporting period by fund house.
WITH aum_series AS (
    SELECT date(d.full_date) AS full_date, a.fund_house, a.aum_crore,
           LAG(a.aum_crore) OVER (PARTITION BY a.fund_house ORDER BY d.full_date) AS prior_aum_crore
    FROM fact_aum AS a
    JOIN dim_date AS d USING (date_key)
)
SELECT full_date, fund_house, aum_crore,
       aum_crore - prior_aum_crore AS change_crore,
       ROUND(100.0 * (aum_crore * 1.0 / NULLIF(prior_aum_crore, 0) - 1), 2) AS change_pct
FROM aum_series
ORDER BY fund_house, full_date;

-- 8. Transaction count and invested/redeemed value by transaction type.
SELECT transaction_type, COUNT(*) AS transaction_count,
       SUM(amount_inr) AS total_amount_inr,
       ROUND(AVG(amount_inr), 2) AS average_amount_inr
FROM fact_transactions
GROUP BY transaction_type
ORDER BY total_amount_inr DESC;

-- 9. Most recent NAV observation in the cleaned daily calendar for every scheme.
WITH ranked_nav AS (
    SELECT n.amfi_code, date(d.full_date) AS full_date, n.nav,
           ROW_NUMBER() OVER (PARTITION BY n.amfi_code ORDER BY d.full_date DESC) AS row_num
    FROM fact_nav AS n
    JOIN dim_date AS d USING (date_key)
)
SELECT f.amfi_code, f.scheme_name, r.full_date AS nav_date, r.nav
FROM ranked_nav AS r
JOIN dim_fund AS f USING (amfi_code)
WHERE r.row_num = 1
ORDER BY f.scheme_name;

-- 10. Average one-, three-, and five-year returns by fund category.
SELECT f.category, COUNT(*) AS scheme_count,
       ROUND(AVG(p.return_1yr_pct), 2) AS average_1yr_return_pct,
       ROUND(AVG(p.return_3yr_pct), 2) AS average_3yr_return_pct,
       ROUND(AVG(p.return_5yr_pct), 2) AS average_5yr_return_pct
FROM fact_performance AS p
JOIN dim_fund AS f USING (amfi_code)
GROUP BY f.category
ORDER BY average_3yr_return_pct DESC;
