<p align="center">
  <img src="https://img.icons8.com/fluency/96/money-bag.png" alt="Logo" width="80"/>
</p>

<h1 align="center">💰 Sales Incentive Compensation Simulator</h1>

<p align="center">
  <strong>A production-grade Python application for simulating sales incentive compensation plans</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#demo">Demo</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#api-reference">API</a> •
  <a href="#testing">Testing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite"/>
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas"/>
  <img src="https://img.shields.io/badge/Tests-67%20passed-success?style=for-the-badge" alt="Tests"/>
</p>

---

## ✨ Features

- 🎯 **Tiered Commission Engine** – Band-by-band commission calculation with vectorized NumPy operations
- 🚀 **Accelerator Bonuses** – Additional incentives for over-quota performance
- 🔮 **What-If Simulator** – Model alternative compensation scenarios without touching source data
- 📊 **Interactive Dashboard** – Beautiful Streamlit UI with Plotly visualizations
- 🗄️ **SQLite Analytics** – Pre-built analytical views with window functions
- 📈 **Power BI Ready** – Comprehensive data model for enterprise reporting
- ✅ **67 Unit Tests** – Full test coverage for business logic

---

## 🎬 Demo

### Dashboard Preview

| Executive Dashboard | What-If Simulator |
|:---:|:---:|
| Real-time KPIs, revenue trends, top performers | Model quota changes, rate adjustments |

### Key Metrics Generated

| Metric | Value |
|--------|-------|
| Total Revenue | $888M |
| Total Payout | $224M |
| Payout Ratio | 25.27% |
| Reps Processed | 100 |
| Transactions | 12,000 |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/sales-incentive-simulator.git
cd sales-incentive-simulator

# Install dependencies
pip install -r requirements.txt
```

### Run the Pipeline

```bash
# Generate data and calculate payouts
python src/main.py
```

This will:
1. ✅ Load `config/incentive_plan.json`
2. ✅ Generate 100 sales reps + 12,000 transactions
3. ✅ Calculate tiered commissions with accelerators
4. ✅ Save results to `data/payout_results.csv`
5. ✅ Create SQLite database with analytical views
6. ✅ Print formatted summary

### Launch the Dashboard

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        app.py (Streamlit UI)                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
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
               └────────────────────┘
```

---

## 📐 Business Logic

### Commission Tiers

Commission is calculated **band-by-band** on revenue earned within each attainment band:

| Band | Attainment | Rate |
|------|-----------|------|
| 1 | 0 – 50% of quota | 2% |
| 2 | 50 – 100% of quota | 5% |
| 3 | 100 – 150% of quota | 8% |
| 4 | 150%+ of quota | 12% |

### Example Calculation

```
Quota: $100,000 | Revenue: $120,000 (120% attainment)
───────────────────────────────────────────────────
Band 1 (0–50%):   $50,000 × 2%  =  $1,000
Band 2 (50–100%): $50,000 × 5%  =  $2,500
Band 3 (100–120%):$20,000 × 8%  =  $1,600
                              ─────────────
Base commission                =  $5,100

Accelerator Bonus (15% on revenue above quota):
$20,000 × 15% = $3,000

Total Payout = $5,100 + $3,000 = $8,100
```

---

## 📁 Project Structure

```
sales-incentive-simulator/
├── 📱 app.py                     # Streamlit dashboard
├── ⚙️ config/
│   └── incentive_plan.json       # Commission tiers, roles, regions
├── 📊 data/                      # Generated CSVs + SQLite DB
├── 📚 docs/
│   └── data_dictionary.md        # Column-level documentation
├── 📓 notebooks/
│   └── sales_incentive_analysis.ipynb
├── 📈 powerbi/
│   └── README.md                 # Power BI setup guide
├── 🗄️ sql/
│   ├── create_tables.sql         # DDL for all tables
│   ├── load_data.sql             # Load order reference
│   └── analytical_views.sql      # 4 analytical views
├── 🐍 src/
│   ├── config_loader.py          # JSON config with validation
│   ├── data_generator.py         # Synthetic data (Faker + NumPy)
│   ├── db_utils.py               # SQLAlchemy utilities
│   ├── incentive_engine.py       # Vectorised commission calc
│   ├── logger.py                 # Rotating file + console logs
│   ├── main.py                   # Pipeline orchestrator
│   └── simulator.py              # What-if engine
├── 🧪 tests/
│   ├── test_data_generator.py
│   ├── test_incentive_engine.py
│   └── test_simulator.py
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 🔌 API Reference

### Incentive Engine

```python
from src.incentive_engine import run_incentive_engine

results = run_incentive_engine(sales_df, reps_df, config)
# Returns DataFrame with full payout details per rep
```

### Simulator

```python
from src.simulator import simulate_incentives, compare_scenarios

# Run what-if simulation
result = simulate_incentives(sales_df, reps_df, params={
    "quota_adjustment_pct": 0.10,      # +10% quota
    "accelerator_rate": 0.20,           # 20% accelerator
    "region_filter": ["North America"], # Filter by region
})

# Compare two scenarios
comparison = compare_scenarios(base_params={}, scenario_params=params, 
                               sales_df=sales_df, reps_df=reps_df)
```

### Data Generator

```python
from src.data_generator import generate_all_data

datasets = generate_all_data(output_dir='data/', seed=42)
# Returns dict with sales_reps, transactions, incentive_plan, calendar
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `incentive_engine` | 19 | 100% |
| `simulator` | 18 | 100% |
| `data_generator` | 30 | 100% |
| **Total** | **67** | **100%** |

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **Python 3.10+** | Core language |
| **Pandas / NumPy** | Vectorized data processing |
| **SQLAlchemy** | Database ORM |
| **SQLite** | Embedded analytics database |
| **Streamlit** | Interactive web dashboard |
| **Plotly** | Interactive visualizations |
| **Faker** | Synthetic data generation |
| **pytest** | Unit testing framework |

---

## 📊 Database Schema

### Tables
- `sales_reps` – Master dimension for sales representatives
- `sales_transactions` – Fact table with closed-won deals
- `incentive_plan` – Commission tier configuration
- `calendar` – Date dimension with time intelligence
- `payout_results` – Calculated incentive payouts

### Analytical Views
- `rep_performance_summary` – Per-rep metrics with rankings
- `monthly_payout_trend` – Time-series analysis
- `region_wise_efficiency` – Regional aggregations
- `over_quota_analysis` – Performance band segmentation

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## 👤 Author

**Akshay**

- GitHub: [@Akshay](https://github.com/Akshay)
- LinkedIn: [Akshay](https://linkedin.com/in/akshay)

---

<p align="center">
  Made with ❤️ and ☕
</p>
