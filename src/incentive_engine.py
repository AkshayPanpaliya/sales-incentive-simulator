"""
incentive_engine.py
-------------------
Core vectorised incentive calculation engine for the Sales Incentive
Compensation Simulator.

Implements a tiered commission structure with an additive accelerator bonus.
All computation is done with Pandas/NumPy vectorised operations – no Python
for-loops iterate over individual rows.

Business Rules
--------------
Tiered commission is applied band-by-band to the actual revenue generated
within each quota-attainment band:

    Quota = 100,000 | Attainment = 120% | Revenue = 120,000
    ─────────────────────────────────────────────────────────
    Band 0–50 %  →  50,000 × 2 %  =  1,000
    Band 50–100% →  50,000 × 5 %  =  2,500
    Band 100–120%→  20,000 × 8 %  =  1,600
    ─────────────────────────────────────────
    Base commission            =  5,100

    Accelerator (above 100% quota, rate 15%):
    Incremental revenue above quota = 20,000
    Accelerator bonus = 20,000 × 15% = 3,000

    Total payout = 5,100 + 3,000 = 8,100
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public calculation functions
# ---------------------------------------------------------------------------


def calculate_attainment(
    sales_df: pd.DataFrame,
    reps_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute quota-attainment metrics for every sales representative.

    Representatives who have no transactions in *sales_df* are still included
    (attainment = 0 %).

    Parameters
    ----------
    sales_df : pd.DataFrame
        Transaction data.  Must contain columns ``rep_id`` and ``deal_amount``.
    reps_df : pd.DataFrame
        Sales rep master data.  Must contain columns ``rep_id`` and ``quota``.

    Returns
    -------
    pd.DataFrame
        Columns: ``rep_id``, ``total_sales``, ``quota``, ``attainment_pct``.
        ``attainment_pct`` is expressed as a decimal fraction (1.0 = 100 %).

    Raises
    ------
    ValueError
        If required columns are missing from either input DataFrame.
    """
    _require_columns(sales_df, ["rep_id", "deal_amount"], "sales_df")
    _require_columns(reps_df, ["rep_id", "quota"], "reps_df")

    # Aggregate transactions per rep; use outer join to include zero-sales reps.
    total_sales: pd.Series = (
        sales_df.groupby("rep_id")["deal_amount"]
        .sum()
        .rename("total_sales")
    )

    attainment_df: pd.DataFrame = (
        reps_df[["rep_id", "quota"]]
        .merge(total_sales, on="rep_id", how="left")
    )
    attainment_df["total_sales"] = attainment_df["total_sales"].fillna(0.0)

    # Guard against zero / negative quotas (should not occur with valid data).
    safe_quota: pd.Series = attainment_df["quota"].replace(0, np.nan)
    attainment_df["attainment_pct"] = (
        attainment_df["total_sales"] / safe_quota
    ).fillna(0.0)

    logger.debug(
        "Attainment computed for %d reps. Avg attainment: %.1f%%.",
        len(attainment_df),
        attainment_df["attainment_pct"].mean() * 100,
    )
    return attainment_df.reset_index(drop=True)


