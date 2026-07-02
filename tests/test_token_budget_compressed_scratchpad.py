#!/usr/bin/env python3
"""Tests for V3.10.0 Phase 3 models: TokenBudget + CompressedScratchpadEntry.

Covers spec docs/spec/v3.10.0_spec.md §5.5 (TokenBudget) and §5.6
(CompressedScratchpadEntry).

Dimension coverage (per Testing Iron Rule 3):
  - Happy Path: default/custom construction, threshold logic, serialization
  - Boundary: zero budget, ratio 0.0/1.0, exactly-at-threshold, over-budget
  - Error: negative usage clamped, empty/missing dict fields
  - Performance: threshold check completes in <1ms
"""

from __future__ import annotations

import time
import unittest

from scripts.collaboration.models import CompressedScratchpadEntry, TokenBudget


class TestTokenBudgetDefaults(unittest.TestCase):
    """Verify: default construction matches spec §5.5."""

    def test_default_values_match_spec(self):
        """Verify: spec-mandated defaults are total=100k, per_role=20k, output=10k, ratio=0.8."""
        budget = TokenBudget()
        self.assertEqual(budget.total_input_budget, 100_000)
        self.assertEqual(budget.per_role_input_budget, 20_000)
        self.assertEqual(budget.output_budget, 10_000)
        self.assertAlmostEqual(budget.warning_ratio, 0.8)

    def test_custom_values_override_defaults(self):
        """Verify: all four fields accept custom values."""
        budget = TokenBudget(
            total_input_budget=50_000,
            per_role_input_budget=8_000,
            output_budget=4_000,
            warning_ratio=0.9,
        )
        self.assertEqual(budget.total_input_budget, 50_000)
        self.assertEqual(budget.per_role_input_budget, 8_000)
        self.assertEqual(budget.output_budget, 4_000)
        self.assertAlmostEqual(budget.warning_ratio, 0.9)


class TestTokenBudgetWarningThreshold(unittest.TestCase):
    """Verify: warning_threshold = int(total * ratio)."""

    def test_warning_threshold_default(self):
        """Verify: 100_000 * 0.8 = 80_000."""
        budget = TokenBudget()
        self.assertEqual(budget.warning_threshold(), 80_000)

    def test_warning_threshold_custom_ratio(self):
        """Verify: 50_000 * 0.9 = 45_000."""
        budget = TokenBudget(total_input_budget=50_000, warning_ratio=0.9)
        self.assertEqual(budget.warning_threshold(), 45_000)

    def test_warning_threshold_ratio_zero(self):
        """Verify: ratio 0.0 → threshold 0 (warn immediately on any usage)."""
        budget = TokenBudget(total_input_budget=50_000, warning_ratio=0.0)
        self.assertEqual(budget.warning_threshold(), 0)

    def test_warning_threshold_ratio_one(self):
        """Verify: ratio 1.0 → threshold equals budget (warn only at limit)."""
        budget = TokenBudget(total_input_budget=50_000, warning_ratio=1.0)
        self.assertEqual(budget.warning_threshold(), 50_000)


class TestTokenBudgetIsWarning(unittest.TestCase):
    """Verify: is_warning triggers at threshold, not below."""

    def test_is_warning_true_at_threshold(self):
        """Verify: usage == threshold → warning True."""
        budget = TokenBudget()
        self.assertTrue(budget.is_warning(80_000))

    def test_is_warning_true_above_threshold(self):
        """Verify: usage > threshold → warning True."""
        budget = TokenBudget()
        self.assertTrue(budget.is_warning(90_000))

    def test_is_warning_false_below_threshold(self):
        """Verify: usage < threshold → warning False."""
        budget = TokenBudget()
        self.assertFalse(budget.is_warning(79_999))

    def test_is_warning_false_zero_usage(self):
        """Verify: 0 usage → warning False."""
        budget = TokenBudget()
        self.assertFalse(budget.is_warning(0))


class TestTokenBudgetIsExceeded(unittest.TestCase):
    """Verify: is_exceeded triggers at hard limit."""

    def test_is_exceeded_true_at_limit(self):
        """Verify: usage == budget → exceeded True."""
        budget = TokenBudget()
        self.assertTrue(budget.is_exceeded(100_000))

    def test_is_exceeded_true_above_limit(self):
        """Verify: usage > budget → exceeded True."""
        budget = TokenBudget()
        self.assertTrue(budget.is_exceeded(150_000))

    def test_is_exceeded_false_below_limit(self):
        """Verify: usage < budget → exceeded False."""
        budget = TokenBudget()
        self.assertFalse(budget.is_exceeded(99_999))


