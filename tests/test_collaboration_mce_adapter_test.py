#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCEAdapter Test Suite — CarryMem Integration

Tests MCEAdapter core functionality:
- Initialization & status management
- classify / classify_batch (CarryMem classify_message format)
- store_memory / retrieve_memories
- whoami / check_conflicts
- Error handling & graceful degradation
- Thread safety
- Type mapping (DevSquad ↔ CarryMem)
"""

import os
import sys
import threading
import unittest
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.mce_adapter import (
    MCEAdapter,
    MCEResult,
    MCEStatus,
    get_global_mce_adapter,
    CARRYMEM_TO_DEVOPSQUAD,
    DEVSQUAD_TO_CARRYMEM,
)


class TestTypeMapping(unittest.TestCase):
    """T1: CarryMem ↔ DevSquad type mapping"""

    def test_carrymem_to_devsquad_mapping(self):
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["user_preference"], "knowledge")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["correction"], "correction")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["fact_declaration"], "knowledge")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["decision"], "analysis")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["relationship"], "knowledge")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["task_pattern"], "pattern")
        self.assertEqual(CARRYMEM_TO_DEVOPSQUAD["sentiment_marker"], "semantic")

    def test_devsquad_to_carrymem_mapping(self):
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["knowledge"], "fact_declaration")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["episodic"], "task_pattern")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["semantic"], "sentiment_marker")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["feedback"], "correction")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["pattern"], "task_pattern")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["analysis"], "decision")
        self.assertEqual(DEVSQUAD_TO_CARRYMEM["correction"], "correction")

    def test_roundtrip_mapping_primary(self):
        for ds_type, cm_type in DEVSQUAD_TO_CARRYMEM.items():
            back = CARRYMEM_TO_DEVOPSQUAD.get(cm_type)
            self.assertIsNotNone(back,
                f"No reverse mapping for CarryMem type: {cm_type}")

    def test_all_carrymem_types_have_reverse(self):
        for cm_type in CARRYMEM_TO_DEVOPSQUAD:
            ds_type = CARRYMEM_TO_DEVOPSQUAD[cm_type]
            self.assertIn(ds_type, DEVSQUAD_TO_CARRYMEM,
                f"DevSquad type '{ds_type}' (from CarryMem '{cm_type}') not in DEVSQUAD_TO_CARRYMEM")


class TestMCEResult(unittest.TestCase):
    """T2: MCEResult data class"""

    def test_default_values(self):
        result = MCEResult()
        self.assertEqual(result.memory_type, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.tier, "tier2")
        self.assertEqual(result.metadata, {})

    def test_custom_values(self):
        result = MCEResult(
            memory_type="knowledge",
            confidence=0.92,
            tier="tier3",
            metadata={"carrymem_type": "fact_declaration"}
        )
        self.assertEqual(result.memory_type, "knowledge")
        self.assertAlmostEqual(result.confidence, 0.92)
        self.assertEqual(result.tier, "tier3")
        self.assertEqual(result.metadata["carrymem_type"], "fact_declaration")

    def test_to_dict(self):
        result = MCEResult(memory_type="correction", confidence=0.78)
        d = result.to_dict()
        self.assertEqual(d["type"], "correction")
        self.assertAlmostEqual(d["confidence"], 0.78)


class TestMCEStatus(unittest.TestCase):
    """T3: MCEStatus data class"""

    def test_default_status(self):
        status = MCEStatus()
        self.assertFalse(status.available)
        self.assertEqual(status.version, "")
        self.assertIsNone(status.init_error)


class TestMCEAdapterInit(unittest.TestCase):
    """T4: MCEAdapter initialization"""

    def test_init_disabled(self):
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.is_available)

    def test_init_enabled_no_carrymem(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            status = adapter.status
            self.assertFalse(status.available)
            self.assertIsNotNone(status.init_error)
            self.assertIn("CarryMem", status.init_error)


class TestMCEAdapterClassify(unittest.TestCase):
    """T5: classify with CarryMem unavailable"""

    def test_classify_disabled_returns_none(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.classify("User prefers dark mode")
        self.assertIsNone(result)

    def test_classify_enabled_no_carrymem_returns_none(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            result = adapter.classify("any text")
            self.assertIsNone(result)


class TestMCEAdapterBatchClassify(unittest.TestCase):
    """T6: batch classify"""

    def test_batch_classify_empty_list(self):
        adapter = MCEAdapter(enable=False)
        results = adapter.classify_batch([])
        self.assertEqual(len(results), 0)

    def test_batch_classify_disabled(self):
        adapter = MCEAdapter(enable=False)
        results = adapter.classify_batch(["text1", "text2"])
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsNone(r)


class TestMCEAdapterStoreRetrieve(unittest.TestCase):
    """T7: store and retrieve"""

    def test_store_memory_disabled(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.store_memory({"content": "test"})
        self.assertFalse(result)

    def test_retrieve_memories_disabled(self):
        adapter = MCEAdapter(enable=False)
        results = adapter.retrieve_memories("query")
        self.assertEqual(results, [])


class TestMCEAdapterWhoami(unittest.TestCase):
    """T8: whoami (CarryMem v0.8+)"""

    def test_whoami_disabled(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.whoami()
        self.assertIsNone(result)


class TestMCEAdapterCheckConflicts(unittest.TestCase):
    """T9: check_conflicts (CarryMem v0.8+)"""

    def test_check_conflicts_disabled(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.check_conflicts()
        self.assertEqual(result, [])


class TestMCEAdapterErrorHandling(unittest.TestCase):
    """T10: error handling & graceful degradation"""

    def test_graceful_degrade_on_import_error(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            self.assertIsNone(adapter.classify("any text"))
            self.assertFalse(adapter.store_memory({"content": "x"}))
            self.assertEqual(adapter.retrieve_memories("x"), [])


class TestMCEAdapterLifecycle(unittest.TestCase):
    """T11: lifecycle management"""

    def test_shutdown_disabled(self):
        adapter = MCEAdapter(enable=False)
        adapter.shutdown()
        self.assertFalse(adapter.is_available)

    def test_double_shutdown_safe(self):
        adapter = MCEAdapter(enable=False)
        adapter.shutdown()
        adapter.shutdown()
        self.assertFalse(adapter.is_available)


class TestGlobalMCESingleton(unittest.TestCase):
    """T12: global singleton"""

    def test_get_global_default_disabled(self):
        adapter = get_global_mce_adapter(enable=False)
        self.assertIsNotNone(adapter)
        self.assertFalse(adapter.is_available)

    def test_get_global_singleton(self):
        a1 = get_global_mce_adapter(enable=False)
        a2 = get_global_mce_adapter(enable=False)
        self.assertIs(a1, a2)


class TestMCEAdapterThreadSafety(unittest.TestCase):
    """T13: thread safety"""

    def test_concurrent_classify_disabled(self):
        adapter = MCEAdapter(enable=False)
        errors = []
        results = [None] * 10

        def classify_worker(idx):
            try:
                results[idx] = adapter.classify(f"concurrent test {idx}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=classify_worker, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        for r in results:
            self.assertIsNone(r)


class TestNormalizeResult(unittest.TestCase):
    """T14: result normalization (CarryMem format)"""

    def test_normalize_carrymem_format(self):
        raw = {
            "should_remember": True,
            "entries": [
                {"type": "user_preference", "confidence": 0.85, "tier": 2, "content": "dark mode"}
            ],
        }
        result = MCEAdapter._normalize_result(raw)
        self.assertEqual(result.memory_type, "knowledge")
        self.assertAlmostEqual(result.confidence, 0.85)
        self.assertEqual(result.tier, "tier2")
        self.assertEqual(result.metadata.get("carrymem_type"), "user_preference")

    def test_normalize_carrymem_decision(self):
        raw = {
            "should_remember": True,
            "entries": [
                {"type": "decision", "confidence": 0.92, "tier": 3}
            ],
        }
        result = MCEAdapter._normalize_result(raw)
        self.assertEqual(result.memory_type, "analysis")

    def test_normalize_carrymem_no_entries(self):
        raw = {"should_remember": False, "entries": []}
        result = MCEAdapter._normalize_result(raw)
        self.assertEqual(result.memory_type, "general")

    def test_normalize_none_returns_empty(self):
        result = MCEAdapter._normalize_result(None)
        self.assertIsInstance(result, MCEResult)
        self.assertEqual(result.memory_type, "")

    def test_normalize_string_maps_type(self):
        result = MCEAdapter._normalize_result("correction")
        self.assertEqual(result.memory_type, "correction")

    def test_normalize_string_unknown_type(self):
        result = MCEAdapter._normalize_result("unknown_type")
        self.assertEqual(result.memory_type, "unknown_type")


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.testsRun - len(result.failures) - len(result.errors)


if __name__ == "__main__":
    passed = run_all_tests()
    total = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases()
    print(f"\n{'='*60}")
    print(f"MCEAdapter Test Results: {passed}/{total} passed")
    if passed == total:
        print("ALL MCE ADAPTER TESTS PASSED!")
    print(f"{'='*60}")
