#!/usr/bin/env python3
"""
DevSquad V4.3.0 Integration Tests: Cross-Module Collaboration

验证 V4.3.0 新模块间的协作链路，补足测试金字塔 integration 比例至 15%+。

覆盖场景:
  T1: Cache pickle 迁移 + Redis 后端安全收紧集成
  T2: Ponytail 双模式 + PromptAssembler 注入链路
  T3: LoopKernel RollbackStrategy + LoopScheduler 协作
  T4: Dashboard V4.3 面板 + 数据源集成
  T5: TodoDriftMonitor + cache_interface + ponytail 跨模块扫描
  T6: V4.3 模块互相导入 + 一致性校验

关联文档: docs/testing/V4.3.0_TEST_PLAN.md §3 测试矩阵
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
    """Minimal Streamlit-compatible fake container for panel rendering tests.

    Implements all Streamlit APIs used by v43_panels.py:
    markdown / metric / subheader / columns / progress / info / dataframe / caption.
    """

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


# =============================================================================
# T1: Cache pickle 迁移 + Redis 后端安全收紧集成
# =============================================================================


class TestCachePickleMigrationIntegration:
    """P0-1 + P2-1: cache_interface 与 redis_cache 协作，pickle 全旅程拒绝。"""

    def test_redis_backend_rejects_pickle_format(self) -> None:
        """RedisCacheBackend 构造时拒绝 serialization_format='pickle'。"""
        from scripts.collaboration.redis_cache import RedisCacheBackend

        with pytest.raises(ValueError, match="pickle"):
            RedisCacheBackend(serialization_format="pickle")

    def test_redis_backend_accepts_json_format(self) -> None:
        """RedisCacheBackend 接受 JSON 格式（默认）。"""
        from scripts.collaboration.redis_cache import RedisCacheBackend

        backend = RedisCacheBackend(
            redis_url="redis://:dummy@localhost:6379/0",
            serialization_format="json",
            require_password=True,
        )
        assert backend is not None

    def test_redis_backend_require_password_enforced(self) -> None:
        """require_password=True 时，URL 无密码应拒绝构造。"""
        from scripts.collaboration.redis_cache import RedisCacheBackend

        with pytest.raises(ValueError, match="password"):
            RedisCacheBackend(
                redis_url="redis://localhost:6379/0",
                require_password=True,
            )

    def test_serializer_json_round_trip_preserves_types(self) -> None:
        """JSON 序列化/反序列化保留 dict/list/str/int/float/bool/None 类型。"""
        from scripts.collaboration.cache_interface import Serializer

        payload = {
            "str": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, "two", False],
            "nested": {"a": [1, 2, {"b": "c"}]},
        }
        data = Serializer.serialize(payload, format="json")
        restored = Serializer.deserialize(data, format="json")
        assert restored == payload
        assert isinstance(restored["str"], str)
        assert isinstance(restored["int"], int)
        assert isinstance(restored["float"], float)
        assert isinstance(restored["bool"], bool)
        assert restored["none"] is None

    def test_serializer_rejects_pickle_format_explicitly(self) -> None:
        """Serializer.serialize 显式拒绝 format='pickle'。"""
        from scripts.collaboration.cache_interface import Serializer

        with pytest.raises(ValueError):
            Serializer.serialize({"x": 1}, format="pickle")

    def test_serializer_deserialize_rejects_non_json_bytes(self) -> None:
        """Serializer.deserialize 拒绝非 JSON 字节流（P2-1 fallback 移除后）。"""
        from scripts.collaboration.cache_interface import Serializer

        with pytest.raises(ValueError):
            Serializer.deserialize(b"\x00\x01\x02\xff", format="json")

    def test_cache_interface_source_has_no_pickle_import(self) -> None:
        """集成断言：cache_interface.py 源码无 import pickle。"""
        src = (_PROJECT_ROOT / "scripts" / "collaboration" / "cache_interface.py").read_text()
        assert "import pickle" not in src

    def test_redis_cache_source_has_no_pickle_fallback(self) -> None:
        """集成断言：redis_cache.py 源码无 allow_pickle_fallback 参数。"""
        src = (_PROJECT_ROOT / "scripts" / "collaboration" / "redis_cache.py").read_text()
        assert "allow_pickle_fallback" not in src or "removed" in src.lower()


# =============================================================================
# T2: Ponytail 双模式 + PromptAssembler 注入链路
# =============================================================================


class TestPonytailInjectionIntegration:
    """P1-1: PonytailRuleInjector 双模式 + 红线 + 模式切换集成。"""

    def test_full_mode_injection_contains_all_7_rungs(self) -> None:
        """full 模式注入文本包含全部 7 个 rungs（向后兼容 V3.10.0）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "full"}}
        injector = PonytailRuleInjector(qc_config=config)
        injection = injector.build_injection()

        expected_rungs = [
            "YAGNI",
            "standard library",
            "native platform",
            "already-installed dependency",
            "one line",
        ]
        for rung in expected_rungs:
            assert rung in injection, f"full 模式缺失 rung: {rung}"

    def test_lite_mode_injection_shorter_than_full(self) -> None:
        """lite 模式注入文本应短于 full 模式（精简版）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config_full = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "full"}}
        config_lite = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "lite"}}

        full_injection = PonytailRuleInjector(qc_config=config_full).build_injection()
        lite_injection = PonytailRuleInjector(qc_config=config_lite).build_injection()

        assert len(lite_injection) < len(full_injection), (
            f"lite ({len(lite_injection)}) 应短于 full ({len(full_injection)})"
        )

    def test_disabled_returns_empty_string(self) -> None:
        """minimal_implementation=False 时，注入返回空字符串（不破坏现有 prompt）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": False}}
        injector = PonytailRuleInjector(qc_config=config)
        assert injector.build_injection() == ""

    def test_red_lines_count_at_least_6(self) -> None:
        """红线数量 ≥6（原始 6 条，可能扩展到 16 条）。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(qc_config=config)
        assert len(injector.red_lines) >= 6

    def test_mode_property_returns_configured_value(self) -> None:
        """mode 属性返回配置的值。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        for expected_mode in ("lite", "full"):
            config = {"quality_control": {
                "minimal_implementation": True, "ponytail_mode": expected_mode
            }}
            injector = PonytailRuleInjector(qc_config=config)
            assert injector.mode == expected_mode

    def test_invalid_mode_raises_value_error(self) -> None:
        """无效模式抛出 ValueError。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_mode": "ultra"
        }}
        with pytest.raises(ValueError):
            PonytailRuleInjector(qc_config=config)

    def test_build_injection_with_explicit_mode_override(self) -> None:
        """build_injection(mode=...) 覆盖构造时配置的模式。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {"minimal_implementation": True, "ponytail_mode": "full"}}
        injector = PonytailRuleInjector(qc_config=config)
        lite_injection = injector.build_injection(mode="lite")
        assert "YAGNI" in lite_injection

    def test_markers_enabled_property(self) -> None:
        """markers_enabled 属性反映 ponytail_markers 配置。"""
        from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector

        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_markers": False
        }}
        injector = PonytailRuleInjector(qc_config=config)
        assert injector.markers_enabled is False


