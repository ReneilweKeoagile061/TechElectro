import os
import pyodbc
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TechElectro Inc. | Inventory Analytics Engine",
    page_icon="https://img.icons8.com/color/48/analytics.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS System ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;500;600;700&display=swap');
    
    :root {
        --btc-green: #1e8a3c;
        --btc-dark-green: #166e2f;
        --btc-light-green: #e6f4e9;
        --white: #ffffff;
        --gray-100: #f5f5f7;
        --gray-200: #e5e5ea;
        --gray-600: #636366;
        --gray-800: #1d1d1f;
        --red-500: #e74c3c;
        --amber-500: #d97706;
        --blue-500: #2daadf;
    }

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif !important;
    }
    
    .stApp {
        background-color: var(--gray-100);
        color: var(--gray-800);
    }
    
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Apple Segmented Control Tab Bar */
    div[data-testid="stTabs"] {
        background-color: transparent !important;
    }
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
        display: none !important;
    }
    div[data-baseweb="tab-list"] {
        gap: 4px !important;
        background-color: var(--gray-200) !important;
        padding: 4px !important;
        border-radius: 10px !important;
        border: none !important;
        display: inline-flex !important;
    }
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        color: var(--gray-600) !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        border-radius: 7px !important;
        transition: all 0.2s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: var(--gray-800) !important;
        background-color: rgba(255,255,255,0.5) !important;
    }
    button[aria-selected="true"] {
        background-color: var(--white) !important;
        color: var(--btc-dark-green) !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
    }

    /* Apple Cards */
    .apple-card {
        background-color: var(--white);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 16px;
        padding: 22px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
    }

    #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Database Connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_db_connection():
    try:
        return pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=localhost;'
            'DATABASE=tech_electro;'
            'Trusted_Connection=yes;',
            timeout=5
        )
    except Exception:
        return None

@st.cache_data(ttl=300)
def load_data():
    conn = get_db_connection()
    if not conn:
        return None
    query = """
    SELECT s.sales_id, s.product_id, p.product_category, p.promotions,
           s.sales_date, s.inventory_quantity, s.product_cost,
           e.gdp, e.inflation_rate, e.seasonal_factor
    FROM sales_data s
    JOIN product_information p ON s.product_id = p.product_id
    LEFT JOIN external_factors e ON s.sales_date = e.sales_date;
    """
    try:
        df = pd.read_sql(query, conn)
        df['sales_date'] = pd.to_datetime(df['sales_date'])
        return df
    except Exception:
        return None

df_raw = load_data()

# ── Sidebar Controls ──────────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
    <div style="width:36px; height:36px; border-radius:8px; background:linear-gradient(135deg, #1e8a3c, #39b54a); display:flex; align-items:center; justify-content:center; color:white; font-weight:800;">TE</div>
    <div>
        <div style="font-weight:700; color:#1d1d1f;">TechElectro</div>
        <div style="font-size:0.68rem; color:#636366;">Inventory Analytics</div>
    </div>
</div>
""", unsafe_allow_html=True)

if df_raw is not None:
    categories = sorted(df_raw['product_category'].unique().tolist())
    selected_categories = st.sidebar.multiselect("Product Category", options=categories, default=categories)
    promo_filter = st.sidebar.radio("Promotion Status", options=["All Products", "Promoted Only (Yes)", "Non-Promoted (No)"])
    
    st.sidebar.markdown("---")
    overstock_ratio = st.sidebar.slider("Overstock Ratio Threshold", 0.2, 0.8, 0.5, 0.05)
    lead_time_days = st.sidebar.slider("Supplier Lead Time (Days)", 1, 30, 7)
    service_level = st.sidebar.select_slider("Target Service Level", options=["90% (Z=1.28)", "95% (Z=1.65)", "99% (Z=2.33)"], value="95% (Z=1.65)")
    
    z_map = {"90% (Z=1.28)": 1.28, "95% (Z=1.65)": 1.65, "99% (Z=2.33)": 2.33}
    z_score = z_map[service_level]

    search_sku = st.sidebar.text_input("Product ID Search", placeholder="e.g. 9402")

    # Reactive Filtering
    df = df_raw[df_raw['product_category'].isin(selected_categories)].copy()
    if promo_filter == "Promoted Only (Yes)":
        df = df[df['promotions'] == 'Yes']
    elif promo_filter == "Non-Promoted (No)":
        df = df[df['promotions'] == 'No']
    if search_sku.strip():
        try:
            df = df[df['product_id'] == int(search_sku.strip())]
        except ValueError:
            pass

# ── Main Header Banner ────────────────────────────────────────────────────────
st.markdown("""
<div class="apple-card" style="margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
    <div>
        <div style="font-size:1.3rem; font-weight:700; color:#1d1d1f;">TechElectro Inventory Optimization Platform</div>
        <div style="font-size:0.8rem; color:#636366; margin-top:2px;">Data-Driven Supply Chain Management, Stockout Prevention & Working Capital Analytics</div>
    </div>
    <div style="background:#e6f4e9; color:#166e2f; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:700;">
        DP-300 Azure Pipeline
    </div>
