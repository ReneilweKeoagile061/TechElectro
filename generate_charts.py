import os
import warnings
import pyodbc
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

# --- Output folder ---
VISUALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visuals")
os.makedirs(VISUALS_DIR, exist_ok=True)

# --- Connection ---
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=tech_electro;"
    "Trusted_Connection=yes;"
)

# --- Styling ---
plt.rcParams["figure.dpi"] = 150
DARK, BLUE, RED, GREEN, ORANGE = "#2E3B4E", "#4A90D9", "#E74C3C", "#2ECC71", "#E67E22"


def save(filename):
    plt.tight_layout()
    plt.savefig(os.path.join(VISUALS_DIR, filename))
    plt.close()


# -- 1. Demand Volatility by Category -----------------------------------------
df = pd.read_sql("""
    SELECT p.product_category,
           STDEV(s.inventory_quantity) AS category_stdev
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    GROUP  BY p.product_category
    ORDER  BY category_stdev DESC
""", conn)

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(df["product_category"], df["category_stdev"], color=DARK)
ax.set_title("Demand Volatility by Category")
ax.set_ylabel("Standard Deviation (units)")
ax.set_xlabel("Product Category")
save("chart1_category_volatility.png")


# -- 2. Capital Tied Up in Low-Velocity Stock ----------------------------------
df = pd.read_sql("""
    WITH category_stats AS (
        SELECT p.product_category,
               AVG(CAST(s.inventory_quantity AS FLOAT)) AS category_avg_demand
        FROM   sales_data s
        JOIN   product_information p ON s.product_id = p.product_id
        GROUP  BY p.product_category
    ),
    flagged AS (
        SELECT p.product_category,
               AVG(CAST(s.inventory_quantity AS FLOAT)) * AVG(s.product_cost) AS capital_tied_up
        FROM   sales_data s
        JOIN   product_information p ON s.product_id = p.product_id
        JOIN   category_stats cs ON p.product_category = cs.product_category
        GROUP  BY s.product_id, p.product_category, cs.category_avg_demand
        HAVING AVG(CAST(s.inventory_quantity AS FLOAT)) < (cs.category_avg_demand * 0.5)
    )
    SELECT product_category,
           SUM(capital_tied_up) AS total_capital_tied_up
    FROM   flagged
    GROUP  BY product_category
    ORDER  BY total_capital_tied_up DESC
""", conn)

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(df["product_category"], df["total_capital_tied_up"], color=RED)
ax.set_title("Capital Tied Up in Low-Velocity Stock by Category")
ax.set_ylabel("Estimated Capital ($)")
ax.set_xlabel("Product Category")
save("chart2_overstock_capital.png")


# -- 3. Monthly Demand Trend by Category --------------------------------------
df = pd.read_sql("""
    SELECT p.product_category,
           DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1) AS month_start,
           SUM(s.inventory_quantity) AS total_units_moved
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    GROUP  BY p.product_category, DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1)
    ORDER  BY p.product_category, month_start
""", conn)

fig, ax = plt.subplots(figsize=(10, 6))
for cat, grp in df.groupby("product_category"):
    ax.plot(grp["month_start"], grp["total_units_moved"], label=cat, linewidth=1.5)
ax.set_title("Monthly Demand Trend by Category (2018\u20132022)")
ax.set_ylabel("Total Units Moved")
ax.set_xlabel("Month")
ax.legend()
save("chart3_demand_trend.png")


# -- 4. Top 10 Highest Reorder-Point Products ---------------------------------
df = pd.read_sql("""
    WITH category_stats AS (
        SELECT p.product_category,
               STDEV(s.inventory_quantity) AS category_stdev
        FROM   sales_data s
        JOIN   product_information p ON s.product_id = p.product_id
        GROUP  BY p.product_category
    )
    SELECT TOP 10
           s.product_id,
           p.product_category,
           ROUND((AVG(CAST(s.inventory_quantity AS FLOAT)) * 7)
               + (1.65 * ISNULL(cs.category_stdev, 0) * SQRT(7)), 1) AS reorder_point
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    JOIN   category_stats cs ON p.product_category = cs.product_category
    GROUP  BY s.product_id, p.product_category, cs.category_stdev
    ORDER  BY reorder_point DESC
""", conn)

