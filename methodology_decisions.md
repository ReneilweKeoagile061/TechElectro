# Methodology & Design Decisions — Defense Notes

Use this as prep for explaining *why*, not just *what*, if Refilwe reviews the code.

---

## SQL Script Decisions

### 1. Why a staging-table pattern instead of importing straight into final tables?

**What I did:** Loaded every CSV into an all-`NVARCHAR` staging table first (`staging_product_information`, etc.), then used `INSERT INTO ... SELECT ... CAST(...)` to move cleaned, typed data into the real tables.

**Why, if asked:**
- Raw CSV data is untrusted until proven otherwise — it can contain malformed dates, stray whitespace, or values that don't match the target column type. Loading straight into a strongly-typed table means the *whole load fails* the moment one row has a bad value.
- Staging as text means the load always succeeds, and type conversion becomes a separate, deliberate step I control — I can inspect the raw values before deciding how to cast them (this is exactly how I caught the DD/MM/YYYY issue and the duplicate-key issues before they became silent bugs).
- This is a standard ETL pattern (Extract → **Stage** → Transform → Load) used in real data engineering, not something specific to this project — separating "get the data in" from "make the data correct" is a deliberate design principle, not a workaround.

**Alternative considered:** SSMS's Import Flat File wizard directly into final tables. Rejected because it can't target an existing table with constraints — it only creates new tables — so it wouldn't respect my PK/FK design at all.

---

### 2. Why `CONVERT(DATE, column, 103)` instead of just casting or letting SQL Server auto-detect the date?

**What I did:** Explicit style code `103` in `CONVERT()`, which tells SQL Server unambiguously "this text is DD/MM/YYYY."

**Why:** SQL Server's automatic date parsing depends on server/session locale settings. A date like `03/04/2020` is genuinely ambiguous — it could mean 3 April or 4 March depending on what locale SQL Server assumes. I confirmed the actual format by checking for day values above 12 in the data (e.g. `31/10/2019`), which only makes sense as DD/MM/YYYY. Rather than trust an implicit, environment-dependent conversion, I used an explicit style code so the conversion is correct regardless of server locale — this is also just safer practice for any date-handling code that might run on a different machine later.

---

### 3. Why `GROUP BY product_id` with `MAX(CASE WHEN Promotions='Yes' THEN 1 ELSE 0 END)` for the duplicate-promotion conflict, instead of just picking one row (e.g. `TOP 1`, `MIN`, or `ROW_NUMBER()`)?

**What I did:** A conditional aggregate that returns "Yes" if *any* row for that product_id said "Yes."

**Why:** I needed a rule, not an arbitrary pick. `TOP 1` or picking the "first" row by insertion order is not deterministic — SQL Server doesn't guarantee row order without an `ORDER BY`, so "first row" could return different results on different runs. I chose "Yes wins" as a *business* rule (a product that was ever promoted counts as promoted) rather than a technical shortcut, and implemented it with an aggregate so it's deterministic and explainable in one line.

**Alternative considered:** `ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY ...)` to pick a single "canonical" row. Rejected because there's no reliable column to order by that would make one row more "correct" than the other — the conflict is genuine, not a matter of picking the freshest record.

---

### 4. Why average the duplicate-date rows in `external_factors` instead of keeping only one (e.g. first or last)?

**What I did:** `GROUP BY sales_date` with `AVG()` on GDP, inflation, seasonal factor.

**Why:** These are macroeconomic values — GDP and inflation don't plausibly change multiple times within a single day in the real world, so the duplicate rows are more likely to represent noisy/repeated *measurements* of the same underlying true value rather than genuinely different facts. Averaging is a reasonable way to reduce noise from repeated observations. Discarding rows (keeping only "first" or "last") would throw away information for no defensible reason, since there's no basis to say one row is more correct than another.

**Alternative considered:** Just picking one row per date arbitrarily. Rejected for the same non-determinism reason as #3, plus it wastes signal that averaging preserves.

---

### 5. Why `LEFT JOIN` for `external_factors` in the `inventory_summary` view, but `INNER JOIN` (plain `JOIN`) for `product_information`?

**What I did:** `sales_data JOIN product_information` (inner) but `LEFT JOIN external_factors`.

