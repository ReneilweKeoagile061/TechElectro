"""
tests/test_data_filters.py
Unit tests for sidebar filter logic — category, promotion, and SKU search.
All tests run in-memory, no database required.
"""

import pandas as pd
import pytest


def apply_category_filter(df, selected_categories):
    return df[df["product_category"].isin(selected_categories)].copy()


def apply_promo_filter(df, promo_filter):
    if promo_filter == "Promoted Only (Yes)":
        return df[df["promotions"].fillna("").astype(str).str.lower().eq("yes")]
    elif promo_filter == "Non-Promoted (No)":
        return df[df["promotions"].fillna("").astype(str).str.lower().eq("no")]
    return df


def apply_sku_search(df, search_sku):
    search = search_sku.strip()
    if search:
        try:
            return df[df["product_id"] == int(search)]
        except ValueError:
            return df  # non-numeric — no filter applied
    return df


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------
class TestCategoryFilter:
    def test_all_categories_returns_full_dataset(self, sample_df):
        categories = sample_df["product_category"].unique().tolist()
        result = apply_category_filter(sample_df, categories)
        assert len(result) == len(sample_df)

    def test_single_category_returns_only_that_category(self, sample_df):
        result = apply_category_filter(sample_df, ["Laptops"])
        assert set(result["product_category"].unique()) == {"Laptops"}

    def test_empty_selection_returns_empty(self, sample_df):
        result = apply_category_filter(sample_df, [])
        assert result.empty

    def test_unknown_category_returns_empty(self, sample_df):
        result = apply_category_filter(sample_df, ["Televisions"])
        assert result.empty

    def test_multiple_categories_returns_union(self, sample_df):
        result = apply_category_filter(sample_df, ["Laptops", "SmartPhones"])
        cats = set(result["product_category"].unique())
        assert cats == {"Laptops", "SmartPhones"}


# ---------------------------------------------------------------------------
# Promotion filter
# ---------------------------------------------------------------------------
class TestPromotionFilter:
    def test_all_returns_unchanged(self, sample_df):
        result = apply_promo_filter(sample_df, "All Products")
        assert len(result) == len(sample_df)

    def test_promoted_only_returns_yes_rows(self, sample_df):
        result = apply_promo_filter(sample_df, "Promoted Only (Yes)")
        assert all(result["promotions"].str.lower() == "yes")

    def test_non_promoted_returns_no_rows(self, sample_df):
        result = apply_promo_filter(sample_df, "Non-Promoted (No)")
        assert all(result["promotions"].str.lower() == "no")

    def test_promoted_and_non_promoted_are_disjoint(self, sample_df):
        promoted = apply_promo_filter(sample_df, "Promoted Only (Yes)")
        non_promoted = apply_promo_filter(sample_df, "Non-Promoted (No)")
        overlap = set(promoted.index) & set(non_promoted.index)
        assert len(overlap) == 0

    def test_promoted_plus_non_promoted_equals_all(self, sample_df):
        all_rows = len(sample_df)
        promoted = len(apply_promo_filter(sample_df, "Promoted Only (Yes)"))
        non_prom = len(apply_promo_filter(sample_df, "Non-Promoted (No)"))
        assert promoted + non_prom == all_rows


# ---------------------------------------------------------------------------
# SKU search filter
# ---------------------------------------------------------------------------
class TestSKUSearch:
    def test_valid_id_returns_matching_rows(self, sample_df):
        result = apply_sku_search(sample_df, "101")
        assert all(result["product_id"] == 101)

    def test_empty_string_returns_all(self, sample_df):
        result = apply_sku_search(sample_df, "")
        assert len(result) == len(sample_df)

    def test_whitespace_only_returns_all(self, sample_df):
        result = apply_sku_search(sample_df, "   ")
        assert len(result) == len(sample_df)

    def test_non_numeric_input_returns_all(self, sample_df):
        """Invalid input should not crash — returns unfiltered data."""
        result = apply_sku_search(sample_df, "abc")
        assert len(result) == len(sample_df)

    def test_non_existent_id_returns_empty(self, sample_df):
        result = apply_sku_search(sample_df, "99999")
        assert result.empty

    def test_search_with_whitespace_padding(self, sample_df):
        """Leading/trailing whitespace should be stripped."""
        result = apply_sku_search(sample_df, "  102  ")
        assert all(result["product_id"] == 102)


# ---------------------------------------------------------------------------
# Combined filter chain
# ---------------------------------------------------------------------------
class TestCombinedFilters:
    def test_category_then_promo_filter(self, sample_df):
        df = apply_category_filter(sample_df, ["Laptops"])
        df = apply_promo_filter(df, "Promoted Only (Yes)")
        assert set(df["product_category"].unique()) == {"Laptops"}
        assert all(df["promotions"].str.lower() == "yes")

    def test_all_filters_narrow_results(self, sample_df):
        df = apply_category_filter(sample_df, ["SmartPhones"])
        df = apply_promo_filter(df, "Promoted Only (Yes)")
        df = apply_sku_search(df, "103")
        assert all(df["product_id"] == 103)
        assert all(df["product_category"] == "SmartPhones")
