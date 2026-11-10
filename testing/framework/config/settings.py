"""
Enterprise Test Settings and Environment Configuration.
Supports multiple deployment profiles: local, staging, production.
Loaded via environment variables or .env files with sensible defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvironmentConfig:
    env_name: str
    base_url: str
    db_path: Path
    headless: bool
    browser_type: str
    viewport_width: int
    viewport_height: int
    default_timeout_ms: int
    slow_mo_ms: int


def load_config() -> EnvironmentConfig:
    env = os.getenv("TEST_ENV", "local").lower()
    base_dir = Path(__file__).resolve().parent.parent.parent.parent

    if env == "staging":
        return EnvironmentConfig(
            env_name="staging",
            base_url=os.getenv("STAGING_BASE_URL", "https://staging.orderhub.internal"),
            db_path=base_dir / "apps" / "order_hub" / "order_hub_staging.db",
            headless=True,
            browser_type=os.getenv("BROWSER", "chromium"),
            viewport_width=1920,
            viewport_height=1080,
            default_timeout_ms=10000,
            slow_mo_ms=0,
        )
    
    # Default to Local Development Profile
    return EnvironmentConfig(
        env_name="local",
        base_url=os.getenv("BASE_URL", "http://127.0.0.1:8002"),
        db_path=base_dir / "apps" / "order_hub" / "order_hub.db",
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        browser_type=os.getenv("BROWSER", "chromium"),
        viewport_width=1440,
        viewport_height=900,
        default_timeout_ms=5000,
        slow_mo_ms=int(os.getenv("SLOW_MO", "0")),
    )
