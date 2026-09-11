import os
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyodbc
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
            --red: #c0392b;
            --amber: #b45309;
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
            margin-bottom: 16px;
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

        .status-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Database configuration
# =============================================================================
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a Streamlit secret with an environment-variable fallback."""
    try:
        value = st.secrets.get(name)
        if value not in (None, ""):
            return str(value).strip()
    except Exception:
        pass

    value = os.getenv(name, default)
    return str(value).strip() if value not in (None, "") else default


def _get_sql_config() -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Return Azure SQL settings.

    Preferred Streamlit Secrets format:
        server = "your-server.database.windows.net"
        database = "tech_electro"
        username = "your-login"
        password = "your-password"

    A legacy [azure_sql] section and AZURE_SQL_* environment variables are
    also supported for local development/backward compatibility.
    """
    server = database = username = password = None

    # Backward-compatible nested secrets.
    try:
        sql_cfg = st.secrets.get("azure_sql", {})
        if hasattr(sql_cfg, "get"):
            server = sql_cfg.get("server")
            database = sql_cfg.get("database")
            username = sql_cfg.get("username")
            password = sql_cfg.get("password")
    except Exception:
        pass

    server = server or _get_secret("server") or _get_secret("AZURE_SQL_SERVER")
    database = (
        database
        or _get_secret("database")
        or _get_secret("AZURE_SQL_DATABASE")
        or "tech_electro"
    )
    username = username or _get_secret("username") or _get_secret("AZURE_SQL_USERNAME")
    password = password or _get_secret("password") or _get_secret("AZURE_SQL_PASSWORD")

    return server, database, username, password


# Kept outside cached functions so the UI can show a useful non-secret error.
LAST_DB_ERROR: Optional[str] = None
LAST_QUERY_ERROR: Optional[str] = None


def _safe_error_message(exc: Exception) -> str:
    """Return a useful database error without exposing credentials."""
    message = " ".join(str(exc).split())
    # Never display the password if a driver happens to echo connection details.
    _, _, _, password = _get_sql_config()
    if password:
        message = message.replace(password, "********")
    return message[:1000] or type(exc).__name__


@st.cache_resource(show_spinner=False)
def get_db_connection() -> Optional[pyodbc.Connection]:
    """
    Connect to SQL Server:
      1. Try Azure SQL (Streamlit Cloud) with Driver 18, then Driver 17.
      2. Fallback to localhost (Windows dev) with Windows Integrated Auth.
    """
    global LAST_DB_ERROR
    LAST_DB_ERROR = None
    server, database, username, password = _get_sql_config()

    # --- Priority 1: Azure SQL ---
    if all([server, database, username, password]):
        azure_attempts = [
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;",
            f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;"
        ]
        for cs in azure_attempts:
            try:
                conn = pyodbc.connect(cs, timeout=15)
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return conn
            except Exception as exc:
                LAST_DB_ERROR = _safe_error_message(exc)
                continue
        
        # If we exhausted Azure attempts, log the last failure
        st.error(f"[DB] Azure SQL connection failed (tried Driver 18 & 17). Last error: {LAST_DB_ERROR}")
        return None

    # --- Priority 2: Localhost fallback ---
    local_attempts = [
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=tech_electro;Trusted_Connection=yes;TrustServerCertificate=yes;Connection Timeout=5;",
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=tech_electro;Trusted_Connection=yes;Connection Timeout=5;",
    ]
    for cs in local_attempts:
        try:
            conn = pyodbc.connect(cs, timeout=5)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return conn
        except Exception:
            continue

    LAST_DB_ERROR = "No database connection available. Check secrets or local SQL Server."
    st.error(f"[DB] {LAST_DB_ERROR}")
    return None


