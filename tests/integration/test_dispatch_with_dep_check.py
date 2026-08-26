#!/usr/bin/env python3
"""Integration tests for DispatchHooks + DependencyHallucinationChecker (V4.3.0 P1-7).

Validates the anti-ghost-feature dispatch pipeline integration:
  1. ``post_execution_processing`` auto-invokes the dependency scan on every
     worker output containing code markers
  2. SUSPICIOUS/UNKNOWN findings are written to the scratchpad (user-visible)
  3. Usage tracker ticks record detection events
  4. Module call counter increments (CI anti-ghost detection)
  5. Skip conditions (short output, pure prose) work correctly
  6. ``enable_dependency_scan=False`` disables the scan (test isolation)

Spec: docs/architecture/V4.3.0_ARCHITECTURE.md §9.2 (dispatch hook integration)
      docs/prd/V4.3.0_PRD.md §9.2 P1-7
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dependency_hallucination_checker import get_call_count
from scripts.collaboration.dispatch_hooks import DispatchHooks
from scripts.collaboration.scratchpad import ScratchpadEntry


def _reset_call_counter_er() -> None:
    import scripts.collaboration.dependency_hallucination_checker as mod
    mod._call_counter_er = 0


class _MockScratchpad:
    """Minimal Scratchpad stub for testing."""

    def __init__(self) -> None:
        self.entries: list[ScratchpadEntry] = []

    def write(self, entry: ScratchpadEntry) -> None:
        self.entries.append(entry)


class _MockUsageTracker:
    """Minimal UsageTracker stub for testing."""

    def __init__(self) -> None:
        self.ticks: dict[str, int] = {}

    def tick(self, key: str) -> None:
        self.ticks[key] = self.ticks.get(key, 0) + 1


class _MockCoordinator:
    """Minimal Coordinator stub for testing."""

    def collect_results(self) -> dict[str, Any]:
        return {"scratchpad": ""}


def _make_hooks(
    enable_dependency_scan: bool = True,
) -> DispatchHooks:
    """Build a DispatchHooks instance with stubs for isolated testing."""
    return DispatchHooks(
        coordinator=_MockCoordinator(),
        enterprise=None,
        quality_guard=None,
        perf_monitor=None,
        anchor_checker=None,
        output_slicer=None,
        scratchpad=_MockScratchpad(),
        usage_tracker=_MockUsageTracker(),
        dispatch_history=[],
        max_history=10,
        enable_quality_guard=False,
        enable_dependency_scan=enable_dependency_scan,
    )


class T1_DispatchHookAutoTriggersScan(unittest.TestCase):
    """T1: post_execution_processing auto-invokes the dependency scan."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.hooks = _make_hooks()

    def test_01_suspicious_package_in_worker_output_detected(self) -> None:
        """Verify: hallucinated package in worker output is detected."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "Here is the implementation:\n"
                    "import huggingface_cli\n"
                    "print('done')\n"
                    "# end of code"
                ),
            }
        ]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["is_clean"])
        self.assertEqual(results[0]["stats"]["suspicious"], 1)

    def test_02_call_counter_increments(self) -> None:
        """Verify: module call counter increments (anti-ghost CI check)."""
        before = get_call_count()
        worker_results = [
            {
                "role_id": "coder",
                "output": "import requests\n# more code here to pass length threshold",
            }
        ]
        self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        after = get_call_count()
        self.assertEqual(after, before + 1)

    def test_03_scratchpad_records_warning(self) -> None:
        """Verify: SUSPICIOUS findings write a scratchpad WARNING entry."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import huggingface_cli\n"
                    "# more code here to pass length threshold"
                ),
            }
        ]
        self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(self.hooks.scratchpad.entries), 1)
        entry = self.hooks.scratchpad.entries[0]
        self.assertIn("Dependency Hallucination", entry.content)
        self.assertIn("huggingface_cli", entry.content)

    def test_04_usage_tracker_ticks_suspicious(self) -> None:
        """Verify: usage tracker records suspicious detection."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import huggingface_cli\n"
                    "# more code here to pass length threshold"
                ),
            }
        ]
        self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertIn(
            "dependency_hallucination_suspicious",
            self.hooks.usage_tracker.ticks,
        )

    def test_05_clean_output_no_scratchpad_noise(self) -> None:
        """Verify: clean code does not write scratchpad entries."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import requests\n"
                    "import numpy\n"
                    "# more code here to pass length threshold"
                ),
            }
        ]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        # Clean output → no scan_results returned (findings are empty)
        self.assertEqual(len(results), 0)
        self.assertEqual(len(self.hooks.scratchpad.entries), 0)


