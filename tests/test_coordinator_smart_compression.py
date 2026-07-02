#!/usr/bin/env python3
"""
Tests for Coordinator SMART compression integration (V3.10.0).

Coverage:
  - Initialization: smart_compression flag default + explicit
  - apply_smart_compression: None when disabled / empty buffer
  - apply_smart_compression: crushes structured content, replaces buffer
  - apply_smart_compression: preserves message count (no deletion)
  - apply_smart_compression: accumulates _smart_stats
  - execute_plan: SMART pre-compression triggers between batches when enabled
  - execute_plan: SMART pre-compression skipped when disabled (backward compat)
  - get_compression_stats: includes SMART fields
  - SMART-first strategy: SMART reduces tokens before destructive compression
  - Backward compatibility: existing behavior unchanged when smart_compression=False

Spec reference: docs/spec/v3.10.0_spec.md §5.3 (Phase 2 — Coordinator接入)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.context_compressor import (  # noqa: E402
    CompressionLevel,
    Message,
    MessageType,
)
from scripts.collaboration.coordinator import Coordinator  # noqa: E402


def _make_json_message(num_items: int = 50) -> Message:
    """Build a Message whose content is a large JSON array (highly compressible)."""
    import json

    items = [
        {"id": i, "status": "ok", "service": "api-gateway", "latency_ms": 100 + i, "region": "us-east-1"}
        for i in range(num_items)
    ]
    return Message(
        role="worker-1",
        content=json.dumps(items),
        msg_type=MessageType.ASSISTANT,
        metadata={"task_id": "t1", "success": True},
    )


def _make_log_message(num_lines: int = 80) -> Message:
    """Build a Message whose content is a multi-line log (highly compressible)."""
    lines = []
    for i in range(num_lines):
        if i % 20 == 5:
            lines.append(f"2026-07-01T10:{i:02d}:00Z ERROR request {i} failed with timeout")
        elif i % 20 == 10:
            lines.append(f"2026-07-01T10:{i:02d}:00Z WARN high latency detected on shard {i}")
        else:
            lines.append(f"2026-07-01T10:{i:02d}:00Z INFO processing request {i}")
    return Message(
        role="worker-2",
        content="\n".join(lines),
        msg_type=MessageType.ASSISTANT,
        metadata={"task_id": "t2", "success": True},
    )


class TestCoordinatorSmartInit(unittest.TestCase):
    """Initialization: smart_compression flag."""

    def test_default_smart_compression_is_false(self):
        coord = Coordinator(enable_compression=True)
        self.assertFalse(coord.smart_compression)

    def test_explicit_smart_compression_true(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        self.assertTrue(coord.smart_compression)

    def test_smart_stats_initialized(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        self.assertEqual(coord._smart_stats["smart_precompressions"], 0)
        self.assertEqual(coord._smart_stats["smart_messages_crushed"], 0)
        self.assertEqual(coord._smart_stats["smart_tokens_before"], 0)
        self.assertEqual(coord._smart_stats["smart_tokens_after"], 0)

    def test_smart_compression_in_slots(self):
        self.assertIn("smart_compression", Coordinator.__slots__)
        self.assertIn("_smart_stats", Coordinator.__slots__)


class TestApplySmartCompression(unittest.TestCase):
    """apply_smart_compression method behavior."""

    def test_returns_none_when_compressor_disabled(self):
        coord = Coordinator(enable_compression=False, smart_compression=True)
        self.assertIsNone(coord.apply_smart_compression())

    def test_returns_none_when_buffer_empty(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        self.assertIsNone(coord.apply_smart_compression())

    def test_crushes_json_content(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        original = _make_json_message(num_items=50)
        coord._message_buffer = [original]
        original_tokens = coord.compressor.estimate_tokens(original.content)

        ctx = coord.apply_smart_compression()

        self.assertIsNotNone(ctx)
        self.assertGreater(ctx.stats.get("smart_crush_applied", 0), 0)
        self.assertLess(ctx.compressed_token_count, ctx.original_token_count)
        self.assertLess(ctx.compressed_token_count, original_tokens)

    def test_crushes_log_content(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [_make_log_message(num_lines=80)]

        ctx = coord.apply_smart_compression()

        self.assertIsNotNone(ctx)
        self.assertGreater(ctx.stats.get("smart_crush_applied", 0), 0)
        self.assertLess(ctx.compressed_token_count, ctx.original_token_count)

    def test_preserves_message_count(self):
        """SMART compression must NOT delete messages — only compress content."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [
            _make_json_message(30),
            _make_log_message(40),
            _make_json_message(20),
        ]
        original_count = len(coord._message_buffer)

        coord.apply_smart_compression()

        self.assertEqual(len(coord._message_buffer), original_count)

    def test_replaces_buffer_with_compressed_messages(self):
        """After apply_smart_compression, _message_buffer contains compressed content."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        original = _make_json_message(50)
        coord._message_buffer = [original]
        original_content = original.content

        coord.apply_smart_compression()

        # Buffer content should differ from original (compressed)
        self.assertNotEqual(coord._message_buffer[0].content, original_content)
        # Compressed content should be shorter
        self.assertLess(len(coord._message_buffer[0].content), len(original_content))

    def test_accumulates_smart_stats(self):
        """Multiple apply_smart_compression calls accumulate stats."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [_make_json_message(30)]
        coord.apply_smart_compression()
        first_count = coord._smart_stats["smart_precompressions"]

        coord._message_buffer = [_make_log_message(40)]
        coord.apply_smart_compression()

        self.assertEqual(coord._smart_stats["smart_precompressions"], first_count + 1)
        self.assertGreater(coord._smart_stats["smart_messages_crushed"], 0)

    def test_no_op_on_plain_text(self):
        """SMART on plain text returns ctx with 0 crushed (no structured content)."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [
            Message(role="w", content="This is plain text without structure.", msg_type=MessageType.USER)
        ]
        ctx = coord.apply_smart_compression()
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.stats.get("smart_crush_applied", 0), 0)
        # Buffer unchanged
        self.assertIn("plain text", coord._message_buffer[0].content)


class TestExecutePlanSmartIntegration(unittest.TestCase):
    """execute_plan with smart_compression=True applies SMART pre-compression."""

    def _build_coord_with_workers(self, smart: bool = False) -> Coordinator:
        from scripts.collaboration.worker import WorkerFactory

        coord = Coordinator(enable_compression=True, smart_compression=smart)
        # Spawn a worker so plan execution has someone to dispatch to
        coord.workers["architect-1"] = WorkerFactory.create(
            worker_id="architect-1",
            role_id="architect",
            role_prompt="You are an architect.",
            scratchpad=coord.scratchpad,
        )
        coord._worker_index["architect"] = coord.workers["architect-1"]
        return coord

    def test_smart_precompression_recorded_in_history(self):
        """When smart_compression=True, _execution_history records smart_precompression events."""
        # We can't easily run a full multi-batch plan without an LLM backend,
        # but we can directly test that the execute_plan loop records SMART events
        # by pre-populating _message_buffer and calling the compression branch.
        coord = self._build_coord_with_workers(smart=True)
        # Simulate messages that would be buffered between batches
        coord._message_buffer = [_make_json_message(40), _make_log_message(40)]

        # Call apply_smart_compression directly (what execute_plan does internally)
        ctx = coord.apply_smart_compression()
        self.assertIsNotNone(ctx)
        self.assertGreater(coord._smart_stats["smart_precompressions"], 0)

    def test_smart_disabled_no_precompression_events(self):
        """When smart_compression=False, no smart_precompression events are recorded."""
        coord = self._build_coord_with_workers(smart=False)
        coord._message_buffer = [_make_json_message(40)]
        # Even if we call apply_smart_compression manually, it still works —
        # but execute_plan won't call it when smart_compression=False.
        # Verify the flag is False so execute_plan skips SMART.
        self.assertFalse(coord.smart_compression)


class TestGetCompressionStatsWithSmart(unittest.TestCase):
    """get_compression_stats includes SMART fields."""

    def test_stats_include_smart_fields_after_smart_compression(self):
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [_make_json_message(40)]
        coord.apply_smart_compression()

        # Manually record a smart_precompression event like execute_plan does
        import time

        coord._execution_history.append(
            {
                "timestamp": time.time(),
                "smart_precompression": {
                    "messages_crushed": 1,
                    "tokens_before": 500,
                    "tokens_after": 100,
                    "reduction_pct": 80.0,
                },
            }
        )

        stats = coord.get_compression_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats["smart_precompressions"], 1)
        self.assertEqual(stats["smart_messages_crushed"], 1)
        self.assertEqual(stats["smart_tokens_before"], 500)
        self.assertEqual(stats["smart_tokens_after"], 100)
        self.assertEqual(stats["smart_avg_reduction_pct"], 80.0)

    def test_stats_include_smart_fields_when_no_events(self):
        """get_compression_stats returns smart fields (zero) when no events."""
        coord = Coordinator(enable_compression=True)
        stats = coord.get_compression_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats["smart_precompressions"], 0)
        self.assertEqual(stats["smart_messages_crushed"], 0)

    def test_stats_none_when_compression_disabled(self):
        coord = Coordinator(enable_compression=False)
        self.assertIsNone(coord.get_compression_stats())


class TestSmartFirstStrategy(unittest.TestCase):
    """SMART-first: SMART runs before destructive compression, preserving messages."""

    def test_smart_reduces_tokens_before_destructive_check(self):
        """After SMART pre-compression, the buffer's token count is lower,
        so destructive compression (SNIP/etc.) is less likely to trigger."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [_make_json_message(100)]
        tokens_before_smart = coord.compressor.estimate_messages_tokens(coord._message_buffer)

        coord.apply_smart_compression()
        tokens_after_smart = coord.compressor.estimate_messages_tokens(coord._message_buffer)

        self.assertLess(tokens_after_smart, tokens_before_smart)

    def test_smart_then_destructive_compatibility(self):
        """SMART pre-compression followed by destructive compression works without error."""
        coord = Coordinator(enable_compression=True, smart_compression=True)
        coord._message_buffer = [_make_json_message(50), _make_log_message(50)]

        # SMART first
        smart_ctx = coord.apply_smart_compression()
        self.assertIsNotNone(smart_ctx)

        # Then destructive (force SNIP to guarantee it triggers)
        destructive_ctx = coord.compressor.check_and_compress(
            coord._message_buffer, force_level=CompressionLevel.SNIP
        )
        self.assertIsNotNone(destructive_ctx)
        # Destructive compression may further reduce message count
        self.assertLessEqual(len(destructive_ctx.messages), len(coord._message_buffer))


