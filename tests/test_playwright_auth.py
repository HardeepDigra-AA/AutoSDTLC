"""
End-to-End Playwright Automation Test Suite for User Registration & Login App.
Technology: Pure Python (pytest + playwright).
Test Cases:
1. test_successful_user_registration_and_db_persistence:
   - Fills out full name, username, and password.
   - Submits signup form and verifies redirect to /login with success banner.
   - Verifies the user is actually stored in SQLite database.
2. test_successful_login_and_dashboard_access:
   - Logs in using registered credentials.
   - Verifies redirect to /dashboard and validates user full name and username display.
   - Clicks logout and verifies session is terminated.
3. test_login_failure_with_invalid_credentials:
   - Attempts login with invalid password.
   - Asserts error banner 'Invalid username or password' is displayed and user remains on /login.
4. test_duplicate_username_registration_rejected:
   - Attempts to register an existing username.
   - Asserts rejection banner 'Username already taken'.
"""
from __future__ import annotations

import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8001"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "auth_app.db"


@pytest.fixture(scope="session", autouse=True)
def run_auth_server():
    """Starts the FastAPI auth application in the background for E2E testing."""
    server_process = subprocess.Popen(
        [
            Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python",
            "-m", "uvicorn", "auth_app:app", "--host", "127.0.0.1", "--port", "8001"
        ],
        cwd=Path(__file__).resolve().parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(1.8)  # Give uvicorn a moment to bind
    yield server_process
    server_process.terminate()
    server_process.wait()


def test_successful_user_registration(page: Page):
    test_user = f"playwright_user_{int(time.time())}"
    
    page.goto(f"{BASE_URL}/signup")
    expect(page.locator("h2")).to_have_text("Create Account")

    # Fill registration fields
    page.fill("#full_name", "Automation Test Engineer")
    page.fill("#username", test_user)
    page.fill("#password", "SecurePass123!")
    page.click("#btn-submit-signup")

    # Validate redirection to login page with success alert
    page.wait_for_url(f"{BASE_URL}/login*")
    expect(page.locator("#success-banner")).to_contain_text("Account created successfully")

    # Direct database assertion: verify record persisted to SQLite
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT username, full_name FROM users WHERE username = ?", (test_user,)).fetchone()
    conn.close()
    assert row is not None, "User was not persisted to SQLite database!"
    assert row[0] == test_user
    assert row[1] == "Automation Test Engineer"


def test_successful_login_and_logout_flow(page: Page):
    test_user = f"login_user_{int(time.time())}"
    password = "MySecretPassword456!"

    # 1. Register first
    page.goto(f"{BASE_URL}/signup")
    page.fill("#full_name", "John Tester")
    page.fill("#username", test_user)
    page.fill("#password", password)
    page.click("#btn-submit-signup")
    page.wait_for_url(f"{BASE_URL}/login*")

    # 2. Log in with newly registered account
    page.fill("#username", test_user)
    page.fill("#password", password)
    page.click("#btn-submit-login")

    # 3. Assert access to protected dashboard
    page.wait_for_url(f"{BASE_URL}/dashboard")
    expect(page.locator("#user-display-name")).to_have_text("John Tester")
    expect(page.locator("#user-username")).to_have_text(test_user)

    # 4. Perform logout
    page.click("#btn-logout")
    page.wait_for_url(f"{BASE_URL}/login*")
    expect(page.locator("#success-banner")).to_contain_text("Logged out successfully")


def test_login_failure_with_wrong_password(page: Page):
    page.goto(f"{BASE_URL}/login")
    page.fill("#username", "non_existent_user_99")
    page.fill("#password", "wrong_password_123")
    page.click("#btn-submit-login")

    page.wait_for_url(f"{BASE_URL}/login*")
    expect(page.locator("#error-banner")).to_contain_text("Invalid username or password")


def test_duplicate_username_registration_rejected(page: Page):
    duplicate_user = f"dup_user_{int(time.time())}"
    
    # First registration
    page.goto(f"{BASE_URL}/signup")
    page.fill("#full_name", "First User")
    page.fill("#username", duplicate_user)
    page.fill("#password", "password123")
    page.click("#btn-submit-signup")
    page.wait_for_url(f"{BASE_URL}/login*")

    # Attempt second registration with same username
    page.goto(f"{BASE_URL}/signup")
    page.fill("#full_name", "Second User")
    page.fill("#username", duplicate_user)
    page.fill("#password", "password456")
    page.click("#btn-submit-signup")

    page.wait_for_url(f"{BASE_URL}/signup*")
    expect(page.locator("#error-banner")).to_contain_text("Username already taken")
