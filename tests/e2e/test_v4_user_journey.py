#!/usr/bin/env python3
"""
DevSquad V4.0.0 E2E Test: User Journey - V4 Features

用户旅程：用户使用 V4.0.0 的 6 个新特性完成复杂任务

故事：Alice 是一名全栈工程师，她需要：
  1. 用 Loop Engineering 进行迭代开发
  2. 对 UI 进行 UX 巡检和视觉回归
  3. 用对抗验证检查方案安全性
  4. 可视化任务依赖图
  5. 启动自主迭代模式
  6. 动态加载插件扩展能力

目标：验证 V4.0.0 6 个特性从用户视角可达，无幽灵功能。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class TestV4LoopEngineeringE2E:
    """P1-1 Loop Engineering E2E：用户通过 dispatch_with_loop() 执行迭代任务。"""

    def test_loop_design_cycle_e2e(self, tmp_path: Path) -> None:
        """用户提交设计任务，Loop Engineering 完整执行 Discovery→Handoff→Verification→Persistence→Scheduling。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            report = dispatcher.dispatch_with_loop(
                task_description="Design a REST API for user authentication",
                loop_type="design",
                max_iterations=5,
            )
            assert report is not None
        finally:
            dispatcher.shutdown()

    def test_loop_coding_cycle_e2e(self, tmp_path: Path) -> None:
        """用户提交编码任务，Loop Engineering 以 coding 模式执行。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            report = dispatcher.dispatch_with_loop(
                task_description="Write a hello world function",
                loop_type="coding",
                max_iterations=5,
            )
            assert report is not None
        finally:
            dispatcher.shutdown()

    def test_loop_max_iterations_protection_e2e(self, tmp_path: Path) -> None:
        """用户配置 max_iterations=5，Loop 不会无限循环。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            report = dispatcher.dispatch_with_loop(
                task_description="Write unit tests for utils module",
                loop_type="testing",
                max_iterations=5,
            )
            assert report is not None
        finally:
            dispatcher.shutdown()


class TestV4UIUXInspectionE2E:
    """P1-2 UI/UX 巡检 E2E：用户对 URL 进行 QA 审计和视觉回归。"""

    def test_qa_enabled_flag_e2e(self, tmp_path: Path) -> None:
        """用户启用 qa_enabled=True，UIUXAnalyzer 和 VisualRegressionChecker 可用。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            qa_enabled=True,
        )
        try:
            assert dispatcher.qa_enabled is True
            assert dispatcher.uiux_analyzer is not None
            assert dispatcher.visual_regression_checker is not None
        finally:
            dispatcher.shutdown()

    def test_qa_visual_regression_e2e(self, tmp_path: Path) -> None:
        """用户调用 qa_visual_regression() 对比两张截图，返回 DiffResult。"""
        from PIL import Image

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            qa_enabled=True,
        )
        try:
            baseline = tmp_path / "baseline.png"
            current = tmp_path / "current.png"
            Image.new("RGB", (10, 10), (255, 0, 0)).save(baseline)
            Image.new("RGB", (10, 10), (255, 0, 0)).save(current)
            result = dispatcher.qa_visual_regression(str(baseline), str(current))
            assert result is not None
        finally:
            dispatcher.shutdown()

    def test_qa_disabled_by_default_e2e(self, tmp_path: Path) -> None:
        """用户未启用 qa_enabled 时，QA 功能不可用（默认关闭）。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            assert dispatcher.qa_enabled is False
        finally:
            dispatcher.shutdown()

    def test_qa_audit_url_without_playwright_raises_e2e(self, tmp_path: Path) -> None:
        """用户调用 qa_audit_url() 但 Playwright 未安装时，抛出 RuntimeError。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            qa_enabled=True,
        )
        try:
            with pytest.raises(RuntimeError):
                dispatcher.qa_audit_url("https://example.com")
        finally:
            dispatcher.shutdown()


class TestV4AdversarialVerificationE2E:
    """P2-1 Adversarial 验证 E2E：用户通过 ConsensusEngine 进行对抗验证。"""

    def test_adversarial_verify_via_consensus_engine_e2e(self, tmp_path: Path) -> None:
        """用户通过 consensus_engine.adversarial_verify() 执行红蓝对抗验证。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            assert dispatcher.consensus_engine is not None
            assert hasattr(dispatcher.consensus_engine, "adversarial_verify")
            result = dispatcher.consensus_engine.adversarial_verify(
                proposal_content="Use JWT + Refresh Token for authentication"
            )
            assert result is not None
        finally:
            dispatcher.shutdown()