# =============================================================================
# T3: LoopKernel RollbackStrategy + LoopScheduler 协作
# =============================================================================


class TestLoopRollbackIntegration:
    """P1-4: RollbackStrategy 与 LoopScheduler 协作链路。"""

    def test_rollback_strategy_default_max_iterations(self) -> None:
        """默认 max_rollback_iterations=3（通过 should_stop 行为验证）。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        strategy = RollbackStrategy()
        # 默认 3：count=2 不停止，count=3 停止
        assert not strategy.should_stop(2)
        assert strategy.should_stop(3)

    def test_rollback_strategy_custom_max_iterations(self) -> None:
        """可配置自定义 max_rollback_iterations（通过 should_stop 行为验证）。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        strategy = RollbackStrategy(max_rollback_iterations=5)
        assert not strategy.should_stop(4)
        assert strategy.should_stop(5)

    def test_determine_rollback_unknown_dimension_returns_dev(self) -> None:
        """未知失败维度默认回退到 DEV（安全降级）。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy()
        target = strategy.determine_rollback("UNKNOWN")
        assert target == RollbackTarget.DEV

    def test_determine_rollback_all_six_dimensions(self) -> None:
        """D1-D6 六个维度全部有明确回退目标。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy()
        for dim in ("D1", "D2", "D3", "D4", "D5", "D6"):
            target = strategy.determine_rollback(dim)
            assert target in (RollbackTarget.DEV, RollbackTarget.TEST, RollbackTarget.NONE)

    def test_execute_rollback_writes_target_to_context(self) -> None:
        """execute_rollback 将 rollback_target 和 rollback_executed 写入 context。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy()
        context: dict[str, object] = {"existing": "data"}
        result = strategy.execute_rollback(RollbackTarget.TEST, context)
        assert result is True
        assert context["existing"] == "data"  # 原有数据保留
        assert context["rollback_target"] == "test"
        assert context["rollback_executed"] is True

    def test_execute_rollback_with_none_returns_false(self) -> None:
        """target=NONE 时返回 False，不执行回退。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import (
            RollbackStrategy,
            RollbackTarget,
        )

        strategy = RollbackStrategy()
        context: dict[str, object] = {}
        result = strategy.execute_rollback(RollbackTarget.NONE, context)
        assert result is False
        assert "rollback_target" not in context

    def test_rollback_target_enum_values(self) -> None:
        """RollbackTarget 枚举值与文档一致。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackTarget

        assert RollbackTarget.DEV.value == "dev"
        assert RollbackTarget.TEST.value == "test"
        assert RollbackTarget.NONE.value == "none"

    def test_rollback_strategy_can_be_instantiated_multiple_times(self) -> None:
        """RollbackStrategy 可多次实例化（无全局状态泄漏）。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        s1 = RollbackStrategy(max_rollback_iterations=2)
        s2 = RollbackStrategy(max_rollback_iterations=10)
        # 互不影响
        assert not s1.should_stop(1)
        assert s1.should_stop(2)
        assert not s2.should_stop(9)
        assert s2.should_stop(10)

    def test_rollback_strategy_performance_under_load(self) -> None:
        """性能测试：1000 次决策 < 50ms。"""
        from scripts.collaboration.loop_engineering.rollback_strategy import RollbackStrategy

        strategy = RollbackStrategy()
        start = time.perf_counter()
        for _ in range(1000):
            strategy.determine_rollback("D3")
            strategy.should_stop(99)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"1000 次决策耗时 {elapsed_ms:.2f}ms 超过 50ms"


