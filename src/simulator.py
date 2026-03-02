"""
simulator.py
------------
What-if simulation engine for the Sales Incentive Compensation Simulator.

Allows analysts to rapidly test alternative compensation scenarios by
parameterising quota adjustments, accelerator rates, commission-rate overrides,
and rep/region filters – without mutating the source data.

Typical Usage
-------------
>>> from src.simulator import simulate_incentives, compare_scenarios
>>>
>>> base_result = simulate_incentives(sales_df, reps_df, params={})
>>>
>>> scenario_result = simulate_incentives(
...     sales_df, reps_df,
...     params={
...         "quota_adjustment_pct": 0.10,    # raise quotas 10%
...         "accelerator_rate": 0.20,         # raise accelerator rate
...         "region_filter": ["North America", "EMEA"],
...     }
... )
>>>
>>> comparison = compare_scenarios(
...     base_params={},
...     scenario_params={"quota_adjustment_pct": 0.10},
...     sales_df=sales_df,
...     reps_df=reps_df,
... )
"""

from __future__ import annotations

import copy
from typing import Any

import pandas as pd

from src.config_loader import load_config
from src.incentive_engine import run_incentive_engine
from src.logger import get_logger

logger = get_logger(__name__)


def simulate_incentives(
    sales_df: pd.DataFrame,
    reps_df: pd.DataFrame,
    params: dict[str, Any],
) -> pd.DataFrame:
    """
    Run a what-if incentive simulation with custom parameters.

    This function never mutates the caller's DataFrames.  All modifications
    are applied to deep copies of the inputs before the incentive engine is
    invoked.

    Parameters
    ----------
    sales_df : pd.DataFrame
        Sales transactions data.  Required columns: ``rep_id``, ``deal_amount``.
    reps_df : pd.DataFrame
        Sales reps data.  Required columns: ``rep_id``, ``quota``, ``rep_name``,
        ``region``, ``role``.
    params : dict
        Simulation parameters (all optional):

        ``tiers`` : list[dict]
            Override the default commission tiers.
        ``accelerator_rate`` : float
            Override the accelerator commission rate.
        ``accelerator_threshold`` : float
            Override the attainment fraction at which the accelerator triggers.
        ``quota_adjustment_pct`` : float
            Fractional change applied to every rep's quota before calculation.
            E.g. ``0.10`` raises quotas by 10 %; ``-0.05`` lowers by 5 %.
        ``region_filter`` : list[str]
            Restrict analysis to reps in these regions only.
        ``role_filter`` : list[str]
            Restrict analysis to reps with these roles only.
        ``commission_rate_override`` : dict[int, float]
            Map tier-index (0-based) to a new commission rate, e.g.
            ``{2: 0.10}`` overrides tier 2's rate to 10 %.

    Returns
    -------
    pd.DataFrame
        Payout results with full column set (see
        :func:`src.incentive_engine.run_incentive_engine`).

    Raises
    ------
    ValueError
        If *sales_df* or *reps_df* are empty after applying filters, or if
        filter lists reference unknown regions / roles.
    """
    config: dict[str, Any] = load_config()

    # ── Work on deep copies so we never mutate caller data ─────────────────
    sim_reps: pd.DataFrame = reps_df.copy()
    sim_sales: pd.DataFrame = sales_df.copy()
    sim_config: dict[str, Any] = copy.deepcopy(config)

    # ── Apply region filter ────────────────────────────────────────────────
    if "region_filter" in params and params["region_filter"]:
        regions = params["region_filter"]
        unknown = set(regions) - set(sim_reps["region"].unique())
        if unknown:
            logger.warning("Region filter contains unknown regions: %s", unknown)
        sim_reps = sim_reps[sim_reps["region"].isin(regions)]
        if sim_reps.empty:
            raise ValueError(
                f"No reps found after applying region_filter={regions}."
            )
        logger.debug("Region filter applied: %d reps remaining.", len(sim_reps))

    # ── Apply role filter ──────────────────────────────────────────────────
    if "role_filter" in params and params["role_filter"]:
        roles = params["role_filter"]
        unknown = set(roles) - set(sim_reps["role"].unique())
        if unknown:
            logger.warning("Role filter contains unknown roles: %s", unknown)
        sim_reps = sim_reps[sim_reps["role"].isin(roles)]
        if sim_reps.empty:
            raise ValueError(
                f"No reps found after applying role_filter={roles}."
            )
        logger.debug("Role filter applied: %d reps remaining.", len(sim_reps))

    # Keep only transactions belonging to the filtered rep set.
    valid_rep_ids = set(sim_reps["rep_id"])
    sim_sales = sim_sales[sim_sales["rep_id"].isin(valid_rep_ids)]

    # ── Apply quota adjustment ─────────────────────────────────────────────
    if "quota_adjustment_pct" in params:
        adj: float = float(params["quota_adjustment_pct"])
        sim_reps = sim_reps.copy()
        sim_reps["quota"] = sim_reps["quota"] * (1.0 + adj)
        logger.debug(
            "Quota adjustment of %+.1f%% applied.", adj * 100
        )

    # ── Apply commission-rate override ─────────────────────────────────────
    if "commission_rate_override" in params:
        overrides: dict[int, float] = params["commission_rate_override"]
        for tier_idx, new_rate in overrides.items():
            if 0 <= int(tier_idx) < len(sim_config["tiers"]):
                sim_config["tiers"][int(tier_idx)]["commission_rate"] = float(new_rate)
                logger.debug(
                    "Tier %d commission_rate overridden to %.4f.", tier_idx, new_rate
                )

    # ── Apply accelerator overrides ────────────────────────────────────────
    if "accelerator_rate" in params:
        sim_config["accelerator"]["rate"] = float(params["accelerator_rate"])
        logger.debug(
            "Accelerator rate overridden to %.4f.", params["accelerator_rate"]
        )
    if "accelerator_threshold" in params:
        sim_config["accelerator"]["threshold"] = float(params["accelerator_threshold"])
        logger.debug(
            "Accelerator threshold overridden to %.4f.",
            params["accelerator_threshold"],
        )

    # ── Apply full tier override ───────────────────────────────────────────
    if "tiers" in params and params["tiers"]:
        sim_config["tiers"] = params["tiers"]
        logger.debug("Full tier configuration overridden.")

    logger.info(
        "Running simulation: %d reps, %d transactions, params=%s.",
        len(sim_reps),
        len(sim_sales),
        {k: v for k, v in params.items() if k not in ("tiers",)},
    )

    return run_incentive_engine(sim_sales, sim_reps, sim_config)


