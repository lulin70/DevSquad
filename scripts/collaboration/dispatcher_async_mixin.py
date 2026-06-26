"""Async dispatch mixin for MultiAgentDispatcher.

Extracts async worker execution so the main dispatcher file can focus on
the synchronous dispatch path.
"""

import logging
import os
import time
from typing import Any, cast

from .async_adapter import SyncToAsyncAdapter
from .async_llm_backend import AsyncLLMBackendFactory
from .dispatch_models import ROLE_TEMPLATES, DispatchResult
from .dispatcher_base import DispatcherBase
from .llm_cache_async import AsyncLLMCache
from .usage_tracker import track_usage

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
