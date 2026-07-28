"""Unit tests for QualityCalibrationGate (V4.3.2 Gate 0).

Verifies the instrument calibration gate that validates whether
ConfidenceScorer + FiveAxisConsensusEngine can correctly rank 4
known-quality outputs (gold > llm > filler > empty).

7-dimension coverage: Happy / Error / Boundary / Performance / Config /
Integration.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration.quality_calibration_gate import (  # noqa: E402
    _GAP_THRESHOLD,
    _ORDERING,
    CalibrationGateResult,
    run_calibration_gate,
)


class TestCalibrationGateHappyPath(unittest.TestCase):
    """Happy path tests: gate passes with real gold_outputs.json."""

    def test_01_gate_passes_with_known_good_outputs(self) -> None:
        """Happy: run_calibration_gate() with real data -> passed=True.

        Verifies gold > llm > filler > empty ordering and gap >= 0.15.
        """
        result = run_calibration_gate()
        self.assertTrue(result.passed, f"Gate should pass. Diagnostics: {result.diagnostics}")
        self.assertTrue(result.ordering_correct)
        self.assertGreaterEqual(result.gap_gold_filler, _GAP_THRESHOLD)

    def test_02_gate_scores_all_10_dimensions(self) -> None:
        """Config: each of 4 outputs has 10 dimension scores (5 factor + 5 axis)."""
        result = run_calibration_gate()
        expected_dims = {
            "completeness", "certainty", "specificity", "consistency", "model_quality",
            "correctness", "readability", "architecture", "security", "performance",
        }
        for output_id in _ORDERING:
            dims = result.scores.get(output_id, {})
            self.assertEqual(len(dims), 10, f"{output_id} should have 10 dimensions")
            self.assertEqual(set(dims.keys()), expected_dims)

    def test_03_gate_loads_gold_outputs_json(self) -> None:
        """Integration: data/calibration/gold_outputs.json loaded correctly with 4 outputs."""
        result = run_calibration_gate()
        for output_id in _ORDERING:
            self.assertIn(output_id, result.scores)
            self.assertIsInstance(result.scores[output_id], dict)


class TestCalibrationGateMarkdown(unittest.TestCase):
    """Tests for CalibrationGateResult.to_markdown()."""

    def test_04_to_markdown_contains_section_and_table(self) -> None:
        """Happy: to_markdown() contains header, table, and scores."""
        result = run_calibration_gate()
        md = result.to_markdown()
        self.assertIn("Gate 0: Instrument Calibration Result", md)
        self.assertIn("| Output | Mean Score | Dimensions |", md)
        self.assertIn("gold", md)
        self.assertIn("filler", md)
        self.assertIn("Passed", md)


class TestCalibrationGateErrorHandling(unittest.TestCase):
    """Error path tests: gate fails gracefully."""

    def test_05_gate_fails_when_data_file_missing(self) -> None:
        """Error: missing data file -> passed=False + diagnostics non-empty."""
        with patch(
            "scripts.collaboration.quality_calibration_gate._DATA_PATH",
            new=Path("/nonexistent/path/gold_outputs.json"),
        ):
            result = run_calibration_gate()
        self.assertFalse(result.passed)
        self.assertTrue(len(result.diagnostics) > 0)
        self.assertIn("Failed to load", result.diagnostics[0])

    def test_06_gate_fails_when_ordering_wrong(self) -> None:
        """Error: swapped gold/filler -> ordering_correct=False -> passed=False."""
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "calibration_outputs": {
                            "gold": "",
                            "llm": "short text",
                            "filler": "## Design\n\nDetailed content.\n\n```python\nx = 1\n```",
                            "empty": "",
                        },
                        "probe_tasks": {},
                    },
                    f,
                )
            with patch(
                "scripts.collaboration.quality_calibration_gate._DATA_PATH",
                new=Path(tmp_path),
            ):
                result = run_calibration_gate()
            self.assertFalse(result.ordering_correct)
            self.assertFalse(result.passed)
        finally:
            os.unlink(tmp_path)

    def test_07_gate_fails_when_gap_insufficient(self) -> None:
        """Boundary: gold and filler identical -> gap=0 < threshold -> passed=False."""
        identical = (
            "## Good design\n\nDetailed content with code.\n\n"
            "```python\nx = 1\n```\n\nError handling with try/except."
        )
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "calibration_outputs": {
                            "gold": identical,
                            "llm": "Some content.",
                            "filler": identical,
                            "empty": "",
                        },
                        "probe_tasks": {},
                    },
                    f,
                )
            with patch(
                "scripts.collaboration.quality_calibration_gate._DATA_PATH",
                new=Path(tmp_path),
            ):
                result = run_calibration_gate()
            self.assertLess(result.gap_gold_filler, _GAP_THRESHOLD)
            self.assertFalse(result.passed)
        finally:
            os.unlink(tmp_path)


class TestCalibrationGatePerformance(unittest.TestCase):
    """Performance tests."""

    def test_08_gate_completes_within_5_seconds(self) -> None:
        """Performance: Gate 0 execution < 5 seconds."""
        start = time.time()
        result = run_calibration_gate()
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"Gate took {elapsed:.2f}s, expected < 5s")
        self.assertIsInstance(result, CalibrationGateResult)


if __name__ == "__main__":
    unittest.main()
