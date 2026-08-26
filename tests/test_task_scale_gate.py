#!/usr/bin/env python3
"""
Unit tests for TaskScaleGate (V4.5.2 §3).

Covers T1–T6 from V4.5.2_ARCHITECTURE.md §3.5 / V4.5.2_TEST_PLAN §3.4:
  T1 large: 跨 ≥3 模块 → L
  T2 medium: 2 模块/3-4 文件 → M
  T3 small: 单文件/问答 → S
  T4 default: 无法判定 → M (保底)
  T5 override: --all-roles → L
  T6 precedence: gate(第一道) 先于 role_matcher(第二道)
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from scripts.collaboration.task_scale_gate import (  # noqa: E402
    L_MAX_ROLES,
    M_MAX_ROLES,
    ORCHESTRATOR_AUTO,
    ORCHESTRATOR_CONSENSUS,
    ORCHESTRATOR_MINI,
    S_MAX_ROLES,
    TaskScaleGate,
    get_call_counter_er,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# T1 — Large (L)
# ---------------------------------------------------------------------------


class TestT1Large:
    def test_scale_large_cross_3_modules(self):
        """跨 ≥3 模块 → L."""
        gate = TaskScaleGate()
        # explicit module_count=3 triggers L
        scale = gate.decide(
            "需要 auth、payment、inventory 联动",
            module_count=3,
        )
        assert scale.level == "L"
        assert scale.max_roles == L_MAX_ROLES
        assert scale.orchestrator == ORCHESTRATOR_CONSENSUS
        assert scale.single_role is False

    def test_scale_large_5_files(self):
        """≥5 文件 → L."""
        gate = TaskScaleGate()
        scale = gate.decide("修改 5 个文件 foo.py, bar.py, baz.py, x.py, y.py")
        assert scale.level == "L"

    def test_scale_large_project_hint(self):
        """完整流程 / 新建项目 关键词 → L."""
        gate = TaskScaleGate()
        for hint in ["完整流程", "整体重写", "新建项目", "从零搭建", "--full"]:
            scale = gate.decide(f"task: {hint}")
            assert scale.level == "L", f"hint={hint!r} should be L"

    def test_scale_large_via_all_roles(self):
        """--all-roles 显式 → L."""
        gate = TaskScaleGate()
        scale = gate.decide("任何任务", all_roles=True)
        assert scale.level == "L"
        assert "all-roles" in scale.signal


# ---------------------------------------------------------------------------
# T2 — Medium (M)
# ---------------------------------------------------------------------------


class TestT2Medium:
    def test_scale_medium_2_modules(self):
        """2 模块 → M."""
        gate = TaskScaleGate()
        scale = gate.decide("需要 auth 和 payment 2 个模块的联动")
        assert scale.level == "M"
        assert scale.max_roles == M_MAX_ROLES
        assert scale.orchestrator == ORCHESTRATOR_MINI

    def test_scale_medium_3_to_4_files(self):
        """3-4 文件 → M."""
        gate = TaskScaleGate()
        scale = gate.decide("修改 3 个文件")
        assert scale.level == "M"

    def test_scale_medium_via_hint(self):
        """集成测试/联调 等中等关键词 → M."""
        gate = TaskScaleGate()
        for hint in ["两个模块", "联调", "集成测试", "端到端", "单功能开发"]:
            scale = gate.decide(f"task: {hint}")
            assert scale.level == "M", f"hint={hint!r} should be M"


# ---------------------------------------------------------------------------
# T3 — Small (S)
# ---------------------------------------------------------------------------


class TestT3Small:
    def test_scale_small_one_file(self):
        """files=1 → S."""
        gate = TaskScaleGate()
        scale = gate.decide("修改 main.py 这个单文件")
        assert scale.level == "S"
        assert scale.max_roles == S_MAX_ROLES
        assert scale.orchestrator == ORCHESTRATOR_AUTO
        assert scale.single_role is True  # S always single-role

    def test_scale_small_qa(self):
        """纯问答 → S."""
        gate = TaskScaleGate()
        for hint in ["什么是 X", "怎么用 Y", "如何实现 Z"]:
            scale = gate.decide(hint)
            assert scale.level == "S", f"hint={hint!r} should be S"

    def test_scale_small_bug_fix(self):
        """bug 修复/简单问答 → S."""
        gate = TaskScaleGate()
        for hint in ["修复这个 bug", "简单问题"]:
            scale = gate.decide(hint)
            assert scale.level == "S", f"hint={hint!r} should be S"

    def test_scale_small_via_explicit_override(self):
        """显式 --scale S 覆盖 → S."""
        gate = TaskScaleGate()
        scale = gate.decide("任何复杂任务", scale_override="S")
        assert scale.level == "S"
        assert "explicit" in scale.signal


# ---------------------------------------------------------------------------
# T4 — Default fallback
# ---------------------------------------------------------------------------


class TestT4DefaultFallback:
    def test_scale_default_fallback_to_medium(self):
        """无明确信号 → 保底 M（宁可多验证）。"""
        gate = TaskScaleGate()
        scale = gate.decide("做一些事情")
        assert scale.level == "M"
        assert "default" in scale.signal or "fallback" in scale.signal

    def test_scale_default_empty_task(self):
        """空任务 → M (保底)."""
        gate = TaskScaleGate()
        scale = gate.decide("")
        assert scale.level == "M"


# ---------------------------------------------------------------------------
# T5 — Override flag
# ---------------------------------------------------------------------------


class TestT5OverrideFlag:
    def test_explicit_scale_M(self):
        gate = TaskScaleGate()
        scale = gate.decide("修复", scale_override="M")
        assert scale.level == "M"
        assert "explicit" in scale.signal

    def test_explicit_scale_L(self):
        gate = TaskScaleGate()
        scale = gate.decide("单文件 bug", scale_override="L")
        assert scale.level == "L"
        # Explicit override beats small signal

    def test_invalid_scale_override_ignored(self):
        """非 S/M/L 的 override → 忽略，走门禁判定."""
        gate = TaskScaleGate()
        scale = gate.decide("单文件 bug", scale_override="X")
        assert scale.level == "S"  # signal still matches

    def test_single_role_flag_propagates(self):
        """OrderChainDetector 的 single_role 标志可穿透."""
        gate = TaskScaleGate()
        # M with single_role=True → preserves single_role
        scale = gate.decide("跨 2 个模块", single_role=True)
        assert scale.level == "M"
        assert scale.single_role is True


# ---------------------------------------------------------------------------
# T6 — Precedence: gate runs BEFORE role_matcher
# ---------------------------------------------------------------------------


class TestT6Precedence:
    def test_gate_decides_before_role_matcher(self):
        """TaskScaleGate.decide() 在 match_roles() 之前；max_roles 用于 cap."""
        gate = TaskScaleGate()
        # L → max_roles=999
        scale_l = gate.decide("跨 3 个模块的完整流程")
        assert scale_l.max_roles >= L_MAX_ROLES or scale_l.max_roles == L_MAX_ROLES
        # S → max_roles=1
        scale_s = gate.decide("单文件 bug")
        assert scale_s.max_roles == S_MAX_ROLES

    def test_signal_explainable(self):
        """signal 必须可解释（explainability）。"""
        gate = TaskScaleGate()
        for task, expected_substr in [
            ("跨 3 个模块", "module"),
            ("foo.py 单文件", "file"),
            ("--full project", "hint"),
            ("集成测试", "hint"),
        ]:
            scale = gate.decide(task)
            assert scale.signal, f"signal empty for task={task!r}"
            assert expected_substr.lower() in scale.signal.lower(), (
                f"task={task!r} signal={scale.signal!r} expected substring={expected_substr!r}"
            )


# ---------------------------------------------------------------------------
# Anti-Ghost + 额外检查
# ---------------------------------------------------------------------------


class TestAntiGhost:
    def test_call_counter_increments(self):
        """每次 decide() 都会让 _call_counter_er 增加。"""
        before = get_call_counter_er()
        gate = TaskScaleGate()
        for _ in range(5):
            gate.decide("any task")
        after = get_call_counter_er()
        assert after - before == 5

    def test_signal_contains_useful_info(self):
        """signal 字段至少包含信号名（module/file/explicit/hint）。"""
        gate = TaskScaleGate()
        scale = gate.decide("跨 3 个模块")
        # signal should be non-empty and explain the decision
        assert scale.signal
        assert len(scale.signal) > 0