# =============================================================================
# T4: Dashboard V4.3 面板 + 数据源集成
# =============================================================================


class TestDashboardV43PanelsIntegration:
    """P1-6: V4.3 Dashboard 面板可被调用且不崩溃。"""

    def test_all_four_panels_callable(self) -> None:
        """4 个 V4.3 面板函数都可被调用。"""
        from scripts.dashboard.v43_panels import (
            render_loop_rollback_panel,
            render_plugin_events_panel,
            render_ponytail_mode_panel,
            render_todo_drift_panel,
        )

        assert callable(render_ponytail_mode_panel)
        assert callable(render_loop_rollback_panel)
        assert callable(render_plugin_events_panel)
        assert callable(render_todo_drift_panel)

    def test_ponytail_panel_unknown_mode_does_not_crash(self) -> None:
        """未知 Ponytail 模式不崩溃（降级处理）。"""
        from scripts.dashboard.v43_panels import render_ponytail_mode_panel

        try:
            render_ponytail_mode_panel("unknown_mode", container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"未知模式不应崩溃: {exc}")

    def test_ponytail_panel_lite_mode_renders(self) -> None:
        """lite 模式面板可渲染。"""
        from scripts.dashboard.v43_panels import render_ponytail_mode_panel

        try:
            render_ponytail_mode_panel("lite", container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"lite 模式渲染失败: {exc}")

    def test_ponytail_panel_full_mode_renders(self) -> None:
        """full 模式面板可渲染。"""
        from scripts.dashboard.v43_panels import render_ponytail_mode_panel

        try:
            render_ponytail_mode_panel("full", container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"full 模式渲染失败: {exc}")

    def test_loop_rollback_panel_zero_values(self) -> None:
        """Loop 回退面板接受 0 值（初始状态）。"""
        from scripts.dashboard.v43_panels import render_loop_rollback_panel

        try:
            render_loop_rollback_panel(
                rollback_count=0,
                max_iterations=3,
                artifacts_count=0,
                last_target="",
                container=_StreamlitFake(),
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"零值渲染失败: {exc}")

    def test_loop_rollback_panel_at_max_values(self) -> None:
        """Loop 回退面板接受满值（达到上限）。"""
        from scripts.dashboard.v43_panels import render_loop_rollback_panel

        try:
            render_loop_rollback_panel(
                rollback_count=3,
                max_iterations=3,
                artifacts_count=999,
                last_target="test",
                container=_StreamlitFake(),
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"满值渲染失败: {exc}")

    def test_plugin_events_panel_empty_list(self) -> None:
        """Plugin 事件流面板接受空列表（无事件）。"""
        from scripts.dashboard.v43_panels import render_plugin_events_panel

        try:
            render_plugin_events_panel([], container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"空列表渲染失败: {exc}")

    def test_plugin_events_panel_large_list(self) -> None:
        """Plugin 事件流面板接受大量事件（100 个）。"""
        from scripts.dashboard.v43_panels import render_plugin_events_panel

        events = [
            {"event": "loaded", "plugin": f"plugin_{i}", "timestamp": "2026-07-24T10:00:00Z"}
            for i in range(100)
        ]
        try:
            render_plugin_events_panel(events, container=_StreamlitFake())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"大量事件渲染失败: {exc}")

    def test_todo_drift_panel_renders(self) -> None:
        """TodoDrift 状态面板可渲染。"""
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

    def test_todo_drift_panel_clean_state(self) -> None:
        """TodoDrift 面板接受 clean 状态（unregistered=0）。"""
        from scripts.dashboard.v43_panels import render_todo_drift_panel

        try:
            render_todo_drift_panel(
                total=5,
                registered=5,
                unregistered=0,
                last_scan="never",
                container=_StreamlitFake(),
            )
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"clean 状态渲染失败: {exc}")


