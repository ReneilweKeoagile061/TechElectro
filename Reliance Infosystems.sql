--i am adding a use master to get session active connection off db before i DROP prev runs--
USE master;
GO

IF DB_ID('tech_electro') IS NOT NULL
BEGIN
    ALTER DATABASE tech_electro SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE tech_electro;
END
GO

CREATE DATABASE tech_electro;
GO

USE tech_electro;
GO

--Create tables--

CREATE TABLE product_information (
    product_id INT PRIMARY KEY,
    product_category VARCHAR(50),
    promotions VARCHAR(10)
);

CREATE TABLE sales_data (
    sales_id INT IDENTITY(1,1) PRIMARY KEY,
    product_id INT NOT NULL,
    sales_date DATE NOT NULL,
    inventory_quantity INT,
    product_cost DECIMAL(10,2),
    FOREIGN KEY (product_id) REFERENCES product_information(product_id)
);

CREATE TABLE external_factors (
    sales_date DATE PRIMARY KEY,
    gdp DECIMAL(18,2),
    inflation_rate DECIMAL(5,2),
    seasonal_factor DECIMAL(5,2)
);
GO

--staging tables--

CREATE TABLE staging_product_information (
    Product_ID        NVARCHAR(50),
    Product_Category  NVARCHAR(50),
    Promotions        NVARCHAR(50)
);

CREATE TABLE staging_sales_data (
    Product_ID          NVARCHAR(50),
    Sales_Date          NVARCHAR(50),
    Inventory_Quantity  NVARCHAR(50),
    Product_Cost        NVARCHAR(50)
);

CREATE TABLE staging_external_factors (
    Sales_Date        NVARCHAR(50),
    GDP               NVARCHAR(50),
    Inflation_Rate    NVARCHAR(50),
    Seasonal_Factor   NVARCHAR(50)
);
GO

--load the raw CSVs from Refilwe--

BULK INSERT staging_product_information
FROM 'C:\Users\pc\Downloads\Product_Information.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');

BULK INSERT staging_sales_data
FROM 'C:\Users\pc\Downloads\Sales data.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');

BULK INSERT staging_external_factors
FROM 'C:\Users\pc\Downloads\External_Factors.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');

--verify success on staging--

SELECT 'product_information' AS tbl, COUNT(*) AS row_count FROM staging_product_information
UNION ALL
SELECT 'sales_data', COUNT(*) FROM staging_sales_data
UNION ALL
SELECT 'external_factors', COUNT(*) FROM staging_external_factors;

--TRANSFORMATIONS BEGIN; CLEAN + LOAD--

--Dedupe product_information on a rule of "yes wins" for conflicting promotions--

INSERT INTO product_information (product_id, product_category, promotions)
SELECT
    CAST(Product_ID AS INT),
    MAX(Product_Category),
    CASE WHEN MAX(CASE WHEN Promotions = 'Yes' THEN 1 ELSE 0 END) = 1 THEN 'Yes' ELSE 'No' END
FROM staging_product_information
GROUP BY CAST(Product_ID AS INT);

--Load the sales_data--

INSERT INTO sales_data (product_id, sales_date, inventory_quantity, product_cost)
SELECT
    CAST(Product_ID AS INT),
    CONVERT(DATE, Sales_Date, 103),
    CAST(Inventory_Quantity AS INT),
    CAST(Product_Cost AS DECIMAL(10,2))
FROM staging_sales_data;

--load external_factors and chose to avg duplicate-date conflicts--

INSERT INTO external_factors (sales_date, gdp, inflation_rate, seasonal_factor)
SELECT
    CONVERT(DATE, Sales_Date, 103) AS sales_date,
    AVG(CAST(GDP AS DECIMAL(18,2))),
    AVG(CAST(Inflation_Rate AS DECIMAL(5,2))),
    AVG(CAST(Seasonal_Factor AS DECIMAL(5,2)))
FROM staging_external_factors
GROUP BY CONVERT(DATE, Sales_Date, 103);

--VERIFY--

SELECT COUNT(*) FROM product_information;   -- expect 1375
SELECT COUNT(*) FROM sales_data;            -- expect 1500
SELECT COUNT(*) FROM external_factors;      -- expect 1019

SELECT TOP 5 * FROM product_information ORDER BY product_id;
SELECT TOP 5 * FROM sales_data ORDER BY sales_id;
SELECT TOP 5 * FROM external_factors ORDER BY sales_date;

--IF success, DROP staging table--

DROP TABLE staging_product_information, staging_sales_data, staging_external_factors;

--Build the inventory_summary view — joins all three--

CREATE VIEW inventory_summary AS
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
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
LEFT JOIN external_factors e ON s.sales_date = e.sales_date;
GO

