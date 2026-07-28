"""Unit tests for QualityProbeSlice (V4.3.2 Slice 1).

Verifies the thin-slice quality probe that runs 3-task x 3-arm x n-samples
comparison to measure LLM vs Mock output quality signal strength.

7-dimension coverage: Happy / Error / Boundary / Config / Integration.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.llm_backend import MockBackend  # noqa: E402
from scripts.collaboration.quality_calibration_gate import (  # noqa: E402
    CalibrationGateResult,
)
from scripts.collaboration.quality_probe_slice import (  # noqa: E402
    _ARM_FROZEN,
    _ARM_LLM,
    _ARM_ROLE_SPECIFIC,
    _TASK_IDS,
    _determine_signal_strength,
    run_probe_slice,
)


class TestProbeSliceHappyPath(unittest.TestCase):
    """Happy path tests."""

    def test_01_probe_without_llm_backend(self) -> None:
        """Happy: llm_backend=None -> 2 arms only + llm_arm_skipped=True."""
        report = run_probe_slice(llm_backend=None, n_samples=2)
        self.assertTrue(report.gate_passed)
        self.assertTrue(report.llm_arm_skipped)
        self.assertEqual(report.signal_strength, "noise")
        for task_id in _TASK_IDS:
            self.assertIn(_ARM_FROZEN, report.task_results[task_id])
            self.assertIn(_ARM_ROLE_SPECIFIC, report.task_results[task_id])
            self.assertNotIn(_ARM_LLM, report.task_results[task_id])

    def test_02_probe_with_mock_llm_backend(self) -> None:
        """Happy: MockBackend as LLM arm -> 3 arms x n samples."""
        mock_llm = MockBackend()
        report = run_probe_slice(llm_backend=mock_llm, n_samples=2)
        self.assertTrue(report.gate_passed)
        self.assertFalse(report.llm_arm_skipped)
        for task_id in _TASK_IDS:
            self.assertEqual(len(report.task_results[task_id]), 3)

    def test_03_probe_report_to_markdown(self) -> None:
        """Happy: to_markdown() contains table and conclusion."""
        report = run_probe_slice(llm_backend=None, n_samples=1)
        md = report.to_markdown()
        self.assertIn("Slice 1: Thin-Slice Quality Probe Report", md)
        self.assertIn("frozen_mock", md)
        self.assertIn("Signal Strength", md)


class TestSignalStrengthDetermination(unittest.TestCase):
    """Config tests for _determine_signal_strength()."""

    def test_04_signal_strength_significant(self) -> None:
        """Config: median delta > 0.15 -> 'significant'."""
        mean_stddev = {
            "simple": {
                _ARM_FROZEN: (0.30, 0.0),
                _ARM_ROLE_SPECIFIC: (0.35, 0.0),
                _ARM_LLM: (0.60, 0.0),
            },
            "medium": {
                _ARM_FROZEN: (0.30, 0.0),
                _ARM_ROLE_SPECIFIC: (0.35, 0.0),
                _ARM_LLM: (0.55, 0.0),
            },
            "complex": {
                _ARM_FROZEN: (0.30, 0.0),
                _ARM_ROLE_SPECIFIC: (0.35, 0.0),
                _ARM_LLM: (0.70, 0.0),
            },
        }
        strength, conclusion = _determine_signal_strength(mean_stddev, True, False)
        self.assertEqual(strength, "significant")
        self.assertIn("substantial", conclusion)

    def test_05_signal_strength_marginal(self) -> None:
        """Config: 0.05 < median delta <= 0.15 -> 'marginal'."""
        mean_stddev = {
            "simple": {
                _ARM_FROZEN: (0.40, 0.0),
                _ARM_ROLE_SPECIFIC: (0.40, 0.0),
                _ARM_LLM: (0.50, 0.0),
            },
            "medium": {
                _ARM_FROZEN: (0.40, 0.0),
                _ARM_ROLE_SPECIFIC: (0.40, 0.0),
                _ARM_LLM: (0.52, 0.0),
            },
            "complex": {
                _ARM_FROZEN: (0.40, 0.0),
                _ARM_ROLE_SPECIFIC: (0.40, 0.0),
                _ARM_LLM: (0.48, 0.0),
            },
        }
        strength, _ = _determine_signal_strength(mean_stddev, True, False)
        self.assertEqual(strength, "marginal")

    def test_06_signal_strength_noise(self) -> None:
        """Config: median delta <= 0.05 -> 'noise'."""
        mean_stddev = {
            "simple": {
                _ARM_FROZEN: (0.50, 0.0),
                _ARM_ROLE_SPECIFIC: (0.50, 0.0),
                _ARM_LLM: (0.52, 0.0),
            },
            "medium": {
                _ARM_FROZEN: (0.50, 0.0),
                _ARM_ROLE_SPECIFIC: (0.50, 0.0),
                _ARM_LLM: (0.53, 0.0),
            },
            "complex": {
                _ARM_FROZEN: (0.50, 0.0),
                _ARM_ROLE_SPECIFIC: (0.50, 0.0),
                _ARM_LLM: (0.54, 0.0),
            },
        }
        strength, _ = _determine_signal_strength(mean_stddev, True, False)
        self.assertEqual(strength, "noise")


class TestProbeSliceErrorHandling(unittest.TestCase):
    """Error path tests."""

    def test_07_probe_gate_not_passed(self) -> None:
        """Error: Gate 0 fails -> signal_strength='calibration_failed'."""
        failed_result = CalibrationGateResult(passed=False, diagnostics=["mock failure"])
        with patch(
            "scripts.collaboration.quality_probe_slice.run_calibration_gate",
            return_value=failed_result,
        ):
            report = run_probe_slice(llm_backend=None, n_samples=1)
        self.assertFalse(report.gate_passed)
        self.assertEqual(report.signal_strength, "calibration_failed")
        self.assertEqual(len(report.task_results), 0)

    def test_08_probe_llm_skipped_returns_noise(self) -> None:
        """Boundary: llm_backend=None + gate passed -> 'noise' (cannot assess LLM gap)."""
        report = run_probe_slice(llm_backend=None, n_samples=1)
        self.assertTrue(report.gate_passed)
        self.assertTrue(report.llm_arm_skipped)
        self.assertEqual(report.signal_strength, "noise")


if __name__ == "__main__":
    unittest.main()
