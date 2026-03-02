"""
main.py
-------
Main entry point for the Sales Incentive Compensation Simulator.

Execution pipeline
------------------
1.  Load the incentive-plan configuration.
2.  Generate synthetic data (skipped when CSVs already exist in data/).
3.  Run the incentive calculation engine on the full dataset.
4.  Persist payout results to data/payout_results.csv.
5.  Set up the SQLite database (tables, data load, analytical views).
6.  Print a formatted summary to stdout.
7.  Execute a sample what-if simulation to demonstrate the simulator module.

Run
---
    python src/main.py
"""

from __future__ import annotations

import os
import sys
import textwrap

import pandas as pd

# Make sure the project root is on the Python path when run directly.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.config_loader import load_config
from src.data_generator import generate_all_data
from src.db_utils import query_to_df, setup_database
from src.incentive_engine import run_incentive_engine
from src.logger import get_logger
from src.simulator import compare_scenarios, get_scenario_summary, simulate_incentives

logger = get_logger(__name__)

_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH = os.path.join(_DATA_DIR, "sales_incentive.db")


def _load_or_generate_data() -> dict[str, pd.DataFrame]:
    """
    Return a dict of DataFrames.

    If all four CSVs are already present in *data/* they are loaded from disk;
    otherwise :func:`generate_all_data` is called to create them.
    """
    expected_files = {
        "sales_reps": os.path.join(_DATA_DIR, "sales_reps.csv"),
        "sales_transactions": os.path.join(_DATA_DIR, "sales_transactions.csv"),
        "incentive_plan": os.path.join(_DATA_DIR, "incentive_plan.csv"),
        "calendar": os.path.join(_DATA_DIR, "calendar.csv"),
    }

    if all(os.path.isfile(p) for p in expected_files.values()):
        logger.info("Existing CSVs found – loading from disk (skipping generation).")
        return {name: pd.read_csv(path) for name, path in expected_files.items()}

    logger.info("One or more CSVs missing – generating synthetic data.")
    return generate_all_data(output_dir=_DATA_DIR, seed=42)


def _print_summary(results_df: pd.DataFrame) -> None:
    """Print a formatted summary table to stdout."""
    summary = {
        "Total revenue":          f"${results_df['total_sales'].sum():>15,.0f}",
        "Total quota":            f"${results_df['quota'].sum():>15,.0f}",
        "Total payout":           f"${results_df['total_payout'].sum():>15,.0f}",
        "Total base commission":  f"${results_df['base_commission'].sum():>15,.0f}",
        "Total accelerator bonus":f"${results_df['accelerator_bonus'].sum():>15,.0f}",
        "Avg attainment":         f"{results_df['attainment_pct'].mean()*100:>14.1f}%",
        "% reps above quota":     f"{(results_df['attainment_pct']>=1.0).mean()*100:>14.1f}%",
        "Overall payout ratio":   f"{results_df['total_payout'].sum()/results_df['total_sales'].sum()*100:>14.2f}%",
        "Reps processed":         f"{len(results_df):>15,}",
    }

    width = 55
    border = "─" * width
    print(f"\n{'═'*width}")
    print(f"  {'Sales Incentive Simulator – Payout Summary':^{width-4}}")
    print(f"{'═'*width}")
    for label, value in summary.items():
        print(f"  {label:<34}{value}")
    print(f"{'═'*width}\n")

    # Per-region breakdown
    region_grp = (
        results_df.groupby("region")
        .agg(
            reps=("rep_id", "count"),
            revenue=("total_sales", "sum"),
            payout=("total_payout", "sum"),
            avg_attainment=("attainment_pct", "mean"),
        )
        .reset_index()
    )
    print(f"  {'Region breakdown':^{width-4}}")
    print(f"  {border}")
    header = f"  {'Region':<20} {'Reps':>5} {'Revenue':>14} {'Payout':>12} {'Attain%':>8}"
    print(header)
    print(f"  {border}")
    for _, row in region_grp.iterrows():
        print(
            f"  {row['region']:<20} {row['reps']:>5} "
            f"${row['revenue']:>13,.0f} ${row['payout']:>11,.0f} "
            f"{row['avg_attainment']*100:>7.1f}%"
        )
    print(f"{'═'*width}\n")


