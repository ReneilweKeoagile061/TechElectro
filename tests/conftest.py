"""
tests/conftest.py
Shared pytest fixtures for TechElectro Inventory Analytics Engine.
"""

import pandas as pd
import pytest


@pytest.fixture
def sample_df():
    """Minimal but realistic dataset matching the app's SQL query output."""
    return pd.DataFrame(
        {
            "sales_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "product_id": [101, 101, 102, 102, 103, 103, 104, 104],
            "product_category": [
                "Laptops",
                "Laptops",
                "Laptops",
                "Laptops",
                "SmartPhones",
                "SmartPhones",
                "SmartPhones",
                "SmartPhones",
            ],
            "promotions": ["Yes", "Yes", "No", "No", "Yes", "No", "No", "No"],
            "sales_date": pd.to_datetime(
                [
                    "2022-01-15",
                    "2022-02-20",
                    "2022-01-10",
                    "2022-03-05",
                    "2022-02-14",
                    "2022-04-01",
                    "2022-01-22",
                    "2022-05-10",
                ]
            ),
            "inventory_quantity": [5.0, 7.0, 50.0, 55.0, 20.0, 22.0, 2.0, 3.0],
            "product_cost": [800.0, 800.0, 600.0, 600.0, 400.0, 400.0, 350.0, 350.0],
            "gdp": [1.5, 1.6, 1.5, 1.7, 1.6, 1.5, 1.4, 1.6],
            "inflation_rate": [5.2, 5.3, 5.2, 5.4, 5.3, 5.2, 5.1, 5.3],
            "seasonal_factor": [1.0, 1.1, 1.0, 1.2, 1.1, 1.0, 0.9, 1.1],
        }
    )


@pytest.fixture
def cat_stats(sample_df):
    """Category-level aggregations as produced by the app."""
    stats = (
        sample_df.groupby("product_category", dropna=False)
        .agg(
            avg_demand=("inventory_quantity", "mean"),
            category_stdev=("inventory_quantity", "std"),
            total_units=("inventory_quantity", "sum"),
        )
        .reset_index()
    )
    stats["category_stdev"] = stats["category_stdev"].fillna(0)
    return stats


@pytest.fixture
def df_sku(sample_df, cat_stats):
    """SKU-level aggregations merged with category stats."""
    sku = (
        sample_df.groupby(["product_id", "product_category", "promotions"], dropna=False)
        .agg(
            sku_demand=("inventory_quantity", "mean"),
            sku_cost=("product_cost", "mean"),
        )
        .reset_index()
    )
    sku = sku.merge(
        cat_stats[["product_category", "avg_demand", "category_stdev"]],
        on="product_category",
        how="left",
    )
    sku["sku_cost"] = sku["sku_cost"].fillna(0)
    return sku