--small thing to check is if sales dates have matching external_factors dates--
--Inner join might drop off sales records therefore i prefer LEFT JOIN--

SELECT COUNT(*) FROM inventory_summary WHERE gdp IS NULL;

--INVENTORY OPTIMIZATION ANALYSIS--

-- A. Demand pattern per product: average, variability, and trend signal
SELECT
    product_id,
    COUNT(*) AS num_sales_records,
    AVG(inventory_quantity) AS avg_units_per_sale,
    MIN(inventory_quantity) AS min_units,
    MAX(inventory_quantity) AS max_units,
    STDEV(inventory_quantity) AS demand_volatility
FROM sales_data
GROUP BY product_id
ORDER BY demand_volatility DESC;

-- B. Category-level view: which categories are highest velocity / most volatile
SELECT
    p.product_category,
    COUNT(*) AS total_records,
    SUM(s.inventory_quantity) AS total_units_moved,
    AVG(s.inventory_quantity) AS avg_units_per_sale,
    AVG(s.product_cost) AS avg_unit_cost
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
GROUP BY p.product_category
ORDER BY total_units_moved DESC;

-- C. Simple reorder point estimate per product
-- Reorder point = (avg daily demand * lead time) + safety stock
-- Using STDEV as a stand-in for demand variability (safety stock = z * stdev * sqrt(lead time))
-- Assuming a 7-day lead time and a 1.65 z-score (~95% service level) as a starting assumption
SELECT
    product_id,
    AVG(inventory_quantity) AS avg_demand,
    STDEV(inventory_quantity) AS demand_stdev,
    (AVG(inventory_quantity) * 7) AS lead_time_demand,
    (1.65 * ISNULL(STDEV(inventory_quantity), 0) * SQRT(7)) AS safety_stock,
    (AVG(inventory_quantity) * 7) + (1.65 * ISNULL(STDEV(inventory_quantity), 0) * SQRT(7)) AS reorder_point
FROM sales_data
GROUP BY product_id
ORDER BY reorder_point DESC;

-- D. Promotion impact check: does "Yes" promotion correlate with higher demand?
SELECT
    p.promotions,
    AVG(s.inventory_quantity) AS avg_units_per_sale,
    COUNT(*) AS num_records
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
GROUP BY p.promotions;

-- E. Seasonal factor correlation (rough): average demand by seasonal_factor band
SELECT
    CASE 
        WHEN e.seasonal_factor < 0.95 THEN 'Low season'
        WHEN e.seasonal_factor BETWEEN 0.95 AND 1.05 THEN 'Normal'
        ELSE 'High season'
    END AS season_band,
    AVG(s.inventory_quantity) AS avg_units_per_sale,
    COUNT(*) AS num_records
FROM sales_data s
JOIN external_factors e ON s.sales_date = e.sales_date
GROUP BY CASE 
        WHEN e.seasonal_factor < 0.95 THEN 'Low season'
        WHEN e.seasonal_factor BETWEEN 0.95 AND 1.05 THEN 'Normal'
        ELSE 'High season'
    END;

--INSIGHTS--

--Query C — demand_stdev is NULL for every row. This isn't broken,it's communicating... With 1,500 sales records spread across 1,375 unique products, the average product has only ~1.1 sales records. STDEV() of a single value is mathematically undefined, so SQL Server correctly returns NULL.--

--Lets investigate--
SELECT product_id, COUNT(*) AS num_records
FROM sales_data
GROUP BY product_id
ORDER BY num_records DESC;

--Output : max is only 3 records per product, and most products have 1–2. With 1,375 products and 1,500 sales rows, you genuinely can't compute reliable per-product volatility from this data; there's just not enough repetition.--
--lets see the distribution shape--
SELECT num_records, COUNT(*) AS how_many_products
FROM (
    SELECT product_id, COUNT(*) AS num_records
    FROM sales_data
    GROUP BY product_id
) t
GROUP BY num_records
ORDER BY num_records;

--Output: 1,258 of 1,375 products (91.5%) have only a single sales observation. Only 109 have 2, and just 8 have 3. That single fact justifies the category-level pivot on its own — no reasonable analyst could compute meaningful per-SKU volatility from that distribution.--


--RE_ORDER QUERY--

