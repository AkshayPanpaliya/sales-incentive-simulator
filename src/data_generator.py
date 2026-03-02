"""
data_generator.py
-----------------
Generates realistic synthetic data for the Sales Incentive Simulator.

Creates:
* 100 sales reps  – spanning 4 regions and 5 roles with role-specific quotas.
* 12,000+ sales transactions – log-normally distributed deal amounts varying by
  role, dated throughout 2024.
* Incentive plan reference data – one row per role per commission tier.
* A calendar / date-dimension table – every day of 2024 with time-intelligence
  attributes needed by analytical views and Power BI.

All generators accept a *seed* argument so results are fully reproducible.

Usage
-----
>>> from src.data_generator import generate_all_data
>>> datasets = generate_all_data(output_dir="data/", seed=42)
>>> datasets.keys()
dict_keys(['sales_reps', 'transactions', 'incentive_plan', 'calendar'])
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

from src.config_loader import load_config
from src.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Role distribution weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_ROLE_WEIGHTS: dict[str, float] = {
    "Enterprise AE": 0.30,
    "Mid-Market AE": 0.25,
    "SMB AE": 0.25,
    "SDR": 0.10,
    "Sales Manager": 0.10,
}

# Deal-amount log-normal scale factor per role.
# These multipliers are applied to the base mean so that Enterprise AEs close
# much larger deals than SDRs, reflecting real-world distributions.
_ROLE_DEAL_MULTIPLIER: dict[str, float] = {
    "Enterprise AE": 3.0,
    "Mid-Market AE": 1.5,
    "SMB AE": 0.7,
    "SDR": 0.4,
    "Sales Manager": 2.5,
}

_BASE_DEAL_MEAN: float = 45_000.0   # target mean deal amount across all reps
_DEAL_LOG_SIGMA: float = 0.8        # log-normal shape parameter


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------


def generate_sales_reps(n_reps: int = 100, seed: int = 42) -> pd.DataFrame:
    """
    Generate a DataFrame of synthetic sales representatives.

    Parameters
    ----------
    n_reps : int
        Total number of sales reps to generate (default 100).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: rep_id, rep_name, region, role, quota, hire_date.
    """
    config = load_config()
    rng = np.random.default_rng(seed)
    fake = Faker()
    Faker.seed(seed)

    roles = list(_ROLE_WEIGHTS.keys())
    weights = list(_ROLE_WEIGHTS.values())

    assigned_roles: list[str] = list(
        rng.choice(roles, size=n_reps, p=weights)
    )
    regions: list[str] = config["regions"]
    assigned_regions: list[str] = list(
        rng.choice(regions, size=n_reps)
    )

    quotas: list[float] = []
    for role in assigned_roles:
        q_min = config["roles"][role]["quota_min"]
        q_max = config["roles"][role]["quota_max"]
        # Round to nearest $5,000 to look realistic
        raw = rng.integers(q_min, q_max, endpoint=True)
        quotas.append(int(round(raw / 5_000) * 5_000))

    # Hire dates uniformly distributed between 2019-01-01 and 2023-12-31
    start_ord = pd.Timestamp("2019-01-01").toordinal()
    end_ord = pd.Timestamp("2023-12-31").toordinal()
    hire_ordinals = rng.integers(start_ord, end_ord, size=n_reps)
    hire_dates: list[str] = [
        pd.Timestamp.fromordinal(int(o)).strftime("%Y-%m-%d")
        for o in hire_ordinals
    ]

    df = pd.DataFrame(
        {
            "rep_id": range(1, n_reps + 1),
            "rep_name": [fake.name() for _ in range(n_reps)],
            "region": assigned_regions,
            "role": assigned_roles,
            "quota": quotas,
            "hire_date": hire_dates,
        }
    )

    _validate_no_nulls(df, ["rep_id", "rep_name", "region", "role", "quota", "hire_date"])
    logger.info("Generated %d sales reps across %d regions.", n_reps, len(regions))
    return df


def generate_transactions(
    sales_reps_df: pd.DataFrame,
    n_transactions: int = 12_000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a DataFrame of synthetic sales transactions.

    Deal amounts follow a log-normal distribution with per-role multipliers so
    that Enterprise AEs and Sales Managers close materially larger deals than
    SMB AEs or SDRs.

    Parameters
    ----------
    sales_reps_df : pd.DataFrame
        Output of :func:`generate_sales_reps`.
    n_transactions : int
        Number of transactions to generate (default 12,000).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: transaction_id, rep_id, deal_date, deal_amount,
                 product_category, customer_segment.
    """
    config = load_config()
    rng = np.random.default_rng(seed)

    rep_ids: np.ndarray = sales_reps_df["rep_id"].values
    rep_roles: dict[int, str] = dict(
        zip(sales_reps_df["rep_id"], sales_reps_df["role"])
    )

    # Assign each transaction to a rep (uniform distribution)
    assigned_rep_ids: np.ndarray = rng.choice(rep_ids, size=n_transactions)

    # Build per-transaction deal amounts vectorised by role multiplier
    multipliers = np.array(
        [_ROLE_DEAL_MULTIPLIER.get(rep_roles[rid], 1.0) for rid in assigned_rep_ids]
    )
    log_means = np.log(_BASE_DEAL_MEAN * multipliers) - 0.5 * _DEAL_LOG_SIGMA ** 2
    deal_amounts: np.ndarray = np.exp(
        rng.normal(loc=log_means, scale=_DEAL_LOG_SIGMA)
    )
    # Minimum deal of $500 to avoid unrealistic tiny numbers
    deal_amounts = np.maximum(deal_amounts, 500.0).round(2)

    # Random deal dates spread across the full year 2024
    start_ts = pd.Timestamp("2024-01-01")
    end_ts = pd.Timestamp("2024-12-31")
    total_days = (end_ts - start_ts).days + 1
    day_offsets = rng.integers(0, total_days, size=n_transactions)
    deal_dates: list[str] = [
        (start_ts + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d")
        for d in day_offsets
    ]

    product_categories: list[str] = config["product_categories"]
    customer_segments: list[str] = config["customer_segments"]

    assigned_products: list[str] = list(
        rng.choice(product_categories, size=n_transactions)
    )
    assigned_segments: list[str] = list(
        rng.choice(customer_segments, size=n_transactions)
    )

    df = pd.DataFrame(
        {
            "transaction_id": range(1, n_transactions + 1),
            "rep_id": assigned_rep_ids,
            "deal_date": deal_dates,
            "deal_amount": deal_amounts,
            "product_category": assigned_products,
            "customer_segment": assigned_segments,
        }
    )

    _validate_no_nulls(
        df,
        ["transaction_id", "rep_id", "deal_date", "deal_amount",
         "product_category", "customer_segment"],
    )
    _validate_fk_integrity(df, sales_reps_df)
    logger.info(
        "Generated %d transactions. Total revenue: $%,.0f.",
        n_transactions,
        df["deal_amount"].sum(),
    )
    return df


def generate_incentive_plan(config: dict[str, Any] | None = None) -> pd.DataFrame:
    """
    Generate a reference DataFrame of incentive-plan records.

    One row is created for every (role, tier) combination, giving analysts a
    normalised view of the compensation structure.

    Parameters
    ----------
    config : dict or None
        Parsed incentive-plan configuration.  Loaded automatically if *None*.

    Returns
    -------
    pd.DataFrame
        Columns: plan_id, role, threshold_min, threshold_max,
                 commission_rate, accelerator_rate, effective_from.
    """
    if config is None:
        config = load_config()

    tiers: list[dict] = config["tiers"]
    accel_rate: float = config["accelerator"]["rate"]
    effective_from: str = config["effective_from"]
    roles: list[str] = list(config["roles"].keys())

    records: list[dict] = []
    plan_id: int = 1
    for role in roles:
        for tier in tiers:
            records.append(
                {
                    "plan_id": plan_id,
                    "role": role,
                    "threshold_min": tier["threshold_min"],
                    "threshold_max": tier["threshold_max"],
                    "commission_rate": tier["commission_rate"],
                    "accelerator_rate": accel_rate,
                    "effective_from": effective_from,
                }
            )
            plan_id += 1

    df = pd.DataFrame(records)
    logger.info(
        "Generated incentive plan: %d role-tier combinations.", len(df)
    )
    return df


def generate_calendar(
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
) -> pd.DataFrame:
    """
    Generate a calendar / date-dimension table.

    This table is the standard «date dimension» used in star-schema models.
    Every row represents a single calendar day with pre-computed time-
    intelligence attributes that eliminate the need for expensive run-time
    calculations in SQL or DAX.

    Parameters
    ----------
    start_date : str
        ISO-formatted start date (inclusive), default ``"2024-01-01"``.
    end_date : str
        ISO-formatted end date (inclusive), default ``"2024-12-31"``.

    Returns
    -------
    pd.DataFrame
        Columns: date, year, quarter, month, month_name, week,
                 day_of_week, is_weekend, is_month_end, is_quarter_end.
    """
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")

    df = pd.DataFrame(
        {
            "date": date_range.strftime("%Y-%m-%d"),
            "year": date_range.year,
            "quarter": date_range.quarter,
            "month": date_range.month,
            "month_name": date_range.strftime("%B"),
            "week": date_range.isocalendar().week.astype(int),
            "day_of_week": date_range.strftime("%A"),
            "is_weekend": (date_range.dayofweek >= 5).astype(int),
            "is_month_end": date_range.is_month_end.astype(int),
            "is_quarter_end": date_range.is_quarter_end.astype(int),
        }
    )

    logger.info(
        "Generated calendar from %s to %s (%d days).",
        start_date,
        end_date,
        len(df),
    )
    return df


def generate_all_data(
    output_dir: str = "data/",
    seed: int = 42,
) -> dict[str, pd.DataFrame]:
    """
    Orchestrate all data generators and persist results as CSV files.

    Parameters
    ----------
    output_dir : str
        Directory where CSV files will be written.  Created if absent.
    seed : int
        Master random seed propagated to each individual generator.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys: ``"sales_reps"``, ``"transactions"``, ``"incentive_plan"``,
              ``"calendar"``.
    """
    os.makedirs(output_dir, exist_ok=True)
    config = load_config()

    logger.info("=== Starting full data generation (seed=%d) ===", seed)

    sales_reps = generate_sales_reps(n_reps=100, seed=seed)
    transactions = generate_transactions(sales_reps, n_transactions=12_000, seed=seed)
    incentive_plan = generate_incentive_plan(config)
    calendar = generate_calendar()

    datasets: dict[str, pd.DataFrame] = {
        "sales_reps": sales_reps,
        "transactions": transactions,
        "incentive_plan": incentive_plan,
        "calendar": calendar,
    }

    for name, df in datasets.items():
        csv_path = os.path.join(output_dir, f"{name}.csv")
        df.to_csv(csv_path, index=False)
        logger.info("Saved '%s' → %s (%d rows).", name, csv_path, len(df))

    logger.info("=== Data generation complete. ===")
    return datasets


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------


def _validate_no_nulls(df: pd.DataFrame, columns: list[str]) -> None:
    """
    Raise *ValueError* if any of *columns* contain null / NaN values.
    """
    for col in columns:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise ValueError(
                f"Data quality failure: column '{col}' contains {null_count} "
                "null value(s).  Check generator logic."
            )


def _validate_fk_integrity(
    transactions_df: pd.DataFrame,
    sales_reps_df: pd.DataFrame,
) -> None:
    """
    Raise *ValueError* if any ``rep_id`` in *transactions_df* is not present
    in *sales_reps_df* (foreign-key violation).
    """
    valid_ids: set[int] = set(sales_reps_df["rep_id"].tolist())
    orphan_ids = set(transactions_df["rep_id"].tolist()) - valid_ids
    if orphan_ids:
        raise ValueError(
            f"FK integrity failure: {len(orphan_ids)} transaction rep_id(s) "
            f"do not exist in sales_reps: {sorted(orphan_ids)[:10]}"
        )