# =============================================================================
# Data loading
# =============================================================================
INVENTORY_QUERY = """
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


@st.cache_data(ttl=300, show_spinner="Loading inventory data…")
def load_data() -> Optional[pd.DataFrame]:
    """Load and clean the dashboard dataset from Azure SQL."""
    global LAST_QUERY_ERROR
    LAST_QUERY_ERROR = None

    conn = get_db_connection()
    if conn is None:
        return None

    try:
        df = pd.read_sql(INVENTORY_QUERY, conn)

        required_columns = {
            "product_id",
            "product_category",
            "sales_date",
            "inventory_quantity",
        }
        missing = required_columns.difference(df.columns)
        if missing:
            LAST_QUERY_ERROR = f"The SQL query did not return required columns: {', '.join(sorted(missing))}."
            return None

        df["sales_date"] = pd.to_datetime(df["sales_date"], errors="coerce")
        df["inventory_quantity"] = pd.to_numeric(df["inventory_quantity"], errors="coerce")
        df["product_cost"] = pd.to_numeric(df["product_cost"], errors="coerce")

        for column in ["gdp", "inflation_rate", "seasonal_factor"]:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        df["product_category"] = df["product_category"].astype("string").str.strip()
        df["promotions"] = df["promotions"].astype("string").str.strip()

        df = df.dropna(
            subset=[
                "product_id",
                "product_category",
                "sales_date",
                "inventory_quantity",
            ]
        )

        return df.reset_index(drop=True)

    except Exception as exc:
        LAST_QUERY_ERROR = _safe_error_message(exc)
        # Surface the REAL query error — remove the line below after diagnosis.
        st.error(f"[Query] SQL query failed — {type(exc).__name__}: {LAST_QUERY_ERROR}")
        return None


# =============================================================================
# Reusable UI helpers
# =============================================================================
def render_metric_card(
    label: str,
    value: str,
    note: str,
    accent: str,
    note_color: str,
) -> None:
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
        margin=dict(t=20, b=20, l=20, r=20),
        height=height,
        font=dict(family="Arial, sans-serif", color="#1d1d1f"),
        hoverlabel=dict(bgcolor="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)", zeroline=False)
    return fig


def card_start(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="apple-card">
            <div class="section-title">{title}</div>
            <div class="section-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# Sidebar branding
# =============================================================================
st.sidebar.markdown(
    """
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
        <div style="width:36px; height:36px; border-radius:8px;
                    background:linear-gradient(135deg,#1e8a3c,#39b54a);
                    display:flex; align-items:center; justify-content:center;
                    color:white; font-weight:800;">TE</div>
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
    <div class="apple-card" style="display:flex; justify-content:space-between;
         align-items:center; gap:20px;">
        <div>
            <div style="font-size:1.3rem; font-weight:700; color:#1d1d1f;">
                TechElectro Inventory Optimization Platform
            </div>
            <div style="font-size:0.8rem; color:#636366; margin-top:2px;">
                Data-driven supply chain management, stockout prevention & working capital analytics
            </div>
        </div>
        <div style="background:#e6f4e9; color:#166e2f; padding:4px 12px;
                    border-radius:20px; font-size:0.75rem; font-weight:700;
                    white-space:nowrap;">
            Azure SQL Pipeline
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Load data
# =============================================================================
df_raw = load_data()


# =============================================================================
# Connection/data error states
# =============================================================================
if df_raw is None:
    server, database, username, password = _get_sql_config()

    if not all([server, database, username, password]):
        st.error(
            "Azure SQL is not configured. Add `server`, `database`, `username`, "
            "and `password` to Streamlit Cloud Secrets."
        )
    elif LAST_QUERY_ERROR:
        st.error("Azure SQL connected, but the dashboard query could not be loaded.")
        with st.expander("Technical error details"):
            st.code(LAST_QUERY_ERROR)
    else:
        st.error(
            "The Azure SQL connection could not be established. Check the server name, "
            "credentials, database permissions, ODBC Driver 18, and Azure SQL firewall rules."
        )
        if LAST_DB_ERROR:
            with st.expander("Technical error details"):
                st.code(LAST_DB_ERROR)

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
    df = df[df["promotions"].fillna("").astype(str).str.lower().eq("yes")]
elif promo_filter == "Non-Promoted (No)":
    df = df[df["promotions"].fillna("").astype(str).str.lower().eq("no")]

if search_sku.strip():
    try:
        sku_value = int(search_sku.strip())
        df = df[df["product_id"] == sku_value]
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
df_sku["is_overstock"] = df_sku["sku_demand"] < (
    df_sku["avg_demand"] * overstock_ratio
)
df_sku["lead_time_demand"] = df_sku["sku_demand"] * lead_time_days
df_sku["safety_stock"] = (
    z_score * df_sku["category_stdev"] * np.sqrt(lead_time_days)
)
df_sku["reorder_point"] = df_sku["lead_time_demand"] + df_sku["safety_stock"]

overstock_df = df_sku[df_sku["is_overstock"]].sort_values(
    "capital_tied_up", ascending=False
)

total_capital_risk = float(overstock_df["capital_tied_up"].sum())
flagged_skus = int(len(overstock_df))
total_units_analyzed = float(df["inventory_quantity"].sum())


# =============================================================================
# Sidebar data summary
# =============================================================================
st.sidebar.markdown("---")
st.sidebar.caption(
    f"Loaded {len(df_raw):,} records across {df_raw['product_id'].nunique():,} SKUs."
)
st.sidebar.caption(
    f"Filtered period: {df['sales_date'].min():%b %Y} – {df['sales_date'].max():%b %Y}"
)


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
        "Inventory Quantity Analyzed",
        f"{total_units_analyzed:,.0f} Units",
        "Filtered dataset",
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
        card_start(
            "Capital Tied Up in Low-Velocity Stock ($k)",
            "Capital exposure from SKUs flagged as overstock.",
        )

        cap_cat = (
            overstock_df.groupby("product_category", as_index=False)["capital_tied_up"]
            .sum()
            .sort_values("capital_tied_up", ascending=False)
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
        card_end()

    with c_b:
        card_start(
            "Demand Volatility by Category (Std Dev σ)",
            "Variation in inventory quantity across the filtered dataset.",
        )

        fig2 = px.bar(
            cat_stats.sort_values("category_stdev", ascending=False),
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
        card_end()

    st.caption(
        "Note: the dashboard uses inventory_quantity as the demand/volume proxy because that is the measure available in the source query."
    )


# =============================================================================
# TAB 2: Overstocking and capital risk
# =============================================================================
with t2:
    ratio_pct = int(overstock_ratio * 100)
    card_start(
        "Low-Velocity Overstock Register",
        f"Flagged products with average demand below {ratio_pct}% of their category baseline.",
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

    card_end()


# =============================================================================
# TAB 3: Stockouts and reorder targets
# =============================================================================
with t3:
    card_start(
        "Stockout Exposure & Reorder Targets",
        f"Calculated reorder targets using {service_level} and a {lead_time_days}-day supplier lead time.",
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
    fig3.update_layout(barmode="group")
    chart_layout(fig3, 360)
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

    st.info(
        "This view estimates reorder targets from demand variability. It does not calculate actual customer satisfaction or confirmed stockout events because those fields are not present in the current SQL query."
    )
    card_end()


# =============================================================================
# TAB 4: Demand trends and macro drivers
# =============================================================================
with t4:
    card_start(
        "Monthly Demand Trends",
        "Historical inventory quantity by product category. The date range reflects the data currently stored in Azure SQL.",
    )

    trend_df = (
        df.groupby(
            ["product_category", pd.Grouper(key="sales_date", freq="M")],
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
            "inventory_quantity": "Units",
            "product_category": "Category",
        },
    )
    chart_layout(fig4, 340)
    st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    macro_cols = ["gdp", "inflation_rate", "seasonal_factor"]
    available_macro = [
        col for col in macro_cols if col in df.columns and df[col].notna().any()
    ]

    if available_macro:
        st.markdown(
            "<div style='font-weight:700; margin:12px 0 8px;'>Macro Driver Snapshot</div>",
            unsafe_allow_html=True,
        )
        macro_summary = (
            df[available_macro]
            .describe()
            .T[["mean", "min", "max"]]
            .rename(
                columns={
                    "mean": "Average",
                    "min": "Minimum",
                    "max": "Maximum",
                }
            )
        )
        st.dataframe(
            macro_summary.style.format("{:.3f}"),
            use_container_width=True,
        )
    else:
        st.caption("No usable macro-factor values are available for the current filters.")

    card_end()


# =============================================================================
# TAB 5: Action plan and export
# =============================================================================
with t5:
    card_start(
        "Procurement & Reorder Action List",
        "Exportable procurement plan generated dynamically from the active filters, lead time and service-level assumptions.",
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

    card_end()


# =============================================================================
# Footer
# =============================================================================
st.caption(
    "TechElectro Inventory Analytics • Azure SQL • Calculations are based on the filtered dataset and dashboard assumptions."
)
