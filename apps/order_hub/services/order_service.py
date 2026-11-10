import random
import uuid

from apps.order_hub.database.connection import get_db


def validate_and_apply_coupon(code: str, subtotal: float) -> tuple[float, str | None]:
    if not code:
        return 0.0, None

    clean_code = code.strip().upper()
    conn = get_db()
    coupon = conn.execute("SELECT * FROM coupons WHERE code = ? AND is_active = 1", (clean_code,)).fetchone()

    if not coupon:
        conn.close()
        raise ValueError(f"Coupon code '{clean_code}' is invalid or expired.")

    if subtotal < coupon["min_order_amount"]:
        conn.close()
        raise ValueError(f"Minimum order of ${coupon['min_order_amount']:.2f} required for coupon '{clean_code}'.")

    if coupon["used_count"] >= coupon["max_uses"]:
        conn.close()
        raise ValueError(f"Coupon '{clean_code}' usage limit has been reached.")

    if coupon["discount_type"] == "PERCENTAGE":
        discount = round(subtotal * (coupon["discount_value"] / 100.0), 2)
    else:
        discount = min(coupon["discount_value"], subtotal)

    conn.close()
    return discount, clean_code


def create_order(
    customer_username: str,
    sku: str,
    quantity: int,
    coupon_code: str | None = None,
    shipping_speed: str = "STANDARD"
) -> dict:
    conn = get_db()
    cursor = conn.cursor()

    # 1. Fetch User & verify active status
    user = cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (customer_username,)).fetchone()
    if not user:
        conn.close()
        raise ValueError(f"Customer '{customer_username}' is not active or not found.")

    # 2. Fetch Product & check stock availability
    product = cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    if not product:
        conn.close()
        raise ValueError(f"Product SKU '{sku}' not found in catalog.")

    available_stock = product["stock_quantity"] - product["reserved_quantity"]
    if available_stock < quantity:
        conn.close()
        raise ValueError(
            f"Insufficient available stock for '{product['name']}'. Requested: {quantity}, Available: {available_stock}."
        )

    # 3. Financial calculations
    unit_price = product["price"]
    subtotal = round(unit_price * quantity, 2)
    discount, applied_coupon = validate_and_apply_coupon(coupon_code, subtotal)
    
    # Tier loyalty bonus discount
    tier_discount = 0.0
    if user["loyalty_tier"] == "GOLD":
        tier_discount = round(subtotal * 0.05, 2)
    elif user["loyalty_tier"] == "PLATINUM":
        tier_discount = round(subtotal * 0.10, 2)
    discount = round(discount + tier_discount, 2)

    # Tax & Shipping
    tax_amount = round((subtotal - discount) * 0.08, 2)
    shipping_amount = 15.0 if shipping_speed == "EXPRESS" else (0.0 if (subtotal - discount) > 100.0 else 9.99)
    total_amount = round(subtotal - discount + tax_amount + shipping_amount, 2)

    order_num = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    tracking_no = f"TRK-{random.randint(100000, 999999)}"

    # 4. Atomic Transaction: Insert Order & Items, Deduct Stock, Record Audit
    cursor.execute("""
    INSERT INTO orders (
        order_number, customer_username, subtotal, discount_amount, tax_amount,
        shipping_amount, total_amount, coupon_applied, status, payment_reference, shipping_tracking_number
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?)
    """, (
        order_num, customer_username, subtotal, discount, tax_amount,
        shipping_amount, total_amount, applied_coupon, f"PAY-{uuid.uuid4().hex[:6].upper()}", tracking_no
    ))

    cursor.execute("""
    INSERT INTO order_items (order_number, product_sku, quantity, unit_price, subtotal)
    VALUES (?, ?, ?, ?, ?)
    """, (order_num, sku, quantity, unit_price, subtotal))

    # Deduct stock directly from product
    new_stock = product["stock_quantity"] - quantity
    cursor.execute("UPDATE products SET stock_quantity = ? WHERE sku = ?", (new_stock, sku))

    # Increment coupon usage count if used
    if applied_coupon:
        cursor.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code = ?", (applied_coupon,))

    # Log audit event
    cursor.execute("""
    INSERT INTO audit_logs (action, actor, entity_type, entity_id, details)
    VALUES ('ORDER_PLACED', ?, 'ORDER', ?, ?)
    """, (customer_username, order_num, f"Total: ${total_amount}, SKU: {sku} x{quantity}"))

    conn.commit()
    conn.close()

    return {
        "order_number": order_num,
        "subtotal": subtotal,
        "discount_amount": discount,
        "tax_amount": tax_amount,
        "shipping_amount": shipping_amount,
        "total_amount": total_amount,
        "tracking_number": tracking_no,
        "status": "CONFIRMED"
    }


def update_order_fulfillment(order_number: str, new_status: str, actor: str) -> dict:
    valid_statuses = {"CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

    conn = get_db()
    cursor = conn.cursor()

    order = cursor.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,)).fetchone()
    if not order:
        conn.close()
        raise ValueError(f"Order '{order_number}' not found.")

    # Restock inventory on cancellation
    if new_status == "CANCELLED" and order["status"] != "CANCELLED":
        items = cursor.execute("SELECT product_sku, quantity FROM order_items WHERE order_number = ?", (order_number,)).fetchall()
        for it in items:
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE sku = ?", (it["quantity"], it["product_sku"]))

    cursor.execute("UPDATE orders SET status = ? WHERE order_number = ?", (new_status, order_number))
    cursor.execute("""
    INSERT INTO audit_logs (action, actor, entity_type, entity_id, details)
    VALUES ('STATUS_UPDATED', ?, 'ORDER', ?, ?)
    """, (actor, order_number, f"Status updated from {order['status']} to {new_status}"))

    conn.commit()
    conn.close()
    return {"order_number": order_number, "previous_status": order["status"], "new_status": new_status}
