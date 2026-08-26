#!/usr/bin/env python3
"""DispatchHooks — Post-dispatch hooks and post-execution processing extracted from MultiAgentDispatcher.

Contains:
  - post_dispatch_hooks: history recording, quality audit, performance monitoring
  - post_execution_processing: collect, slice, anchor check after execution
  - slice_outputs: truncate oversized worker outputs
  - check_anchor_drift: detect goal-output alignment drift
  - scan_worker_outputs_for_hallucinated_deps: V4.3.0 P1-7 anti-Slopsquatting
"""

import logging
import time
from datetime import datetime
from typing import Any

from .dispatch_models import DispatchResult, PerformanceMetric
from .dispatch_steps import PostDispatchPipeline  # V4.3.0 P1-8 re-export (E2E-05 contract)
from .models import EntryType
from .scratchpad import ScratchpadEntry

logger = logging.getLogger(__name__)


__all__ = [
    "DispatchHooks",
    "PostDispatchPipeline",  # re-exported for E2E-05 contract
]


# V4.3.0 P1-7: Minimum worker output length to trigger dependency hallucination
# scan. Short outputs (e.g., "OK", "done") cannot contain meaningful imports
# and are skipped to avoid unnecessary scanning overhead.
_MIN_OUTPUT_LEN_FOR_DEP_SCAN = 50

# V4.3.0 P1-7: Substring heuristic to detect code-bearing worker outputs.
# If none of these markers appear, the output is treated as prose and skipped.
# This is a performance optimization; the checker itself handles pure prose
# correctly (returns zero findings) but we avoid the call entirely.
_CODE_MARKERS = (
    "import ", "from ", "require(", "def ", "class ", "const ", "let ",
)


