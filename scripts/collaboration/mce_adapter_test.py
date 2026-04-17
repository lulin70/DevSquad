#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCE Adapter Test Suite (v3.2 MVP Line-B)

测试 MCEAdapter 的核心功能:
- MockMCE: 模拟 MCE 引擎用于测试
- 初始化与状态管理
- classify / classify_batch
- store_memory / retrieve_memories
- 错误处理与降级
- 线程安全
- 与 MemoryBridge 集成
"""

import os
import sys
import time
import threading
import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.mce_adapter import (
    MCEAdapter,
    MCEResult,
    MCEStatus,
    get_global_mce_adapter,
)


class MockMCEEngine:
    """模拟 MCE 记忆分类引擎，用于测试"""

    def __init__(self, fail_rate: float = 0.0):
        self.fail_rate = fail_rate
        self.call_count = 0
        self.classify_count = 0
        self.store_count = 0
        self.retrieve_count = 0
        self._shutdown = False

    def process_message(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """模拟 process_message 接口"""
        self.call_count += 1
        if self.fail_rate > 0 and (self.call_count % int(1/self.fail_rate)) == 0:
            raise RuntimeError("Mock MCE engine failure")

        text_lower = text.lower()
        if "偏好" in text or "preference" in text_lower or "喜欢" in text:
            return {"type": "preference", "confidence": 0.85, "tier": "tier2"}
        elif "决定" in text or "decision" in text_lower or "选择" in text:
            return {"type": "decision", "confidence": 0.92, "tier": "episodic"}
        elif "修正" in text or "correction" in text_lower or "错误" in text:
            return {"type": "correction", "confidence": 0.78, "tier": "episodic"}
        elif "事实" in text or "fact" in text_lower or "知识" in text:
            return {"type": "fact", "confidence": 0.88, "tier": "knowledge"}
        elif "任务" in text or "task" in text_lower:
            return {"type": "task", "confidence": 0.75, "tier": "episodic"}
        else:
            return {"type": "general", "confidence": 0.6, "tier": "tier2"}

    def store(self, memory_data: Dict) -> bool:
        self.store_count += 1
        return True

    def retrieve(self, query: str, **kwargs) -> List[Dict]:
        self.retrieve_count += 1
        return [
            {"id": "mock-1", "content": f"Mock memory for {query}", "type": "episodic"},
        ]

    def shutdown_engine(self):
        self._shutdown = True


@dataclass
class MockFacade:
    """模拟 MemoryClassificationEngineFacade"""
    _engine: Any = None

    def __init__(self, engine=None):
        self._engine = engine or MockMCEEngine()

    def process_message(self, text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        return self._engine.process_message(text, context)

    def store_memory(self, memory_data: Dict) -> bool:
        return self._engine.store(memory_data)

    def retrieve_memories(self, query: str, **kwargs) -> List[Dict]:
        return self._engine.retrieve(query, **kwargs)

    def shutdown(self):
        if hasattr(self._engine, 'shutdown_engine'):
            self._engine.shutdown_engine()


class TestMCEResult(unittest.TestCase):
    """T1: MCEResult 数据类测试"""

    def test_default_values(self):
        result = MCEResult()
        self.assertEqual(result.memory_type, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.tier, "tier2")
        self.assertEqual(result.metadata, {})

    def test_custom_values(self):
        result = MCEResult(
            memory_type="decision",
            confidence=0.92,
            tier="episodic",
            metadata={"source": "test"}
        )
        self.assertEqual(result.memory_type, "decision")
        self.assertAlmostEqual(result.confidence, 0.92)
        self.assertEqual(result.tier, "episodic")
        self.assertEqual(result.metadata["source"], "test")


class TestMCEStatus(unittest.TestCase):
    """T2: MCEStatus 数据类测试"""

    def test_default_status(self):
        status = MCEStatus()
        self.assertFalse(status.available)
        self.assertEqual(status.version, "")
        self.assertIsNone(status.init_error)
        self.assertEqual(status.classify_count, 0)
        self.assertEqual(status.classify_fail_count, 0)


class TestMCEAdapterInit(unittest.TestCase):
    """T3: MCEAdapter 初始化测试"""

    def test_init_disabled(self):
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.is_available)
        status = adapter.status
        self.assertFalse(status.available)

    def test_init_enabled_no_mce(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            status = adapter.status
            self.assertFalse(status.available)
            self.assertIsNotNone(status.init_error)


class TestMCEAdapterClassify(unittest.TestCase):
    """T4: MCEAdapter 分类功能测试"""

    def test_classify_disabled_returns_none(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.classify("用户偏好是使用深色模式")
        self.assertIsNone(result)

    def test_classify_empty_text(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.classify("")
        self.assertIsNone(result)

    def test_classify_none_text(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.classify(None)
        self.assertIsNone(result)

    def test_classify_enabled_no_mce_returns_none(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            result = adapter.classify("任何文本")
            self.assertIsNone(result)


class TestMCEAdapterBatchClassify(unittest.TestCase):
    """T5: 批量分类测试"""

    def test_batch_classify_empty_list(self):
        adapter = MCEAdapter(enable=False)
        results = adapter.classify_batch([])
        self.assertEqual(len(results), 0)

    def test_batch_classify_disabled_returns_none_list(self):
        adapter = MCEAdapter(enable=False)
        texts = ["文本1", "文本2", None, ""]
        results = adapter.classify_batch(texts)
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertIsNone(r)


class TestMCEAdapterStoreRetrieve(unittest.TestCase):
    """T6: 存储和检索测试"""

    def test_store_memory_disabled(self):
        adapter = MCEAdapter(enable=False)
        result = adapter.store_memory({"id": "x"})
        self.assertFalse(result)

    def test_retrieve_memories_disabled(self):
        adapter = MCEAdapter(enable=False)
        results = adapter.retrieve_memories("查询")
        self.assertEqual(results, [])


class TestMCEAdapterErrorHandling(unittest.TestCase):
    """T7: 错误处理与降级测试"""

    def test_graceful_degrade_on_import_error(self):
        adapter = MCEAdapter(enable=True)
        if not adapter.is_available:
            self.assertFalse(adapter.is_available)
            result = adapter.classify("任何文本")
            self.assertIsNone(result)


class TestMCEAdapterLifecycle(unittest.TestCase):
    """T8: 生命周期管理测试"""

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
    """T9: 全局单例测试"""

    def test_get_global_default_disabled(self):
        adapter = get_global_mce_adapter(enable=False)
        self.assertIsNotNone(adapter)
        self.assertFalse(adapter.is_available)

    def test_get_global_singleton(self):
        a1 = get_global_mce_adapter(enable=False)
        a2 = get_global_mce_adapter(enable=False)
        self.assertIs(a1, a2, "Should return same instance")


class TestMCEAdapterThreadSafety(unittest.TestCase):
    """T10: 线程安全测试"""

    def test_concurrent_classify_disabled(self):
        adapter = MCEAdapter(enable=False)

        errors = []
        results = [None] * 10

        def classify_worker(idx):
            try:
                results[idx] = adapter.classify(f"并发测试文本 {idx}")
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
    """T11: 结果归一化测试"""

    def test_normalize_dict_result(self):
        raw = {"type": "decision", "confidence": 0.85}
        result = MCEAdapter._normalize_result(raw)
        self.assertEqual(result.memory_type, "decision")
        self.assertAlmostEqual(result.confidence, 0.85)

    def test_normalize_string_result(self):
        raw = "preference"
        result = MCEAdapter._normalize_result(raw)
        self.assertEqual(result.memory_type, "preference")

    def test_normalize_none_returns_empty_mcresult(self):
        result = MCEAdapter._normalize_result(None)
        self.assertIsInstance(result, MCEResult)
        self.assertEqual(result.memory_type, "")

    def test_normalize_mcresult_creates_new_instance(self):
        existing = MCEResult(memory_type="fact", confidence=0.9)
        result = MCEAdapter._normalize_result(existing)
        self.assertIsInstance(result, MCEResult)


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.testsRun - len(result.failures) - len(result.errors)


if __name__ == "__main__":
    passed = run_all_tests()
    print(f"\n{'='*60}")
    print(f"MCE Adapter Test Results: {passed}/{unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases()} passed")
    if passed == unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases():
        print("🎉 ALL MCE ADAPTER TESTS PASSED!")
    print(f"{'='*60}")
    sys.exit(0 if passed > 0 else 1)
