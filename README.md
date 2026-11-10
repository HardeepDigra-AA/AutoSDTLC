# OrderHub Enterprise Platform & Playwright Automation Framework

An enterprise-standard, full-stack E-Commerce platform built with **Python 3 / FastAPI** and automated using **Playwright** with the **Page Object Model (POM)** design pattern.

---

## 🏛️ Architecture Overview

The repository cleanly decouples the production application layer from the test automation framework in dedicated parent folders:

```text
├── apps/                                  # 🚀 PRODUCTION APPLICATION LAYER
│   └── order_hub/
│       ├── database/
│       │   └── connection.py              # SQLite relational schema & migrations
│       ├── services/
│       │   ├── auth_service.py            # SHA-256 password hashing & session management
│       │   ├── inventory_service.py       # Warehouse batch intake & automatic stock sync
│       │   └── order_service.py           # Multi-tiered pricing, coupons & transactions
│       ├── static/js/
│       │   └── components.js              # Shadow DOM Web Component (<order-summary-widget>)
│       └── main.py                        # FastAPI routes, HTML UI & JSON REST endpoints
│
└── testing/                               # 🎭 ENTERPRISE PLAYWRIGHT FRAMEWORK
    ├── conftest.py                        # Background server fixture & browser lifecycle
    ├── framework/
    │   ├── config/                        # Multi-environment settings (local, staging, prod)
    │   └── pages/                         # Page Object Model (BasePage, Auth, Catalog, Checkout, Orders)
    ├── test_data/                         # Test Data Management (TDM) & Database Seeder
    └── tests_e2e/specs/                   # End-to-End Playwright test specifications
```

---

## 🚀 Running the Application

To launch the OrderHub web application locally:

```bash
uvicorn apps.order_hub.main:app --host 127.0.0.1 --port 8002 --reload
```

Open your browser at: **[http://127.0.0.1:8002](http://127.0.0.1:8002)**

---

## 🧪 Running the Playwright Test Suite

The test suite self-bootstraps the application server, provisions synthetic test fixtures, and executes across headless Chromium:

```bash
pytest testing/tests_e2e/specs/ -v
```

### Key Automated Scenarios Covered:
1. **User Authentication & Registration**: Positive signup, duplicate username rejection, invalid credentials.
2. **Catalog Search, Filtering & Pagination**: Category dropdown filter, live query search, multi-page pagination.
3. **Shadow DOM Piercing**: Piercing into encapsulated custom elements (`<order-summary-widget>`) to validate real-time totals.
4. **Network Interception & API Mocking**: `page.route` mocking coupon validation endpoints.
5. **Cross-Module Invariant Verification**: Direct database assertions verifying inventory stock deductions after order placement.

---

## 🛡️ Code Quality & Linting

```bash
ruff check .
```
