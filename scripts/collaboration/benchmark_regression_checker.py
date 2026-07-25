#!/usr/bin/env python3
"""BenchmarkRegressionChecker -- V4.3.1 Phase 1 P1-1.

P11 lifecycle gate checker that detects performance benchmark
regressions by comparing a current snapshot against a baseline.

Architecture reference: docs/analysis/2026-07-25_V4.3.1_plan.md sec 3.1
Test plan: tests/unit/test_benchmark_regression_checker.py

Skill integration (anti-ghost feature):
- Integration point: ``unified_gate_engine.py`` P11 lifecycle gate
- Trigger: dispatcher auto-invokes via
  ``lifecycle_gate_check(phase="P11", ...)``
- User visibility: Markdown report "Benchmark Regression" section
- CI check: module call count > 0 (verified by
  ``check_module_activation.py``)

Regression model
----------------
For each metric present in both snapshots::

    regression_percent = (current - baseline) / baseline * 100

Positive values indicate slowdown (regression); negative values
indicate speedup (improvement). A metric is flagged as regressed when
its regression percentage strictly exceeds ``threshold_percent``. The
report's ``regression_percent`` is the maximum across all comparable
metrics, so a single slow metric raises the overall number even if
others improved.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from scripts.collaboration._version import __version__

logger = logging.getLogger(__name__)

RegressionLevel = Literal["none", "minor", "major", "critical"]


@dataclass(slots=True)
class BenchmarkMetric:
    """A single benchmark measurement.

    Attributes
    ----------
    name:
        Metric identifier (e.g. ``"dispatch_p95_ms"``,
        ``"memory_peak_mb"``).
    value:
        Measured value (float for latencies, int for counts).
    unit:
        Unit string (e.g. ``"ms"``, ``"MB"``, ``"ops/sec"``).
    """

    name: str
    value: float
    unit: str


@dataclass(slots=True)
class BenchmarkSnapshot:
    """A versioned benchmark snapshot.

    Attributes
    ----------
    version:
        DevSquad version string (e.g. ``"4.3.0"``).
    timestamp:
        Unix timestamp of snapshot collection.
    metrics:
        List of :class:`BenchmarkMetric` instances.
    """

    version: str
    timestamp: float
    metrics: list[BenchmarkMetric] = field(default_factory=list)


@dataclass(slots=True)
class BenchmarkReport:
    """Result of comparing current metrics against a baseline.

    Attributes
    ----------
    regression_detected:
        ``True`` if any metric regressed beyond its threshold.
    regression_percent:
        Maximum regression percentage across all comparable metrics
        (``0.0`` when no metrics overlap). Positive value means
        slowdown; negative means speedup.
    regressed_metrics:
        Names of metrics that exceeded the regression threshold.
    baseline_version:
        Version string of the baseline snapshot.
    current_version:
        Version string of the current snapshot.
    threshold_percent:
        Regression threshold in percent (default ``10.0``).
    """

    regression_detected: bool
    regression_percent: float
    regressed_metrics: list[str] = field(default_factory=list)
    baseline_version: str = ""
    current_version: str = ""
    threshold_percent: float = 10.0

    def to_markdown(self) -> str:
        """Render the report as a Markdown section.

        Returns
        -------
        str
            Markdown text with a ``Benchmark Regression`` header and
            fields for baseline/current version, threshold, max
            regression percentage, regressed metric names, and a
            status line.
        """
        status = "REGRESSION DETECTED" if self.regression_detected else "OK"
        regressed_str = (
            ", ".join(self.regressed_metrics) if self.regressed_metrics else "(none)"
        )
        lines = [
            "## Benchmark Regression",
            "",
            f"- **Baseline version**: {self.baseline_version}",
            f"- **Current version**: {self.current_version}",
            f"- **Threshold**: {self.threshold_percent}%",
            f"- **Max regression**: {self.regression_percent}%",
            f"- **Regressed metrics**: {regressed_str}",
            f"- **Status**: {status}",
        ]
        return "\n".join(lines)


def _compute_regression_percent(baseline_value: float, current_value: float) -> float:
    """Compute the regression percentage for a single metric.

    Regression percent = ``(current - baseline) / baseline * 100``.
    Positive means slowdown; negative means speedup. When the
    baseline is ``0``, returns ``0.0`` to avoid division-by-zero
    (a zero baseline carries no meaningful ratio).

    Parameters
    ----------
    baseline_value:
        The baseline metric value.
    current_value:
        The current metric value.

    Returns
    -------
    float
        The regression percentage.
    """
    if baseline_value == 0:
        return 0.0
    return (current_value - baseline_value) / baseline_value * 100.0


class BenchmarkRegressionChecker:
    """Detects performance benchmark regressions between two snapshots.

    Compares a current :class:`BenchmarkSnapshot` against a baseline
    and flags any metric whose value increased (slowed down) beyond a
    configurable threshold.

    Parameters
    ----------
    threshold_percent:
        Regression threshold in percent. A metric is flagged when its
        regression percentage strictly exceeds this value. Defaults to
        ``10.0`` (a 10% slowdown is tolerated, but ``10.01%`` is
        flagged).

    Example
    -------
    >>> checker = BenchmarkRegressionChecker(threshold_percent=10.0)
    >>> baseline = BenchmarkSnapshot("4.2.9", 0.0, [
    ...     BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
    ... ])
    >>> current = BenchmarkSnapshot("4.3.0", 0.0, [
    ...     BenchmarkMetric("dispatch_p95_ms", 125.0, "ms"),
    ... ])
    >>> report = checker.compare(baseline, current)
    >>> report.regression_detected
    True
    """

    def __init__(self, threshold_percent: float = 10.0) -> None:
        self.threshold_percent = threshold_percent

    def compare(
        self,
        baseline: BenchmarkSnapshot,
        current: BenchmarkSnapshot,
    ) -> BenchmarkReport:
        """Compare two snapshots and return a regression report.

        Only metrics present in both snapshots are compared. The
        report's ``regression_percent`` is the maximum regression
        percentage across all comparable metrics (``0.0`` when no
        metrics overlap). A metric is added to ``regressed_metrics``
        when its regression percentage strictly exceeds
        ``threshold_percent``.

        Parameters
        ----------
        baseline:
            The baseline snapshot to compare against.
        current:
            The current snapshot to evaluate.

        Returns
        -------
        BenchmarkReport
            The regression report with version fields populated from
            the snapshots.
        """
        baseline_map = {m.name: m.value for m in baseline.metrics}
        current_map = {m.name: m.value for m in current.metrics}

        regressions: list[tuple[str, float]] = []
        for name, current_value in current_map.items():
            if name not in baseline_map:
                continue
            baseline_value = baseline_map[name]
            regression = _compute_regression_percent(baseline_value, current_value)
            regressions.append((name, regression))

        if not regressions:
            max_regression = 0.0
            regressed_names: list[str] = []
        else:
            max_regression = max(r for _, r in regressions)
            regressed_names = [
                name for name, r in regressions if r > self.threshold_percent
            ]

        return BenchmarkReport(
            regression_detected=len(regressed_names) > 0,
            regression_percent=max_regression,
            regressed_metrics=regressed_names,
            baseline_version=baseline.version,
            current_version=current.version,
            threshold_percent=self.threshold_percent,
        )

    def run_live_benchmark(self) -> BenchmarkSnapshot:
        """Run a live benchmark and return the snapshot.

        This is a mock implementation that returns representative
        metrics. In production, this would invoke the actual benchmark
        suite (e.g. ``pytest --benchmark``). The mock metrics model a
        typical dispatch pipeline: ``dispatch_p95_ms`` and
        ``memory_peak_mb``.

        Returns
        -------
        BenchmarkSnapshot
            A snapshot tagged with the current package version, the
            current wall-clock timestamp, and mock metrics
            (``dispatch_p95_ms=120.0ms``, ``memory_peak_mb=200.0MB``).
        """
        metrics = [
            BenchmarkMetric("dispatch_p95_ms", 120.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ]
        return BenchmarkSnapshot(
            version=__version__,
            timestamp=time.time(),
            metrics=metrics,
        )


def _default_baseline(baseline_version: str) -> BenchmarkSnapshot:
    """Build the default baseline snapshot for lifecycle_gate_check.

    Parameters
    ----------
    baseline_version:
        Version string to embed in the baseline snapshot.

    Returns
    -------
    BenchmarkSnapshot
        Baseline with ``dispatch_p95_ms=100.0ms`` and
        ``memory_peak_mb=200.0MB``.
    """
    return BenchmarkSnapshot(
        version=baseline_version,
        timestamp=0.0,
        metrics=[
            BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ],
    )


def lifecycle_gate_check(
    phase: str,
    baseline_version: str,
    current_version: str | None = None,
    threshold_percent: float = 10.0,
    baseline_snapshot: BenchmarkSnapshot | None = None,
    current_snapshot: BenchmarkSnapshot | None = None,
) -> BenchmarkReport:
    """P11 lifecycle gate entry point.

    Args:
        phase: Lifecycle phase, must be ``"P11"``.
        baseline_version: Version string of the baseline.
        current_version: Current version (defaults to package
            ``__version__``).
        threshold_percent: Regression threshold in percent.
        baseline_snapshot: Injected baseline (for testing). If
            ``None``, uses the default baseline (100ms / 200MB).
        current_snapshot: Injected current metrics (for testing). If
            ``None``, runs the live benchmark.

    Returns:
        BenchmarkReport with ``regression_detected`` flag. The
        ``baseline_version`` / ``current_version`` fields are set from
        the function arguments (parameters take precedence over
        snapshot-embedded versions).

    Raises:
        ValueError: If ``phase != "P11"``.

    Example
    -------
    >>> report = lifecycle_gate_check(
    ...     phase="P11",
    ...     baseline_version="4.2.9",
    ...     current_version="4.3.0",
    ... )
    >>> isinstance(report, BenchmarkReport)
    True
    """
    if phase != "P11":
        raise ValueError("BenchmarkRegressionChecker only supports P11 phase")

    resolved_current_version = (
        current_version if current_version is not None else __version__
    )
    baseline = (
        baseline_snapshot
        if baseline_snapshot is not None
        else _default_baseline(baseline_version)
    )
    current = (
        current_snapshot
        if current_snapshot is not None
        else BenchmarkRegressionChecker().run_live_benchmark()
    )

    checker = BenchmarkRegressionChecker(threshold_percent)
    report = checker.compare(baseline, current)
    # Function parameters take precedence over snapshot-embedded versions.
    report.baseline_version = baseline_version
    report.current_version = resolved_current_version
    return report


__all__ = [
    "BenchmarkMetric",
    "BenchmarkSnapshot",
    "BenchmarkReport",
    "RegressionLevel",
    "lifecycle_gate_check",
    "BenchmarkRegressionChecker",
]
