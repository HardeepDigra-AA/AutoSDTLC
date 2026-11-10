"""
Base Page Object Model (POM) encapsulation.
Provides standardized element wrappers, explicit wait strategies, and fluent actions.
"""
from __future__ import annotations

from playwright.sync_api import Locator, Page


class BasePage:
    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def navigate_to(self, path: str = ""):
        target = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        self.page.goto(target)

    def get_by_test_id(self, test_id: str) -> Locator:
        return self.page.locator(f"[data-testid='{test_id}']")

    def wait_for_url_contains(self, snippet: str, timeout_ms: int = 5000):
        self.page.wait_for_url(f"**/*{snippet}*", timeout=timeout_ms)

    def get_current_url(self) -> str:
        return self.page.url
