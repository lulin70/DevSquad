"""Utility mixin for MultiAgentDispatcher.

Extracts language resolution, quick dispatch, and report formatting helpers.
"""

import locale
import logging
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase

logger = logging.getLogger(__name__)


class DispatcherUtilsMixin(DispatcherBase):
    """Provides utility helpers used by MultiAgentDispatcher."""

    micro_task_planner: Any
    usage_tracker: Any
    coordinator: Any
    post_dispatch: Any
    enterprise: Any
    persist_dir: str
    llm_backend: Any

    def analyze_task(self, task_description: str) -> list[dict[str, Any]]:
        """Analyze task and match appropriate roles."""
        from .usage_tracker import track_usage

        track_usage("dispatcher.analyze_task")
        return self.role_matcher.analyze_task(task_description)

    def decompose_task(
        self,
        task_description: str,
        spec: dict[str, Any] | None = None,
    ) -> Any:
        """Decompose a task into micro-tasks using the configured planner.

        V3.8 #7: When a :class:`MicroTaskPlanner` is configured via
        the ``micro_task_planner`` parameter, this method delegates to
        ``planner.plan(task_description, spec)`` and returns the
        resulting :class:`MicroTaskPlan`. When no planner is
        configured, returns ``None``.
        """
        if self.micro_task_planner is None:
            return None
        return self.micro_task_planner.plan(task_description, spec=spec)

    def _maybe_decompose_task(
        self,
        task_description: str,
        use_micro_tasks: bool,
        kwargs: dict[str, Any],
    ) -> Any:
        """V3.8 #7: Optionally decompose the task into micro-tasks.

        Runs only when ``use_micro_tasks=True`` and a
        :class:`MicroTaskPlanner` is configured. Returns the
        :class:`MicroTaskPlan` (or ``None`` when decomposition is
        disabled or fails — graceful degradation).
        """
        if not use_micro_tasks or self.micro_task_planner is None:
            return None
        try:
            spec: dict[str, Any] = {}
            for key in ("files", "functions", "tests", "acceptance_criteria"):
                if key in kwargs:
                    spec[key] = kwargs[key]
            plan = self.decompose_task(task_description, spec=spec or None)
            if plan is not None:
                logger.info(
                    "MicroTaskPlanner decomposed task into %d micro-tasks "
                    "(est. %d min)",
                    len(plan.micro_tasks),
                    plan.total_estimated_minutes,
                )
                if self.usage_tracker:
                    self.usage_tracker.tick("micro_task_planner")
            return plan
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("Micro-task decomposition failed: %s", exc)
            return None

    def _resolve_language(self, lang: str) -> str:
        """Resolve language from 'auto' to a specific language code."""
        if lang != "auto":
            return lang

        try:
            try:
                loc = locale.getlocale()[0] or ""
            except (ValueError, TypeError):
                loc = ""
            if loc.startswith("ja"):
                return "ja"
            elif loc.startswith("zh"):
                return "zh"
            else:
                return "zh"
        except (ValueError, TypeError, OSError) as e:
            logger.debug("Locale detection failed, using default language: %s", e)
            return "zh"

    def _execute_workers(
        self, plan: Any, _task_description: str
    ) -> tuple[Any, list[dict[str, Any]], list[str], dict[str, float]]:
        """Execute workers via Coordinator. Returns (exec_result, worker_results, errors, timing)."""
        exec_result = self.coordinator.execute_plan(plan)
        worker_results, step6_time, step7_time = self.post_dispatch._collect_worker_results(exec_result)
        exec_errors = list(exec_result.errors) if exec_result.errors else []
        return exec_result, worker_results, exec_errors, {
            "step6_time": step6_time,
            "step7_time": step7_time,
        }

    def _get_current_tenant_id(self) -> str:
        """Get current tenant_id for data isolation, defaults to 'default'."""
        if self.enterprise.enable_multi_tenant and self.enterprise.tenant_manager:
            current_tenant = self.enterprise.tenant_manager.get_current_tenant()
            if current_tenant:
                return str(current_tenant.tenant_id)
        return "default"

    def quick_dispatch(
        self,
        task: str,
        output_format: str = "structured",
        include_action_items: bool = True,
        include_timing: bool = False,
    ) -> DispatchResult:
        """Quick dispatch returning DispatchResult with formatted report."""
        result = self.dispatch(task)

        if output_format == "structured":
            result.summary = self.report_formatter.format_structured_report(
                result, include_action_items, include_timing
            )
        elif output_format == "compact":
            result.summary = self.report_formatter.format_compact_report(result)
        else:
            result.summary = result.to_markdown()

        return result

    def _format_structured_report(
        self, result: DispatchResult, include_action_items: bool = True, include_timing: bool = False
    ) -> str:
        return self.report_formatter.format_structured_report(result, include_action_items, include_timing)

    def _format_compact_report(self, result: DispatchResult) -> str:
        return self.report_formatter.format_compact_report(result)

    def _extract_findings(self, scratchpad_summary: str) -> list[str]:
        return self.report_formatter.extract_findings(scratchpad_summary)

    def _generate_action_items(self, result: DispatchResult) -> list[dict[str, str]]:
        return self.report_formatter.generate_action_items(result)
