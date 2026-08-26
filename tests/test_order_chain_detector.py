#!/usr/bin/env python3
"""
Unit tests for OrderChainDetector (V4.5.2 §4).

Covers T1–T6 from V4.5.2_ARCHITECTURE.md §4.8 / V4.5.2_TEST_PLAN §3.5:
  T1 explicit_sequential: --sequential / sequential=True → single_role=True
  T2 role_metadata: ROLE_REGISTRY sequential_only → single
  T3 heuristic_debug: debug/root cause +3 → ≥3 触发
  T4 counterexample_override: 显式分派 "X评审+Y审查" → 关闭单链
  T5 default_parallel: 无信号 → single_role=False
  T6 user_flag_wins: user flag > chain > mode
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from scripts.collaboration.order_chain_detector import (  # noqa: E402
    OrderChainDecision,
    OrderChainDetector,
    get_call_counter_er,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# T1 — Explicit sequential flag
# ---------------------------------------------------------------------------


class TestT1ExplicitSequential:
    def test_explicit_sequential_flag(self):
        """sequential=True → single_role=True, source=user."""
        detector = OrderChainDetector()
        decision = detector.detect("any task", sequential=True)
        assert decision.single_role is True
        assert decision.source == "user"
        assert "sequential" in decision.signal

    def test_no_parallel_alias(self):
        """no_parallel=True 也触发单链."""
        detector = OrderChainDetector()
        decision = detector.detect("any task", no_parallel=True)
        assert decision.single_role is True
        assert decision.source == "user"

    def test_mode_sequential(self):
        """mode=sequential → single_role=True."""
        detector = OrderChainDetector()
        decision = detector.detect("any task", mode="sequential")
        assert decision.single_role is True
        assert decision.source == "user"
        assert "mode=sequential" in decision.signal


# ---------------------------------------------------------------------------
# T2 — Role metadata (sequential_only=True)
# ---------------------------------------------------------------------------


class TestT2RoleMetadata:
    def test_solo_coder_sequential_only(self):
        """solo-coder has sequential_only=True (per V4.5.2 model)."""
        from scripts.collaboration.models_dispatch import ROLE_REGISTRY
        assert ROLE_REGISTRY["solo-coder"].sequential_only is True

    def test_user_specifies_solo_coder_triggers_single_role(self):
        """When user specifies solo-coder, single_role=True via role_meta."""
        detector = OrderChainDetector()
        decision = detector.detect(
            "fix the bug",
            roles=["solo-coder"],
        )
        assert decision.single_role is True
        assert decision.source == "role_meta"
        assert "sequential_only=True" in decision.signal
        assert decision.role_id == "solo-coder"


# ---------------------------------------------------------------------------
# T3 — Heuristic (debug / math / refactor)
# ---------------------------------------------------------------------------


class TestT3Heuristic:
    def test_debug_keyword_triggers_single_role(self):
        """debug / root cause / 排查 触发单链（+3）."""
        detector = OrderChainDetector()
        for kw in ["debug this bug", "root cause analysis", "排查故障", "trace bug"]:
            decision = detector.detect(kw)
            assert decision.single_role is True, f"task={kw!r} should be single_role"
            assert decision.source == "heuristic"

    def test_math_derivation_triggers_single_role(self):
        """数学推导 / prove / step-by-step 触发单链."""
        detector = OrderChainDetector()
        for kw in ["prove theorem", "数学推导", "step-by-step derivation"]:
            decision = detector.detect(kw)
            assert decision.single_role is True, f"task={kw!r} should be single_role"

    def test_score_visible(self):
        """heuristic score 必须可观察（debug 可见性）."""
        detector = OrderChainDetector()
        decision = detector.detect("debug and refactor step by step")
        # debug +3 + refactor_step +2 = 5
        assert decision.score >= 3
        assert decision.single_role is True

    def test_subthreshold_score_returns_false(self):
        """score < 3 → 单链不触发."""
        detector = OrderChainDetector()
        # broad+1 only (整个项目 触发 broad_hints) — score < 3
        decision = detector.detect("请 整个项目 重写")
        assert decision.single_role is False
        assert decision.score >= 1


# ---------------------------------------------------------------------------
# T4 — Counter-example override
# ---------------------------------------------------------------------------


class TestT4CounterExample:
    def test_explicit_multi_role_assigns_parallel(self):
        """'X评审 + Y审查 + Z测试' 显式分派 → multi-role, NOT single."""
        detector = OrderChainDetector()
        decision = detector.detect("需要架构师评审 + 安全审查 + 测试设计")
        assert decision.single_role is False
        assert "counter-example" in decision.signal or decision.source == "heuristic"

    def test_consensus_mode_hint_overrides(self):
        """--consensus / 并行 / 共识 → multi-role."""
        detector = OrderChainDetector()
        for kw in [
            "请 --consensus 处理",
            "并行完成",
            "需要共识",
        ]:
            decision = detector.detect(kw)
            assert decision.single_role is False, f"task={kw!r} should be parallel"

    def test_counter_example_overrides_strong_heuristic(self):
        """即使有 debug 关键词，explicit multi-role 优先级更高."""
        detector = OrderChainDetector()
        # debug keyword + multi-role hint → counter-example wins
        decision = detector.detect("debug 这个 bug 同时需要架构师评审 + 安全审查")
        assert decision.single_role is False


# ---------------------------------------------------------------------------
# T5 — Default (no signal)
# ---------------------------------------------------------------------------


class TestT5Default:
    def test_no_signal_returns_parallel(self):
        """无信号 → 默认多 Agent (single_role=False)."""
        detector = OrderChainDetector()
        decision = detector.detect("implement feature X")
        assert decision.single_role is False
        assert decision.source == "default"

    def test_empty_task_returns_parallel(self):
        """空任务 → 默认多 Agent."""
        detector = OrderChainDetector()
        decision = detector.detect("")
        assert decision.single_role is False
        assert decision.source == "default"


# ---------------------------------------------------------------------------
# T6 — Precedence (user > chain > mode)
# ---------------------------------------------------------------------------


class TestT6Precedence:
    def test_user_sequential_overrides_heuristic(self):
        """显式 sequential 即使任务无 debug 信号也触发单链."""
        detector = OrderChainDetector()
        decision = detector.detect("build a hello world", sequential=True)
        assert decision.single_role is True
        assert decision.source == "user"

    def test_user_allow_parallel_overrides_role_meta(self):
        """allow_parallel 即使角色 sequential_only=True 也关闭单链."""
        detector = OrderChainDetector()
        decision = detector.detect(
            "fix the bug",
            roles=["solo-coder"],
            allow_parallel=True,
        )
        # user allow_parallel > role_meta sequential_only
        assert decision.single_role is False
        assert decision.source == "user"

    def test_user_sequential_overrides_role_meta(self):
        """user sequential 与 role_meta 都触发单链（结果一致）."""
        detector = OrderChainDetector()
        decision = detector.detect(
            "fix the bug",
            roles=["solo-coder"],
            sequential=True,
        )
        assert decision.single_role is True
        # user flag wins as source
        assert decision.source == "user"


# ---------------------------------------------------------------------------
# Anti-Ghost + role_id passthrough
# ---------------------------------------------------------------------------


class TestAntiGhostAndRolePassthrough:
    def test_call_counter_increments(self):
        """detect() 每次调用让 _call_counter_er 增加。"""
        before = get_call_counter_er()
        detector = OrderChainDetector()
        for _ in range(5):
            detector.detect("any")
        after = get_call_counter_er()
        assert after - before == 5

    def test_role_id_in_decision(self):
        """decision.role_id 携带角色信息."""
        detector = OrderChainDetector()
        decision = detector.detect(
            "debug this",
            roles=["solo-coder"],
            sequential=True,
        )
        assert decision.role_id == "solo-coder"

    def test_invalid_source_raises(self):
        """手动构造非法 source 必须报错（数据契约）."""
        with pytest.raises(ValueError, match="Invalid source"):
            OrderChainDecision(single_role=False, source="invalid", signal="x")
