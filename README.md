# Sales Incentive Compensation Simulator

A production-grade, end-to-end Python application that simulates sales
incentive compensation plans.  It generates realistic synthetic sales data,
calculates tiered commissions with accelerators, persists results to SQLite,
and exposes a what-if simulation engine for plan optimisation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      src/main.py (orchestrator)                  │
└──────────┬─────────────┬───────────────────┬────────────────────┘
           │             │                   │
    ┌──────▼──────┐ ┌────▼──────┐  ┌─────────▼─────────┐
    │config_loader│ │data_      │  │ incentive_engine   │
    │.py          │ │generator  │  │ .py                │
    │             │ │.py        │  │ (vectorised calc)  │
    └──────┬──────┘ └────┬──────┘  └─────────┬─────────┘
           │             │                   │
           │      ┌──────▼──────┐    ┌───────▼────────┐
           │      │  data/*.csv │    │  simulator.py   │
           │      └──────┬──────┘    │  (what-if)     │
           │             │           └───────┬────────┘
           └─────────────┴───────────────────┘
                         │
                  ┌──────▼──────┐
                  │  db_utils   │
                  │  .py        │
                  └──────┬──────┘
                         │
               ┌─────────▼──────────┐
               │  SQLite Database   │
               │  sales_incentive   │
               │  .db               │
               │                    │
               │  Tables:           │
               │  • sales_reps      │
               │  • sales_txns      │
               │  • incentive_plan  │
               │  • calendar        │
               │  • payout_results  │
               │                    │
               │  Views (4):        │
               │  • rep_performance │
               │  • monthly_trend   │
               │  • region_eff.     │
               │  • over_quota      │
               └────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
git clone <repo-url>
cd sales-incentive-simulator
pip install -r requirements.txt
```

### Run the full pipeline

```bash
python src/main.py
```

This will:
1. Load `config/incentive_plan.json`
2. Generate 100 sales reps + 12,000 transactions (or load from `data/` if CSVs exist)
3. Calculate incentive payouts using the tiered commission engine
4. Save `data/payout_results.csv`
5. Create and populate `data/sales_incentive.db`
6. Print a formatted summary to stdout
7. Run a sample what-if simulation

### Run tests

```bash
python -m pytest tests/ -v
```

### Run Jupyter notebook

```bash
jupyter notebook notebooks/sales_incentive_analysis.ipynb
```

---

## Folder Structure

```
sales-incentive-simulator/
├── config/
│   └── incentive_plan.json       # Commission tiers, roles, regions
├── data/                         # Generated CSVs + SQLite DB (gitignored)
│   └── .gitkeep
├── docs/
│   └── data_dictionary.md        # Column-level data dictionary
├── notebooks/
│   └── sales_incentive_analysis.ipynb
├── powerbi/
│   └── README.md                 # Power BI dashboard design guide
├── sql/
│   ├── create_tables.sql         # DDL for all tables
│   ├── load_data.sql             # Load order reference + PRAGMA settings
│   └── analytical_views.sql      # 4 analytical views with window functions
├── src/
│   ├── __init__.py
│   ├── config_loader.py          # JSON config loader with caching + validation
│   ├── data_generator.py         # Synthetic data generation (Faker + NumPy)
│   ├── db_utils.py               # SQLAlchemy / SQLite utilities
│   ├── incentive_engine.py       # Core vectorised incentive calculator
│   ├── logger.py                 # Centralised logging (rotating file + console)
│   ├── main.py                   # Pipeline orchestrator
│   └── simulator.py              # What-if simulation engine
├── tests/
│   ├── __init__.py
│   ├── test_data_generator.py
│   ├── test_incentive_engine.py
│   └── test_simulator.py
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Business Logic

### Commission Tiers

Commission is calculated **band-by-band** on the revenue earned within each
attainment band – not as a flat rate on total revenue.

| Band | Attainment | Rate |
|------|-----------|------|
| 1 | 0 – 50% of quota | 2% |
| 2 | 50 – 100% of quota | 5% |
| 3 | 100 – 150% of quota | 8% |
| 4 | 150%+ of quota | 12% |

**Example** – Quota: $100,000 | Revenue: $120,000 (120% attainment)

```
Band 1 (0–50%):   $50,000 × 2%  =  $1,000
Band 2 (50–100%): $50,000 × 5%  =  $2,500
Band 3 (100–120%):$20,000 × 8%  =  $1,600
                              ─────────────
Base commission                =  $5,100
```

### Accelerator Bonus

Reps who exceed 100% of quota earn an **additional** accelerator bonus on all
incremental revenue above quota:

```
Incremental revenue = $120,000 − $100,000 = $20,000
Accelerator bonus   = $20,000 × 15%       =  $3,000

Total payout = $5,100 + $3,000 = $8,100
```

---

## API Reference

### `src.incentive_engine`

```python
run_incentive_engine(sales_df, reps_df, config) -> pd.DataFrame
```
Main entry point.  Returns a DataFrame with full payout details per rep.

```python
calculate_attainment(sales_df, reps_df) -> pd.DataFrame
apply_tiered_commission(attainment_df, tiers) -> pd.Series
apply_accelerator(attainment_df, accelerator_config) -> pd.Series
calculate_payouts(attainment_df, tiers, accelerator_config) -> pd.DataFrame
```

### `src.simulator`

```python
simulate_incentives(sales_df, reps_df, params) -> pd.DataFrame
```
Run a parameterised what-if simulation.  Supported params:
`tiers`, `accelerator_rate`, `accelerator_threshold`, `quota_adjustment_pct`,
`region_filter`, `role_filter`, `commission_rate_override`.

```python
compare_scenarios(base_params, scenario_params, sales_df, reps_df) -> pd.DataFrame
get_scenario_summary(simulation_result) -> dict
```

### `src.data_generator`

```python
generate_all_data(output_dir='data/', seed=42) -> dict[str, pd.DataFrame]
generate_sales_reps(n_reps=100, seed=42) -> pd.DataFrame
generate_transactions(sales_reps_df, n_transactions=12000, seed=42) -> pd.DataFrame
generate_calendar(start_date, end_date) -> pd.DataFrame
generate_incentive_plan(config) -> pd.DataFrame
```

### `src.config_loader`

```python
load_config(path=None) -> dict   # cached after first load
reset_cache()                     # for test isolation
```

---

## Data Dictionary

See [`docs/data_dictionary.md`](docs/data_dictionary.md) for full column-level
documentation of all tables and views.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

Tests cover:
- **Incentive engine** – tiered commission math, edge cases (zero sales,
  200%+ attainment), attainment aggregation.
- **Simulator** – region/role filters, quota adjustments, accelerator overrides,
  immutability of source DataFrames.
- **Data generator** – row counts, schema, FK integrity, null checks,
  reproducibility.

---

## Power BI Setup

See [`powerbi/README.md`](powerbi/README.md) for:
- Connection instructions (SQLite ODBC or CSV import)
- Data model / relationship diagram
- 4 report pages described in detail
- Full DAX measures reference
- Slicer configuration
- Color theme JSON

---

## Assumptions

1. **Analysis period** – All transactions are dated within calendar year 2024.
2. **Quota frequency** – Quotas are annual; no sub-period proration is applied.
3. **Accelerator additivity** – The accelerator bonus is additive to the tiered
   base commission (not a replacement rate).
4. **Role-based deal sizing** – Enterprise AEs close larger deals than SDRs
   as modelled by role-specific log-normal multipliers.
5. **No draws or recoveries** – The model does not include salary draws,
   minimum guarantees, or clawback provisions.
6. **Single plan version** – All reps operate under the same tier structure.
   Role differentiation affects only quota size, not commission rates.
7. **Synthetic data** – All names and figures are generated; any resemblance
   to real persons or organisations is coincidental.
