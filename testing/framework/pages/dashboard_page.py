"""
Page Object Model for the Orders Dashboard View.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

from testing.framework.pages.base_page import BasePage


class OrdersDashboardPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.nav_user = self.get_by_test_id("nav-user")
        self.btn_logout = self.get_by_test_id("btn-logout")
        self.select_product = self.get_by_test_id("select-product")
        self.input_quantity = self.get_by_test_id("input-quantity")
        self.input_coupon = self.get_by_test_id("input-coupon")
        self.btn_submit_order = self.get_by_test_id("btn-submit-order")
        self.orders_table = self.get_by_test_id("orders-table")
        self.order_rows = self.get_by_test_id("order-row")

    def open_dashboard(self):
        self.navigate_to("/")
        return self

    def place_order(self, sku: str, quantity: int = 1, coupon: str | None = None):
        self.select_product.select_option(value=sku)
        self.input_quantity.fill(str(quantity))
        if coupon:
            self.input_coupon.fill(coupon)
        else:
            self.input_coupon.fill("")
        self.btn_submit_order.click()

    def get_latest_order_number(self) -> str:
        first_row_order_code = self.order_rows.first.locator("[data-testid='order-number']")
        return first_row_order_code.inner_text().strip()

    def assert_user_logged_in(self, expected_username: str):
        expect(self.nav_user).to_be_visible()
        expect(self.nav_user).to_have_text(expected_username)

    def logout(self):
        self.btn_logout.click()
