"""
Page Object Model for the Authentication & Registration Views.
"""
from __future__ import annotations

from playwright.sync_api import Page, expect

from testing.framework.pages.base_page import BasePage


class AuthPage(BasePage):
    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        # Login Locators
        self.input_username = self.get_by_test_id("input-username")
        self.input_password = self.get_by_test_id("input-password")
        self.input_email = self.get_by_test_id("input-email")
        self.btn_login = self.get_by_test_id("btn-login")
        self.btn_signup = self.get_by_test_id("btn-signup")
        self.alert_error = self.get_by_test_id("alert-error")
        self.alert_success = self.get_by_test_id("alert-success")
        self.link_signup = self.get_by_test_id("link-signup")
        self.link_login = self.get_by_test_id("link-login")

    def open_login(self):
        self.navigate_to("/login")
        return self

    def open_signup(self):
        self.navigate_to("/signup")
        return self

    def register_user(self, username: str, email: str, password: str):
        self.input_username.fill(username)
        self.input_email.fill(email)
        self.input_password.fill(password)
        self.btn_signup.click()

    def login(self, username: str, password: str):
        self.input_username.fill(username)
        self.input_password.fill(password)
        self.btn_login.click()

    def assert_error_banner_contains(self, text: str):
        expect(self.alert_error).to_be_visible()
        expect(self.alert_error).to_contain_text(text)

    def assert_success_banner_contains(self, text: str):
        expect(self.alert_success).to_be_visible()
        expect(self.alert_success).to_contain_text(text)