</div>
""", unsafe_allow_html=True)

if df_raw is not None and len(df) > 0:
    # Calculations
    cat_stats = df.groupby('product_category').agg(
        avg_demand=('inventory_quantity', 'mean'),
        category_stdev=('inventory_quantity', 'std'),
        total_units=('inventory_quantity', 'sum')
    ).reset_index()

    df_sku = df.groupby(['product_id', 'product_category', 'promotions']).agg(
        sku_demand=('inventory_quantity', 'mean'),
        sku_cost=('product_cost', 'mean')
    ).reset_index()

    df_sku = df_sku.merge(cat_stats[['product_category', 'avg_demand', 'category_stdev']], on='product_category')
    df_sku['capital_tied_up'] = df_sku['sku_demand'] * df_sku['sku_cost']
    df_sku['is_overstock'] = df_sku['sku_demand'] < (df_sku['avg_demand'] * overstock_ratio)
    df_sku['lead_time_demand'] = df_sku['sku_demand'] * lead_time_days
    df_sku['safety_stock'] = z_score * df_sku['category_stdev'].fillna(0) * (lead_time_days ** 0.5)
    df_sku['reorder_point'] = df_sku['lead_time_demand'] + df_sku['safety_stock']

    overstock_df = df_sku[df_sku['is_overstock']].sort_values('capital_tied_up', ascending=False)
    total_capital_risk = overstock_df['capital_tied_up'].sum()
    flagged_skus = len(overstock_df)
    total_units_moved = df['inventory_quantity'].sum()

    # ── Top Metric Cards ──────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="apple-card" style="border-top:4px solid #e74c3c;"><div style="font-size:0.68rem; color:#636366; font-weight:700; text-transform:uppercase;">Capital at Risk</div><div style="font-size:1.8rem; font-weight:800; color:#c0392b;">${total_capital_risk:,.2f}</div><div style="font-size:0.72rem; color:#e74c3c;">Demand < {int(overstock_ratio*100)}% Baseline</div></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="apple-card" style="border-top:4px solid #d97706;"><div style="font-size:0.68rem; color:#636366; font-weight:700; text-transform:uppercase;">Flagged Overstock SKUs</div><div style="font-size:1.8rem; font-weight:800; color:#b45309;">{flagged_skus} SKUs</div><div style="font-size:0.72rem; color:#d97706;">Low-Velocity Target</div></div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="apple-card" style="border-top:4px solid #1e8a3c;"><div style="font-size:0.68rem; color:#636366; font-weight:700; text-transform:uppercase;">Sales Volume Analyzed</div><div style="font-size:1.8rem; font-weight:800; color:#166e2f;">{total_units_moved:,} Units</div><div style="font-size:0.72rem; color:#1e8a3c;">Filtered Sales</div></div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""<div class="apple-card" style="border-top:4px solid #2daadf;"><div style="font-size:0.68rem; color:#636366; font-weight:700; text-transform:uppercase;">Target Service Level</div><div style="font-size:1.8rem; font-weight:800; color:#0284c7;">{service_level.split()[0]}</div><div style="font-size:0.72rem; color:#0284c7;">Lead Time: {lead_time_days} Days</div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # ── Interactive Tabs ──────────────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "Executive Overview",
        "Overstocking & Capital Risk",
        "Stockouts & Customer Satisfaction",
        "Demand Trends & Macro Drivers",
        "Actionable Plan & Export"
    ])

    # --- TAB 1: EXECUTIVE OVERVIEW ---
    with t1:
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown("<div class='apple-card'><div style='font-weight:700; margin-bottom:10px;'>Capital Tied Up in Low-Velocity Stock ($k)</div>", unsafe_allow_html=True)
            cap_cat = overstock_df.groupby('product_category')['capital_tied_up'].sum().reset_index()
            cap_cat['capital_k'] = cap_cat['capital_tied_up'] / 1000
            
            fig1 = px.bar(cap_cat, x='product_category', y='capital_k', text_auto='.1f',
                          labels={'product_category': 'Category', 'capital_k': 'Capital ($k)'},
                          color_discrete_sequence=['#e74c3c'])
            fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_b:
            st.markdown("<div class='apple-card'><div style='font-weight:700; margin-bottom:10px;'>Demand Volatility by Category (Std Dev σ)</div>", unsafe_allow_html=True)
            fig2 = px.bar(cat_stats, x='product_category', y='category_stdev', text_auto='.1f',
                          labels={'product_category': 'Category', 'category_stdev': 'Standard Deviation'},
                          color_discrete_sequence=['#1e8a3c'])
            fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 2: OVERSTOCKING & CAPITAL RISK ---
    with t2:
        ratio_pct = int(overstock_ratio * 100)
        st.markdown(f"<div class='apple-card'><div style='font-weight:700; margin-bottom:6px;'>Low-Velocity Overstock Register</div><div style='font-size:0.75rem; color:#636366; margin-bottom:14px;'>Flagged products with daily demand < {ratio_pct}% of category baseline.</div>", unsafe_allow_html=True)
        if len(overstock_df) > 0:
            st.dataframe(
                overstock_df[['product_id', 'product_category', 'promotions', 'sku_demand', 'sku_cost', 'capital_tied_up']]
                .rename(columns={'product_id': 'Product ID', 'product_category': 'Category', 'promotions': 'Promoted', 'sku_demand': 'Avg Daily Demand', 'sku_cost': 'Unit Cost ($)', 'capital_tied_up': 'Capital Tied Up ($)'})
                .style.format({'Avg Daily Demand': '{:.1f}', 'Unit Cost ($)': '${:,.2f}', 'Capital Tied Up ($)': '${:,.2f}'}),
                use_container_width=True
            )
        else:
            st.info("No overstock products flagged at current threshold.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 3: STOCKOUTS & CUSTOMER SATISFACTION (INTERACTIVE SIDE-BY-SIDE BARS - NO OVERLAYS!) ---
    with t3:
        st.markdown(f"<div class='apple-card'><div style='font-weight:700; margin-bottom:6px;'>Stockout Exposure & Reorder Targets</div><div style='font-size:0.75rem; color:#636366; margin-bottom:14px;'>Grouped side-by-side comparison of daily demand vs reorder point target (Target Service Level: {service_level}).</div>", unsafe_allow_html=True)
        
        top_reorder = df_sku.sort_values('reorder_point', ascending=False).head(10).copy()
        top_reorder['Product Label'] = top_reorder.apply(lambda r: f"ID {r.product_id} ({r.product_category[:4]})", axis=1)
        
        # Plotly Grouped Bar Chart — NO OVERLAYS!
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=top_reorder['Product Label'], y=top_reorder['sku_demand'], name='Avg Daily Demand', marker_color='#1e8a3c'))
        fig3.add_trace(go.Bar(x=top_reorder['Product Label'], y=top_reorder['reorder_point'], name='Reorder Point Target', marker_color='#e74c3c'))
        
        fig3.update_layout(barmode='group', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                           margin=dict(t=10, b=10, l=10, r=10), height=340, legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 4: DEMAND TRENDS & MACRO DRIVERS ---
    with t4:
        st.markdown("<div class='apple-card'><div style='font-weight:700; margin-bottom:6px;'>Monthly Demand Trends (2018–2022)</div><div style='font-size:0.75rem; color:#636366; margin-bottom:14px;'>Interactive historical sales volume trends over time.</div>", unsafe_allow_html=True)
        
        trend_df = df.groupby(['product_category', pd.Grouper(key='sales_date', freq='ME')])['inventory_quantity'].sum().reset_index()
        fig4 = px.line(trend_df, x='sales_date', y='inventory_quantity', color='product_category',
                       labels={'sales_date': 'Month', 'inventory_quantity': 'Units Moved', 'product_category': 'Category'},
                       color_discrete_sequence=['#1e8a3c', '#2daadf', '#d97706', '#e74c3c'])
        fig4.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- TAB 5: ACTIONABLE PLAN & CSV EXPORT ---
    with t5:
        st.markdown("<div class='apple-card'><div style='font-weight:700; margin-bottom:6px;'>Procurement & Reorder Action List</div><div style='font-size:0.75rem; color:#636366; margin-bottom:14px;'>Exportable procurement action plan generated dynamically based on active risk parameters.</div>", unsafe_allow_html=True)
        
        action_df = df_sku[['product_id', 'product_category', 'promotions', 'sku_demand', 'lead_time_demand', 'safety_stock', 'reorder_point', 'capital_tied_up', 'is_overstock']].copy()
        action_df.columns = ['Product ID', 'Category', 'Promoted', 'Avg Daily Demand', 'Lead Time Demand', 'Safety Stock Buffer', 'Calculated Reorder Point', 'Capital Tied Up ($)', 'Overstock Risk Flag']
        
        csv_data = action_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Procurement Reorder Action List (CSV)", data=csv_data, file_name="TechElectro_Reorder_Action_List.csv", mime="text/csv")
        
        st.dataframe(action_df.style.format({
            'Avg Daily Demand': '{:.1f}', 'Lead Time Demand': '{:.1f}', 'Safety Stock Buffer': '{:.1f}',
            'Calculated Reorder Point': '{:.1f}', 'Capital Tied Up ($)': '${:,.2f}'
        }), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.warning("Database `tech_electro` connection unavailable. Please check SQL Server connection.")
