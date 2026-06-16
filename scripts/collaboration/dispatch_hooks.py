#!/usr/bin/env python3
"""DispatchHooks — Post-dispatch hooks and post-execution processing extracted from MultiAgentDispatcher.

Contains:
  - post_dispatch_hooks: history recording, quality audit, performance monitoring
  - post_execution_processing: collect, slice, anchor check after execution
  - slice_outputs: truncate oversized worker outputs
  - check_anchor_drift: detect goal-output alignment drift
"""

import logging
import time
from datetime import datetime
from typing import Any

from .dispatch_models import DispatchResult, PerformanceMetric
from .models import EntryType
from .scratchpad import ScratchpadEntry

logger = logging.getLogger(__name__)


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
        """Post-execution: collect, slice, anchor check.

        Returns (summary, anchor_result, collection, errors, timing).
        """
        errors: list[str] = []
        collection = self.coordinator.collect_results()
        scratchpad_summary = collection.get("scratchpad", "")

        self.slice_outputs(worker_results, errors)
        anchor_result = self.check_anchor_drift(worker_results, structured_goal, scratchpad_summary)

        step8_time = time.time()

        return scratchpad_summary, anchor_result, collection, errors, {
            "step8_time": step8_time,
        }

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
