#!/usr/bin/env python3
"""Tests for Coordinator TokenBudget + CCRStore integration (V3.10.0 Phase 3 §5.4-5.6).

Verifies:
  - Coordinator accepts ``token_budget`` and ``ccr_store`` constructor args.
  - ``get_budget_status()`` returns live counters for dashboard/API.
  - ``_check_token_budget_before_batch()`` triggers SMART on warning,
    FULL_COMPACT on exceed.
  - ``_retrieve_compressed_originals()`` replaces ``devsquad_retrieve``
    markers with original content from CCRStore.
  - Scratchpad ``write_compressed`` / ``read_compressed_entries`` /
    ``get_stats`` / ``clear`` cover the CompressedScratchpadEntry lifecycle.

Dimension coverage:
  - Happy Path: budget status, SMART trigger, retrieve round-trip
  - Boundary: no budget configured (None), no CCRStore (None), empty output
  - Error: unknown trace_id retrieval (returns original marker unchanged)
  - Integration: Coordinator + CCRStore + Scratchpad full round-trip
"""

from __future__ import annotations

import unittest

from scripts.collaboration.ccr_store import CCRStore
from scripts.collaboration.coordinator import Coordinator
from scripts.collaboration.models import (
    CompressedScratchpadEntry,
    TokenBudget,
    WorkerResult,
)
from scripts.collaboration.scratchpad import Scratchpad

# =====================================================================
# Coordinator: TokenBudget integration
# =====================================================================


class TestCoordinatorTokenBudgetInit(unittest.TestCase):
    """Coordinator constructor accepts token_budget + exposes it."""

    def test_coordinator_accepts_token_budget(self) -> None:
        budget = TokenBudget(total_input_budget=50_000, warning_ratio=0.8)
        coord = Coordinator(token_budget=budget, enable_compression=True)
        self.assertIs(coord.token_budget, budget)
        self.assertEqual(coord._used_input_tokens, 0)

    def test_coordinator_without_budget_returns_none_status(self) -> None:
        coord = Coordinator(enable_compression=True)
        self.assertIsNone(coord.get_budget_status())

    def test_coordinator_with_budget_returns_status_dict(self) -> None:
        budget = TokenBudget(total_input_budget=50_000, per_role_input_budget=10_000, warning_ratio=0.8)
        coord = Coordinator(token_budget=budget, enable_compression=True)
        status = coord.get_budget_status()
        assert status is not None
        self.assertEqual(status["total_input_budget"], 50_000)
        self.assertEqual(status["per_role_input_budget"], 10_000)
        self.assertEqual(status["used_input_tokens"], 0)
        self.assertEqual(status["remaining_input_tokens"], 50_000)
        self.assertFalse(status["is_warning"])
        self.assertFalse(status["is_exceeded"])
        self.assertEqual(status["warning_threshold"], 40_000)


class TestCheckTokenBudgetBeforeBatch(unittest.TestCase):
    """``_check_token_budget_before_batch`` enforces warning + exceed thresholds."""

    def test_noop_when_no_budget_configured(self) -> None:
        coord = Coordinator(enable_compression=True)
        # Must not raise.
        coord._check_token_budget_before_batch()
        self.assertEqual(coord._used_input_tokens, 0)

    def test_warning_triggers_smart_compression(self) -> None:
        # budget 1000, warning_ratio 0.8 → warning at 800.
        budget = TokenBudget(total_input_budget=1000, warning_ratio=0.8)
        coord = Coordinator(token_budget=budget, enable_compression=True, smart_compression=True)
        # Inject a large message buffer that exceeds warning threshold.
        from scripts.collaboration.context_compressor import Message, MessageType

        big_text = "x" * 5000  # well above 800-token warning threshold
        coord._message_buffer = [Message(role="w1", content=big_text, msg_type=MessageType.ASSISTANT)]
        coord._check_token_budget_before_batch()
        # After SMART compression the buffer should have been processed.
        # used_input_tokens must be > 0 (estimated from buffer).
        self.assertGreater(coord._used_input_tokens, 0)

    def test_exceed_triggers_full_compact(self) -> None:
        # budget 100, warning_ratio 0.5 → warning at 50, exceed at 100.
        budget = TokenBudget(total_input_budget=100, warning_ratio=0.5)
        coord = Coordinator(token_budget=budget, enable_compression=True)
        from scripts.collaboration.context_compressor import Message, MessageType

        big_text = "y" * 10000  # well above 100-token exceed threshold
        coord._message_buffer = [Message(role="w1", content=big_text, msg_type=MessageType.ASSISTANT)]
        # Must not raise; FULL_COMPACT path should be exercised.
        coord._check_token_budget_before_batch()
        self.assertGreater(coord._used_input_tokens, 0)


