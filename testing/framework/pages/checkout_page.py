"""
Page Object Model for the Checkout View.
Handles Shadow DOM inspection, coupon code application, and dynamic calculations.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

from testing.framework.pages.base_page import BasePage


class CheckoutPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.checkout_product_name = self.get_by_test_id("checkout-product-name")
        self.checkout_sku = self.get_by_test_id("checkout-sku")
        self.checkout_quantity = self.get_by_test_id("checkout-quantity")
        self.shipping_speed = self.get_by_test_id("shipping-speed")
        self.coupon_input = self.get_by_test_id("checkout-coupon-input")
        self.btn_apply_coupon = self.get_by_test_id("btn-apply-coupon")
        self.coupon_message = self.get_by_test_id("coupon-message")
        self.btn_confirm_order = self.get_by_test_id("btn-confirm-order")
        self.loading_spinner = self.get_by_test_id("loading-spinner")

        # Shadow DOM Piercing Locators
        # In Playwright, querying into a custom element's shadowRoot:
        self.shadow_widget = self.page.locator("order-summary-widget")
        self.shadow_final_total = self.shadow_widget.locator("#shadow-total")
        self.shadow_discount = self.shadow_widget.locator("#shadow-discount")

    def set_quantity(self, qty: int):
        self.checkout_quantity.fill(str(qty))
        self.checkout_quantity.press("Tab")

    def set_shipping_speed(self, speed: str):
        self.shipping_speed.select_option(value=speed)

    def apply_coupon(self, coupon_code: str):
        self.coupon_input.fill(coupon_code)
        self.btn_apply_coupon.click()

    def submit_order(self):
        self.btn_confirm_order.click()

    def assert_shadow_total_equals(self, expected_total: str):
        expect(self.shadow_final_total).to_have_text(expected_total)

    def assert_coupon_success_message(self, snippet: str):
        expect(self.coupon_message).to_contain_text(snippet)
