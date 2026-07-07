"""QA 共享数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UIUXIssue:
    """单个 UI/UX 问题。"""

    severity: str  # "critical" | "warning" | "info"
    category: str  # "a11y" | "interaction" | "layout" | "ux_antipattern"
    rule: str
    element: str
    message: str
    fix: str
    metric: dict = field(default_factory=dict)


@dataclass
class ChangedRegion:
    """视觉回归变化区域。"""

    x: int
    y: int
    width: int
    height: int
    diff_ratio: float


@dataclass
class DiffResult:
    """视觉回归 Diff 结果。"""

    pixel_diff_ratio: float
    changed_regions: list[ChangedRegion]
    has_display_error: bool
    baseline_size: tuple[int, int]
    current_size: tuple[int, int]


@dataclass
class UIUXAuditReport:
    """UI/UX 巡检报告。"""

    url: str
    issues: list[UIUXIssue]
    audited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def total_count(self) -> int:
        return len(self.issues)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "info")

    @property
    def passed(self) -> bool:
        """是否通过巡检（无 critical 问题）。"""
        return self.critical_count == 0
