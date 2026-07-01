#!/usr/bin/env python3
"""
Tests for ContentRouter + SmartCrusher + ContextCompressor SMART integration.

Coverage:
  - Unit: ContentRouter.detect for all 6 content types
  - Unit: SmartCrusher JSON array crushing (constants/keepers/errors)
  - Unit: SmartCrusher log crushing (errors/boundaries/short-skip)
  - Unit: SmartCrusher routing (short-text skip / explicit type)
  - Integration: ContextCompressor SMART level
  - Performance: large JSON/log crush <100ms
  - Edge cases: empty/invalid/small inputs

Spec reference: docs/spec/v3.10.0_spec.md §5.3
"""

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.content_crusher import (  # noqa: E402
    ContentRouter,
    ContentType,
    SmartCrusher,
)
from scripts.collaboration.context_compressor import (  # noqa: E402
    CompressionLevel,
    ContextCompressor,
    Message,
    MessageType,
)


class TestContentRouter(unittest.TestCase):
    """Unit: ContentRouter.detect classifies all 6 content types."""

    def setUp(self):
        self.router = ContentRouter()

    def test_detect_json_array(self):
        """Verify: JSON array is detected as JSON_ARRAY.

        Scenario: text starts with '[' and parses as JSON list.
        Expected: ContentType.JSON_ARRAY.
        """
        text = json.dumps([{"a": 1}, {"a": 2}])
        self.assertEqual(self.router.detect(text), ContentType.JSON_ARRAY)

    def test_detect_log_with_timestamp(self):
        """Verify: timestamped text is detected as LOG."""
        text = "2026-07-01 10:00:00 INFO starting service"
        self.assertEqual(self.router.detect(text), ContentType.LOG)

    def test_detect_log_with_level_keyword(self):
        """Verify: text with log level keyword is detected as LOG."""
        self.assertEqual(self.router.detect("ERROR something failed"), ContentType.LOG)

    def test_detect_code_python(self):
        """Verify: Python code is detected as CODE."""
        self.assertEqual(self.router.detect("def hello():\n    pass"), ContentType.CODE)

    def test_detect_diff(self):
        """Verify: diff text is detected as DIFF."""
        text = "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@"
        self.assertEqual(self.router.detect(text), ContentType.DIFF)

    def test_detect_html(self):
        """Verify: HTML tags are detected as HTML."""
        self.assertEqual(self.router.detect("<div class='x'>hello</div>"), ContentType.HTML)

    def test_detect_plain_text(self):
        """Verify: plain text defaults to PLAIN_TEXT."""
        self.assertEqual(self.router.detect("Hello world"), ContentType.PLAIN_TEXT)

    def test_detect_empty_returns_plain_text(self):
        """Verify: empty string returns PLAIN_TEXT."""
        self.assertEqual(self.router.detect(""), ContentType.PLAIN_TEXT)
        self.assertEqual(self.router.detect("   "), ContentType.PLAIN_TEXT)

    def test_detect_json_object_not_array(self):
        """Verify: JSON object (not array) does not return JSON_ARRAY."""
        text = json.dumps({"key": "value"})
        result = self.router.detect(text)
        self.assertNotEqual(result, ContentType.JSON_ARRAY)

    def test_detect_diff_takes_precedence_over_html(self):
        """Verify: DIFF is checked before HTML (specificity order)."""
        text = "--- a/file.html\n+++ b/file.html"
        self.assertEqual(self.router.detect(text), ContentType.DIFF)


