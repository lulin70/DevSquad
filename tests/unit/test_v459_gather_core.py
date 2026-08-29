#!/usr/bin/env python3
"""V4.5.9 — Shared gather core unit tests (AC-C1/C3/C5, PRD §4 test matrix).

Covers:
- gather semantics: submission-order results (R1 new contract)
- fault tolerance: single failure does not lose sibling results (hard constraint)
- BaseException defense (KeyboardInterrupt/SystemExit) -> failure WorkerResult
- Semaphore cap: peak concurrency <= max_concurrency
- anti-ghost counter increments per batch entry
- edge cases: zero tasks / max_concurrency=0
"""

import asyncio

import pytest

from scripts.collaboration.gather_core import (
    execute_batch_gather,
    get_call_counter_gather,
)
from scripts.collaboration.models import TaskDefinition, WorkerResult


def _task(tid: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=tid, description=f"task {tid}", role_id="architect", role_prompt="p"
    )


async def _ok(task: TaskDefinition) -> WorkerResult:
    return WorkerResult(worker_id=f"w-{task.task_id}", task_id=task.task_id, success=True)


class TestGatherSemantics:
    @pytest.mark.asyncio
    async def test_results_follow_submission_order(self):
        """R1 new contract: results keep submission order, not completion order."""

        async def run_one(task: TaskDefinition) -> WorkerResult:
            # Later tasks finish first — order must still follow submission.
            delay = {"t1": 0.03, "t2": 0.02, "t3": 0.01}[task.task_id]
            await asyncio.sleep(delay)
            return WorkerResult(
                worker_id=f"w-{task.task_id}", task_id=task.task_id, success=True
            )

        results = await execute_batch_gather(
            [_task("t1"), _task("t2"), _task("t3")], run_one, 3
        )
        assert [r.task_id for r in results] == ["t1", "t2", "t3"]

    @pytest.mark.asyncio
    async def test_results_are_worker_results(self):
        results = await execute_batch_gather([_task("a")], _ok, 1)
        assert len(results) == 1
        assert isinstance(results[0], WorkerResult)
        assert results[0].success is True
        assert results[0].worker_id == "w-a"

    @pytest.mark.asyncio
    async def test_results_identity_preserved(self):
        """run_one's WorkerResult objects are passed through unmodified."""
        expected = WorkerResult(worker_id="w-x", task_id="x", success=True)

        async def run_one(_task: TaskDefinition) -> WorkerResult:
            return expected

        results = await execute_batch_gather([_task("x")], run_one, 1)
        assert results[0] is expected