def compare_scenarios(
    base_params: dict[str, Any],
    scenario_params: dict[str, Any],
    sales_df: pd.DataFrame,
    reps_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Run two simulations and return a side-by-side comparison DataFrame.

    Parameters
    ----------
    base_params : dict
        Parameters for the baseline simulation (often empty ``{}``).
    scenario_params : dict
        Parameters for the alternative scenario.
    sales_df : pd.DataFrame
        Source transactions data.
    reps_df : pd.DataFrame
        Source sales reps data.

    Returns
    -------
    pd.DataFrame
        One row per rep (outer union of both simulations).  Columns from the
        baseline are suffixed ``_base``; columns from the scenario are suffixed
        ``_scenario``.  Additionally contains:

        ``payout_delta``
            Absolute change in total payout (scenario − base).
        ``payout_pct_change``
            Percentage change in total payout relative to base.
    """
    logger.info("Comparing base scenario vs. alternative scenario.")

    base_result = simulate_incentives(sales_df, reps_df, base_params)
    scenario_result = simulate_incentives(sales_df, reps_df, scenario_params)

    # Select numeric KPI columns to compare
    kpi_cols = [
        "total_sales", "quota", "attainment_pct",
        "base_commission", "accelerator_bonus", "total_payout",
        "payout_to_revenue_ratio",
    ]

    base_kpi = base_result[["rep_id", "rep_name", "region", "role"] + kpi_cols].copy()
    scenario_kpi = scenario_result[["rep_id"] + kpi_cols].copy()

    base_kpi = base_kpi.rename(columns={c: f"{c}_base" for c in kpi_cols})
    scenario_kpi = scenario_kpi.rename(columns={c: f"{c}_scenario" for c in kpi_cols})

    comparison = base_kpi.merge(scenario_kpi, on="rep_id", how="outer")

    comparison["payout_delta"] = (
        comparison["total_payout_scenario"].fillna(0.0)
        - comparison["total_payout_base"].fillna(0.0)
    )
    base_payout = comparison["total_payout_base"].replace(0, float("nan"))
    comparison["payout_pct_change"] = (
        comparison["payout_delta"] / base_payout * 100
    ).fillna(0.0)

    logger.info(
        "Comparison complete. Aggregate payout delta: $%+,.0f.",
        comparison["payout_delta"].sum(),
    )
    return comparison


def get_scenario_summary(simulation_result: pd.DataFrame) -> dict[str, float]:
    """
    Compute high-level summary statistics from a simulation result DataFrame.

    Parameters
    ----------
    simulation_result : pd.DataFrame
        Output of :func:`simulate_incentives` or
        :func:`src.incentive_engine.run_incentive_engine`.

    Returns
    -------
    dict
        Keys:

        ``total_payout``         – sum of total_payout across all reps.
        ``total_revenue``        – sum of total_sales across all reps.
        ``avg_attainment``       – mean attainment_pct (decimal fraction).
        ``pct_above_quota``      – fraction of reps with attainment ≥ 1.0.
        ``payout_ratio``         – total_payout / total_revenue.
    """
    total_payout: float = float(simulation_result["total_payout"].sum())
    total_revenue: float = float(simulation_result["total_sales"].sum())
    avg_attainment: float = float(simulation_result["attainment_pct"].mean())
    pct_above_quota: float = float(
        (simulation_result["attainment_pct"] >= 1.0).mean()
    )
    payout_ratio: float = (
        total_payout / total_revenue if total_revenue > 0 else 0.0
    )

    return {
        "total_payout": total_payout,
        "total_revenue": total_revenue,
        "avg_attainment": avg_attainment,
        "pct_above_quota": pct_above_quota,
        "payout_ratio": payout_ratio,
    }
