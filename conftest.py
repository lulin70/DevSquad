# conftest.py - Pytest configuration for DevSquad
"""
Pytest configuration with markers and fixtures.
"""

import os
from pathlib import Path


def _load_env_file() -> None:
    """Load .env file if it exists (not tracked by git).

    Manually parses KEY=VALUE lines without requiring python-dotenv.
    Only sets variables that are not already in the environment (env wins over .env).
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "tech_debt: marks tests with known failures (V3.7.0 tech debt)"
    )


# Known failing tests - now marked with @pytest.mark.xfail instead of collect_ignore
# See individual test files for xfail reasons
