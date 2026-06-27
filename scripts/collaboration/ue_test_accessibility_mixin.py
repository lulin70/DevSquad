"""Accessibility mixin for UETestFramework.

Extracts WCAG 2.1 AA accessibility check generation and the associated
check-list constant so the main framework file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - WCAG 2.1 AA check-list constant
    - Accessibility check generation for UE test plans
"""

from typing import Any

from .ue_test_framework_base import UETestFrameworkBase

# ============================================================
# WCAG 2.1 AA Accessibility Checks
# ============================================================

WCAG_AA_CHECKS: list[dict[str, str]] = [
    {"check": "1.1.1 Non-text Content", "category": "perceivable", "description": "All non-text content has text alternatives"},
    {"check": "1.3.1 Info and Relationships", "category": "perceivable", "description": "Information conveyed through presentation is also available in text"},
    {"check": "1.4.3 Contrast (Minimum)", "category": "perceivable", "description": "Text contrast ratio at least 4.5:1 for normal text"},
    {"check": "1.4.11 Non-text Contrast", "category": "perceivable", "description": "UI components and graphical objects contrast ratio at least 3:1"},
    {"check": "2.1.1 Keyboard", "category": "operable", "description": "All functionality available from keyboard"},
    {"check": "2.4.3 Focus Order", "category": "operable", "description": "Focus order preserves meaning and operability"},
    {"check": "2.4.6 Headings and Labels", "category": "operable", "description": "Headings and labels describe topic or purpose"},
    {"check": "2.4.7 Focus Visible", "category": "operable", "description": "Keyboard focus indicator always visible"},
    {"check": "3.1.1 Language of Page", "category": "understandable", "description": "Default human language of page determinable"},
    {"check": "3.2.2 On Input", "category": "understandable", "description": "Changing input setting does not automatically change context"},
    {"check": "3.3.1 Error Identification", "category": "understandable", "description": "Errors automatically detected and described in text"},
    {"check": "3.3.2 Labels or Instructions", "category": "understandable", "description": "Labels provided when user input required"},
    {"check": "4.1.2 Name Role Value", "category": "robust", "description": "Name and role determinable, states can be set programmatically"},
    {"check": "4.1.3 Status Messages", "category": "robust", "description": "Status messages can be programmatically determined"},
]


class UETestAccessibilityMixin(UETestFrameworkBase):
    """Provides WCAG 2.1 AA accessibility check generation."""

    def _generate_accessibility_checks(self) -> list[dict[str, Any]]:
        """Generate WCAG 2.1 AA accessibility check list."""
        checks = []
        for wcag in WCAG_AA_CHECKS:
            checks.append(
                {
                    "check": wcag["check"],
                    "category": wcag["category"],
                    "description": wcag["description"],
                    "status": "pending",
                    "automated": wcag["category"] in ("perceivable", "operable"),
                }
            )
        return checks
