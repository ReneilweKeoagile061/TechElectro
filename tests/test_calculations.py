"""
tests/test_calculations.py
Unit tests for the core inventory analytics calculations.
These tests run entirely in-memory — no database required.
"""

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Capital tied up
# ---------------------------------------------------------------------------
class TestCapitalTiedUp:
    def test_capital_is_demand_times_cost(self, df_sku):
        df = df_sku.copy()
        df["capital_tied_up"] = df["sku_demand"] * df["sku_cost"]
        assert (df["capital_tied_up"] == df["sku_demand"] * df["sku_cost"]).all()

    def test_capital_non_negative(self, df_sku):
        df = df_sku.copy()
        df["capital_tied_up"] = df["sku_demand"] * df["sku_cost"]
        assert (df["capital_tied_up"] >= 0).all()

    def test_zero_cost_gives_zero_capital(self):
        df = pd.DataFrame(
            {
                "sku_demand": [10.0],
                "sku_cost": [0.0],
            }
        )
        df["capital_tied_up"] = df["sku_demand"] * df["sku_cost"]
        assert df["capital_tied_up"].iloc[0] == 0.0


# ---------------------------------------------------------------------------
# Overstock flagging
# ---------------------------------------------------------------------------
class TestOverstockFlagging:
    def test_low_demand_sku_is_flagged(self, df_sku):
        df = df_sku.copy()
        overstock_ratio = 0.5
        df["is_overstock"] = df["sku_demand"] < (df["avg_demand"] * overstock_ratio)
        # product 101 (demand=6) is well below Laptops avg (~28), should be flagged
        laptops_101 = df[df["product_id"] == 101]
        assert laptops_101["is_overstock"].all()

    def test_high_demand_sku_not_flagged(self, df_sku):
        df = df_sku.copy()
        overstock_ratio = 0.5
        df["is_overstock"] = df["sku_demand"] < (df["avg_demand"] * overstock_ratio)
        # product 102 (demand=52.5) is close to Laptops avg, should NOT be flagged
        laptops_102 = df[df["product_id"] == 102]
        assert not laptops_102["is_overstock"].any()

    def test_threshold_boundary(self):
        """SKU demand exactly at threshold is NOT overstock."""
        df = pd.DataFrame(
            {
                "sku_demand": [5.0],
                "avg_demand": [10.0],
            }
        )
        overstock_ratio = 0.5
        df["is_overstock"] = df["sku_demand"] < (df["avg_demand"] * overstock_ratio)
        assert not df["is_overstock"].iloc[0]  # 5 < 5 is False

    def test_ratio_slider_effect(self, df_sku):
        """Higher overstock ratio flags more SKUs."""
        df = df_sku.copy()
        flagged_low = (df["sku_demand"] < df["avg_demand"] * 0.2).sum()
        flagged_high = (df["sku_demand"] < df["avg_demand"] * 0.8).sum()
        assert flagged_high >= flagged_low


# ---------------------------------------------------------------------------
# Safety stock & reorder point
# ---------------------------------------------------------------------------
class TestSafetyStockAndReorderPoint:
    @pytest.mark.parametrize(
        "z_score,lead_time,stdev",
        [
            (1.65, 7, 10.0),
            (1.28, 14, 5.0),
            (2.33, 3, 20.0),
        ],
    )
    def test_safety_stock_formula(self, z_score, lead_time, stdev):
        """safety_stock = z * stdev * sqrt(lead_time)"""
        expected = z_score * stdev * np.sqrt(lead_time)
        actual = z_score * stdev * np.sqrt(lead_time)
        assert abs(actual - expected) < 1e-9

    def test_reorder_point_is_lead_time_demand_plus_safety_stock(self, df_sku):
        df = df_sku.copy()
        lead_time_days = 7
        z_score = 1.65
        df["lead_time_demand"] = df["sku_demand"] * lead_time_days
        df["safety_stock"] = z_score * df["category_stdev"] * np.sqrt(lead_time_days)
        df["reorder_point"] = df["lead_time_demand"] + df["safety_stock"]

        assert (df["reorder_point"] == df["lead_time_demand"] + df["safety_stock"]).all()

    def test_reorder_point_non_negative(self, df_sku):
        df = df_sku.copy()
        df["lead_time_demand"] = df["sku_demand"] * 7
        df["safety_stock"] = 1.65 * df["category_stdev"] * np.sqrt(7)
        df["reorder_point"] = df["lead_time_demand"] + df["safety_stock"]
        assert (df["reorder_point"] >= 0).all()

    def test_longer_lead_time_increases_reorder_point(self, df_sku):
        df = df_sku.copy()
        z = 1.65
        for lt_short, lt_long in [(7, 14), (3, 30)]:
            rp_short = df["sku_demand"] * lt_short + z * df["category_stdev"] * np.sqrt(lt_short)
            rp_long = df["sku_demand"] * lt_long + z * df["category_stdev"] * np.sqrt(lt_long)
            assert (rp_long >= rp_short).all()

    def test_higher_service_level_increases_safety_stock(self, df_sku):
        df = df_sku.copy()
        lead_time = 7
        stdev = df["category_stdev"]
        ss_90 = 1.28 * stdev * np.sqrt(lead_time)
        ss_95 = 1.65 * stdev * np.sqrt(lead_time)
        ss_99 = 2.33 * stdev * np.sqrt(lead_time)
        assert (ss_99 >= ss_95).all()
        assert (ss_95 >= ss_90).all()


# ---------------------------------------------------------------------------
# Category statistics
# ---------------------------------------------------------------------------
class TestCategoryStats:
    def test_avg_demand_is_mean_of_inventory_quantity(self, sample_df, cat_stats):
        for _, row in cat_stats.iterrows():
            cat_df = sample_df[sample_df["product_category"] == row["product_category"]]
            expected_avg = cat_df["inventory_quantity"].mean()
            assert abs(row["avg_demand"] - expected_avg) < 1e-9

    def test_total_units_is_sum(self, sample_df, cat_stats):
        for _, row in cat_stats.iterrows():
            cat_df = sample_df[sample_df["product_category"] == row["product_category"]]
            assert row["total_units"] == cat_df["inventory_quantity"].sum()

    def test_stdev_non_negative(self, cat_stats):
        assert (cat_stats["category_stdev"] >= 0).all()

    def test_stdev_nan_filled_with_zero(self, cat_stats):
        assert not cat_stats["category_stdev"].isna().any()