fig, ax = plt.subplots(figsize=(8, 6))
ax.barh([f"{r.product_id} ({r.product_category})" for r in df.itertuples()],
        df["reorder_point"], color=BLUE)
ax.invert_yaxis()
ax.set_title("Top 10 Highest-Priority Reorder Products")
ax.set_xlabel("Reorder Point (units)")
save("chart4_top10_reorder.png")


# -- 5. Promotion Impact on Average Demand ------------------------------------
df = pd.read_sql("""
    SELECT p.promotions,
           AVG(CAST(s.inventory_quantity AS FLOAT)) AS avg_units_per_sale,
           COUNT(*) AS num_records
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    GROUP  BY p.promotions
""", conn)

fig, ax = plt.subplots(figsize=(6, 5))
bars = ax.bar(df["promotions"], df["avg_units_per_sale"],
              color=[GREEN if p == "Yes" else "#7F8C8D" for p in df["promotions"]],
              width=0.4)
for bar in bars:
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
ax.set_title("Promotion Impact on Average Units Per Sale", fontsize=13, fontweight="bold")
ax.set_ylabel("Avg Units Per Sale")
ax.set_xlabel("Promotion Active")
ax.set_ylim(0, max(bar.get_height() for bar in bars) * 1.2)
save("chart5_promotion_impact.png")


# -- 6. Average Demand by Seasonal Band ---------------------------------------
df = pd.read_sql("""
    SELECT CASE
               WHEN e.seasonal_factor < 0.95  THEN 'Low Season'
               WHEN e.seasonal_factor <= 1.05 THEN 'Normal'
               ELSE 'High Season'
           END AS season_band,
           AVG(CAST(s.inventory_quantity AS FLOAT)) AS avg_units_per_sale,
           COUNT(*) AS num_records
    FROM   sales_data s
    JOIN   external_factors e ON s.sales_date = e.sales_date
    GROUP  BY CASE
                  WHEN e.seasonal_factor < 0.95  THEN 'Low Season'
                  WHEN e.seasonal_factor <= 1.05 THEN 'Normal'
                  ELSE 'High Season'
              END
""", conn)

df["season_band"] = pd.Categorical(
    df["season_band"], categories=["Low Season", "Normal", "High Season"], ordered=True
)
df = df.sort_values("season_band")

fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(df["season_band"], df["avg_units_per_sale"],
              color=["#5DADE2", "#F0B27A", RED], width=0.5)
for bar, row in zip(bars, df.itertuples()):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
            f"{row.avg_units_per_sale:.1f}\n(n={row.num_records})",
            ha="center", va="bottom", fontsize=9)
ax.set_title("Average Demand by Seasonal Band", fontsize=13, fontweight="bold")
ax.set_ylabel("Avg Units Per Sale")
ax.set_xlabel("Season Band")
ax.set_ylim(0, max(bar.get_height() for bar in bars) * 1.25)
save("chart6_seasonal_demand_bands.png")


# -- 7. Stockout Risk: Top 10 High-Demand Products ----------------------------
df = pd.read_sql("""
    WITH category_stats AS (
        SELECT p.product_category,
               STDEV(s.inventory_quantity) AS category_stdev
        FROM   sales_data s
        JOIN   product_information p ON s.product_id = p.product_id
        GROUP  BY p.product_category
    )
    SELECT TOP 10
           s.product_id,
           p.product_category,
           ROUND(AVG(CAST(s.inventory_quantity AS FLOAT)), 1) AS avg_demand,
           ROUND((AVG(CAST(s.inventory_quantity AS FLOAT)) * 7)
               + (1.65 * ISNULL(cs.category_stdev, 0) * SQRT(7)), 1) AS reorder_point
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    JOIN   category_stats cs ON p.product_category = cs.product_category
    GROUP  BY s.product_id, p.product_category, cs.category_stdev
    ORDER  BY avg_demand DESC
""", conn)

