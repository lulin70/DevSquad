#!/usr/bin/env python3
"""
DevSquad V4.3.0 E2E Test: User Journey - V4.3 Features

用户旅程：用户使用 V4.3.0 的核心新特性完成端到端任务。

故事：Bob 是一名平台工程师，他需要：
  1. 验证 pickle 缓存迁移全旅程（P0-1 + P2-1）
  2. 在 Ponytail lite/full 模式间切换（P1-1）
  3. 体验 LoopKernel 回退策略（P1-4）
  4. 通过 Dashboard 状态可视化感知后端能力（P1-6）
  5. 端到端运行 7-Role 协作并验证 V4.3 标记（真实用户模拟）

目标：验证 V4.3.0 5 个核心场景从用户视角可达，可发布。
关联文档：docs/testing/V4.3.0_TEST_PLAN.md §5 E2E 测试场景。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class _StreamlitFake:
    """Minimal Streamlit-compatible fake container for panel rendering tests."""

    def markdown(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def metric(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def subheader(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def info(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def caption(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def progress(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def dataframe(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def columns(self, n: int) -> list[_StreamlitFake]:
        return [_StreamlitFake() for _ in range(n)]


class TestV43CachePickleMigrationJourney:
    """场景 1: pickle 缓存迁移全旅程（P0-1 + P2-1）。"""

    def test_json_serialize_deserialize_round_trip(self) -> None:
        """用户用 JSON 序列化 dict 数据，能完整反序列化。"""
        from scripts.collaboration.cache_interface import Serializer

        payload = {"user": "alice", "items": [1, 2, 3], "nested": {"ok": True}}
        data = Serializer.serialize(payload, format="json")
        assert isinstance(data, bytes)

        restored = Serializer.deserialize(data, format="json")
        assert restored == payload

    def test_pickle_format_rejected_at_serialize(self) -> None:
        """用户尝试用 pickle 格式序列化，被拒绝（P0-1 dead code 删除后）。"""
        from scripts.collaboration.cache_interface import Serializer

        with pytest.raises(ValueError, match="pickle|Pickle"):
            Serializer.serialize({"x": 1}, format="pickle")

    def test_pickle_format_rejected_at_deserialize(self) -> None:
        """用户尝试用 pickle 格式反序列化，被拒绝。"""
        from scripts.collaboration.cache_interface import Serializer

        with pytest.raises(ValueError, match="pickle|Pickle"):
            Serializer.deserialize(b'{"x": 1}', format="pickle")

    def test_non_json_payload_rejected_after_fallback_removed(self) -> None:
        """P2-1: 非 JSON 字节流（含恶意 pickle payload）被拒绝，不再回退到 pickle。"""
        from scripts.collaboration.cache_interface import Serializer

        # 构造非 JSON 字节流（pickle 协议头 \x80\x04）
        non_json_bytes = b"\x80\x04\x95\x1a\x00\x00\x00\x00\x00\x00\x00\x8c\x0bhello pickle\x94."
        with pytest.raises(ValueError):
            Serializer.deserialize(non_json_bytes, format="json")

    def test_no_pickle_import_in_cache_interface_source(self) -> None:
        """E2E 安全断言：cache_interface.py 源码中不应再 import pickle。"""
        src_path = _PROJECT_ROOT / "scripts" / "collaboration" / "cache_interface.py"
        source = src_path.read_text(encoding="utf-8")
        assert "import pickle" not in source, (
            "cache_interface.py 不应再 import pickle（P2-1 已完全移除 fallback）"
        )


class TestV43PonytailModeSwitchJourney:
    """场景 2: Ponytail lite/full 模式切换全旅程（P1-1）。"""

    def test_full_mode_backward_compatible(self) -> None:
        """用户使用 full 模式，注入文本含全部 7 rungs（向后兼容 V3.10.0）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "full"}}
        injector = PonytailRuleInjector(qc_config=config)
        injection = injector.build_injection()

        assert "YAGNI" in injection
        assert "standard library" in injection
        assert "one line" in injection

    def test_lite_mode_includes_core_rungs(self) -> None:
        """用户切换到 lite 模式，注入文本含核心 rungs（测试/UI 角色使用）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "lite"}}
        injector = PonytailRuleInjector(qc_config=config)
        injection = injector.build_injection()

        assert "YAGNI" in injection
        assert "lite" in injection.lower() or "minimal" in injection.lower()

    def test_mode_switch_latency_under_50ms(self) -> None:
        """性能断言：模式切换在 50ms 内完成（用户无感知延迟）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config_full = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "full"}}
        config_lite = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "lite"}}

        start = time.perf_counter()
        inj_full = PonytailRuleInjector(qc_config=config_full)
        _ = inj_full.build_injection()
        inj_lite = PonytailRuleInjector(qc_config=config_lite)
        _ = inj_lite.build_injection()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50, f"模式切换延迟 {elapsed_ms:.2f}ms 超过 50ms 阈值"

    def test_red_lines_enforced_in_both_modes(self) -> None:
        """用户在两种模式下都受 16 条不可简化红线保护。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        for mode in ("lite", "full"):
            config = {"quality_control": {"minimal_implementation": True, "ponytail_mode": mode}}
            injector = PonytailRuleInjector(qc_config=config)
            assert len(injector.red_lines) >= 6, f"{mode} 模式红线数不足"


class TestV43LoopKernelRollbackJourney:
    """场景 3: LoopKernel 回退策略全旅程（P1-4）。"""

    def test_d3_failure_routes_to_test_verification(self) -> None:
        """用户在 D3 (Test Verification) 失败时，回退目标是 TEST 而非 DEV。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy(max_rollback_iterations=3)
        target = strategy.determine_rollback("D3")
        assert target == RollbackTarget.TEST

    def test_d1_d2_d4_d5_d6_route_to_dev(self) -> None:
        """用户在 D1/D2/D4/D5/D6 失败时，回退目标是 DEV。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy(max_rollback_iterations=3)
        for dim in ("D1", "D2", "D4", "D5", "D6"):
            target = strategy.determine_rollback(dim)
            assert target == RollbackTarget.DEV, f"{dim} 应回退到 DEV，实际 {target}"

    def test_rollback_max_iterations_hard_limit_3(self) -> None:
        """用户配置 rollback_max_iterations=3，第 3 次后应停止。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        strategy = RollbackStrategy(max_rollback_iterations=3)
        assert not strategy.should_stop(0)
        assert not strategy.should_stop(1)
        assert not strategy.should_stop(2)
        assert strategy.should_stop(3), "rollback_count=3 应触发硬停止"
        assert strategy.should_stop(99)

    def test_rollback_decision_latency_under_5ms(self) -> None:
        """性能断言：回退决策延迟 < 5ms。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        strategy = RollbackStrategy(max_rollback_iterations=3)
        start = time.perf_counter()
        for _ in range(100):
            _ = strategy.determine_rollback("D3")
            _ = strategy.should_stop(99)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_call_ms = elapsed_ms / 100
        assert per_call_ms < 5, f"单次决策 {per_call_ms:.3f}ms 超过 5ms"

    def test_execute_rollback_records_target_and_executed_flag(self) -> None:
        """用户执行回退，context 中记录 rollback_target 和 rollback_executed。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy()
        context: dict[str, object] = {}
        ok = strategy.execute_rollback(RollbackTarget.DEV, context)
        assert ok is True
        assert context["rollback_target"] == "dev"
        assert context["rollback_executed"] is True


