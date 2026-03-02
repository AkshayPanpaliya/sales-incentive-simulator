"""
Sales Incentive Compensation Simulator – Streamlit Dashboard
============================================================
A professional interactive dashboard for analyzing sales incentive plans,
exploring rep performance, and running what-if simulations.

Run with: streamlit run app.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config_loader import load_config
from src.data_generator import generate_all_data
from src.incentive_engine import run_incentive_engine
from src.simulator import simulate_incentives, compare_scenarios, get_scenario_summary

# ============================================================================
# Page Configuration
# ============================================================================
st.set_page_config(
    page_title="Sales Incentive Simulator",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #0F4C81;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    .highlight-box {
        background: linear-gradient(90deg, #0F4C81 0%, #2196F3 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Data Loading (Cached)
# ============================================================================
@st.cache_data
def load_data():
    """Load or generate all required data."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    
    required_files = {
        "sales_reps": os.path.join(data_dir, "sales_reps.csv"),
        "sales_transactions": os.path.join(data_dir, "sales_transactions.csv"),
        "payout_results": os.path.join(data_dir, "payout_results.csv"),
    }
    
    if all(os.path.isfile(p) for p in required_files.values()):
        return {
            "sales_reps": pd.read_csv(required_files["sales_reps"]),
            "sales_transactions": pd.read_csv(required_files["sales_transactions"]),
            "payout_results": pd.read_csv(required_files["payout_results"]),
        }
    else:
        st.warning("Data files not found. Please run `python src/main.py` first.")
        return None


@st.cache_data
def get_config():
    """Load configuration."""
    return load_config()


# ============================================================================
# Helper Functions
# ============================================================================
def format_currency(value):
    """Format number as currency."""
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    return f"${value:.0f}"


def format_percent(value):
    """Format number as percentage."""
    return f"{value:.1f}%"


