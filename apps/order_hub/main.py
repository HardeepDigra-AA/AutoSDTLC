"""
OrderHub Application Entrypoint.
Production-ready FastAPI app serving HTML web interface and JSON REST APIs.
"""
from __future__ import annotations

from fastapi import Cookie, FastAPI, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from apps.order_hub.database.connection import get_db, init_db
from apps.order_hub.services.auth_service import (
    create_session,
    delete_session,
    get_session,
    hash_password,
)
from apps.order_hub.services.order_service import create_order

app = FastAPI(title="OrderHub Platform", version="1.0.0")

# Ensure database is bootstrapped
init_db()


def render_html_page(title: str, content: str, session: dict | None = None) -> str:
    user_nav = ""
    if session:
        user_nav = f"""
            <div style="display:flex; align-items:center; gap:16px;">
                <span style="font-size:13px; color:#94a3b8;">Logged in as: <strong style="color:#f8fafc;" data-testid="nav-user">{session['username']}</strong> <span style="background:rgba(59,130,246,0.2); color:#60a5fa; padding:2px 8px; border-radius:12px; font-size:11px;">{session['role']}</span></span>
                <form action="/logout" method="post" style="display:inline;">
                    <button id="btn-logout" data-testid="btn-logout" type="submit" style="background:#334155; color:white; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; font-size:12px;">Sign Out</button>
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
    <title>{title} - OrderHub</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #131b2e;
            --border: #1e293b;
            --primary: #2563eb;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --danger: #ef4444;
            --success: #10b981;
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
        .container {{ max-width: 1100px; margin: 40px auto; padding: 0 20px; }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 28px;
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
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
        }}
        .btn:hover {{ background: #1d4ed8; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }}
        .table th {{ color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        .badge {{ padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
        .badge-placed {{ background: rgba(59,130,246,0.15); color: #60a5fa; }}
        .badge-delivered {{ background: rgba(16,185,129,0.15); color: #34d399; }}
        .alert {{ padding: 12px; border-radius: 8px; font-size: 13px; margin-bottom: 18px; }}
        .alert-danger {{ background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3); color: #f87171; }}
        .alert-success {{ background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); color: #34d399; }}
    </style>
</head>
<body>
    <nav>
        <a href="/" class="brand">Order<span>Hub</span> Enterprise</a>
        {user_nav}
    </nav>
    <div class="container">
        {content}
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# WEB ROUTES
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home_view(session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY name ASC").fetchall()
    orders = conn.execute(
        "SELECT * FROM orders WHERE customer_username = ? ORDER BY created_at DESC",
        (session["username"],)
    ).fetchall()
    conn.close()

    product_options = "".join(
        f'<option value="{p["sku"]}">{p["name"]} - ${p["price"]:.2f} (Stock: {p["stock_quantity"]})</option>'
        for p in products
    )

    order_rows = ""
    for o in orders:
        badge_cls = "badge-delivered" if o["status"] == "DELIVERED" else "badge-placed"
        order_rows += f"""
        <tr data-testid="order-row" data-order-number="{o['order_number']}">
            <td><code data-testid="order-number">{o['order_number']}</code></td>
            <td>${o['total_amount']:.2f}</td>
            <td>${o['discount_amount']:.2f}</td>
            <td><span class="badge {badge_cls}" data-testid="order-status">{o['status']}</span></td>
            <td>{o['created_at']}</td>
        </tr>
        """
    if not order_rows:
        order_rows = "<tr><td colspan='5' style='text-align:center; color:#64748b; padding:24px;'>No orders placed yet.</td></tr>"

    content = f"""
    <div style="display:grid; grid-template-columns: 1fr 2fr; gap:24px;">
        <!-- Left: Place Order Form -->
        <div class="card">
            <h3 style="font-size:16px; margin-bottom:16px;">Create New Order</h3>
            <form id="form-order" action="/orders/place" method="post">
                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Select Product</label>
                <select name="sku" id="select-product" data-testid="select-product" class="form-control" required>
                    {product_options}
                </select>

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Quantity</label>
                <input type="number" id="input-qty" data-testid="input-quantity" name="quantity" min="1" max="100" value="1" class="form-control" required />

                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:4px;">Promotional Coupon</label>
                <input type="text" id="input-coupon" data-testid="input-coupon" name="coupon" placeholder="e.g. SAVE20" class="form-control" />

                <button type="submit" id="btn-submit-order" data-testid="btn-submit-order" class="btn" style="width:100%;">Confirm & Place Order</button>
            </form>
        </div>

        <!-- Right: Order History -->
        <div class="card">
            <h3 style="font-size:16px; margin-bottom:16px;">My Order History</h3>
            <table class="table" id="orders-table" data-testid="orders-table">
                <thead>
                    <tr>
                        <th>Order #</th>
                        <th>Total</th>
                        <th>Discount</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {order_rows}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_html_page("Dashboard", content, session)


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
            <button type="submit" id="btn-login-submit" data-testid="btn-login" class="btn" style="width:100%;">Sign In</button>
        </form>
        <p style="margin-top:16px; font-size:13px; text-align:center; color:#94a3b8;">
            Need an account? <a href="/signup" id="link-signup" data-testid="link-signup" style="color:#60a5fa;">Register here</a>
        </p>
    </div>
    """
    return render_html_page("Login", content)


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
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(key="session_token", value=token, httponly=True)
    return redirect


@app.get("/signup", response_class=HTMLResponse)
def signup_view(error: str | None = None):
    err = f'<div id="alert-error" data-testid="alert-error" class="alert alert-danger">{error}</div>' if error else ""
    content = f"""
    <div class="card" style="max-width:400px; margin: 40px auto;">
        <h2 style="font-size:22px; margin-bottom:6px;">Create Account</h2>
        <p style="color:#94a3b8; font-size:13px; margin-bottom:20px;">Access the multi-tier order platform</p>
        {err}
        <form id="form-signup" action="/signup" method="post">
            <input type="text" id="username" data-testid="input-username" name="username" placeholder="Choose Username" class="form-control" required />
            <input type="email" id="email" data-testid="input-email" name="email" placeholder="Email Address" class="form-control" required />
            <input type="password" id="password" data-testid="input-password" name="password" placeholder="Password" class="form-control" required />
            <button type="submit" id="btn-signup-submit" data-testid="btn-signup" class="btn" style="width:100%;">Create Account</button>
        </form>
        <p style="margin-top:16px; font-size:13px; text-align:center; color:#94a3b8;">
            Already registered? <a href="/login" id="link-login" data-testid="link-login" style="color:#60a5fa;">Sign in</a>
        </p>
    </div>
    """
    return render_html_page("Register", content)


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


@app.post("/orders/place")
def handle_place_order(sku: str = Form(...), quantity: int = Form(...), coupon: str | None = Form(None), session_token: str | None = Cookie(None)):
    session = get_session(session_token)
    if not session:
        return RedirectResponse(url="/login?error=Please+log+in+to+place+orders", status_code=status.HTTP_303_SEE_OTHER)

    try:
        create_order(session["username"], sku, quantity, coupon)
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url=f"/?error={str(e)}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def handle_logout(session_token: str | None = Cookie(None)):
    delete_session(session_token)
    res = RedirectResponse(url="/login?success=Signed+out+successfully.", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie(key="session_token")
    return res


# ---------------------------------------------------------------------------
# API ENDPOINTS (For API testing, Seeds, and Healthchecks)
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
def api_health():
    return {"status": "ok", "service": "order_hub", "version": "1.0.0"}


@app.get("/api/v1/products")
def api_get_products():
    conn = get_db()
    products = [dict(p) for p in conn.execute("SELECT * FROM products").fetchall()]
    conn.close()
    return {"products": products}


@app.post("/api/v1/admin/seed-product")
def api_seed_product(sku: str, name: str, category: str, price: float, stock_quantity: int):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO products (sku, name, category, price, stock_quantity) VALUES (?, ?, ?, ?, ?)",
        (sku, name, category, price, stock_quantity)
    )
    conn.commit()
    conn.close()
    return {"status": "created", "sku": sku}
