import random

from apps.order_hub.database.connection import get_db


def create_order(customer_username: str, sku: str, quantity: int, coupon_code: str | None = None) -> dict:
    conn = get_db()
    cursor = conn.cursor()

    product = cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise ValueError(f"Product SKU '{sku}' not found.")

    if product["stock_quantity"] < quantity:
        conn.close()
        raise ValueError(f"Insufficient stock for '{product['name']}'. Requested: {quantity}, Available: {product['stock_quantity']}.")

    unit_price = product["price"]
    subtotal = unit_price * quantity
    discount = 0.0

    if coupon_code and coupon_code.strip().upper() == "SAVE20":
        discount = round(subtotal * 0.20, 2)

    total_amount = round(subtotal - discount, 2)
    order_num = f"ORD-{random.randint(10000, 99999)}"

    # Atomic transaction
    cursor.execute(
        "INSERT INTO orders (order_number, customer_username, total_amount, discount_amount, status) VALUES (?, ?, ?, ?, 'PLACED')",
        (order_num, customer_username, total_amount, discount)
    )

    cursor.execute(
        "INSERT INTO order_items (order_number, product_sku, quantity, unit_price) VALUES (?, ?, ?, ?)",
        (order_num, sku, quantity, unit_price)
    )

    # Deduct stock
    new_stock = product["stock_quantity"] - quantity
    cursor.execute("UPDATE products SET stock_quantity = ? WHERE sku = ?", (new_stock, sku))

    # Audit log
    cursor.execute(
        "INSERT INTO audit_logs (action, actor, details) VALUES ('ORDER_PLACED', ?, ?)",
        (customer_username, f"Order {order_num} for SKU {sku} x{quantity}")
    )

    conn.commit()
    conn.close()

    return {
        "order_number": order_num,
        "total_amount": total_amount,
        "discount_amount": discount,
        "status": "PLACED"
    }


def update_order_status(order_number: str, new_status: str, actor: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_number = ?", (new_status, order_number))
    cursor.execute("INSERT INTO audit_logs (action, actor, details) VALUES ('STATUS_CHANGED', ?, ?)",
                   (actor, f"Order {order_number} changed to {new_status}"))
    conn.commit()
    rows = cursor.rowcount
    conn.close()
    return rows > 0