class TestTokenBudgetRoleExceeded(unittest.TestCase):
    """Verify: is_role_exceeded checks per-role budget."""

    def test_role_exceeded_true_at_limit(self):
        budget = TokenBudget(per_role_input_budget=20_000)
        self.assertTrue(budget.is_role_exceeded(20_000))

    def test_role_exceeded_false_below_limit(self):
        budget = TokenBudget(per_role_input_budget=20_000)
        self.assertFalse(budget.is_role_exceeded(19_999))


class TestTokenBudgetRemaining(unittest.TestCase):
    """Verify: remaining = max(0, budget - used)."""

    def test_remaining_normal(self):
        """Verify: 100_000 - 30_000 = 70_000."""
        budget = TokenBudget()
        self.assertEqual(budget.remaining(30_000), 70_000)

    def test_remaining_zero_at_limit(self):
        """Verify: at-limit → 0 remaining."""
        budget = TokenBudget()
        self.assertEqual(budget.remaining(100_000), 0)

    def test_remaining_clamped_when_over_budget(self):
        """Verify: over-budget → 0 (never negative)."""
        budget = TokenBudget()
        self.assertEqual(budget.remaining(150_000), 0)


class TestTokenBudgetZeroBudgetBoundary(unittest.TestCase):
    """Verify: zero-budget boundary behaves safely."""

    def test_zero_budget_warning_immediately(self):
        """Verify: 0 budget → threshold 0 → any usage warns."""
        budget = TokenBudget(total_input_budget=0, warning_ratio=0.8)
        self.assertEqual(budget.warning_threshold(), 0)
        self.assertTrue(budget.is_warning(0))
        self.assertTrue(budget.is_exceeded(0))

    def test_zero_budget_remaining_zero(self):
        budget = TokenBudget(total_input_budget=0)
        self.assertEqual(budget.remaining(0), 0)


class TestTokenBudgetSerialization(unittest.TestCase):
    """Verify: to_dict round-trips all four fields."""

    def test_to_dict_contains_all_fields(self):
        budget = TokenBudget(
            total_input_budget=50_000,
            per_role_input_budget=8_000,
            output_budget=4_000,
            warning_ratio=0.9,
        )
        data = budget.to_dict()
        self.assertEqual(data["total_input_budget"], 50_000)
        self.assertEqual(data["per_role_input_budget"], 8_000)
        self.assertEqual(data["output_budget"], 4_000)
        self.assertAlmostEqual(data["warning_ratio"], 0.9)

    def test_to_dict_default_budget(self):
        budget = TokenBudget()
        data = budget.to_dict()
        self.assertEqual(len(data), 4)
        self.assertEqual(data["total_input_budget"], 100_000)


class TestTokenBudgetPerformance(unittest.TestCase):
    """Verify: threshold checks complete in <1ms (called per-Worker in hot path)."""

    def test_is_warning_fast(self):
        """Verify: 1000 is_warning calls complete in <50ms total."""
        budget = TokenBudget()
        start = time.perf_counter()
        for i in range(1000):
            budget.is_warning(i * 100)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 50, f"is_warning too slow: {elapsed_ms:.2f}ms")


# ============================================================
# CompressedScratchpadEntry
# ============================================================


class TestCompressedScratchpadEntryConstruction(unittest.TestCase):
    """Verify: construction with required + optional fields."""

    def test_required_fields_only(self):
        """Verify: summary + trace_id required; others default."""
        entry = CompressedScratchpadEntry(summary="compressed", trace_id="abc123")
        self.assertEqual(entry.summary, "compressed")
        self.assertEqual(entry.trace_id, "abc123")
        self.assertEqual(entry.original_size, 0)
        self.assertEqual(entry.compressed_size, 0)
        self.assertIsNotNone(entry.created_at)

    def test_full_construction(self):
        """Verify: all fields set."""
        entry = CompressedScratchpadEntry(
            summary="[1000 items → 20; trace_id=abc]",
            trace_id="abc",
            original_size=15_000,
            compressed_size=60,
        )
        self.assertEqual(entry.summary, "[1000 items → 20; trace_id=abc]")
        self.assertEqual(entry.trace_id, "abc")
        self.assertEqual(entry.original_size, 15_000)
        self.assertEqual(entry.compressed_size, 60)


