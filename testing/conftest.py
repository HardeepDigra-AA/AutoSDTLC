"""
Pytest Fixtures for Enterprise Playwright Test Execution.
Configures:
- Automatic Web Server background orchestration.
- Configuration loading (.env, CLI flags).
- Database Seeder & Test Data cleanup.
- POM fixtures (AuthPage, OrdersDashboardPage).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from testing.framework.config.settings import EnvironmentConfig, load_config
from testing.framework.pages.auth_page import AuthPage
from testing.framework.pages.dashboard_page import OrdersDashboardPage
from testing.test_data.factories.data_factory import DatabaseTestSeeder


@pytest.fixture(scope="session")
def env_config() -> EnvironmentConfig:
    return load_config()


@pytest.fixture(scope="session")
def db_seeder(env_config: EnvironmentConfig) -> DatabaseTestSeeder:
    seeder = DatabaseTestSeeder(env_config.db_path)
    seeder.seed_baseline_catalog()
    return seeder


@pytest.fixture(scope="session", autouse=True)
def app_server(env_config: EnvironmentConfig):
    """Orchestrates the FastAPI server process on port 8002."""
    import sys
    repo_root = Path(__file__).resolve().parent.parent
    python_exe = sys.executable

    server_process = subprocess.Popen(
        [
            python_exe, "-m", "uvicorn", "apps.order_hub.main:app",
            "--host", "127.0.0.1", "--port", "8002"
        ],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2.0)  # Allow socket bind
    yield server_process
    server_process.terminate()
    server_process.wait()


@pytest.fixture(scope="session")
def browser(env_config: EnvironmentConfig):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=env_config.headless,
            slow_mo=env_config.slow_mo_ms
        )
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser, env_config: EnvironmentConfig) -> BrowserContext:
    context = browser.new_context(
        viewport={"width": env_config.viewport_width, "height": env_config.viewport_height}
    )
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    return context.new_page()


@pytest.fixture(scope="function")
def auth_page(page: Page, env_config: EnvironmentConfig) -> AuthPage:
    return AuthPage(page, env_config.base_url)


@pytest.fixture(scope="function")
def dashboard_page(page: Page, env_config: EnvironmentConfig) -> OrdersDashboardPage:
    return OrdersDashboardPage(page, env_config.base_url)