**Why:** Every sale *must* have a product — that's enforced by the foreign key constraint, so an inner join there can never silently drop a valid row. But a sale's date might not always have a matching row in `external_factors` (I deliberately checked this with `COUNT(*) WHERE gdp IS NULL` after building the view). If I'd used an inner join there and a date was missing, I would have silently lost sales records from the summary without ever knowing it. `LEFT JOIN` guarantees every sale stays in the result, with NULLs for missing economic data rather than a vanished row.

---

### 6. Why category-level statistics instead of per-product, for volatility/safety stock?

**What I did:** Computed `STDEV(inventory_quantity)` grouped by `product_category`, not by `product_id`.

**Why:** I checked first — 91.5% of products have exactly one sales record. `STDEV()` of one value is undefined (SQL Server returns NULL), so computing it per-product would have either errored out or produced NULLs for the overwhelming majority of the table. I verified this with a distribution query before deciding, rather than assuming. Category-level aggregation uses ~300+ records per group, which is statistically meaningful, and I explicitly documented that this makes the result "category-informed guidance" rather than a precise per-SKU number — I didn't present it as more precise than it actually is.

**Alternative considered:** Just reporting NULL/0 safety stock for most products. Rejected because a value of 0 safety stock is actively misleading (implies no buffer needed) rather than honestly reflecting "not enough data."

---

### 7. Why a CTE (`WITH category_stats AS (...)`) instead of a subquery or a temp table?

**What I did:** Used `WITH ... AS (...)` to compute category stats once, then joined it into the main query.

**Why:** Readability and avoiding repeated computation — without the CTE, I'd either have to repeat the `STDEV`/`AVG` subquery inline for every row (expensive and harder to read) or create a separate temp table (more steps, extra cleanup). A CTE scopes cleanly to just this one query, computes the aggregate once, and makes the query's logic easy to follow top-to-bottom: "first figure out category volatility, then use it per product."

**Alternative considered:** A permanent view for category stats. Rejected as overkill — this aggregate is only used in one or two queries, so a lightweight, query-scoped CTE fits better than a persistent database object.

---

### 8. Why `ISNULL(cs.category_stdev, 0)` in the reorder-point formula?

