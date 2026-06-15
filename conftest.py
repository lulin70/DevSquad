# conftest.py - Pytest configuration for DevSquad
"""
Pytest configuration with markers and fixtures.
"""

import pytest


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