def apply_tiered_commission(
    attainment_df: pd.DataFrame,
    tiers: list[dict[str, float]],
) -> pd.Series:
    """
    Compute the base commission for each rep using a tiered band structure.

    The tiers specify attainment *fractions* (not absolute revenue).  For each
    band the commission rate is applied to the actual revenue that falls within
    that band.

    Parameters
    ----------
    attainment_df : pd.DataFrame
        Must contain ``total_sales``, ``quota``, and ``attainment_pct``.
    tiers : list of dict
        Each dict must have keys ``threshold_min``, ``threshold_max``, and
        ``commission_rate``.  Tiers should not overlap and should together
        cover the full attainment range encountered in the data.

    Returns
    -------
    pd.Series
        ``base_commission`` – one value per row of *attainment_df*.
    """
    _require_columns(
        attainment_df, ["total_sales", "quota", "attainment_pct"], "attainment_df"
    )

    quota: np.ndarray = attainment_df["quota"].to_numpy(dtype=float)
    attainment: np.ndarray = attainment_df["attainment_pct"].to_numpy(dtype=float)
    total_sales: np.ndarray = attainment_df["total_sales"].to_numpy(dtype=float)

    base_commission: np.ndarray = np.zeros(len(attainment_df), dtype=float)

    for tier in tiers:
        lo: float = float(tier["threshold_min"])
        hi: float = float(tier["threshold_max"])
        rate: float = float(tier["commission_rate"])

        # Revenue earned within this attainment band for each rep:
        # min(attainment, hi) clamps the upper end,
        # max(…, lo) clamps the lower end.
        effective_upper = np.minimum(attainment, hi)
        effective_lower = np.minimum(attainment, lo)
        revenue_in_band = np.maximum(effective_upper - effective_lower, 0.0) * quota

        base_commission += revenue_in_band * rate

    result = pd.Series(base_commission, index=attainment_df.index, name="base_commission")
    logger.debug(
        "Tiered commission calculated. Mean base commission: $%s.",
        f"{result.mean():,.2f}",
    )
    return result


def apply_accelerator(
    attainment_df: pd.DataFrame,
    accelerator_config: dict[str, float],
) -> pd.Series:
    """
    Compute the accelerator bonus for reps who exceed the accelerator threshold.

    The bonus is calculated on incremental revenue *above* the accelerator
    threshold (expressed as a quota fraction).

    Parameters
    ----------
    attainment_df : pd.DataFrame
        Must contain ``total_sales``, ``quota``, and ``attainment_pct``.
    accelerator_config : dict
        Must contain keys ``threshold`` (float, quota fraction) and
        ``rate`` (float, commission rate on incremental revenue).

    Returns
    -------
    pd.Series
        ``accelerator_bonus`` – one value per row of *attainment_df*.
    """
    _require_columns(
        attainment_df, ["total_sales", "quota", "attainment_pct"], "attainment_df"
    )

    threshold: float = float(accelerator_config["threshold"])
    rate: float = float(accelerator_config["rate"])

    quota: np.ndarray = attainment_df["quota"].to_numpy(dtype=float)
    total_sales: np.ndarray = attainment_df["total_sales"].to_numpy(dtype=float)
    attainment: np.ndarray = attainment_df["attainment_pct"].to_numpy(dtype=float)

    # Incremental revenue above the threshold (zero for under-threshold reps).
    threshold_revenue: np.ndarray = quota * threshold
    incremental_revenue: np.ndarray = np.maximum(total_sales - threshold_revenue, 0.0)
    # Only apply accelerator if attainment exceeds the threshold.
    above_threshold_mask: np.ndarray = attainment > threshold
    accelerator_bonus: np.ndarray = (
        np.where(above_threshold_mask, incremental_revenue * rate, 0.0)
    )

    result = pd.Series(
        accelerator_bonus, index=attainment_df.index, name="accelerator_bonus"
    )
    pct_qualifying = above_threshold_mask.mean() * 100
    logger.debug(
        "Accelerator applied. %.1f%% of reps qualify. Mean bonus: $%s.",
        pct_qualifying,
        f"{result[above_threshold_mask].mean():,.2f}" if above_threshold_mask.any() else "0.00",
    )
    return result