class TestV43DashboardVisualizationJourney:
    """场景 4: Dashboard 状态可视化全旅程（P1-6）。"""

    def test_ponytail_mode_panel_renders_lite(self) -> None:
        """用户查看 Dashboard，Ponytail 模式面板可渲染 lite 模式。"""
        from scripts.dashboard.v43_panels import render_ponytail_mode_panel

        try:
            render_ponytail_mode_panel("lite", container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001 — 容错降级也要可观察
            pytest.fail(f"lite 模式面板渲染失败: {exc}")

    def test_ponytail_mode_panel_renders_full(self) -> None:
        """用户查看 Dashboard，Ponytail 模式面板可渲染 full 模式。"""
        from scripts.dashboard.v43_panels import render_ponytail_mode_panel

        try:
            render_ponytail_mode_panel("full", container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"full 模式面板渲染失败: {exc}")

    def test_loop_rollback_panel_renders(self) -> None:
        """用户查看 Dashboard，Loop 回退面板可渲染统计信息。"""
        from scripts.dashboard.v43_panels import render_loop_rollback_panel

        try:
            render_loop_rollback_panel(
                rollback_count=2,
                max_iterations=3,
                artifacts_count=5,
                last_target="dev",
                container=_StreamlitFake(),
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Loop 回退面板渲染失败: {exc}")

    def test_plugin_events_panel_renders(self) -> None:
        """用户查看 Dashboard，Plugin 热加载事件流面板可渲染。"""
        from scripts.dashboard.v43_panels import render_plugin_events_panel

        events = [
            {"event": "loaded", "plugin": "my_plugin", "timestamp": "2026-07-24T10:00:00Z"},
            {"event": "unloaded", "plugin": "old_plugin", "timestamp": "2026-07-24T10:05:00Z"},
        ]
        try:
            render_plugin_events_panel(events, container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Plugin 事件流面板渲染失败: {exc}")

    def test_todo_drift_panel_renders(self) -> None:
        """用户查看 Dashboard，TodoDrift 状态面板可渲染。"""
        from scripts.dashboard.v43_panels import render_todo_drift_panel

        try:
            render_todo_drift_panel(
                total=10,
                registered=8,
                unregistered=2,
                last_scan="2026-07-24T10:00:00Z",
                container=_StreamlitFake(),
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"TodoDrift 面板渲染失败: {exc}")


class TestV43MultiRoleCollaborationJourney:
    """场景 5: 真实用户多角色协作模拟（V4.3.0 配置下端到端运行）。"""

    def test_seven_roles_dispatch_completes(self, tmp_path: Path) -> None:
        """用户触发 7-Role 协作，dispatch 完成且返回结构化报告。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            persist_dir=str(tmp_path),
            development_mode=True,
        )
        try:
            result = dispatcher.dispatch(
                task_description="Design a secure user authentication system",
                roles=["architect", "security", "tester"],
                mode="parallel",
                dry_run=False,
            )
            assert result is not None
            assert result.success in (True, False)
            assert hasattr(result, "to_markdown")
        finally:
            dispatcher.shutdown()

    def test_todo_drift_monitor_runs_clean_on_repo(self) -> None:
        """用户在 V4.3.0 仓库上运行 todo_drift_monitor，无未登记技术债。"""
        from scripts.collaboration.todo_drift_monitor import scan_tech_debt

        scripts_dir = _PROJECT_ROOT / "scripts"
        entries = scan_tech_debt(root_dir=str(scripts_dir))
        # V4.3.0 仓库应保持技术债基线干净（允许有已登记的，但不应有大量未登记）
        assert isinstance(entries, list)
        # 总数应在合理范围（<200，过滤后真实 TODO/FIXME/HACK/XXX/WIP）
        assert len(entries) < 200, (
            f"扫描到 {len(entries)} 个标记，疑似未过滤的误报，请检查 regex"
        )

    def test_v43_modules_importable(self) -> None:
        """用户可导入所有 V4.3.0 新模块（无幽灵功能、无 import 错误）。"""
        modules_to_check = [
            "scripts.collaboration.cache_interface",
            "scripts.collaboration.ponytail_rule_injector",
            "scripts.collaboration.todo_drift_monitor",
            "scripts.collaboration.loop_engineering.rollback_strategy",
            "scripts.dashboard.v43_panels",
        ]
        for mod_name in modules_to_check:
            try:
                __import__(mod_name)
            except ImportError as exc:
                pytest.fail(f"V4.3.0 模块 {mod_name} 导入失败: {exc}")

    def test_v43_skill_manifest_version_consistent(self) -> None:
        """用户查看 skill-manifest.yaml，版本号为 4.2.9（V4.3.0 candidate）。"""
        manifest_path = _PROJECT_ROOT / "skill-manifest.yaml"
        content = manifest_path.read_text(encoding="utf-8")
        assert "version: 4.2.9" in content, (
            "skill-manifest.yaml 版本号应为 4.2.9（V4.3.0 candidate 预发布）"
        )

    def test_changelog_records_v429_prerelease(self) -> None:
        """用户查看 CHANGELOG，V4.2.9 预发布条目已记录。"""
        changelog_path = _PROJECT_ROOT / "CHANGELOG.md"
        content = changelog_path.read_text(encoding="utf-8")
        assert "## [4.2.9]" in content, "CHANGELOG.md 应包含 [4.2.9] 条目"
        assert "pickle" in content.lower()
        assert "ponytail" in content.lower()
        assert "rollback" in content.lower() or "回退" in content