# =====================================================================
# Coordinator: CCRStore auto-retrieve
# =====================================================================


class TestCoordinatorRetrieveCompressedOriginals(unittest.TestCase):
    """``_retrieve_compressed_originals`` injects original content into Worker output."""

    def test_no_ccr_store_returns_unchanged(self) -> None:
        coord = Coordinator(enable_compression=True)
        result = WorkerResult(
            worker_id="w1",
            task_id="t1",
            success=True,
            output="some output without markers",
        )
        original_output = result.output
        returned = coord._retrieve_compressed_originals(result)
        self.assertEqual(returned.output, original_output)

    def test_no_marker_in_output_returns_unchanged(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            coord = Coordinator(enable_compression=True, ccr_store=store)
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output="plain output with no retrieve marker",
            )
            original_output = result.output
            returned = coord._retrieve_compressed_originals(result)
            self.assertEqual(returned.output, original_output)

    def test_marker_replaced_with_original_content(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            trace_id = store.store("THE ORIGINAL CONTENT FOR RETRIEVAL")
            coord = Coordinator(enable_compression=True, ccr_store=store)
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output=f"summary with devsquad_retrieve(trace_id={trace_id}) marker",
            )
            returned = coord._retrieve_compressed_originals(result)
            self.assertIn("THE ORIGINAL CONTENT FOR RETRIEVAL", str(returned.output))
            self.assertIn("[Retrieved original", str(returned.output))

    def test_marker_with_query_replaced_with_excerpt(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            original = "line one\nline two important\nline three"
            trace_id = store.store(original)
            coord = Coordinator(enable_compression=True, ccr_store=store)
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output=f"devsquad_retrieve(trace_id={trace_id}, query=\"important\")",
            )
            returned = coord._retrieve_compressed_originals(result)
            # Should contain the matching line.
            self.assertIn("important", str(returned.output))

    def test_empty_output_returns_unchanged(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            coord = Coordinator(enable_compression=True, ccr_store=store)
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output="",
            )
            returned = coord._retrieve_compressed_originals(result)
            self.assertEqual(returned.output, "")

    def test_unknown_trace_id_keeps_marker(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            coord = Coordinator(enable_compression=True, ccr_store=store)
            unknown_id = "0" * 32  # valid hex but not stored
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output=f"devsquad_retrieve(trace_id={unknown_id})",
            )
            returned = coord._retrieve_compressed_originals(result)
            # CCRStore.retrieve returns "" for unknown trace_id, so marker
            # is preserved unchanged (empty original → no replacement).
            self.assertIn(f"trace_id={unknown_id}", str(returned.output))


# =====================================================================
# Scratchpad: CompressedScratchpadEntry lifecycle
# =====================================================================