class DispatchHooks:
    """Post-dispatch hooks and post-execution processing.

    Receives all dependencies via __init__ (composition pattern).
    """

    def __init__(
        self,
        coordinator: Any,
        enterprise: Any,
        quality_guard: Any,
        perf_monitor: Any,
        anchor_checker: Any,
        output_slicer: Any,
        scratchpad: Any,
        usage_tracker: Any,
        dispatch_history: list,
        max_history: int,
        enable_quality_guard: bool = True,
        enable_dependency_scan: bool = True,
    ) -> None:
        self.coordinator = coordinator
        self.enterprise = enterprise
        self.quality_guard = quality_guard
        self._perf_monitor = perf_monitor
        self.anchor_checker = anchor_checker
        self.output_slicer = output_slicer
        self.scratchpad = scratchpad
        self.usage_tracker = usage_tracker
        self._dispatch_history = dispatch_history
        self._max_history = max_history
        self.enable_quality_guard = enable_quality_guard
        # V4.3.0 P1-7: Anti-Slopsquatting scan toggle (default on; tests can
        # disable to assert zero-call behavior or to avoid import cycles).
        self.enable_dependency_scan = enable_dependency_scan

    # ------------------------------------------------------------------
    # Post-dispatch hooks (Step 17)
    # ------------------------------------------------------------------

    def post_dispatch_hooks(
        self, result: DispatchResult, task: str, role_ids: list[str], total_duration: float
    ) -> None:
        """Post-dispatch hooks: history recording, quality audit, performance recording."""
        self._dispatch_history.append(result)
        if len(self._dispatch_history) > self._max_history:
            self._dispatch_history = self._dispatch_history[-self._max_history :]

        if self.enable_quality_guard and self.quality_guard:
            try:
                qreport = self.enterprise.audit_quality()
                result.quality_report = qreport.to_markdown()
            except (ValueError, AttributeError, OSError, ImportError) as e:
                logger.warning("Quality audit failed: %s", e)

        perf_metric = PerformanceMetric(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            task_description=task,
            total_duration=total_duration,
            step_timings=result.details.get("timing", {}),
            success=result.success,
            error_count=len(result.errors),
            role_count=len(role_ids),
        )
        self._perf_monitor.record(perf_metric)

    # ------------------------------------------------------------------
    # Post-execution processing (Step 9)
    # ------------------------------------------------------------------

    def post_execution_processing(
        self, worker_results: list[dict[str, Any]], structured_goal: Any
    ) -> tuple[str, Any, Any, list[str], dict[str, float]]:
        """Post-execution: collect, slice, anchor check, dependency scan.

        Returns (summary, anchor_result, collection, errors, timing).
        """
        errors: list[str] = []
        collection = self.coordinator.collect_results()
        scratchpad_summary = collection.get("scratchpad", "")

        self.slice_outputs(worker_results, errors)
        anchor_result = self.check_anchor_drift(worker_results, structured_goal, scratchpad_summary)

        # V4.3.0 P1-7: Anti-Slopsquatting scan on worker outputs containing code.
        # Non-blocking: findings are recorded to scratchpad + usage tracker;
        # dispatch continues regardless. Blocking mode is a future enhancement
        # gated by config (``dependency_scan.blocking`` in .devsquad.yaml).
        self.scan_worker_outputs_for_hallucinated_deps(worker_results)

        step8_time = time.time()

        return scratchpad_summary, anchor_result, collection, errors, {
            "step8_time": step8_time,
        }

    # ------------------------------------------------------------------
    # V4.3.0 P1-7: Dependency hallucination scan (post-worker hook)
    # ------------------------------------------------------------------

    def scan_worker_outputs_for_hallucinated_deps(
        self, worker_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Scan worker outputs for hallucinated dependencies (Slopsquatting).

        V4.3.0 P1-7 anti-ghost-feature contract:
          - Invoked automatically by ``post_execution_processing`` on every
            dispatch (no manual trigger required)
          - Increments ``dependency_hallucination_checker._call_counter_er`` per
            scanned worker output, enabling E2E test E13
            (``test_e2e_dispatch_increments_all_five_counters``) to detect zero-call ghosts
          - Findings are written to the scratchpad as WARNING entries so they
            appear in the user-visible Markdown report
          - Usage tracker ticks ``dependency_hallucination_detected`` when any
            SUSPICIOUS or UNKNOWN finding is reported

        Skip conditions (performance optimization, not correctness):
          - ``enable_dependency_scan`` is False (test isolation)
          - Worker output is shorter than ``_MIN_OUTPUT_LEN_FOR_DEP_SCAN``
          - Worker output contains none of ``_CODE_MARKERS`` (pure prose)

        Args:
            worker_results: List of worker result dicts with "output" key

        Returns:
            List of scan result dicts (one per scanned worker). Workers whose
            output was skipped are not represented in the list.
        """
        if not self.enable_dependency_scan:
            return []

        # Lazy import to avoid module-load cycles in test environments
        from .dependency_hallucination_checker import (
            DependencyCategory,
            security_scan_dependencies,
        )

        scan_results: list[dict[str, Any]] = []

        for wr in worker_results:
            output = wr.get("output")
            if not output or not isinstance(output, str):
                continue
            if len(output) < _MIN_OUTPUT_LEN_FOR_DEP_SCAN:
                continue
            if not any(marker in output for marker in _CODE_MARKERS):
                continue

            role_id = wr.get("role_id", "unknown")
            try:
                result = security_scan_dependencies(output, ecosystem="auto")
            except (ValueError, RuntimeError) as e:
                logger.warning(
                    "Dependency scan failed for worker %s: %s", role_id, e
                )
                continue

            suspicious_count = result.stats.get("suspicious", 0)
            unknown_count = result.stats.get("unknown", 0)

            if suspicious_count == 0 and unknown_count == 0:
                # Clean output — no scratchpad noise. Still counts as a call
                # for anti-ghost-feature purposes (counter already incremented).
                continue

            # Record findings to scratchpad so they surface in the report
            if self.scratchpad is not None:
                finding_lines: list[str] = []
                for f in result.findings:
                    if f.category in (DependencyCategory.SUSPICIOUS, DependencyCategory.UNKNOWN):
                        fix = f" → 建议替换为 `{f.suggested_fix}`" if f.suggested_fix else ""
                        finding_lines.append(
                            f"  - L{f.line_number} `{f.package_name}` "
                            f"({f.ecosystem}/{f.category.value}): {f.reason}{fix}"
                        )
                if finding_lines:
                    self.scratchpad.write(
                        ScratchpadEntry(
                            worker_id="system",
                            entry_type=EntryType.WARNING,
                            content=(
                                f"[Dependency Hallucination] worker={role_id} "
                                f"suspicious={suspicious_count} "
                                f"unknown={unknown_count}\n"
                                + "\n".join(finding_lines)
                            ),
                            confidence=0.9,
                            tags=["dependency-hallucination", "v4.3.0", "p1-7"],
                        )
                    )

            if self.usage_tracker is not None:
                if suspicious_count > 0:
                    self.usage_tracker.tick("dependency_hallucination_suspicious")
                if unknown_count > 0:
                    self.usage_tracker.tick("dependency_hallucination_unknown")

            scan_results.append(
                {
                    "role_id": role_id,
                    "is_clean": result.is_clean,
                    "stats": result.stats,
                    "findings": [f.to_dict() for f in result.findings],
                    "markdown": result.to_markdown(),
                }
            )

        return scan_results

    def slice_outputs(self, worker_results: list[dict[str, Any]], _errors: list[str]) -> None:
        """Slice oversized worker outputs."""
        if self.output_slicer and worker_results:
            try:
                for wr in worker_results:
                    if wr.get("output") and len(wr["output"]) > self.output_slicer.max_slice_lines * 50:
                        slices = self.output_slicer.slice_output(wr["output"], role_id=wr.get("role_id", "unknown"))
                        wr["_slices"] = len(slices)
                        wr["_sliced"] = True
                        if self.usage_tracker:
                            self.usage_tracker.tick("output_sliced")
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning("OutputSlicer failed: %s", e)

        # V4.1.1: Strip [DEBUG-xxx] tags from worker output
        from .execution_guard import ExecutionGuard
        for wr in worker_results:
            output = wr.get("output")
            if output:
                tags = ExecutionGuard.find_debug_tags(output)
                if tags:
                    wr["output"] = ExecutionGuard.remove_debug_lines(output)
                    wr["_debug_tags_found"] = tags
                    if self.usage_tracker:
                        self.usage_tracker.tick("debug_tags_stripped")

    def check_anchor_drift(
        self, worker_results: list[dict[str, Any]], structured_goal: Any, scratchpad_summary: str
    ) -> Any:
        """Check for anchor drift after execution."""
        if not self.anchor_checker or not structured_goal:
            return None
        try:
            combined_output = scratchpad_summary or ""
            for wr in worker_results:
                if wr.get("output"):
                    combined_output += "\n" + wr["output"]
            from .models import AnchorTrigger

            anchor_result = self.anchor_checker.check(
                goal=structured_goal,
                current_output=combined_output,
                trigger=AnchorTrigger.STEP_COMPLETE,
            )
            if not anchor_result.aligned:
                if self.usage_tracker:
                    self.usage_tracker.tick("anchor_drift_detected")
                self.scratchpad.write(
                    ScratchpadEntry(
                        worker_id="system",
                        entry_type=EntryType.WARNING,
                        content=f"[Anchor Drift] {anchor_result.recommendation}",
                        confidence=0.9,
                        tags=["anchor-drift", "v3.7.0"],
                    )
                )
            return anchor_result
        except (ValueError, AttributeError, ImportError, RuntimeError) as anchor_err:
            logger.warning("Anchor check failed: %s", anchor_err)
            return None