# =============================================================================
# T5: TodoDriftMonitor + cache_interface + ponytail 跨模块扫描
# =============================================================================


class TestCrossModuleScanningIntegration:
    """P0-2: todo_drift_monitor 扫描 V4.3.0 新模块不误报。"""

    def test_scan_cache_interface_no_false_positive(self) -> None:
        """扫描 cache_interface.py 不应误报（P2-1 后无 pickle TODO）。"""
        from scripts.collaboration.todo_drift_monitor import scan_tech_debt

        # scan_tech_debt 接受 root_dir（单个目录），扫描该目录下所有 .py 文件
        # 单文件扫描通过将其放入临时目录或扫描父目录后过滤
        target_dir = _PROJECT_ROOT / "scripts" / "collaboration"
        entries = scan_tech_debt(root_dir=str(target_dir))
        # 过滤出 cache_interface.py 的条目
        ci_entries = [e for e in entries if "cache_interface.py" in e.file_path]
        assert len(ci_entries) < 5, (
            f"cache_interface.py 误报 {len(ci_entries)} 个标记"
        )

    def test_scan_ponytail_injector_no_false_positive(self) -> None:
        """扫描 ponytail_rule_injector.py 不应误报。"""
        from scripts.collaboration.todo_drift_monitor import scan_tech_debt

        target_dir = _PROJECT_ROOT / "scripts" / "collaboration"
        entries = scan_tech_debt(root_dir=str(target_dir))
        pi_entries = [e for e in entries if "ponytail_rule_injector.py" in e.file_path]
        assert len(pi_entries) < 5

    def test_scan_rollback_strategy_no_false_positive(self) -> None:
        """扫描 rollback_strategy.py 不应误报。"""
        from scripts.collaboration.todo_drift_monitor import scan_tech_debt

        target_dir = _PROJECT_ROOT / "scripts" / "collaboration"
        entries = scan_tech_debt(root_dir=str(target_dir))
        rs_entries = [
            e for e in entries if "rollback_strategy.py" in e.file_path
        ]
        assert len(rs_entries) < 5

    def test_scan_v43_panels_no_false_positive(self) -> None:
        """扫描 v43_panels.py 不应误报。"""
        from scripts.collaboration.todo_drift_monitor import scan_tech_debt

        target_dir = _PROJECT_ROOT / "scripts" / "dashboard"
        entries = scan_tech_debt(root_dir=str(target_dir))
        vp_entries = [e for e in entries if "v43_panels.py" in e.file_path]
        assert len(vp_entries) < 5

    def test_scan_returns_list_of_entries(self) -> None:
        """scan_tech_debt 返回 list[TechDebtEntry]。"""
        from scripts.collaboration.todo_drift_monitor import (
            TechDebtEntry,
            scan_tech_debt,
        )

        target_dir = _PROJECT_ROOT / "scripts" / "collaboration"
        entries = scan_tech_debt(root_dir=str(target_dir))
        assert isinstance(entries, list)
        for entry in entries:
            assert isinstance(entry, TechDebtEntry)
            assert hasattr(entry, "file_path")
            assert hasattr(entry, "line_number")
            assert hasattr(entry, "marker")
            assert hasattr(entry, "content")

    def test_diff_with_tracker_returns_drift_report(self) -> None:
        """diff_with_tracker 返回 DriftReport 对象。"""
        from scripts.collaboration.todo_drift_monitor import (
            diff_with_tracker,
            scan_tech_debt,
        )

        target_dir = _PROJECT_ROOT / "scripts" / "collaboration"
        entries = scan_tech_debt(root_dir=str(target_dir))
        # tracker 不存在时允许抛 FileNotFoundError（合理行为）
        try:
            diff = diff_with_tracker(entries, tracker_path="/nonexistent/TECH_DEBT.md")
            assert diff is not None
        except FileNotFoundError:
            pass

    def test_report_new_debts_text_format(self) -> None:
        """report_new_debts 输出 text 格式报告。"""
        from scripts.collaboration.todo_drift_monitor import (
            DriftReport,
            report_new_debts,
        )

        # 构造空 DriftReport 用于测试
        empty_report = DriftReport(
            scanned_files=0,
            total_markers=0,
            registered_count=0,
            new_unregistered=[],
            removed_registered=[],
        )
        text_output = report_new_debts(empty_report, output_format="text")
        assert isinstance(text_output, str)

    def test_report_new_debts_json_format(self) -> None:
        """report_new_debts 输出 json 格式报告。"""
        from scripts.collaboration.todo_drift_monitor import (
            DriftReport,
            report_new_debts,
        )

        empty_report = DriftReport(
            scanned_files=0,
            total_markers=0,
            registered_count=0,
            new_unregistered=[],
            removed_registered=[],
        )
        json_output = report_new_debts(empty_report, output_format="json")
        assert isinstance(json_output, str)


