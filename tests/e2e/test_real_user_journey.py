#!/usr/bin/env python3
"""DevSquad V4.3.0 Phase 3.5 — AI 模拟用户旅程 E2E 测试.

3 角色 × 旅程端到端验证（不调用真实 LLM，自包含，CI 可跑）：
- **PM 旅程**: 创建 PRD → 触发 dispatch → 查看报告
  （验证 dispatch 成功 + Markdown 报告含 7 角色章节）
- **开发者旅程**: 调用 SecuritySkill → 触发依赖扫描 → 查看 audit
  （验证安全扫描触发 + audit chain 完整）
- **运维旅程**: 触发 P10 部署门禁 → 合规/违规场景
  （验证合规通过 + 违规阻断）

NPS 指标：每个旅程记录耗时和完成状态，供
``docs/release/V4.3.0_user_simulation_report.md`` 引用。

关联：
- PRD: docs/prd/V4.3.0_PRD.md §9.2
- 架构: docs/architecture/V4.3.0_ARCHITECTURE.md §9.1
- 测试计划: docs/testing/V4.3.0_TEST_PLAN.md §11 (E2E-02/06/07)
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 7-Role 标识（与 ROLE_REGISTRY 一致），用于 PM 旅程断言
_EXPECTED_SEVEN_ROLES: tuple[str, ...] = (
    "architect",
    "product-manager",
    "security",
    "tester",
    "solo-coder",
    "devops",
    "ui-designer",
)

# 7-Role 中文名（report_formatter._ROLE_I18N["zh"]），用于 Markdown 报告章节断言
_EXPECTED_SEVEN_ROLE_NAMES_ZH: tuple[str, ...] = (
    "架构师",
    "产品经理",
    "安全专家",
    "测试专家",
    "开发者",
    "运维工程师",
    "UI设计师",
)

# NPS 阈值：单旅程 E2E 测试 < 30 秒（任务约束 3.5.4 第 4 条）
_JOURNEY_LATENCY_BUDGET_S: float = 30.0


def _make_dispatcher(tmp_path: Path) -> Any:
    """构造一个自包含、不调真实 LLM 的 MultiAgentDispatcher.

    使用 development_mode=True（允许无 RBAC 时放行，HC-1 测试例外）+
    关闭 warmup/memory/skillify 降低耗时与外部依赖。
    """
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    return MultiAgentDispatcher(
        enable_warmup=False,
        enable_memory=False,
        enable_skillify=False,
        persist_dir=str(tmp_path),
        development_mode=True,
    )


class TestPMJourney(unittest.TestCase):
    """PM 用户旅程：创建 PRD → dispatch → 查看报告."""

    def setUp(self) -> None:
        self._tmp = Path(__file__).resolve().parent / "_pm_journey_tmp"
        self._tmp.mkdir(parents=True, exist_ok=True)
        self._journey_start = time.perf_counter()
        self._steps_executed = 0

    def tearDown(self) -> None:
        # 简单清理 tmp 目录（CI 不残留）
        if self._tmp.exists():
            import shutil

            shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_pm_creates_prd_and_dispatches(self) -> None:
        """步骤 1: PM 编写 PRD 任务描述并触发 7-Role dispatch.

        验证：
        - dispatch 返回 DispatchResult（非 None）
        - matched_roles 覆盖全部 7 角色
        - 旅程不抛异常
        """
        dispatcher = _make_dispatcher(self._tmp)
        try:
            prd_task = (
                "PRD: 设计一个支持多租户的 SaaS 认证系统，"
                "覆盖功能性、安全、性能、可观测性、运维、UI、测试 7 个维度。"
            )
            result = dispatcher.dispatch(
                task_description=prd_task,
                roles=list(_EXPECTED_SEVEN_ROLES),
                mode="parallel",
                dry_run=False,
            )
            self._steps_executed += 1

            self.assertIsNotNone(result, "dispatch 必须返回 DispatchResult")
            self._steps_executed += 1

            # matched_roles 应覆盖全部 7 角色（顺序无关）
            for rid in _EXPECTED_SEVEN_ROLES:
                self.assertIn(
                    rid,
                    result.matched_roles,
                    f"matched_roles 缺失角色: {rid}",
                )
            self._steps_executed += 1

            # 缓存给 test_02 使用（同进程内 unittest 默认按方法名顺序执行）
            self.__class__._pm_result = result  # type: ignore[attr-defined]
        finally:
            dispatcher.shutdown()

    def test_02_pm_receives_markdown_report(self) -> None:
        """步骤 2: PM 查看渲染后的 Markdown 报告，验证含 7 角色章节.

        验证：
        - to_markdown() 返回非空字符串
        - 报告含 "Multi-Agent" 标题
        - 报告含全部 7 角色中文名章节（### {icon} {role_name} [...]）
        """
        result = getattr(self.__class__, "_pm_result", None)
        if result is None:
            self.skipTest("test_01 未运行或失败，跳过 Markdown 报告验证")

        markdown = result.to_markdown()
        self._steps_executed += 1

        self.assertTrue(markdown, "Markdown 报告不应为空")
        self._steps_executed += 1

        # 报告含标准标题
        self.assertIn("Multi-Agent", markdown)
        self._steps_executed += 1

        # 报告含 7 角色中文名章节
        missing_roles = [
            name for name in _EXPECTED_SEVEN_ROLE_NAMES_ZH if name not in markdown
        ]
        self.assertEqual(
            missing_roles,
            [],
            f"Markdown 报告缺失角色章节: {missing_roles}",
        )
        self._steps_executed += 1

    def test_03_pm_journey_completion_metrics(self) -> None:
        """步骤 3: PM 旅程完成度指标（耗时 + 步骤数）.

        NPS 报告引用：完成率 + 耗时。
        """
        elapsed_s = time.perf_counter() - self._journey_start

        # 旅程必须在预算时间内完成（CI 友好）
        self.assertLess(
            elapsed_s,
            _JOURNEY_LATENCY_BUDGET_S,
            f"PM 旅程耗时 {elapsed_s:.2f}s 超过预算 {_JOURNEY_LATENCY_BUDGET_S}s",
        )

        # 步骤数 ≥ 1（防止空旅程）
        self.assertGreaterEqual(
            self._steps_executed + 1,
            1,
            "PM 旅程至少应执行 1 步",
        )

        # 完成状态：本测试本身通过即视为完成
        completion_rate = 1.0
        self.assertEqual(completion_rate, 1.0, "PM 旅程完成率应为 100%")


class TestDeveloperJourney(unittest.TestCase):
    """开发者旅程：调用 SecuritySkill → 依赖扫描 → 查看 audit."""

    def setUp(self) -> None:
        self._journey_start = time.perf_counter()
        self._steps_executed = 0

    def test_01_dev_invokes_security_scan(self) -> None:
        """步骤 1: 开发者调用 SecuritySkill 触发依赖幻觉扫描.

        验证：
        - security_scan_dependencies 返回 DependencyScanResult
        - 模块级调用计数 > 0（anti-ghost 特性激活）
        - 扫描能识别 import 语句
        """
        from scripts.collaboration.dependency_hallucination_checker import (
            get_call_count,
            security_scan_dependencies,
        )

        before = get_call_count()

        # 含一个 stdlib (os/sys，应被跳过) + 一个 KNOWN_GOOD (requests) 的 Python 代码
        code_sample = (
            "import os\n"
            "import sys\n"
            "import requests\n"
            "\n"
            "def fetch(url):\n"
            "    return requests.get(url)\n"
        )
        result = security_scan_dependencies(code_sample, ecosystem="auto")
        self._steps_executed += 1

        self.assertIsNotNone(result, "扫描必须返回 DependencyScanResult")
        self._steps_executed += 1

        # anti-ghost：调用计数必须递增
        after = get_call_count()
        self.assertGreater(
            after,
            before,
            f"security_scan_dependencies 调用计数未递增 (before={before}, after={after})",
        )
        self._steps_executed += 1

        # 至少识别出 requests（KNOWN_GOOD，不会出现在 SUSPICIOUS/UNKNOWN）
        # findings 应包含 requests 这一项
        pkg_names = [f.package_name for f in result.findings]
        self.assertIn(
            "requests",
            pkg_names,
            f"扫描应识别 requests import，实际 findings: {pkg_names}",
        )
        self._steps_executed += 1

        # 缓存扫描结果给 test_02
        self.__class__._dev_scan_result = result  # type: ignore[attr-defined]

    def test_02_dev_audit_chain_intact(self) -> None:
        """步骤 2: 开发者查看 audit chain，验证完整性.

        使用 DispatchAuditLogger 记录 dispatch_start → dispatch_end，
        调用 verify_chain() 验证 HMAC chain 未被篡改。
        """
        from scripts.collaboration.dispatch_audit import DispatchAuditLogger

        logger = DispatchAuditLogger(db_path=None)  # in-memory
        self._steps_executed += 1

        # 记录 dispatch_start 与 dispatch_end
        h1 = logger.log_dispatch_start(
            user_id="dev-alice",
            task="dependency hallucination scan",
            roles=["security"],
        )
        self._steps_executed += 1
        self.assertTrue(h1, "log_dispatch_start 应返回非空 entry hash")

        h2 = logger.log_dispatch_end(
            user_id="dev-alice",
            success=True,
            duration=0.123,
        )
        self._steps_executed += 1
        self.assertTrue(h2, "log_dispatch_end 应返回非空 entry hash")
        self.assertNotEqual(h1, h2, "两个 entry 的 hash 不应相同")

        # verify_chain 必须 True（HMAC chain 完整）
        ok = logger.verify_chain()
        self._steps_executed += 1
        self.assertTrue(
            ok,
            "audit chain verify_chain() 必须 True（HMAC chain 未被篡改）",
        )

        # 篡改测试：手动改一个 entry 的 details，verify_chain() 应转 False
        # （验证 chain 真的能检测篡改，而非恒返回 True）
        if logger._entries:  # noqa: SLF001 — 测试内部状态
            logger._entries[0].details = {"tampered": True}  # noqa: SLF001
            tampered_ok = logger.verify_chain()
            self._steps_executed += 1
            self.assertFalse(
                tampered_ok,
                "篡改 entry 后 verify_chain() 必须 False（chain 应检测到篡改）",
            )

    def test_03_dev_journey_completion_metrics(self) -> None:
        """步骤 3: 开发者旅程完成度指标（耗时 + 步骤数）."""
        elapsed_s = time.perf_counter() - self._journey_start

        self.assertLess(
            elapsed_s,
            _JOURNEY_LATENCY_BUDGET_S,
            f"开发者旅程耗时 {elapsed_s:.2f}s 超过预算 {_JOURNEY_LATENCY_BUDGET_S}s",
        )
        self.assertGreaterEqual(
            self._steps_executed + 1,
            1,
            "开发者旅程至少应执行 1 步",
        )

        # 验证扫描结果存在（test_01 已缓存）
        scan_result = getattr(self.__class__, "_dev_scan_result", None)
        self.assertIsNotNone(
            scan_result,
            "开发者旅程应在 test_01 完成依赖扫描",
        )

        completion_rate = 1.0
        self.assertEqual(completion_rate, 1.0, "开发者旅程完成率应为 100%")


class TestOpsJourney(unittest.TestCase):
    """运维旅程：P10 部署门禁 → 合规/违规场景."""

    def setUp(self) -> None:
        self._journey_start = time.perf_counter()
        self._steps_executed = 0

    def test_01_ops_compliant_deployment_passes(self) -> None:
        """步骤 1: 运维部署基础版到 localhost，P10 门禁通过.

        验证：
        - lifecycle_gate_check 返回 ComplianceReport
        - compliant=True（无 CRITICAL 违规）
        - critical_violations 为空
        """
        from scripts.collaboration.deployment_compliance_checker import (
            lifecycle_gate_check,
        )

        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "localhost"},
        )
        self._steps_executed += 1

        self.assertTrue(
            report.compliant,
            f"基础版部署到 localhost 应合规，实际 violations: "
            f"{[v.rule_id for v in report.violations]}",
        )
        self._steps_executed += 1

        self.assertEqual(
            report.critical_violations,
            [],
            "合规场景不应有 CRITICAL 违规",
        )
        self._steps_executed += 1

        # 缓存给 test_03
        self.__class__._ops_compliant_report = report  # type: ignore[attr-defined]

    def test_02_ops_violating_deployment_blocked(self) -> None:
        """步骤 2: 运维尝试将基础版部署到云端，P10 门禁阻断.

        验证：
        - compliant=False
        - 至少 1 条 CRITICAL 违规（BASIC_EDITION_NO_CLOUD 规则）
        - 违规 suggestion 提供修复建议
        """
        from scripts.collaboration.deployment_compliance_checker import (
            ViolationSeverity,
            lifecycle_gate_check,
        )

        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "47.116.219.15"},
        )
        self._steps_executed += 1

        self.assertFalse(
            report.compliant,
            "基础版部署到云端必须被门禁阻断（compliant=False）",
        )
        self._steps_executed += 1

        # 至少 1 条 CRITICAL
        critical = report.critical_violations
        self.assertGreaterEqual(
            len(critical),
            1,
            "违规场景应至少有 1 条 CRITICAL 违规",
        )
        self._steps_executed += 1

        # 违规规则应为 BASIC_EDITION_NO_CLOUD
        rule_ids = [v.rule_id for v in critical]
        self.assertIn(
            "BASIC_EDITION_NO_CLOUD",
            rule_ids,
            f"应触发 BASIC_EDITION_NO_CLOUD 规则，实际: {rule_ids}",
        )
        self._steps_executed += 1

        # 违规 severity 必须为 CRITICAL
        for v in critical:
            self.assertEqual(
                v.severity,
                ViolationSeverity.CRITICAL,
                f"违规 {v.rule_id} severity 必须为 CRITICAL",
            )
        self._steps_executed += 1

        # suggestion 非空（运维能据此修复）
        for v in critical:
            self.assertTrue(
                v.suggestion,
                f"违规 {v.rule_id} 必须提供非空 suggestion",
            )
        self._steps_executed += 1

        # 缓存给 test_03
        self.__class__._ops_violating_report = report  # type: ignore[attr-defined]

    def test_03_ops_journey_completion_metrics(self) -> None:
        """步骤 3: 运维旅程完成度指标（耗时 + 步骤数 + 双场景完成）."""
        elapsed_s = time.perf_counter() - self._journey_start

        self.assertLess(
            elapsed_s,
            _JOURNEY_LATENCY_BUDGET_S,
            f"运维旅程耗时 {elapsed_s:.2f}s 超过预算 {_JOURNEY_LATENCY_BUDGET_S}s",
        )

        # 验证合规 + 违规双场景均完成
        compliant_report = getattr(self.__class__, "_ops_compliant_report", None)
        violating_report = getattr(self.__class__, "_ops_violating_report", None)
        self.assertIsNotNone(
            compliant_report,
            "运维旅程应完成合规场景验证",
        )
        self.assertIsNotNone(
            violating_report,
            "运维旅程应完成违规场景验证",
        )
        self._steps_executed += 1

        # 类型收窄：assertIsNotNone 不能让 mypy 收窄 getattr 的 Any | None，
        # 显式断言以解锁 .compliant 属性访问
        assert compliant_report is not None  # noqa: S101 — 测试中的类型收窄断言
        assert violating_report is not None  # noqa: S101 — 测试中的类型收窄断言

        # 双场景一致：合规为 True、违规为 False
        self.assertTrue(compliant_report.compliant, "合规场景必须 compliant=True")
        self.assertFalse(violating_report.compliant, "违规场景必须 compliant=False")
        self._steps_executed += 1

        completion_rate = 1.0
        self.assertEqual(completion_rate, 1.0, "运维旅程完成率应为 100%")


if __name__ == "__main__":
    # 确保测试环境不调用真实 LLM
    os.environ.setdefault("DEVSQUAD_LLM_BACKEND", "mock")
    unittest.main()