**Why:** Defensive coding — if a category somehow had zero variance data (edge case, didn't occur here but could in a different dataset), `NULL * anything = NULL` would silently propagate and make the entire reorder_point calculation NULL instead of just treating that category as having no measurable volatility (0). This one line prevents a single missing value from silently breaking a downstream calculation.

---

### 9. Why `USE master;` before dropping/recreating the database?

**Why:** SQL Server won't drop a database that a session is actively connected to — and simply running `DROP DATABASE` from a query window whose context was still `tech_electro` counted as "in use" even during the ALTER/rollback step. Switching to `master` first moves my own connection off the database being dropped, which is the standard fix for this specific error (`Msg 3702`).

---

### If she asks "why not just use Python/pandas for the cleaning instead of SQL?"

Honest answer: this project is specifically the DP-300 / Azure Database Administrator learning path — the point is demonstrating SQL Server competency (T-SQL, staging patterns, constraints, joins, aggregates) rather than outsourcing the logic to another language. Doing the cleaning in T-SQL keeps everything inside the database engine, versionable as `.sql` scripts, and directly demonstrates the skills the certification path is testing.

---

## Python Script Decisions

### 10. Why `warnings.filterwarnings('ignore', category=UserWarning)` at the top?

**What it does:** Suppresses the `pandas only supports SQLAlchemy connectable` warning that fires on every `pd.read_sql()` call.

**Why:** The warning is non-blocking — every query returns correct data regardless. It's triggered by newer pandas versions preferring SQLAlchemy over raw DBAPI2 connections (pyodbc is DBAPI2). Adding SQLAlchemy just to silence a cosmetic warning would introduce an unnecessary dependency. The filter is scoped to `UserWarning` only so genuine warnings from other libraries still surface. The migration path (wrapping pyodbc in `sqlalchemy.create_engine`) is noted for a future sprint if the project graduates to production.

---

### 11. Why a `save()` helper function instead of repeating `tight_layout` / `savefig` / `close` after every chart?

```python
def save(filename):
    plt.tight_layout()
    plt.savefig(os.path.join(VISUALS_DIR, filename))
    plt.close()
```

**Why:** Those three lines appeared nine times — that's 27 lines of identical boilerplate. A helper reduces it to one call per chart, makes the output path consistent (always `VISUALS_DIR`), and means if we ever need to change DPI or format (e.g. switch to `.svg`) we change it in one place. It's also self-documenting: `save("chart1.png")` reads exactly like what it does.

---

### 12. Why reuse `df` for every chart instead of `df1`, `df2`, ... `df9`?

**Why:** Each DataFrame is used immediately to draw one chart and is never referenced again. Giving them numbered names implies they'll be needed later — which is misleading — and adds nine variables that sit in memory for the rest of the script doing nothing. Reusing `df` makes the data lifetime explicit: it's created, consumed, and overwritten in the same block.

---

### 13. Why `df.groupby("product_category")` for chart 3 instead of the original `.unique()` filter loop?

**Original:**
```python
for category in df3['product_category'].unique():
    sub = df3[df3['product_category'] == category]
    plt.plot(sub['month_start'], sub['total_units_moved'], ...)
```

**Cleaned:**
```python
for cat, grp in df.groupby("product_category"):
    ax.plot(grp["month_start"], grp["total_units_moved"], label=cat, ...)
```

**Why:** `groupby` is the idiomatic pandas way to split-apply-combine. The original creates a full boolean mask on every iteration — O(n × k) where k is the number of categories. `groupby` partitions once. It's also more readable: the variable names `cat` and `grp` are descriptive, and there's no throwaway `sub` intermediate.

---

### 14. Why inline the label list comprehension for chart 4 instead of storing it in a variable?

**Original:**
```python
labels = [f"{pid} ({cat})" for pid, cat in zip(df4['product_id'], df4['product_category'])]
plt.barh(labels, df4['reorder_point'], ...)
```

**Cleaned:**
```python
ax.barh([f"{r.product_id} ({r.product_category})" for r in df.itertuples()],
        df["reorder_point"], color=BLUE)
```

**Why:** `labels` was a single-use variable — defined one line before it was consumed and never used again. Inlining it removes the name from scope. `itertuples()` is also cleaner than `zip()` over two separate column series because it accesses both attributes from the same row object, which is less likely to go out of sync if columns are reordered.

---

### 15. Why `bar.get_height()` for chart 5 labels instead of zipping with the data series?

**Original:**
```python
for bar, val in zip(bars5, df5['avg_units_per_sale']):
    ax.text(..., f'{val:.1f}', ...)
```

**Cleaned:**
```python
for bar in bars:
    ax.text(..., f'{bar.get_height():.1f}', ...)
```

**Why:** The bar object already *knows* its height — that's what was just plotted. Reading it back from `bar.get_height()` keeps the value in one source of truth (the chart itself) rather than maintaining a parallel reference to the DataFrame column. It also eliminates the `zip`, which means one fewer thing that could go out of sync.

---

### 16. Why named color constants (`DARK, BLUE, RED, GREEN, ORANGE`) instead of hex strings scattered across the file?

**Why:** The original had `'#2E3B4E'`, `'#4A90D9'`, `'#E74C3C'`, `'#E67E22'` appearing in multiple places with no indication of what they meant. Named constants make the palette explicit and consistent — if the brand colour changes, it changes in one line. It also makes the chart code read like intent: `color=RED` is self-explanatory, `color='#E74C3C'` is not.

---

### 17. Why `h1, l1 = ax1.get_legend_handles_labels()` (tuple unpacking) instead of `lines1, labels1`?

**Original:**
```python
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, ...)
```

**Cleaned:**
```python
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, ...)
```

**Why:** `lines1` and `labels1` are misleading names — `lines1` actually holds *all* handle types (bars, lines, patches), not just lines. Short names `h` and `l` (handles, labels) match the matplotlib documentation convention and reduce the name length of a variable that's only used in the very next line.

---

### 18. Why `fig, ax = plt.subplots()` consistently instead of mixing `plt.figure()` / `plt.bar()` and `fig, ax`?

**Why:** The original charts 1–4 used the stateless `plt.bar()` / `plt.title()` API while charts 5–9 used the object-oriented `ax.bar()` / `ax.set_title()` API. Mixing them in the same file is confusing and can cause subtle bugs when multiple figures are open (the stateless API always operates on the "current" figure, which can change unexpectedly). The OO API (`fig, ax`) makes the target explicit on every call, which is the matplotlib-recommended approach for anything beyond single-figure scripts.
