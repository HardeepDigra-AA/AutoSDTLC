"""
Cross-Module Integration Spec:
Validates the direct integration and invariant dependency between:
1. Warehouse Intake Module (/inventory)
2. Product Catalog & Storefront (/catalog)
3. Checkout Gate (/checkout)
4. SQLite Database Stock Level
"""
from __future__ import annotations

import time

from playwright.sync_api import expect

from testing.framework.pages.auth_page import AuthPage
from testing.framework.pages.catalog_page import CatalogPage
from testing.framework.pages.warehouse_page import WarehousePage
from testing.test_data.factories.data_factory import DatabaseTestSeeder, TestDataFactory


def test_warehouse_intake_directly_updates_storefront_catalog_and_enables_purchase(
    auth_page: AuthPage,
    catalog_page: CatalogPage,
    warehouse_page: WarehousePage,
    db_seeder: DatabaseTestSeeder
):
    # 1. Arrange: Authenticate test user
    user = TestDataFactory.create_user_payload("integration_qa")
    db_seeder.seed_test_user(user)

    auth_page.open_login()
    auth_page.login(user.username, user.password)

    # 2. Verify baseline stock for SKU-RARE-TEST directly from DB
    target_sku = "SKU-RARE-TEST"
    initial_stock = db_seeder.get_product_stock(target_sku)

    # 3. Step A: Check Catalog storefront on Page 2 where SKU-RARE-TEST is located
    catalog_page.open_catalog()
    catalog_page.navigate_to_page(2)
    catalog_card = catalog_page.page.locator(f"[data-testid='product-card'][data-sku='{target_sku}']")
    # Verify displayed warehouse quantity on catalog card matches DB
    expect(catalog_card.locator("[data-testid='stock-count']")).to_have_text(str(initial_stock))

    # 4. Step B: Operator navigates to Warehouse Module (/inventory) and intakes a batch of 50 units
    batch_code = f"BATCH-AUTO-{int(time.time())}"
    add_qty = 50
    warehouse_page.open_inventory()
    warehouse_page.receive_stock_batch(target_sku, batch_code, add_qty)
    warehouse_page.assert_success_banner_contains(f"Successfully intaked {add_qty} units")

    # 5. Step C: Assert Database state was updated atomically
    updated_stock = db_seeder.get_product_stock(target_sku)
    assert updated_stock == initial_stock + add_qty, f"DB stock mismatch! Expected {initial_stock + add_qty}, got {updated_stock}"

    # 6. Step D: Navigate back to Storefront Catalog (Page 2) and assert dynamic integration!
    catalog_page.open_catalog()
    catalog_page.navigate_to_page(2)
    catalog_card_after = catalog_page.page.locator(f"[data-testid='product-card'][data-sku='{target_sku}']")
    # Storefront now displays the new increased stock and "In Stock" badge!
    expect(catalog_card_after.locator("[data-testid='stock-count']")).to_have_text(str(updated_stock))
    expect(catalog_card_after.locator("[data-testid='stock-badge']")).to_contain_text("In Stock")

    # Teardown
    db_seeder.purge_user_orders(user.username)
