"""
Page Object Model for the Warehouse Inventory View.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

from testing.framework.pages.base_page import BasePage


class WarehousePage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.select_batch_sku = self.get_by_test_id("select-batch-sku")
        self.input_batch_number = self.get_by_test_id("input-batch-number")
        self.input_batch_qty = self.get_by_test_id("input-batch-qty")
        self.btn_receive_batch = self.get_by_test_id("btn-receive-batch")
        self.alert_success = self.get_by_test_id("alert-success")
        self.batches_table = self.get_by_test_id("batches-table")
        self.batch_rows = self.get_by_test_id("batch-row")

    def open_inventory(self):
        self.navigate_to("/inventory")
        return self

    def receive_stock_batch(self, sku: str, batch_number: str, quantity: int):
        self.select_batch_sku.select_option(value=sku)
        self.input_batch_number.fill(batch_number)
        self.input_batch_qty.fill(str(quantity))
        self.btn_receive_batch.click()

    def assert_success_banner_contains(self, text: str):
        expect(self.alert_success).to_be_visible()
        expect(self.alert_success).to_contain_text(text)
