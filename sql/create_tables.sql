-- =============================================================================
-- Sales Incentive Simulator – Table Definitions
-- Database : SQLite (compatible with PostgreSQL with minor dialect changes)
-- =============================================================================
-- All tables use IF NOT EXISTS so this script is safely idempotent.
-- Foreign-key enforcement is activated by the application layer via:
--   PRAGMA foreign_keys = ON;
-- =============================================================================

-- -----------------------------------------------------------------------------
-- sales_reps
-- Master table of sales representatives.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_reps (
    rep_id      INTEGER PRIMARY KEY,
    rep_name    TEXT    NOT NULL,
    region      TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    quota       REAL    NOT NULL CHECK (quota > 0),
    hire_date   TEXT    NOT NULL   -- ISO-8601: YYYY-MM-DD
);

-- -----------------------------------------------------------------------------
-- sales_transactions
-- Individual closed-won deal records.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_transactions (
    transaction_id   INTEGER PRIMARY KEY,
    rep_id           INTEGER NOT NULL,
    deal_date        TEXT    NOT NULL,   -- ISO-8601: YYYY-MM-DD
    deal_amount      REAL    NOT NULL CHECK (deal_amount >= 0),
    product_category TEXT    NOT NULL,
    customer_segment TEXT    NOT NULL,
    FOREIGN KEY (rep_id) REFERENCES sales_reps (rep_id)
);

-- Index to speed up rep-level aggregations used in every analytical view.
CREATE INDEX IF NOT EXISTS idx_transactions_rep_id
    ON sales_transactions (rep_id);

-- Index to support time-series queries by month / quarter.
CREATE INDEX IF NOT EXISTS idx_transactions_deal_date
    ON sales_transactions (deal_date);

-- -----------------------------------------------------------------------------
-- incentive_plan
-- Reference table describing the commission tiers per role.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incentive_plan (
    plan_id          INTEGER PRIMARY KEY,
    role             TEXT    NOT NULL,
    threshold_min    REAL    NOT NULL CHECK (threshold_min >= 0),
    threshold_max    REAL    NOT NULL,
    commission_rate  REAL    NOT NULL CHECK (commission_rate BETWEEN 0 AND 1),
    accelerator_rate REAL    NOT NULL CHECK (accelerator_rate BETWEEN 0 AND 1),
    effective_from   TEXT    NOT NULL   -- ISO-8601: YYYY-MM-DD
);

-- -----------------------------------------------------------------------------
-- calendar
-- Date-dimension table pre-populated with time-intelligence attributes.
-- Used as the authoritative time axis for all time-series analysis.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calendar (
    date           TEXT    PRIMARY KEY,  -- ISO-8601: YYYY-MM-DD
    year           INTEGER NOT NULL,
    quarter        INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month          INTEGER NOT NULL CHECK (month  BETWEEN 1 AND 12),
    month_name     TEXT    NOT NULL,
    week           INTEGER NOT NULL,
    day_of_week    TEXT    NOT NULL,
    is_weekend     INTEGER NOT NULL CHECK (is_weekend  IN (0, 1)),
    is_month_end   INTEGER NOT NULL CHECK (is_month_end IN (0, 1)),
    is_quarter_end INTEGER NOT NULL CHECK (is_quarter_end IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- payout_results
-- Calculated payout output produced by the incentive engine.
-- Refreshed each time main.py is executed.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payout_results (
    rep_id                  INTEGER PRIMARY KEY,
    rep_name                TEXT,
    region                  TEXT,
    role                    TEXT,
    total_sales             REAL,
    quota                   REAL,
    attainment_pct          REAL,
    base_commission         REAL,
    accelerator_bonus       REAL,
    total_payout            REAL,
    payout_to_revenue_ratio REAL,
    FOREIGN KEY (rep_id) REFERENCES sales_reps (rep_id)
);
