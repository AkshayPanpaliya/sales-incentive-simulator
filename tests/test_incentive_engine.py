"""
tests/test_incentive_engine.py
-------------------------------
Comprehensive unit tests for the core incentive calculation engine.

All tests use deterministic, hard-coded fixture data so results can be
verified by hand and are not dependent on random data-generation behaviour.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on the path regardless of how pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.incentive_engine import (
    apply_accelerator,
    apply_tiered_commission,
    calculate_attainment,
    calculate_payouts,
    run_incentive_engine,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TIERS = [
    {"threshold_min": 0.0,  "threshold_max": 0.5,   "commission_rate": 0.02},
    {"threshold_min": 0.5,  "threshold_max": 1.0,   "commission_rate": 0.05},
    {"threshold_min": 1.0,  "threshold_max": 1.5,   "commission_rate": 0.08},
    {"threshold_min": 1.5,  "threshold_max": 999.0, "commission_rate": 0.12},
]

ACCELERATOR = {"threshold": 1.0, "rate": 0.15}


@pytest.fixture()
def simple_reps() -> pd.DataFrame:
    """Three reps: one at 40%, one at 100%, one at 160% attainment."""
    return pd.DataFrame(
        {
            "rep_id":   [1, 2, 3],
            "rep_name": ["Alice", "Bob", "Carol"],
            "region":   ["North America", "EMEA", "APAC"],
            "role":     ["Enterprise AE", "Mid-Market AE", "SMB AE"],
            "quota":    [100_000.0, 200_000.0, 50_000.0],
            "hire_date":["2021-01-01", "2020-06-15", "2022-03-10"],
        }
    )


@pytest.fixture()
def simple_sales(simple_reps: pd.DataFrame) -> pd.DataFrame:
    """Deterministic deal amounts to hit precise attainment levels."""
    return pd.DataFrame(
        {
            "transaction_id":   [101, 102, 103],
            "rep_id":           [1, 2, 3],
            "deal_date":        ["2024-03-01", "2024-06-15", "2024-09-20"],
            "deal_amount":      [40_000.0, 200_000.0, 80_000.0],  # 40%, 100%, 160%
            "product_category": ["Enterprise Software", "Cloud Services", "Hardware"],
            "customer_segment": ["Enterprise", "Mid-Market", "SMB"],
        }
    )


@pytest.fixture()
def zero_sales_reps() -> pd.DataFrame:
    """Rep with no transactions at all."""
    return pd.DataFrame(
        {
            "rep_id":   [10],
            "rep_name": ["Dave"],
            "region":   ["LATAM"],
            "role":     ["SDR"],
            "quota":    [150_000.0],
            "hire_date":["2023-01-01"],
        }
    )


@pytest.fixture()
def zero_sales_transactions() -> pd.DataFrame:
    """Empty transactions frame (no deals for rep 10)."""
    return pd.DataFrame(
        columns=["transaction_id", "rep_id", "deal_date",
                 "deal_amount", "product_category", "customer_segment"]
    ).astype({"deal_amount": float, "rep_id": int})


# ---------------------------------------------------------------------------
# calculate_attainment tests
# ---------------------------------------------------------------------------


class TestCalculateAttainment:
    def test_basic_attainment(
        self, simple_sales: pd.DataFrame, simple_reps: pd.DataFrame
    ) -> None:
        """Attainment percentages match expected values for 3 reps."""
        result = calculate_attainment(simple_sales, simple_reps)

        alice = result.loc[result["rep_id"] == 1].iloc[0]
        bob   = result.loc[result["rep_id"] == 2].iloc[0]
        carol = result.loc[result["rep_id"] == 3].iloc[0]

        assert abs(alice["attainment_pct"] - 0.40) < 1e-6
        assert abs(bob["attainment_pct"]   - 1.00) < 1e-6
        assert abs(carol["attainment_pct"] - 1.60) < 1e-6

    def test_zero_sales_rep_included(
        self, zero_sales_transactions: pd.DataFrame, zero_sales_reps: pd.DataFrame
    ) -> None:
        """A rep with no sales still appears in the result with attainment 0."""
        result = calculate_attainment(zero_sales_transactions, zero_sales_reps)

        assert len(result) == 1
        assert result.iloc[0]["attainment_pct"] == 0.0
        assert result.iloc[0]["total_sales"] == 0.0

    def test_required_columns_enforced(self) -> None:
        """ValueError raised when required columns are missing."""
        bad_sales = pd.DataFrame({"rep_id": [1], "wrong_col": [100.0]})
        reps = pd.DataFrame({"rep_id": [1], "quota": [100_000.0]})

        with pytest.raises(ValueError, match="deal_amount"):
            calculate_attainment(bad_sales, reps)

    def test_total_sales_aggregated_correctly(
        self, simple_reps: pd.DataFrame
    ) -> None:
        """Multiple transactions for the same rep are summed correctly."""
        multi_sales = pd.DataFrame(
            {
                "transaction_id": [1, 2, 3],
                "rep_id":         [1, 1, 1],
                "deal_date":      ["2024-01-01", "2024-02-01", "2024-03-01"],
                "deal_amount":    [30_000.0, 40_000.0, 30_000.0],  # total = 100k = 100%
                "product_category": ["Enterprise Software"] * 3,
                "customer_segment": ["Enterprise"] * 3,
            }
        )
        result = calculate_attainment(multi_sales, simple_reps)
        alice = result.loc[result["rep_id"] == 1].iloc[0]
        assert abs(alice["total_sales"] - 100_000.0) < 1e-6
        assert abs(alice["attainment_pct"] - 1.00) < 1e-6


# ---------------------------------------------------------------------------
# apply_tiered_commission tests
# ---------------------------------------------------------------------------


class TestApplyTieredCommission:
    def _build_attainment(
        self, total_sales: float, quota: float
    ) -> pd.DataFrame:
        """Helper to build a minimal attainment DataFrame for a single rep."""
        return pd.DataFrame(
            {
                "rep_id":        [1],
                "total_sales":   [total_sales],
                "quota":         [quota],
                "attainment_pct":[total_sales / quota],
            }
        )

    def test_below_50_pct_only_tier_1(self) -> None:
        """40% attainment: only the first tier (0–50%) applies."""
        # quota=100k, sales=40k → 40% attainment
        # Band 0–40%: 40k × 2% = 800
        df = self._build_attainment(40_000.0, 100_000.0)
        commission = apply_tiered_commission(df, TIERS)
        assert abs(commission.iloc[0] - 800.0) < 1e-4

    def test_at_exactly_100_pct(self) -> None:
        """100% attainment: tiers 1 and 2 each fully apply."""
        # quota=100k, sales=100k
        # Band 0–50%:  50k × 2% = 1,000
        # Band 50–100%:50k × 5% = 2,500
        # Total = 3,500
        df = self._build_attainment(100_000.0, 100_000.0)
        commission = apply_tiered_commission(df, TIERS)
        assert abs(commission.iloc[0] - 3_500.0) < 1e-4

    def test_above_150_pct_all_tiers(self) -> None:
        """160% attainment: all four tiers contribute."""
        # quota=100k, sales=160k
        # Band 0–50%:   50k × 2% = 1,000
        # Band 50–100%: 50k × 5% = 2,500
        # Band 100–150%:50k × 8% = 4,000
        # Band 150–160%:10k ×12% = 1,200
        # Total = 8,700
        df = self._build_attainment(160_000.0, 100_000.0)
        commission = apply_tiered_commission(df, TIERS)
        assert abs(commission.iloc[0] - 8_700.0) < 1e-4

    def test_zero_sales(self) -> None:
        """Zero sales → zero commission."""
        df = self._build_attainment(0.0, 100_000.0)
        commission = apply_tiered_commission(df, TIERS)
        assert commission.iloc[0] == 0.0

    def test_commission_is_non_negative(self) -> None:
        """Commission must never be negative for any valid input."""
        for attainment in [0.0, 0.25, 0.75, 1.0, 1.3, 2.0]:
            df = self._build_attainment(attainment * 100_000.0, 100_000.0)
            commission = apply_tiered_commission(df, TIERS)
            assert commission.iloc[0] >= 0.0


# ---------------------------------------------------------------------------
# apply_accelerator tests
# ---------------------------------------------------------------------------


class TestApplyAccelerator:
    def _build_attainment(
        self, total_sales: float, quota: float
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "rep_id":        [1],
                "total_sales":   [total_sales],
                "quota":         [quota],
                "attainment_pct":[total_sales / quota],
            }
        )

    def test_below_threshold_no_accelerator(self) -> None:
        """Attainment below 100% → accelerator bonus is 0."""
        df = self._build_attainment(80_000.0, 100_000.0)
        bonus = apply_accelerator(df, ACCELERATOR)
        assert bonus.iloc[0] == 0.0

    def test_at_threshold_no_accelerator(self) -> None:
        """Attainment exactly at 100% → accelerator bonus is 0 (strict >)."""
        df = self._build_attainment(100_000.0, 100_000.0)
        bonus = apply_accelerator(df, ACCELERATOR)
        assert bonus.iloc[0] == 0.0

    def test_above_threshold_accelerator_applied(self) -> None:
        """120% attainment → accelerator on 20k incremental revenue."""
        # incremental revenue = 120k – 100k = 20k
        # bonus = 20k × 15% = 3,000
        df = self._build_attainment(120_000.0, 100_000.0)
        bonus = apply_accelerator(df, ACCELERATOR)
        assert abs(bonus.iloc[0] - 3_000.0) < 1e-4

    def test_custom_accelerator_config(self) -> None:
        """Custom threshold and rate are honoured."""
        custom = {"threshold": 0.8, "rate": 0.25}
        # 100% attainment, quota=100k; threshold=80% → 20k incremental × 25% = 5k
        df = self._build_attainment(100_000.0, 100_000.0)
        bonus = apply_accelerator(df, custom)
        assert abs(bonus.iloc[0] - 5_000.0) < 1e-4


# ---------------------------------------------------------------------------
# calculate_payouts end-to-end tests
# ---------------------------------------------------------------------------


class TestCalculatePayouts:
    def test_end_to_end_payout_at_120pct(self) -> None:
        """
        End-to-end payout at 120% attainment.

        quota=100k, sales=120k:
          base_commission  = 1,000 + 2,500 + 1,600 = 5,100
          accelerator_bonus = 20,000 × 15%         = 3,000
          total_payout                              = 8,100
        """
        attainment_df = pd.DataFrame(
            {
                "rep_id":        [1],
                "total_sales":   [120_000.0],
                "quota":         [100_000.0],
                "attainment_pct":[1.20],
            }
        )
        result = calculate_payouts(attainment_df, TIERS, ACCELERATOR)

        assert abs(result.iloc[0]["base_commission"] - 5_100.0) < 1e-4
        assert abs(result.iloc[0]["accelerator_bonus"] - 3_000.0) < 1e-4
        assert abs(result.iloc[0]["total_payout"] - 8_100.0) < 1e-4

    def test_payout_to_revenue_ratio_in_valid_range(
        self,
        simple_sales: pd.DataFrame,
        simple_reps: pd.DataFrame,
    ) -> None:
        """Payout-to-revenue ratio must be in [0, 1] for all reps."""
        attainment_df = calculate_attainment(simple_sales, simple_reps)
        result = calculate_payouts(attainment_df, TIERS, ACCELERATOR)
        ratios = result["payout_to_revenue_ratio"]
        assert (ratios >= 0.0).all(), "Negative payout ratio detected."
        assert (ratios <= 1.0).all(), "Payout ratio exceeds 100%."

    def test_zero_sales_rep_payout_is_zero(
        self,
        zero_sales_transactions: pd.DataFrame,
        zero_sales_reps: pd.DataFrame,
    ) -> None:
        """Rep with zero sales must have zero payout and zero ratio."""
        attainment_df = calculate_attainment(zero_sales_transactions, zero_sales_reps)
        result = calculate_payouts(attainment_df, TIERS, ACCELERATOR)
        assert result.iloc[0]["total_payout"] == 0.0
        assert result.iloc[0]["payout_to_revenue_ratio"] == 0.0

    def test_payout_increases_monotonically_with_sales(self) -> None:
        """Higher sales must always produce a higher or equal total payout."""
        payouts = []
        for sales_amount in [0, 25_000, 50_000, 100_000, 150_000, 200_000]:
            df = pd.DataFrame(
                {
                    "rep_id":        [1],
                    "total_sales":   [float(sales_amount)],
                    "quota":         [100_000.0],
                    "attainment_pct":[sales_amount / 100_000.0],
                }
            )
            result = calculate_payouts(df, TIERS, ACCELERATOR)
            payouts.append(result.iloc[0]["total_payout"])

        for i in range(1, len(payouts)):
            assert payouts[i] >= payouts[i - 1], (
                f"Payout decreased: {payouts[i-1]} → {payouts[i]}"
            )


# ---------------------------------------------------------------------------
# run_incentive_engine integration test
# ---------------------------------------------------------------------------


class TestRunIncentiveEngine:
    def test_integration(
        self,
        simple_sales: pd.DataFrame,
        simple_reps: pd.DataFrame,
    ) -> None:
        """Full pipeline returns a DataFrame with all expected columns."""
        config = {
            "tiers": TIERS,
            "accelerator": ACCELERATOR,
        }
        result = run_incentive_engine(simple_sales, simple_reps, config)

        required_cols = [
            "rep_id", "rep_name", "region", "role",
            "total_sales", "quota", "attainment_pct",
            "base_commission", "accelerator_bonus",
            "total_payout", "payout_to_revenue_ratio",
        ]
        for col in required_cols:
            assert col in result.columns, f"Missing column: {col}"

        assert len(result) == len(simple_reps)

    def test_raises_on_empty_sales(
        self, simple_reps: pd.DataFrame
    ) -> None:
        """Empty sales DataFrame must raise ValueError."""
        empty_sales = pd.DataFrame(
            columns=["rep_id", "deal_amount", "deal_date",
                     "product_category", "customer_segment"]
        )
        config = {"tiers": TIERS, "accelerator": ACCELERATOR}
        with pytest.raises(ValueError):
            run_incentive_engine(empty_sales, simple_reps, config)

    def test_high_attainment_rep(self, simple_reps: pd.DataFrame) -> None:
        """Rep with 250% attainment produces non-negative payout."""
        high_sales = pd.DataFrame(
            {
                "transaction_id":   [999],
                "rep_id":           [1],
                "deal_date":        ["2024-11-01"],
                "deal_amount":      [250_000.0],  # 250% of 100k quota
                "product_category": ["Enterprise Software"],
                "customer_segment": ["Enterprise"],
            }
        )
        config = {"tiers": TIERS, "accelerator": ACCELERATOR}
        result = run_incentive_engine(high_sales, simple_reps, config)
        alice = result.loc[result["rep_id"] == 1].iloc[0]
        assert alice["total_payout"] > 0
        assert alice["attainment_pct"] == pytest.approx(2.50, rel=1e-4)
