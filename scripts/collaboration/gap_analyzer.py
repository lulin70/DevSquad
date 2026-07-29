"""V4.4.0 P1-2 Gap Analyzer — TOGAF Gap Analysis & Architecture Roadmap.

Analyzes gaps between current and target architecture, prioritizes them,
generates a roadmap, and feeds the ``LoopScheduler`` CONTINUE/STOP decision.

Anti-ghost: module-level ``_call_counter`` increments on every public
method call.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

# Anti-ghost: module-level call counter (AG-1/AG-2)
_call_counter: int = 0


class GapPriority(Enum):
    """Priority levels for a gap."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Ordering for sorting (lower = higher priority)
_PRIORITY_ORDER: dict[GapPriority, int] = {
    GapPriority.CRITICAL: 0,
    GapPriority.HIGH: 1,
    GapPriority.MEDIUM: 2,
    GapPriority.LOW: 3,
}

# Effort string → numeric mapping for sorting
_EFFORT_MAP: dict[str, float] = {
    "low": 1.0,
    "medium": 5.0,
    "high": 10.0,
    "critical": 20.0,
}

# Stop words excluded when building readable gap ids from work_package text
_ID_STOP_WORDS: frozenset[str] = frozenset({
    "add", "migrate", "from", "to", "the", "for", "and", "or", "with",
    "capability", "of", "a", "an", "in", "on", "at", "by", "be",
})


def _slugify_work_package(work_package: str) -> str:
    """Extract up to 3 meaningful keywords from work_package for a readable id.

    Args:
        work_package: Free-text work description.

    Returns:
        Hyphen-joined lowercase keywords (e.g. "auth" from "Add auth capability").
    """
    keywords = re.findall(r"\b[a-z][a-z0-9]+\b", work_package.lower())
    meaningful = [k for k in keywords if k not in _ID_STOP_WORDS]
    return "-".join(meaningful[:3]) if meaningful else "gap"


def _coerce_priority(value: Any) -> GapPriority:
    """Accept str or GapPriority."""
    if isinstance(value, GapPriority):
        return value
    if isinstance(value, str):
        try:
            return GapPriority(value.lower())
        except ValueError as exc:
            raise ValueError(
                f"Unknown priority: {value!r}. "
                f"Must be one of {[p.value for p in GapPriority]}"
            ) from exc
    raise TypeError(f"priority must be str or GapPriority, got {type(value)!r}")


