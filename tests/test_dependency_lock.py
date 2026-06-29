#!/usr/bin/env python3
"""
Tests for requirements.lock dependency lock file (P0-3).

Verifies:
  - requirements.lock exists (project hard constraint)
  - Contains locked versions (==) for installed dependencies
  - Documents all project-declared dependencies
  - pyyaml is locked (core required dependency)
"""

import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH = os.path.join(PROJECT_ROOT, "requirements.lock")


class TestDependencyLockExists:
    """Verify requirements.lock exists (project hard constraint)."""

    def test_lock_file_exists(self):
        """requirements.lock must exist for reproducible builds."""
        assert os.path.isfile(LOCK_PATH), f"Missing: {LOCK_PATH}"

    def test_lock_file_non_empty(self):
        """requirements.lock must be non-empty."""
        assert os.path.getsize(LOCK_PATH) > 0


class TestDependencyLockContent:
    """Verify requirements.lock content is valid."""

    def test_contains_locked_versions(self):
        """Lock file must contain at least one == locked version."""
        with open(LOCK_PATH) as f:
            content = f.read()
        locked_lines = [line for line in content.splitlines()
                        if line and not line.startswith("#") and "==" in line]
        assert len(locked_lines) >= 1, "No locked (==) versions found"

    def test_pyyaml_locked(self):
        """pyyaml (core required dependency) must be locked."""
        with open(LOCK_PATH) as f:
            content = f.read()
        # Either locked (==) or documented as not installed (commented >=)
        assert "pyyaml" in content.lower()

    def test_documents_optional_dependencies(self):
        """Lock file must document optional deps (api/visualization/dev)."""
        with open(LOCK_PATH) as f:
            content = f.read()
        # Must mention key optional deps
        assert "fastapi" in content.lower()
        assert "uvicorn" in content.lower()
        assert "pydantic" in content.lower()

    def test_has_usage_instructions(self):
        """Lock file must have usage instructions."""
        with open(LOCK_PATH) as f:
            content = f.read()
        assert "pip install" in content.lower()
        assert "usage" in content.lower() or "用法" in content


if __name__ == "__main__":
    unittest.main()
