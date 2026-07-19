"""DEPRECATED shim — V4.2.0 will delete this file.

Import from ``ue_test_mixins`` instead. The class definition now lives in
the merged module; this file only re-exports for backward compatibility.
"""

from .ue_test_mixins import WCAG_AA_CHECKS, UETestAccessibilityMixin

__all__ = ["WCAG_AA_CHECKS", "UETestAccessibilityMixin"]
