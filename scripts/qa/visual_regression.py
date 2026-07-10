"""视觉回归检查器：PIL ImageChops 像素级 Diff + 区域检测。

借鉴 TraeMultiAgentSkill 的 visual_regression.py 理念：
- 像素级 Diff 比例
- 变化区域识别（连通分量简化版：网格扫描）
- 显示错误检测（尺寸不匹配或大面积变化）

软依赖：Pillow（必需）。无 Pillow 时模块可导入但 compare() 抛 RuntimeError。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .models import ChangedRegion, DiffResult

logger = logging.getLogger(__name__)


class VisualRegressionChecker:
    """视觉回归检查器。

    默认阈值：pixel_diff_ratio < 1% 视为通过。
    """

    def __init__(
        self,
        pixel_diff_threshold: float = 0.01,
        region_grid_size: int = 50,
        display_error_ratio: float = 0.15,
    ) -> None:
        self._pixel_diff_threshold = pixel_diff_threshold
        self._region_grid_size = region_grid_size
        self._display_error_ratio = display_error_ratio

    def compare(
        self,
        baseline: Path | str,
        current: Path | str,
    ) -> DiffResult:
        """比较两张图片，返回 Diff 结果。

        Args:
            baseline: 基线图片路径。
            current: 当前图片路径。

        Returns:
            DiffResult 包含差异比例和变化区域。

        Raises:
            RuntimeError: Pillow 未安装。
            FileNotFoundError: 图片不存在。
        """
        try:
            from PIL import Image, ImageChops
        except ImportError as exc:
            raise RuntimeError(
                "Pillow is required for visual regression. Install with: pip install Pillow"
            ) from exc

        baseline_path = Path(baseline)
        current_path = Path(current)
        if not baseline_path.exists():
            raise FileNotFoundError(f"Baseline image not found: {baseline_path}")
        if not current_path.exists():
            raise FileNotFoundError(f"Current image not found: {current_path}")

        img_a = Image.open(baseline_path).convert("RGB")
        img_b = Image.open(current_path).convert("RGB")

        size_a = img_a.size
        size_b = img_b.size

        # 尺寸不匹配：归一化到较小尺寸
        if size_a != size_b:
            min_w = min(size_a[0], size_b[0])
            min_h = min(size_a[1], size_b[1])
            img_a = img_a.resize((min_w, min_h))
            img_b = img_b.resize((min_w, min_h))

        # 像素级 Diff
        diff = ImageChops.difference(img_a, img_b)
        diff_data = list(diff.getdata())

        total_pixels = len(diff_data)
        if total_pixels == 0:
            return DiffResult(
                pixel_diff_ratio=0.0,
                changed_regions=[],
                has_display_error=False,
                baseline_size=size_a,
                current_size=size_b,
            )

        # 统计差异像素（任一通道差异 > 阈值）
        diff_threshold = 16
        diff_pixels = sum(
            1 for r, g, b in diff_data
            if r > diff_threshold or g > diff_threshold or b > diff_threshold
        )
        pixel_diff_ratio = diff_pixels / total_pixels

        # 区域检测：网格扫描
        changed_regions = self._detect_regions(diff, img_a.size)

        # 显示错误：尺寸不匹配 或 大面积变化
        has_display_error = (
            size_a != size_b
            or pixel_diff_ratio > self._display_error_ratio
        )

        return DiffResult(
            pixel_diff_ratio=pixel_diff_ratio,
            changed_regions=changed_regions,
            has_display_error=has_display_error,
            baseline_size=size_a,
            current_size=size_b,
        )

    def is_regression(self, result: DiffResult) -> bool:
        """判断是否为视觉回归。"""
        return (
            result.pixel_diff_ratio > self._pixel_diff_threshold
            or result.has_display_error
        )

    def _detect_regions(self, diff_img: Any, size: tuple[int, int]) -> list[ChangedRegion]:
        """网格扫描检测变化区域。

        将图片划分为 grid_size x grid_size 的网格，
        统计每个网格的差异像素比例，超过阈值的网格作为变化区域。
        """
        try:
            import PIL  # noqa: F401 — verify Pillow availability
        except ImportError:
            return []

        width, height = size
        grid = self._region_grid_size
        cell_w = max(1, width // grid)
        cell_h = max(1, height // grid)

        regions: list[ChangedRegion] = []
        diff_data = diff_img.load()

        diff_threshold = 16
        cell_pixel_threshold = 0.20  # 网格内 20% 像素变化才标记

        for gy in range(grid):
            for gx in range(grid):
                x0 = gx * cell_w
                y0 = gy * cell_h
                x1 = min(x0 + cell_w, width)
                y1 = min(y0 + cell_h, height)

                cell_total = (x1 - x0) * (y1 - y0)
                if cell_total == 0:
                    continue

                cell_diff = 0
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        r, g, b = diff_data[x, y][:3]
                        if r > diff_threshold or g > diff_threshold or b > diff_threshold:
                            cell_diff += 1

                ratio = cell_diff / cell_total
                if ratio > cell_pixel_threshold:
                    regions.append(ChangedRegion(
                        x=x0,
                        y=y0,
                        width=x1 - x0,
                        height=y1 - y0,
                        diff_ratio=round(ratio, 3),
                    ))

        return regions
