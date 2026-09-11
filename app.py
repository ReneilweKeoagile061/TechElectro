import os
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pymssql
import streamlit as st


# =============================================================================
# Page configuration
# =============================================================================
st.set_page_config(
    page_title="TechElectro Inc. | Inventory Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# Styling
# =============================================================================
st.markdown(
    """
    <style>
        :root {
            --green: #1e8a3c;
            --green-dark: #166e2f;
            --green-light: #e6f4e9;
            --white: #ffffff;
            --gray-100: #f5f5f7;
            --gray-200: #e5e5ea;
            --gray-600: #636366;
            --gray-800: #1d1d1f;
            --red: #e74c3c;
            --amber: #d97706;
            --blue: #0284c7;
        }

        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        }

        .stApp {
            background: var(--gray-100);
            color: var(--gray-800);
        }

        header[data-testid="stHeader"] {
            background: transparent !important;
        }

        #MainMenu, footer {
            visibility: hidden;
        }

        div[data-testid="stTabs"] {
            background: transparent !important;
        }

        div[data-baseweb="tab-highlight"],
        div[data-baseweb="tab-border"] {
            display: none !important;
        }

        div[data-baseweb="tab-list"] {
            gap: 4px !important;
            background: var(--gray-200) !important;
            padding: 4px !important;
            border-radius: 10px !important;
            border: none !important;
            display: inline-flex !important;
            max-width: 100%;
        }

        button[data-baseweb="tab"] {
            background: transparent !important;
            border: none !important;
            color: var(--gray-600) !important;
            font-size: 0.85rem !important;
            font-weight: 600 !important;
            padding: 8px 18px !important;
            border-radius: 7px !important;
        }

        button[data-baseweb="tab"]:hover {
            color: var(--gray-800) !important;
            background: rgba(255, 255, 255, 0.5) !important;
        }

        button[aria-selected="true"] {
            background: var(--white) !important;
            color: var(--green-dark) !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08) !important;
        }

        .apple-card {
            background: var(--white);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        }

        .metric-card {
            background: var(--white);
            border: 1px solid rgba(0, 0, 0, 0.06);
            border-radius: 16px;
            padding: 18px 20px;
            min-height: 125px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        }

        .metric-label {
            font-size: 0.68rem;
            color: var(--gray-600);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        .metric-value {
            font-size: 1.75rem;
            font-weight: 800;
            margin-top: 5px;
        }

        .metric-note {
            font-size: 0.72rem;
            margin-top: 4px;
        }

        .section-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 4px;
        }

        .section-subtitle {
            font-size: 0.75rem;
            color: var(--gray-600);
            margin-bottom: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Database configuration and connection
# =============================================================================
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a flat Streamlit secret, with an environment-variable fallback."""
    try:
        if name in st.secrets:
            val = st.secrets[name]
            if val is not None:
                return str(val)
    except Exception:
        pass
    return os.getenv(name, default)


def _get_sql_config() -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    server = _get_secret("server") or _get_secret("AZURE_SQL_SERVER")
    database = _get_secret("database", "tech_electro") or _get_secret("AZURE_SQL_DATABASE", "tech_electro")
    username = _get_secret("username") or _get_secret("AZURE_SQL_USERNAME")
    password = _get_secret("password") or _get_secret("AZURE_SQL_PASSWORD")

    return server, database, username, password


@st.cache_resource(show_spinner=False)
def get_db_connection() -> Optional["pymssql.Connection"]:
    """Create and cache an encrypted Azure SQL connection via FreeTDS (pymssql)."""
    server, database, username, password = _get_sql_config()

    if not all([server, database, username, password]):
        return None

    try:
        return pymssql.connect(
            server=server,
            user=username,
            password=password,
            database=database,
            timeout=15,
            login_timeout=15,
        )
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner="Loading inventory data…")
def load_data() -> Optional[pd.DataFrame]:
    """Load the dashboard dataset from Azure SQL."""
    conn = get_db_connection()
    if conn is None:
        return None

    query = """
        SELECT
            s.sales_id,
            s.product_id,
            p.product_category,
            p.promotions,
            s.sales_date,
            s.inventory_quantity,
            s.product_cost,
            e.gdp,
            e.inflation_rate,
            e.seasonal_factor
        FROM sales_data AS s
        INNER JOIN product_information AS p
            ON s.product_id = p.product_id
        LEFT JOIN external_factors AS e
            ON s.sales_date = e.sales_date;
    """

    try:
        df = pd.read_sql(query, conn)
        df["sales_date"] = pd.to_datetime(df["sales_date"], errors="coerce")
        df["inventory_quantity"] = pd.to_numeric(df["inventory_quantity"], errors="coerce")
        df["product_cost"] = pd.to_numeric(df["product_cost"], errors="coerce")
        df = df.dropna(subset=["product_id", "product_category", "sales_date", "inventory_quantity"])
        return df
    except Exception:
        return None


# =============================================================================
# Reusable UI helpers
# =============================================================================
def render_metric_card(label: str, value: str, note: str, accent: str, note_color: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card" style="border-top:4px solid {accent};">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color:{accent};">{value}</div>
            <div class="metric-note" style="color:{note_color};">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_layout(fig: go.Figure, height: int = 320) -> go.Figure:
    """Apply consistent dashboard styling to a Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=10),
        height=height,
        font=dict(family="Arial, sans-serif", color="#1d1d1f"),
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


# =============================================================================
# Load data
# =============================================================================
df_raw = load_data()


# =============================================================================
# Sidebar
# =============================================================================
st.sidebar.markdown(
    """
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
        <div style="width:36px; height:36px; border-radius:8px; background:linear-gradient(135deg,#1e8a3c,#39b54a); display:flex; align-items:center; justify-content:center; color:white; font-weight:800;">TE</div>
        <div>
            <div style="font-weight:700; color:#1d1d1f;">TechElectro</div>
            <div style="font-size:0.68rem; color:#636366;">Inventory Analytics</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Header
# =============================================================================
st.markdown(
    """
    <div class="apple-card" style="margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; gap:20px;">
        <div>
            <div style="font-size:1.3rem; font-weight:700; color:#1d1d1f;">TechElectro Inventory Optimization Platform</div>
            <div style="font-size:0.8rem; color:#636366; margin-top:2px;">Data-driven supply chain management, stockout prevention & working capital analytics</div>
        </div>
        <div style="background:#e6f4e9; color:#166e2f; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:700; white-space:nowrap;">
            Azure SQL Pipeline
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Connection/data error states
# =============================================================================
if df_raw is None:
    server, database, username, password = _get_sql_config()
    if not all([server, database, username, password]):
        st.error(
            "Azure SQL is not configured. Add `server`, `database`, `username`, and `password` "
            "to Streamlit Cloud Secrets."
        )
    else:
        st.error(
            "The Azure SQL connection could not be established. Check the server name, "
            "credentials, database permissions, and Azure SQL firewall rules."
        )
    st.stop()


if df_raw.empty:
    st.warning("The database connection succeeded, but the dashboard query returned no records.")
    st.stop()


# =============================================================================
# Sidebar controls
# =============================================================================
categories = sorted(df_raw["product_category"].dropna().astype(str).unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Product Category",
    options=categories,
    default=categories,
)

promo_filter = st.sidebar.radio(
    "Promotion Status",
    options=["All Products", "Promoted Only (Yes)", "Non-Promoted (No)"],
)

st.sidebar.markdown("---")

overstock_ratio = st.sidebar.slider(
    "Overstock Ratio Threshold",
    min_value=0.20,
    max_value=0.80,
    value=0.50,
    step=0.05,
    help="Flags SKUs whose average inventory quantity is below this share of their category baseline.",
)

lead_time_days = st.sidebar.slider(
    "Supplier Lead Time (Days)",
    min_value=1,
    max_value=30,
    value=7,
)

service_level = st.sidebar.select_slider(
    "Target Service Level",
    options=["90% (Z=1.28)", "95% (Z=1.65)", "99% (Z=2.33)"],
    value="95% (Z=1.65)",
)

z_map = {
    "90% (Z=1.28)": 1.28,
    "95% (Z=1.65)": 1.65,
    "99% (Z=2.33)": 2.33,
}
z_score = z_map[service_level]

search_sku = st.sidebar.text_input(
    "Product ID Search",
    placeholder="e.g. 9402",
)

if st.sidebar.button("Refresh Data", use_container_width=True):
    load_data.clear()
    get_db_connection.clear()
    st.rerun()


# =============================================================================
# Reactive filtering
# =============================================================================
df = df_raw[df_raw["product_category"].isin(selected_categories)].copy()

if promo_filter == "Promoted Only (Yes)":
    df = df[df["promotions"].astype(str).str.strip().str.lower() == "yes"]
elif promo_filter == "Non-Promoted (No)":
    df = df[df["promotions"].astype(str).str.strip().str.lower() == "no"]

if search_sku.strip():
    try:
        df = df[df["product_id"] == int(search_sku.strip())]
    except ValueError:
        st.sidebar.warning("Product ID must be numeric.")


if df.empty:
    st.info("No records match the current filters. Adjust the sidebar filters and try again.")
    st.stop()


# =============================================================================
# Analytics calculations
# =============================================================================
cat_stats = (
    df.groupby("product_category", dropna=False)
    .agg(
        avg_demand=("inventory_quantity", "mean"),
        category_stdev=("inventory_quantity", "std"),
        total_units=("inventory_quantity", "sum"),
    )
    .reset_index()
)

cat_stats["category_stdev"] = cat_stats["category_stdev"].fillna(0)

df_sku = (
    df.groupby(["product_id", "product_category", "promotions"], dropna=False)
    .agg(
        sku_demand=("inventory_quantity", "mean"),
        sku_cost=("product_cost", "mean"),
    )
    .reset_index()
)

df_sku = df_sku.merge(
    cat_stats[["product_category", "avg_demand", "category_stdev"]],
    on="product_category",
    how="left",
)

df_sku["sku_cost"] = df_sku["sku_cost"].fillna(0)
df_sku["capital_tied_up"] = df_sku["sku_demand"] * df_sku["sku_cost"]
df_sku["is_overstock"] = df_sku["sku_demand"] < (df_sku["avg_demand"] * overstock_ratio)
df_sku["lead_time_demand"] = df_sku["sku_demand"] * lead_time_days
df_sku["safety_stock"] = z_score * df_sku["category_stdev"] * np.sqrt(lead_time_days)
df_sku["reorder_point"] = df_sku["lead_time_demand"] + df_sku["safety_stock"]

overstock_df = df_sku[df_sku["is_overstock"]].sort_values(
    "capital_tied_up", ascending=False
)

total_capital_risk = float(overstock_df["capital_tied_up"].sum())
flagged_skus = int(len(overstock_df))
total_units_moved = int(df["inventory_quantity"].sum())


# =============================================================================
# KPI cards
# =============================================================================
m1, m2, m3, m4 = st.columns(4)

with m1:
    render_metric_card(
        "Capital at Risk",
        f"${total_capital_risk:,.2f}",
        f"Demand < {int(overstock_ratio * 100)}% of baseline",
        "#c0392b",
        "#e74c3c",
    )

with m2:
    render_metric_card(
        "Flagged Overstock SKUs",
        f"{flagged_skus:,} SKUs",
        "Low-velocity target",
        "#b45309",
        "#d97706",
    )

with m3:
    render_metric_card(
        "Sales Volume Analyzed",
        f"{total_units_moved:,} Units",
        "Filtered sales volume",
        "#166e2f",
        "#1e8a3c",
    )

with m4:
    render_metric_card(
        "Target Service Level",
        service_level.split()[0],
        f"Lead time: {lead_time_days} days",
        "#0284c7",
        "#0284c7",
    )

st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)


# =============================================================================
# Dashboard tabs
# =============================================================================
t1, t2, t3, t4, t5 = st.tabs(
    [
        "Executive Overview",
        "Overstocking & Capital Risk",
        "Stockouts & Customer Satisfaction",
        "Demand Trends & Macro Drivers",
        "Actionable Plan & Export",
    ]
)


# =============================================================================
# TAB 1: Executive overview
# =============================================================================
with t1:
    c_a, c_b = st.columns(2)

    with c_a:
        st.markdown(
            """
            <div class="apple-card">
                <div class="section-title">Capital Tied Up in Low-Velocity Stock ($k)</div>
                <div class="section-subtitle">Capital exposure from SKUs flagged as overstock.</div>
            """,
            unsafe_allow_html=True,
        )

        cap_cat = (
            overstock_df.groupby("product_category", as_index=False)["capital_tied_up"]
            .sum()
        )
        cap_cat["capital_k"] = cap_cat["capital_tied_up"] / 1000

        fig1 = px.bar(
            cap_cat,
            x="product_category",
            y="capital_k",
            text_auto=".1f",
            labels={"product_category": "Category", "capital_k": "Capital ($k)"},
        )
        chart_layout(fig1, 300)
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c_b:
        st.markdown(
            """
            <div class="apple-card">
                <div class="section-title">Demand Volatility by Category (Std Dev σ)</div>
                <div class="section-subtitle">Variation in inventory quantity across the filtered dataset.</div>
            """,
            unsafe_allow_html=True,
        )

        fig2 = px.bar(
            cat_stats,
            x="product_category",
            y="category_stdev",
            text_auto=".1f",
            labels={
                "product_category": "Category",
                "category_stdev": "Standard Deviation",
            },
        )
        chart_layout(fig2, 300)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# TAB 2: Overstocking and capital risk
# =============================================================================
with t2:
    ratio_pct = int(overstock_ratio * 100)

    st.markdown(
        f"""
        <div class="apple-card">
            <div class="section-title">Low-Velocity Overstock Register</div>
            <div class="section-subtitle">Flagged products with average demand below {ratio_pct}% of their category baseline.</div>
        """,
        unsafe_allow_html=True,
    )

    if not overstock_df.empty:
        display_overstock = overstock_df[
            [
                "product_id",
                "product_category",
                "promotions",
                "sku_demand",
                "sku_cost",
                "capital_tied_up",
            ]
        ].rename(
            columns={
                "product_id": "Product ID",
                "product_category": "Category",
                "promotions": "Promoted",
                "sku_demand": "Avg Daily Demand",
                "sku_cost": "Unit Cost ($)",
                "capital_tied_up": "Capital Tied Up ($)",
            }
        )

        st.dataframe(
            display_overstock.style.format(
                {
                    "Avg Daily Demand": "{:.1f}",
                    "Unit Cost ($)": "${:,.2f}",
                    "Capital Tied Up ($)": "${:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No overstock products are flagged at the current threshold.")

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# TAB 3: Stockouts and customer satisfaction
# =============================================================================
with t3:
    st.markdown(
        f"""
        <div class="apple-card">
            <div class="section-title">Stockout Exposure & Reorder Targets</div>
            <div class="section-subtitle">Grouped comparison of average daily demand and calculated reorder point at a {service_level} target service level.</div>
        """,
        unsafe_allow_html=True,
    )

    top_reorder = df_sku.sort_values("reorder_point", ascending=False).head(10).copy()
    top_reorder["Product Label"] = top_reorder.apply(
        lambda row: f"ID {row['product_id']} ({str(row['product_category'])[:4]})",
        axis=1,
    )

    fig3 = go.Figure()
    fig3.add_trace(
        go.Bar(
            x=top_reorder["Product Label"],
            y=top_reorder["sku_demand"],
            name="Avg Daily Demand",
        )
    )
    fig3.add_trace(
        go.Bar(
            x=top_reorder["Product Label"],
            y=top_reorder["reorder_point"],
            name="Reorder Point Target",
        )
    )
    fig3.update_layout(
        barmode="group",
        legend=dict(orientation="h", y=1.1),
    )
    chart_layout(fig3, 340)
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# TAB 4: Demand trends and macro drivers
# =============================================================================
with t4:
    st.markdown(
        """
        <div class="apple-card">
            <div class="section-title">Monthly Demand Trends</div>
            <div class="section-subtitle">Historical inventory quantity by product category. The date range reflects the data currently stored in Azure SQL.</div>
        """,
        unsafe_allow_html=True,
    )

    trend_df = (
        df.groupby(
            ["product_category", pd.Grouper(key="sales_date", freq="ME")],
            dropna=False,
        )["inventory_quantity"]
        .sum()
        .reset_index()
    )

    fig4 = px.line(
        trend_df,
        x="sales_date",
        y="inventory_quantity",
        color="product_category",
        markers=True,
        labels={
            "sales_date": "Month",
            "inventory_quantity": "Units Moved",
            "product_category": "Category",
        },
    )
    chart_layout(fig4, 340)
    st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    # Macro-factor snapshot when the source columns contain usable values.
    macro_cols = ["gdp", "inflation_rate", "seasonal_factor"]
    available_macro = [col for col in macro_cols if col in df.columns and df[col].notna().any()]

    if available_macro:
        st.markdown(
            "<div style='font-weight:700; margin:12px 0 8px;'>Macro Driver Snapshot</div>",
            unsafe_allow_html=True,
        )
        macro_summary = df[available_macro].describe().T[["mean", "min", "max"]].rename(
            columns={"mean": "Average", "min": "Minimum", "max": "Maximum"}
        )
        st.dataframe(
            macro_summary.style.format("{:.3f}"),
            use_container_width=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# TAB 5: Action plan and export
# =============================================================================
with t5:
    st.markdown(
        """
        <div class="apple-card">
            <div class="section-title">Procurement & Reorder Action List</div>
            <div class="section-subtitle">Exportable procurement plan generated dynamically from the active filters, lead time and service-level assumptions.</div>
        """,
        unsafe_allow_html=True,
    )

    action_df = df_sku[
        [
            "product_id",
            "product_category",
            "promotions",
            "sku_demand",
            "lead_time_demand",
            "safety_stock",
            "reorder_point",
            "capital_tied_up",
            "is_overstock",
        ]
    ].copy()

    action_df.columns = [
        "Product ID",
        "Category",
        "Promoted",
        "Avg Daily Demand",
        "Lead Time Demand",
        "Safety Stock Buffer",
        "Calculated Reorder Point",
        "Capital Tied Up ($)",
        "Overstock Risk Flag",
    ]

    action_df = action_df.sort_values(
        ["Overstock Risk Flag", "Capital Tied Up ($)"],
        ascending=[False, False],
    )

    csv_data = action_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Procurement Reorder Action List (CSV)",
        data=csv_data,
        file_name="TechElectro_Reorder_Action_List.csv",
        mime="text/csv",
        use_container_width=False,
    )

    st.dataframe(
        action_df.style.format(
            {
                "Avg Daily Demand": "{:.1f}",
                "Lead Time Demand": "{:.1f}",
                "Safety Stock Buffer": "{:.1f}",
                "Calculated Reorder Point": "{:.1f}",
                "Capital Tied Up ($)": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Footer
# =============================================================================
st.caption(
    "TechElectro Inventory Analytics • Azure SQL • Calculations are based on the filtered dataset and dashboard assumptions."
)