class T2_SkipConditions(unittest.TestCase):
    """T2: Skip conditions prevent unnecessary scans."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.hooks = _make_hooks()

    def test_01_short_output_skipped(self) -> None:
        """Verify: output < 50 chars is skipped (no scan)."""
        worker_results = [
            {"role_id": "coder", "output": "import os\n"}  # 10 chars
        ]
        before = get_call_count()
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 0)
        self.assertEqual(get_call_count(), before)  # no scan → no increment

    def test_02_pure_prose_skipped(self) -> None:
        """Verify: output without code markers is skipped."""
        worker_results = [
            {
                "role_id": "pm",
                "output": (
                    "This is a long prose description without any code markers. "
                    "It discusses requirements and design but contains no imports "
                    "or function definitions whatsoever."
                ),
            }
        ]
        before = get_call_count()
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 0)
        self.assertEqual(get_call_count(), before)

    def test_03_empty_output_skipped(self) -> None:
        """Verify: empty output is skipped."""
        worker_results = [{"role_id": "coder", "output": ""}]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 0)

    def test_04_none_output_skipped(self) -> None:
        """Verify: None output is skipped gracefully."""
        worker_results = [{"role_id": "coder", "output": None}]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 0)


class T3_DisableScanToggle(unittest.TestCase):
    """T3: enable_dependency_scan=False disables the scan entirely."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.hooks = _make_hooks(enable_dependency_scan=False)

    def test_01_disabled_scan_returns_empty(self) -> None:
        """Verify: disabled scan returns empty list."""
        worker_results = [
            {
                "role_id": "coder",
                "output": "import huggingface_cli\n# code here",
            }
        ]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 0)

    def test_02_disabled_scan_no_call_increment(self) -> None:
        """Verify: disabled scan does not increment call counter."""
        before = get_call_count()
        worker_results = [
            {
                "role_id": "coder",
                "output": "import huggingface_cli\n# code here",
            }
        ]
        self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(get_call_count(), before)


class T4_PostExecutionProcessingIntegration(unittest.TestCase):
    """T4: Full post_execution_processing pipeline includes dep scan."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.hooks = _make_hooks()

    def test_01_post_execution_processing_runs_dep_scan(self) -> None:
        """Verify: post_execution_processing triggers dep scan on code output."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import huggingface_cli\n"
                    "# implementation here to reach length threshold"
                ),
            }
        ]
        before = get_call_count()
        # structured_goal=None is fine; anchor_checker is None so it short-circuits
        self.hooks.post_execution_processing(worker_results, structured_goal=None)
        after = get_call_count()
        self.assertGreater(after, before)
        # Scratchpad should have the dependency hallucination warning
        self.assertEqual(len(self.hooks.scratchpad.entries), 1)

    def test_02_post_execution_processing_clean_output(self) -> None:
        """Verify: post_execution_processing handles clean output gracefully."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import requests\n"
                    "# implementation here to reach length threshold"
                ),
            }
        ]
        # Should not raise
        summary, anchor, collection, errors, timing = (
            self.hooks.post_execution_processing(
                worker_results, structured_goal=None
            )
        )
        self.assertIsInstance(errors, list)
        self.assertIn("step8_time", timing)


class T5_MultiWorkerScenarios(unittest.TestCase):
    """T5: Multiple workers with mixed code outputs."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.hooks = _make_hooks()

    def test_01_multiple_workers_one_suspicious(self) -> None:
        """Verify: scan handles multiple workers, flagging only suspicious ones."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import requests\n"
                    "# clean implementation here to reach length threshold"
                ),
            },
            {
                "role_id": "architect",
                "output": (
                    "import huggingface_cli\n"
                    "# suspicious code here to reach length threshold"
                ),
            },
        ]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        # Only the suspicious worker should appear in results (clean is skipped)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["role_id"], "architect")
        self.assertEqual(results[0]["stats"]["suspicious"], 1)

    def test_02_multiple_workers_all_suspicious(self) -> None:
        """Verify: scan handles multiple suspicious workers."""
        worker_results = [
            {
                "role_id": "coder",
                "output": (
                    "import huggingface_cli\n"
                    "# code here to reach length threshold"
                ),
            },
            {
                "role_id": "architect",
                "output": (
                    "import aws-cdk\n"
                    "# code here to reach length threshold"
                ),
            },
        ]
        results = self.hooks.scan_worker_outputs_for_hallucinated_deps(worker_results)
        self.assertEqual(len(results), 2)
        total_suspicious = sum(r["stats"]["suspicious"] for r in results)
        self.assertEqual(total_suspicious, 2)


if __name__ == "__main__":
    unittest.main()
