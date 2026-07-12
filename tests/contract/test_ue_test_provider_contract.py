#!/usr/bin/env python3
"""
UETestProvider Contract Tests

Validates that all UETestProvider implementations conform to the Protocol
interface defined in protocols.py.

UETestFramework (real implementation) inherits generate_ue_test_plan directly
and validate_user_journey / assess_usability via mixins. It does NOT currently
implement is_available() — this gap is documented by test_ue_test_framework_missing_is_available.

Contract test ownership: shared between DevSquad and UE testing teams.
Any breaking change to UETestProvider Protocol must be negotiated.
"""

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.protocols import UETestProvider


class TestUETestProviderProtocolDefinition(unittest.TestCase):
    """Verify the UETestProvider Protocol definition itself is well-formed."""

    def test_protocol_has_generate_ue_test_plan(self):
        self.assertTrue(hasattr(UETestProvider, "generate_ue_test_plan"))

    def test_protocol_has_validate_user_journey(self):
        self.assertTrue(hasattr(UETestProvider, "validate_user_journey"))

    def test_protocol_has_assess_usability(self):
        self.assertTrue(hasattr(UETestProvider, "assess_usability"))

    def test_protocol_has_is_available(self):
        self.assertTrue(hasattr(UETestProvider, "is_available"))


class _MinimalUETestProvider:
    """Minimal structurally-compatible implementation for subtyping verification."""

    def generate_ue_test_plan(self, project_description: str) -> Any:
        return {"plan": project_description}

    def validate_user_journey(self, journey: Any, actual_results: dict[str, Any]) -> Any:  # noqa: ARG002
        return {"valid": True}

    def assess_usability(self, interface_description: str) -> Any:  # noqa: ARG002
        return {"score": 8}

    def is_available(self) -> bool:
        return True


class TestUETestProviderStructuralSubtyping(unittest.TestCase):
    """Verify any class with the right methods satisfies UETestProvider structurally."""

    def test_minimal_implementation_is_instance_of_protocol(self):
        """A class implementing all methods should satisfy runtime_checkable isinstance."""
        self.assertIsInstance(_MinimalUETestProvider(), UETestProvider)

    def test_missing_method_fails_isinstance(self):
        """A class missing a method should NOT satisfy isinstance."""

        class IncompleteProvider:
            def generate_ue_test_plan(self, project_description: str) -> Any:  # noqa: ARG002
                return {}

            def validate_user_journey(self, journey: Any, actual_results: dict[str, Any]) -> Any:  # noqa: ARG002
                return {}

            def assess_usability(self, interface_description: str) -> Any:  # noqa: ARG002
                return {}

            # Missing is_available

        self.assertNotIsInstance(IncompleteProvider(), UETestProvider)


class TestUETestFrameworkContractGap(unittest.TestCase):
    """Document the known gap: UETestFramework does not implement is_available().

    UETestFramework has 3/4 UETestProvider methods (generate_ue_test_plan,
    validate_user_journey via mixin, assess_usability via mixin) but is
    missing is_available(). This test documents the gap so it can be tracked.
    """

    def test_ue_test_framework_has_generate_ue_test_plan(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "generate_ue_test_plan"))

    def test_ue_test_framework_has_validate_user_journey(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "validate_user_journey"))

    def test_ue_test_framework_has_assess_usability(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "assess_usability"))

    def test_ue_test_framework_missing_is_available(self):
        """Document: UETestFramework does NOT implement is_available().

        This is a known gap. When fixed, this test should be updated to
        verify UETestFramework fully satisfies UETestProvider.
        """
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertFalse(
            hasattr(UETestFramework, "is_available"),
            "UETestFramework now has is_available() — update this test to verify full Protocol compliance",
        )


if __name__ == "__main__":
    unittest.main()
