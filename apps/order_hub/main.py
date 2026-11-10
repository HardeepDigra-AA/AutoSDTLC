"""
Enterprise OrderHub Platform Main Entrypoint.
Includes:
- Multi-tier modular views: Auth, Products, Orders, Warehouse Inventory & Admin.
- Pagination, Category filters, Search parameters.
- Async REST APIs with artificial delay toggles (for testing loading spinners and network interception).
- Custom Web Components (Shadow DOM).
- Dynamic elements & Modals.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import Cookie, FastAPI, Form, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from apps.order_hub.database.connection import get_db, init_db
from apps.order_hub.services.auth_service import (
    create_session,
    delete_session,
    get_session,
    hash_password,
)
from apps.order_hub.services.inventory_service import add_inventory_batch
from apps.order_hub.services.order_service import (
    create_order,
    validate_and_apply_coupon,
)

app = FastAPI(title="OrderHub Enterprise Platform", version="2.0.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

init_db()


def render_page(title: str, content: str, session: dict | None = None) -> str:
    user_nav = ""
    if session:
        user_nav = f"""
            <div style="display:flex; align-items:center; gap:16px;">
                <span style="font-size:13px; color:#94a3b8;">
                    Logged in as: <strong style="color:#f8fafc;" data-testid="nav-username">{session['username']}</strong>
                    <span style="background:rgba(59,130,246,0.2); color:#60a5fa; padding:2px 8px; border-radius:12px; font-size:11px;" data-testid="nav-role">{session['role']}</span>
                </span>
                <a href="/catalog" data-testid="nav-catalog" style="color:#cbd5e1; text-decoration:none; font-size:13px;">Catalog</a>
                <a href="/orders" data-testid="nav-orders" style="color:#cbd5e1; text-decoration:none; font-size:13px;">Orders</a>
                <a href="/inventory" data-testid="nav-inventory" style="color:#cbd5e1; text-decoration:none; font-size:13px;">Warehouse</a>
                <form action="/logout" method="post" style="display:inline;">
                    <button id="btn-logout" data-testid="btn-logout" type="submit" style="background:#334155; color:white; border:none; padding:6px 14px; border-radius:6px; cursor:pointer; font-size:12px;">Sign Out</button>
                </form>
            </div>
        """
    else:
        user_nav = """
            <div>
                <a href="/login" data-testid="nav-login" style="color:#60a5fa; text-decoration:none; margin-right:16px; font-size:13px;">Sign In</a>
                <a href="/signup" data-testid="nav-signup" style="background:#2563eb; color:white; padding:6px 14px; border-radius:6px; text-decoration:none; font-size:13px;">Register</a>
            </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - OrderHub Enterprise</title>
    <script>
        class OrderSummaryWidget extends HTMLElement {{
            constructor() {{
                super();
                this.attachShadow({{ mode: 'open' }});
            }}

            static get observedAttributes() {{
                return ['subtotal', 'discount', 'tax', 'shipping', 'total'];
            }}

            attributeChangedCallback(name, oldValue, newValue) {{
                this.render();
            }}

            connectedCallback() {{
                this.render();
            }}

            render() {{
                const subtotal = parseFloat(this.getAttribute('subtotal') || '0.00').toFixed(2);
                const discount = parseFloat(this.getAttribute('discount') || '0.00').toFixed(2);
                const tax = parseFloat(this.getAttribute('tax') || '0.00').toFixed(2);
                const shipping = parseFloat(this.getAttribute('shipping') || '0.00').toFixed(2);
                const total = parseFloat(this.getAttribute('total') || '0.00').toFixed(2);

                this.shadowRoot.innerHTML = `
                    <style>
                        :host {{
                            display: block;
                            background: #1e293b;
                            border: 1px solid #334155;
                            border-radius: 8px;
                            padding: 16px;
                            color: #f8fafc;
                            font-family: inherit;
                        }}
                        .row {{
                            display: flex;
                            justify-content: space-between;
                            font-size: 13px;
                            margin-bottom: 8px;
                            color: #94a3b8;
                        }}
                        .row.total {{
                            border-top: 1px solid #334155;
                            padding-top: 8px;
                            font-size: 15px;
                            font-weight: 700;
                            color: #38bdf8;
                        }}
                        .discount-val {{ color: #34d399; }}
                    </style>
                    <div>
                        <div class="row"><span>Subtotal:</span><span id="shadow-subtotal">$${{subtotal}}</span></div>
                        <div class="row"><span>Discount:</span><span id="shadow-discount" class="discount-val">-$${{discount}}</span></div>
                        <div class="row"><span>Tax (8%):</span><span id="shadow-tax">$${{tax}}</span></div>
                        <div class="row"><span>Shipping:</span><span id="shadow-shipping">$${{shipping}}</span></div>
                        <div class="row total"><span>Final Total:</span><span id="shadow-total" data-testid="shadow-final-total">$${{total}}</span></div>
                    </div>
                `;
            }}
        }}
        if (!customElements.get('order-summary-widget')) {{
            customElements.define('order-summary-widget', OrderSummaryWidget);
        }}
    </script>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #131b2e;
            --surface-hover: #1c263d;
            --border: #1e293b;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --danger: #ef4444;
            --success: #10b981;
            --warning: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
        }}
        nav {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 14px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .brand {{ font-size: 18px; font-weight: 800; color: #f8fafc; text-decoration: none; }}
        .brand span {{ color: #3b82f6; }}
        .container {{ max-width: 1200px; margin: 32px auto; padding: 0 20px; }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .form-control {{
            width: 100%;
            padding: 10px 14px;
            background: #0b0f19;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: white;
            font-size: 14px;
            margin-bottom: 14px;
            outline: none;
        }}
        .form-control:focus {{ border-color: var(--primary); }}
        .btn {{
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .btn:hover {{ background: var(--primary-hover); }}
        .btn-secondary {{ background: #334155; }}
        .btn-secondary:hover {{ background: #475569; }}
        .btn-danger {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }}
        .btn-danger:hover {{ background: rgba(239, 68, 68, 0.3); }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }}
        .table th {{ color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        .badge {{ padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
        .badge-confirmed {{ background: rgba(59,130,246,0.15); color: #60a5fa; }}
        .badge-delivered {{ background: rgba(16,185,129,0.15); color: #34d399; }}
        .badge-cancelled {{ background: rgba(239,68,68,0.15); color: #f87171; }}
        .badge-stock {{ background: rgba(16,185,129,0.1); color: #34d399; }}
        .badge-lowstock {{ background: rgba(245,158,11,0.15); color: #fbbf24; }}
        .badge-outstock {{ background: rgba(239,68,68,0.15); color: #f87171; }}
        .alert {{ padding: 12px 16px; border-radius: 8px; font-size: 13px; margin-bottom: 20px; }}
        .alert-danger {{ background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #f87171; }}
        .alert-success {{ background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); color: #34d399; }}
        .pagination {{ display: flex; gap: 8px; margin-top: 20px; justify-content: center; }}
        .page-link {{
            padding: 6px 12px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            text-decoration: none;
            font-size: 13px;
        }}
        .page-link.active {{ background: var(--primary); border-color: var(--primary); }}
        /* Async Loading Spinner Modal */
        #loading-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 9999;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            color: white;
            font-size: 14px;
        }}
        .spinner {{
            width: 40px; height: 40px;
            border: 4px solid #334155;
            border-top: 4px solid #3b82f6;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 12px;
        }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div id="loading-overlay" data-testid="loading-spinner">
        <div class="spinner"></div>
        <span id="loading-text">Processing asynchronous transaction...</span>
    </div>

    <nav>
        <a href="/catalog" class="brand">Order<span>Hub</span> Enterprise</a>
        {user_nav}
    </nav>
    <div class="container">
        {content}
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# ROOT & AUTH VIEWS
# ---------------------------------------------------------------------------
@app.get("/")
def root_redirect(session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if session:
        return RedirectResponse(url="/catalog", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_view(error: str | None = None, success: str | None = None):
    err = f'<div id="alert-error" data-testid="alert-error" class="alert alert-danger">{error}</div>' if error else ""
    succ = f'<div id="alert-success" data-testid="alert-success" class="alert alert-success">{success}</div>' if success else ""
    content = f"""
    <div class="card" style="max-width:400px; margin: 40px auto;">
        <h2 style="font-size:22px; margin-bottom:6px;">Sign In to OrderHub</h2>
        <p style="color:#94a3b8; font-size:13px; margin-bottom:20px;">Enterprise E-Commerce Operations Portal</p>
        {err}
        {succ}
        <form id="form-login" action="/login" method="post">
            <input type="text" id="username" data-testid="input-username" name="username" placeholder="Username" class="form-control" required />
            <input type="password" id="password" data-testid="input-password" name="password" placeholder="Password" class="form-control" required />
            <button type="submit" id="btn-login-submit" data-testid="btn-login" class="btn" style="width:100%; justify-content:center;">Sign In</button>
        </form>
        <p style="margin-top:16px; font-size:13px; text-align:center; color:#94a3b8;">
            Need an account? <a href="/signup" id="link-signup" data-testid="link-signup" style="color:#60a5fa;">Register here</a>
        </p>
    </div>
    """
    return render_page("Sign In", content)


@app.post("/login")
def handle_login(response: Response, username: str = Form(...), password: str = Form(...)):
    clean_user = username.strip().lower()
    pw_hash = hash_password(password)

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (clean_user, pw_hash)).fetchone()
    conn.close()

    if not user:
        return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=status.HTTP_303_SEE_OTHER)

    token = create_session(clean_user, user["role"])
    redirect = RedirectResponse(url="/catalog", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(key="session_token", value=token, httponly=True)
    return redirect


@app.get("/signup", response_class=HTMLResponse)
def signup_view(error: str | None = None):
    err = f'<div id="alert-error" data-testid="alert-error" class="alert alert-danger">{error}</div>' if error else ""
    content = f"""
    <div class="card" style="max-width:400px; margin: 40px auto;">
        <h2 style="font-size:22px; margin-bottom:6px;">Create Account</h2>
        <p style="color:#94a3b8; font-size:13px; margin-bottom:20px;">Access the multi-tier enterprise ordering engine</p>
        {err}
        <form id="form-signup" action="/signup" method="post">
            <input type="text" id="username" data-testid="input-username" name="username" placeholder="Choose Username" class="form-control" required />
            <input type="email" id="email" data-testid="input-email" name="email" placeholder="Email Address" class="form-control" required />
            <input type="password" id="password" data-testid="input-password" name="password" placeholder="Password" class="form-control" required />
            <button type="submit" id="btn-signup-submit" data-testid="btn-signup" class="btn" style="width:100%; justify-content:center;">Create Account</button>
        </form>
        <p style="margin-top:16px; font-size:13px; text-align:center; color:#94a3b8;">
            Already registered? <a href="/login" id="link-login" data-testid="link-login" style="color:#60a5fa;">Sign in</a>
        </p>
    </div>
    """
    return render_page("Register", content)


@app.post("/signup")
def handle_signup(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    clean_user = username.strip().lower()
    clean_email = email.strip().lower()

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ? OR email = ?", (clean_user, clean_email)).fetchone()
    if existing:
        conn.close()
        return RedirectResponse(url="/signup?error=Username+or+Email+already+exists", status_code=status.HTTP_303_SEE_OTHER)

    pw_hash = hash_password(password)
    conn.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (clean_user, clean_email, pw_hash))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/login?success=Account+created+successfully!+Please+sign+in.", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def handle_logout(session_token: str | None = Cookie(None)):
    delete_session(session_token)
    res = RedirectResponse(url="/login?success=Signed+out+successfully.", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie(key="session_token")
    return res


# ---------------------------------------------------------------------------
# CATALOG VIEW (With Search, Filtering & Pagination)
# ---------------------------------------------------------------------------
@app.get("/catalog", response_class=HTMLResponse)
def catalog_view(
    category: str | None = None,
    q: str | None = None,
    page: int = 1,
    limit: int = 4,
    session_token: str | None = Cookie(None)
):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db()
    query_str = "SELECT * FROM products WHERE 1=1"
    params = []

    if category and category != "ALL":
        query_str += " AND category = ?"
        params.append(category)

    if q:
        query_str += " AND (name LIKE ? OR sku LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    # Count total for pagination
    count_query = query_str.replace("SELECT *", "SELECT COUNT(*)")
    total_products = conn.execute(count_query, params).fetchone()[0]

    # Limit and offset
    offset = (page - 1) * limit
    query_str += " ORDER BY name ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    products = conn.execute(query_str, params).fetchall()
    categories = [row[0] for row in conn.execute("SELECT DISTINCT category FROM products").fetchall()]
    conn.close()

    # Product cards
    cards_html = ""
    for p in products:
        stock_badge = (
            f'<span class="badge badge-stock" data-testid="stock-badge">In Stock ({p["stock_quantity"]})</span>'
            if p["stock_quantity"] > 5
            else (
                f'<span class="badge badge-lowstock" data-testid="stock-badge">Low Stock ({p["stock_quantity"]})</span>'
                if p["stock_quantity"] > 0
                else '<span class="badge badge-outstock" data-testid="stock-badge">Out of Stock (0)</span>'
            )
        )
        "disabled" if p["stock_quantity"] <= 0 else ""
        button_html = (
            f'<a href="/checkout?sku={p["sku"]}" class="btn" style="width:100%; justify-content:center; text-decoration:none;" data-testid="btn-buy-now">Buy Now →</a>'
            if p["stock_quantity"] > 0
            else '<button class="btn btn-secondary" style="width:100%; justify-content:center; opacity:0.5; cursor:not-allowed;" data-testid="btn-buy-now" disabled>Out of Stock</button>'
        )
        cards_html += f"""
        <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;" data-testid="product-card" data-sku="{p['sku']}">
            <div>
                <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:8px;">
                    <span style="font-size:11px; color:#60a5fa; font-weight:700;" data-testid="product-category">{p['category']}</span>
                    {stock_badge}
                </div>
                <h4 style="font-size:16px; margin-bottom:6px;" data-testid="product-name">{p['name']}</h4>
                <p style="font-size:12px; color:#94a3b8; margin-bottom:12px;">SKU: <code data-testid="product-sku">{p['sku']}</code> | Warehouse Qty: <strong style="color:#f8fafc;" data-testid="stock-count">{p['stock_quantity']}</strong></p>
            </div>
            <div>
                <div style="font-size:18px; font-weight:700; color:#38bdf8; margin-bottom:12px;" data-testid="product-price">${p['price']:.2f}</div>
                {button_html}
            </div>
        </div>
        """

    # Pagination buttons
    total_pages = max(1, (total_products + limit - 1) // limit)
    pagination_html = ""
    for p_num in range(1, total_pages + 1):
        active_cls = "active" if p_num == page else ""
        pagination_html += f'<a href="/catalog?page={p_num}&category={category or ""}&q={q or ""}" class="page-link {active_cls}" data-testid="pagination-page-{p_num}">{p_num}</a>'

    content = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
        <div>
            <h2 style="font-size:24px; margin-bottom:4px;">Enterprise Product Catalog</h2>
            <p style="color:#94a3b8; font-size:13px;">Browse active products with dynamic inventory sync</p>
        </div>
        <form action="/catalog" method="get" style="display:flex; gap:12px;">
            <input type="text" name="q" placeholder="Search SKU or name..." value="{q or ''}" data-testid="search-input" class="form-control" style="margin-bottom:0; width:220px;" />
            <select name="category" data-testid="category-filter" class="form-control" style="margin-bottom:0; width:160px;">
                <option value="ALL">All Categories</option>
                {"".join(f'<option value="{c}" {"selected" if category == c else ""}>{c}</option>' for c in categories)}
            </select>
            <button type="submit" data-testid="btn-search" class="btn">Filter</button>
        </form>
    </div>

    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap:20px;" id="products-grid" data-testid="products-grid">
        {cards_html or '<div style="grid-column: 1/-1; text-align:center; padding:40px; color:#64748b;">No products matched the filter criteria.</div>'}
    </div>

    <div class="pagination" data-testid="pagination-container">
        {pagination_html}
    </div>
    """
    return render_page("Catalog", content, session)


# ---------------------------------------------------------------------------
# CHECKOUT VIEW (Interactive Shadow DOM Widget, Coupons, Dynamic Async Price)
# ---------------------------------------------------------------------------
@app.get("/checkout", response_class=HTMLResponse)
def checkout_view(sku: str, session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url=f"/login?redirect=/checkout?sku={sku}", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    conn.close()

    if not product:
        return RedirectResponse(url="/catalog?error=Product+not+found", status_code=status.HTTP_303_SEE_OTHER)

    content = f"""
    <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:28px;">
        <!-- Left: Order Form -->
        <div class="card">
            <h3 style="font-size:18px; margin-bottom:16px;">Configure Order</h3>
            <div style="padding:14px; background:#0b0f19; border:1px solid #1e293b; border-radius:8px; margin-bottom:20px;">
                <h4 style="font-size:15px;" data-testid="checkout-product-name">{product['name']}</h4>
                <p style="font-size:12px; color:#94a3b8;">SKU: <code data-testid="checkout-sku">{product['sku']}</code> | Unit Price: <strong style="color:#38bdf8;">${product['price']:.2f}</strong></p>
            </div>

            <form id="checkout-form" action="/orders/place" method="post" onsubmit="showLoading()">
                <input type="hidden" name="sku" id="sku" value="{product['sku']}" />

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:6px;">Quantity</label>
                <input type="number" id="quantity" name="quantity" min="1" max="{product['stock_quantity']}" value="1" data-testid="checkout-quantity" class="form-control" onchange="recalculatePrice()" required />

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:6px;">Shipping Option</label>
                <select name="shipping_speed" id="shipping_speed" data-testid="shipping-speed" class="form-control" onchange="recalculatePrice()">
                    <option value="STANDARD">Standard Shipping ($9.99 or FREE over $100)</option>
                    <option value="EXPRESS">Express Priority Carrier ($15.00)</option>
                </select>

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:6px;">Promotional Coupon</label>
                <div style="display:flex; gap:10px; margin-bottom:16px;">
                    <input type="text" id="coupon" name="coupon" placeholder="e.g. SAVE20" data-testid="checkout-coupon-input" class="form-control" style="margin-bottom:0;" />
                    <button type="button" id="btn-apply-coupon" data-testid="btn-apply-coupon" class="btn btn-secondary" onclick="applyCouponAsync()">Apply</button>
                </div>
                <div id="coupon-message" data-testid="coupon-message" style="font-size:12px; margin-bottom:16px;"></div>

                <button type="submit" id="btn-confirm-order" data-testid="btn-confirm-order" class="btn" style="width:100%; justify-content:center;">
                    Authorize Payment & Submit Order
                </button>
            </form>
        </div>

        <!-- Right: Shadow DOM Web Component Encapsulation -->
        <div>
            <h3 style="font-size:18px; margin-bottom:16px;">Live Ledger Preview</h3>
            <order-summary-widget
                id="summary-widget"
                data-testid="order-summary-widget"
                subtotal="{product['price']:.2f}"
                discount="0.00"
                tax="{(product['price'] * 0.08):.2f}"
                shipping="9.99"
                total="{(product['price'] * 1.08 + 9.99):.2f}">
            </order-summary-widget>

            <div style="margin-top:20px; padding:16px; background:#131b2e; border:1px solid #1e293b; border-radius:8px; font-size:12px; color:#94a3b8;">
                <p>🔒 <strong>Architectural Note for Automation:</strong> The summary above is rendered inside an encapsulated <strong>Shadow DOM</strong> (<code style="color:#60a5fa;">order-summary-widget</code>). Playwright automates this cleanly using piercing selectors.</p>
            </div>
        </div>
    </div>

    <script>
        const unitPrice = {product['price']};
        let activeDiscount = 0.0;

        async function applyCouponAsync() {{
            const code = document.getElementById('coupon').value.trim();
            const msgEl = document.getElementById('coupon-message');
            if (!code) return;

            msgEl.innerHTML = '<span style="color:#94a3b8;">Validating coupon via API...</span>';
            const qty = parseInt(document.getElementById('quantity').value) || 1;
            const subtotal = unitPrice * qty;

            try {{
                const resp = await fetch(`/api/v1/coupons/validate?code=${{encodeURIComponent(code)}}&subtotal=${{subtotal}}`);
                const data = await resp.json();
                if (resp.ok) {{
                    activeDiscount = data.discount;
                    msgEl.innerHTML = `<span style="color:#34d399;">✓ Coupon applied! Saved $${{data.discount.toFixed(2)}}</span>`;
                    recalculatePrice();
                }} else {{
                    activeDiscount = 0.0;
                    msgEl.innerHTML = `<span style="color:#f87171;">✕ ${{data.detail || 'Invalid coupon'}}</span>`;
                    recalculatePrice();
                }}
            }} catch(err) {{
                msgEl.innerHTML = `<span style="color:#f87171;">Server error validating coupon.</span>`;
            }}
        }}

        function recalculatePrice() {{
            const qty = parseInt(document.getElementById('quantity').value) || 1;
            const shippingType = document.getElementById('shipping_speed').value;
            const subtotal = unitPrice * qty;
            const tax = (subtotal - activeDiscount) * 0.08;
            let shipping = 9.99;
            if (shippingType === 'EXPRESS') shipping = 15.00;
            else if ((subtotal - activeDiscount) > 100.0) shipping = 0.00;

            const total = subtotal - activeDiscount + tax + shipping;

            const widget = document.getElementById('summary-widget');
            widget.setAttribute('subtotal', subtotal.toFixed(2));
            widget.setAttribute('discount', activeDiscount.toFixed(2));
            widget.setAttribute('tax', tax.toFixed(2));
            widget.setAttribute('shipping', shipping.toFixed(2));
            widget.setAttribute('total', total.toFixed(2));
        }}

        function showLoading() {{
            document.getElementById('loading-overlay').style.display = 'flex';
        }}
    </script>
    """
    return render_page("Checkout", content, session)


@app.post("/orders/place")
async def place_order_route(
    sku: str = Form(...),
    quantity: int = Form(...),
    shipping_speed: str = Form("STANDARD"),
    coupon: str | None = Form(None),
    session_token: str | None = Cookie(None)
):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Simulate realistic database transaction latency for E2E tests
    await asyncio.sleep(0.4)

    try:
        order = create_order(
            customer_username=session["username"],
            sku=sku,
            quantity=quantity,
            coupon_code=coupon,
            shipping_speed=shipping_speed
        )
        return RedirectResponse(url=f"/orders?success=Order+{order['order_number']}+confirmed!", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url=f"/checkout?sku={sku}&error={str(e)}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# ORDERS HISTORY VIEW
# ---------------------------------------------------------------------------
@app.get("/orders", response_class=HTMLResponse)
def orders_view(success: str | None = None, session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    succ = f'<div id="alert-success" data-testid="alert-success" class="alert alert-success">{success}</div>' if success else ""

    conn = get_db()
    orders = conn.execute("""
    SELECT o.*, p.name as product_name, oi.quantity, oi.unit_price
    FROM orders o
    JOIN order_items oi ON o.order_number = oi.order_number
    JOIN products p ON oi.product_sku = p.sku
    WHERE o.customer_username = ?
    ORDER BY o.created_at DESC
    """, (session["username"],)).fetchall()
    conn.close()

    rows = ""
    for o in orders:
        badge_cls = (
            "badge-delivered" if o["status"] == "DELIVERED"
            else ("badge-cancelled" if o["status"] == "CANCELLED" else "badge-confirmed")
        )
        rows += f"""
        <tr data-testid="order-row" data-order-number="{o['order_number']}">
            <td><code data-testid="order-number">{o['order_number']}</code></td>
            <td data-testid="order-product-name">{o['product_name']} (x{o['quantity']})</td>
            <td data-testid="order-total">${o['total_amount']:.2f}</td>
            <td><span class="badge {badge_cls}" data-testid="order-status">{o['status']}</span></td>
            <td><code data-testid="order-tracking">{o['shipping_tracking_number']}</code></td>
            <td>{o['created_at']}</td>
        </tr>
        """

    content = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h2>My Order History</h2>
        <a href="/catalog" class="btn">Continue Shopping</a>
    </div>
    {succ}
    <div class="card">
        <table class="table" id="orders-table" data-testid="orders-table">
            <thead>
                <tr>
                    <th>Order #</th>
                    <th>Product Item</th>
                    <th>Total Charged</th>
                    <th>Fulfillment Status</th>
                    <th>Tracking #</th>
                    <th>Date Placed</th>
                </tr>
            </thead>
            <tbody>
                {rows or '<tr><td colspan="6" style="text-align:center; padding:32px; color:#64748b;">No orders placed yet.</td></tr>'}
            </tbody>
        </table>
    </div>
    """
    return render_page("Orders", content, session)


# ---------------------------------------------------------------------------
# WAREHOUSE INVENTORY MANAGEMENT VIEW (Cross-Module Dependency)
# ---------------------------------------------------------------------------
@app.get("/inventory", response_class=HTMLResponse)
def inventory_view(success: str | None = None, session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    succ = f'<div id="alert-success" data-testid="alert-success" class="alert alert-success">{success}</div>' if success else ""

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY sku ASC").fetchall()
    batches = conn.execute("""
    SELECT b.*, p.name as product_name
    FROM inventory_batches b
    JOIN products p ON b.sku = p.sku
    ORDER BY b.created_at DESC
    """).fetchall()
    conn.close()

    product_options = "".join(f'<option value="{p["sku"]}">{p["sku"]} - {p["name"]} (Current: {p["stock_quantity"]})</option>' for p in products)

    batch_rows = ""
    for b in batches:
        batch_rows += f"""
        <tr data-testid="batch-row" data-batch="{b['batch_number']}">
            <td><code data-testid="batch-code">{b['batch_number']}</code></td>
            <td>{b['sku']} - {b['product_name']}</td>
            <td><strong style="color:#34d399;" data-testid="batch-added-qty">+{b['received_quantity']}</strong></td>
            <td>{b['available_quantity']}</td>
            <td>{b['created_at']}</td>
        </tr>
        """

    content = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <div>
            <h2>Warehouse Inventory Hub</h2>
            <p style="color:#94a3b8; font-size:13px;">Manage physical stock batches, intake replenishment, and view live inventory audits</p>
        </div>
        <a href="/catalog" class="btn btn-secondary">← View Storefront Catalog</a>
    </div>
    {succ}
    <div style="display:grid; grid-template-columns: 1fr 2fr; gap:24px;">
        <div class="card">
            <h3 style="font-size:16px; margin-bottom:16px;">Receive Inventory Batch</h3>
            <form action="/inventory/receive" method="post">
                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Select SKU to Replenish</label>
                <select name="sku" data-testid="select-batch-sku" class="form-control" required>
                    {product_options}
                </select>

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Shipment Batch Number</label>
                <input type="text" name="batch_number" placeholder="BATCH-2026-X" data-testid="input-batch-number" class="form-control" required />

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Received Quantity (Units)</label>
                <input type="number" name="quantity" min="1" max="1000" value="50" data-testid="input-batch-qty" class="form-control" required />

                <button type="submit" data-testid="btn-receive-batch" class="btn" style="width:100%; justify-content:center;">Intake Batch to Stock</button>
            </form>
        </div>

        <div class="card">
            <h3 style="font-size:16px; margin-bottom:16px;">Warehouse Intake Audit Log</h3>
            <table class="table" data-testid="batches-table">
                <thead>
                    <tr>
                        <th>Batch Code</th>
                        <th>Target Product</th>
                        <th>Added Qty</th>
                        <th>Available</th>
                        <th>Received Date</th>
                    </tr>
                </thead>
                <tbody>
                    {batch_rows or '<tr><td colspan="5" style="text-align:center; padding:24px; color:#64748b;">No batches recorded.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_page("Warehouse", content, session)


@app.post("/inventory/receive")
def receive_inventory_route(sku: str = Form(...), batch_number: str = Form(...), quantity: int = Form(...)):
    res = add_inventory_batch(sku, batch_number, quantity)
    return RedirectResponse(
        url=f"/inventory?success=Successfully+intaked+{quantity}+units+for+{sku}!+Total+stock+now:+{res['new_total_stock']}",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ---------------------------------------------------------------------------
# ASYNC REST APIS (For Network Interception, Mocking & Contract Testing)
# ---------------------------------------------------------------------------
@app.get("/api/v1/coupons/validate")
def api_validate_coupon(code: str, subtotal: float):
    try:
        discount, coupon_code = validate_and_apply_coupon(code, subtotal)
        return {"valid": True, "code": coupon_code, "discount": discount}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
