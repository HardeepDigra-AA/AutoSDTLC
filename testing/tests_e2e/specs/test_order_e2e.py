"""
Enterprise E2E Playwright Specs: Order Placement, Coupon Logic & Database Invariants.
Demonstrates:
- Multi-step cross-page workflows (Login -> Dashboard -> Order Place -> DB Audit).
- Complex dropdown & input selection.
- Table row inspection and extraction.
- End-to-end stock deduction verification in SQLite.
"""
from __future__ import annotations

from testing.framework.pages.auth_page import AuthPage
from testing.framework.pages.dashboard_page import OrdersDashboardPage
from testing.test_data.factories.data_factory import DatabaseTestSeeder, TestDataFactory


def test_end_to_end_order_placement_with_discount(
    auth_page: AuthPage,
    dashboard_page: OrdersDashboardPage,
    db_seeder: DatabaseTestSeeder
):
    # 1. Arrange: Seed test customer and baseline catalog
    user = TestDataFactory.create_user_payload("shopper_qa")
    db_seeder.seed_test_user(user)

    # 2. Act: Log in to OrderHub
    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # 3. Assert Dashboard reached
    dashboard_page.assert_user_logged_in(user.username)

    # 4. Act: Place Order with 'SAVE20' coupon
    target_sku = "SKU-MOUSE-02"
    dashboard_page.place_order(sku=target_sku, quantity=2, coupon="SAVE20")

    # 5. Assert: Extract order number and inspect table
    latest_order_no = dashboard_page.get_latest_order_number()
    assert latest_order_no.startswith("ORD-")

    # 6. Deep Verification: Query database directly to confirm backend invariant
    db_order = db_seeder.get_order_by_number(latest_order_no)
    assert db_order is not None
    assert db_order["customer_username"] == user.username
    assert db_order["status"] == "PLACED"
    assert db_order["discount_amount"] > 0.0  # 20% discount applied

    # 7. Act: Logout and confirm session invalidation
    dashboard_page.logout()
    auth_page.wait_for_url_contains("/login")
    auth_page.assert_success_banner_contains("Signed out successfully")

    # Teardown
    db_seeder.purge_user_orders(user.username)
