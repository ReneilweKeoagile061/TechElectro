# TechElectro Inc. Inventory Optimization Dashboard

Data-driven inventory optimization project for TechElectro Inc., addressing overstocking, understocking, and customer satisfaction risk through SQL Server analytics and an interactive Streamlit dashboard.

## Live Dashboard
[Insert Streamlit Cloud URL once deployed]

---

## 1. End-to-End Problem-Solving Process

1. **Environment setup** — SQL Server 2022 + SSMS installed and configured locally.
2. **Schema design** — three normalized tables (`product_information`, `sales_data`, `external_factors`) with PK/FK constraints.
3. **Data ingestion** — raw CSVs loaded into all-text staging tables via `BULK INSERT`, avoiding type-conversion failures on untrusted data.
4. **Data cleaning** — staging data transformed and cast into final tables with explicit, documented rules (see Decisions below).
5. **Data modeling** — an `inventory_summary` view joins all three tables (`LEFT JOIN` on external factors to avoid silently dropping sales records).
6. **Analysis** — reorder-point, overstock-risk, demand-trend, promotion, and seasonal-effect queries built in T-SQL.
7. **Visualization** — Python (`pyodbc` + `pandas` + `plotly`) connects live to SQL Server; results rendered as an interactive Streamlit dashboard.

Full SQL: [`Reliance Infosystems.sql`](./Reliance%20Infosystems.sql)
Full methodology rationale: [`methodology_decisions.md`](./methodology_decisions.md)

---

## 2. Key Findings and Insights

- **91.5% of products (1,258 of 1,375) have only one sales record** — per-SKU demand volatility is statistically uncomputable. Safety stock is calculated at the **category level** instead.
- **~\ in capital is tied up in low-velocity stock** — products moving at under 50% of their category's average demand, concentrated most heavily in SmartPhones and Laptops.
- **No measurable promotion effect** on sales volume — promoted and non-promoted products show statistically indistinguishable average demand.
- **No measurable seasonal effect** — demand is flat across low/normal/high season bands (a ~1-unit spread).
- **Category is the one real demand driver** — SmartPhones and Home_Appliances show meaningfully higher volatility than Electronics, directly shaping reorder-point recommendations.

---

## 3. Decisions Made and Rationale

| Decision | Why |
|---|---|
| Staging-table pattern (all-text, then cast) | Untrusted CSV data shouldn't cause a load to fail outright; separates "get it in" from "make it correct" |
| `CONVERT(DATE, col, 103)` explicit date parsing | Source dates are DD/MM/YYYY (confirmed via day values >12); implicit parsing risks silently swapping day/month |
| "Yes wins" rule for conflicting promotion flags | A product ever promoted counts as promoted — deterministic, explainable business rule |
| `AVG()` on duplicate-date economic records | GDP/inflation are continuous macro measures; averaging reduces noise without discarding data |
| `LEFT JOIN` on external_factors | Guarantees no sales record is silently dropped if a date has no matching economic data |
| Category-level (not per-product) volatility | 91.5% of products have a single sales record — per-SKU STDEV is mathematically undefined |

Full rationale with alternatives considered: [`methodology_decisions.md`](./methodology_decisions.md)

---

## 4. Recommendations

**Immediate (0–30 days)**
- Initiate clearance for ~340 flagged low-velocity SKUs (~\ in tied-up capital)
- Set reorder alerts for the top 10 highest reorder-point products
- Run a controlled test of promotion effectiveness before the next promotional cycle

**Short-term (30–90 days)**
- Collect actual supplier lead-time data to replace the current 7-day assumption
- Increase sales data granularity for richer per-SKU analytics
- Segment SmartPhones into velocity tiers given their bimodal demand pattern

**Future (90+ days)**
- Migrate to Azure SQL Database and deploy the dashboard for remote, always-on management access
- Automate data refresh (scheduled feed instead of manual CSV import)
- Recalibrate the seasonal index against TechElectro's own POS history
- Capture direct customer satisfaction KPIs (stockout rate, order fill rate, return rate)

---

## 5. Challenges Encountered and How They Were Addressed

| Challenge | Resolution |
|---|---|
| 91.5% of SKUs have a single sales record | Pivoted to category-level statistics as the only statistically valid basis |
| Duplicate product records with conflicting promotion flags | "Yes wins" rule via `GROUP BY` + conditional `MAX` |
| Duplicate economic records for the same date | Resolved via `GROUP BY` + `AVG()` |
| Sales dates without matching economic data | `LEFT JOIN` instead of `INNER JOIN` to preserve all sales records |
| Database drop blocked by active session | `USE master;` before `DROP DATABASE` to release the connection |

---

## 6. Technology Stack

| Component | Technology |
|---|---|
| Database engine | Microsoft SQL Server 2022 |
| DB management | SQL Server Management Studio (SSMS) |
| Data ingestion | T-SQL `BULK INSERT` |
| Scripting | Python 3.14 |
| DB connectivity | `pyodbc` |
| Data manipulation | `pandas` |
| Visualization | `plotly`, `matplotlib` |
| Dashboard framework | Streamlit |
| Architecture diagram | draw.io |

---

## 7. Repository Contents

- `app.py` — interactive Streamlit dashboard
- `generate_charts.py` — standalone chart generation script
- `Reliance Infosystems.sql` — full SQL script (schema, staging, cleaning, analysis)
- `methodology_decisions.md` — detailed rationale for every technical decision
- `TechElectro_Inventory_Report.md` — full management report
- `architecture_diagram.drawio` — solution architecture diagram
- `visuals/` — exported chart images
- `requirements.txt` — Python dependencies

---

## 8. Business Value

This project directly targets TechElectro's stated problem: overstocking and understocking eroding customer satisfaction and tying up capital. The dashboard gives management a live, filterable view of both risks simultaneously, capital at risk from slow-moving stock, and reorder urgency for fast-moving stock, with adjustable service-level and lead-time assumptions so recommendations can be tuned to real supplier terms as that data becomes available.
