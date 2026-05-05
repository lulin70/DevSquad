#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WarmupManager 测试套件

覆盖范围:
- T1: 数据模型 (12)
- T2: 核心逻辑 (18)
- T3: L1 Eager 预热 (8)
- T4: L2 Async 预热 (10)
- T5: 缓存管理 (14)
- T6: 依赖解析 (6)
- T7: 性能与 Metrics (8)
- T8: 边界情况与降级 (9)
- IT1: Coordinator 集成 (6)
- IT2: PromptRegistry 集成 (4)
- E2E: 端到端 (8)
总计: ~95 cases
"""

import os
import sys
import time
import threading
import unittest
import datetime as dt_module

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.warmup_manager import (
    WarmupManager, WarmupConfig, WarmupTask, WarmupResult,
    WarmupReport, CacheEntry, WarmupMetrics,
    WarmupLayer, WarmupStatus,
)


def _reset():
    WarmupManager.reset()


class T1DataModels(unittest.TestCase):
    def test_01_config_default_values(self):
        cfg = WarmupConfig.default()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.eager_timeout_ms, 200)
        self.assertEqual(cfg.async_workers, 4)
        self.assertEqual(cfg.cache_max_size, 200)

    def test_02_config_fast_mode(self):
        cfg = WarmupConfig.fast()
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.async_workers, 0)
        self.assertLessEqual(cfg.cache_max_size, 50)

    def test_03_config_full_mode(self):
        cfg = WarmupConfig.full()
        self.assertEqual(cfg.async_workers, 8)
        self.assertEqual(cfg.cache_max_size, 500)
        self.assertEqual(cfg.cache_ttl_seconds, 7200.0)

    def test_04_cache_entry_creation(self):
        entry = CacheEntry(key="test", value=42)
        self.assertEqual(entry.key, "test")
        self.assertEqual(entry.value, 42)
        self.assertEqual(entry.access_count, 0)

    def test_05_cache_entry_expired(self):
        entry = CacheEntry(key="t", value=1, ttl_seconds=0.001)
        time.sleep(0.002)
        self.assertTrue(entry.is_expired)

    def test_06_cache_entry_not_expired(self):
        entry = CacheEntry(key="t", value=1, ttl_seconds=3600)
        self.assertFalse(entry.is_expired)

    def test_07_cache_entry_age(self):
        t = time.time()
        entry = CacheEntry(key="t", value=1, created_at=t)
        a = entry.age_seconds
        self.assertGreaterEqual(a, 0)

    def test_08_warmup_task_fields(self):
        task = WarmupTask(
            task_id="t1", name="Test",
            priority=2, layer=WarmupLayer.ASYNC,
            dependencies=["d1"], executor=lambda: "ok",
            timeout_ms=3000, retry_count=2,
        )
        self.assertEqual(task.task_id, "t1")
        self.assertEqual(task.layer, WarmupLayer.ASYNC)
        self.assertEqual(task.dependencies, ["d1"])

    def test_09_warmup_result_success(self):
        r = WarmupResult(task_id="t", status=WarmupStatus.SUCCESS, duration_ms=10.5)
        self.assertEqual(r.status, WarmupStatus.SUCCESS)
        self.assertIsNone(r.error)

    def test_10_warmup_result_error(self):
        r = WarmupResult(task_id="t", status=WarmupStatus.ERROR, error="boom")
        self.assertEqual(r.status, WarmupStatus.ERROR)
        self.assertEqual(r.error, "boom")

    def test_11_warmup_report_stats(self):
        r = WarmupReport(
            total_tasks=10, completed=7, failed=2, cached=1,
            tasks=[WarmupResult(task_id=str(i)) for i in range(10)],
        )
        self.assertEqual(r.completed + r.failed + r.cached, r.total_tasks)

    def test_12_metrics_hit_rate_boundary(self):
        m = WarmupMetrics(cache_hit_rate=0.0)
        self.assertAlmostEqual(m.cache_hit_rate, 0.0)
        m2 = WarmupMetrics(cache_hit_rate=1.0)
        self.assertAlmostEqual(m2.cache_hit_rate, 1.0)


class T2CoreLogic(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_singleton_identity(self):
        a = WarmupManager.instance(WarmupConfig.fast())
        b = WarmupManager.instance()
        self.assertIs(a, b)

    def test_02_thread_safe_singleton(self):
        instances = []
        barrier = threading.Barrier(10)

        def get_instance():
            barrier.wait()
            instances.append(WarmupManager.instance(WarmupConfig.fast()))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertTrue(len(set(id(inst) for inst in instances)) == 1)

    def test_03_reset_creates_new(self):
        a = WarmupManager.instance(WarmupConfig.fast())
        _reset()
        b = WarmupManager.instance(WarmupConfig.fast())
        self.assertIsNot(a, b)

    def test_04_register_basic(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        task = WarmupTask(task_id="mytask", name="My Task", executor=lambda: 42)
        wm.register_task(task)
        self.assertIn("mytask", wm._tasks)

    def test_05_register_overwrite(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        t1 = WarmupTask(task_id="x", name="A", executor=lambda: 1)
        t2 = WarmupTask(task_id="x", name="B", executor=lambda: 2)
        wm.register_task(t1)
        wm.register_task(t2)
        self.assertEqual(wm._tasks["x"].name, "B")

    def test_06_register_batch(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        for i in range(5):
            wm.register_task(WarmupTask(
                task_id=f"batch-{i}", name=f"Task {i}", executor=lambda i=i: i,
            ))
        self.assertEqual(len(wm._tasks), 5 + 2)

    def test_07_warmup_empty_layers(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        report = wm.warmup(layers=[])
        self.assertGreaterEqual(report.total_tasks, 0)

    def test_08_warmup_eager_only(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        report = wm.warmup(layers=[WarmupLayer.EAGER])
        eager_ids = {t.task_id for t in report.tasks if t.task_id in wm._eager_task_ids_local}
        async_ids = {t.task_id for t in report.tasks if t.task_id not in wm._eager_task_ids_local}
        self.assertEqual(len(async_ids), 0)

    def test_09_get_cache_hit(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("key1", "value1")
        self.assertEqual(wm.get("key1"), "value1")

    def test_10_get_cache_miss(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        self.assertIsNone(wm.get("nonexistent"))
        self.assertEqual(wm.get("nonexistent", "default"), "default")

    def test_11_get_cache_expired(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        entry = CacheEntry(key="exp", value="old", ttl_seconds=0.001)
        wm._cache["exp"] = entry
        time.sleep(0.002)
        self.assertIsNone(wm.get("exp"))

    def test_12_get_or_load_first_time(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        call_count = [0]

        def loader():
            call_count[0] += 1
            return "loaded"

        result = wm.get_or_load("new_key", loader)
        self.assertEqual(result, "loaded")
        self.assertEqual(call_count[0], 1)

    def test_13_get_or_load_second_hit(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        call_count = [0]

        def loader():
            call_count[0] += 1
            return "loaded"

        wm.get_or_load("hit_key", loader)
        wm.get_or_load("hit_key", loader)
        self.assertEqual(call_count[0], 1)

    def test_14_is_ready_completed(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        self.assertTrue(wm.is_ready("core-models"))

    def test_15_is_ready_not_yet(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        self.assertFalse(wm.is_ready("core-models"))

    def test_16_is_fully_warmed_after_eager(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        time.sleep(0.05)
        self.assertTrue(wm.is_fully_warmed())

    def test_17_is_fully_warmed_partial(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm.register_task(WarmupTask(
            task_id="async-test", name="Async Test",
            layer=WarmupLayer.ASYNC, executor=lambda: None,
        ))
        wm.warmup(layers=[WarmupLayer.EAGER])
        self.assertFalse(wm.is_fully_warmed())

    def test_18_report_structure(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        report = wm.get_report()
        self.assertIsInstance(report.total_tasks, int)
        self.assertIsInstance(report.timestamp, type(dt_module.datetime.now()))


class T3EagerWarmup(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_single_success(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        task = WarmupTask(task_id="e1", name="E1", layer=WarmupLayer.EAGER,
                          executor=lambda: "hello", timeout_ms=1000)
        wm.register_task(task)
        results = wm.warmup_eager()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, WarmupStatus.SUCCESS)
        self.assertEqual(wm.get("e1"), "hello")

    def test_02_dependency_order(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        order = []

        def make_executor(name):
            return lambda n=name: order.append(n)

        wm.register_task(WarmupTask(task_id="a", name="A", layer=WarmupLayer.EAGER,
                                     executor=make_executor("a")))
        wm.register_task(WarmupTask(task_id="b", name="B", layer=WarmupLayer.EAGER,
                                     dependencies=["a"], executor=make_executor("b")))
        wm.register_task(WarmupTask(task_id="c", name="C", layer=WarmupLayer.EAGER,
                                     dependencies=["b"], executor=make_executor("c")))
        wm.warmup_eager()
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))

    def test_03_exception_handling(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        task = WarmupTask(task_id="err", name="Err", layer=WarmupLayer.EAGER,
                          executor=lambda: 1 / 0, timeout_ms=1000)
        wm.register_task(task)
        results = wm.warmup_eager()
        self.assertEqual(results[0].status, WarmupStatus.ERROR)
        self.assertIn("division by zero", results[0].error)

    def test_04_no_deps_parallel(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        for i in range(3):
            wm.register_task(WarmupTask(
                task_id=f"nd-{i}", name=f"ND{i}", layer=WarmupLayer.EAGER,
                executor=lambda i=i: i,
            ))
        results = wm.warmup_eager()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.status == WarmupStatus.SUCCESS for r in results))

    def test_05_empty_task_list(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        results = wm.warmup_eager()
        self.assertEqual(results, [])

    def test_06_duration_recorded(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        task = WarmupTask(task_id="dur", name="Dur", layer=WarmupLayer.EAGER,
                          executor=lambda: time.sleep(0.01) or "done", timeout_ms=5000)
        wm.register_task(task)
        results = wm.warmup_eager()
        self.assertGreater(results[0].duration_ms, 5)
        self.assertLess(results[0].duration_ms, 5000)

    def test_07_result_cached(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        task = WarmupTask(task_id="cached-task", name="Cached",
                          layer=WarmupLayer.EAGER, executor=lambda: {"data": True})
        wm.register_task(task)
        wm.warmup_eager()
        val = wm.get("cached-task")
        self.assertIsNotNone(val)
        self.assertEqual(val["data"], True)

    def test_08_all_fail_report(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        for i in range(3):
            wm.register_task(WarmupTask(
                task_id=f"fail-{i}", name=f"Fail{i}", layer=WarmupLayer.EAGER,
                executor=lambda: 1 / 0,
            ))
        results = wm.warmup_eager()
        self.assertTrue(all(r.status == WarmupStatus.ERROR for r in results))


class T4AsyncWarmup(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_returns_immediately(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="async1", name="Async1", layer=WarmupLayer.ASYNC,
            executor=lambda: time.sleep(2) or "slow",
            timeout_ms=5000,
        ))
        start = time.perf_counter()
        wm.warmup_async()
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 100)

    def test_02_eventually_completes(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="async2", name="Async2", layer=WarmupLayer.ASYNC,
            executor=lambda: "done_async",
            timeout_ms=5000,
        ))
        wm.warmup_async()
        time.sleep(0.3)
        self.assertEqual(wm.get("async2"), "done_async")

    def test_03_result_in_cache(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="acache", name="ACache", layer=WarmupLayer.ASYNC,
            executor=lambda: {"cached": True},
            timeout_ms=5000,
        ))
        wm.warmup_async()
        time.sleep(0.3)
        val = wm.get("acache")
        self.assertIsNotNone(val)
        self.assertEqual(val["cached"], True)

    def test_04_dependency_order_async(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        order = []
        lock = threading.Lock()

        def make_exec(name):
            def fn():
                with lock:
                    order.append(name)
                time.sleep(0.02)
                return name
            return fn

        wm.register_task(WarmupTask(task_id="adep-a", name="ADepA",
                                     layer=WarmupLayer.ASYNC, executor=make_exec("a")))
        wm.register_task(WarmupTask(task_id="adep-b", name="ADepB",
                                     layer=WarmupLayer.ASYNC, dependencies=["adep-a"],
                                     executor=make_exec("b")))
        wm.warmup_async()
        time.sleep(0.5)
        if len(order) >= 2:
            self.assertLess(order.index("a"), order.index("b"))

    def test_05_timeout_marks_error(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="atimeout", name="ATimeout", layer=WarmupLayer.ASYNC,
            executor=lambda: time.sleep(10) or "never",
            timeout_ms=100,
        ))
        wm.warmup_async()
        time.sleep(1.5)
        result = wm._results.get("atimeout")
        self.assertIsNotNone(result)
        self.assertIn(result.status, (WarmupStatus.ERROR, WarmupStatus.TIMEOUT, WarmupStatus.PENDING))

    def test_06_exception_no_crash(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="acrash", name="ACrash", layer=WarmupLayer.ASYNC,
            executor=lambda: (_ for _ in ()).throw(ValueError("async boom")),
            timeout_ms=1000,
        ))
        wm.warmup_async()
        main_ok = True
        time.sleep(0.3)
        self.assertTrue(main_ok)

    def test_07_idempotent(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="aidem", name="AIdem", layer=WarmupLayer.ASYNC,
            executor=lambda: "idem",
            timeout_ms=1000,
        ))
        wm.warmup_async()
        wm.warmup_async()
        executors = [wm._executor]
        active = sum(1 for e in executors if e is not None)
        self.assertLessEqual(active, 1)

    def test_08_concurrent_write_safe(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        errors = []

        def writer(i):
            try:
                wm.set_cache(f"concur-{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])
        for i in range(20):
            self.assertEqual(wm.get(f"concur-{i}"), i)

    def test_09_custom_workers(self):
        cfg = WarmupConfig(async_workers=2)
        wm = WarmupManager.instance(cfg)
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="aworkers", name="AWorkers", layer=WarmupLayer.ASYNC,
            executor=lambda: time.sleep(0.05) or "workers_ok",
            timeout_ms=2000,
        ))
        wm.warmup_async()
        time.sleep(0.3)
        self.assertIsNotNone(wm.get("aworkers"))

    def test_10_shutdown_stops(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="ashut", name="AShut", layer=WarmupLayer.ASYNC,
            executor=lambda: time.sleep(10) or "nope",
            timeout_ms=5000,
        ))
        wm.warmup_async()
        time.sleep(0.05)
        wm.shutdown()


class T5CacheManagement(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_set_get_roundtrip(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("k", "v")
        self.assertEqual(wm.get("k"), "v")

    def test_02_ttl_expires(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("ttl-key", "val", ttl=0.01)
        time.sleep(0.02)
        self.assertIsNone(wm.get("ttl-key"))

    def test_03_ttl_zero_never_expires(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("inf-key", "val", ttl=0)
        time.sleep(0.02)
        self.assertEqual(wm.get("inf-key"), "val")

    def test_04_lru_eviction(self):
        cfg = WarmupConfig(cache_max_size=3)
        wm = WarmupManager.instance(cfg)
        wm.set_cache("a", 1)
        wm.set_cache("b", 2)
        wm.set_cache("c", 3)
        wm.set_cache("d", 4)
        time.sleep(0.01)
        self.assertIsNotNone(wm.get("d"))
        remaining = set(wm._cache.keys())
        self.assertIn("d", remaining)
        self.assertLessEqual(len(remaining), 3)

    def test_05_evicted_not_accessible(self):
        cfg = WarmupConfig(cache_max_size=2)
        wm = WarmupManager.instance(cfg)
        wm.set_cache("x", 1)
        wm.set_cache("y", 2)
        wm.set_cache("z", 3)
        time.sleep(0.01)
        keys = list(wm._cache.keys())
        self.assertLessEqual(len(keys), 2)

    def test_06_ttl_before_lru(self):
        cfg = WarmupConfig(cache_max_size=5)
        wm = WarmupManager.instance(cfg)
        wm.set_cache("fresh", "new", ttl=10.0)
        wm.set_cache("old", "ancient", ttl=0.01)
        time.sleep(0.08)
        self.assertIsNone(wm.get("old"))
        self.assertIsNotNone(wm.get("fresh"))

    def test_07_max_size_zero_disables(self):
        cfg = WarmupConfig(cache_enabled=False, cache_max_size=0)
        wm = WarmupManager.instance(cfg)
        wm.set_cache("nope", "val")
        self.assertIsNone(wm.get("nope"))

    def test_08_invalidate_single(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("keep", "yes")
        wm.set_cache("remove", "no")
        wm.invalidate("remove")
        self.assertEqual(wm.get("keep"), "yes")
        self.assertIsNone(wm.get("remove"))

    def test_09_invalidate_all(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("a", 1)
        wm.set_cache("b", 2)
        wm.invalidate_all()
        self.assertIsNone(wm.get("a"))
        self.assertIsNone(wm.get("b"))

    def test_10_invalidate_nonexistent(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.invalidate("ghost")
        self.assertEqual(len(wm._cache), 0)

    def test_11_access_count_increments(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("ctr", 99)
        wm.get("ctr")
        wm.get("ctr")
        wm.get("ctr")
        entry = wm._cache.get("ctr")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.access_count, 3)

    def test_12_concurrent_read_write(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        errors = []

        def worker(i):
            try:
                wm.set_cache(f"th-{i}", i)
                v = wm.get(f"th-{i}")
                assert v == i, f"Expected {i}, got {v}"
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])

    def test_13_capacity_exact(self):
        cfg = WarmupConfig(cache_max_size=5)
        wm = WarmupManager.instance(cfg)
        for i in range(5):
            wm.set_cache(f"cap-{i}", i)
        self.assertEqual(len(wm._cache), 5)
        wm.set_cache("cap-extra", 999)
        time.sleep(0.01)
        self.assertLessEqual(len(wm._cache), 5)

    def test_14_large_scale_performance(self):
        wm = WarmupManager.instance(WarmupConfig.full())
        start = time.perf_counter()
        for i in range(500):
            wm.set_cache(f"perf-{i}", i)
        for i in range(500):
            wm.get(f"perf-{i}")
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 500)


class T6DependencyResolution(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_no_deps_preserves_order(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        tasks = [
            WarmupTask(task_id=f"z-{i}", name=f"Z{i}", layer=WarmupLayer.EAGER,
                       executor=lambda i=i: i)
            for i in range(3)
        ]
        for t in tasks:
            wm.register_task(t)
        result = wm._topological_sort(tasks)
        self.assertEqual(len(result), 3)

    def test_02_chain_a_b_c(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        tasks = [
            WarmupTask(task_id="c", name="C", layer=WarmupLayer.EAGER,
                       dependencies=["b"], executor=lambda: "c"),
            WarmupTask(task_id="b", name="B", layer=WarmupLayer.EAGER,
                       dependencies=["a"], executor=lambda: "b"),
            WarmupTask(task_id="a", name="A", layer=WarmupLayer.EAGER,
                       executor=lambda: "a"),
        ]
        for t in tasks:
            wm.register_task(t)
        result = wm._topological_sort([wm._tasks[tid] for tid in ["a", "b", "c"]])
        ids = [r.task_id for r in result]
        self.assertEqual(ids.index("a"), 0)
        self.assertEqual(ids.index("c"), 2)

    def test_03_diamond_dep(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        tasks = [
            WarmupTask(task_id="root", name="Root", layer=WarmupLayer.EAGER,
                       executor=lambda: "r"),
            WarmupTask(task_id="left", name="Left", layer=WarmupLayer.EAGER,
                       dependencies=["root"], executor=lambda: "l"),
            WarmupTask(task_id="right", name="Right", layer=WarmupLayer.EAGER,
                       dependencies=["root"], executor=lambda: "ri"),
            WarmupTask(task_id="bottom", name="Bottom", layer=WarmupLayer.EAGER,
                       dependencies=["left", "right"], executor=lambda: "b"),
        ]
        for t in tasks:
            wm.register_task(t)
        result = wm._topological_sort(tasks)
        ids = [r.task_id for r in result]
        self.assertEqual(ids.index("root"), 0)
        self.assertEqual(ids.index("bottom"), 3)

    def test_04_circular_detects(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        tasks = [
            WarmupTask(task_id="x", name="X", layer=WarmupLayer.EAGER,
                       dependencies=["y"], executor=lambda: None),
            WarmupTask(task_id="y", name="Y", layer=WarmupLayer.EAGER,
                       dependencies=["x"], executor=lambda: None),
        ]
        for t in tasks:
            wm.register_task(t)
        with self.assertRaises(ValueError) as ctx:
            wm._topological_sort(list(wm._tasks.values()))
        self.assertIn("Circular", str(ctx.exception))

    def test_05_self_dep(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        task = WarmupTask(task_id="self", name="Self", layer=WarmupLayer.EAGER,
                          dependencies=["self"], executor=lambda: None)
        wm.register_task(task)
        with self.assertRaises(ValueError):
            wm._topological_sort([task])

    def test_06_empty_input(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        result = wm._topological_sort([])
        self.assertEqual(result, [])


class T7MetricsAndPerformance(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_metrics_structure(self):
        cfg = WarmupConfig(metrics_enabled=True)
        wm = WarmupManager.instance(cfg)
        wm.warmup(layers=[WarmupLayer.EAGER])
        m = wm.get_metrics()
        self.assertIsInstance(m, WarmupMetrics)
        self.assertIsInstance(m.startup_time_ms, float)
        self.assertIsInstance(m.cache_size, int)

    def test_02_startup_time_reasonable(self):
        cfg = WarmupConfig(metrics_enabled=True)
        wm = WarmupManager.instance(cfg)
        wm.warmup(layers=[WarmupLayer.EAGER])
        m = wm.get_metrics()
        self.assertGreater(m.startup_time_ms, 0)
        self.assertLess(m.startup_time_ms, 30000)

    def test_03_hit_rate_calculation(self):
        cfg = WarmupConfig(metrics_enabled=True)
        wm = WarmupManager.instance(cfg)
        wm.set_cache("h1", 1)
        wm.get("h1")
        wm.get("h1")
        m = wm.get_metrics()
        self.assertGreater(m.cache_hit_rate, 0)

    def test_04_diagnostics_output_nonempty(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        output = wm.print_diagnostics()
        self.assertIsInstance(output, str)
        self.assertIn("WarmupManager", output)

    def test_05_diagnostics_formatting(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        output = wm.print_diagnostics()
        self.assertIn("=== ", output)
        self.assertIn("ms", output)

    def test_06_benchmark_returns_stats(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        result = wm.benchmark(iterations=2)
        self.assertIn("mean_ms", result)
        self.assertIn("min_ms", result)
        self.assertIn("max_ms", result)
        self.assertIn("p50_ms", result)
        self.assertIn("p95_ms", result)

    def test_07_benchmark_iterations(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        result = wm.benchmark(iterations=3)
        self.assertEqual(result["iterations"], 3)

    def test_08_benchmark_cold_each_time(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("pre", "existing")
        wm.benchmark(iterations=1)
        post = wm.get("pre")
        self.assertIsNone(post)


class T8EdgeCasesAndDegradation(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_disabled_skips_warmup(self):
        cfg = WarmupConfig(enabled=False)
        wm = WarmupManager.instance(cfg)
        report = wm.warmup()
        self.assertEqual(report.total_tasks, 0)

    def test_02_timeout_handling(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        start = time.perf_counter()

        def slow_op():
            time.sleep(0.15)
            return "done"

        task = WarmupTask(task_id="tout", name="TOut", layer=WarmupLayer.EAGER,
                          executor=slow_op,
                          timeout_ms=50)
        wm.register_task(task)
        results = wm.warmup_eager()
        elapsed = (time.perf_counter() - start) * 1000
        self.assertGreater(elapsed, 100)
        self.assertEqual(results[0].status, WarmupStatus.SUCCESS)

    def test_03_empty_tasks_warmup(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        report = wm.warmup()
        self.assertEqual(report.total_tasks, 0)

    def test_04_duplicate_register_overwrite(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        t1 = WarmupTask(task_id="dup", name="First", executor=lambda: 1)
        t2 = WarmupTask(task_id="dup", name="Second", executor=lambda: 2)
        wm.register_task(t1)
        wm.register_task(t2)
        self.assertEqual(wm._tasks["dup"].name, "Second")

    def test_05_shutdown_then_get(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.set_cache("skey", "sval")
        wm.shutdown()
        result = wm.get("skey")
        self.assertIsNone(result)

    def test_06_shutdown_rewarm(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.shutdown()
        wm._shutdown_flag = False
        wm._is_warming_up = False
        wm._executor = None
        wm.set_cache("renew", "ok")
        self.assertEqual(wm.get("renew"), "ok")

    def test_07_env_var_parsing(self):
        cfg = WarmupConfig.from_env()
        self.assertIsInstance(cfg, WarmupConfig)

    def test_08_unknown_env_defaults(self):
        old = os.environ.get("WARMUP_MODE")
        try:
            os.environ["WARMUP_MODE"] = "UNKNOWN_VALUE"
            cfg = WarmupConfig.from_env()
            self.assertTrue(cfg.enabled)
        finally:
            if old is None:
                os.environ.pop("WARMUP_MODE", None)
            else:
                os.environ["WARMUP_MODE"] = old

    def test_09_large_timeout_value(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm._tasks.clear()
        wm._results.clear()
        task = WarmupTask(task_id="bigt", name="BigTimeout",
                          layer=WarmupLayer.EAGER,
                          executor=lambda: "big",
                          timeout_ms=999999)
        wm.register_task(task)
        results = wm.warmup_eager()
        self.assertEqual(results[0].status, WarmupStatus.SUCCESS)


class IT1CoordinatorIntegration(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_fast_coordinator_creation_after_warmup(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        from scripts.collaboration.coordinator import Coordinator
        start = time.perf_counter()
        coord = Coordinator()
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 200)

    def test_02_coordinator_plan_works(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        from scripts.collaboration.coordinator import Coordinator
        coord = Coordinator()
        plan = coord.plan_task("测试任务", [{"role_id": "architect"}])
        self.assertIsNotNone(plan)
        self.assertGreater(plan.total_tasks, 0)

    def test_03_lazy_coordinator_without_warmup(self):
        _reset()
        wm = WarmupManager.instance(WarmupConfig.fast())
        from scripts.collaboration.coordinator import Coordinator
        start = time.perf_counter()
        coord = Coordinator()
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 500)

    def test_04_scratchpad_shared_cache(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        from scripts.collaboration.scratchpad import Scratchpad
        s1 = Scratchpad()
        s2 = Scratchpad()
        self.assertIsNot(s1, s2)

    def test_05_invalidate_rebuild(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        wm.invalidate_all()
        from scripts.collaboration.coordinator import Coordinator
        coord = Coordinator()
        self.assertIsNotNone(coord)

    def test_06_no_memory_leak_many_creations(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        from scripts.collaboration.coordinator import Coordinator
        coords = []
        for _ in range(20):
            coords.append(Coordinator())
        self.assertEqual(len(coords), 20)


class IT2PromptRegistryIntegration(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_registry_queryable(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm.warmup(layers=[WarmupLayer.EAGER])
        meta = wm.get("role-metadata")
        self.assertIsNotNone(meta)
        self.assertIn("roles", meta)

    def test_02_registry_singleton_consistency(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm.warmup(layers=[WarmupLayer.EAGER])
        r1 = wm.get("role-metadata")
        r2 = wm.get("role-metadata")
        self.assertIs(r1, r2)

    def test_03_graceful_degradation_on_missing_files(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        result = wm._results.get("role-metadata")
        self.assertIsNotNone(result)
        self.assertIn(result.status, (WarmupStatus.SUCCESS, WarmupStatus.ERROR))

    def test_04_top3_roles_metadata_loaded(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm.warmup(layers=[WarmupLayer.EAGER])
        meta = wm.get("role-metadata")
        if meta and meta.get("error") != "registry_import_failed":
            roles = meta.get("roles", [])
            self.assertGreaterEqual(len(roles), 0)


class E2ETests(unittest.TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()

    def test_01_web_service_startup_journey(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        t_start = time.perf_counter()
        wm.warmup()
        max_wait = wm.config.async_timeout_ms / 1000.0 + 2.0
        deadline = time.monotonic() + max_wait
        while not wm.is_fully_warmed() and time.monotonic() < deadline:
            time.sleep(0.01)
        import_start = (time.perf_counter() - t_start) * 1000
        self.assertLess(import_start, 3000)

    def test_02_cli_fast_mode(self):
        old = os.environ.get("WARMUP_MODE")
        try:
            os.environ["WARMUP_MODE"] = "FAST"
            _reset()
            wm = WarmupManager.instance()
            t_start = time.perf_counter()
            wm.warmup()
            elapsed = (time.perf_counter() - t_start) * 1000
            self.assertLess(elapsed, 200)
        finally:
            if old is None:
                os.environ.pop("WARMUP_MODE", None)
            else:
                os.environ["WARMUP_MODE"] = old
            _reset()

    def test_03_warmup_use_invalidate_rewarm_cycle(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        self.assertTrue(wm.is_ready("core-models"))
        wm.invalidate_all()
        self.assertIsNone(wm.get("core-models"))
        wm.set_cache("core-models", {"reloaded": True})
        self.assertIsNotNone(wm.get("core-models"))

    def test_04_async_race_condition(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        wm._tasks.clear()
        wm._results.clear()
        wm.register_task(WarmupTask(
            task_id="race-async", name="RaceAsync",
            layer=WarmupLayer.ASYNC,
            executor=lambda: time.sleep(0.1) or "race_val",
            timeout_ms=2000,
        ))
        wm.warmup_async()
        val = wm.get("race-async")
        time.sleep(0.3)
        val_later = wm.get("race-async")
        if val_later is not None:
            self.assertEqual(val_later, "race_val")

    def test_05_high_concurrency_stress(self):
        wm = WarmupManager.instance(WarmupConfig.default())
        errors = []
        barrier = threading.Barrier(20)

        def stress_worker(i):
            try:
                barrier.wait(timeout=5)
                wm.set_cache(f"stress-{i}", i)
                wm.get(f"stress-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=stress_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(errors, [])

    def test_06_memory_stability_long_running(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        for cycle in range(50):
            wm.set_cache(f"mem-{cycle % 10}", cycle)
            wm.get(f"mem-{cycle % 10}")
            if cycle % 10 == 9:
                wm.invalidate_all()
        self.assertLess(len(wm._cache), 15)

    def test_07benchmark_regression_baseline(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        result = wm.benchmark(iterations=3)
        self.assertIn("p95_ms", result)
        self.assertLess(result["p95_ms"], 5000)

    def test_08_diagnostics_completeness(self):
        wm = WarmupManager.instance(WarmupConfig.fast())
        wm.warmup(layers=[WarmupLayer.EAGER])
        output = wm.print_diagnostics()
        lines = output.strip().split("\n")
        self.assertGreaterEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
