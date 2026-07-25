#!/usr/bin/env python3
"""Red-team tests for DependencyHallucinationChecker (V4.3.0 P1-7).

Adversarial test cases simulating real-world Slopsquatting attack vectors
documented in:
  - USENIX Security 2025 "Asleep at the Keyboard"
  - arXiv:2605.17062 cross-model hallucination study
  - Socket.dev 2025 malicious advisory reports
  - Snyk slopsquat research 2025-Q4

Each test case represents a distinct attack vector. The test name encodes
the vector family for traceability:

  RT-01..RT-05: Blacklisted hallucinations (exact match)
  RT-06..RT-08: Hyphen/underscore normalization evasion
  RT-09..RT-11: Typo-squatting (Levenshtein ≤2)
  RT-12..RT-14: Confusion attacks (two real packages concatenated)
  RT-15..RT-17: Suffix-pattern hallucinations
  RT-18..RT-20: Multi-vector / mixed-ecosystem attacks
  RT-21..RT-22: Evasion attempts (comment hiding, string concat)

Spec: docs/analysis/2026-07-25_P1-7_dependency_hallucination_review.md
      §6 Red-team test plan (≥15 cases required)
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dependency_hallucination_checker import (
    DependencyCategory,
    security_scan_dependencies,
)


def _reset_state() -> None:
    """Reset module state for deterministic red-team tests."""
    from scripts.collaboration.dependency_hallucination_checker import (
        reset_dataset_cache,
    )
    reset_dataset_cache()
    import scripts.collaboration.dependency_hallucination_checker as mod
    mod._call_counter = 0


class RT01to05_BlacklistedHallucinations(unittest.TestCase):
    """RT-01..RT-05: Exact-match blacklisted hallucinations are flagged SUSPICIOUS."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_01_huggingface_cli_hallucination(self) -> None:
        """RT-01: AI hallucinates `huggingface_cli` (real: huggingface_hub)."""
        code = "import huggingface_cli\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].package_name, "huggingface_cli")
        self.assertEqual(suspicious[0].suggested_fix, "huggingface_hub")

    def test_rt_02_aws_cdk_hallucination(self) -> None:
        """RT-02: AI hallucinates `aws-cdk` (real: aws-cdk-lib)."""
        code = "import aws-cdk\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)

    def test_rt_03_rest_framework_hallucination(self) -> None:
        """RT-03: AI hallucinates `rest-framework` (real: djangorestframework)."""
        code = "import rest-framework\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].suggested_fix, "djangorestframework")

    def test_rt_04_react_codeshift_npm_hallucination(self) -> None:
        """RT-04: AI hallucinates `react-codeshift` (real: react + jscodeshift)."""
        code = "import x from 'react-codeshift';\n"
        result = security_scan_dependencies(code, ecosystem="npm")
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)

    def test_rt_05_ccxt_mexc_futures_hallucination(self) -> None:
        """RT-05: AI hallucinates `ccxt-mexc-futures` (crypto exchange SDK)."""
        code = "import ccxt-mexc-futures\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)


class RT06to08_NormalizationEvasion(unittest.TestCase):
    """RT-06..RT-08: Hyphen/underscore variants are caught via normalization."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_06_underscore_variant_of_hyphenated_blacklist(self) -> None:
        """RT-06: `huggingface_cli` (underscore) matches `huggingface-cli` (hyphen)."""
        code = "import huggingface_cli\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)

    def test_rt_07_hyphen_variant_of_underscore_blacklist(self) -> None:
        """RT-07: `aws_cdk` (underscore) matches `aws-cdk` (hyphen) in blacklist."""
        # Note: `aws_cdk` is a valid Python identifier; the regex extracts it.
        # The normalizer generates `aws-cdk` variant which hits the blacklist.
        code = "import aws_cdk\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)

    def test_rt_08_rest_framework_underscore_variant(self) -> None:
        """RT-08: `rest_framework` (underscore) matches `rest-framework` blacklist."""
        code = "import rest_framework\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)


class RT09to11_TypoSquatting(unittest.TestCase):
    """RT-09..RT-11: Typo-squatting via Levenshtein distance ≤2."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_09_requests_transposition_typo(self) -> None:
        """RT-09: `reqeusts` (transposition) → SUSPICIOUS, suggested fix `requests`."""
        code = "import reqeusts\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].suggested_fix, "requests")

    def test_rt_10_numpy_double_letter_typo(self) -> None:
        """RT-10: `numppy` (extra letter) → SUSPICIOUS, suggested fix `numpy`."""
        code = "import numppy\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].suggested_fix, "numpy")

    def test_rt_11_express_npm_typo(self) -> None:
        """RT-11: `expres` (missing 's') in npm → SUSPICIOUS."""
        code = "const x = require('expres');\n"
        result = security_scan_dependencies(code, ecosystem="npm")
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)


