# TechElectro Inc. — Inventory Optimization Project Report

**Prepared by:** Reliance Infosystems Analytics Team  
**Date:** September 2026  
**Project:** Elevate Customer Satisfaction: Revolutionize Supply Chain with Inventory Optimization

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [End-to-End Problem-Solving Process](#2-end-to-end-problem-solving-process)
3. [Key Findings and Insights](#3-key-findings-and-insights)
4. [Decisions Made and Rationale](#4-decisions-made-and-rationale)
5. [Recommendations](#5-recommendations)
6. [Challenges and How They Were Addressed](#6-challenges-and-how-they-were-addressed)
7. [Technology Stack](#7-technology-stack)
8. [Visualizations and Dashboards](#8-visualizations-and-dashboards)
9. [Conclusion](#9-conclusion)

---

## 1. Executive Summary

TechElectro Inc., a global consumer electronics leader, faces persistent inventory imbalances — simultaneously overstocking low-demand SKUs while running out of high-velocity products. These imbalances erode customer satisfaction, tie up working capital, and reduce operational efficiency across the supply chain.

This project delivered a complete, data-driven inventory optimization analysis using **SQL Server 2022** as the analytical engine and **Python** for visualization. The analysis covered 1,375 unique products, 1,500 sales transactions, and 1,019 days of external economic data spanning 2018–2022.

**Key headline numbers:**

| Metric | Value |
|---|---|
| Total capital tied up in low-velocity stock | **\$503,055** across all categories |
| Highest-risk category (overstocking) | **SmartPhones — \$152,345** |
| Highest-demand category (stockout risk) | **SmartPhones — avg 58 units/SKU moved** |
| Promotion uplift on avg demand | **Negligible (+0.3 units)** — promotions not driving volume |
| Peak seasonal demand band | **Normal season** — demand does not peak sharply in High Season |
| Inflation correlation with demand | **Weak inverse** — demand holds steady despite inflation changes |

---

## 2. End-to-End Problem-Solving Process

### Phase 1 — Environment Setup
- Installed **SQL Server 2022** and **SSMS** on the local machine.
- Created the `tech_electro` database and defined three normalized tables: `product_information`, `sales_data`, and `external_factors`.
- Designed **staging tables** (NVARCHAR columns) to safely absorb raw CSV data before type-casting.

### Phase 2 — Data Ingestion
- Used `BULK INSERT` to load the three CSV files (Product Information, Sales Data, External Factors) into staging tables.
- Applied UTF-8 encoding (`CODEPAGE = '65001'`) and flexible row terminators to handle Windows/Unix line endings.

### Phase 3 — Data Transformation and Cleaning
- **Product Information:** Deduplication with a "Yes wins" rule — if any record for a product had `Promotions = 'Yes'`, the product was flagged as promoted.
- **Sales Data:** Type-cast Product ID (INT), Sales Date (DATE using format 103 for DD/MM/YYYY), Inventory Quantity (INT), and Product Cost (DECIMAL).
- **External Factors:** Duplicate date rows were resolved by averaging GDP, Inflation Rate, and Seasonal Factor — appropriate for continuous economic measures.
- Staging tables were dropped once verified clean.

### Phase 4 — Data Modelling
- Created the `inventory_summary` view joining all three tables via `LEFT JOIN` on `sales_date` to preserve all sales records even where external factor data was absent.
- Verified join quality: checked for NULLs in the GDP column to quantify coverage gaps.

### Phase 5 — Analytical Queries
Five analytical layers were built in SQL:

| Query | Purpose |
|---|---|
| **A — Demand Pattern** | Avg, min, max, and std dev of inventory quantity per product |
| **B — Category-Level View** | Total units moved, avg demand, avg cost per category |
| **C — Reorder Point** | Per-product reorder point using category-level volatility as proxy |
| **D — Promotion Impact** | Avg demand comparison: Promoted vs. Non-promoted |
| **E — Seasonal Factor Correlation** | Avg demand split by Low/Normal/High season band |

### Phase 6 — Visualization
- Connected Python to SQL Server via `pyodbc`.
- Executed all analytical queries and rendered **9 publication-quality charts** using `matplotlib`.
- All charts saved to the `visuals/` folder for embedding in this report and management presentations.

---

## 3. Key Findings and Insights

### 3.1 Demand Volatility is Category-Wide, Not Product-Specific

> **Finding:** 91.5% of products (1,258 of 1,375) have only a single sales record. Only 8 products have 3 records. Per-SKU STDEV is mathematically undefined for ~92% of the portfolio.

**Implication:** Inventory decisions cannot be made at the individual SKU level with this data. **Category-level volatility is the only statistically valid basis for reorder calculations.** SmartPhones show the highest volatility (σ = 29.5 units), followed by Home Appliances (σ = 29.4).

---

### 3.2 \$503,055 Tied Up in Low-Velocity Stock

| Category | Capital at Risk | Products Flagged |
|---|---|---|
| SmartPhones | \$152,345 | 100 SKUs |
| Laptops | \$133,039 | 92 SKUs |
| Electronics | \$117,436 | 69 SKUs |
| Home Appliances | \$100,236 | 79 SKUs |

> **Definition:** A product is flagged as "low velocity" if its average demand is less than 50% of its category average — the most likely candidates for overstock write-downs.

---

### 3.3 Reorder Points Differentiated by Category Volatility

- **Product 9402 (SmartPhone):** Reorder point = **828.9 units** *(highest)*
- **Product 2010 (Home Appliance):** 828.1 units
- **Products 2587 / 7442 (Laptops):** 826.5 units
- **Electronics cluster:** ~821.5 units (lower category volatility σ = 27.8)

---

### 3.4 Promotions Are NOT Driving Demand Volume

| Promotion | Avg Units Per Sale | Records |
|---|---|---|
| Yes | 51.4 | 793 |
| No | 51.7 | 707 |

> **Critical insight for management:** The 0.3-unit difference is statistically negligible. Promotional spend is not correlated with higher sales volumes. This warrants a strategic review of the promotions budget.

---

### 3.5 Seasonal Patterns Are Flat — No Clear Peak Season

| Season Band | Avg Units/Sale | Records |
|---|---|---|
| Normal (0.95–1.05) | 51.9 | 630 |
| Low (<0.95) | 51.7 | 400 |
| High (>1.05) | 51.0 | 470 |

> **Insight:** Demand is remarkably stable across seasonal bands. High season does not drive higher unit volumes — the seasonal index in the external data may not be calibrated to TechElectro's actual demand curve.

---

### 3.6 SmartPhones Lead Both Risk Dimensions

SmartPhones appear at the **top of both** the overstocking risk list (\$152k capital tied up) and the understocking risk list (highest reorder points). This reflects a **bimodal SKU distribution** within the category — some SmartPhone SKUs are fast-movers (stockout risk) while others are slow-movers (overstock risk).

---

### 3.7 Inflation Has Limited Impact on Demand

Monthly demand held relatively stable across 2018–2022 despite inflation fluctuations ranging 2–4%. Consumer electronics appear relatively inelastic to moderate inflation at TechElectro's price points.

---

## 4. Decisions Made and Rationale

| Decision | Rationale |
|---|---|
| **Category-level STDEV for reorder points** | 91.5% of SKUs have only 1 sales record — per-SKU STDEV returns NULL. Category-level is the only statistically defensible approach. |
| **"Yes wins" deduplication for Promotions** | A product ever promoted should be treated as promoted. MAX flag preserves the most commercially relevant state. |
| **AVG for duplicate external factor dates** | Economic indicators are continuous measures. Averaging duplicates is more defensible than keeping first/last. |
| **LEFT JOIN for inventory_summary view** | INNER JOIN would drop sales records with no matching external_factor date, silently understating sales figures. |
| **7-day lead time assumption** | No lead time data supplied. 7 days is a commonly used default for B2B electronics distribution. Must be updated with actual supplier data. |
| **Z-score of 1.65 (~95% service level)** | Balances stockout risk reduction with safety stock cost. Adjustable per category — higher for SmartPhones, lower for slow-moving categories. |
| **50% of category avg as overstock threshold** | Products moving at less than half the category average are clear slow movers with a conservative, defensible cut-off. |

---

## 5. Recommendations

### 5.1 Immediate Actions (0–30 days)

1. **Initiate stock clearance for 340 flagged low-velocity SKUs** — particularly the 100 SmartPhone SKUs (\$152k at risk). Use promotional pricing, bundling, or channel liquidation.
2. **Set reorder alerts** for the top 10 highest reorder-point products, starting with Product 9402 (SmartPhone).
3. **Review promotions strategy** — current data shows no volume uplift from promotions. Run a controlled A/B test before the next promotional cycle.

### 5.2 Short-Term Improvements (30–90 days)

4. **Collect actual supplier lead time data** — replace the 7-day assumption with supplier-specific lead times.
5. **Increase sales data granularity** — ensure each individual transaction is captured, not aggregated, to enable per-SKU analytics.
6. **Segment SmartPhones into velocity tiers (A/B/C)** — the bimodal demand pattern means the category needs split management strategies.

### 5.3 Future Improvements (90+ days)

7. **Implement demand forecasting** — rolling average or ARIMA per-category model once richer data is available.
8. **Build a live data pipeline** — replace batch CSV imports with a continuous feed (Azure Data Factory or SSIS) into the analytics layer.
9. **Build an interactive Power BI / Tableau dashboard** — replace static charts with a live, filterable management dashboard.
10. **Recalibrate the seasonal index** — rebuild from TechElectro's own POS history; the current external index shows no meaningful demand variation.
11. **Add customer satisfaction KPIs** — stockout rate, order fill rate, and return rate should be captured in the next data collection cycle as direct satisfaction proxies.

---

## 6. Challenges and How They Were Addressed

| Challenge | Resolution |
|---|---|
| **91.5% of SKUs have a single sales record — STDEV returns NULL** | Pivoted to category-level statistics as the statistically valid proxy for per-product safety stock calculations. Documented as a data quality finding and a recommendation to improve data collection frequency. |
| **Duplicate product records with conflicting promotion flags** | Applied a "Yes wins" GROUP BY rule using MAX(CASE WHEN promotions = 'Yes' THEN 1 ELSE 0 END). |
| **Duplicate dates in external_factors** | Resolved with GROUP BY + AVG() on all numeric columns — appropriate for continuous economic measures. |
| **Sales dates without matching external factor records** | Used LEFT JOIN in the inventory_summary view instead of INNER JOIN to preserve all sales records. NULL count query verified the gap size. |
| **pandas UserWarning for raw pyodbc connection** | Warning is non-blocking; data reads correctly. Documented migration path to SQLAlchemy for a future sprint to avoid adding an unnecessary dependency now. |
| **No customer satisfaction data in any dataset** | Addressed indirectly by quantifying stockout risk (high-demand products below reorder threshold) and overstocking risk. Recommended explicit satisfaction metrics for future data capture. |

---

## 7. Technology Stack

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Database Engine | Microsoft SQL Server | 2022 | Data storage, transformation, analytics |
| DB Management | SSMS | 20.x | Query development, schema management |
| Data Ingestion | T-SQL BULK INSERT | — | CSV → Staging table load |
| Scripting Language | Python | 3.x | Chart generation and automation |
| Data Connectivity | pyodbc | 5.3.0 | Python → SQL Server bridge |
| Data Manipulation | pandas | 3.0.5 | Query results → DataFrames |
| Visualization | matplotlib | 3.11.1 | Chart rendering and export |
| Numerical Computing | numpy | 2.5.3 | Array operations in chart generation |
| Runtime Environment | Python venv (.venv) | — | Isolated dependency management |
| Diagram Tool | draw.io | — | Architecture diagram |
| Report Format | Markdown | — | Management deliverable |

---

## 8. Visualizations and Dashboards

All 9 charts are saved in the `visuals/` folder.

| # | File | Business Question |
|---|---|---|
| 1 | `chart1_category_volatility.png` | Which categories have the most unpredictable demand? |
| 2 | `chart2_overstock_capital.png` | How much capital is locked in slow-moving stock, by category? |
| 3 | `chart3_demand_trend.png` | How has category demand evolved month-on-month 2018–2022? |
| 4 | `chart4_top10_reorder.png` | Which 10 products need urgent replenishment attention? |
| 5 | `chart5_promotion_impact.png` | Are promotions actually moving more product? |
| 6 | `chart6_seasonal_demand_bands.png` | Does seasonality drive meaningful demand swings? |
| 7 | `chart7_understocking_risk.png` | Which fast-moving products are most exposed to stockouts? |
| 8 | `chart8_turnover_by_category.png` | Which categories turn stock fastest vs. cost the most? |
| 9 | `chart9_gdp_inflation_demand.png` | Does macroeconomic inflation affect TechElectro's sales volumes? |

> **For the management presentation:** Prioritize charts 2, 4, 5, 7, and 8 on the executive summary slide. Charts 1, 3, 6, and 9 support the analytical narrative in the appendix.

---

## 9. Conclusion

This project successfully established an end-to-end, data-driven inventory analytics capability for TechElectro Inc. The analysis has revealed that:

- **\$503k in capital** is tied up in slow-moving inventory — immediate action can recover a significant portion.
- **SmartPhones** require a dual-track strategy: liquidate slow movers while protecting fast movers from stockout.
- **Promotions and seasonality** are not driving the demand shifts TechElectro may have assumed — these assumptions should be re-examined before the next planning cycle.
- The **data foundation is sound but thin** — increasing transaction granularity will unlock per-product demand forecasting.

The recommendations in Section 5 provide a clear, phased roadmap from immediate stock clearance through to a mature, automated inventory intelligence platform.

---

*Attachments: `Reliance Infosystems.sql` · `generate_charts.py` · `visuals/` (9 PNG charts) · `architecture_diagram.drawio`*
