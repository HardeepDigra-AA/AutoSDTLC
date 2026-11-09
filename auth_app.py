"""
Production-ready Authentication and Session Management App.
Stack: Pure Python 3 (FastAPI, SQLite, Jinja2/HTML, hashlib).
Features:
- Registration with SHA-256 password hashing and SQLite persistence.
- Secure Login verifying credentials against the SQLite database.
- Session cookie issuance and protected dashboard.
- Logout and session invalidation.
- Error banners for invalid credentials or duplicate usernames.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from pathlib import Path

from fastapi import Cookie, FastAPI, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="Secure Auth App", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "auth_app.db"

# Active server sessions in memory: session_token -> username
ACTIVE_SESSIONS: dict[str, str] = {}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# UI TEMPLATES
# ---------------------------------------------------------------------------
HTML_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - AuthApp</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --border: #334155;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --error: #ef4444;
            --success: #10b981;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            min-height: 100vh;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 32px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }}
        h2 {{ margin-bottom: 8px; font-size: 24px; font-weight: 700; }}
        p.subtitle {{ color: var(--text-muted); font-size: 14px; margin-bottom: 24px; }}
        .form-group {{ margin-bottom: 18px; }}
        label {{ display: block; font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }}
        input {{
            width: 100%;
            padding: 10px 14px;
            background: #0f172a;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }}
        input:focus {{ border-color: var(--primary); }}
        .btn {{
            width: 100%;
            padding: 11px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .btn:hover {{ background: var(--primary-hover); }}
        .btn-secondary {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text);
            margin-top: 10px;
        }}
        .btn-secondary:hover {{ background: var(--border); }}
        .banner {{
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .banner-error {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; }}
        .banner-success {{ background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; }}
        .footer-link {{ margin-top: 20px; text-align: center; font-size: 13px; color: var(--text-muted); }}
        .footer-link a {{ color: var(--primary); text-decoration: none; font-weight: 600; }}
        .footer-link a:hover {{ text-decoration: underline; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
        }}
    </style>
</head>
<body>
    <div class="card">
        {content}
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index(session_id: str | None = Cookie(None)):
    if session_id and session_id in ACTIVE_SESSIONS:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# SIGN UP
# ---------------------------------------------------------------------------
@app.get("/signup", response_class=HTMLResponse)
def signup_page(error: str | None = None):
    err_banner = f'<div id="error-banner" class="banner banner-error">{error}</div>' if error else ""
    content = f"""
        <span class="badge">Registration</span>
        <h2>Create Account</h2>
        <p class="subtitle">Enter your details to register in SQLite database.</p>
        {err_banner}
        <form id="signup-form" action="/signup" method="post">
            <div class="form-group">
                <label for="full_name">Full Name</label>
                <input id="full_name" name="full_name" type="text" placeholder="John Doe" required />
            </div>
            <div class="form-group">
                <label for="username">Username</label>
                <input id="username" name="username" type="text" placeholder="johndoe" required />
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input id="password" name="password" type="password" placeholder="••••••••" required />
            </div>
            <button id="btn-submit-signup" type="submit" class="btn">Sign Up</button>
        </form>
        <div class="footer-link">
            Already have an account? <a id="link-login" href="/login">Log in here</a>
        </div>
    """
    return HTML_SHELL.format(title="Sign Up", content=content)


@app.post("/signup")
def handle_signup(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    clean_username = username.strip().lower()
    clean_name = full_name.strip()

    if not clean_username or not password:
        return RedirectResponse(url="/signup?error=Username+and+password+are+required", status_code=status.HTTP_303_SEE_OTHER)

    conn = get_db_connection()
    user_exists = conn.execute("SELECT id FROM users WHERE username = ?", (clean_username,)).fetchone()
    if user_exists:
        conn.close()
        return RedirectResponse(url="/signup?error=Username+already+taken.+Please+choose+another.", status_code=status.HTTP_303_SEE_OTHER)

    hashed_pw = hash_password(password)
    conn.execute(
        "INSERT INTO users (username, password_hash, full_name) VALUES (?, ?, ?)",
        (clean_username, hashed_pw, clean_name)
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/login?success=Account+created+successfully!+Please+log+in.", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page(error: str | None = None, success: str | None = None):
    err_banner = f'<div id="error-banner" class="banner banner-error">{error}</div>' if error else ""
    success_banner = f'<div id="success-banner" class="banner banner-success">{success}</div>' if success else ""
    content = f"""
        <span class="badge">Security Gate</span>
        <h2>Welcome Back</h2>
        <p class="subtitle">Sign in to access your secure dashboard.</p>
        {err_banner}
        {success_banner}
        <form id="login-form" action="/login" method="post">
            <div class="form-group">
                <label for="username">Username</label>
                <input id="username" name="username" type="text" placeholder="Enter username" required />
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input id="password" name="password" type="password" placeholder="••••••••" required />
            </div>
            <button id="btn-submit-login" type="submit" class="btn">Log In</button>
        </form>
        <div class="footer-link">
            Don't have an account? <a id="link-signup" href="/signup">Sign up here</a>
        </div>
    """
    return HTML_SHELL.format(title="Log In", content=content)


@app.post("/login")
def handle_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    clean_username = username.strip().lower()
    hashed_pw = hash_password(password)

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (clean_username, hashed_pw)
    ).fetchone()
    conn.close()

    if not user:
        return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=status.HTTP_303_SEE_OTHER)

    # Generate secure session token
    token = secrets.token_hex(24)
    ACTIVE_SESSIONS[token] = clean_username

    redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(key="session_id", value=token, httponly=True, max_age=3600)
    return redirect


# ---------------------------------------------------------------------------
# DASHBOARD (PROTECTED)
# ---------------------------------------------------------------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(session_id: str | None = Cookie(None)):
    if not session_id or session_id not in ACTIVE_SESSIONS:
        return RedirectResponse(url="/login?error=Authentication+required.+Please+log+in.", status_code=status.HTTP_303_SEE_OTHER)

    username = ACTIVE_SESSIONS[session_id]
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    full_name = user["full_name"] if user else username
    created_at = user["created_at"] if user else "Unknown"

    content = f"""
        <span class="badge" style="background:rgba(16,185,129,0.15); color:#34d399;">Authenticated</span>
        <h2>Hello, <span id="user-display-name">{full_name}</span>!</h2>
        <p class="subtitle">You have successfully authenticated via SQLite credential verification.</p>
        
        <div style="background:#0f172a; border:1px solid #334155; border-radius:8px; padding:16px; margin-bottom:20px; font-size:13px;">
            <p style="margin-bottom:8px;"><strong>Username:</strong> <code id="user-username">{username}</code></p>
            <p style="margin-bottom:8px;"><strong>Account Created:</strong> <code>{created_at}</code></p>
            <p><strong>Session Token:</strong> <code>{session_id[:12]}...</code></p>
        </div>

        <form action="/logout" method="post">
            <button id="btn-logout" type="submit" class="btn btn-secondary">Log Out</button>
        </form>
    """
    return HTML_SHELL.format(title="Dashboard", content=content)


@app.post("/logout")
def handle_logout(session_id: str | None = Cookie(None)):
    if session_id and session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    redirect = RedirectResponse(url="/login?success=Logged+out+successfully.", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(key="session_id")
    return redirect


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