def calculate_payouts(
    attainment_df: pd.DataFrame,
    tiers: list[dict[str, float]],
    accelerator_config: dict[str, float],
) -> pd.DataFrame:
    """
    Combine tiered commission and accelerator bonus into a full payout table.

    Parameters
    ----------
    attainment_df : pd.DataFrame
        Output of :func:`calculate_attainment`.
    tiers : list of dict
        Commission tier definitions.
    accelerator_config : dict
        Accelerator parameters (``threshold`` and ``rate``).

    Returns
    -------
    pd.DataFrame
        Columns: ``rep_id``, ``total_sales``, ``quota``, ``attainment_pct``,
                 ``base_commission``, ``accelerator_bonus``, ``total_payout``,
                 ``payout_to_revenue_ratio``.
    """
    result_df: pd.DataFrame = attainment_df.copy()

    result_df["base_commission"] = apply_tiered_commission(attainment_df, tiers)
    result_df["accelerator_bonus"] = apply_accelerator(
        attainment_df, accelerator_config
    )
    result_df["total_payout"] = (
        result_df["base_commission"] + result_df["accelerator_bonus"]
    )

    # Guard against zero-revenue reps (avoid division by zero).
    safe_sales = result_df["total_sales"].replace(0, np.nan)
    result_df["payout_to_revenue_ratio"] = (
        result_df["total_payout"] / safe_sales
    ).fillna(0.0)

    return result_df


def run_incentive_engine(
    sales_df: pd.DataFrame,
    reps_df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """
    Main entry point – orchestrate the full incentive calculation pipeline.

    Parameters
    ----------
    sales_df : pd.DataFrame
        Sales transactions (``rep_id``, ``deal_amount`` required).
    reps_df : pd.DataFrame
        Sales rep master data (``rep_id``, ``quota``, ``rep_name``, ``region``,
        ``role`` required).
    config : dict
        Parsed incentive-plan configuration (output of
        :func:`src.config_loader.load_config`).

    Returns
    -------
    pd.DataFrame
        Full payout results merged with rep attributes.  Columns:
        ``rep_id``, ``rep_name``, ``region``, ``role``, ``total_sales``,
        ``quota``, ``attainment_pct``, ``base_commission``,
        ``accelerator_bonus``, ``total_payout``, ``payout_to_revenue_ratio``.
    """
    _require_columns(sales_df, ["rep_id", "deal_amount"], "sales_df")
    _require_columns(
        reps_df, ["rep_id", "quota", "rep_name", "region", "role"], "reps_df"
    )
    if sales_df.empty:
        raise ValueError("sales_df is empty – no transactions to process.")
    if reps_df.empty:
        raise ValueError("reps_df is empty – no sales reps defined.")

    tiers: list[dict] = config["tiers"]
    accelerator_config: dict = config["accelerator"]

    logger.info(
        "Running incentive engine: %d transactions for %d reps.",
        len(sales_df),
        len(reps_df),
    )

    attainment_df = calculate_attainment(sales_df, reps_df)
    payout_df = calculate_payouts(attainment_df, tiers, accelerator_config)

    # Enrich with rep demographics
    rep_attrs = reps_df[["rep_id", "rep_name", "region", "role"]]
    results = rep_attrs.merge(payout_df, on="rep_id", how="left")

    # Summary statistics for observability
    total_payout = results["total_payout"].sum()
    total_revenue = results["total_sales"].sum()
    avg_attainment = results["attainment_pct"].mean() * 100
    pct_above_quota = (results["attainment_pct"] >= 1.0).mean() * 100
    overall_payout_ratio = total_payout / total_revenue if total_revenue > 0 else 0.0

    logger.info(
        "Incentive engine complete.\n"
        "  Total revenue   : $%s\n"
        "  Total payout    : $%s\n"
        "  Payout ratio    : %.2f%%\n"
        "  Avg attainment  : %.1f%%\n"
        "  %% above quota  : %.1f%%",
        f"{total_revenue:>12,.0f}",
        f"{total_payout:>12,.0f}",
        overall_payout_ratio * 100,
        avg_attainment,
        pct_above_quota,
    )

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_columns(df: pd.DataFrame, columns: list[str], name: str) -> None:
    """
    Raise *ValueError* if any of *columns* are absent from *df*.
    """
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame '{name}' is missing required columns: {sorted(missing)}"
        )
