#!/usr/bin/env python3
"""Shared asyncio.gather execution core (V4.5.9).

Single source of truth for parallel batch execution. Both the sync
Coordinator (via the asyncio.run bridge in ``_execute_parallel``) and the
AsyncCoordinator (native) delegate here. Do NOT reimplement gather
semantics elsewhere.

Semantics (the single implementation):
1. ``asyncio.Semaphore(max_concurrency)`` caps in-flight tasks (AC-C5).
2. ``asyncio.gather(..., return_exceptions=True)`` — a single Worker failure
   never discards the results of the other parallel Workers (hard constraint).
3. BaseException defense — KeyboardInterrupt/SystemExit (or any exception that
   escapes ``run_one``) is converted into a failure ``WorkerResult`` instead of
   unwinding the whole batch.
4. Results keep submission order (``tasks`` order) — a deliberate behavior
   change from the legacy completion-order thread pool (PRD V4.5.9 R1, logged).

``run_one`` is the per-task callback injected by the calling Coordinator: it
owns worker routing, briefing, timeout and retry, and is expected to catch
per-task ``Exception`` itself (translating them into ``WorkerResult``). This
core only owns the gather mechanism — keeping it small is a design constraint.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .models import TaskDefinition, WorkerResult

logger = logging.getLogger(__name__)

# V4.5.9 anti-ghost counter: bumped once per execute_batch_gather() entry.
# Verified by scripts/check_module_activation.py (GatherCore_V459.1).
_call_counter_gather = 0


def _inc_call_counter_gather() -> None:
    """Bump the module-level anti-ghost counter."""
    global _call_counter_gather
    _call_counter_gather += 1


def get_call_counter_gather() -> int:
    """Return the current anti-ghost counter value."""
    return _call_counter_gather


async def execute_batch_gather(
    tasks: list[TaskDefinition],
    run_one: Callable[[TaskDefinition], Awaitable[WorkerResult]],
    max_concurrency: int,
) -> list[WorkerResult]:
    """Execute ``tasks`` concurrently through ``run_one`` under a semaphore.

    Args:
        tasks: Task definitions in submission order.
        run_one: Per-task coroutine factory injected by the calling
            Coordinator (routes to ``Worker.aexecute`` or a sync bridge).
        max_concurrency: Semaphore cap on in-flight tasks. Non-positive
            values are treated as unbounded (clamped to ``len(tasks)``).

    Returns:
        WorkerResult list in submission order; never shorter than ``tasks``.
    """
    _inc_call_counter_gather()
    if not tasks:
        return []

    limit = max_concurrency if max_concurrency and max_concurrency > 0 else len(tasks)
    semaphore = asyncio.Semaphore(limit)

    async def _run_one_limited(task: TaskDefinition) -> WorkerResult:
        async with semaphore:
            try:
                return await run_one(task)
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                # BaseException defense (AC-C1 hard constraint). Since Python
                # 3.8 (bpo-32528) gather(return_exceptions=True) does NOT
                # capture KeyboardInterrupt/SystemExit raised inside a child —
                # they would unwind the whole batch. Convert any escaped
                # exception into a failure WorkerResult so one Worker can
                # never discard the sibling results.
                logger.error("Worker raised unexpected exception in gather: %s", e, exc_info=e)
                return WorkerResult(
                    worker_id="<unknown>",
                    task_id="<unknown>",
                    success=False,
                    error=f"Unexpected exception: {e!r}",
                )

    raw_results = await asyncio.gather(
        *(_run_one_limited(t) for t in tasks),
        return_exceptions=True,
    )

    results: list[WorkerResult] = []
    for r in raw_results:
        if isinstance(r, BaseException):
            # Belt-and-suspenders: should be unreachable because
            # _run_one_limited converts escaped exceptions, but a defensive
            # conversion keeps the result list pure WorkerResult.
            logger.error("Worker raised unexpected exception in gather: %s", r, exc_info=r)
            results.append(
                WorkerResult(
                    worker_id="<unknown>",
                    task_id="<unknown>",
                    success=False,
                    error=f"Unexpected exception: {r!r}",
                )
            )
        else:
            results.append(r)
    return results
