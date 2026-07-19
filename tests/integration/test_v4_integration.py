"""V4.0.0 集成验证：确认 6 个特性全部通过 dispatcher 可触达（无幽灵功能）。

特性清单与集成路径:
- P1-1 Loop Engineering: dispatcher.dispatch_with_loop() 公共 API
- P1-2 UI/UX 巡检: qa_enabled=True + qa_audit_url()/qa_visual_regression() API
- P2-1 Adversarial 验证: ConsensusEngine.adversarial_verify() API
- P2-2 DAG 可视化: scripts/dashboard/dag_views.py DAGVisualizer
- P3-1 Autonomous: autonomous_enabled=True + dispatch_autonomous() API
- P3-2 插件热加载: plugins_enabled=True + 7 个公共 API
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher


class TestV4Integration:
    """V4.0.0 6 特性集成验证。"""

    def test_all_v4_features_disabled_by_default(self) -> None:
        """默认所有 V4.0.0 特性都关闭。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        assert d.qa_enabled is False
        assert d.autonomous_enabled is False
        assert d.plugins_enabled is False
        assert getattr(d, "uiux_analyzer", None) is None
        assert getattr(d, "visual_regression_checker", None) is None
        assert getattr(d, "autonomous_controller", None) is None
        assert getattr(d, "plugin_hot_loader", None) is None

    def test_p1_1_loop_engineering_accessible_via_dispatch_with_loop(self) -> None:
        """P1-1 Loop Engineering 通过 dispatch_with_loop() 公共 API 可触达。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        assert hasattr(d, "dispatch_with_loop")
        assert callable(d.dispatch_with_loop)

    def test_p1_1_loop_engineering_modules_importable(self) -> None:
        """P1-1 Loop Engineering 模块可导入。"""
        from scripts.collaboration.loop_engineering import (
            HandoffAdapter,
            LoopEngineeringConfig,
            LoopKernel,
            LoopType,
        )

        assert LoopKernel is not None
        assert LoopEngineeringConfig is not None
        assert HandoffAdapter is not None
        assert LoopType is not None

    def test_p1_2_qa_enabled(self, tmp_path: Path) -> None:
        """P1-2 UI/UX 巡检可通过 dispatcher 启用。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            persist_dir=str(tmp_path),
            qa_enabled=True,
        )
        assert d.qa_enabled is True
        assert d.uiux_analyzer is not None
        assert d.visual_regression_checker is not None
        assert hasattr(d, "qa_audit_url")
        assert hasattr(d, "qa_visual_regression")

    def test_p1_2_qa_disabled_raises(self) -> None:
        """P1-2 未启用时调用 qa_audit_url 抛 RuntimeError。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        with pytest.raises(RuntimeError, match="UIUXAnalyzer not enabled"):
            d.qa_audit_url("http://localhost:9999")

    def test_p2_1_adversarial_accessible_via_consensus_engine(self) -> None:
        """P2-1 Adversarial 验证通过 ConsensusEngine.adversarial_verify() 可触达。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        assert hasattr(d, "consensus_engine")
        assert hasattr(d.consensus_engine, "adversarial_verify")
        assert callable(d.consensus_engine.adversarial_verify)

    def test_p2_1_adversarial_modules_importable(self) -> None:
        """P2-1 Adversarial 模块可导入。"""
        from scripts.collaboration.adversarial_verify import (
            AdversarialVerifyMode,
            BlueTeam,
            Judge,
            RedTeam,
        )

        assert RedTeam is not None
        assert BlueTeam is not None
        assert Judge is not None
        assert AdversarialVerifyMode is not None

    def test_p2_2_dag_visualizer_accessible(self) -> None:
        """P2-2 DAG 可视化模块可导入。"""
        from scripts.dashboard.dag_views import DAGVisualizer

        assert DAGVisualizer is not None

    def test_p3_1_autonomous_enabled(self, tmp_path: Path) -> None:
        """P3-1 Autonomous 可通过 dispatcher 启用。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            persist_dir=str(tmp_path),
            autonomous_enabled=True,
        )
        assert d.autonomous_enabled is True
        assert d.autonomous_controller is not None
        assert hasattr(d, "dispatch_autonomous")

    def test_p3_1_autonomous_disabled_raises(self) -> None:
        """P3-1 未启用时调用 dispatch_autonomous 抛 RuntimeError。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        with pytest.raises(RuntimeError, match="AutonomousLoopController not enabled"):
            d.dispatch_autonomous("test objective")

    def test_p3_2_plugins_enabled(self, tmp_path: Path) -> None:
        """P3-2 插件热加载可通过 dispatcher 启用。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            persist_dir=str(tmp_path),
            plugins_enabled=True,
        )
        assert d.plugins_enabled is True
        assert d.plugin_hot_loader is not None
        # 7 个公共 API 存在
        for api in (
            "register_plugin",
            "unregister_plugin",
            "register_builtin_plugin",
            "get_plugin",
            "list_plugins",
            "scan_plugins",
            "reload_plugins",
        ):
            assert hasattr(d, api), f"Missing API: {api}"

    def test_p3_2_plugins_disabled_raises(self) -> None:
        """P3-2 未启用时调用 register_plugin 抛 RuntimeError。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        with pytest.raises(RuntimeError, match="PluginHotLoader not enabled"):
            d.register_plugin("x", object())

    def test_all_v4_features_enabled_together(self, tmp_path: Path) -> None:
        """所有 V4.0.0 特性可同时启用（无冲突）。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            persist_dir=str(tmp_path),
            qa_enabled=True,
            autonomous_enabled=True,
            plugins_enabled=True,
        )
        assert d.qa_enabled is True
        assert d.autonomous_enabled is True
        assert d.plugins_enabled is True
        assert d.uiux_analyzer is not None
        assert d.visual_regression_checker is not None
        assert d.autonomous_controller is not None
        assert d.plugin_hot_loader is not None
        # P1-1 和 P2-1/P2-2 始终可通过 API 触达（无需 flag）
        assert hasattr(d, "dispatch_with_loop")
        assert hasattr(d, "consensus_engine")

    def test_v4_version_is_current(self) -> None:
        """验证版本号已升级到 V4.x。"""
        from scripts.collaboration._version import __version__

        assert __version__.startswith("4."), f"Expected 4.x, got {__version__}"
