"""Merged dispatcher mixins for MultiAgentDispatcher.

This module is the V4.1.2 Phase 3 Wave 3 consolidation of the following 6
previously-separate mixin files:

- ``dispatcher_async_mixin.py``      -> ``DispatcherAsyncMixin``
- ``dispatcher_audit_mixin.py``       -> ``DispatcherAuditMixin``
- ``dispatcher_error_mixin.py``       -> ``DispatcherErrorMixin``
- ``dispatcher_lifecycle_mixin.py``   -> ``DispatcherLifecycleMixin``
- ``dispatcher_status_mixin.py``      -> ``DispatcherStatusMixin``
- ``dispatcher_utils_mixin.py``       -> ``DispatcherUtilsMixin``

The original files have been converted to thin shims that re-export from this
module for backward compatibility; they will be deleted in V4.2.0.
"""

import locale
import logging
import os
import time
from typing import Any, cast

from ._version import __version__
from .async_adapter import SyncToAsyncAdapter
from .async_llm_backend import AsyncLLMBackendFactory
from .dispatch_models import ROLE_TEMPLATES, DispatchResult
from .dispatcher_base import DispatcherBase
from .llm_cache_async import AsyncLLMCache
from .rbac_engine import Permission, PermissionDeniedError
from .usage_tracker import track_usage
from .user_friendly_error import make_user_friendly_error

logger = logging.getLogger(__name__)