x = range(len(df))
fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(x, df["reorder_point"], color=RED,   alpha=0.75, label="Reorder Point")
ax.bar(x, df["avg_demand"],    color=GREEN, alpha=0.9,  label="Avg Daily Demand")
ax.set_xticks(list(x))
ax.set_xticklabels([f"ID {r.product_id}\n({r.product_category[:4]})" for r in df.itertuples()],
                   fontsize=8)
ax.set_title("Top 10 High-Demand Products \u2014 Stockout Risk Profile", fontsize=13, fontweight="bold")
ax.set_ylabel("Units")
ax.legend()
save("chart7_understocking_risk.png")


# -- 8. Stock Turnover Proxy vs. Unit Cost (dual-axis) ------------------------
df = pd.read_sql("""
    SELECT p.product_category,
           ROUND(CAST(SUM(s.inventory_quantity) AS FLOAT)
                 / COUNT(DISTINCT s.product_id), 1) AS avg_units_per_product,
           ROUND(AVG(s.product_cost), 2)            AS avg_unit_cost
    FROM   sales_data s
    JOIN   product_information p ON s.product_id = p.product_id
    GROUP  BY p.product_category
    ORDER  BY avg_units_per_product DESC
""", conn)

x = range(len(df))
fig, ax1 = plt.subplots(figsize=(8, 5))
ax1.bar(x, df["avg_units_per_product"], color=BLUE, alpha=0.85, label="Avg units per SKU")
ax1.set_xticks(list(x))
ax1.set_xticklabels(df["product_category"])
ax1.set_ylabel("Avg Units Moved per SKU", color=BLUE)
ax1.tick_params(axis="y", labelcolor=BLUE)

ax2 = ax1.twinx()
ax2.plot(list(x), df["avg_unit_cost"], color=ORANGE, marker="o", linewidth=2, label="Avg Unit Cost ($)")
ax2.set_ylabel("Avg Unit Cost ($)", color=ORANGE)
ax2.tick_params(axis="y", labelcolor=ORANGE)

ax1.set_title("Stock Turnover Proxy vs. Unit Cost by Category", fontweight="bold")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper right")
save("chart8_turnover_by_category.png")


# -- 9. Monthly Demand vs. Inflation Rate -------------------------------------
df = pd.read_sql("""
    SELECT DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1) AS month_start,
           AVG(CAST(e.inflation_rate AS FLOAT)) AS avg_inflation,
           SUM(s.inventory_quantity)            AS total_units_moved
    FROM   sales_data s
    JOIN   external_factors e ON s.sales_date = e.sales_date
    GROUP  BY DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1)
    ORDER  BY month_start
""", conn)

fig, ax1 = plt.subplots(figsize=(12, 5))
ax1.fill_between(df["month_start"], df["total_units_moved"], color=BLUE, alpha=0.2)
ax1.plot(df["month_start"], df["total_units_moved"], color=BLUE, linewidth=1.8, label="Total Units Moved")
ax1.set_ylabel("Total Units Moved", color=BLUE)
ax1.tick_params(axis="y", labelcolor=BLUE)

ax2 = ax1.twinx()
ax2.plot(df["month_start"], df["avg_inflation"], color=RED, linewidth=1.5,
         linestyle="--", label="Avg Inflation Rate (%)")
ax2.set_ylabel("Inflation Rate (%)", color=RED)
ax2.tick_params(axis="y", labelcolor=RED)

ax1.set_title("Monthly Demand vs. Inflation Rate (External Factor Influence)", fontweight="bold")
ax1.set_xlabel("Month")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=9)
save("chart9_gdp_inflation_demand.png")


conn.close()
print(f"Done -- 9 charts saved to: {VISUALS_DIR}")
