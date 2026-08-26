"""Unit tests for RoleSpecificMockBackend (V4.3.2).

Verifies the role-specific mock backend that produces differentiated
content per role when role_specific=True.

7-dimension coverage: Happy / Config / Boundary / Integration.
"""

from __future__ import annotations

import os
import sys
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.role_specific_mock_backend import (  # noqa: E402
    _ROLE_TEMPLATES,
    RoleSpecificMockBackend,
)


class TestRoleSpecificMockDefaultMode(unittest.TestCase):
    """Tests for role_specific=False (default, compatible with MockBackend)."""

    def test_01_default_mode_produces_mock_header(self) -> None:
        """Happy: role_specific=False -> output contains [MOCK MODE] header."""
        backend = RoleSpecificMockBackend(role_specific=False)
        output = backend.generate(
            "test prompt", role_name="Architect", task_description="design"
        )
        self.assertIn("[MOCK MODE]", output)
        self.assertIn("Architect", output)
        self.assertIn("design", output)

    def test_02_default_mode_no_role_template(self) -> None:
        """Config: role_specific=False -> no role-specific template appended."""
        backend = RoleSpecificMockBackend(role_specific=False)
        output = backend.generate("test", role_name="Architect")
        self.assertNotIn("## Architecture Analysis", output)


class TestRoleSpecificMockRoleMode(unittest.TestCase):
    """Tests for role_specific=True."""

    def test_03_architect_template_appended(self) -> None:
        """Config: role_specific=True + role_name='Architect' -> architecture template."""
        backend = RoleSpecificMockBackend(role_specific=True)
        output = backend.generate("design auth", role_name="Architect")
        self.assertIn("## Architecture Analysis", output)
        self.assertIn("Component decomposition", output)
        self.assertIn("NFRs", output)

    def test_04_all_7_roles_have_templates(self) -> None:
        """Config: all 7 core roles produce role-specific output."""
        backend = RoleSpecificMockBackend(role_specific=True)
        roles = [
            "architect",
            "product-manager",
            "security",
            "tester",
            "solo-coder",
            "devops",
            "ui-designer",
        ]
        for role in roles:
            output = backend.generate("task", role_name=role)
            template = _ROLE_TEMPLATES[role]
            marker = template.split("\n")[0]
            self.assertIn(marker, output, f"Role {role} template not found in output")

    def test_05_is_available_returns_true(self) -> None:
        """Happy: is_available() -> True (no external dependencies)."""
        backend = RoleSpecificMockBackend()
        self.assertTrue(backend.is_available())


class TestRoleSpecificMockBoundary(unittest.TestCase):
    """Boundary tests."""

    def test_06_unknown_role_falls_back_to_base_mock(self) -> None:
        """Boundary: unknown role name -> no template appended (base mock only)."""
        backend = RoleSpecificMockBackend(role_specific=True)
        output = backend.generate("task", role_name="UnknownRole123")
        self.assertIn("[MOCK MODE]", output)
        for template in _ROLE_TEMPLATES.values():
            marker = template.split("\n")[0]
            self.assertNotIn(marker, output)

    def test_07_partial_role_name_match(self) -> None:
        """Boundary: partial role name match ('arch' matches 'architect')."""
        backend = RoleSpecificMockBackend(role_specific=True)
        output = backend.generate("task", role_name="arch")
        self.assertIn("## Architecture Analysis", output)


class TestRoleSpecificMockIntegration(unittest.TestCase):
    """Integration tests."""

    def test_08_call_counter_increments(self) -> None:
        """Integration: _call_counter_er increments on each generate() call."""
        import scripts.collaboration.role_specific_mock_backend as module

        before = module._call_counter_er
        backend = RoleSpecificMockBackend()
        backend.generate("test1")
        backend.generate("test2")
        after = module._call_counter_er
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
