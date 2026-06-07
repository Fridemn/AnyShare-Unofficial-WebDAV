"""Shared test utilities for AnyShare Unofficial tests."""

from __future__ import annotations

import os
from pathlib import Path


def load_test_env() -> dict[str, str]:
    """Load test environment variables from the process and optional ``tests/.env``.

    Process environment values take precedence over values from ``tests/.env``.
    """
    env: dict[str, str] = {}
    keys = ("TEST_ONLINE", "TEST_BASE_URL", "TEST_SHARING_LINK", "TEST_AUTH_COOKIE", "TEST_DIR_PATH")

    # Always start with process environment (highest precedence)
    for key in keys:
        value = os.environ.get(key)
        if value:
            env[key] = value

    # Try tests/.env (real credentials, git-ignored)
    tests_dir = Path(__file__).parent
    dotenv_path = tests_dir / ".env"
    if dotenv_path.exists():
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in keys:
                env.setdefault(key, value)  # process env wins over file

    return env


def online_tests_enabled(env: dict[str, str]) -> bool:
    """Return True when online integration tests were explicitly enabled."""
    return env.get("TEST_ONLINE", "").lower() in {"1", "true", "yes", "on"}
