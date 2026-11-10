"""
Enterprise E2E Playwright Specs: Authentication & Registration Journey.
Demonstrates:
- Dynamic Synthetic Test Data generation.
- Form manipulation and client-side assertions.
- Database state verification.
"""
from __future__ import annotations

from testing.framework.pages.auth_page import AuthPage
from testing.test_data.factories.data_factory import DatabaseTestSeeder, TestDataFactory


def test_positive_user_registration_flow(auth_page: AuthPage, db_seeder: DatabaseTestSeeder):
    # 1. Arrange: Generate unique test data
    user_data = TestDataFactory.create_user_payload("reg_qa")

    # 2. Act: Navigate and register user
    auth_page.open_signup()
    auth_page.register_user(user_data.username, user_data.email, user_data.password)

    # 3. Assert UI: Redirects to login with confirmation
    auth_page.wait_for_url_contains("/login")
    auth_page.assert_success_banner_contains("Account created successfully")

    # 4. Teardown / Cleanup hook
    db_seeder.purge_user_orders(user_data.username)


def test_negative_duplicate_registration_rejected(auth_page: AuthPage, db_seeder: DatabaseTestSeeder):
    # Arrange: Seed existing user directly into DB
    user_data = TestDataFactory.create_user_payload("dup_qa")
    db_seeder.seed_test_user(user_data)

    # Act: Attempt to register with identical username
    auth_page.open_signup()
    auth_page.register_user(user_data.username, "another_email@domain.com", "SamplePass123!")

    # Assert: Error alert shown and user stays on registration page
    auth_page.assert_error_banner_contains("Username or Email already exists")
    assert "/signup" in auth_page.get_current_url()

    # Teardown
    db_seeder.purge_user_orders(user_data.username)


def test_negative_invalid_login_credentials(auth_page: AuthPage):
    # Act: Submit non-existent user credentials
    auth_page.open_login()
    auth_page.login("non_existent_user_999", "BadPassword@999")

    # Assert: Explicit security rejection banner
    auth_page.assert_error_banner_contains("Invalid username or password")
