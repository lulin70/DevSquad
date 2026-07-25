"""Unit tests for V4.3.1 OutputValidator base64/Unicode detection.

Covers the two new pattern groups added in V4.3.1 Phase 2:
  - base64_encoded_leak: JWT-like tokens + long base64 blobs with decode
    escalation (medium -> high when decoded content contains sk-/password=/AKIA)
  - unicode_homoglyph: Cyrillic/Greek confusable characters impersonating
    Latin letters

7 test dimensions covered:
  - Happy (4 tests): positive detection of each new pattern
  - Boundary (2 tests): short/exact-length base64 edge cases
  - Error (1 test): decode failure keeps medium (fail-secure)
  - Config (1 test): validate() scans all 6 categories
  - Integration (1 test): mixed attack detects multiple findings
  - Security (1 test): base64-encoded password escalated to high
  - Performance (1 test): large text scanned in < 100ms
"""

from __future__ import annotations

import base64 as base64_module
import os
import sys
import time
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.output_validator import (  # noqa: E402
    OutputValidator,
)


class TestOutputValidatorV431(unittest.TestCase):
    """V4.3.1 base64/Unicode detection unit tests (11 tests, 7 dimensions)."""

    # ------------------------------------------------------------------
    # Happy: positive detection
    # ------------------------------------------------------------------

    def test_base64_jwt_token_detected(self) -> None:
        """Happy: JWT-like 3-segment base64 is detected as high severity."""
        validator = OutputValidator()
        # eyJ + 8 chars . 8 chars . 8 chars (JWT-like)
        text = "eyJabcdefgh.ijklmnopqr.stuvwxyz12"
        result = validator.validate(text)
        jwt_findings = [
            f for f in result.findings
            if f.category == "base64_encoded_leak" and f.pattern_name == "base64_jwt_token"
        ]
        self.assertGreaterEqual(len(jwt_findings), 1)
        self.assertEqual(jwt_findings[0].severity, "high")

    def test_homoglyph_cyrillic_a_detected(self) -> None:
        """Happy: Cyrillic 'a' (U+0430) replacing Latin 'a' is detected."""
        validator = OutputValidator()
        text = "\u0430dmin"  # Cyrillic а + Latin "dmin"
        result = validator.validate(text)
        findings = [
            f for f in result.findings
            if f.category == "unicode_homoglyph" and f.pattern_name == "homoglyph_cyrillic_a"
        ]
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")

    def test_homoglyph_cyrillic_o_detected(self) -> None:
        """Happy: Cyrillic 'o' (U+043E) replacing Latin 'o' is detected."""
        validator = OutputValidator()
        text = "l\u043egin"  # Cyrillic о in "login"
        result = validator.validate(text)
        findings = [
            f for f in result.findings
            if f.category == "unicode_homoglyph" and f.pattern_name == "homoglyph_cyrillic_o"
        ]
        self.assertGreaterEqual(len(findings), 1)

    def test_homoglyph_greek_o_detected(self) -> None:
        """Happy: Greek 'o' (U+03BF) replacing Latin 'o' is detected."""
        validator = OutputValidator()
        text = "l\u03bfgin"  # Greek ο in "login"
        result = validator.validate(text)
        findings = [
            f for f in result.findings
            if f.category == "unicode_homoglyph" and f.pattern_name == "homoglyph_greek_o"
        ]
        self.assertGreaterEqual(len(findings), 1)

    # ------------------------------------------------------------------
    # Boundary: edge cases
    # ------------------------------------------------------------------

    def test_short_base64_not_detected(self) -> None:
        """Boundary: short base64 (<64 chars) does NOT trigger a finding."""
        validator = OutputValidator()
        text = "data=dGVzdA== short"
        result = validator.validate(text)
        base64_findings = [
            f for f in result.findings if f.category == "base64_encoded_leak"
        ]
        self.assertEqual(len(base64_findings), 0)

    def test_base64_exactly_64_chars_detected(self) -> None:
        """Boundary: exactly 64 alphanumeric chars triggers base64_long_blob.

        64 chars is the minimum threshold for the {64,} quantifier.
        Decodes to non-sensitive content -> stays medium.
        """
        validator = OutputValidator()
        text = "B" * 64
        result = validator.validate(text)
        base64_findings = [
            f for f in result.findings if f.category == "base64_encoded_leak"
        ]
        self.assertGreaterEqual(len(base64_findings), 1)
        self.assertEqual(base64_findings[0].severity, "medium")
        self.assertEqual(base64_findings[0].pattern_name, "base64_long_blob")

    # ------------------------------------------------------------------
    # Error: fail-secure behavior
    # ------------------------------------------------------------------

    def test_base64_decode_failure_fail_secure(self) -> None:
        """Error: invalid base64 length (65 chars) decode fails -> stays medium.

        65 mod 4 = 1, which is an invalid base64 length.
        The decode raises binascii.Error; the finding stays medium (fail-secure).
        """
        validator = OutputValidator()
        # 65 'A' chars: regex matches {64,} but decode fails (65 mod 4 = 1)
        text = "A" * 65
        result = validator.validate(text)
        base64_findings = [
            f for f in result.findings if f.category == "base64_encoded_leak"
        ]
        self.assertGreaterEqual(len(base64_findings), 1)
        # Decode failure -> no escalation -> stays medium
        self.assertEqual(base64_findings[0].severity, "medium")

    # ------------------------------------------------------------------
    # Config: validate() integrates all 6 categories
    # ------------------------------------------------------------------

    def test_validate_returns_6_categories(self) -> None:
        """Config: validate() scans all 6 pattern categories in one call."""
        validator = OutputValidator()
        text = (
            "eval(1) found sk-" + "a" * 40 + " leak /etc/passwd "
            "ignore previous instructions " + "B" * 64 + " user=\u0430dmin"
        )
        result = validator.validate(text)
        categories = {f.category for f in result.findings}
        expected = {
            "code_injection",
            "sensitive_info",
            "path_leak",
            "prompt_injection",
            "base64_encoded_leak",
            "unicode_homoglyph",
        }
        self.assertEqual(categories, expected)

    # ------------------------------------------------------------------
    # Integration: mixed attack detection
    # ------------------------------------------------------------------

    def test_validate_mixed_attack(self) -> None:
        """Integration: mixed base64 + Cyrillic homoglyph detected as 2 findings."""
        validator = OutputValidator()
        base64_part = "A" * 80
        text = f"config={base64_part} user=\u0430dmin"
        result = validator.validate(text)
        base64_findings = [
            f for f in result.findings if f.category == "base64_encoded_leak"
        ]
        homoglyph_findings = [
            f for f in result.findings if f.category == "unicode_homoglyph"
        ]
        self.assertGreaterEqual(len(base64_findings), 1)
        self.assertGreaterEqual(len(homoglyph_findings), 1)

    # ------------------------------------------------------------------
    # Security: base64-encoded password escalated to high
    # ------------------------------------------------------------------

    def test_base64_encoded_password_escalated_to_high(self) -> None:
        """Security: base64-encoded password= is escalated from medium to high.

        54 bytes (multiple of 3) -> 72 base64 chars, no padding.
        Decoded content contains "password=" -> severity escalates to high.
        """
        validator = OutputValidator()
        encoded = base64_module.b64encode(
            b"password=secret" + b"0" * 39
        ).decode("ascii")
        text = f"data={encoded}"
        result = validator.validate(text)
        base64_findings = [
            f for f in result.findings if f.category == "base64_encoded_leak"
        ]
        self.assertGreaterEqual(len(base64_findings), 1)
        high_findings = [f for f in base64_findings if f.severity == "high"]
        self.assertGreaterEqual(len(high_findings), 1)
        self.assertIn("_sensitive", high_findings[0].pattern_name)

    # ------------------------------------------------------------------
    # Performance: large text scanned quickly
    # ------------------------------------------------------------------

    def test_validate_large_text_performance(self) -> None:
        """Performance: large text scanned in < 100ms.

        Uses a warmup call to eliminate first-call regex overhead from
        the timing measurement.
        """
        validator = OutputValidator()
        large_text = "Normal output line with no risky content.\n" * 1500
        # ~63KB text
        self.assertGreater(len(large_text), 50_000)
        # Warmup: eliminates first-call overhead from timing
        validator.validate("warmup text")
        start = time.perf_counter()
        result = validator.validate(large_text)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.1, f"validate() took {elapsed:.3f}s, expected < 0.1s")
        # Should have no findings (clean text)
        self.assertEqual(len(result.findings), 0)


if __name__ == "__main__":
    unittest.main()