class TestScratchpadCompressedEntries(unittest.TestCase):
    """Scratchpad ``write_compressed`` / ``read_compressed_entries`` lifecycle."""

    def test_write_compressed_returns_entry(self) -> None:
        sp = Scratchpad()
        entry = sp.write_compressed(
            summary="100 items compressed to 5",
            trace_id="abc123",
            original_size=5000,
            compressed_size=200,
        )
        self.assertIsInstance(entry, CompressedScratchpadEntry)
        self.assertEqual(entry.summary, "100 items compressed to 5")
        self.assertEqual(entry.trace_id, "abc123")
        self.assertEqual(entry.original_size, 5000)
        self.assertEqual(entry.compressed_size, 200)

    def test_read_compressed_entries_returns_list(self) -> None:
        sp = Scratchpad()
        sp.write_compressed(summary="s1", trace_id="t1")
        sp.write_compressed(summary="s2", trace_id="t2")
        entries = sp.read_compressed_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].summary, "s1")
        self.assertEqual(entries[1].summary, "s2")

    def test_read_compressed_entries_empty_initially(self) -> None:
        sp = Scratchpad()
        self.assertEqual(sp.read_compressed_entries(), [])

    def test_get_stats_includes_compressed_count(self) -> None:
        sp = Scratchpad()
        sp.write_compressed(summary="s1", trace_id="t1")
        sp.write_compressed(summary="s2", trace_id="t2")
        stats = sp.get_stats()
        self.assertEqual(stats["compressed_entries_count"], 2)

    def test_clear_resets_compressed_entries(self) -> None:
        sp = Scratchpad()
        sp.write_compressed(summary="s1", trace_id="t1")
        self.assertEqual(len(sp.read_compressed_entries()), 1)
        sp.clear()
        self.assertEqual(sp.read_compressed_entries(), [])
        self.assertEqual(sp.get_stats()["compressed_entries_count"], 0)


# =====================================================================
# Integration: Coordinator + CCRStore + Scratchpad full round-trip
# =====================================================================


class TestCoordinatorCCRStoreScratchpadIntegration(unittest.TestCase):
    """End-to-end: Coordinator wires CCRStore into ContextCompressor and Scratchpad."""

    def test_coordinator_passes_ccr_store_to_compressor(self) -> None:
        with CCRStore(db_path=":memory:") as store:
            coord = Coordinator(enable_compression=True, ccr_store=store)
            assert coord.compressor is not None
            self.assertIs(coord.compressor._ccr_store, store)

    def test_full_round_trip_compress_then_retrieve(self) -> None:
        """Compress JSON via SmartCrusher → store original → retrieve via Coordinator."""
        import json

        with CCRStore(db_path=":memory:") as store:
            coord = Coordinator(enable_compression=True, ccr_store=store)
            # 100-item JSON array triggers crush_json_array.
            items = [{"id": i, "name": f"item-{i}", "type": "record"} for i in range(100)]
            text = json.dumps(items, ensure_ascii=False)
            # Crush via compressor's SmartCrusher so CCRStore is invoked.
            crushed = coord.compressor._crusher.crush(text)  # type: ignore[union-attr]
            self.assertIn("retrieve full: trace_id=", crushed)
            # Extract trace_id from marker.
            import re

            match = re.search(r"trace_id=([a-f0-9]+)", crushed)
            assert match is not None
            trace_id = match.group(1)
            # Simulate a Worker output referencing the trace_id.
            worker_output = f"Summary: see devsquad_retrieve(trace_id={trace_id})"
            result = WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output=worker_output,
            )
            returned = coord._retrieve_compressed_originals(result)
            # The original JSON content must be injected back.
            self.assertIn("item-0", str(returned.output))
            self.assertIn("item-99", str(returned.output))

    def test_scratchpad_records_compressed_entry_for_audit(self) -> None:
        """Scratchpad can store a CompressedScratchpadEntry for audit/dashboard."""
        sp = Scratchpad()
        with CCRStore(db_path=":memory:") as store:
            trace_id = store.store("audit trail original content")
            entry = sp.write_compressed(
                summary="compressed audit trail",
                trace_id=trace_id,
                original_size=5000,
                compressed_size=200,
            )
            self.assertAlmostEqual(entry.reduction_ratio, 0.96, places=2)
            entries = sp.read_compressed_entries()
            self.assertEqual(len(entries), 1)
            # Stats reflect the compressed entry.
            stats = sp.get_stats()
            self.assertEqual(stats["compressed_entries_count"], 1)


# =====================================================================
# Performance: budget status lookup is cheap (dashboard polling path)
# =====================================================================


class TestBudgetStatusPerformance(unittest.TestCase):
    """``get_budget_status`` runs in <1ms — safe for dashboard polling."""

    def test_budget_status_under_1ms(self) -> None:
        import time

        budget = TokenBudget(total_input_budget=100_000, warning_ratio=0.8)
        coord = Coordinator(token_budget=budget, enable_compression=True)
        start = time.perf_counter()
        for _ in range(1000):
            coord.get_budget_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100)  # <0.1ms per call on average


if __name__ == "__main__":
    unittest.main()