def _run_sample_simulation(
    sales_df: pd.DataFrame,
    reps_df: pd.DataFrame,
) -> None:
    """Demonstrate the what-if simulator with a concrete example."""
    print("Running sample what-if simulation: +10% quota, accelerator rate → 20%")
    print("─" * 60)

    scenario_params = {
        "quota_adjustment_pct": 0.10,
        "accelerator_rate": 0.20,
    }
    comparison = compare_scenarios(
        base_params={},
        scenario_params=scenario_params,
        sales_df=sales_df,
        reps_df=reps_df,
    )

    base_summary = get_scenario_summary(
        simulate_incentives(sales_df, reps_df, params={})
    )
    scenario_summary = get_scenario_summary(
        simulate_incentives(sales_df, reps_df, params=scenario_params)
    )

    delta_payout = scenario_summary["total_payout"] - base_summary["total_payout"]
    print(f"  Base total payout    : ${base_summary['total_payout']:>12,.0f}")
    print(f"  Scenario total payout: ${scenario_summary['total_payout']:>12,.0f}")
    print(f"  Payout delta         : ${delta_payout:>+12,.0f}")
    print(
        f"  Payout delta %       : {delta_payout/base_summary['total_payout']*100:>+11.2f}%"
        if base_summary["total_payout"] > 0
        else "  Payout delta %       :          N/A"
    )
    print()


def main() -> None:
    """Orchestrate the full Sales Incentive Simulator pipeline."""
    logger.info("╔══ Sales Incentive Compensation Simulator ══╗")
    logger.info("║  Starting main pipeline ...                ║")

    # ── Step 1: Configuration ───────────────────────────────────────────────
    config = load_config()
    logger.info("Config v%s loaded (effective %s).", config["version"], config["effective_from"])

    # ── Step 2: Data ────────────────────────────────────────────────────────
    datasets = _load_or_generate_data()
    sales_df = datasets["sales_transactions"]
    reps_df = datasets["sales_reps"]

    # ── Step 3: Incentive engine ────────────────────────────────────────────
    logger.info("Running incentive calculation engine …")
    results_df = run_incentive_engine(sales_df, reps_df, config)

    # ── Step 4: Persist results ─────────────────────────────────────────────
    payout_path = os.path.join(_DATA_DIR, "payout_results.csv")
    results_df.to_csv(payout_path, index=False)
    logger.info("Payout results saved → %s", payout_path)

    # ── Step 5: Database ────────────────────────────────────────────────────
    all_data: dict[str, pd.DataFrame] = {
        **datasets,
        "payout_results": results_df[
            [
                "rep_id", "rep_name", "region", "role",
                "total_sales", "quota", "attainment_pct",
                "base_commission", "accelerator_bonus",
                "total_payout", "payout_to_revenue_ratio",
            ]
        ],
    }
    engine = setup_database(all_data, db_path=_DB_PATH)

    # ── Step 6: Summary ─────────────────────────────────────────────────────
    _print_summary(results_df)

    # Sample analytical query via the view
    try:
        top_reps = query_to_df(
            engine,
            "SELECT rep_name, region, role, attainment_pct, deal_count "
            "FROM rep_performance_summary ORDER BY attainment_pct DESC LIMIT 5",
        )
        print("Top 5 reps by attainment (from analytical view):")
        print(top_reps.to_string(index=False))
        print()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not query rep_performance_summary view: %s", exc)

    # ── Step 7: Sample what-if simulation ───────────────────────────────────
    _run_sample_simulation(sales_df, reps_df)

    logger.info("╚══ Pipeline complete. ══╝")


if __name__ == "__main__":
    main()
