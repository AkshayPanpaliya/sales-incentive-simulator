"""
tests/test_simulator.py
------------------------
Unit tests for the what-if simulation engine.

All tests use small, deterministic fixture DataFrames so results can be
verified analytically without relying on the stochastic data generator.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.simulator import compare_scenarios, get_scenario_summary, simulate_incentives

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TIERS = [
    {"threshold_min": 0.0,  "threshold_max": 0.5,   "commission_rate": 0.02},
    {"threshold_min": 0.5,  "threshold_max": 1.0,   "commission_rate": 0.05},
    {"threshold_min": 1.0,  "threshold_max": 1.5,   "commission_rate": 0.08},
    {"threshold_min": 1.5,  "threshold_max": 999.0, "commission_rate": 0.12},
]

ACCELERATOR = {"threshold": 1.0, "rate": 0.15}


@pytest.fixture()
def sample_reps() -> pd.DataFrame:
    """Six reps spread across two regions and two roles."""
    return pd.DataFrame(
        {
            "rep_id":   [1, 2, 3, 4, 5, 6],
            "rep_name": ["Alice", "Bob", "Carol", "Dan", "Eve", "Frank"],
            "region":   ["North America", "North America", "EMEA",
                         "EMEA", "APAC", "APAC"],
            "role":     ["Enterprise AE", "Mid-Market AE", "Enterprise AE",
                         "Mid-Market AE", "SMB AE", "SDR"],
            "quota":    [200_000.0, 100_000.0, 200_000.0,
                         100_000.0,  80_000.0,  60_000.0],
            "hire_date":["2020-01-01"] * 6,
        }
    )


@pytest.fixture()
def sample_sales(sample_reps: pd.DataFrame) -> pd.DataFrame:
    """Deterministic sales: each rep sells exactly their quota amount."""
    records = []
    for _, rep in sample_reps.iterrows():
        records.append(
            {
                "transaction_id":   int(rep["rep_id"]) * 100,
                "rep_id":           int(rep["rep_id"]),
                "deal_date":        "2024-06-30",
                "deal_amount":      float(rep["quota"]),
                "product_category": "Cloud Services",
                "customer_segment": "Enterprise",
            }
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# simulate_incentives tests
# ---------------------------------------------------------------------------


class TestSimulateIncentives:
    def test_default_params_returns_all_reps(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Default params (empty dict) returns results for all reps."""
        result = simulate_incentives(sample_sales, sample_reps, params={})
        assert len(result) == len(sample_reps)

    def test_quota_adjustment_reduces_attainment_but_raises_payout(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """
        A +10% quota increase raises the quota bar.
        With fixed sales equal to original quota, attainment drops below 100%,
        so no accelerator fires and total payout must be ≤ base payout.
        """
        base = simulate_incentives(sample_sales, sample_reps, params={})
        scenario = simulate_incentives(
            sample_sales, sample_reps,
            params={"quota_adjustment_pct": 0.10},
        )
        # Attainment in scenario must be lower (quota went up, sales fixed)
        assert scenario["attainment_pct"].mean() < base["attainment_pct"].mean()
        # Total payout in scenario must be ≤ base (no accelerator in scenario)
        assert scenario["total_payout"].sum() <= base["total_payout"].sum()

    def test_quota_decrease_raises_attainment(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """A -10% quota decrease must raise avg attainment above base."""
        base = simulate_incentives(sample_sales, sample_reps, params={})
        scenario = simulate_incentives(
            sample_sales, sample_reps,
            params={"quota_adjustment_pct": -0.10},
        )
        assert scenario["attainment_pct"].mean() > base["attainment_pct"].mean()

    def test_region_filter_limits_reps(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """region_filter must restrict results to reps in the specified regions."""
        result = simulate_incentives(
            sample_sales, sample_reps,
            params={"region_filter": ["North America"]},
        )
        assert set(result["region"].unique()) == {"North America"}
        assert len(result) == 2  # Alice and Bob

    def test_role_filter_limits_reps(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """role_filter must restrict results to reps with the specified roles."""
        result = simulate_incentives(
            sample_sales, sample_reps,
            params={"role_filter": ["Enterprise AE"]},
        )
        assert set(result["role"].unique()) == {"Enterprise AE"}
        assert len(result) == 2  # Alice and Carol

    def test_region_and_role_filter_combined(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Combined region + role filter must apply both constraints."""
        result = simulate_incentives(
            sample_sales, sample_reps,
            params={
                "region_filter": ["EMEA"],
                "role_filter": ["Enterprise AE"],
            },
        )
        # Only Carol (EMEA + Enterprise AE)
        assert len(result) == 1
        assert result.iloc[0]["rep_name"] == "Carol"

    def test_accelerator_rate_change_affects_overquota_reps(
        self, sample_reps: pd.DataFrame
    ) -> None:
        """Higher accelerator rate must produce a higher total payout for over-quota reps."""
        # Create sales that give all reps 150% attainment
        over_quota_sales = pd.DataFrame(
            [
                {
                    "transaction_id":   i * 100,
                    "rep_id":           int(rep["rep_id"]),
                    "deal_date":        "2024-09-01",
                    "deal_amount":      float(rep["quota"]) * 1.5,
                    "product_category": "Enterprise Software",
                    "customer_segment": "Enterprise",
                }
                for i, (_, rep) in enumerate(sample_reps.iterrows(), start=1)
            ]
        )
        base = simulate_incentives(over_quota_sales, sample_reps, params={})
        high_accel = simulate_incentives(
            over_quota_sales, sample_reps,
            params={"accelerator_rate": 0.30},
        )
        assert high_accel["total_payout"].sum() > base["total_payout"].sum()

    def test_commission_rate_override(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Overriding tier 1 commission rate from 5% to 10% must raise payout."""
        base = simulate_incentives(sample_sales, sample_reps, params={})
        # Tier index 1 = threshold 50–100%, rate 5% → override to 10%
        override = simulate_incentives(
            sample_sales, sample_reps,
            params={"commission_rate_override": {1: 0.10}},
        )
        # All reps are at 100% attainment so tier 1 fires for everyone
        assert override["total_payout"].sum() > base["total_payout"].sum()

    def test_unknown_region_filter_warns_but_raises(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """An entirely unknown region filter should raise ValueError (no reps match)."""
        with pytest.raises(ValueError, match="No reps found"):
            simulate_incentives(
                sample_sales, sample_reps,
                params={"region_filter": ["Antarctica"]},
            )

    def test_source_dataframes_not_mutated(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """simulate_incentives must not modify the caller's DataFrames."""
        reps_copy = sample_reps.copy(deep=True)
        sales_copy = sample_sales.copy(deep=True)

        simulate_incentives(
            sample_sales, sample_reps,
            params={"quota_adjustment_pct": 0.5},
        )

        pd.testing.assert_frame_equal(sample_reps, reps_copy)
        pd.testing.assert_frame_equal(sample_sales, sales_copy)


# ---------------------------------------------------------------------------
# compare_scenarios tests
# ---------------------------------------------------------------------------


class TestCompareScenarios:
    def test_returns_correct_columns(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Comparison DataFrame must contain payout_delta and payout_pct_change."""
        comparison = compare_scenarios(
            base_params={},
            scenario_params={"quota_adjustment_pct": 0.10},
            sales_df=sample_sales,
            reps_df=sample_reps,
        )
        assert "payout_delta" in comparison.columns
        assert "payout_pct_change" in comparison.columns

    def test_identical_scenarios_produce_zero_delta(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Comparing a scenario with itself must yield zero payout delta."""
        comparison = compare_scenarios(
            base_params={},
            scenario_params={},
            sales_df=sample_sales,
            reps_df=sample_reps,
        )
        assert comparison["payout_delta"].abs().sum() == pytest.approx(0.0, abs=1e-4)

    def test_quota_increase_produces_negative_delta(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Raising quotas with fixed sales lowers payouts → negative aggregate delta."""
        comparison = compare_scenarios(
            base_params={},
            scenario_params={"quota_adjustment_pct": 0.20},
            sales_df=sample_sales,
            reps_df=sample_reps,
        )
        assert comparison["payout_delta"].sum() < 0


# ---------------------------------------------------------------------------
# get_scenario_summary tests
# ---------------------------------------------------------------------------


class TestGetScenarioSummary:
    def test_summary_keys(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Summary dict must contain all expected keys."""
        result = simulate_incentives(sample_sales, sample_reps, params={})
        summary = get_scenario_summary(result)

        expected_keys = {
            "total_payout", "total_revenue", "avg_attainment",
            "pct_above_quota", "payout_ratio",
        }
        assert expected_keys == set(summary.keys())

    def test_summary_value_types(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """All summary values must be Python floats."""
        result = simulate_incentives(sample_sales, sample_reps, params={})
        summary = get_scenario_summary(result)

        for key, value in summary.items():
            assert isinstance(value, float), f"Key '{key}' is not a float: {type(value)}"

    def test_pct_above_quota_is_fraction(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """pct_above_quota must be a fraction in [0, 1]."""
        result = simulate_incentives(sample_sales, sample_reps, params={})
        summary = get_scenario_summary(result)
        assert 0.0 <= summary["pct_above_quota"] <= 1.0

    def test_payout_ratio_is_positive(
        self, sample_sales: pd.DataFrame, sample_reps: pd.DataFrame
    ) -> None:
        """Payout ratio must be non-negative."""
        result = simulate_incentives(sample_sales, sample_reps, params={})
        summary = get_scenario_summary(result)
        assert summary["payout_ratio"] >= 0.0
