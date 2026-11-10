from apps.order_hub.database.connection import get_db


def add_inventory_batch(sku: str, batch_number: str, quantity: int, expiry_date: str | None = None) -> dict:
    conn = get_db()
    cursor = conn.cursor()

    product = cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise ValueError(f"SKU '{sku}' does not exist in product catalog.")

    cursor.execute("""
    INSERT INTO inventory_batches (sku, batch_number, received_quantity, available_quantity, expiry_date)
    VALUES (?, ?, ?, ?, ?)
    """, (sku, batch_number, quantity, quantity, expiry_date))

    # Dependency ripple: Update total stock in products table
    new_stock = product["stock_quantity"] + quantity
    cursor.execute("UPDATE products SET stock_quantity = ? WHERE sku = ?", (new_stock, sku))

    cursor.execute("""
    INSERT INTO audit_logs (action, actor, entity_type, entity_id, details)
    VALUES ('BATCH_RECEIVED', 'WAREHOUSE_ADMIN', 'INVENTORY', ?, ?)
    """, (batch_number, f"Added {quantity} units to SKU {sku}. Total stock: {new_stock}"))

    conn.commit()
    conn.close()
    return {"batch_number": batch_number, "sku": sku, "new_total_stock": new_stock}


def check_stock_availability(sku: str, required_qty: int) -> tuple[bool, int]:
    conn = get_db()
    product = conn.execute("SELECT stock_quantity, reserved_quantity FROM products WHERE sku = ?", (sku,)).fetchone()
    conn.close()
    if not product:
        return False, 0
    available = product["stock_quantity"] - product["reserved_quantity"]
    return (available >= required_qty), available