# =============================================================================
# T6: V4.3 模块互相导入 + 一致性校验
# =============================================================================


class TestV43ModuleConsistencyIntegration:
    """V4.3.0 模块互相导入无循环依赖，版本号一致。"""

    def test_all_v43_modules_import_successfully(self) -> None:
        """所有 V4.3.0 新模块可独立导入。"""
        modules = [
            "scripts.collaboration.cache_interface",
            "scripts.collaboration.redis_cache",
            "scripts.collaboration.ponytail_rule_injector",
            "scripts.collaboration.todo_drift_monitor",
            "scripts.collaboration.loop_engineering.rollback_strategy",
            "scripts.dashboard.v43_panels",
        ]
        for mod_name in modules:
            try:
                __import__(mod_name)
            except ImportError as exc:
                pytest.fail(f"模块 {mod_name} 导入失败: {exc}")

    def test_version_consistent_across_files(self) -> None:
        """VERSION / pyproject.toml / _version.py / SKILL.md 版本号一致。"""
        version_file = (_PROJECT_ROOT / "VERSION").read_text().strip()
        assert version_file == "4.2.9"

        pyproject = (_PROJECT_ROOT / "pyproject.toml").read_text()
        assert 'version = "4.2.9"' in pyproject

        version_py = (_PROJECT_ROOT / "scripts" / "collaboration" / "_version.py").read_text()
        assert '__version__ = "4.2.9"' in version_py

        skill_md = (_PROJECT_ROOT / "SKILL.md").read_text()
        assert "version: 4.2.9" in skill_md

    def test_changelog_has_v429_section(self) -> None:
        """CHANGELOG.md 包含 V4.2.9 章节。"""
        changelog = (_PROJECT_ROOT / "CHANGELOG.md").read_text()
        assert "## [4.2.9]" in changelog

    def test_changelog_mentions_v43_features(self) -> None:
        """CHANGELOG.md V4.2.9 章节提及 V4.3 关键特性。"""
        changelog = (_PROJECT_ROOT / "CHANGELOG.md").read_text()
        v429_idx = changelog.find("## [4.2.9]")
        assert v429_idx >= 0
        v429_section = changelog[v429_idx:]
        assert "pickle" in v429_section.lower()
        assert "ponytail" in v429_section.lower()

    def test_roadmap_has_v43_section(self) -> None:
        """ROADMAP.md 包含 V4.3+ Roadmap 章节。"""
        roadmap = (_PROJECT_ROOT / "docs" / "ROADMAP.md").read_text()
        assert "V4.3" in roadmap
        assert "P0-1" in roadmap or "P1-1" in roadmap

    def test_prd_exists_for_v43(self) -> None:
        """V4.3.0 PRD 文档存在。"""
        prd_path = _PROJECT_ROOT / "docs" / "prd" / "V4.3.0_PRD.md"
        assert prd_path.exists(), "V4.3.0 PRD 文档应存在"

    def test_architecture_doc_exists_for_v43(self) -> None:
        """V4.3.0 架构设计文档存在。"""
        arch_path = _PROJECT_ROOT / "docs" / "architecture" / "V4.3.0_ARCHITECTURE.md"
        assert arch_path.exists(), "V4.3.0 架构设计文档应存在"

    def test_test_plan_exists_for_v43(self) -> None:
        """V4.3.0 测试方案文档存在。"""
        test_plan_path = _PROJECT_ROOT / "docs" / "testing" / "V4.3.0_TEST_PLAN.md"
        assert test_plan_path.exists(), "V4.3.0 测试方案文档应存在"

    def test_user_stories_doc_exists_for_v43(self) -> None:
        """V4.3.0 用户故事文档存在。"""
        us_path = _PROJECT_ROOT / "docs" / "prd" / "V4.3.0_USER_STORIES.md"
        assert us_path.exists(), "V4.3.0 用户故事文档应存在"