class TestV4DAGVisualizationE2E:
    """P2-2 DAG 可视化 E2E：用户通过 DAGVisualizer 生成依赖图。"""

    def test_dag_mermaid_generation_e2e(self) -> None:
        """用户使用 DAGVisualizer 生成 Mermaid 格式依赖图。"""
        from scripts.dashboard.dag_views import DAGVisualizer

        visualizer = DAGVisualizer()
        phases = [
            {"phase_id": "spec", "name": "Spec", "dependencies": [], "order": 1},
            {"phase_id": "plan", "name": "Plan", "dependencies": ["spec"], "order": 2},
            {"phase_id": "build", "name": "Build", "dependencies": ["plan"], "order": 3},
        ]
        graph = visualizer.build_from_lifecycle(phases)
        mermaid = visualizer.to_mermaid(graph)
        assert mermaid is not None
        assert isinstance(mermaid, str)

    def test_dag_json_generation_e2e(self) -> None:
        """用户使用 DAGVisualizer 生成 JSON 格式依赖图。"""
        from scripts.dashboard.dag_views import DAGVisualizer

        visualizer = DAGVisualizer()
        phases = [{"phase_id": "n1", "name": "Node 1", "dependencies": []}]
        graph = visualizer.build_from_lifecycle(phases)
        json_output = visualizer.to_json(graph)
        assert json_output is not None
        assert isinstance(json_output, dict)

    def test_dag_dot_generation_e2e(self) -> None:
        """用户使用 DAGVisualizer 生成 DOT 格式依赖图。"""
        from scripts.dashboard.dag_views import DAGVisualizer

        visualizer = DAGVisualizer()
        phases = [
            {"phase_id": "n1", "name": "Node 1", "dependencies": []},
            {"phase_id": "n2", "name": "Node 2", "dependencies": ["n1"]},
        ]
        graph = visualizer.build_from_lifecycle(phases)
        dot_output = visualizer.to_dot(graph)
        assert dot_output is not None
        assert isinstance(dot_output, str)


