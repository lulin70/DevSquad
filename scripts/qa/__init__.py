"""V4.0.0 P1-2: UI/UX 巡检与视觉回归。

借鉴 TraeMultiAgentSkill 的 uiux_analyzer + visual_regression 理念：
- 4 大检测维度 (a11y / interaction / layout / ux_antipattern)
- PIL ImageChops 像素级 Diff
- Playwright 单次综合探针 (软依赖)
"""

from .models import (
    ChangedRegion,
    DiffResult,
    UIUXAuditReport,
    UIUXIssue,
)
from .uiux_analyzer import UIUXAnalyzer
from .visual_regression import VisualRegressionChecker

__all__ = [
    "ChangedRegion",
    "DiffResult",
    "UIUXAnalyzer",
    "UIUXAuditReport",
    "UIUXIssue",
    "VisualRegressionChecker",
]
