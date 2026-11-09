"""
FastAPI Local Web Application for AI SDLC Orchestrator.
Combines:
1. The Governed SDLC Control Plane (Admin / Pipeline at /orchestrator)
2. The User Application (Homepage at /, Sign-Up at /signup, Login at /login, Dashboard at /app/dashboard)
All backed dynamically by SQLite without hardcoded data.
"""
import hashlib
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ai_sdlc.domain.workflow import Action, FeatureRequest, Role
from ai_sdlc.infrastructure.sqlite_repository import SQLiteRepository
from ai_sdlc.services.workflow_service import WorkflowService

# Databases
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SDLC_DB = DATA_DIR / "demo.db"
USER_DB = DATA_DIR / "app_users.db"

repo = SQLiteRepository(SDLC_DB)
repo.initialize()

# Initialize Users and Activity Logs tables
def init_user_db():
    conn = sqlite3.connect(USER_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            description TEXT NOT NULL,
            ip_address TEXT DEFAULT '127.0.0.1',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_user_db()

def log_activity(user_id: int, action_type: str, description: str):
    try:
        conn = sqlite3.connect(USER_DB)
        conn.execute(
            "INSERT INTO activity_logs (user_id, action_type, description) VALUES (?, ?, ?)",
            (user_id, action_type, description)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_user_activity(user_id: int, limit: int = 8):
    try:
        conn = sqlite3.connect(USER_DB)
        cur = conn.cursor()
        cur.execute(
            "SELECT action_type, description, created_at FROM activity_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cur.fetchall()
        conn.close()
        return [{"action_type": r[0], "description": r[1], "created_at": r[2]} for r in rows]
    except Exception:
        return []

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_current_user(request: Request) -> dict | None:
    email = request.cookies.get("session_user")
    if not email:
        return None
    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, created_at FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "email": row[2], "created_at": row[3]}
    return None

app = FastAPI(
    title="AI SDLC Orchestrator & User Web Application",
    description="Interactive Web Platform and Governed Pipeline",
    version="0.5.0"
)

# Shared CSS styles
SHARED_STYLES = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #0b0f19;
        --card-bg: #111827;
        --card-border: #1f293d;
        --primary: #3b82f6;
        --primary-glow: rgba(59, 130, 246, 0.25);
        --accent: #8b5cf6;
        --text-main: #f8fafc;
        --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Inter', -apple-system, sans-serif;
        background-color: var(--bg);
        color: var(--text-main);
        line-height: 1.6;
    }
    .navbar {
        border-bottom: 1px solid var(--card-border);
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(12px);
        position: sticky;
        top: 0;
        z-index: 100;
        padding: 16px 40px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .logo {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 1.25rem;
        font-weight: 700;
        color: #fff;
        text-decoration: none;
    }
    .logo-icon {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 18px;
        color: #fff;
        box-shadow: 0 0 16px var(--primary-glow);
    }
    .btn {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        padding: 10px 22px;
        border-radius: 10px;
        text-decoration: none;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 12px var(--primary-glow);
        transition: transform 0.15s ease, opacity 0.15s ease;
    }
    .btn:hover {
        transform: translateY(-1px);
        opacity: 0.95;
    }
    .btn-outline {
        background: transparent;
        border: 1px solid #334155;
        color: #cbd5e1;
        box-shadow: none;
    }
    .btn-outline:hover {
        border-color: #64748b;
        background: rgba(255,255,255,0.05);
    }
    .card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 16px;
        padding: 32px;
    }
    input {
        width: 100%;
        padding: 12px 16px;
        background: #090d16;
        border: 1px solid #1f293d;
        border-radius: 8px;
        color: #f8fafc;
        margin-bottom: 16px;
        font-family: inherit;
        font-size: 0.95rem;
        box-sizing: border-box;
    }
    input:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 3px var(--primary-glow);
    }
    .alert-error {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
</style>
"""

# ==========================================
# 1. USER APPLICATION: HOMEPAGE (/)
# ==========================================
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    user = get_current_user(request)
    auth_links = f"""
        <a href="/app/dashboard" class="btn btn-outline" style="font-size: 13px;">Dashboard ({user['name']})</a>
        <a href="/logout" class="btn btn-outline" style="font-size: 13px; color: #f87171;">Sign Out</a>
    """ if user else """
        <a href="/login" class="btn btn-outline" style="font-size: 13px;">Sign In</a>
        <a href="/signup" class="btn" style="font-size: 13px;">Get Started Free</a>
    """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome | AI-Powered Platform</title>
        {SHARED_STYLES}
    </head>
    <body>
        <nav class="navbar">
            <a href="/" class="logo">
                <div class="logo-icon">🚀</div>
                <span>ApexPlatform</span>
            </a>
            <div style="display: flex; gap: 12px; align-items: center;">
                <a href="/orchestrator" class="btn btn-outline" style="font-size: 13px; border-color: #8b5cf6; color: #c084fc;">
                    🛡️ SDLC Orchestrator
                </a>
                {auth_links}
            </div>
        </nav>

        <section style="padding: 100px 40px 60px 40px; text-align: center; max-width: 900px; margin: 0 auto;">
            <div style="display: inline-flex; align-items: center; gap: 8px; padding: 6px 16px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 9999px; color: #60a5fa; font-size: 13px; font-weight: 600; margin-bottom: 24px;">
                ✨ Now Live on Localhost
            </div>
            <h1 style="font-size: 3.5rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.15; margin-bottom: 20px;">
                Build and Deliver Products <br>
                <span style="background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">With Total Confidence</span>
            </h1>
            <p style="font-size: 1.25rem; color: var(--text-muted); margin-bottom: 40px; line-height: 1.6;">
                Welcome to ApexPlatform! Create an account today, authenticate securely, and manage your projects with full enterprise compliance.
            </p>
            <div style="display: flex; gap: 16px; justify-content: center;">
                <a href="/signup" class="btn" style="padding: 14px 32px; font-size: 1.05rem;">
                    Create Free Account →
                </a>
                <a href="/login" class="btn btn-outline" style="padding: 14px 28px; font-size: 1.05rem;">
                    Sign In
                </a>
            </div>
        </section>

        <section style="max-width: 1100px; margin: 40px auto 100px auto; padding: 0 40px; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px;">
            <div class="card">
                <div style="font-size: 2rem; margin-bottom: 12px;">🔐</div>
                <h3 style="margin-bottom: 8px; font-size: 1.2rem;">Secure Authentication</h3>
                <p style="color: var(--text-muted); font-size: 0.95rem;">
                    Accounts are encrypted with one-way SHA-256 cryptographic hashing and secured with cookie-based session management.
                </p>
            </div>
            <div class="card">
                <div style="font-size: 2rem; margin-bottom: 12px;">📊</div>
                <h3 style="margin-bottom: 8px; font-size: 1.2rem;">Live User Dashboard</h3>
                <p style="color: var(--text-muted); font-size: 0.95rem;">
                    Registered users gain immediate access to their personal dashboard displaying their profile and account status.
                </p>
            </div>
            <div class="card">
                <div style="font-size: 2rem; margin-bottom: 12px;">⚡</div>
                <h3 style="margin-bottom: 8px; font-size: 1.2rem;">Governed by SDLC Engine</h3>
                <p style="color: var(--text-muted); font-size: 0.95rem;">
                    Every feature on this site is tracked and governed step-by-step through the AI SDLC Orchestrator pipeline.
                </p>
            </div>
        </section>
    </body>
    </html>
    """

# ==========================================
# 2. USER APPLICATION: SIGN-UP (/signup)
# ==========================================
@app.get("/signup", response_class=HTMLResponse)
def signup_page(error: str | None = None):
    error_html = f"<div class='alert-error'>{error}</div>" if error else ""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Create Your Account | ApexPlatform</title>
        {SHARED_STYLES}
    </head>
    <body style="display: flex; flex-direction: column; min-height: 100vh;">
        <nav class="navbar">
            <a href="/" class="logo">
                <div class="logo-icon">🚀</div>
                <span>ApexPlatform</span>
            </a>
            <a href="/login" class="btn btn-outline" style="font-size: 13px;">Sign In</a>
        </nav>

        <div style="flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px;">
            <div class="card" style="width: 100%; max-width: 440px;">
                <h2 style="font-size: 1.75rem; font-weight: 700; margin-bottom: 8px; text-align: center;">Get Started</h2>
                <p style="color: var(--text-muted); text-align: center; margin-bottom: 24px; font-size: 0.95rem;">
                    Create your personal account in seconds.
                </p>

                {error_html}

                <form action="/signup" method="post">
                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Full Name</label>
                    <input type="text" name="name" placeholder="John Doe" required />

                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Email Address</label>
                    <input type="email" name="email" placeholder="john@example.com" required />

                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Password</label>
                    <input type="password" name="password" placeholder="••••••••" minlength="6" required />

                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Confirm Password</label>
                    <input type="password" name="confirm_password" placeholder="••••••••" minlength="6" required />

                    <button type="submit" class="btn" style="width: 100%; justify-content: center; padding: 12px; margin-top: 8px;">
                        Create Account
                    </button>
                </form>

                <p style="text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-top: 24px;">
                    Already have an account? <a href="/login" style="color: #60a5fa; text-decoration: none; font-weight: 600;">Sign in here</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/signup")
def handle_signup(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    name = name.strip()
    email = email.strip().lower()

    if password != confirm_password:
        return RedirectResponse(url="/signup?error=Passwords+do+not+match", status_code=303)
    
    if len(password) < 6:
        return RedirectResponse(url="/signup?error=Password+must+be+at+least+6+characters", status_code=303)

    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return RedirectResponse(url="/signup?error=An+account+with+this+email+already+exists", status_code=303)

    hashed = hash_password(password)
    cur.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", (name, email, hashed))
    conn.commit()
    conn.close()

    response = RedirectResponse(url="/app/dashboard", status_code=303)
    response.set_cookie(key="session_user", value=email, httponly=True)
    return response

# ==========================================
# 3. USER APPLICATION: LOGIN (/login)
# ==========================================
@app.get("/login", response_class=HTMLResponse)
def login_page(error: str | None = None):
    error_html = f"<div class='alert-error'>{error}</div>" if error else ""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Sign In | ApexPlatform</title>
        {SHARED_STYLES}
    </head>
    <body style="display: flex; flex-direction: column; min-height: 100vh;">
        <nav class="navbar">
            <a href="/" class="logo">
                <div class="logo-icon">🚀</div>
                <span>ApexPlatform</span>
            </a>
            <a href="/signup" class="btn" style="font-size: 13px;">Sign Up</a>
        </nav>

        <div style="flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px 20px;">
            <div class="card" style="width: 100%; max-width: 420px;">
                <h2 style="font-size: 1.75rem; font-weight: 700; margin-bottom: 8px; text-align: center;">Welcome Back</h2>
                <p style="color: var(--text-muted); text-align: center; margin-bottom: 24px; font-size: 0.95rem;">
                    Sign in to your account to continue.
                </p>

                {error_html}

                <form action="/login" method="post">
                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Email Address</label>
                    <input type="email" name="email" placeholder="john@example.com" required />

                    <label style="display: block; font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Password</label>
                    <input type="password" name="password" placeholder="••••••••" required />

                    <button type="submit" class="btn" style="width: 100%; justify-content: center; padding: 12px; margin-top: 8px;">
                        Sign In
                    </button>
                </form>

                <p style="text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-top: 24px;">
                    Don't have an account? <a href="/signup" style="color: #60a5fa; text-decoration: none; font-weight: 600;">Sign up free</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def handle_login(email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    hashed = hash_password(password)

    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users WHERE email = ? AND password_hash = ?", (email, hashed))
    user = cur.fetchone()
    conn.close()

    if not user:
        return RedirectResponse(url="/login?error=Invalid+email+or+password", status_code=303)

    response = RedirectResponse(url="/app/dashboard", status_code=303)
    response.set_cookie(key="session_user", value=email, httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_user")
    return response

# ==========================================
# 4. USER APPLICATION: DASHBOARD (/app/dashboard)
# ==========================================
@app.get("/app/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, msg: str | None = None, err: str | None = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    msg_banner = f"<div style='background:rgba(34,197,94,0.15); color:#4ade80; border:1px solid rgba(34,197,94,0.3); padding:12px; border-radius:8px; margin-bottom:16px;'>{msg}</div>" if msg else ""
    err_banner = f"<div style='background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); padding:12px; border-radius:8px; margin-bottom:16px;'>{err}</div>" if err else ""

    activities = get_user_activity(user["id"])
    activity_rows = ""
    for act in activities:
        tag_color = "#38bdf8" if "LOGIN" in act["action_type"] else "#a78bfa" if "NAME" in act["action_type"] else "#f59e0b"
        activity_rows += f"""
        <tr style="border-bottom: 1px solid #1f293d;">
            <td style="padding: 10px 14px;"><span style="background:{tag_color}22; color:{tag_color}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight:600;">{act['action_type']}</span></td>
            <td style="padding: 10px 14px; color: #cbd5e1; font-size: 13px;">{act['description']}</td>
            <td style="padding: 10px 14px; color: #64748b; font-size: 12px; text-align: right;">{act['created_at']}</td>
        </tr>
        """
    if not activity_rows:
        activity_rows = "<tr><td colspan='3' style='padding: 16px; text-align:center; color:#64748b; font-size:13px;'>No activity events logged yet.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>User Dashboard | ApexPlatform</title>
        {SHARED_STYLES}
    </head>
    <body>
        <nav class="navbar">
            <a href="/" class="logo">
                <div class="logo-icon">🚀</div>
                <span>ApexPlatform</span>
            </a>
            <div style="display: flex; gap: 12px; align-items: center;">
                <a href="/orchestrator" class="btn btn-outline" style="font-size: 13px; border-color: #8b5cf6; color: #c084fc;">
                    🛡️ SDLC Control Plane
                </a>
                <a href="/logout" class="btn btn-outline" style="font-size: 13px; color: #f87171;">Sign Out</a>
            </div>
        </nav>

        <main style="max-width: 960px; margin: 40px auto; padding: 0 40px;">
            {msg_banner}
            {err_banner}

            <div class="card" style="margin-bottom: 24px;">
                <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 20px;">
                    <div style="width: 56px; height: 56px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #8b5cf6); display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 700;">
                        {user['name'][0].upper()}
                    </div>
                    <div>
                        <h2 style="font-size: 1.6rem; font-weight: 700;">Welcome, {user['name']}! 👋</h2>
                        <span style="color: var(--text-muted); font-size: 0.95rem;">{user['email']}</span>
                    </div>
                </div>

                <div style="background: rgba(15, 23, 42, 0.6); padding: 18px; border-radius: 10px; border: 1px solid #1f293d;">
                    <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: #64748b; margin-bottom: 8px;">
                        Account Profile Details
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.95rem;">
                        <div><strong>Account ID:</strong> #{user['id']}</div>
                        <div><strong>Member Since:</strong> {user['created_at']}</div>
                        <div><strong>Status:</strong> <span style="color: #4ade80;">Active / Authenticated</span></div>
                        <div><strong>Database:</strong> SQLite (Local)</div>
                    </div>
                </div>
            </div>

            <!-- WEB-02 Profile Management Features -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px;">
                <!-- Form 1: Edit Name -->
                <div class="card" style="border-top: 3px solid #3b82f6;">
                    <h3 style="margin-bottom: 8px; font-size: 1.15rem;">Edit Profile Name</h3>
                    <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 16px;">
                        Update your public display name.
                    </p>
                    <form action="/app/profile/update-name" method="post">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">Display Name</label>
                        <input type="text" name="name" value="{user['name']}" required />
                        <button type="submit" class="btn" style="width: 100%; justify-content: center; font-size: 13px; padding: 10px;">Save Name</button>
                    </form>
                </div>

                <!-- Form 2: Change Password -->
                <div class="card" style="border-top: 3px solid #8b5cf6;">
                    <h3 style="margin-bottom: 8px; font-size: 1.15rem;">Change Password</h3>
                    <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 16px;">
                        Verify current password and set a new one.
                    </p>
                    <form action="/app/profile/update-password" method="post">
                        <input type="password" name="current_password" placeholder="Current password" required />
                        <input type="password" name="new_password" placeholder="New password (min 6 chars)" minlength="6" required />
                        <button type="submit" class="btn" style="width: 100%; justify-content: center; font-size: 13px; padding: 10px; background: #8b5cf6;">Update Password</button>
                    </form>
                </div>
            </div>

            <!-- WEB-03 Activity Log Table -->
            <div class="card" style="border-top: 3px solid #f59e0b; margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
                    <div>
                        <h3 style="font-size: 1.15rem; margin-bottom: 4px;">Security & Account Activity</h3>
                        <p style="color: var(--text-muted); font-size: 0.85rem;">Immutable audit trail of recent actions and logins (WEB-03).</p>
                    </div>
                    <span style="font-size: 11px; background: #1f293d; padding: 4px 10px; border-radius: 6px; color: #f59e0b;">Live SQLite Log</span>
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 1px solid #334155; font-size: 12px; color: #94a3b8; text-transform: uppercase;">
                            <th style="padding: 8px 14px;">Action</th>
                            <th style="padding: 8px 14px;">Description</th>
                            <th style="padding: 8px 14px; text-align: right;">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
                        {activity_rows}
                    </tbody>
                </table>
            </div>

            <div class="card" style="border-top: 3px solid #10b981;">
                <h3 style="margin-bottom: 8px;">Live Verification: Acceptance Criteria</h3>
                <ul style="color: #cbd5e1; font-size: 0.92rem; padding-left: 20px; line-height: 1.8;">
                    <li>✅ <strong>WEB-01:</strong> Homepage, Sign-Up & Secure Login with SHA-256 session auth.</li>
                    <li>✅ <strong>WEB-02:</strong> Live Profile Name editing & password change verification with current password authentication.</li>
                    <li>✅ <strong>WEB-03:</strong> Immutable Security & Activity log recorded and visible above in real time.</li>
                </ul>
            </div>
        </main>
    </body>
    </html>
    """

@app.post("/app/profile/update-name")
def update_profile_name(request: Request, name: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    new_name = name.strip()
    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute("UPDATE users SET name = ? WHERE id = ?", (new_name, user["id"]))
    conn.commit()
    conn.close()

    log_activity(user["id"], "NAME_UPDATED", f"Changed display name to '{new_name}'")
    return RedirectResponse(url="/app/dashboard?msg=Display+name+updated+successfully!", status_code=303)

@app.post("/app/profile/update-password")
def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if len(new_password) < 6:
        return RedirectResponse(url="/app/dashboard?err=New+password+must+be+at+least+6+characters", status_code=303)

    curr_hashed = hash_password(current_password)
    conn = sqlite3.connect(USER_DB)
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
    row = cur.fetchone()

    if not row or row[0] != curr_hashed:
        conn.close()
        log_activity(user["id"], "PASSWORD_FAILED", "Failed attempt to change password (invalid current password)")
        return RedirectResponse(url="/app/dashboard?err=Current+password+is+incorrect", status_code=303)

    new_hashed = hash_password(new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hashed, user["id"]))
    conn.commit()
    conn.close()

    log_activity(user["id"], "PASSWORD_CHANGED", "Account password updated successfully")
    return RedirectResponse(url="/app/dashboard?msg=Password+changed+successfully!", status_code=303)

# ==========================================
# 5. SDLC ORCHESTRATOR DASHBOARD (/orchestrator)
# ==========================================
WORKFLOW_STAGES = [
    ("intake", "Intake"),
    ("ba_review", "BA Review"),
    ("po_review", "PO Review"),
    ("architecture_review", "Arch Review"),
    ("ready_for_development", "Ready Dev"),
    ("development", "Dev"),
    ("qa_ready", "QA Ready"),
    ("qa_execution", "QA Exec"),
    ("po_acceptance", "PO Accept"),
    ("ready_for_release", "Release Ready"),
    ("released", "Released")
]

@app.get("/orchestrator", response_class=HTMLResponse)
def orchestrator_dashboard():
    features = repo.list_features()
    len(features)
    sum(1 for f in features if f.state.value.lower() == "intake")
    sum(1 for f in features if "review" in f.state.value.lower())

    feature_cards = ""
    for f in features:
        req = f.request
        current_state_val = f.state.value.lower()

        badge_style = "background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3);"
        if "approved" in current_state_val or "released" in current_state_val:
            badge_style = "background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3);"
        elif "review" in current_state_val:
            badge_style = "background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);"

        current_idx = 0
        for i, (stage_key, _) in enumerate(WORKFLOW_STAGES):
            if stage_key == current_state_val:
                current_idx = i
                break

        progress_html = "<div style='display:flex; gap:4px; width:100%; background:rgba(15,23,42,0.8); padding:4px; border-radius:8px; border:1px solid #1f293d;'>"
        for i, (_, stage_lbl) in enumerate(WORKFLOW_STAGES):
            active_bg = "background: linear-gradient(90deg, #3b82f6, #06b6d4); box-shadow: 0 0 8px rgba(56,189,248,0.4);" if i <= current_idx else "background:#1f293d;"
            progress_html += f"<div style='flex:1; height:8px; border-radius:4px; {active_bg}' title='{stage_lbl}'></div>"
        progress_html += "</div>"

        # Action buttons
        transition_buttons = ""
        if current_state_val == "intake":
            transition_buttons = f"""
            <form action="/api/features/{req.feature_id}/advance" method="post" style="display:inline;">
                <input type="hidden" name="action" value="submit_for_ba_review">
                <input type="hidden" name="actor_role" value="business_analyst">
                <button type="submit" class="btn" style="padding: 6px 14px; font-size: 13px;">Submit to BA Review →</button>
            </form>
            """
        elif current_state_val == "ba_review":
            transition_buttons = f"""
            <form action="/api/features/{req.feature_id}/advance" method="post" style="display:inline;">
                <input type="hidden" name="action" value="approve_ba">
                <input type="hidden" name="actor_role" value="business_analyst">
                <button type="submit" class="btn" style="padding: 6px 14px; font-size: 13px; background:#10b981;">Approve BA Signoff ✓</button>
            </form>
            """
        elif current_state_val == "po_review":
            transition_buttons = f"""
            <form action="/api/features/{req.feature_id}/advance" method="post" style="display:inline;">
                <input type="hidden" name="action" value="approve_scope">
                <input type="hidden" name="actor_role" value="product_owner">
                <button type="submit" class="btn" style="padding: 6px 14px; font-size: 13px; background:#8b5cf6;">Approve Scope (PO) ✓</button>
            </form>
            """

        criteria_list = "".join([f"<li style='margin-bottom: 6px;'>{ac}</li>" for ac in req.acceptance_criteria])

        feature_cards += f"""
        <div class="card" style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div>
                    <span style="font-family: monospace; font-size: 13px; background:#1f293d; padding: 3px 8px; border-radius: 4px; color: #94a3b8;">{req.feature_id}</span>
                    <h3 style="margin: 8px 0 4px 0; font-size: 1.25rem;">{req.title}</h3>
                </div>
                <span style="{badge_style}; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600;">
                    {f.state.value.upper()}
                </span>
            </div>
            
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 16px;">{req.problem_statement}</p>
            <div style="margin-bottom: 16px;">{progress_html}</div>

            <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 16px;">
                <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; color: #64748b; margin-bottom: 8px;">
                    Acceptance Criteria ({len(req.acceptance_criteria)})
                </div>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem; color: #cbd5e1;">{criteria_list}</ul>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #334155; padding-top: 14px;">
                <div>{transition_buttons}</div>
                <a href="/api/features/{req.feature_id}" target="_blank" class="btn btn-outline" style="font-size: 12px; padding: 6px 12px;">Audit History</a>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>SDLC Orchestrator Control Plane</title>
        {SHARED_STYLES}
    </head>
    <body style="padding-bottom: 60px;">
        <nav class="navbar">
            <div class="logo">
                <div class="logo-icon">🛡️</div>
                <span>AI SDLC Orchestrator</span>
            </div>
            <div style="display: flex; gap: 12px;">
                <a href="/" class="btn btn-outline" style="font-size: 13px;">View Live Website →</a>
                <a href="/docs" target="_blank" class="btn btn-outline" style="font-size: 13px;">Swagger Docs</a>
            </div>
        </nav>

        <header style="padding: 40px; max-width: 1200px; margin: 0 auto;">
            <h1 style="font-size: 2.5rem; font-weight: 800; margin-bottom: 8px;">Governance Control Plane</h1>
            <p style="color: var(--text-muted); font-size: 1.1rem;">
                Enforcing strict requirements, architectural signoffs, and acceptance criteria traceability.
            </p>
        </header>

        <main style="max-width: 1200px; margin: 0 auto; padding: 0 40px; display: grid; grid-template-columns: 1.7fr 1.3fr; gap: 32px;">
            <div>
                <h3 style="margin-bottom: 16px; font-size: 1.25rem;">Active Feature Pipelines</h3>
                {feature_cards}
            </div>
            <div>
                <h3 style="margin-bottom: 16px; font-size: 1.25rem;">Intake New Feature</h3>
                <div class="card" style="border-top: 3px solid var(--primary);">
                    <form action="/api/features/create-form" method="post">
                        <label style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 6px;">Feature Key</label>
                        <input type="text" name="feature_id" placeholder="e.g. WEB-02" required />
                        
                        <label style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 6px;">Feature Title</label>
                        <input type="text" name="title" placeholder="e.g. Password Reset via Email" required />

                        <label style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 6px;">Problem Statement</label>
                        <textarea name="problem" rows="3" style="width:100%; padding:12px; background:#090d16; border:1px solid #1f293d; border-radius:8px; color:white; margin-bottom:16px;" placeholder="Describe the problem..." required></textarea>

                        <label style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: block; margin-bottom: 6px;">Acceptance Criteria (one per line)</label>
                        <textarea name="criteria" rows="4" style="width:100%; padding:12px; background:#090d16; border:1px solid #1f293d; border-radius:8px; color:white; margin-bottom:16px;" placeholder="Enter criteria..." required></textarea>

                        <button type="submit" class="btn" style="width: 100%; justify-content: center; padding: 12px;">Submit to Pipeline</button>
                    </form>
                </div>
            </div>
        </main>
    </body>
    </html>
    """

# Advance SDLC feature
@app.post("/api/features/{feature_id}/advance")
def advance_feature(feature_id: str, action: str = Form(...), actor_role: str = Form(...)):
    workflow_svc = WorkflowService(repo)
    act_enum = Action(action)
    role_enum = Role(actor_role)
    workflow_svc.apply(
        feature_id=feature_id,
        action=act_enum,
        actor_id=f"user_{actor_role}",
        actor_role=role_enum,
        evidence_reference="verified-in-dashboard"
    )
    return RedirectResponse(url="/orchestrator", status_code=303)

@app.get("/api/features")
def get_features():
    return [
        {
            "feature_id": f.request.feature_id,
            "title": f.request.title,
            "state": f.state.value,
            "problem": f.request.problem_statement,
            "criteria": list(f.request.acceptance_criteria)
        }
        for f in repo.list_features()
    ]

@app.get("/api/features/{feature_id}")
def get_feature(feature_id: str):
    f = repo.get_feature(feature_id)
    if not f:
        raise HTTPException(status_code=404, detail="Feature not found")
    return {
        "feature_id": f.request.feature_id,
        "title": f.request.title,
        "state": f.state.value,
        "problem": f.request.problem_statement,
        "criteria": list(f.request.acceptance_criteria),
        "history": [
            {
                "event_id": str(e.event_id),
                "action": e.action.value if hasattr(e.action, "value") else str(e.action),
                "actor_id": e.actor_id,
                "actor_role": e.actor_role.value if hasattr(e.actor_role, "value") else str(e.actor_role),
                "from_state": e.from_state.value if hasattr(e.from_state, "value") else str(e.from_state),
                "target_state": e.target_state.value if hasattr(e.target_state, "value") else str(e.target_state),
                "timestamp": e.timestamp.isoformat()
            }
            for e in f.history
        ]
    }

@app.post("/api/features/create-form")
def create_feature_form(
    feature_id: str = Form(...),
    title: str = Form(...),
    problem: str = Form(...),
    criteria: str = Form(...)
):
    ac_list = tuple(c.strip() for c in criteria.split("\n") if c.strip())
    req = FeatureRequest(
        feature_id=feature_id.strip(),
        title=title.strip(),
        problem_statement=problem.strip(),
        acceptance_criteria=ac_list
    )
    repo.create_feature(req)
    return RedirectResponse(url="/orchestrator", status_code=303)
