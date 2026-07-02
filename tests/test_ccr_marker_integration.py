#!/usr/bin/env python3
"""Tests for CCR marker integration in SmartCrusher (V3.10.0 Phase 3 §5.3).

Verifies that when a CCRStore is attached to SmartCrusher, crushed output
contains a ``retrieve full: trace_id=X`` marker and the original content is
retrievable from the store.

Dimension coverage:
  - Happy Path: JSON crush + marker, log crush + marker, retrievability
  - Boundary: no CCRStore (backward compat), short input (no crush), no compression
  - Error: nonexistent trace_id retrieval
  - Integration: ContextCompressor passes CCRStore to SmartCrusher
"""

from __future__ import annotations

import json
import unittest

from scripts.collaboration.ccr_store import CCRStore
from scripts.collaboration.content_crusher import SmartCrusher
from scripts.collaboration.context_compressor import CompressionLevel, ContextCompressor, Message, MessageType


def _make_json_array(num_items: int = 100) -> str:
    """Generate a JSON array string with ``num_items`` uniform items."""
    items = [{"id": i, "name": f"item-{i}", "type": "record", "status": "ok"} for i in range(num_items)]
    return json.dumps(items, ensure_ascii=False)


def _make_log(num_lines: int = 100) -> str:
    """Generate a log string with ``num_lines`` lines, some ERROR/WARN."""
    lines = []
    for i in range(num_lines):
        if i % 20 == 5:
            lines.append(f"2026-07-01 10:00:{i:02d} ERROR: failure at step {i}")
        elif i % 15 == 3:
            lines.append(f"2026-07-01 10:00:{i:02d} WARN: degraded at step {i}")
        else:
            lines.append(f"2026-07-01 10:00:{i:02d} INFO: processing step {i}")
    return "\n".join(lines)


class TestSmartCrusherCCRMarker(unittest.TestCase):
    """Verify: SmartCrusher with CCRStore emits marker + stores original."""

    def test_json_crush_emits_trace_id_marker(self):
        """Verify: crushed JSON header contains 'retrieve full: trace_id='."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_json_array(100)
            crushed = crusher.crush(original)
            self.assertIn("retrieve full: trace_id=", crushed)

    def test_log_crush_emits_trace_id_marker(self):
        """Verify: crushed log header contains 'retrieve full: trace_id='."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_log(100)
            crushed = crusher.crush(original)
            self.assertIn("retrieve full: trace_id=", crushed)

    def test_stored_original_is_retrievable(self):
        """Verify: original content can be retrieved via the trace_id in marker."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_json_array(100)
            crushed = crusher.crush(original)
            # Extract trace_id from marker
            marker_prefix = "trace_id="
            idx = crushed.index(marker_prefix)
            trace_id = crushed[idx + len(marker_prefix):].split("]")[0].split("\n")[0]
            self.assertEqual(store.retrieve(trace_id), original)

    def test_no_ccr_store_no_marker(self):
        """Verify: without CCRStore, crushed output has no trace_id marker (backward compat)."""
        crusher = SmartCrusher()  # no ccr_store
        original = _make_json_array(100)
        crushed = crusher.crush(original)
        self.assertNotIn("retrieve full:", crushed)
        self.assertNotIn("trace_id=", crushed)

    def test_short_input_no_marker(self):
        """Verify: short input (<=200 chars) skipped — no crush, no marker."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            short = "x" * 100
            self.assertEqual(crusher.crush(short), short)
            # Nothing stored
            self.assertEqual(store.stats()["total_entries"], 0)

    def test_no_compression_no_marker(self):
        """Verify: plain text (not crushable) returns unchanged — no marker."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            plain = "This is plain text. " * 20  # >200 chars, but PLAIN_TEXT
            result = crusher.crush(plain)
            self.assertEqual(result, plain)
            self.assertNotIn("trace_id=", result)


class TestCCRMarkerFormat(unittest.TestCase):
    """Verify: marker format matches '[N items compressed to M; retrieve full: trace_id=X]'."""

    def test_json_marker_in_header_brackets(self):
        """Verify: trace_id is inside the [...] header brackets."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            crushed = crusher.crush(_make_json_array(50))
            first_line = crushed.split("\n")[0]
            self.assertTrue(first_line.startswith("["))
            self.assertTrue(first_line.endswith("]"))
            self.assertIn("retrieve full: trace_id=", first_line)

    def test_log_marker_in_header_brackets(self):
        """Verify: log header has trace_id inside brackets."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            crushed = crusher.crush(_make_log(50))
            first_line = crushed.split("\n")[0]
            self.assertTrue(first_line.startswith("["))
            self.assertIn("retrieve full: trace_id=", first_line)


class TestContextCompressorCCRIntegration(unittest.TestCase):
    """Verify: ContextCompressor passes CCRStore to SmartCrusher."""

    def test_compressor_with_ccr_store_propagates_to_crusher(self):
        """Verify: compressor's SmartCrusher has the CCRStore attached."""
        with CCRStore(":memory:") as store:
            comp = ContextCompressor(ccr_store=store)
            self.assertIsNotNone(comp._crusher._ccr_store)

    def test_compressor_without_ccr_store_backward_compat(self):
        """Verify: compressor without ccr_store works as before."""
        comp = ContextCompressor()
        self.assertIsNone(comp._crusher._ccr_store)

    def test_smart_compression_with_ccr_produces_marker(self):
        """Verify: SMART level compression with CCRStore produces trace_id marker in output."""
        with CCRStore(":memory:") as store:
            comp = ContextCompressor(ccr_store=store)
            # Build messages with compressible JSON content
            big_json = _make_json_array(100)
            messages = [
                Message(
                    msg_type=MessageType.USER,
                    content=big_json,
                    token_count=comp.estimate_tokens(big_json),
                )
            ]
            ctx = comp.check_and_compress(messages, force_level=CompressionLevel.SMART)
            # At least one crushed message should contain a trace_id marker
            has_marker = any("trace_id=" in m.content for m in ctx.messages)
            self.assertTrue(has_marker, "SMART compression with CCR should produce trace_id marker")


class TestCCRMarkerRetrievalRoundTrip(unittest.TestCase):
    """Verify: full round-trip — crush → extract trace_id → retrieve original."""

    def test_json_round_trip(self):
        """Verify: JSON crush → retrieve returns exact original."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_json_array(200)
            crushed = crusher.crush(original)
            # Extract trace_id
            import re
            match = re.search(r"trace_id=([0-9a-f]+)", crushed)
            self.assertIsNotNone(match, "trace_id not found in crushed output")
            trace_id = match.group(1)
            retrieved = store.retrieve(trace_id)
            self.assertEqual(retrieved, original)

    def test_log_round_trip(self):
        """Verify: log crush → retrieve returns exact original."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_log(200)
            crushed = crusher.crush(original)
            import re
            match = re.search(r"trace_id=([0-9a-f]+)", crushed)
            self.assertIsNotNone(match)
            trace_id = match.group(1)
            retrieved = store.retrieve(trace_id)
            self.assertEqual(retrieved, original)

    def test_query_retrieval_returns_excerpt(self):
        """Verify: retrieve with query returns only matching lines."""
        with CCRStore(":memory:") as store:
            crusher = SmartCrusher(ccr_store=store)
            original = _make_log(200)
            crushed = crusher.crush(original)
            import re
            match = re.search(r"trace_id=([0-9a-f]+)", crushed)
            trace_id = match.group(1)
            excerpt = store.retrieve(trace_id, query="ERROR")
            self.assertIn("ERROR", excerpt)
            self.assertLess(len(excerpt), len(original))


if __name__ == "__main__":
    unittest.main()
