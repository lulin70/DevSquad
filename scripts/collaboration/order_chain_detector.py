#!/usr/bin/env python3
"""
OrderChainDetector — Second-pass routing for dispatch (V4.5.2 §4).

Detects whether a task should run as a SINGLE-ROLE CHAIN (sequential)
instead of MULTI-AGENT PARALLEL.

Strong-order dependencies (debug, math derivation, step-by-step refactor)
cause multi-agent parallel to REGRESS 39-70% (upstream v2.8.4 empirical).

判定优先级（命中即停）:
  ① 用户显式 flag → single_role=True (--sequential / sequential=True)
  ② 角色元数据 sequential_only=True → single_role=True (source=role_meta)
  ③ 任务启发式 → 累计分 ≥3 且无反例 → single_role=True
  ④ 默认 → single_role=False

Anti-Ghost: _call_counter_er 每次 detect() 递增。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Module-level Anti-Ghost counter (CI: check_module_activation.py asserts > 0)
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return module activation counter (for Anti-Ghost verification)."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


@dataclass(frozen=True)
class OrderChainDecision:
    """Decision result of OrderChainDetector.detect().

    Attributes:
        single_role: True → use single-role chain (sequential).
        source: 'user' | 'role_meta' | 'heuristic' | 'default'.
        signal: explainable signal text (why this decision was made).
        score: heuristic cumulative score (debug visibility).
        role_id: role forced to single chain (when single_role=True).
    """

    single_role: bool
    source: str
    signal: str
    score: int = 0
    role_id: str | None = None

    def __post_init__(self) -> None:
        if self.source not in ("user", "role_meta", "heuristic", "default"):
            raise ValueError(
                f"Invalid source: {self.source!r} "
                f"(must be user/role_meta/heuristic/default)"
            )


# === Heuristic patterns ===

# Debug / root cause: weight +3 (highest)
_DEBUG_HINTS = re.compile(
    r"(\bdebug\b|\b根因\b|\broot[- ]cause\b|\btrace\s+bug\b|\b复现\b"
    r"|\bfix\s+bug\b|\bbug\s+fix\b|排查|定位)",
    re.IGNORECASE,
)

# Math / proof derivation: weight +3
_MATH_HINTS = re.compile(
    r"(\bprove\b|\b推导\b|\b数学\b|\b公式\b|\b证明\b|\bstep[- ]by[- ]step\b"
    r"|\b数学推导\b|\bformal proof\b)",
    re.IGNORECASE,
)

# Step-by-step refactor: weight +2
_REFACTOR_STEP_HINTS = re.compile(
    r"(\brefactor\s+step\b|\b分步\b|\b分阶段\b|\bincrementally\s+migrate\b"
    r"|\b逐步重构\b|\bmigrate\s+step\b)",
    re.IGNORECASE,
)

# Ambiguous broad task: weight +1 (only adds, never single)
_BROAD_HINTS = re.compile(
    r"(\b整体重写\b|\b重构整个\b|\b整个项目\b)",
    re.IGNORECASE,
)

# === Counter-examples (override even strong signals) ===

# Explicit multi-role assignment: must NOT be single
_MULTI_ROLE_HINTS = re.compile(
    r"(架构师评审\s*\+\s*安全审查|架构师\s*\+\s*安全\s*\+\s*测试|"
    r"\+.*审查|\+.*测试|\+.*设计)"
    r"|(需要.*?、.*?、.*?意见)",
    re.IGNORECASE,
)

# Consensus / parallel explicit
_PARALLEL_HINTS = re.compile(
    r"(--consensus|--allow-parallel|--parallel|consensus\s+mode|并行|共识)",
    re.IGNORECASE,
)


class OrderChainDetector:
    """Detect whether a task is a strong-order chain (single-role execution).

    Used by PreDispatchPipeline.execute() AFTER TaskScaleGate but BEFORE
    match_roles(), to decide whether to force single-role execution.

    Usage:
        detector = OrderChainDetector()
        decision = detector.detect(task, roles, mode, **kwargs)
        # decision.single_role → True for debug/math/sequential flag
        # decision.source → 'user' / 'role_meta' / 'heuristic' / 'default'
    """

    # Heuristic thresholds
    HEURISTIC_THRESHOLD = 3  # cumulative score ≥ this → single_role

    def __init__(self) -> None:
        self._local_call_count = 0

    def detect(
        self,
        task: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        **kwargs: object,
    ) -> OrderChainDecision:
        """Detect whether the task requires single-role chain execution.

        Args:
            task: Task description text.
            roles: User-specified role list (None → auto-match from task).
            mode: Dispatch mode (auto/parallel/sequential/consensus).
            **kwargs: Recognized flags:
                - sequential: bool (user explicit single-role)
                - no_parallel: bool (alias)
                - allow_parallel: bool (user explicit multi-role)
                - top_matched_role: str (auto-matched top role id)

        Returns:
            OrderChainDecision with single_role/source/signal/score/role_id.
        """
        _inc_call_counter_er()
        self._local_call_count += 1

        # ① User explicit flag (highest priority)
        if kwargs.get("sequential") or kwargs.get("no_parallel"):
            role_id = roles[0] if roles else kwargs.get("top_matched_role")
            return OrderChainDecision(
                single_role=True,
                source="user",
                signal="explicit --sequential / sequential=True",
                role_id=role_id,
            )

        if kwargs.get("allow_parallel"):
            return OrderChainDecision(
                single_role=False,
                source="user",
                signal="explicit --allow-parallel",
            )

        # mode=sequential is a strong user signal too
        if mode == "sequential":
            role_id = roles[0] if roles else kwargs.get("top_matched_role")
            return OrderChainDecision(
                single_role=True,
                source="user",
                signal="mode=sequential",
                role_id=role_id,
            )

        # ② Role metadata: user-specified role has sequential_only=True
        if roles:
            try:
                from .models_dispatch import ROLE_REGISTRY
                for rid in roles:
                    rdef = ROLE_REGISTRY.get(rid)
                    if rdef and getattr(rdef, "sequential_only", False):
                        return OrderChainDecision(
                            single_role=True,
                            source="role_meta",
                            signal=f"role {rid!r} has sequential_only=True",
                            role_id=rid,
                        )
            except (ImportError, AttributeError):
                pass

        # ③ Heuristic scan
        task_lower = task.lower() if task else ""

        # Counter-examples override (must come BEFORE score accumulation)
        if _MULTI_ROLE_HINTS.search(task) or _PARALLEL_HINTS.search(task):
            return OrderChainDecision(
                single_role=False,
                source="heuristic",
                signal="counter-example: explicit multi-role / parallel hint",
                score=0,
            )

        # Accumulate score
        score = 0
        signals: list[str] = []
        if _DEBUG_HINTS.search(task_lower):
            score += 3
            signals.append("debug+3")
        if _MATH_HINTS.search(task_lower):
            score += 3
            signals.append("math+3")
        if _REFACTOR_STEP_HINTS.search(task_lower):
            score += 2
            signals.append("refactor_step+2")
        if _BROAD_HINTS.search(task):
            score += 1
            signals.append("broad+1")

        if score >= self.HEURISTIC_THRESHOLD:
            role_id = roles[0] if roles else kwargs.get("top_matched_role")
            signal_str = ", ".join(signals) if signals else f"score={score}"
            return OrderChainDecision(
                single_role=True,
                source="heuristic",
                signal=signal_str,
                score=score,
                role_id=role_id,
            )

        # ④ Default: allow multi-agent parallel
        if score > 0:
            return OrderChainDecision(
                single_role=False,
                source="default",
                signal=f"heuristic score {score} below threshold {self.HEURISTIC_THRESHOLD}",
                score=score,
            )

        return OrderChainDecision(
            single_role=False,
            source="default",
            signal="no signal → allow parallel",
            score=0,
        )


__all__ = [
    "OrderChainDecision",
    "OrderChainDetector",
    "get_call_counter_er",
]


# Initialize anti-ghost counter on module load
_inc_call_counter_er()
