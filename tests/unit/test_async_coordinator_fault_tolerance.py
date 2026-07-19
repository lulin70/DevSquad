"""Tests for AsyncCoordinator fault tolerance (P0-2 / TD-2).

Validates that one Worker failure does not discard the results of all other
parallel Workers in `_execute_parallel_async`. Before V4.1.2, the call used
`asyncio.gather(*tasks, return_exceptions=False)`, which caused a single
Worker exception to propagate and lose all sibling results.

Coverage target: `scripts/collaboration/async_coordinator.py` from 0% → ≥60%.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from scripts.collaboration.async_coordinator import AsyncCoordinator
from scripts.collaboration.models_base import TaskDefinition, WorkerResult
from scripts.collaboration.models_lifecycle import BatchMode, TaskBatch
from scripts.collaboration.scratchpad import Scratchpad


@pytest.fixture
def coordinator(tmp_path) -> AsyncCoordinator:
    """Create an AsyncCoordinator with a temporary scratchpad."""
    scratchpad = Scratchpad(persist_dir=str(tmp_path / "scratchpad"))
    return AsyncCoordinator(
        scratchpad=scratchpad,
        enable_compression=False,
        briefing_mode=False,
        task_timeout=10.0,
    )


def _make_task(role_id: str, task_id: str | None = None) -> TaskDefinition:
    return TaskDefinition(
        task_id=task_id or f"task-{role_id}",
        description=f"Test task for {role_id}",
        role_id=role_id,
    )


def _make_batch(tasks: list[TaskDefinition]) -> TaskBatch:
    return TaskBatch(
        mode=BatchMode.PARALLEL,
        tasks=tasks,
        max_concurrency=len(tasks),
    )


def _make_worker(worker_id: str, result: WorkerResult) -> MagicMock:
    """Create a mock Worker whose `worker_id` and `execute` return the given result."""
    worker = MagicMock()
    worker.worker_id = worker_id
    worker.execute = MagicMock(return_value=result)
    return worker


class TestAsyncCoordinatorFaultTolerance:
    """P0-2: One Worker failure must not discard other Workers' results."""

    @pytest.mark.asyncio
    async def test_one_worker_failure_does_not_lose_others(self, coordinator: AsyncCoordinator) -> None:
        """When one Worker raises, the other parallel Workers' results survive.

        Before V4.1.2: `return_exceptions=False` caused asyncio.gather to
        propagate the first exception, losing all sibling results.
        """
        task_a = _make_task("architect", "task-a")
        task_b = _make_task("tester", "task-b")
        task_c = _make_task("security", "task-c")
        batch = _make_batch([task_a, task_b, task_c])

        # Worker A succeeds; Worker B's async wrapper raises; Worker C succeeds.
        result_a = WorkerResult(worker_id="arch-1", task_id="task-a", success=True, output={"role": "architect"})
        result_c = WorkerResult(worker_id="sec-1", task_id="task-c", success=True, output={"role": "security"})

        worker_a = _make_worker("arch-1", result_a)
        # Worker B has a real worker (so _get_worker_for_task returns it),
        # but the AsyncWorkerWrapper raises mid-execution.
        worker_b = _make_worker("test-1", WorkerResult(worker_id="test-1", task_id="task-b", success=True))
        worker_c = _make_worker("sec-1", result_c)

        # Wire _get_worker_for_task by task_id (TaskDefinition is unhashable).
        coordinator._get_worker_for_task = MagicMock(side_effect=lambda t: {  # type: ignore[assignment]
            "task-a": worker_a,
            "task-b": worker_b,
            "task-c": worker_c,
        }.get(t.task_id))

        # Force the AsyncWorkerWrapper for B to raise, simulating mid-execution failure.
        async def _failing_async_worker(worker: MagicMock, task: TaskDefinition) -> WorkerResult:
            if task.task_id == "task-b":
                raise RuntimeError("Worker B exploded mid-flight")
            # A and C return their results via the underlying mock.
            return worker.execute(task)

        coordinator._get_async_worker = MagicMock(side_effect=lambda w: _AsyncWorkerStub(w, _failing_async_worker))  # type: ignore[assignment]

        results = await coordinator._execute_parallel_async(batch)

        # All three tasks produced a result — none was lost.
        assert len(results) == 3, f"Expected 3 results (one per task), got {len(results)}"
        # Successful Workers' outputs survived.
        task_ids = {r.task_id for r in results}
        assert task_ids == {"task-a", "task-b", "task-c"}, f"Missing task IDs: {task_ids}"
        # Worker B's failure was wrapped into a failed WorkerResult.
        failed = [r for r in results if not r.success]
        assert len(failed) == 1, f"Expected exactly 1 failed result, got {len(failed)}"
        assert failed[0].task_id == "task-b"
        assert "exploded" in (failed[0].error or "")

    @pytest.mark.asyncio
    async def test_all_workers_succeed_returns_all_results(self, coordinator: AsyncCoordinator) -> None:
        """Happy path: all Workers succeed, all results returned."""
        task_a = _make_task("architect", "task-a")
        task_b = _make_task("tester", "task-b")
        batch = _make_batch([task_a, task_b])

        result_a = WorkerResult(worker_id="arch-1", task_id="task-a", success=True)
        result_b = WorkerResult(worker_id="test-1", task_id="task-b", success=True)

        worker_a = _make_worker("arch-1", result_a)
        worker_b = _make_worker("test-1", result_b)

        coordinator._get_worker_for_task = MagicMock(side_effect=lambda t: {  # type: ignore[assignment]
            "task-a": worker_a,
            "task-b": worker_b,
        }.get(t.task_id))
        coordinator._get_async_worker = MagicMock(side_effect=lambda w: _AsyncWorkerStub(w, None))  # type: ignore[assignment]

        results = await coordinator._execute_parallel_async(batch)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert {r.task_id for r in results} == {"task-a", "task-b"}

    @pytest.mark.asyncio
    async def test_no_worker_for_task_returns_failed_result(self, coordinator: AsyncCoordinator) -> None:
        """When _get_worker_for_task returns None, a failed WorkerResult is produced."""
        task = _make_task("nonexistent", "task-x")
        batch = _make_batch([task])

        # No worker registered for this task.
        coordinator._get_worker_for_task = MagicMock(return_value=None)  # type: ignore[assignment]

        results = await coordinator._execute_parallel_async(batch)

        assert len(results) == 1
        assert not results[0].success
        assert "No worker found" in (results[0].error or "")
        assert results[0].task_id == "task-x"

    @pytest.mark.asyncio
    async def test_empty_batch_returns_empty_list(self, coordinator: AsyncCoordinator) -> None:
        """An empty TaskBatch produces an empty result list (no gather call)."""
        batch = _make_batch([])
        results = await coordinator._execute_parallel_async(batch)
        assert results == []


class _AsyncWorkerStub:
    """Minimal AsyncWorkerWrapper stub for testing.

    If `override` is provided, it is awaited instead of the underlying worker.
    This lets tests inject failures (raise exceptions) for specific tasks.
    """

    def __init__(self, worker: MagicMock, override: Any) -> None:
        self.worker = worker
        self._override = override
        self.timeout = None

    async def execute(self, task: TaskDefinition) -> WorkerResult:
        if self._override is not None:
            return await self._override(self.worker, task)
        return self.worker.execute(task)
