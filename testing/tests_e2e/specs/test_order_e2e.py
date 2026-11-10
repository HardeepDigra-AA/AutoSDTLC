"""
Enterprise E2E Playwright Specs: Advanced Real-World Testing Matrix.
Exercises:
1. Multi-Page User Journey (Registration -> Catalog Search -> Checkout -> Order History).
2. Shadow DOM piercing automation (<order-summary-widget>).
3. Network API Request Mocking & Interception.
4. Pagination & Dynamic Category Filtering.
5. Cross-Module Invariant Verification (Inventory Stock Deduction in Database).
"""
from __future__ import annotations

import json

from playwright.sync_api import Page

from testing.framework.pages.auth_page import AuthPage
from testing.framework.pages.catalog_page import CatalogPage
from testing.framework.pages.checkout_page import CheckoutPage
from testing.framework.pages.dashboard_page import OrdersDashboardPage
from testing.test_data.factories.data_factory import DatabaseTestSeeder, TestDataFactory


def test_catalog_category_filtering_and_pagination(
    auth_page: AuthPage,
    catalog_page: CatalogPage,
    db_seeder: DatabaseTestSeeder
):
    # 1. Arrange: Authenticate seeded user
    user = TestDataFactory.create_user_payload("shopper_e2e")
    db_seeder.seed_test_user(user)

    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # 2. Act: Navigate to Catalog and filter by 'Accessories'
    catalog_page.open_catalog()
    catalog_page.filter_by_category("Accessories")

    # 3. Assert: All visible items match category
    catalog_page.assert_all_visible_products_belong_to_category("Accessories")

    # 4. Act: Reset search and exercise pagination
    catalog_page.filter_by_category("ALL")
    catalog_page.navigate_to_page(2)
    assert "page=2" in catalog_page.get_current_url()

    # Teardown
    db_seeder.purge_user_orders(user.username)


def test_shadow_dom_piercing_and_coupon_calculation(
    auth_page: AuthPage,
    catalog_page: CatalogPage,
    checkout_page: CheckoutPage,
    db_seeder: DatabaseTestSeeder
):
    # 1. Arrange: Create user
    user = TestDataFactory.create_user_payload("shadow_user")
    db_seeder.seed_test_user(user)

    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # 2. Act: Go to checkout for Logitech MX Master 3S ($99.99)
    target_sku = "SKU-LOGI-MX3S"
    catalog_page.open_catalog()
    catalog_page.click_buy_now_for_sku(target_sku)

    # 3. Assert Shadow DOM initial total: Subtotal $99.99 + Tax $8.00 + Shipping $9.99 = $117.98
    checkout_page.assert_shadow_total_equals("$117.98")

    # 4. Act: Apply 'SAVE20' coupon
    checkout_page.apply_coupon("SAVE20")
    checkout_page.assert_coupon_success_message("Coupon applied! Saved $20.00")

    # 5. Assert: Shadow DOM updates dynamically!
    # ($99.99 - $20.00) = $79.99 + Tax $6.40 + Shipping $9.99 = $96.38
    checkout_page.assert_shadow_total_equals("$96.38")

    # Teardown
    db_seeder.purge_user_orders(user.username)


def test_network_interception_and_api_mocking(
    page: Page,
    auth_page: AuthPage,
    checkout_page: CheckoutPage,
    db_seeder: DatabaseTestSeeder
):
    """Demonstrates Playwright's page.route() to mock coupon validation response."""
    user = TestDataFactory.create_user_payload("mock_qa")
    db_seeder.seed_test_user(user)

    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # Set up Network Interception on /api/v1/coupons/validate
    def handle_mock_coupon(route):
        mock_payload = {"valid": True, "code": "SUPERVIP", "discount": 75.00}
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(mock_payload)
        )

    page.route("**/api/v1/coupons/validate*", handle_mock_coupon)

    # Open checkout directly
    checkout_page.navigate_to("/checkout?sku=SKU-DELL-U32")
    checkout_page.apply_coupon("SUPERVIP")

    # Assert mocked coupon result reflected in UI
    checkout_page.assert_coupon_success_message("Saved $75.00")

    # Clean up route
    page.unroute("**/api/v1/coupons/validate*")
    db_seeder.purge_user_orders(user.username)


def test_end_to_end_order_lifecycle_and_db_stock_deduction(
    auth_page: AuthPage,
    checkout_page: CheckoutPage,
    dashboard_page: OrdersDashboardPage,
    db_seeder: DatabaseTestSeeder
):
    # 1. Arrange: Check initial stock for SKU-MACBOOK-14
    target_sku = "SKU-MACBOOK-14"
    initial_stock = db_seeder.get_product_stock(target_sku)
    assert initial_stock > 0

    user = TestDataFactory.create_user_payload("order_shopper")
    db_seeder.seed_test_user(user)

    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # 2. Act: Navigate directly to checkout for SKU-MACBOOK-14 and place order
    checkout_page.navigate_to(f"/checkout?sku={target_sku}")
    checkout_page.set_quantity(2)
    checkout_page.set_shipping_speed("EXPRESS")
    checkout_page.submit_order()

    # 3. Assert UI redirects to Orders with confirmed alert
    dashboard_page.wait_for_url_contains("/orders")
    latest_order = dashboard_page.get_latest_order_number()
    assert latest_order.startswith("ORD-")

    # 4. Cross-Module Invariant Verification: Database stock must be deducted by exactly 2!
    final_stock = db_seeder.get_product_stock(target_sku)
    assert final_stock == initial_stock - 2, f"Stock invariant failed! Expected {initial_stock - 2}, got {final_stock}"

    # Teardown
    db_seeder.purge_user_orders(user.username)