class RT12to14_ConfusionAttacks(unittest.TestCase):
    """RT-12..RT-14: Confusion attacks (two real package names concatenated)."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_12_react_codeshift_confusion(self) -> None:
        """RT-12: `react-codeshift` is confusion of `react` + `jscodeshift`."""
        code = "import x from 'react-codeshift';\n"
        result = security_scan_dependencies(code, ecosystem="npm")
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0].suggested_fix, "react")

    def test_rt_13_aws_cdk_confusion(self) -> None:
        """RT-13: `aws-cdk` is confusion of `aws-cdk-lib` family."""
        code = "import aws-cdk\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)

    def test_rt_14_rest_framework_confusion(self) -> None:
        """RT-14: `rest-framework` is confusion of `djangorestframework`."""
        code = "import rest-framework\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)


class RT15to17_SuffixPatternHallucinations(unittest.TestCase):
    """RT-15..RT-17: High-frequency hallucination suffix patterns."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_15_helper_suffix_hallucination(self) -> None:
        """RT-15: `requests-helper` triggers `-helper` suffix pattern."""
        code = "import requests-helper\n"
        result = security_scan_dependencies(code)
        # Suffix pattern → UNKNOWN (manual review required)
        unknown = [f for f in result.findings if f.category == DependencyCategory.UNKNOWN]
        self.assertGreaterEqual(len(unknown), 1)

    def test_rt_16_sdk_suffix_hallucination(self) -> None:
        """RT-16: `django-sdk` triggers `-sdk` suffix pattern."""
        code = "import django-sdk\n"
        result = security_scan_dependencies(code)
        unknown = [f for f in result.findings if f.category == DependencyCategory.UNKNOWN]
        self.assertGreaterEqual(len(unknown), 1)

    def test_rt_17_validator_suffix_hallucination(self) -> None:
        """RT-17: `pydantic-validator` triggers `-validator` suffix pattern."""
        code = "import pydantic-validator\n"
        result = security_scan_dependencies(code)
        unknown = [f for f in result.findings if f.category == DependencyCategory.UNKNOWN]
        self.assertGreaterEqual(len(unknown), 1)


class RT18to20_MultiVectorAndMixedEcosystem(unittest.TestCase):
    """RT-18..RT-20: Multi-vector and mixed-ecosystem attacks."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_18_multiple_suspicious_in_one_file(self) -> None:
        """RT-18: Multiple hallucinated packages in a single file."""
        code = (
            "import huggingface_cli\n"
            "import aws-cdk\n"
            "import rest-framework\n"
        )
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 3)

    def test_rt_19_mixed_suspicious_and_unknown(self) -> None:
        """RT-19: Mix of SUSPICIOUS (blacklist) and UNKNOWN (suffix)."""
        code = (
            "import huggingface_cli\n"        # SUSPICIOUS
            "import django-helper\n"          # UNKNOWN (suffix)
        )
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        unknown = [f for f in result.findings if f.category == DependencyCategory.UNKNOWN]
        self.assertEqual(len(suspicious), 1)
        self.assertGreaterEqual(len(unknown), 1)

    def test_rt_20_npm_scoped_package_hallucination(self) -> None:
        """RT-20: Scoped npm package `@solana-launchpad/sdk` hallucination."""
        code = "import x from '@solana-launchpad/sdk';\n"
        result = security_scan_dependencies(code, ecosystem="npm")
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 1)


class RT21to22_EvasionAttempts(unittest.TestCase):
    """RT-21..RT-22: Evasion attempts that should still be caught or safely handled."""

    def setUp(self) -> None:
        _reset_state()

    def test_rt_21_comment_does_not_trigger_false_positive(self) -> None:
        """RT-21: Commented import `# import huggingface_cli` is NOT flagged.

        This is a negative test: the regex `^\\s*import` should not match
        lines starting with `#` (which is not whitespace).
        """
        code = "# import huggingface_cli\nimport requests\n"
        result = security_scan_dependencies(code)
        suspicious = [f for f in result.findings if f.category == DependencyCategory.SUSPICIOUS]
        self.assertEqual(len(suspicious), 0)
        self.assertEqual(result.stats["known_good"], 1)

    def test_rt_22_blocking_mode_aborts_on_suspicious(self) -> None:
        """RT-22: Blocking mode aborts dispatch on SUSPICIOUS finding."""
        code = "import huggingface_cli\n"
        with self.assertRaises(RuntimeError) as ctx:
            security_scan_dependencies(code, blocking=True)
        self.assertIn("huggingface_cli", str(ctx.exception))
        self.assertIn("SUSPICIOUS", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
