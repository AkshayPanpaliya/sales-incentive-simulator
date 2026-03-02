-- =============================================================================
-- Sales Incentive Simulator – Data Load Reference Script
-- =============================================================================
-- NOTE: In this project all data loading is performed programmatically by
-- src/db_utils.py using pandas.DataFrame.to_sql().  This script serves as:
--   1. A human-readable specification of the load order and PRAGMA settings.
--   2. A template for manual / migration loads outside of Python.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- SQLite Performance PRAGMAs
-- These settings dramatically improve bulk-insert throughput.
-- ---------------------------------------------------------------------------
PRAGMA journal_mode = WAL;        -- Write-Ahead Logging: concurrent reads OK
PRAGMA synchronous  = NORMAL;     -- Safe balance between speed and durability
PRAGMA foreign_keys = ON;         -- Enforce referential integrity
PRAGMA cache_size   = -64000;     -- Use 64 MB page cache (negative = kibibytes)
PRAGMA temp_store   = MEMORY;     -- Store temp tables in memory

-- ---------------------------------------------------------------------------
-- Load order
-- Tables must be loaded in dependency order to satisfy FK constraints.
-- ---------------------------------------------------------------------------
--  1. calendar          (no FK dependencies)
--  2. sales_reps        (no FK dependencies)
--  3. incentive_plan    (no FK dependencies)
--  4. sales_transactions REFERENCES sales_reps(rep_id)
--  5. payout_results    REFERENCES sales_reps(rep_id)

-- ---------------------------------------------------------------------------
-- Template INSERT (illustrative – values supplied by Python in practice)
-- ---------------------------------------------------------------------------

-- sales_reps
-- INSERT INTO sales_reps (rep_id, rep_name, region, role, quota, hire_date)
-- VALUES
--   (1, 'Alice Johnson', 'North America', 'Enterprise AE', 1050000, '2021-03-15'),
--   (2, 'Bob Martinez',  'EMEA',          'Mid-Market AE',  550000, '2020-07-22');

-- sales_transactions
-- INSERT INTO sales_transactions
--   (transaction_id, rep_id, deal_date, deal_amount, product_category, customer_segment)
-- VALUES
--   (1, 1, '2024-02-14', 125000.00, 'Enterprise Software', 'Enterprise'),
--   (2, 1, '2024-05-01',  87500.00, 'Cloud Services',      'Mid-Market');

-- incentive_plan
-- INSERT INTO incentive_plan
--   (plan_id, role, threshold_min, threshold_max, commission_rate, accelerator_rate, effective_from)
-- VALUES
--   (1, 'Enterprise AE', 0.0, 0.5,   0.02, 0.15, '2024-01-01'),
--   (2, 'Enterprise AE', 0.5, 1.0,   0.05, 0.15, '2024-01-01'),
--   (3, 'Enterprise AE', 1.0, 1.5,   0.08, 0.15, '2024-01-01'),
--   (4, 'Enterprise AE', 1.5, 999.0, 0.12, 0.15, '2024-01-01');

-- payout_results
-- INSERT INTO payout_results
--   (rep_id, rep_name, region, role, total_sales, quota, attainment_pct,
--    base_commission, accelerator_bonus, total_payout, payout_to_revenue_ratio)
-- VALUES
--   (1, 'Alice Johnson', 'North America', 'Enterprise AE',
--    1260000.00, 1050000.00, 1.2,
--    63000.00, 31500.00, 94500.00, 0.075);

-- ---------------------------------------------------------------------------
-- Post-load integrity check (run manually to verify load)
-- ---------------------------------------------------------------------------
-- SELECT
--   'sales_reps'         AS tbl, COUNT(*) AS row_count FROM sales_reps
-- UNION ALL SELECT 'sales_transactions', COUNT(*) FROM sales_transactions
-- UNION ALL SELECT 'incentive_plan',     COUNT(*) FROM incentive_plan
-- UNION ALL SELECT 'calendar',           COUNT(*) FROM calendar
-- UNION ALL SELECT 'payout_results',     COUNT(*) FROM payout_results;