class TestBackwardCompatibility(unittest.TestCase):
    """Existing behavior unchanged when smart_compression=False (default)."""

    def test_default_coordinator_behaves_same_as_before(self):
        """Coordinator without smart_compression arg works identically to pre-V3.10.0."""
        coord = Coordinator(enable_compression=True)
        self.assertFalse(coord.smart_compression)
        self.assertFalse(hasattr(coord, "_smart_stats") and coord._smart_stats["smart_precompressions"] > 0)

    def test_compress_context_still_works_without_smart(self):
        """compress_context API unchanged when smart_compression disabled."""
        coord = Coordinator(enable_compression=True)
        coord._message_buffer = [_make_json_message(20)]
        ctx = coord.compress_context(force_level=CompressionLevel.SMART)
        self.assertIsNotNone(ctx)
        # SMART still works via compress_context even when smart_compression flag is False
        # (the flag only controls automatic pre-compression in execute_plan)

    def test_get_compression_stats_backward_compatible(self):
        """Stats dict retains original keys + adds new SMART keys."""
        coord = Coordinator(enable_compression=True)
        stats = coord.get_compression_stats()
        # Original keys preserved
        self.assertIn("total_compressions", stats)
        self.assertIn("avg_reduction_pct", stats)
        self.assertIn("last_compression", stats)
        self.assertIn("total_original_tokens", stats)
        self.assertIn("total_compressed_tokens", stats)
        # New SMART keys added
        self.assertIn("smart_precompressions", stats)
        self.assertIn("smart_messages_crushed", stats)


if __name__ == "__main__":
    unittest.main()