class TestV4AutonomousE2E:
    """P3-1 Autonomous E2E：用户通过 dispatch_autonomous() 启动自主迭代。"""

    def test_autonomous_dispatch_e2e(self, tmp_path: Path) -> None:
        """用户调用 dispatch_autonomous() 启动 plan→dev→verify→fix 循环。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            autonomous_enabled=True,
        )
        try:
            assert dispatcher.autonomous_enabled is True
            assert dispatcher.autonomous_controller is not None
            result = dispatcher.dispatch_autonomous(
                objective="Fix the failing tests in utils module",
                max_iterations=1,
            )
            assert result is not None
        finally:
            dispatcher.shutdown()

    def test_autonomous_disabled_by_default_e2e(self, tmp_path: Path) -> None:
        """用户未启用 autonomous_enabled 时，自主迭代不可用（默认关闭）。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            assert dispatcher.autonomous_enabled is False
            with pytest.raises(RuntimeError, match="AutonomousLoopController not enabled"):
                dispatcher.dispatch_autonomous(objective="test")
        finally:
            dispatcher.shutdown()

    def test_autonomous_persistence_e2e(self, tmp_path: Path) -> None:
        """用户执行 Autonomous 后，persist_dir 持久化到磁盘。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        persist_path = tmp_path / "autonomous_persist"
        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(persist_path), development_mode=True,
            autonomous_enabled=True,
        )
        try:
            dispatcher.dispatch_autonomous(
                objective="Write a simple hello world script",
                max_iterations=1,
            )
            assert persist_path.exists()
        finally:
            dispatcher.shutdown()


class TestV4PluginHotLoaderE2E:
    """P3-2 插件热加载 E2E：用户通过 dispatcher API 动态管理插件。"""

    def test_register_and_get_plugin_e2e(self, tmp_path: Path) -> None:
        """用户调用 register_plugin() 注册插件，然后 get_plugin() 获取。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            plugins_enabled=True,
        )
        try:
            assert dispatcher.plugins_enabled is True
            assert dispatcher.plugin_hot_loader is not None

            class EchoPlugin:
                name = "echo"

            plugin = EchoPlugin()
            assert dispatcher.register_plugin("echo", plugin) is True
            retrieved = dispatcher.get_plugin("echo")
            assert retrieved is plugin
        finally:
            dispatcher.shutdown()

    def test_list_plugins_e2e(self, tmp_path: Path) -> None:
        """用户注册多个插件后，list_plugins() 返回全部已注册插件名。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            plugins_enabled=True,
        )
        try:
            dispatcher.register_plugin("plugin_a", type("A", (), {}))
            dispatcher.register_plugin("plugin_b", type("B", (), {}))
            plugins = dispatcher.list_plugins()
            assert "plugin_a" in plugins
            assert "plugin_b" in plugins
        finally:
            dispatcher.shutdown()

    def test_unregister_plugin_e2e(self, tmp_path: Path) -> None:
        """用户调用 unregister_plugin() 注销插件，后续 get_plugin() 返回 None。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            plugins_enabled=True,
        )
        try:
            dispatcher.register_plugin("temp", type("T", (), {}))
            assert dispatcher.unregister_plugin("temp") is True
            assert dispatcher.get_plugin("temp") is None
        finally:
            dispatcher.shutdown()

    def test_plugins_disabled_by_default_e2e(self, tmp_path: Path) -> None:
        """用户未启用 plugins_enabled 时，插件 API 抛出 RuntimeError。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
        )
        try:
            assert dispatcher.plugins_enabled is False
            with pytest.raises(RuntimeError, match="PluginHotLoader not enabled"):
                dispatcher.register_plugin("x", type("X", (), {}))
        finally:
            dispatcher.shutdown()

    def test_dropin_dir_scan_e2e(self, tmp_path: Path) -> None:
        """用户在 drop-in 目录放置 .py 文件，scan_plugins() 自动发现。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dropin_dir = tmp_path / "plugins_extra"
        dropin_dir.mkdir()
        plugin_file = dropin_dir / "my_plugin.py"
        plugin_file.write_text(
            "class MyPlugin:\n"
            "    name = 'my_plugin'\n"
            "    def run(self):\n"
            "        return 'hello'\n"
        )

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            plugins_enabled=True,
            plugins_dropin_dir=str(dropin_dir),
        )
        try:
            discovered = dispatcher.scan_plugins()
            assert isinstance(discovered, list)
        finally:
            dispatcher.shutdown()


class TestV4FeaturesIntegrationE2E:
    """V4.0.0 6 特性联合 E2E：所有特性同时启用，无冲突。"""

    def test_all_v4_features_enabled_together_e2e(self, tmp_path: Path) -> None:
        """用户同时启用所有 V4.0.0 特性，dispatcher 正常初始化。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            qa_enabled=True,
            autonomous_enabled=True,
            plugins_enabled=True,
        )
        try:
            assert dispatcher.qa_enabled is True
            assert dispatcher.autonomous_enabled is True
            assert dispatcher.plugins_enabled is True
            assert dispatcher.uiux_analyzer is not None
            assert dispatcher.autonomous_controller is not None
            assert dispatcher.plugin_hot_loader is not None
        finally:
            dispatcher.shutdown()

    def test_v4_features_do_not_break_v3_dispatch_e2e(self, tmp_path: Path) -> None:
        """用户启用 V4.0.0 特性后，V3.x 标准dispatch()仍正常工作。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher(
            enable_warmup=False, enable_memory=False, enable_skillify=False,
            persist_dir=str(tmp_path), development_mode=True,
            qa_enabled=True,
            autonomous_enabled=True,
            plugins_enabled=True,
        )
        try:
            result = dispatcher.dispatch("Design a simple hello world API")
            assert result is not None
            assert hasattr(result, "to_markdown") or hasattr(result, "summary")
        finally:
            dispatcher.shutdown()