def _coerce_effort(value: Any) -> float:
    """Accept str (low/medium/high) or numeric effort."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return _EFFORT_MAP.get(value.lower(), 5.0)
    return 5.0


@dataclass
class Gap:
    """A single architecture gap.

    Attributes:
        id: Stable unique identifier.
        current_state: Current state description.
        target_state: Target state description.
        work_package: Work needed to close the gap.
        priority: GapPriority level.
        effort: Estimated effort in person-days (or string descriptor).
        closure_delta: Last loop's closure progress (negative = regressing).
    """

    id: str
    current_state: str
    target_state: str
    work_package: str
    priority: GapPriority = GapPriority.MEDIUM
    effort: float = 5.0
    closure_delta: float = 0.0

    def __post_init__(self) -> None:
        self.priority = _coerce_priority(self.priority)
        if isinstance(self.effort, str):
            self.effort = _coerce_effort(self.effort)


class GapAnalyzer:
    """Analyzer for architecture gaps with roadmap generation.

    Anti-ghost: every public method increments ``_call_counter``.
    """

    def __init__(self) -> None:
        self._gaps: dict[str, Gap] = {}
        self._target_state: dict[str, Any] | None = None

    def add_gap(
        self,
        current_state: str,
        target_state: str,
        work_package: str,
        priority: GapPriority | str = GapPriority.MEDIUM,
        effort: float | str = 5.0,
    ) -> Gap:
        """Manually add a gap (for testing and explicit gap registration).

        Generates a readable id from ``work_package`` keywords (e.g.
        ``"Add auth capability"`` → ``"G-auth"``). A short hash suffix
        is appended when the slug already exists, preserving uniqueness.

        Args:
            current_state: Current state description.
            target_state: Target state description.
            work_package: Work needed to close the gap.
            priority: GapPriority or string.
            effort: Numeric (person-days) or string (low/medium/high).

        Returns:
            The created Gap.
        """
        global _call_counter
        _call_counter += 1

        slug = _slugify_work_package(work_package)
        gid = f"G-{slug}"
        if gid in self._gaps:
            suffix = hashlib.sha256(
                f"{current_state}->{target_state}".encode()
            ).hexdigest()[:8]
            gid = f"G-{slug}-{suffix}"
        coerced_priority = _coerce_priority(priority)
        coerced_effort = _coerce_effort(effort)
        gap = Gap(
            id=gid,
            current_state=current_state,
            target_state=target_state,
            work_package=work_package,
            priority=coerced_priority,
            effort=coerced_effort,
        )
        self._gaps[gid] = gap
        return gap

    def analyze(
        self,
        current: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Gap]:
        """Analyze gaps between current and target state.

        Two modes:
        1. P2 mode (``target`` only): store target architecture, return [].
        2. P3 mode (``current`` + ``target``): compare and return gaps.

        Args:
            current: Current architecture dict (capability → version/state).
            target: Target architecture dict (capability → version/state).

        Returns:
            List of Gap objects (empty in P2 mode).
        """
        global _call_counter
        _call_counter += 1

        # Handle kwargs for E2E test compatibility
        if current is None and "current_state" in kwargs:
            current = kwargs["current_state"]
        if target is None and "target_state" in kwargs:
            target = kwargs["target_state"]

        if target is not None and current is None:
            # P2 mode: just store the target
            self._target_state = target
            return []

        if target is None and current is None:
            return []

        if current is None:
            current = {}
        if target is None:
            target = {}

        gaps: list[Gap] = []
        for capability, target_val in target.items():
            current_val = current.get(capability)
            if current_val is None:
                # Missing capability
                gap = self.add_gap(
                    current_state="missing",
                    target_state=str(target_val),
                    work_package=f"Add {capability} capability",
                    priority=GapPriority.HIGH,
                    effort="medium",
                )
                gaps.append(gap)
            elif current_val != target_val:
                # Changed capability
                gap = self.add_gap(
                    current_state=str(current_val),
                    target_state=str(target_val),
                    work_package=f"Migrate {capability} from {current_val} to {target_val}",
                    priority=GapPriority.MEDIUM,
                    effort="medium",
                )
                gaps.append(gap)
        return gaps

    def prioritize(self, gaps: list[Gap] | None = None) -> list[Gap]:
        """Sort gaps by priority (critical→low) then effort (ascending).

        Args:
            gaps: List of gaps to sort. If None, uses all stored gaps.

        Returns:
            Sorted list of gaps.
        """
        global _call_counter
        _call_counter += 1

        if gaps is None:
            gaps = list(self._gaps.values())
        return sorted(
            gaps,
            key=lambda g: (_PRIORITY_ORDER.get(g.priority, 99), g.effort),
        )

    def generate_roadmap(self, gaps: list[Gap] | None = None) -> str:
        """Render a Markdown roadmap table.

        Args:
            gaps: List of gaps to include. If None, uses prioritized stored gaps.

        Returns:
            Markdown table with columns: Phase | Gap | Priority | Effort.
        """
        global _call_counter
        _call_counter += 1

        if gaps is None:
            gaps = self.prioritize()

        lines = [
            "## Gap Analysis Roadmap",
            "",
            "| Phase | Gap | Priority | Effort |",
            "|---|---|---|---|",
        ]
        for i, gap in enumerate(gaps, start=1):
            lines.append(
                f"| Phase {i} | {gap.work_package} | "
                f"{gap.priority.value} | {gap.effort} |"
            )
        lines.append("")
        return "\n".join(lines)

    def track(
        self,
        gap_id: str,
        closure_delta: float,
    ) -> Gap:
        """Record gap-closure progress.

        Args:
            gap_id: The gap to track.
            closure_delta: Progress made (positive = closing, negative = regressing).

        Returns:
            Updated Gap.

        Raises:
            KeyError: If gap_id not found.
        """
        global _call_counter
        _call_counter += 1

        if gap_id not in self._gaps:
            raise KeyError(f"Unknown gap_id: {gap_id!r}")

        gap = self._gaps[gap_id]
        gap.closure_delta = closure_delta
        return gap

    def suggest_scheduler_decision(self, gap_id: str) -> str:
        """Suggest a LoopScheduler decision based on closure delta.

        Args:
            gap_id: The gap to evaluate.

        Returns:
            "CONTINUE" if delta > 0, "STOP" if delta <= 0.
        """
        global _call_counter
        _call_counter += 1

        if gap_id not in self._gaps:
            raise KeyError(f"Unknown gap_id: {gap_id!r}")

        gap = self._gaps[gap_id]
        if gap.closure_delta <= 0:
            return "STOP"
        return "CONTINUE"
