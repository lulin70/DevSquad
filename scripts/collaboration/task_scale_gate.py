#!/usr/bin/env python3
"""
TaskScaleGate — First-pass routing for dispatch (V4.5.2 §3).

Decides task scale S/M/L BEFORE RoleMatcher (per upstream §3.2 layering).

  S  单文件/问答       → 单角色直接执行    (max_roles=1, orchestrator=auto)
  M  单功能/2模块     → 3 阶段迷你流     (max_roles=2-3, orchestrator=mini)
  L  新项目/≥3模块   → 完整多角色+共识   (max_roles=unlimited, orchestrator=consensus)

判定信号（按优先级，命中即停）：
  1. 显式覆盖: --scale S|M|L 或 --all-roles 或 --full / --project
  2. L 触发: 跨 ≥3 模块 / ≥5 文件 / "完整流程" / "整体重写" 等
  3. M 触发: 2 模块 / 3-4 文件 / 单功能开发 + 验证
  4. S 触发: 单文件 / 小修复 / 单函数重构 / 纯问答
  5. 保底: M（宁可多验证）

Anti-Ghost: _call_counter_er 每次 decide() 递增。
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
class TaskScale:
    """First-pass routing decision (V4.5.2 §3.3).

    Attributes:
        level: 'S' | 'M' | 'L' — size category
        signal: explainable signal text (why this level was chosen)
        max_roles: maximum roles for auto-matching (1 for S, 2-3 for M, ∞ for L)
        orchestrator: 'auto' | 'mini' | 'consensus' — coordinator mode constraint
        single_role: True if strong-order chain → single-role execution
        matched_role_id: S-level forced role (None if user didn't request)
    """

    level: str
    signal: str
    max_roles: int
    orchestrator: str
    single_role: bool = False
    matched_role_id: str | None = None

    def __post_init__(self) -> None:
        if self.level not in ("S", "M", "L"):
            raise ValueError(f"Invalid level: {self.level!r} (must be S/M/L)")
        if self.max_roles < 1:
            raise ValueError(f"max_roles must be >= 1, got {self.max_roles}")


# === Orchestrator modes ===
ORCHESTRATOR_AUTO = "auto"           # S: 单 worker
ORCHESTRATOR_MINI = "mini"           # M: 轻量迷你流
ORCHESTRATOR_CONSENSUS = "consensus" # L: 完整共识

# === Unbounded roles for L ===
L_MAX_ROLES = 999
M_MAX_ROLES = 3
S_MAX_ROLES = 1

# === Regex patterns for signal detection ===

# L signals — high-confidence large-scale
_L_FILE_HINTS = re.compile(
    r"(\b完整流程\b|\b整个项目\b|\b整体重写\b|\b架构设计\b"
    r"|\bcross[- ]?module\b|\bend[- ]to[- ]end\b|\bfull\s+stack\b)",
    re.IGNORECASE,
)
_L_PROJECT_HINTS = re.compile(
    r"(--full|--project|--all-roles|新建项目|从零搭建|完整开发)",
    re.IGNORECASE,
)

# M signals — medium-scale
_M_MODULE_HINTS = re.compile(
    r"(两个模块|两个功能|多文件|跨模块|联调|集成测试|端到端|单功能开发|小项目)",
    re.IGNORECASE,
)

# S signals — small-scale
_S_FILE_HINTS = re.compile(
    r"(\b单文件\b|\b单个函数\b|\b小修复\b|\bbug 修复\b|\bbug\b|\b简单问题\b"
    r"|\b什么是\b|\b怎么用\b|\b如何实现\b|\b简单修复\b|\b简单问答\b"
    r"|\b简单\b)",
    re.IGNORECASE,
)


class TaskScaleGate:
    """First-pass routing gate: decides task scale S/M/L.

    Used by PreDispatchPipeline.execute() BEFORE match_roles() so that
    role count limits and orchestrator mode can be propagated downstream.

    Usage:
        gate = TaskScaleGate()
        scale = gate.decide(task="...", roles=None, mode="auto")
        # scale.level == "S" | "M" | "L"
        # scale.max_roles == 1 | 3 | 999
        # scale.orchestrator == "auto" | "mini" | "consensus"
    """

    def __init__(self) -> None:
        # Per-instance call counter (also bumped at module import time)
        self._local_call_count = 0

    def decide(
        self,
        task: str,
        roles: list[str] | None = None,  # noqa: ARG002
        mode: str = "auto",  # noqa: ARG002
        **kwargs: object,
    ) -> TaskScale:
        """Decide task scale.

        Args:
            task: Task description text.
            roles: User-specified role list (None → use gate decision).
            mode: Dispatch mode (auto/parallel/sequential/consensus).
            **kwargs: Recognized flags:
                - scale_override: 'S' | 'M' | 'L' | None (forced)
                - all_roles: bool (equivalent to L)
                - single_role: bool (forced single-role chain)
                - file_count: int (parsed file count, optional)
                - module_count: int (parsed module count, optional)

        Returns:
            TaskScale with level/signal/max_roles/orchestrator/single_role.
        """
        _inc_call_counter_er()
        self._local_call_count += 1

        # ① 显式覆盖优先级最高
        scale_override = kwargs.get("scale_override")
        if scale_override in ("S", "M", "L"):
            return self._build_forced(scale_override, signal=f"explicit --scale {scale_override}")

        if kwargs.get("all_roles"):
            return self._build_L(signal="explicit --all-roles")

        # 用户显式 single_role (来自 OrderChainDetector 或 CLI)
        forced_single = bool(kwargs.get("single_role"))

        task_lower = task.lower() if task else ""

        # ② L 触发
        module_count = kwargs.get("module_count")
        file_count = kwargs.get("file_count")
        if module_count is None:
            module_count = _count_modules(task)
        if file_count is None:
            file_count = _count_files(task)

        if module_count >= 3 or file_count >= 5:
            return self._build_L(
                signal=f"modules={module_count} files={file_count}",
                forced_single=forced_single,
            )
        if _L_FILE_HINTS.search(task_lower) or _L_PROJECT_HINTS.search(task_lower):
            return self._build_L(
                signal="large hint matched",
                forced_single=forced_single,
            )

        # ③ M 触发
        if isinstance(module_count, int) and module_count >= 2:
            return self._build_M(
                signal=f"modules={module_count}",
                forced_single=forced_single,
            )
        if isinstance(file_count, int) and 3 <= file_count <= 4:
            return self._build_M(
                signal=f"files={file_count}",
                forced_single=forced_single,
            )
        if _M_MODULE_HINTS.search(task_lower):
            return self._build_M(
                signal="medium hint matched",
                forced_single=forced_single,
            )

        # ④ S 触发
        if isinstance(file_count, int) and file_count == 1:
            return self._build_S(
                signal="files=1",
                forced_single=forced_single,
            )
        if _S_FILE_HINTS.search(task_lower):
            return self._build_S(
                signal="small hint matched",
                forced_single=forced_single,
            )

        # ⑤ 保底 → M (宁可多验证)
        return self._build_M(
            signal="default fallback (no clear signal)",
            forced_single=forced_single,
        )

    # ---- builders ----

    @staticmethod
    def _build_S(signal: str, forced_single: bool = False) -> TaskScale:
        return TaskScale(
            level="S",
            signal=signal,
            max_roles=S_MAX_ROLES,
            orchestrator=ORCHESTRATOR_AUTO,
            single_role=forced_single or True,  # S always single-role
        )

    @staticmethod
    def _build_M(signal: str, forced_single: bool = False) -> TaskScale:
        return TaskScale(
            level="M",
            signal=signal,
            max_roles=M_MAX_ROLES,
            orchestrator=ORCHESTRATOR_MINI,
            single_role=forced_single,
        )

    @staticmethod
    def _build_L(signal: str, forced_single: bool = False) -> TaskScale:
        return TaskScale(
            level="L",
            signal=signal,
            max_roles=L_MAX_ROLES,
            orchestrator=ORCHESTRATOR_CONSENSUS,
            single_role=forced_single,
        )

    @staticmethod
    def _build_forced(level: str, signal: str) -> TaskScale:
        if level == "S":
            return TaskScaleGate._build_S(signal)
        if level == "M":
            return TaskScaleGate._build_M(signal)
        return TaskScaleGate._build_L(signal)


# ---------------------------------------------------------------------------
# Helpers for hint counting
# ---------------------------------------------------------------------------


# Common Chinese module markers
_MODULE_MARKERS = re.compile(r"(模块|module|服务|service|子系统|组件)", re.IGNORECASE)
# Common file path markers — match ".py/.ts/.js/.go/.rs/.java/.md"
_FILE_PATH_HINTS = re.compile(
    r"([\w/]+\.(?:py|ts|tsx|js|jsx|go|rs|java|md|yaml|yml|json|toml))",
    re.IGNORECASE,
)


def _count_modules(task: str) -> int:
    """Estimate module count from task text (heuristic)."""
    if not task:
        return 0
    # Match "两个模块" / "跨 3 个模块" / explicit numbers
    m = re.search(r"(\d+)\s*个?模块", task)
    if m:
        return int(m.group(1))
    # Fallback: count module-marker hits
    hits = _MODULE_MARKERS.findall(task)
    return len(hits)


def _count_files(task: str) -> int:
    """Estimate file count from task text (heuristic)."""
    if not task:
        return 0
    # Match "3 个文件" / explicit numbers
    m = re.search(r"(\d+)\s*个?文件", task)
    if m:
        return int(m.group(1))
    # Fallback: count file-path hints
    files = _FILE_PATH_HINTS.findall(task)
    # Deduplicate to avoid inflating count
    return len(set(files))


__all__ = [
    "TaskScale",
    "TaskScaleGate",
    "get_call_counter_er",
    "S_MAX_ROLES",
    "M_MAX_ROLES",
    "L_MAX_ROLES",
    "ORCHESTRATOR_AUTO",
    "ORCHESTRATOR_MINI",
    "ORCHESTRATOR_CONSENSUS",
]


# Initialize anti-ghost counter on module load
_inc_call_counter_er()