class DispatcherAsyncMixin(DispatcherBase):
    """Provides async dispatch helpers used by MultiAgentDispatcher."""

    scratchpad: Any
    persist_dir: str
    enable_compression: bool
    compression_threshold: int
    llm_backend: Any
    stream: bool
    memory_bridge: Any
    enable_memory: bool
    execution_guard: Any
    coordinator: Any
    post_dispatch: Any
    pre_dispatch: Any
    metrics_service: Any
    usage_tracker: Any
    enterprise: Any

    async def async_dispatch(
        self,
        task_description: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        """Async version of dispatch() using AsyncCoordinator. Falls back to sync on failure."""
        track_usage("dispatcher.async_dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        phase = "async_dispatch"

        self.metrics_service.safe_record(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("async_dispatch")

        pre_result = self.pre_dispatch.execute(task_description, roles, mode, dry_run, start_time, phase, **kwargs)
        if pre_result.early_return:
            self.metrics_service.safe_record(lambda m: m.tasks_in_progress_gauge.labels(phase=phase).dec())
            return cast(DispatchResult, pre_result.early_return)

        tenant_ctx = pre_result.tenant_ctx

        try:
            matched_roles = pre_result.matched_roles
            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").inc(len(matched_roles)))

            exec_result, worker_results, exec_errors, exec_timing = await self._execute_async_workers(
                pre_result.plan, task_description, matched_roles, kwargs
            )

            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").dec(len(matched_roles)))

            return cast(
                DispatchResult,
                self.post_dispatch.execute(
                    pre_result=pre_result,
                    exec_result=exec_result,
                    worker_results=worker_results,
                    exec_errors=exec_errors,
                    exec_timing=exec_timing,
                    start_time=start_time,
                    phase=phase,
                    **kwargs,
                ),
            )

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            return self._handle_dispatch_error(dispatch_err, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)
        except (ImportError, ModuleNotFoundError) as import_err:
            return self._handle_dispatch_error(import_err, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)
        except (RuntimeError, OSError, ConnectionError, TimeoutError) as e:
            return self._handle_dispatch_error(e, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)

    async def _execute_async_workers(
        self, plan: Any, task_description: str, matched_roles: list[dict[str, Any]], kwargs: dict[str, Any]
    ) -> tuple[Any, list[dict[str, Any]], list[str], dict[str, float]]:
        """Execute workers asynchronously, falling back to sync on failure."""
        if kwargs.get('use_async_backend', False) or os.environ.get('DEVSQUAD_USE_ASYNC', '').lower() in ('1', 'true'):
            try:
                AsyncLLMBackendFactory.create(self.llm_backend.__class__.__name__)
            except (ImportError, AttributeError, RuntimeError):
                SyncToAsyncAdapter(self.llm_backend)
        else:
            SyncToAsyncAdapter(self.llm_backend)

        if kwargs.get('use_async_cache', False):
            try:
                AsyncLLMCache(cache_dir=self.persist_dir or "data/llm_cache")
            except (ImportError, AttributeError, OSError) as e:
                logger.debug("Async cache init failed: %s", e)

        try:
            from .async_coordinator import AsyncCoordinator

            async_coordinator = AsyncCoordinator(
                scratchpad=self.scratchpad,
                persist_dir=self.persist_dir,
                enable_compression=self.enable_compression,
                compression_threshold=self.compression_threshold,
                llm_backend=self.llm_backend,
                stream=self.stream,
                memory_provider=self.memory_bridge if self.enable_memory else None,
                task_timeout=kwargs.get("task_timeout", 300),
                max_concurrency=kwargs.get("max_concurrency", 10),
                execution_guard=self.execution_guard,
            )

            async_plan = async_coordinator.plan_task(
                task_description=task_description,
                available_roles=[
                    {
                        "role_id": r["role_id"],
                        "role_prompt": str(ROLE_TEMPLATES.get(r["role_id"], {}).get("prompt", "")),
                        "confidence": r.get("confidence", 0.5),
                    }
                    for r in matched_roles
                ],
            )
            async_coordinator.spawn_workers(async_plan)
            exec_result = await async_coordinator.execute_plan(async_plan)

            worker_results, step6_time, step7_time = self.post_dispatch._collect_worker_results(exec_result)
            exec_errors = list(exec_result.errors) if exec_result.errors else []
            return exec_result, worker_results, exec_errors, {"step6_time": step6_time, "step7_time": step7_time}

        except (ImportError, RuntimeError, AttributeError, OSError) as async_err:
            logger.warning("Async dispatch failed, falling back to sync: %s", async_err)
            return self._execute_workers(plan, task_description)


class DispatcherAuditMixin(DispatcherBase):
    """Provides audit logging helpers used by MultiAgentDispatcher."""

    _audit_logger: Any

    def _log_dispatch_end_audit(
        self, user_id: str, success: bool, duration: float
    ) -> None:
        """Log dispatch_end event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_dispatch_end(
                user_id=user_id,
                success=success,
                duration=duration,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_dispatch_end failed: %s", audit_err)

    def _log_dispatch_error_audit(
        self, user_id: str, error: Exception
    ) -> None:
        """Log an error event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_error(
                user_id=user_id,
                error_type=type(error).__name__,
                context={"message": str(error)[:200]},
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_error failed: %s", audit_err)

    def _attach_audit_entries(self, result: DispatchResult) -> None:
        """Attach recent audit entries to the dispatch result."""
        if self._audit_logger is None:
            return
        try:
            entries = self._audit_logger.get_entries(limit=50)
            result.audit_entries = [
                {
                    "event_type": e.event_type,
                    "user_id": e.user_id,
                    "timestamp": e.timestamp,
                    "details": e.details,
                    "entry_hash": e.entry_hash,
                }
                for e in entries
            ]
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit get_entries failed: %s", audit_err)


class DispatcherErrorMixin(DispatcherBase):
    """Provides uniform error handling used by MultiAgentDispatcher."""

    enterprise: Any
    metrics_service: Any

    def _handle_dispatch_error(
        self,
        error: Exception,
        task_description: str,
        tenant_ctx: Any,
        phase: str,
        start_time: float,
        lang: str,
        is_async: bool = False,
    ) -> DispatchResult:
        """Handle dispatch errors uniformly for sync and async paths."""
        prefix = "Async " if is_async else ""
        if isinstance(error, (ValueError, TypeError, AttributeError)):
            logger.error(
                "%sdispatch validation error for task '%s': %s - %s",
                prefix, task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "validation"
        elif isinstance(error, (ImportError, ModuleNotFoundError)):
            logger.error(
                "Missing dependency during %sdispatch of task '%s': %s",
                prefix.lower(), task_description[:50], error, exc_info=True,
            )
            error_key, metrics_label = "backend_unavailable", "dependency"
        else:
            logger.critical(
                "UNEXPECTED ERROR in %sdispatch task '%s': %s - %s",
                prefix.lower(), task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "unknown"

        self.enterprise.clear_tenant_context(tenant_ctx)
        self.metrics_service.safe_record(lambda m: (
            m.record_error(metrics_label, "dispatcher"),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))
        friendly = make_user_friendly_error(error_key, original_error=error)
        return DispatchResult(
            success=False,
            task_description=task_description,
            matched_roles=[],
            summary=friendly.message,
            errors=[friendly.format()],
            duration_seconds=time.time() - start_time,
            lang=lang,
        )


class DispatcherLifecycleMixin(DispatcherBase):
    """Provides graceful shutdown helpers used by MultiAgentDispatcher."""

    warmup_manager: Any
    memory_bridge: Any
    usage_tracker: Any
    enterprise: Any
    _audit_logger: Any

    def shutdown(self) -> None:
        """Gracefully shut down all components."""
        self._shutdown_component(
            self.warmup_manager, "shutdown",
            (RuntimeError, OSError, AttributeError), "Warmup shutdown failed")
        self._shutdown_component(
            self.memory_bridge, "cleanup_expired_memories",
            (OSError, AttributeError, RuntimeError), "Memory cleanup failed")
        self._shutdown_component(
            self.usage_tracker, "persist",
            (OSError, ValueError, AttributeError), "Usage tracker persist failed")
        self._shutdown_component(
            self.enterprise.audit_logger, "force_flush",
            (OSError, AttributeError, RuntimeError), "Audit flush failed")
        self._shutdown_component(
            self._audit_logger, "close",
            (OSError, AttributeError, RuntimeError), "Dispatch audit close failed")
        self._shutdown_component(
            self.enterprise.tenant_manager, "clear_context",
            (AttributeError, RuntimeError, OSError), "Tenant cleanup failed")

    def _shutdown_component(
        self, component: Any, method: str, exc_types: tuple[type[BaseException], ...], msg: str
    ) -> None:
        """Safely call a shutdown method on a component."""
        if not component:
            return
        try:
            getattr(component, method)()
        except exc_types as e:
            logger.debug("%s: %s", msg, e)


class DispatcherStatusMixin(DispatcherBase):
    """Provides status and history helpers used by MultiAgentDispatcher."""

    coordinator: Any
    scratchpad: Any
    batch_scheduler: Any
    consensus_engine: Any
    compressor: Any
    permission_guard: Any
    warmup_manager: Any
    memory_bridge: Any
    skillifier: Any
    quality_guard: Any
    execution_guard: Any
    _dispatch_history: list[Any]
    enterprise: Any

    def get_status(self) -> dict[str, Any]:
        """获取系统状态"""
        status = {
            "version": __version__,
            "persist_dir": self.persist_dir,
            "components": {
                "coordinator": self.coordinator is not None,
                "scratchpad": self.scratchpad is not None,
                "batch_scheduler": self.batch_scheduler is not None,
                "consensus": self.consensus_engine is not None,
                "compressor": self.compressor is not None,
                "permission_guard": self.permission_guard is not None,
                "warmup_manager": self.warmup_manager is not None,
                "memory_bridge": self.memory_bridge is not None,
                "skillifier": self.skillifier is not None,
                "quality_guard": self.quality_guard is not None,
                "performance_monitor": True,
                "execution_guard": self.execution_guard is not None,
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }
        self._append_perf_status(status)
        self._append_warmup_status(status)
        self._append_memory_status(status)
        return status

    def _append_perf_status(self, status: dict[str, Any]) -> None:
        """Append performance stats to status dict."""
        try:
            perf_stats = self._perf_monitor.get_statistics()
            status["performance"] = perf_stats
            regression = self._perf_monitor.detect_regression()
            if regression:
                status["regression_detected"] = regression
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.debug("Performance stats collection failed: %s", e)

    def _append_warmup_status(self, status: dict[str, Any]) -> None:
        """Append warmup metrics to status dict."""
        if not self.warmup_manager:
            return
        try:
            metrics = self.warmup_manager.get_metrics()
            status["warmup_metrics"] = {
                "cache_size": metrics.cache_size,
                "hit_rate": round(metrics.cache_hit_rate, 3) if metrics.cache_hit_rate else 0,
                "tasks_completed": metrics.tasks_completed,
                "eager_duration_ms": round(metrics.eager_duration_ms, 2),
            }
        except (AttributeError, ValueError, RuntimeError):
            status["warmup_metrics"] = None

    def _append_memory_status(self, status: dict[str, Any]) -> None:
        """Append memory stats to status dict."""
        if not self.memory_bridge:
            return
        try:
            mem_stats = self.memory_bridge.get_statistics()
            status["memory_stats"] = {
                "total_memories": mem_stats.total_memories,
                "by_type_counts": mem_stats.by_type_counts,
                "index_built": mem_stats.index_built,
            }
        except (AttributeError, ValueError, OSError):
            status["memory_stats"] = None

    def get_history(self, limit: int = 10, **kwargs: Any) -> list[dict[str, Any]]:
        """Get dispatch history."""
        if self.enterprise.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.enterprise.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return []
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self._perf_monitor.get_statistics()

    def check_performance_regression(self) -> dict[str, Any] | None:
        """Check for performance regression."""
        return self._perf_monitor.detect_regression()


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
