"""
Enterprise Test Data Management & Factories.
Includes Dynamic Synthesizers, Database Seeders, and Cleanup Hooks.
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


@dataclass
class ProductData:
    sku: str
    name: str
    category: str
    price: float
    stock_quantity: int


class TestDataFactory:
    """Generates synthetic, deterministic, or randomized test entities."""

    @staticmethod
    def create_user_payload(prefix: str = "qa_user") -> UserData:
        unique_suffix = f"{int(time.time() * 1000) % 100000}_{random.randint(100, 999)}"
        username = f"{prefix}_{unique_suffix}"
        email = f"{username}@example.com"
        password = "SecurePassword@2026!"
        return UserData(username=username, email=email, password=password)

    @staticmethod
    def create_product_payload(prefix: str = "PROD") -> ProductData:
        rand_id = random.randint(1000, 9999)
        sku = f"{prefix}-{rand_id}"
        return ProductData(
            sku=sku,
            name=f"Enterprise Widget {rand_id}",
            category="Hardware",
            price=round(random.uniform(29.99, 499.99), 2),
            stock_quantity=random.randint(10, 100)
        )


class DatabaseTestSeeder:
    """Manages pre-test fixtures, baseline dataset seeds, and post-test teardowns."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def seed_baseline_catalog(self) -> list[ProductData]:
        catalog = [
            ProductData("SKU-LAPTOP-01", "MacBook Pro 16 M3", "Electronics", 2499.00, 15),
            ProductData("SKU-MOUSE-02", "Logitech MX Master 3S", "Accessories", 99.99, 50),
            ProductData("SKU-KEYBOARD-03", "Keychron Q1 Pro Mechanical", "Accessories", 199.50, 25),
            ProductData("SKU-MONITOR-04", "Dell UltraSharp 32 4K", "Displays", 789.00, 10),
            ProductData("SKU-LOWSTOCK-05", "Rare Vintage Terminal Display", "Vintage", 450.00, 1),
        ]
        conn = self._get_connection()
        cursor = conn.cursor()
        for p in catalog:
            cursor.execute("""
            INSERT OR REPLACE INTO products (sku, name, category, price, stock_quantity)
            VALUES (?, ?, ?, ?, ?)
            """, (p.sku, p.name, p.category, p.price, p.stock_quantity))
        conn.commit()
        conn.close()
        return catalog

    def seed_test_user(self, user: UserData) -> None:
        conn = self._get_connection()
        pw_hash = hashlib.sha256(user.password.encode("utf-8")).hexdigest()
        conn.execute("""
        INSERT OR REPLACE INTO users (username, email, password_hash, role)
        VALUES (?, ?, ?, ?)
        """, (user.username, user.email, pw_hash, user.role))
        conn.commit()
        conn.close()

    def get_order_by_number(self, order_number: str) -> dict | None:
        conn = self._get_connection()
        order = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
        conn.close()
        return dict(order) if order else None

    def purge_user_orders(self, username: str) -> None:
        conn = self._get_connection()
        conn.execute("DELETE FROM orders WHERE customer_username = ?", (username,))
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
