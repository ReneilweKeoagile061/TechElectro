"""
tests/test_azure_connection.py
Integration / smoke tests against the live Azure SQL database.
These are SKIPPED automatically if Azure credentials are not set,
so they don't block local development or CI runs without secrets.
"""

import os

import pandas as pd
import pytest

# Skip entire module if secrets are not available
pytestmark = pytest.mark.skipif(
    not os.getenv("server"),
    reason="Azure SQL secrets not configured — set env vars server/database/username/password to run.",
)


def get_azure_conn():
    import pyodbc

    cs = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER=tcp:{os.environ['server']},1433;"
        f"DATABASE={os.environ.get('database', 'tech_electro')};"
        f"UID={os.environ['username']};"
        f"PWD={os.environ['password']};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(cs, timeout=30)


@pytest.fixture(scope="module")
def azure_conn():
    conn = get_azure_conn()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Connection smoke tests
# ---------------------------------------------------------------------------
class TestAzureConnection:
    def test_connection_succeeds(self, azure_conn):
        """Basic ping — SELECT 1 must succeed."""
        cur = azure_conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1

    def test_database_is_tech_electro(self, azure_conn):
        cur = azure_conn.cursor()
        cur.execute("SELECT DB_NAME()")
        assert cur.fetchone()[0] == "tech_electro"


# ---------------------------------------------------------------------------
# Table existence & row count tests
# ---------------------------------------------------------------------------
class TestTablePopulation:
    @pytest.mark.parametrize(
        "table,min_rows",
        [
            ("product_information", 1000),
            ("sales_data", 1000),
            ("external_factors", 500),
        ],
    )
    def test_table_has_minimum_rows(self, azure_conn, table, min_rows):
        cur = azure_conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        assert count >= min_rows, f"{table} has only {count} rows (expected >= {min_rows})"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestTableSchema:
    def test_product_information_columns(self, azure_conn):
        cur = azure_conn.cursor()
        cur.execute("SELECT TOP 1 * FROM product_information")
        columns = {d[0].lower() for d in cur.description}
        assert {"product_id", "product_category", "promotions"}.issubset(columns)

    def test_sales_data_columns(self, azure_conn):
        cur = azure_conn.cursor()
        cur.execute("SELECT TOP 1 * FROM sales_data")
        columns = {d[0].lower() for d in cur.description}
        assert {
            "sales_id",
            "product_id",
            "sales_date",
            "inventory_quantity",
            "product_cost",
        }.issubset(columns)

    def test_external_factors_columns(self, azure_conn):
        cur = azure_conn.cursor()
        cur.execute("SELECT TOP 1 * FROM external_factors")
        columns = {d[0].lower() for d in cur.description}
        assert {"sales_date", "gdp", "inflation_rate", "seasonal_factor"}.issubset(columns)


# ---------------------------------------------------------------------------
# Dashboard query test
# ---------------------------------------------------------------------------
class TestDashboardQuery:
    def test_main_query_returns_rows(self, azure_conn):
        """The exact query used by the dashboard must return data."""
        query = """
            SELECT
                s.sales_id, s.product_id, p.product_category, p.promotions,
                s.sales_date, s.inventory_quantity, s.product_cost,
                e.gdp, e.inflation_rate, e.seasonal_factor
            FROM sales_data AS s
            INNER JOIN product_information AS p ON s.product_id = p.product_id
            LEFT JOIN external_factors AS e ON s.sales_date = e.sales_date
        """
        df = pd.read_sql(query, azure_conn)
        assert len(df) > 0, "Dashboard query returned no rows"

    def test_main_query_has_required_columns(self, azure_conn):
        query = """
            SELECT TOP 1
                s.sales_id, s.product_id, p.product_category, p.promotions,
                s.sales_date, s.inventory_quantity, s.product_cost,
                e.gdp, e.inflation_rate, e.seasonal_factor
            FROM sales_data AS s
            INNER JOIN product_information AS p ON s.product_id = p.product_id
            LEFT JOIN external_factors AS e ON s.sales_date = e.sales_date
        """
        df = pd.read_sql(query, azure_conn)
        required = {
            "product_id",
            "product_category",
            "promotions",
            "sales_date",
            "inventory_quantity",
            "product_cost",
        }
        assert required.issubset(set(df.columns))

    def test_no_null_product_categories(self, azure_conn):
        cur = azure_conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM sales_data s "
            "INNER JOIN product_information p ON s.product_id = p.product_id "
            "WHERE p.product_category IS NULL"
        )
        assert cur.fetchone()[0] == 0
