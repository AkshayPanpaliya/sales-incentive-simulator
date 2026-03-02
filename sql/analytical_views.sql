-- =============================================================================
-- Sales Incentive Simulator – Analytical Views
-- =============================================================================
-- All views use CREATE VIEW IF NOT EXISTS for idempotent execution.
-- Window functions (RANK, LAG, NTILE, PERCENT_RANK, SUM OVER) require
-- SQLite ≥ 3.25.0 (shipped with Python 3.8+).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- View 1: rep_performance_summary
-- Each rep's aggregated performance metrics with intra-region and intra-role
-- ranking and an overall percentile rank.
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS rep_performance_summary AS
SELECT
    r.rep_id,
    r.rep_name,
    r.region,
    r.role,
    r.quota,
    COALESCE(SUM(t.deal_amount), 0)                               AS total_sales,
    ROUND(COALESCE(SUM(t.deal_amount), 0) / r.quota * 100, 2)    AS attainment_pct,
    COUNT(t.transaction_id)                                        AS deal_count,
    ROUND(AVG(t.deal_amount), 2)                                  AS avg_deal_size,
    RANK() OVER (
        PARTITION BY r.region
        ORDER BY COALESCE(SUM(t.deal_amount), 0) DESC
    )                                                              AS region_rank,
    RANK() OVER (
        PARTITION BY r.role
        ORDER BY COALESCE(SUM(t.deal_amount), 0) DESC
    )                                                              AS role_rank,
    ROUND(
        PERCENT_RANK() OVER (
            ORDER BY COALESCE(SUM(t.deal_amount), 0) DESC
        ) * 100, 2
    )                                                              AS percentile_rank
FROM sales_reps r
LEFT JOIN sales_transactions t ON r.rep_id = t.rep_id
GROUP BY r.rep_id, r.rep_name, r.region, r.role, r.quota;

-- -----------------------------------------------------------------------------
-- View 2: monthly_payout_trend
-- Monthly revenue and deal counts segmented by region and role.
-- Includes cumulative revenue (running total) and month-over-month growth.
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS monthly_payout_trend AS
WITH monthly_sales AS (
    SELECT
        strftime('%Y-%m', t.deal_date) AS month,
        r.region,
        r.role,
        SUM(t.deal_amount)             AS monthly_revenue,
        COUNT(t.transaction_id)        AS deal_count
    FROM  sales_transactions t
    JOIN  sales_reps r ON t.rep_id = r.rep_id
    GROUP BY
        strftime('%Y-%m', t.deal_date),
        r.region,
        r.role
)
SELECT
    month,
    region,
    role,
    monthly_revenue,
    deal_count,
    SUM(monthly_revenue) OVER (
        PARTITION BY region
        ORDER BY month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                          AS cumulative_revenue,
    LAG(monthly_revenue, 1) OVER (
        PARTITION BY region, role
        ORDER BY month
    )                                                          AS prev_month_revenue,
    ROUND(
        (
            monthly_revenue
            - LAG(monthly_revenue, 1) OVER (
                PARTITION BY region, role
                ORDER BY month
              )
        )
        / NULLIF(
            LAG(monthly_revenue, 1) OVER (
                PARTITION BY region, role
                ORDER BY month
            ),
            0
          ) * 100,
        2
    )                                                          AS mom_growth_pct
FROM monthly_sales;

-- -----------------------------------------------------------------------------
-- View 3: region_wise_efficiency
-- Region-level aggregations: total quota, total revenue, overall attainment,
-- average per-rep attainment, and the proportion of reps above quota.
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS region_wise_efficiency AS
SELECT
    r.region,
    COUNT(DISTINCT r.rep_id)                                              AS rep_count,
    SUM(r.quota)                                                          AS total_quota,
    COALESCE(SUM(t.deal_amount), 0)                                       AS total_revenue,
    ROUND(COALESCE(SUM(t.deal_amount), 0) / SUM(r.quota) * 100, 2)       AS region_attainment_pct,
    ROUND(
        AVG(COALESCE(sub.rep_total, 0) / r.quota * 100),
        2
    )                                                                      AS avg_rep_attainment_pct,
    COUNT(
        CASE WHEN COALESCE(sub.rep_total, 0) >= r.quota THEN 1 END
    )                                                                      AS reps_above_quota,
    ROUND(
        COUNT(CASE WHEN COALESCE(sub.rep_total, 0) >= r.quota THEN 1 END)
        * 100.0 / COUNT(r.rep_id),
        2
    )                                                                      AS pct_reps_above_quota
FROM  sales_reps r
LEFT JOIN (
    SELECT rep_id, SUM(deal_amount) AS rep_total
    FROM   sales_transactions
    GROUP BY rep_id
) sub ON r.rep_id = sub.rep_id
LEFT JOIN sales_transactions t ON r.rep_id = t.rep_id
GROUP BY r.region;

-- -----------------------------------------------------------------------------
-- View 4: over_quota_analysis
-- Rep-level attainment with performance-band labelling, quartile segmentation,
-- and a cross-reference to the calculated payout for cost-of-sales analysis.
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS over_quota_analysis AS
WITH rep_sales AS (
    SELECT
        rep_id,
        SUM(deal_amount) AS total_sales,
        COUNT(*)         AS deal_count
    FROM  sales_transactions
    GROUP BY rep_id
)
SELECT
    r.rep_id,
    r.rep_name,
    r.region,
    r.role,
    r.quota,
    COALESCE(rs.total_sales, 0)                                 AS total_sales,
    ROUND(COALESCE(rs.total_sales, 0) / r.quota * 100, 2)      AS attainment_pct,
    CASE
        WHEN COALESCE(rs.total_sales, 0) / r.quota >= 1.5 THEN 'High Risk – 150%+'
        WHEN COALESCE(rs.total_sales, 0) / r.quota >= 1.0 THEN 'Above Quota'
        WHEN COALESCE(rs.total_sales, 0) / r.quota >= 0.5 THEN 'On Track'
        ELSE                                                         'At Risk'
    END                                                          AS performance_band,
    NTILE(4) OVER (
        ORDER BY COALESCE(rs.total_sales, 0) / r.quota DESC
    )                                                            AS quartile,
    pr.total_payout,
    pr.payout_to_revenue_ratio
FROM  sales_reps r
LEFT JOIN rep_sales    rs ON r.rep_id = rs.rep_id
LEFT JOIN payout_results pr ON r.rep_id = pr.rep_id;