class TestSmartCrusherJson(unittest.TestCase):
    """Unit: SmartCrusher JSON array crushing."""

    def setUp(self):
        self.crusher = SmartCrusher(json_max_representative=3)

    def _make_array(self, n=100, with_error=True):
        items = [{"id": i, "name": "task", "status": "ok"} for i in range(n)]
        if with_error:
            items[n // 2] = {"id": n // 2, "name": "task", "status": "error", "error": "timeout"}
        return json.dumps(items)

    def test_crush_json_array_compresses(self):
        """Verify: large JSON array is compressed."""
        text = self._make_array(100)
        crushed = self.crusher.crush_json_array(text)
        self.assertLess(len(crushed), len(text))

    def test_crush_json_array_includes_summary_header(self):
        """Verify: output includes compression summary header."""
        text = self._make_array(100)
        crushed = self.crusher.crush_json_array(text)
        self.assertIn("100 items compressed to", crushed)

    def test_crush_json_array_preserves_error_item(self):
        """Verify: error items are retained in output."""
        text = self._make_array(100, with_error=True)
        crushed = self.crusher.crush_json_array(text)
        self.assertIn("timeout", crushed)
        self.assertIn("error", crushed)

    def test_crush_json_array_extracts_constant_fields(self):
        """Verify: constant fields are extracted and reported."""
        text = self._make_array(100)
        crushed = self.crusher.crush_json_array(text)
        self.assertIn("constant_fields", crushed)
        self.assertIn('"name": "task"', crushed)

    def test_crush_json_array_small_skipped(self):
        """Verify: arrays with <=5 items are not compressed."""
        text = json.dumps([{"a": 1}, {"a": 2}, {"a": 3}])
        self.assertEqual(self.crusher.crush_json_array(text), text)

    def test_crush_json_array_invalid_json(self):
        """Verify: invalid JSON returns original text unchanged."""
        text = "[not valid json"
        self.assertEqual(self.crusher.crush_json_array(text), text)

    def test_crush_json_array_preserves_first_and_last(self):
        """Verify: first and last items are in keepers."""
        items = [{"id": i, "val": i} for i in range(50)]
        text = json.dumps(items)
        crushed = self.crusher.crush_json_array(text)
        self.assertIn('"id": 0', crushed)
        self.assertIn('"id": 49', crushed)

    def test_crush_json_array_non_list_returns_original(self):
        """Verify: JSON dict (not list) returns original text."""
        text = json.dumps({"key": "value"})
        self.assertEqual(self.crusher.crush_json_array(text), text)


class TestSmartCrusherLog(unittest.TestCase):
    """Unit: SmartCrusher log crushing."""

    def setUp(self):
        self.crusher = SmartCrusher(log_max_context_lines=3)

    def _make_log(self, n=50, with_error=True):
        lines = [f"2026-07-01 10:00:{i:02d} INFO line {i}" for i in range(n)]
        if with_error:
            lines[n // 2] = "2026-07-01 10:25:00 ERROR something failed"
        return "\n".join(lines)

    def test_crush_log_compresses(self):
        """Verify: long log is compressed."""
        text = self._make_log(50)
        crushed = self.crusher.crush_log(text)
        self.assertLess(len(crushed), len(text))

    def test_crush_log_preserves_error_lines(self):
        """Verify: ERROR lines are retained."""
        text = self._make_log(50, with_error=True)
        crushed = self.crusher.crush_log(text)
        self.assertIn("ERROR something failed", crushed)

    def test_crush_log_includes_header(self):
        """Verify: output includes compression summary header."""
        text = self._make_log(50)
        crushed = self.crusher.crush_log(text)
        self.assertIn("log lines compressed to", crushed)

    def test_crush_log_short_skipped(self):
        """Verify: logs with <=20 lines are not compressed."""
        text = self._make_log(10)
        self.assertEqual(self.crusher.crush_log(text), text)

    def test_crush_log_preserves_boundary_lines(self):
        """Verify: first and last lines are retained for context."""
        text = self._make_log(50)
        crushed = self.crusher.crush_log(text)
        self.assertIn("line 0", crushed)
        self.assertIn("line 49", crushed)

    def test_crush_log_warn_lines_preserved(self):
        """Verify: WARN lines are also retained."""
        lines = [f"2026-07-01 10:00:{i:02d} INFO line {i}" for i in range(30)]
        lines[15] = "2026-07-01 10:15:00 WARNING slow query"
        text = "\n".join(lines)
        crushed = self.crusher.crush_log(text)
        self.assertIn("WARNING slow query", crushed)


class TestSmartCrusherRoute(unittest.TestCase):
    """Unit: SmartCrusher.crush routing."""

    def setUp(self):
        self.crusher = SmartCrusher()

    def test_crush_short_text_skipped(self):
        """Verify: text <=200 chars is returned unchanged."""
        text = "short text"
        self.assertEqual(self.crusher.crush(text), text)

    def test_crush_routes_json_automatically(self):
        """Verify: JSON array is routed to crush_json_array."""
        items = [{"id": i, "name": "x"} for i in range(50)]
        text = json.dumps(items)
        crushed = self.crusher.crush(text)
        self.assertIn("items compressed to", crushed)

    def test_crush_routes_log_automatically(self):
        """Verify: log text is routed to crush_log."""
        lines = [f"2026-07-01 10:00:{i:02d} INFO line {i}" for i in range(30)]
        text = "\n".join(lines)
        crushed = self.crusher.crush(text)
        self.assertIn("log lines compressed to", crushed)

    def test_crush_plain_text_unchanged(self):
        """Verify: long plain text without structure is returned unchanged."""
        text = "This is a plain text paragraph. " * 20
        result = self.crusher.crush(text)
        self.assertEqual(result, text)

    def test_crush_with_explicit_content_type(self):
        """Verify: explicit content_type overrides auto-detection."""
        items = [{"id": i} for i in range(50)]
        text = json.dumps(items)
        crushed = self.crusher.crush(text, content_type=ContentType.JSON_ARRAY)
        self.assertIn("items compressed to", crushed)

    def test_crush_explicit_plain_text_skips_crushing(self):
        """Verify: explicit PLAIN_TEXT type skips crushing."""
        items = [{"id": i} for i in range(50)]
        text = json.dumps(items)
        result = self.crusher.crush(text, content_type=ContentType.PLAIN_TEXT)
        self.assertEqual(result, text)


class TestContextCompressorSmartIntegration(unittest.TestCase):
    """Integration: ContextCompressor SMART compression level."""

    def setUp(self):
        self.comp = ContextCompressor()

    def _make_json_msg(self, n=100):
        items = [{"id": i, "name": "task", "status": "ok"} for i in range(n)]
        items[n // 2] = {"id": n // 2, "name": "task", "status": "error", "error": "fail"}
        return Message(role="tool", content=json.dumps(items), msg_type=MessageType.TOOL_RESULT)

    def _make_log_msg(self, n=50):
        lines = [f"2026-07-01 10:00:{i:02d} INFO line {i}" for i in range(n)]
        lines[n // 2] = "2026-07-01 10:25:00 ERROR crash"
        return Message(role="tool", content="\n".join(lines), msg_type=MessageType.TOOL_RESULT)

    def test_smart_level_compresses_messages(self):
        """Verify: SMART level reduces token count."""
        msgs = [self._make_json_msg(100), self._make_log_msg(50)]
        orig = self.comp.estimate_messages_tokens(msgs)
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertLess(result.compressed_token_count, orig)

    def test_smart_level_preserves_message_count(self):
        """Verify: SMART preserves all messages (no pruning)."""
        msgs = [self._make_json_msg(100), self._make_log_msg(50)]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertEqual(len(result.messages), len(msgs))

    def test_smart_level_marks_crushed_metadata(self):
        """Verify: crushed messages are tagged with smart_crushed=True."""
        msgs = [self._make_json_msg(100), Message(role="user", content="short")]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertTrue(result.messages[0].metadata.get("smart_crushed"))
        self.assertIsNone(result.messages[1].metadata.get("smart_crushed"))

    def test_smart_level_short_messages_unchanged(self):
        """Verify: short messages are not crushed."""
        msgs = [Message(role="user", content="hello world")]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertEqual(result.messages[0].content, "hello world")
        self.assertIsNone(result.messages[0].metadata.get("smart_crushed"))

    def test_smart_level_stats_correct(self):
        """Verify: stats report crush count and total."""
        msgs = [self._make_json_msg(100), self._make_log_msg(50), Message(role="user", content="hi")]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertEqual(result.stats["smart_crush_applied"], 2)
        self.assertEqual(result.stats["smart_crush_total"], 3)

    def test_smart_level_preserves_error_in_json(self):
        """Verify: error items survive compression in SMART level."""
        msgs = [self._make_json_msg(100)]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertIn("fail", result.messages[0].content)

    def test_smart_level_preserves_error_in_log(self):
        """Verify: ERROR lines survive compression in SMART level."""
        msgs = [self._make_log_msg(50)]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertIn("ERROR crash", result.messages[0].content)

    def test_smart_level_compression_level_set(self):
        """Verify: result.compression_level is SMART."""
        msgs = [self._make_json_msg(100)]
        result = self.comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        self.assertEqual(result.compression_level, CompressionLevel.SMART)


class TestPerformance(unittest.TestCase):
    """Performance: crush operations complete within 100ms."""

    def test_crush_large_json_under_100ms(self):
        """Verify: crushing 10000-item JSON array completes <100ms."""
        items = [{"id": i, "name": "task", "status": "ok", "data": f"payload-{i}"} for i in range(10000)]
        text = json.dumps(items)
        crusher = SmartCrusher()
        start = time.perf_counter()
        crusher.crush(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100, f"Took {elapsed_ms:.1f}ms")

    def test_crush_large_log_under_100ms(self):
        """Verify: crushing 5000-line log completes <100ms."""
        lines = [f"2026-07-01 10:00:{i % 60:02d} INFO processing line {i}" for i in range(5000)]
        lines[2500] = "2026-07-01 10:41:00 ERROR critical failure"
        text = "\n".join(lines)
        crusher = SmartCrusher()
        start = time.perf_counter()
        crusher.crush(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100, f"Took {elapsed_ms:.1f}ms")

    def test_detect_large_text_under_50ms(self):
        """Verify: content detection on 50KB text completes <50ms."""
        text = "2026-07-01 10:00:00 INFO line\n" * 2000
        router = ContentRouter()
        start = time.perf_counter()
        router.detect(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 50, f"Took {elapsed_ms:.1f}ms")


class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty/None/mixed content."""

    def setUp(self):
        self.crusher = SmartCrusher()
        self.router = ContentRouter()

    def test_detect_none_like_empty(self):
        """Verify: None-like input returns PLAIN_TEXT."""
        self.assertEqual(self.router.detect(""), ContentType.PLAIN_TEXT)

    def test_crush_empty_string(self):
        """Verify: empty string is returned unchanged."""
        self.assertEqual(self.crusher.crush(""), "")

    def test_crush_json_with_mixed_types(self):
        """Verify: JSON array with mixed types (dict + str) is handled."""
        items = [{"id": i} for i in range(40)] + ["string_item"] * 10
        text = json.dumps(items)
        crushed = self.crusher.crush(text)
        # Should not crash; either compressed or returned as-is
        self.assertIsInstance(crushed, str)

    def test_crush_log_with_no_errors(self):
        """Verify: log with no errors still compresses (boundaries only)."""
        lines = [f"2026-07-01 10:00:{i:02d} INFO line {i}" for i in range(50)]
        text = "\n".join(lines)
        crushed = self.crusher.crush_log(text)
        self.assertIn("log lines compressed to", crushed)

    def test_json_constants_with_non_dict_items(self):
        """Verify: constant extraction handles non-dict items gracefully."""
        items = [{"a": 1}, "not_dict", {"a": 1}, 42, {"a": 1}]
        text = json.dumps(items)
        # Should not crash
        crushed = self.crusher.crush_json_array(text)
        self.assertIsInstance(crushed, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