class TestGatherFaultTolerance:
    @pytest.mark.asyncio
    async def test_single_failure_keeps_other_results(self):
        """Hard constraint: 3 tasks, 1 fails -> 3 results (2 success, 1 failure).

        Mirrors the real run_one contract: per-task Exception is caught by the
        callback and translated into a failure WorkerResult with task identity.
        """

        async def run_one(task: TaskDefinition) -> WorkerResult:
            try:
                if task.task_id == "t2":
                    raise RuntimeError("boom")
                return await _ok(task)
            except Exception as e:
                return WorkerResult(
                    worker_id="unknown", task_id=task.task_id, success=False, error=str(e)
                )

        results = await execute_batch_gather(
            [_task("t1"), _task("t2"), _task("t3")], run_one, 3
        )
        assert len(results) == 3
        by_id = {r.task_id: r for r in results}
        assert by_id["t1"].success is True
        assert by_id["t3"].success is True
        assert by_id["t2"].success is False
        assert "boom" in (by_id["t2"].error or "")

    @pytest.mark.asyncio
    async def test_order_preserved_with_middle_failure(self):
        """A failure occupies its positional slot; siblings keep submission order."""

        async def run_one(task: TaskDefinition) -> WorkerResult:
            try:
                if task.task_id == "t2":
                    raise RuntimeError("mid failure")
                return await _ok(task)
            except Exception as e:
                return WorkerResult(
                    worker_id="unknown", task_id=task.task_id, success=False, error=str(e)
                )

        results = await execute_batch_gather(
            [_task("t1"), _task("t2"), _task("t3")], run_one, 3
        )
        assert [r.task_id for r in results] == ["t1", "t2", "t3"]

    @pytest.mark.asyncio
    async def test_all_failures_return_all_results(self):
        async def run_one(task: TaskDefinition) -> WorkerResult:
            try:
                raise ValueError("always fails")
            except Exception as e:
                return WorkerResult(
                    worker_id="unknown", task_id=task.task_id, success=False, error=str(e)
                )

        results = await execute_batch_gather([_task("x"), _task("y")], run_one, 2)
        assert len(results) == 2
        assert all(r.success is False for r in results)

    @pytest.mark.asyncio
    async def test_escaped_exception_defensive_conversion(self):
        """A rogue run_one that does not catch Exception still yields 3 results,
        with the escaped one converted to the <unknown> failure WorkerResult."""

        async def run_one(task: TaskDefinition) -> WorkerResult:
            if task.task_id == "t2":
                raise RuntimeError("rogue boom")
            return await _ok(task)

        results = await execute_batch_gather(
            [_task("t1"), _task("t2"), _task("t3")], run_one, 3
        )
        assert len(results) == 3
        assert results[0].success is True
        assert results[2].success is True
        assert results[1].success is False
        assert results[1].worker_id == "<unknown>"
        assert results[1].task_id == "<unknown>"
        assert "rogue boom" in (results[1].error or "")

    @pytest.mark.asyncio
    async def test_baseexception_defense(self):
        """KeyboardInterrupt escaping run_one must not unwind the batch
        (bpo-32528: gather(return_exceptions=True) does not capture it)."""

        async def run_one(task: TaskDefinition) -> WorkerResult:
            if task.task_id == "t2":
                raise KeyboardInterrupt
            return await _ok(task)

        results = await execute_batch_gather(
            [_task("t1"), _task("t2"), _task("t3")], run_one, 3
        )
        assert len(results) == 3
        assert results[0].success is True
        assert results[2].success is True
        assert results[1].success is False
        assert results[1].worker_id == "<unknown>"
        assert results[1].task_id == "<unknown>"


class TestGatherSemaphore:
    @pytest.mark.asyncio
    async def test_peak_concurrency_capped(self):
        active = 0
        peak = 0

        async def run_one(task: TaskDefinition) -> WorkerResult:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.005)
            active -= 1
            return await _ok(task)

        tasks = [_task(f"t{i}") for i in range(10)]
        results = await execute_batch_gather(tasks, run_one, 3)
        assert len(results) == 10
        assert all(r.success for r in results)
        assert peak <= 3

    @pytest.mark.asyncio
    async def test_semaphore_reaches_max_concurrency(self):
        active = 0
        peak = 0

        async def run_one(task: TaskDefinition) -> WorkerResult:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.005)
            active -= 1
            return await _ok(task)

        tasks = [_task(f"t{i}") for i in range(12)]
        await execute_batch_gather(tasks, run_one, 3)
        assert peak == 3


class TestGatherCounter:
    @pytest.mark.asyncio
    async def test_counter_increments_per_batch(self):
        before = get_call_counter_gather()
        await execute_batch_gather([_task("a")], _ok, 1)
        await execute_batch_gather([_task("b")], _ok, 1)
        assert get_call_counter_gather() == before + 2

    @pytest.mark.asyncio
    async def test_counter_exposes_module_level_value(self):
        from scripts.collaboration import gather_core

        assert gather_core._call_counter_gather == get_call_counter_gather()


class TestGatherEdgeCases:
    @pytest.mark.asyncio
    async def test_zero_tasks_returns_empty(self):
        assert await execute_batch_gather([], _ok, 4) == []

    @pytest.mark.asyncio
    async def test_max_concurrency_zero_does_not_hang(self):
        """max_concurrency<=0 is treated as unbounded (clamped to len(tasks))."""
        results = await execute_batch_gather([_task("a"), _task("b")], _ok, 0)
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_more_tasks_than_concurrency_all_complete(self):
        tasks = [_task(f"t{i}") for i in range(7)]
        results = await execute_batch_gather(tasks, _ok, 2)
        assert len(results) == 7
        assert [r.task_id for r in results] == [t.task_id for t in tasks]