-- Category-level demand stats (statistically meaningful, unlike per-product)
WITH category_stats AS (
    SELECT
        p.product_category,
        AVG(CAST(s.inventory_quantity AS FLOAT)) AS avg_demand,
        STDEV(s.inventory_quantity) AS category_stdev
    FROM sales_data s
    JOIN product_information p ON s.product_id = p.product_id
    GROUP BY p.product_category
)
-- Reorder point per product, using its own avg demand but category-level volatility
SELECT
    s.product_id,
    p.product_category,
    AVG(CAST(s.inventory_quantity AS FLOAT)) AS product_avg_demand,
    cs.category_stdev,
    (AVG(CAST(s.inventory_quantity AS FLOAT)) * 7) AS lead_time_demand,
    (1.65 * ISNULL(cs.category_stdev, 0) * SQRT(7)) AS safety_stock,
    (AVG(CAST(s.inventory_quantity AS FLOAT)) * 7) 
        + (1.65 * ISNULL(cs.category_stdev, 0) * SQRT(7)) AS reorder_point
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
JOIN category_stats cs ON p.product_category = cs.product_category
GROUP BY s.product_id, p.product_category, cs.category_stdev
ORDER BY reorder_point DESC;

--OUTPUT--
--,375 rows returned, no NULLs in category_stdev, and the ranking makes sense: SmartPhones and Home_Appliances (higher category-level volatility, ~29.5 and 29.4) push reorder points up around 828–829, while Electronics (lower stdev, ~27.8) settles a bit lower. Laptops split — some rows at 826 and some lower, tracking their own product_avg_demand of 100 vs 99.--

--Haha, let me investigate seasonal bands--
SELECT
    CASE 
        WHEN e.seasonal_factor < 0.95 THEN 'Low season'
        WHEN e.seasonal_factor BETWEEN 0.95 AND 1.05 THEN 'Normal'
        ELSE 'High season'
    END AS season_band,
    AVG(CAST(s.inventory_quantity AS FLOAT)) AS avg_units_per_sale,
    COUNT(*) AS num_records
FROM sales_data s
JOIN external_factors e ON s.sales_date = e.sales_date
GROUP BY CASE 
        WHEN e.seasonal_factor < 0.95 THEN 'Low season'
        WHEN e.seasonal_factor BETWEEN 0.95 AND 1.05 THEN 'Normal'
        ELSE 'High season'
    END
ORDER BY avg_units_per_sale DESC;


--Top 10 highest reorder-point products--
WITH category_stats AS (
    SELECT
        p.product_category,
        STDEV(s.inventory_quantity) AS category_stdev
    FROM sales_data s
    JOIN product_information p ON s.product_id = p.product_id
    GROUP BY p.product_category
)
SELECT TOP 10
    s.product_id,
    p.product_category,
    p.promotions,
    ROUND(AVG(CAST(s.inventory_quantity AS FLOAT)), 1) AS avg_demand,
    ROUND((AVG(CAST(s.inventory_quantity AS FLOAT)) * 7) 
        + (1.65 * ISNULL(cs.category_stdev, 0) * SQRT(7)), 1) AS reorder_point
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
JOIN category_stats cs ON p.product_category = cs.product_category
GROUP BY s.product_id, p.product_category, p.promotions, cs.category_stdev
ORDER BY reorder_point DESC;

--Overstock / dead-stock risk query--
WITH category_stats AS (
    SELECT
        p.product_category,
        AVG(CAST(s.inventory_quantity AS FLOAT)) AS category_avg_demand
    FROM sales_data s
    JOIN product_information p ON s.product_id = p.product_id
    GROUP BY p.product_category
)
SELECT
    s.product_id,
    p.product_category,
    ROUND(AVG(CAST(s.inventory_quantity AS FLOAT)), 1) AS product_avg_demand,
    ROUND(cs.category_avg_demand, 1) AS category_avg_demand,
    ROUND(AVG(s.product_cost), 2) AS avg_unit_cost,
    ROUND(AVG(CAST(s.inventory_quantity AS FLOAT)) * AVG(s.product_cost), 2) AS capital_tied_up_estimate,
    CASE 
        WHEN AVG(CAST(s.inventory_quantity AS FLOAT)) < (cs.category_avg_demand * 0.5) 
        THEN 'Overstock risk — low velocity'
        ELSE 'Normal'
    END AS risk_flag
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
JOIN category_stats cs ON p.product_category = cs.product_category
GROUP BY s.product_id, p.product_category, cs.category_avg_demand
HAVING AVG(CAST(s.inventory_quantity AS FLOAT)) < (cs.category_avg_demand * 0.5)
ORDER BY capital_tied_up_estimate DESC;

--Demand trend--
SELECT
    p.product_category,
    DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1) AS month_start,
    COUNT(*) AS num_transactions,
    ROUND(AVG(CAST(s.inventory_quantity AS FLOAT)), 1) AS avg_units_per_sale,
    SUM(s.inventory_quantity) AS total_units_moved
FROM sales_data s
JOIN product_information p ON s.product_id = p.product_id
GROUP BY p.product_category, DATEFROMPARTS(YEAR(s.sales_date), MONTH(s.sales_date), 1)
ORDER BY p.product_category, month_start;
