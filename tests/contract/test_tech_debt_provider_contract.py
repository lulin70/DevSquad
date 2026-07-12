#!/usr/bin/env python3
"""
TechDebtProvider Contract Tests

Validates that all TechDebtProvider implementations conform to the Protocol
interface defined in protocols.py.

TechDebtManager (real implementation) has identify_debt, scan_codebase_debt,
prioritize, and get_debt_report but does NOT currently implement is_available() —
this gap is documented by test_tech_debt_manager_missing_is_available.

Contract test ownership: shared between DevSquad and tech debt management teams.
Any breaking change to TechDebtProvider Protocol must be negotiated.
"""

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.protocols import TechDebtProvider


class TestTechDebtProviderProtocolDefinition(unittest.TestCase):
    """Verify the TechDebtProvider Protocol definition itself is well-formed."""

    def test_protocol_has_identify_debt(self):
        self.assertTrue(hasattr(TechDebtProvider, "identify_debt"))

    def test_protocol_has_scan_codebase_debt(self):
        self.assertTrue(hasattr(TechDebtProvider, "scan_codebase_debt"))

    def test_protocol_has_prioritize(self):
        self.assertTrue(hasattr(TechDebtProvider, "prioritize"))

    def test_protocol_has_get_debt_report(self):
        self.assertTrue(hasattr(TechDebtProvider, "get_debt_report"))

    def test_protocol_has_is_available(self):
        self.assertTrue(hasattr(TechDebtProvider, "is_available"))


class _MinimalTechDebtProvider:
    """Minimal structurally-compatible implementation for subtyping verification."""

    def identify_debt(self, source: str, category: Any, description: str, location: str, **kwargs: Any) -> Any:  # noqa: ARG002
        return {"id": 1}

    def scan_codebase_debt(self, project_path: str) -> list[Any]:  # noqa: ARG002
        return []

    def prioritize(self) -> list[Any]:
        return []

    def get_debt_report(self) -> Any:
        return {"total": 0}

    def is_available(self) -> bool:
        return True


class TestTechDebtProviderStructuralSubtyping(unittest.TestCase):
    """Verify any class with the right methods satisfies TechDebtProvider structurally."""

    def test_minimal_implementation_is_instance_of_protocol(self):
        """A class implementing all methods should satisfy runtime_checkable isinstance."""
        self.assertIsInstance(_MinimalTechDebtProvider(), TechDebtProvider)

    def test_missing_method_fails_isinstance(self):
        """A class missing a method should NOT satisfy isinstance."""

        class IncompleteProvider:
            def identify_debt(self, source, category, description, location, **kwargs):  # noqa: ARG002
                return {}

            def scan_codebase_debt(self, project_path: str) -> list:  # noqa: ARG002
                return []

            def prioritize(self) -> list:
                return []

            def get_debt_report(self):
                return {}

            # Missing is_available

        self.assertNotIsInstance(IncompleteProvider(), TechDebtProvider)


class TestTechDebtManagerContractGap(unittest.TestCase):
    """Document the known gap: TechDebtManager does not implement is_available().

    TechDebtManager has 4/5 TechDebtProvider methods (identify_debt,
    scan_codebase_debt, prioritize, get_debt_report) but is missing
    is_available(). This test documents the gap so it can be tracked.
    """

    def test_tech_debt_manager_has_identify_debt(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "identify_debt"))

    def test_tech_debt_manager_has_scan_codebase_debt(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "scan_codebase_debt"))

    def test_tech_debt_manager_has_prioritize(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "prioritize"))

    def test_tech_debt_manager_has_get_debt_report(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "get_debt_report"))

    def test_tech_debt_manager_missing_is_available(self):
        """Document: TechDebtManager does NOT implement is_available().

        This is a known gap. When fixed, this test should be updated to
        verify TechDebtManager fully satisfies TechDebtProvider.
        """
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertFalse(
            hasattr(TechDebtManager, "is_available"),
            "TechDebtManager now has is_available() — update this test to verify full Protocol compliance",
        )


if __name__ == "__main__":
    unittest.main()
