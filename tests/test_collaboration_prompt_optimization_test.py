#!/usr/bin/env python3
"""
Prompt Optimization System - Integration Tests

Tests for two Claude Code-inspired prompt optimization features:
  Feature 1: Dynamic Prompt Assembly (TaskComplexity-driven)
  Feature 2: Compression-Aware Prompt Adaptation

Note: PromptVariantGenerator tests removed (module was ghost feature - never used in production).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.context_compressor import CompressionLevel
from scripts.collaboration.models import TaskDefinition
from scripts.collaboration.prompt_assembler import (
    PromptAssembler,
    TaskComplexity,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker


class TestComplexityDetection(unittest.TestCase):
    """T2: 任务复杂度自动检测 (8)"""

    def setUp(self):
        self.assembler = PromptAssembler(role_id="arch", base_prompt="test")

    def test_simple_very_short(self):
        c = self.assembler.detect_complexity("写个hello函数")
        self.assertEqual(c, TaskComplexity.SIMPLE)

    def test_simple_with_simple_keyword(self):
        c = self.assembler.detect_complexity("快速修复一个小bug")
        self.assertEqual(c, TaskComplexity.SIMPLE)

    def test_complex_with_architecture_keywords(self):
        c = self.assembler.detect_complexity("设计高可用的微服务架构，支持分布式部署和容灾")
        self.assertEqual(c, TaskComplexity.COMPLEX)

    def test_long_multi_requirement_is_complex(self):
        long_desc = (
            "对系统进行全面性能优化："
            "1.数据库查询优化 2.缓存策略设计 3.API响应时间改善 "
            "4.并发处理能力提升 5.资源利用率监控 6.全链路追踪集成"
        )
        c = self.assembler.detect_complexity(long_desc)
        self.assertEqual(c, TaskComplexity.COMPLEX)

    def test_medium_default_for_normal_task(self):
        c = self.assembler.detect_complexity("实现用户注册功能，需要邮箱验证")
        self.assertEqual(c, TaskComplexity.MEDIUM)

    def test_medium_mixed_signals(self):
        c = self.assembler.detect_complexity("创建API模块，包括认证、权限、日志、错误处理")
        self.assertIn(c, [TaskComplexity.MEDIUM, TaskComplexity.COMPLEX])

    def test_simple_strong_signal_overrides(self):
        c = self.assembler.detect_complexity("简单写个工具函数来格式化日期")
        self.assertEqual(c, TaskComplexity.SIMPLE)

    def test_empty_description_falls_to_default(self):
        c = self.assembler.detect_complexity("")
        self.assertIn(c, [TaskComplexity.SIMPLE, TaskComplexity.MEDIUM])


class TestAssemblyVariants(unittest.TestCase):
    """T3: 提示词组装变体 (9)"""

    def setUp(self):
        self.base = "你是系统架构师。负责系统架构设计、技术选型。"
        self.asm = PromptAssembler(role_id="architect", base_prompt=self.base)

    def test_simple_produces_compact_or_standard(self):
        result = self.asm.assemble(task_description="写个排序函数")
        self.assertIn(result.variant_used, ["compact", "standard"])
        # V3.10.0: ponytail minimal-implementation injection adds ~170 tokens;
        # threshold raised from 1000 to 1500 to account for the new feature.
        self.assertLess(result.tokens_estimate, 1500)

    def test_complex_produces_enhanced(self):
        result = self.asm.assemble(task_description="设计分布式微服务架构方案，含服务发现和负载均衡")
        self.assertEqual(result.variant_used, "enhanced")
        self.assertEqual(result.complexity, TaskComplexity.COMPLEX)

    def test_medium_produces_standard(self):
        result = self.asm.assemble(task_description="实现完整的用户登录功能，支持OAuth2.0和邮箱验证")
        self.assertEqual(result.variant_used, "standard")

    def test_compact_no_constraints(self):
        result = self.asm.assemble(task_description="写个hello world")
        if result.complexity == TaskComplexity.SIMPLE:
            self.assertNotIn("约束条件", result.instruction)
            self.assertNotIn("反模式警告", result.instruction)

    def test_enhanced_has_constraints_and_antipatterns(self):
        result = self.asm.assemble(task_description="设计高可用微服务架构")
        if result.complexity == TaskComplexity.COMPLEX:
            self.assertIn("约束条件", result.instruction)

    def test_findings_included(self):
        findings = ["发现数据库连接池配置过低"]
        result = self.asm.assemble(task_description="优化系统", related_findings=findings)
        self.assertGreater(result.metadata["findings_included"], 0)

    def test_metadata_complete(self):
        result = self.asm.assemble(task_description="test", related_findings=["A", "B", "C"])
        meta = result.metadata
        self.assertIn("compression_applied", meta)
        self.assertEqual(meta["findings_total"], 3)

    def test_role_specific_anti_patterns(self):
        arch = PromptAssembler(role_id="architect", base_prompt="")
        tester = PromptAssembler(role_id="tester", base_prompt="")
        self.assertNotEqual(arch._get_role_anti_patterns(), tester._get_role_anti_patterns())

    def test_estimate_tokens_reasonable(self):
        tokens = PromptAssembler.estimate_tokens("test" * 100)
        self.assertGreater(tokens, 10)


class TestCompressionOverrides(unittest.TestCase):
    """T4: 压缩级别覆盖 (7)"""

    def setUp(self):
        self.asm = PromptAssembler(role_id="coder", base_prompt="你是开发者。负责开发调试重构优化。")

    def test_none_compression_full_output(self):
        result = self.asm.assemble(
            task_description="实现CRUD API接口，包含增删改查功能", compression_level=CompressionLevel.NONE
        )
        self.assertGreater(len(result.instruction), 50)

    def test_session_memory_minimal_lines(self):
        result = self.asm.assemble(task_description="实现CRUD API", compression_level=CompressionLevel.SESSION_MEMORY)
        lines = result.instruction.strip().split("\n")
        self.assertLessEqual(len(lines), 60)

    def test_full_compact_ultra_short(self):
        result = self.asm.assemble(task_description="实现CRUD API", compression_level=CompressionLevel.FULL_COMPACT)
        self.assertIn("[coder]", result.instruction)
        self.assertLess(len(result.instruction), 3000)

    def test_compression_marked_in_metadata(self):
        result = self.asm.assemble(task_description="t", compression_level=CompressionLevel.SNIP)
        self.assertTrue(result.metadata.get("compression_applied"))

    def test_full_compact_overrides_complexity(self):
        result = self.asm.assemble(
            task_description="设计高可用分布式系统",
            compression_level=CompressionLevel.FULL_COMPACT,
        )
        self.assertIn("[coder]", result.instruction)
        self.assertLess(len(result.instruction), 3000)

    def test_snip_limits_findings(self):
        many = [f"发现{i}" for i in range(20)]
        result = self.asm.assemble(
            task_description="分析问题", related_findings=many, compression_level=CompressionLevel.SNIP
        )
        self.assertLessEqual(result.metadata["findings_included"], 3)

    def test_snip_reduces_vs_none(self):
        r_none = self.asm.assemble(task_description="实现功能", compression_level=CompressionLevel.NONE)
        r_snip = self.asm.assemble(task_description="实现功能", compression_level=CompressionLevel.SNIP)
        self.assertLessEqual(len(r_snip.instruction), len(r_none.instruction))


class TestWorkerIntegration(unittest.TestCase):
    """T7: Worker 与 PromptAssembler 集成 (6)"""

    def setUp(self):
        self.sp = Scratchpad()

    def test_worker_do_work_returns_string(self):
        w = Worker(worker_id="w-i1", role_id="arch", role_prompt="你是架构师。", scratchpad=self.sp)
        task = TaskDefinition(task_id="t1", description="设计模块结构")
        ctx = w._build_execution_context(task)
        output = w._do_work(ctx)
        self.assertIsInstance(output, str)
        self.assertGreater(len(output), 10)

    def test_worker_stores_last_prompt(self):
        w = Worker(worker_id="w-i2", role_id="arch", role_prompt="你是架构师。", scratchpad=self.sp)
        task = TaskDefinition(task_id="t2", description="快速修复登录bug")
        ctx = w._build_execution_context(task)
        w._do_work(ctx)
        last = w.get_last_prompt()
        self.assertIsNotNone(last)
        self.assertIsInstance(last.complexity, TaskComplexity)
        self.assertIn(last.variant_used, ["compact", "standard", "enhanced"])

    def test_simple_task_yields_compact(self):
        w = Worker(worker_id="w-i3", role_id="coder", role_prompt="你是开发者。", scratchpad=self.sp)
        task = TaskDefinition(task_id="t3", description="写个日志工具类")
        ctx = w._build_execution_context(task)
        w._do_work(ctx)
        last = w.get_last_prompt()
        self.assertIn(last.complexity, [TaskComplexity.SIMPLE, TaskComplexity.MEDIUM])
        self.assertIn(last.variant_used, ["compact", "standard"])

    def test_complex_task_yields_enhanced(self):
        w = Worker(worker_id="w-i4", role_id="arch", role_prompt="你是架构师。", scratchpad=self.sp)
        task = TaskDefinition(
            task_id="t4",
            description=("设计完整的CI/CD流水线，包括：1.自动化构建 2.多环境部署 3.回滚机制 4.监控告警"),
        )
        ctx = w._build_execution_context(task)
        w._do_work(ctx)
        last = w.get_last_prompt()
        self.assertEqual(last.complexity, TaskComplexity.COMPLEX)
        self.assertEqual(last.variant_used, "enhanced")

    def test_compression_level_propagates(self):
        w = Worker(worker_id="w-i5", role_id="coder", role_prompt="你是开发者。", scratchpad=self.sp)
        task = TaskDefinition(task_id="t5", description="导出数据功能")
        ctx = w._build_execution_context(task, compression_level=CompressionLevel.FULL_COMPACT)
        output = w._do_work(ctx)
        last = w.get_last_prompt()
        self.assertTrue(last.metadata.get("compression_applied"))
        self.assertLess(len(output), 500)

    def test_execute_returns_result(self):
        w = Worker(worker_id="w-i6", role_id="tester", role_prompt="你是测试专家。", scratchpad=self.sp)
        task = TaskDefinition(task_id="t6", description="添加单元测试")
        result = w.execute(task)
        self.assertTrue(result.success)


class TestEdgeCases(unittest.TestCase):
    """T8: 边界情况 (5 - PromptVariantGenerator tests removed)"""

    def setUp(self):
        self.asm = PromptAssembler(role_id="arch", base_prompt="test")

    def test_empty_description_ok(self):
        r = self.asm.assemble(task_description="")
        self.assertIsNotNone(r.instruction)

    def test_very_long_description_ok(self):
        r = self.asm.assemble(task_description="重要任务 " * 300)
        self.assertIsNotNone(r.instruction)

    def test_none_findings_ok(self):
        r = self.asm.assemble(task_description="test", related_findings=None)
        self.assertIsNotNone(r.instruction)

    def test_empty_findings_ok(self):
        r = self.asm.assemble(task_description="test", related_findings=[])
        self.assertNotIn("相关发现", r.instruction)

    def test_unknown_role_no_crash(self):
        a = PromptAssembler(role_id="unknown-x", base_prompt="t")
        self.assertIsInstance(a._get_role_anti_patterns(), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