def create_gauge_chart(value, title, max_val=200):
    """Create a gauge chart for attainment."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={'text': title, 'font': {'size': 16}},
        number={'suffix': '%', 'font': {'size': 24}},
        gauge={
            'axis': {'range': [0, max_val], 'tickwidth': 1},
            'bar': {'color': "#0F4C81"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 50], 'color': '#ffcdd2'},
                {'range': [50, 100], 'color': '#fff9c4'},
                {'range': [100, 150], 'color': '#c8e6c9'},
                {'range': [150, max_val], 'color': '#81c784'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    return fig


# ============================================================================
# Sidebar Navigation
# ============================================================================
def render_sidebar():
    """Render the sidebar with navigation and filters."""
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/money-bag.png", width=80)
        st.markdown("## 💰 Sales Incentive Simulator")
        st.markdown("---")
        
        page = st.radio(
            "📊 Navigation",
            ["🏠 Executive Dashboard", "👥 Rep Performance", "🔮 What-If Simulator", "📈 Data Explorer"],
            index=0
        )
        
        st.markdown("---")
        st.markdown("### 🎯 Quick Stats")
        
        data = load_data()
        if data:
            payout = data["payout_results"]
            st.metric("Total Reps", len(payout))
            st.metric("Total Revenue", format_currency(payout["total_sales"].sum()))
            st.metric("Total Payout", format_currency(payout["total_payout"].sum()))
        
        st.markdown("---")
        st.markdown(
            """
            <div style='text-align: center; color: #666; font-size: 0.8rem;'>
                Built with ❤️ using Streamlit<br>
                © 2024 Sales Incentive Simulator
            </div>
            """,
            unsafe_allow_html=True
        )
        
        return page


# ============================================================================
# Page 1: Executive Dashboard
# ============================================================================
def render_executive_dashboard(data, config):
    """Render the executive dashboard page."""
    st.markdown('<h1 class="main-header">📊 Executive Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Real-time overview of sales incentive performance</p>', unsafe_allow_html=True)
    
    payout = data["payout_results"]
    sales = data["sales_transactions"]
    
    # KPI Cards Row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_revenue = payout["total_sales"].sum()
    total_payout = payout["total_payout"].sum()
    avg_attainment = payout["attainment_pct"].mean() * 100
    pct_above_quota = (payout["attainment_pct"] >= 1.0).mean() * 100
    payout_ratio = (total_payout / total_revenue) * 100
    
    with col1:
        st.metric("💵 Total Revenue", format_currency(total_revenue), "+12.5% YoY")
    with col2:
        st.metric("💰 Total Payout", format_currency(total_payout), f"{payout_ratio:.1f}% of rev")
    with col3:
        st.metric("📈 Avg Attainment", f"{avg_attainment:.0f}%", "+8.2%")
    with col4:
        st.metric("🎯 Above Quota", f"{pct_above_quota:.0f}%", "+5.1%")
    with col5:
        st.metric("👥 Total Reps", len(payout), "100")
    
    st.markdown("---")
    
    # Charts Row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Revenue vs Quota by Region")
        region_data = payout.groupby("region").agg({
            "total_sales": "sum",
            "quota": "sum",
            "attainment_pct": "mean"
        }).reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Revenue',
            x=region_data['region'],
            y=region_data['total_sales'],
            marker_color='#0F4C81'
        ))
        fig.add_trace(go.Bar(
            name='Quota',
            x=region_data['region'],
            y=region_data['quota'],
            marker_color='#90CAF9'
        ))
        fig.update_layout(
            barmode='group',
            height=350,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🥧 Payout Distribution by Role")
        role_payout = payout.groupby("role")["total_payout"].sum().reset_index()
        fig = px.pie(
            role_payout,
            values='total_payout',
            names='role',
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4
        )
        fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📅 Monthly Revenue Trend")
        sales["deal_date"] = pd.to_datetime(sales["deal_date"])
        monthly = sales.groupby(sales["deal_date"].dt.to_period("M"))["deal_amount"].sum().reset_index()
        monthly["deal_date"] = monthly["deal_date"].astype(str)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=monthly["deal_date"],
            y=monthly["deal_amount"],
            mode='lines+markers',
            line=dict(color='#0F4C81', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(15, 76, 129, 0.1)'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="Month",
            yaxis_title="Revenue"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🎯 Attainment Distribution")
        fig = px.histogram(
            payout,
            x=payout["attainment_pct"] * 100,
            nbins=20,
            color_discrete_sequence=['#0F4C81']
        )
        fig.add_vline(x=100, line_dash="dash", line_color="red", annotation_text="Quota")
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="Attainment %",
            yaxis_title="Number of Reps"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Top Performers Table
    st.markdown("### 🏆 Top 10 Performers")
    top_performers = payout.nlargest(10, "total_payout")[
        ["rep_name", "region", "role", "total_sales", "quota", "attainment_pct", "total_payout"]
    ].copy()
    top_performers["attainment_pct"] = (top_performers["attainment_pct"] * 100).round(1).astype(str) + "%"
    top_performers["total_sales"] = top_performers["total_sales"].apply(format_currency)
    top_performers["quota"] = top_performers["quota"].apply(format_currency)
    top_performers["total_payout"] = top_performers["total_payout"].apply(format_currency)
    top_performers.columns = ["Rep Name", "Region", "Role", "Revenue", "Quota", "Attainment", "Payout"]
    
    st.dataframe(top_performers, use_container_width=True, hide_index=True)


# ============================================================================
# Page 2: Rep Performance
# ============================================================================
def render_rep_performance(data, config):
    """Render the rep performance analysis page."""
    st.markdown('<h1 class="main-header">👥 Rep Performance Analysis</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Deep dive into individual and team performance metrics</p>', unsafe_allow_html=True)
    
    payout = data["payout_results"]
    sales = data["sales_transactions"]
    reps = data["sales_reps"]
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_regions = st.multiselect(
            "🌍 Filter by Region",
            options=payout["region"].unique(),
            default=payout["region"].unique()
        )
    with col2:
        selected_roles = st.multiselect(
            "👔 Filter by Role",
            options=payout["role"].unique(),
            default=payout["role"].unique()
        )
    with col3:
        attainment_range = st.slider(
            "📊 Attainment Range (%)",
            min_value=0,
            max_value=int(payout["attainment_pct"].max() * 100) + 100,
            value=(0, int(payout["attainment_pct"].max() * 100) + 100)
        )
    
    # Apply filters
    filtered = payout[
        (payout["region"].isin(selected_regions)) &
        (payout["role"].isin(selected_roles)) &
        (payout["attainment_pct"] * 100 >= attainment_range[0]) &
        (payout["attainment_pct"] * 100 <= attainment_range[1])
    ]
    
    st.markdown(f"**Showing {len(filtered)} of {len(payout)} reps**")
    st.markdown("---")
    
    # Scatter Plot
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📊 Revenue vs Payout by Rep")
        fig = px.scatter(
            filtered,
            x="total_sales",
            y="total_payout",
            color="region",
            size="attainment_pct",
            hover_name="rep_name",
            hover_data=["role", "quota"],
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig.update_layout(
            height=450,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Total Revenue ($)",
            yaxis_title="Total Payout ($)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📈 Performance Bands")
        
        def get_band(att):
            if att >= 1.5:
                return "🔥 Superstar (150%+)"
            elif att >= 1.0:
                return "✅ Above Quota"
            elif att >= 0.5:
                return "⚠️ On Track"
            else:
                return "🔴 At Risk"
        
        filtered["band"] = filtered["attainment_pct"].apply(get_band)
        band_counts = filtered["band"].value_counts()
        
        fig = px.bar(
            x=band_counts.values,
            y=band_counts.index,
            orientation='h',
            color=band_counts.index,
            color_discrete_map={
                "🔥 Superstar (150%+)": "#4CAF50",
                "✅ Above Quota": "#8BC34A",
                "⚠️ On Track": "#FF9800",
                "🔴 At Risk": "#F44336"
            }
        )
        fig.update_layout(
            height=450,
            showlegend=False,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Number of Reps",
            yaxis_title=""
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Heatmap
    st.markdown("### 🗺️ Performance Heatmap: Region × Role")
    heatmap_data = filtered.pivot_table(
        values="attainment_pct",
        index="region",
        columns="role",
        aggfunc="mean"
    ) * 100
    
    fig = px.imshow(
        heatmap_data,
        color_continuous_scale="RdYlGn",
        aspect="auto",
        text_auto=".0f"
    )
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)
    
    # Rep Details Table
    st.markdown("### 📋 Rep Details")
    display_df = filtered[
        ["rep_name", "region", "role", "total_sales", "quota", "attainment_pct", 
         "base_commission", "accelerator_bonus", "total_payout"]
    ].copy()
    display_df["attainment_pct"] = (display_df["attainment_pct"] * 100).round(1)
    display_df = display_df.sort_values("total_payout", ascending=False)
    
    st.dataframe(
        display_df.style.format({
            "total_sales": "${:,.0f}",
            "quota": "${:,.0f}",
            "attainment_pct": "{:.1f}%",
            "base_commission": "${:,.0f}",
            "accelerator_bonus": "${:,.0f}",
            "total_payout": "${:,.0f}"
        }).background_gradient(subset=["attainment_pct"], cmap="RdYlGn"),
        use_container_width=True,
        hide_index=True
    )


# ============================================================================
# Page 3: What-If Simulator
# ============================================================================
def render_simulator(data, config):
    """Render the what-if simulation page."""
    st.markdown('<h1 class="main-header">🔮 What-If Simulator</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Model alternative compensation scenarios and see the impact</p>', unsafe_allow_html=True)
    
    reps = data["sales_reps"]
    sales = data["sales_transactions"]
    payout = data["payout_results"]
    
    # Simulation Parameters
    st.markdown("### ⚙️ Simulation Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📊 Quota Adjustment**")
        quota_adj = st.slider(
            "Adjust all quotas by",
            min_value=-50,
            max_value=50,
            value=0,
            step=5,
            format="%d%%"
        )
    
    with col2:
        st.markdown("**🚀 Accelerator Rate**")
        accel_rate = st.slider(
            "Accelerator commission rate",
            min_value=5,
            max_value=30,
            value=15,
            step=1,
            format="%d%%"
        )
    
    with col3:
        st.markdown("**🎯 Accelerator Threshold**")
        accel_threshold = st.slider(
            "Accelerator triggers at",
            min_value=75,
            max_value=150,
            value=100,
            step=5,
            format="%d%% quota"
        )
    
    # Commission Tier Overrides
    st.markdown("### 📈 Commission Tier Rates")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        tier1_rate = st.number_input("Tier 1 (0-50%)", min_value=0.0, max_value=20.0, value=2.0, step=0.5, format="%.1f")
    with col2:
        tier2_rate = st.number_input("Tier 2 (50-100%)", min_value=0.0, max_value=20.0, value=5.0, step=0.5, format="%.1f")
    with col3:
        tier3_rate = st.number_input("Tier 3 (100-150%)", min_value=0.0, max_value=20.0, value=8.0, step=0.5, format="%.1f")
    with col4:
        tier4_rate = st.number_input("Tier 4 (150%+)", min_value=0.0, max_value=25.0, value=12.0, step=0.5, format="%.1f")
    
    # Region/Role Filters
    col1, col2 = st.columns(2)
    with col1:
        region_filter = st.multiselect(
            "🌍 Filter by Region (leave empty for all)",
            options=reps["region"].unique()
        )
    with col2:
        role_filter = st.multiselect(
            "👔 Filter by Role (leave empty for all)",
            options=reps["role"].unique()
        )
    
    st.markdown("---")
    
    # Run Simulation Button
    if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
        with st.spinner("Running simulation..."):
            # Build params
            scenario_params = {
                "quota_adjustment_pct": quota_adj / 100,
                "accelerator_rate": accel_rate / 100,
                "accelerator_threshold": accel_threshold / 100,
                "commission_rate_override": {
                    0: tier1_rate / 100,
                    1: tier2_rate / 100,
                    2: tier3_rate / 100,
                    3: tier4_rate / 100,
                }
            }
            
            if region_filter:
                scenario_params["region_filter"] = region_filter
            if role_filter:
                scenario_params["role_filter"] = role_filter
            
            # Run simulations
            try:
                base_result = simulate_incentives(sales, reps, params={})
                scenario_result = simulate_incentives(sales, reps, params=scenario_params)
                
                base_summary = get_scenario_summary(base_result)
                scenario_summary = get_scenario_summary(scenario_result)
                
                # Display Results
                st.markdown("### 📊 Simulation Results")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("#### 📍 Base Scenario")
                    st.metric("Total Payout", format_currency(base_summary["total_payout"]))
                    st.metric("Avg Attainment", f"{base_summary['avg_attainment']*100:.1f}%")
                    st.metric("% Above Quota", f"{base_summary['pct_above_quota']*100:.1f}%")
                
                with col2:
                    st.markdown("#### 🔮 New Scenario")
                    st.metric("Total Payout", format_currency(scenario_summary["total_payout"]))
                    st.metric("Avg Attainment", f"{scenario_summary['avg_attainment']*100:.1f}%")
                    st.metric("% Above Quota", f"{scenario_summary['pct_above_quota']*100:.1f}%")
                
                with col3:
                    st.markdown("#### 📈 Delta")
                    payout_delta = scenario_summary["total_payout"] - base_summary["total_payout"]
                    payout_pct = (payout_delta / base_summary["total_payout"]) * 100 if base_summary["total_payout"] > 0 else 0
                    
                    st.metric(
                        "Payout Change",
                        format_currency(abs(payout_delta)),
                        f"{payout_pct:+.1f}%",
                        delta_color="inverse" if payout_delta > 0 else "normal"
                    )
                    
                    att_delta = (scenario_summary["avg_attainment"] - base_summary["avg_attainment"]) * 100
                    st.metric("Attainment Change", f"{abs(att_delta):.1f}%", f"{att_delta:+.1f}%")
                
                # Comparison Chart
                st.markdown("### 📊 Payout Comparison by Rep")
                comparison = base_result[["rep_name", "total_payout"]].merge(
                    scenario_result[["rep_name", "total_payout"]],
                    on="rep_name",
                    suffixes=("_base", "_scenario")
                )
                comparison["delta"] = comparison["total_payout_scenario"] - comparison["total_payout_base"]
                comparison = comparison.sort_values("delta", ascending=True)
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='Base',
                    y=comparison["rep_name"],
                    x=comparison["total_payout_base"],
                    orientation='h',
                    marker_color='#90CAF9'
                ))
                fig.add_trace(go.Bar(
                    name='Scenario',
                    y=comparison["rep_name"],
                    x=comparison["total_payout_scenario"],
                    orientation='h',
                    marker_color='#0F4C81'
                ))
                fig.update_layout(
                    barmode='group',
                    height=max(400, len(comparison) * 25),
                    margin=dict(l=20, r=20, t=30, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error running simulation: {str(e)}")
    else:
        st.info("👆 Adjust the parameters above and click 'Run Simulation' to see results")


# ============================================================================
# Page 4: Data Explorer
# ============================================================================
def render_data_explorer(data, config):
    """Render the data explorer page."""
    st.markdown('<h1 class="main-header">📈 Data Explorer</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Explore and download the underlying data</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["👥 Sales Reps", "💰 Transactions", "📊 Payout Results", "⚙️ Configuration"])
    
    with tab1:
        st.markdown("### Sales Representatives")
        st.dataframe(data["sales_reps"], use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Download CSV",
            data["sales_reps"].to_csv(index=False),
            "sales_reps.csv",
            "text/csv"
        )
    
    with tab2:
        st.markdown("### Sales Transactions")
        st.markdown(f"**{len(data['sales_transactions']):,} transactions**")
        st.dataframe(data["sales_transactions"].head(1000), use_container_width=True, hide_index=True)
        st.caption("Showing first 1,000 rows")
        st.download_button(
            "📥 Download CSV",
            data["sales_transactions"].to_csv(index=False),
            "sales_transactions.csv",
            "text/csv"
        )
    
    with tab3:
        st.markdown("### Payout Results")
        st.dataframe(
            data["payout_results"].style.format({
                "total_sales": "${:,.0f}",
                "quota": "${:,.0f}",
                "attainment_pct": "{:.2%}",
                "base_commission": "${:,.0f}",
                "accelerator_bonus": "${:,.0f}",
                "total_payout": "${:,.0f}",
                "payout_to_revenue_ratio": "{:.2%}"
            }),
            use_container_width=True,
            hide_index=True
        )
        st.download_button(
            "📥 Download CSV",
            data["payout_results"].to_csv(index=False),
            "payout_results.csv",
            "text/csv"
        )
    
    with tab4:
        st.markdown("### Incentive Plan Configuration")
        st.json(config)


# ============================================================================
# Main App
# ============================================================================
def main():
    """Main application entry point."""
    page = render_sidebar()
    
    data = load_data()
    config = get_config()
    
    if data is None:
        st.error("⚠️ Data not found! Please run `python src/main.py` first to generate the data.")
        st.code("python src/main.py", language="bash")
        return
    
    if page == "🏠 Executive Dashboard":
        render_executive_dashboard(data, config)
    elif page == "👥 Rep Performance":
        render_rep_performance(data, config)
    elif page == "🔮 What-If Simulator":
        render_simulator(data, config)
    elif page == "📈 Data Explorer":
        render_data_explorer(data, config)


if __name__ == "__main__":
    main()
