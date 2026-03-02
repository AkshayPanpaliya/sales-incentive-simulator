"""
tests/test_data_generator.py
-----------------------------
Unit tests for the synthetic data generation module.

Verifies row counts, schema completeness, referential integrity, and data
quality (no unexpected nulls) without depending on external services.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_generator import (
    generate_all_data,
    generate_calendar,
    generate_incentive_plan,
    generate_sales_reps,
    generate_transactions,
)


# ---------------------------------------------------------------------------
# generate_sales_reps
# ---------------------------------------------------------------------------


class TestGenerateSalesReps:
    def test_default_row_count(self) -> None:
        """Default call must produce exactly 100 rows."""
        reps = generate_sales_reps(seed=0)
        assert len(reps) == 100

    def test_custom_row_count(self) -> None:
        """n_reps parameter must be honoured."""
        reps = generate_sales_reps(n_reps=50, seed=0)
        assert len(reps) == 50

    def test_required_columns_present(self) -> None:
        """All six required columns must be present."""
        reps = generate_sales_reps(seed=0)
        required = {"rep_id", "rep_name", "region", "role", "quota", "hire_date"}
        assert required.issubset(set(reps.columns))

    def test_rep_ids_are_unique(self) -> None:
        """rep_id values must be unique (acts as primary key)."""
        reps = generate_sales_reps(seed=0)
        assert reps["rep_id"].nunique() == len(reps)

    def test_no_null_values_in_key_columns(self) -> None:
        """No nulls in any key column."""
        reps = generate_sales_reps(seed=0)
        key_cols = ["rep_id", "rep_name", "region", "role", "quota", "hire_date"]
        for col in key_cols:
            assert reps[col].isna().sum() == 0, f"Nulls found in column: {col}"

    def test_quotas_are_positive(self) -> None:
        """All quota values must be strictly positive."""
        reps = generate_sales_reps(seed=0)
        assert (reps["quota"] > 0).all()

    def test_roles_are_valid(self) -> None:
        """All roles must be drawn from the configured role set."""
        from src.config_loader import load_config
        config = load_config()
        valid_roles = set(config["roles"].keys())
        reps = generate_sales_reps(seed=0)
        assert set(reps["role"].unique()).issubset(valid_roles)

    def test_regions_are_valid(self) -> None:
        """All regions must be drawn from the configured region list."""
        from src.config_loader import load_config
        config = load_config()
        valid_regions = set(config["regions"])
        reps = generate_sales_reps(seed=0)
        assert set(reps["region"].unique()).issubset(valid_regions)

    def test_reproducibility(self) -> None:
        """Same seed must produce identical DataFrames."""
        reps_a = generate_sales_reps(seed=99)
        reps_b = generate_sales_reps(seed=99)
        pd.testing.assert_frame_equal(reps_a, reps_b)

    def test_different_seeds_differ(self) -> None:
        """Different seeds should (almost certainly) produce different rep names."""
        reps_a = generate_sales_reps(seed=1)
        reps_b = generate_sales_reps(seed=2)
        # It is astronomically unlikely that all names would match.
        assert not reps_a["rep_name"].equals(reps_b["rep_name"])


# ---------------------------------------------------------------------------
# generate_transactions
# ---------------------------------------------------------------------------


class TestGenerateTransactions:
    @pytest.fixture()
    def reps(self) -> pd.DataFrame:
        return generate_sales_reps(n_reps=20, seed=7)

    def test_default_row_count(self, reps: pd.DataFrame) -> None:
        """Default call must produce exactly 12,000 rows."""
        txns = generate_transactions(reps, n_transactions=12_000, seed=0)
        assert len(txns) == 12_000

    def test_required_columns_present(self, reps: pd.DataFrame) -> None:
        """All six required columns must be present."""
        txns = generate_transactions(reps, seed=0)
        required = {
            "transaction_id", "rep_id", "deal_date",
            "deal_amount", "product_category", "customer_segment",
        }
        assert required.issubset(set(txns.columns))

    def test_transaction_ids_are_unique(self, reps: pd.DataFrame) -> None:
        """transaction_id values must be unique."""
        txns = generate_transactions(reps, seed=0)
        assert txns["transaction_id"].nunique() == len(txns)

    def test_fk_integrity(self, reps: pd.DataFrame) -> None:
        """Every rep_id in transactions must exist in the sales_reps DataFrame."""
        txns = generate_transactions(reps, seed=0)
        valid_ids = set(reps["rep_id"].tolist())
        orphan_ids = set(txns["rep_id"].tolist()) - valid_ids
        assert len(orphan_ids) == 0, f"FK violation: {orphan_ids}"

    def test_no_null_values_in_key_columns(self, reps: pd.DataFrame) -> None:
        """No nulls in any key column."""
        txns = generate_transactions(reps, seed=0)
        key_cols = [
            "transaction_id", "rep_id", "deal_date",
            "deal_amount", "product_category", "customer_segment",
        ]
        for col in key_cols:
            assert txns[col].isna().sum() == 0, f"Nulls found in column: {col}"

    def test_deal_amounts_are_positive(self, reps: pd.DataFrame) -> None:
        """All deal amounts must be strictly positive."""
        txns = generate_transactions(reps, seed=0)
        assert (txns["deal_amount"] > 0).all()

    def test_deal_dates_within_2024(self, reps: pd.DataFrame) -> None:
        """All deal dates must fall within calendar year 2024."""
        txns = generate_transactions(reps, seed=0)
        dates = pd.to_datetime(txns["deal_date"])
        assert (dates.dt.year == 2024).all()


# ---------------------------------------------------------------------------
# generate_calendar
# ---------------------------------------------------------------------------


class TestGenerateCalendar:
    def test_date_range_coverage(self) -> None:
        """Calendar must cover every day from 2024-01-01 to 2024-12-31."""
        cal = generate_calendar("2024-01-01", "2024-12-31")
        assert cal.iloc[0]["date"] == "2024-01-01"
        assert cal.iloc[-1]["date"] == "2024-12-31"

    def test_row_count_for_leap_year_2024(self) -> None:
        """2024 is a leap year, so the calendar must have 366 rows."""
        cal = generate_calendar("2024-01-01", "2024-12-31")
        assert len(cal) == 366

    def test_required_columns_present(self) -> None:
        """All ten required columns must be present."""
        cal = generate_calendar()
        required = {
            "date", "year", "quarter", "month", "month_name",
            "week", "day_of_week", "is_weekend", "is_month_end", "is_quarter_end",
        }
        assert required.issubset(set(cal.columns))

    def test_no_null_values(self) -> None:
        """Calendar must contain no null values in any column."""
        cal = generate_calendar()
        assert cal.isna().sum().sum() == 0

    def test_weekend_flag_is_binary(self) -> None:
        """is_weekend must only contain 0 or 1."""
        cal = generate_calendar()
        assert set(cal["is_weekend"].unique()).issubset({0, 1})

    def test_quarter_values_are_valid(self) -> None:
        """Quarter values must be in {1, 2, 3, 4}."""
        cal = generate_calendar()
        assert set(cal["quarter"].unique()).issubset({1, 2, 3, 4})

    def test_all_months_represented(self) -> None:
        """All 12 months must be present in the 2024 calendar."""
        cal = generate_calendar()
        assert cal["month"].nunique() == 12

    def test_quarter_end_flag(self) -> None:
        """is_quarter_end should be 1 for the last day of each quarter."""
        cal = generate_calendar()
        q_ends = cal[cal["is_quarter_end"] == 1]["date"].tolist()
        # 2024 quarter-end dates
        expected = {"2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"}
        assert expected.issubset(set(q_ends))


# ---------------------------------------------------------------------------
# generate_all_data
# ---------------------------------------------------------------------------


class TestGenerateAllData:
    def test_returns_all_four_keys(self) -> None:
        """generate_all_data must return a dict with all four expected keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets = generate_all_data(output_dir=tmpdir, seed=42)
        assert set(datasets.keys()) == {
            "sales_reps", "transactions", "incentive_plan", "calendar"
        }

    def test_csvs_are_written(self) -> None:
        """One CSV file per dataset must be written to output_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_all_data(output_dir=tmpdir, seed=42)
            for name in ("sales_reps", "transactions", "incentive_plan", "calendar"):
                assert os.path.isfile(os.path.join(tmpdir, f"{name}.csv")), (
                    f"Missing CSV: {name}.csv"
                )

    def test_sales_reps_count(self) -> None:
        """generate_all_data must produce exactly 100 sales reps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets = generate_all_data(output_dir=tmpdir, seed=42)
        assert len(datasets["sales_reps"]) == 100

    def test_transactions_count(self) -> None:
        """generate_all_data must produce exactly 12,000 transactions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets = generate_all_data(output_dir=tmpdir, seed=42)
        assert len(datasets["transactions"]) == 12_000

    def test_fk_integrity_in_all_data(self) -> None:
        """All transaction rep_ids must exist in sales_reps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            datasets = generate_all_data(output_dir=tmpdir, seed=42)
        valid_ids = set(datasets["sales_reps"]["rep_id"].tolist())
        orphans = set(datasets["transactions"]["rep_id"].tolist()) - valid_ids
        assert len(orphans) == 0, f"FK violation: {orphans}"
