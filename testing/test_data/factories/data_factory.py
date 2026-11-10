"""
Enterprise Test Data Seeder & Factory.
Seeds complete enterprise fixtures:
- Vendors / Suppliers
- Product Catalog with categories and stock levels
- Coupons (SAVE20, FLAT50, VIP100)
- Customer Accounts with loyalty tiers
"""
from __future__ import annotations

import hashlib
import random
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UserData:
    username: str
    email: str
    password: str
    role: str = "CUSTOMER"
    loyalty_tier: str = "BRONZE"
    credits: float = 50.0


@dataclass
class ProductData:
    sku: str
    vendor_code: str
    name: str
    category: str
    price: float
    cost_price: float
    stock_quantity: int
    tags: str = "featured,enterprise"


class TestDataFactory:
    """Generates synthetic, deterministic, or randomized test entities."""

    @staticmethod
    def create_user_payload(prefix: str = "qa_user", loyalty: str = "BRONZE") -> UserData:
        unique_suffix = f"{int(time.time() * 1000) % 100000}_{random.randint(100, 999)}"
        username = f"{prefix}_{unique_suffix}"
        email = f"{username}@enterprise.test"
        password = "SecurePassword@2026!"
        return UserData(username=username, email=email, password=password, loyalty_tier=loyalty)

    @staticmethod
    def create_batch_payload(sku: str) -> dict:
        batch_no = f"BAT-{random.randint(10000, 99999)}"
        return {"sku": sku, "batch_number": batch_no, "quantity": random.randint(25, 100)}


class DatabaseTestSeeder:
    """Manages pre-test fixtures, baseline dataset seeds, and post-test teardowns."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def seed_complete_enterprise_baseline(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        # 1. Vendors
        cursor.execute("INSERT OR REPLACE INTO vendors (vendor_code, name, rating) VALUES ('VEND-APPLE', 'Apple Enterprise Distribution', 4.9)")
        cursor.execute("INSERT OR REPLACE INTO vendors (vendor_code, name, rating) VALUES ('VEND-LOGI', 'Logitech Global Supply', 4.7)")
        cursor.execute("INSERT OR REPLACE INTO vendors (vendor_code, name, rating) VALUES ('VEND-DELL', 'Dell Direct Partner', 4.6)")

        # 2. Product Catalog (Across categories for testing filters & pagination)
        catalog = [
            ("SKU-MACBOOK-16", "VEND-APPLE", "MacBook Pro 16 M3 Max", "Laptops", 3499.00, 2800.00, 15, "premium,laptops"),
            ("SKU-MACBOOK-14", "VEND-APPLE", "MacBook Pro 14 M3 Pro", "Laptops", 1999.00, 1600.00, 20, "popular,laptops"),
            ("SKU-LOGI-MX3S", "VEND-LOGI", "Logitech MX Master 3S Wireless", "Accessories", 99.99, 60.00, 45, "wireless,mouse"),
            ("SKU-LOGI-KEYB", "VEND-LOGI", "Logitech MX Mechanical Mini", "Accessories", 149.99, 90.00, 30, "keyboard,wireless"),
            ("SKU-DELL-U32", "VEND-DELL", "Dell UltraSharp 32-inch 4K USB-C Hub", "Displays", 849.00, 650.00, 12, "displays,4k"),
            ("SKU-DELL-U27", "VEND-DELL", "Dell UltraSharp 27-inch 4K IPS", "Displays", 579.00, 420.00, 25, "displays,office"),
            ("SKU-CABLE-TH4", "VEND-APPLE", "Thunderbolt 4 Pro Cable (1.8m)", "Cables", 129.00, 60.00, 50, "cables,apple"),
            ("SKU-RARE-TEST", "VEND-LOGI", "Vintage Prototype Trackball Controller", "Vintage", 499.00, 250.00, 2, "rare,lowstock"),
        ]

        for p in catalog:
            cursor.execute("""
            INSERT OR REPLACE INTO products (sku, vendor_code, name, category, price, cost_price, stock_quantity, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

        # 3. Promotional Coupons
        cursor.execute("INSERT OR REPLACE INTO coupons (code, discount_type, discount_value, min_order_amount) VALUES ('SAVE20', 'PERCENTAGE', 20.0, 50.0)")
        cursor.execute("INSERT OR REPLACE INTO coupons (code, discount_type, discount_value, min_order_amount) VALUES ('FLAT50', 'FIXED', 50.0, 200.0)")
        cursor.execute("INSERT OR REPLACE INTO coupons (code, discount_type, discount_value, min_order_amount) VALUES ('VIP100', 'FIXED', 100.0, 500.0)")

        conn.commit()
        conn.close()

    def seed_test_user(self, user: UserData) -> None:
        conn = self._get_connection()
        pw_hash = hashlib.sha256(user.password.encode("utf-8")).hexdigest()
        conn.execute("""
        INSERT OR REPLACE INTO users (username, email, password_hash, role, loyalty_tier, credits)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user.username, user.email, pw_hash, user.role, user.loyalty_tier, user.credits))
        conn.commit()
        conn.close()

    def get_order_by_number(self, order_number: str) -> dict | None:
        conn = self._get_connection()
        order = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        conn.close()
        return dict(order) if order else None

    def get_product_stock(self, sku: str) -> int:
        conn = self._get_connection()
        stock = conn.execute("SELECT stock_quantity FROM products WHERE sku = ?", (sku,)).fetchone()[0]
        conn.close()
        return stock

    def purge_user_orders(self, username: str) -> None:
        conn = self._get_connection()
        orders = conn.execute("SELECT order_number FROM orders WHERE customer_username = ?", (username,)).fetchall()
        for o in orders:
            conn.execute("DELETE FROM order_items WHERE order_number = ?", (o["order_number"],))
        conn.execute("DELETE FROM orders WHERE customer_username = ?", (username,))
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
