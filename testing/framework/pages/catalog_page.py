"""
Page Object Model for the Product Catalog View.
Encapsulates search, category filters, pagination, and product selection.
"""
from __future__ import annotations

from playwright.sync_api import Page

from testing.framework.pages.base_page import BasePage


class CatalogPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.search_input = self.get_by_test_id("search-input")
        self.category_filter = self.get_by_test_id("category-filter")
        self.btn_search = self.get_by_test_id("btn-search")
        self.products_grid = self.get_by_test_id("products-grid")
        self.product_cards = self.get_by_test_id("product-card")
        self.pagination_container = self.get_by_test_id("pagination-container")

    def open_catalog(self):
        self.navigate_to("/catalog")
        return self

    def filter_by_category(self, category_name: str):
        self.category_filter.select_option(value=category_name)
        self.btn_search.click()

    def search_product(self, query: str):
        self.search_input.fill(query)
        self.btn_search.click()

    def click_buy_now_for_sku(self, sku: str):
        card = self.page.locator(f"[data-testid='product-card'][data-sku='{sku}']")
        card.locator("[data-testid='btn-buy-now']").click()

    def navigate_to_page(self, page_number: int):
        self.get_by_test_id(f"pagination-page-{page_number}").click()

    def assert_all_visible_products_belong_to_category(self, expected_category: str):
        category_labels = self.product_cards.locator("[data-testid='product-category']").all_inner_texts()
        for cat in category_labels:
            assert cat.upper() == expected_category.upper(), f"Expected {expected_category}, got {cat}"