class TestCompressedScratchpadEntryReductionRatio(unittest.TestCase):
    """Verify: reduction_ratio = 1 - compressed/original."""

    def test_reduction_ratio_normal(self):
        """Verify: 15000 original, 60 compressed → 0.996 ratio."""
        entry = CompressedScratchpadEntry(
            summary="x", trace_id="t", original_size=15_000, compressed_size=60
        )
        self.assertAlmostEqual(entry.reduction_ratio, 0.996, places=3)

    def test_reduction_ratio_zero_original(self):
        """Verify: original_size=0 → ratio 0.0 (avoid div-by-zero)."""
        entry = CompressedScratchpadEntry(summary="x", trace_id="t", original_size=0)
        self.assertEqual(entry.reduction_ratio, 0.0)

    def test_reduction_ratio_full_compression(self):
        """Verify: compressed_size=0 → ratio 1.0 (everything removed)."""
        entry = CompressedScratchpadEntry(
            summary="", trace_id="t", original_size=10_000, compressed_size=0
        )
        self.assertAlmostEqual(entry.reduction_ratio, 1.0)

    def test_reduction_ratio_no_compression(self):
        """Verify: compressed == original → ratio 0.0."""
        entry = CompressedScratchpadEntry(
            summary="x" * 100, trace_id="t", original_size=100, compressed_size=100
        )
        self.assertAlmostEqual(entry.reduction_ratio, 0.0)


class TestCompressedScratchpadEntrySerialization(unittest.TestCase):
    """Verify: to_dict / from_dict round-trip."""

    def test_to_dict_contains_all_fields(self):
        entry = CompressedScratchpadEntry(
            summary="compressed summary",
            trace_id="trace-001",
            original_size=5000,
            compressed_size=50,
        )
        data = entry.to_dict()
        self.assertEqual(data["summary"], "compressed summary")
        self.assertEqual(data["trace_id"], "trace-001")
        self.assertEqual(data["original_size"], 5000)
        self.assertEqual(data["compressed_size"], 50)
        self.assertIn("created_at", data)

    def test_from_dict_roundtrip(self):
        """Verify: from_dict(to_dict(entry)) preserves all fields."""
        original = CompressedScratchpadEntry(
            summary="round-trip",
            trace_id="rt-001",
            original_size=8000,
            compressed_size=80,
        )
        data = original.to_dict()
        restored = CompressedScratchpadEntry.from_dict(data)
        self.assertEqual(restored.summary, original.summary)
        self.assertEqual(restored.trace_id, original.trace_id)
        self.assertEqual(restored.original_size, original.original_size)
        self.assertEqual(restored.compressed_size, original.compressed_size)
        self.assertEqual(restored.created_at, original.created_at)

    def test_from_dict_missing_created_at(self):
        """Verify: missing created_at → defaults to now (graceful)."""
        data = {"summary": "s", "trace_id": "t", "original_size": 100, "compressed_size": 10}
        entry = CompressedScratchpadEntry.from_dict(data)
        self.assertEqual(entry.summary, "s")
        self.assertEqual(entry.trace_id, "t")
        self.assertIsNotNone(entry.created_at)

    def test_from_dict_empty_dict(self):
        """Verify: empty dict → defaults (summary/trace_id empty strings)."""
        entry = CompressedScratchpadEntry.from_dict({})
        self.assertEqual(entry.summary, "")
        self.assertEqual(entry.trace_id, "")
        self.assertEqual(entry.original_size, 0)
        self.assertEqual(entry.compressed_size, 0)


class TestCompressedScratchpadEntryMarkerFormat(unittest.TestCase):
    """Verify: summary can carry the CCR marker convention."""

    def test_marker_format(self):
        """Verify: summary follows '[N items compressed to M; retrieve full: trace_id=X]'."""
        trace_id = "abc123"
        summary = f"[1000 items compressed to 20; retrieve full: trace_id={trace_id}]"
        entry = CompressedScratchpadEntry(
            summary=summary, trace_id=trace_id, original_size=15_000, compressed_size=len(summary)
        )
        self.assertIn(trace_id, entry.summary)
        self.assertIn("retrieve full:", entry.summary)
        self.assertGreater(entry.original_size, entry.compressed_size)


if __name__ == "__main__":
    unittest.main()
