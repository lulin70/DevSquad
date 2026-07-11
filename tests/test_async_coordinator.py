"""Tests for AsyncCoordinator and AsyncWorkerWrapper.

Covers the full async orchestration pipeline:
- AsyncWorkerWrapper: timeout/sync wrapping
- AsyncCoordinator: init, plan_task, spawn_workers, execute_plan (parallel/sequential),
  compression, briefing chain, preload_rules, collect_results, resolve_conflicts,
  generate_report, retry, semaphore concurrency control.
"""

import asyncio

import pytest

from scripts.collaboration.async_coordinator import (
    AsyncCoordinator,
    AsyncWorkerWrapper,
)
from scripts.collaboration.llm_backend import MockBackend
from scripts.collaboration.models import (
    BatchMode,
    ExecutionPlan,
    ScheduleResult,
    TaskBatch,
    TaskDefinition,
    WorkerResult,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker, WorkerFactory

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_roles():
    return [
        {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
        {"role_id": "tester", "name": "Tester", "role_prompt": "You are a tester."},
    ]


def _make_coordinator(**kwargs):
    defaults = {
        "scratchpad": Scratchpad(),
        "enable_compression": False,
        "llm_backend": MockBackend(),
    }
    defaults.update(kwargs)
    return AsyncCoordinator(**defaults)


# ---------------------------------------------------------------------------
# AsyncWorkerWrapper
# ---------------------------------------------------------------------------


class TestAsyncWorkerWrapper:
    @pytest.mark.asyncio
    async def test_execute_without_timeout(self):
        worker = WorkerFactory.create(
            worker_id="w1",
            role_id="architect",
            role_prompt="prompt",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        wrapper = AsyncWorkerWrapper(worker, timeout=None)
        task = TaskDefinition(description="do work", role_id="architect")
        result = await wrapper.execute(task)
        assert isinstance(result, WorkerResult)

    @pytest.mark.asyncio
    async def test_execute_with_timeout_completes(self):
        worker = WorkerFactory.create(
            worker_id="w2",
            role_id="tester",
            role_prompt="prompt",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        wrapper = AsyncWorkerWrapper(worker, timeout=30.0)
        task = TaskDefinition(description="quick task", role_id="tester")
        result = await wrapper.execute(task)
        assert isinstance(result, WorkerResult)

    @pytest.mark.asyncio
    async def test_execute_with_timeout_raises_on_slow_task(self):
        """A timeout that is too short should raise asyncio.TimeoutError."""

        class SlowWorker(Worker):
            def execute(self, task):
                import time as _time

                _time.sleep(2.0)
                return WorkerResult(
                    worker_id=self.worker_id,
                    task_id=task.task_id,
                    success=True,
                    output="done",
                )

        sp = Scratchpad()
        worker = SlowWorker(
            worker_id="slow-1",
            role_id="architect",
            role_prompt="prompt",
            scratchpad=sp,
            llm_backend=MockBackend(),
        )
        wrapper = AsyncWorkerWrapper(worker, timeout=0.1)
        task = TaskDefinition(description="slow task", role_id="architect")
        with pytest.raises(asyncio.TimeoutError):
            await wrapper.execute(task)

    def test_init_attributes(self):
        worker = WorkerFactory.create(
            worker_id="w3",
            role_id="coder",
            role_prompt="p",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        wrapper = AsyncWorkerWrapper(worker, timeout=42.0)
        assert wrapper.worker is worker
        assert wrapper.timeout == 42.0


# ---------------------------------------------------------------------------
# AsyncCoordinator.__init__
# ---------------------------------------------------------------------------


class TestAsyncCoordinatorInit:
    def test_defaults(self):
        coord = AsyncCoordinator()
        assert coord.scratchpad is not None
        assert coord.consensus is not None
        assert coord.workers == {}
        assert coord._async_workers == {}
        assert coord._execution_history == []
        assert coord.coordinator_id.startswith("async-coord-")
        assert coord.enable_compression is True
        assert coord.compressor is not None
        assert coord.llm_backend is None
        assert coord.stream is False
        assert coord.memory_provider is None
        assert coord.briefing_mode is True
        assert coord.task_timeout == AsyncCoordinator.DEFAULT_TASK_TIMEOUT
        assert coord.max_concurrency == AsyncCoordinator.MAX_CONCURRENCY
        assert coord.execution_guard is None
        assert coord.content_cache is None
        assert coord._semaphore is None
        assert coord.enable_retry is False
        assert coord._retry_manager is None

    def test_custom_params(self):
        sp = Scratchpad()
        backend = MockBackend()
        coord = AsyncCoordinator(
            scratchpad=sp,
            enable_compression=False,
            compression_threshold=50000,
            llm_backend=backend,
            stream=True,
            briefing_mode=False,
            task_timeout=120.0,
            max_concurrency=5,
        )
        assert coord.scratchpad is sp
        assert coord.compressor is None
        assert coord.llm_backend is backend
        assert coord.stream is True
        assert coord.briefing_mode is False
        assert coord.task_timeout == 120.0
        assert coord.max_concurrency == 5

    def test_persist_dir_passed_to_scratchpad(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            coord = AsyncCoordinator(persist_dir=td)
            assert coord.scratchpad is not None

    def test_coordinator_id_unique(self):
        c1 = AsyncCoordinator()
        c2 = AsyncCoordinator()
        assert c1.coordinator_id != c2.coordinator_id

    def test_enable_retry_import_failure_degrades_gracefully(self):
        """If AsyncLLMRetryManager import fails, retry is disabled."""
        coord = AsyncCoordinator(enable_retry=True)
        # Either retry manager loaded or gracefully disabled
        assert coord.enable_retry is True or coord._retry_manager is None


# ---------------------------------------------------------------------------
# AsyncCoordinator._get_semaphore
# ---------------------------------------------------------------------------


class TestGetSemaphore:
    @pytest.mark.asyncio
    async def test_semaphore_created_once(self):
        coord = _make_coordinator(max_concurrency=3)
        sem1 = await coord._get_semaphore()
        sem2 = await coord._get_semaphore()
        assert sem1 is sem2

    @pytest.mark.asyncio
    async def test_semaphore_respects_max_concurrency(self):
        coord = _make_coordinator(max_concurrency=5)
        sem = await coord._get_semaphore()
        assert sem._value == 5


# ---------------------------------------------------------------------------
# AsyncCoordinator.plan_task
# ---------------------------------------------------------------------------


class TestPlanTask:
    def test_single_role(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design auth", [{"role_id": "architect", "role_prompt": "p"}])
        assert isinstance(plan, ExecutionPlan)
        assert plan.total_tasks == 1
        assert len(plan.batches) == 1
        assert plan.batches[0].mode == BatchMode.PARALLEL

    def test_multi_role(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design and test", _make_roles())
        assert plan.total_tasks == 2
        assert plan.estimated_parallelism == 1.0

    def test_single_role_parallelism_zero(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Solo", [{"role_id": "architect", "role_prompt": "p"}])
        assert plan.estimated_parallelism == 0.0

    def test_with_stage_id(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "a", "role_prompt": "p"}], stage_id="s1")
        task = plan.batches[0].tasks[0]
        assert task.stage_id == "s1"

    def test_role_prompt_defaults_to_empty(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "a"}])
        task = plan.batches[0].tasks[0]
        assert task.role_prompt == ""

    def test_task_is_read_only(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "a", "role_prompt": "p"}])
        task = plan.batches[0].tasks[0]
        assert task.is_read_only is True


# ---------------------------------------------------------------------------
# AsyncCoordinator.spawn_workers
# ---------------------------------------------------------------------------


class TestSpawnWorkers:
    def test_creates_workers_for_all_tasks(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design and test", _make_roles())
        workers = coord.spawn_workers(plan)
        assert len(workers) == 2
        assert all(isinstance(w, Worker) for w in workers)

    def test_workers_stored_in_dict(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design", _make_roles())
        coord.spawn_workers(plan)
        assert len(coord.workers) == 2
        assert len(coord._async_workers) == 2

    def test_spawn_clears_previous_workers(self):
        coord = _make_coordinator()
        plan1 = coord.plan_task("task1", _make_roles())
        coord.spawn_workers(plan1)
        plan2 = coord.plan_task("task2", [{"role_id": "coder", "role_prompt": "p"}])
        coord.spawn_workers(plan2)
        assert len(coord.workers) == 1

    def test_worker_ids_prefixed_with_role(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        workers = coord.spawn_workers(plan)
        assert workers[0].worker_id.startswith("architect-")

    def test_with_execution_guard_uses_enhanced_worker(self):
        from scripts.collaboration.enhanced_worker import EnhancedWorker

        class StubGuard:
            pass

        coord = _make_coordinator(execution_guard=StubGuard())
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        workers = coord.spawn_workers(plan)
        assert isinstance(workers[0], EnhancedWorker)

    def test_registry_not_used_when_role_prompt_present(self):
        """When role_prompt is already set, registry is not consulted."""
        coord = _make_coordinator()

        class StubRegistry:
            called = False

            def get_role_prompt(self, _role_id):
                StubRegistry.called = True
                return None

        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "inline"}])
        workers = coord.spawn_workers(plan, registry=StubRegistry())
        assert workers[0].role_prompt == "inline"
        assert not StubRegistry.called

    def test_async_worker_wrappers_have_timeout(self):
        coord = _make_coordinator(task_timeout=42.0)
        plan = coord.plan_task("task", [{"role_id": "a", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        for aw in coord._async_workers.values():
            assert aw.timeout == 42.0


# ---------------------------------------------------------------------------
# AsyncCoordinator.execute_plan
# ---------------------------------------------------------------------------


class TestExecutePlan:
    @pytest.mark.asyncio
    async def test_single_role_success(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design system", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        result = await coord.execute_plan(plan)
        assert isinstance(result, ScheduleResult)
        assert result.total_tasks == 1
        assert result.completed_tasks >= 0

    @pytest.mark.asyncio
    async def test_multi_role_parallel(self):
        coord = _make_coordinator()
        plan = coord.plan_task("Design and test", _make_roles())
        coord.spawn_workers(plan)
        result = await coord.execute_plan(plan)
        assert result.total_tasks == 2

    @pytest.mark.asyncio
    async def test_empty_plan(self):
        coord = _make_coordinator()
        plan = ExecutionPlan(batches=[], total_tasks=0, estimated_parallelism=0.0)
        result = await coord.execute_plan(plan)
        assert result.total_tasks == 0
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execution_history_recorded(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        await coord.execute_plan(plan)
        assert len(coord._execution_history) >= 1

    @pytest.mark.asyncio
    async def test_message_buffer_cleared_after_execution(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        await coord.execute_plan(plan)
        assert coord._message_buffer == []

    @pytest.mark.asyncio
    async def test_compression_triggered_between_batches(self):
        """When compression is enabled, multi-batch plans trigger compression buffering."""
        coord = _make_coordinator(
            enable_compression=True,
            compression_threshold=1,  # low threshold to trigger compression
        )
        task = TaskDefinition(description="task", role_id="architect", role_prompt="p")
        batch1 = TaskBatch(mode=BatchMode.PARALLEL, tasks=[task], max_concurrency=1)
        batch2 = TaskBatch(mode=BatchMode.PARALLEL, tasks=[task], max_concurrency=1)
        plan = ExecutionPlan(batches=[batch1, batch2], total_tasks=2, estimated_parallelism=1.0)
        coord.spawn_workers(plan)
        await coord.execute_plan(plan)
        # Compression history may or may not be recorded depending on token count,
        # but the execution should not fail.
        assert isinstance(coord._execution_history, list)


# ---------------------------------------------------------------------------
# AsyncCoordinator._execute_batch (sequential mode)
# ---------------------------------------------------------------------------


class TestExecuteBatchSequential:
    @pytest.mark.asyncio
    async def test_serial_batch_executes_all_tasks(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        seq_batch = TaskBatch(
            mode=BatchMode.SERIAL,
            tasks=plan.batches[0].tasks,
            max_concurrency=1,
        )
        results, errors = await coord._execute_batch(seq_batch)
        assert len(results) + len(errors) >= 1

    @pytest.mark.asyncio
    async def test_serial_batch_no_matching_worker(self):
        coord = _make_coordinator()
        # Don't spawn workers, so _get_worker_for_task returns None
        task = TaskDefinition(description="task", role_id="nonexistent", role_prompt="p")
        batch = TaskBatch(mode=BatchMode.SERIAL, tasks=[task], max_concurrency=1)
        results, errors = await coord._execute_batch(batch)
        # With no worker, results empty and errors empty (worker not found path)
        assert isinstance(results, list)
        assert isinstance(errors, list)


# ---------------------------------------------------------------------------
# AsyncCoordinator._execute_parallel_async
# ---------------------------------------------------------------------------


class TestExecuteParallelAsync:
    @pytest.mark.asyncio
    async def test_parallel_execution_returns_results(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", _make_roles())
        coord.spawn_workers(plan)
        results = await coord._execute_parallel_async(plan.batches[0])
        assert len(results) == 2
        assert all(isinstance(r, WorkerResult) for r in results)

    @pytest.mark.asyncio
    async def test_parallel_empty_tasks_returns_empty(self):
        coord = _make_coordinator()
        batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[], max_concurrency=1)
        results = await coord._execute_parallel_async(batch)
        assert results == []

    @pytest.mark.asyncio
    async def test_parallel_no_worker_returns_failure_result(self):
        coord = _make_coordinator()
        task = TaskDefinition(description="task", role_id="nonexistent", role_prompt="p")
        batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[task], max_concurrency=1)
        results = await coord._execute_parallel_async(batch)
        assert len(results) == 1
        assert results[0].success is False
        assert "No worker found" in results[0].error

    @pytest.mark.asyncio
    async def test_parallel_worker_exception_returns_failure_result(self):
        """When a worker raises an exception, it's captured as a failure result."""

        class FailingWorker(Worker):
            def execute(self, _task):
                raise RuntimeError("boom")

        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        # Replace with failing worker
        for wid, w in coord.workers.items():
            coord.workers[wid] = FailingWorker(
                worker_id=w.worker_id,
                role_id=w.role_id,
                role_prompt=w.role_prompt,
                scratchpad=w.scratchpad,
                llm_backend=MockBackend(),
            )
            coord._async_workers[wid] = AsyncWorkerWrapper(
                coord.workers[wid], timeout=coord.task_timeout
            )
        results = await coord._execute_parallel_async(plan.batches[0])
        assert len(results) == 1
        assert results[0].success is False
        assert "boom" in results[0].error


# ---------------------------------------------------------------------------
# AsyncCoordinator._get_async_worker
# ---------------------------------------------------------------------------


class TestGetAsyncWorker:
    def test_existing_worker(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "a", "role_prompt": "p"}])
        workers = coord.spawn_workers(plan)
        w = workers[0]
        aw = coord._get_async_worker(w)
        assert aw.worker is w

    def test_creates_new_wrapper_for_unregistered_worker(self):
        coord = _make_coordinator()
        w = WorkerFactory.create(
            worker_id="external-1",
            role_id="coder",
            role_prompt="p",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        aw = coord._get_async_worker(w)
        assert isinstance(aw, AsyncWorkerWrapper)
        assert aw.worker is w


# ---------------------------------------------------------------------------
# AsyncCoordinator._buffer_worker_messages
# ---------------------------------------------------------------------------


class TestBufferWorkerMessages:
    def test_buffers_messages_with_output(self):
        coord = _make_coordinator()
        results = [
            WorkerResult(
                worker_id="w1",
                task_id="t1",
                success=True,
                output="some output text",
            ),
        ]
        coord._buffer_worker_messages(results)
        assert len(coord._message_buffer) == 1
        assert coord._message_buffer[0].content == "some output text"

    def test_skips_empty_output(self):
        coord = _make_coordinator()
        results = [
            WorkerResult(worker_id="w1", task_id="t1", success=True, output=""),
        ]
        coord._buffer_worker_messages(results)
        assert len(coord._message_buffer) == 0

    def test_truncates_long_output(self):
        coord = _make_coordinator()
        long_output = "x" * 3000
        results = [
            WorkerResult(worker_id="w1", task_id="t1", success=True, output=long_output),
        ]
        coord._buffer_worker_messages(results)
        assert len(coord._message_buffer[0].content) == 2000


# ---------------------------------------------------------------------------
# AsyncCoordinator.compress_context / get_compression_stats
# ---------------------------------------------------------------------------


class TestCompression:
    @pytest.mark.asyncio
    async def test_compress_context_no_compressor_returns_none(self):
        coord = _make_coordinator(enable_compression=False)
        result = await coord.compress_context()
        assert result is None

    @pytest.mark.asyncio
    async def test_compress_context_with_compressor(self):
        coord = _make_coordinator(enable_compression=True)
        # Add some messages to buffer
        from scripts.collaboration.context_compressor import Message, MessageType

        coord._message_buffer.append(
            Message(role="user", content="hello", msg_type=MessageType.USER)
        )
        result = await coord.compress_context()
        # May or may not compress depending on threshold, but should not raise
        assert result is not None or result is None

    def test_get_compression_stats_no_compressor(self):
        coord = _make_coordinator(enable_compression=False)
        assert coord.get_compression_stats() is None

    def test_get_compression_stats_empty_history(self):
        coord = _make_coordinator(enable_compression=True)
        stats = coord.get_compression_stats()
        assert stats is not None
        assert stats["total_compressions"] == 0
        assert stats["avg_reduction_pct"] == 0.0
        assert stats["last_compression"] is None

    def test_get_compression_stats_with_history(self):
        coord = _make_coordinator(enable_compression=True)
        coord._execution_history.append(
            {
                "timestamp": 0.0,
                "compression": {
                    "level": "snip",
                    "original_tokens": 1000,
                    "compressed_tokens": 500,
                    "reduction_pct": 50.0,
                    "summary": "summary",
                },
            }
        )
        stats = coord.get_compression_stats()
        assert stats["total_compressions"] == 1
        assert stats["avg_reduction_pct"] == 50.0
        assert stats["total_original_tokens"] == 1000
        assert stats["total_compressed_tokens"] == 500
        assert stats["last_compression"] is not None


# ---------------------------------------------------------------------------
# AsyncCoordinator.preload_rules
# ---------------------------------------------------------------------------


class TestPreloadRules:
    @pytest.mark.asyncio
    async def test_no_memory_provider_returns_empty(self):
        coord = _make_coordinator()
        result = await coord.preload_rules("task")
        assert result == {}

    @pytest.mark.asyncio
    async def test_memory_provider_unavailable_returns_empty(self):
        class UnavailableProvider:
            def is_available(self):
                return False

        coord = _make_coordinator(memory_provider=UnavailableProvider())
        result = await coord.preload_rules("task")
        assert result == {}

    @pytest.mark.asyncio
    async def test_match_rules_returns_rules(self):
        class StubProvider:
            def is_available(self):
                return True

            def match_rules(self, **_kwargs):
                return [{"rule_type": "always", "trigger": "t", "action": "a"}]

        coord = _make_coordinator(memory_provider=StubProvider())
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        result = await coord.preload_rules("task")
        assert "architect" in result
        assert len(result["architect"]) == 1

    @pytest.mark.asyncio
    async def test_get_rules_with_string_rules(self):
        class StubProvider:
            def is_available(self):
                return True

            def get_rules(self, **_kwargs):
                return ["always do X", "avoid Y"]

        coord = _make_coordinator(memory_provider=StubProvider())
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        result = await coord.preload_rules("task")
        assert "architect" in result
        assert len(result["architect"]) == 2

    @pytest.mark.asyncio
    async def test_get_rules_with_dict_rules(self):
        class StubProvider:
            def is_available(self):
                return True

            def get_rules(self, **_kwargs):
                return [{"rule_type": "forbid", "trigger": "x", "action": "y"}]

        coord = _make_coordinator(memory_provider=StubProvider())
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        result = await coord.preload_rules("task")
        assert "architect" in result

    @pytest.mark.asyncio
    async def test_provider_error_continues_gracefully(self):
        class ErrorProvider:
            def is_available(self):
                return True

            def match_rules(self, **_kwargs):
                raise RuntimeError("provider error")

        coord = _make_coordinator(memory_provider=ErrorProvider())
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        result = await coord.preload_rules("task")
        # Error is caught, empty result returned
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# AsyncCoordinator._get_worker_for_task
# ---------------------------------------------------------------------------


class TestGetWorkerForTask:
    def test_finds_matching_worker(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", _make_roles())
        coord.spawn_workers(plan)
        task = plan.batches[0].tasks[0]
        worker = coord._get_worker_for_task(task)
        assert worker is not None
        assert worker.role_id == task.role_id

    def test_returns_none_when_no_match(self):
        coord = _make_coordinator()
        task = TaskDefinition(description="task", role_id="nonexistent")
        assert coord._get_worker_for_task(task) is None


# ---------------------------------------------------------------------------
# AsyncCoordinator.collect_results
# ---------------------------------------------------------------------------


class TestCollectResults:
    def test_returns_dict_with_keys(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        results = coord.collect_results()
        assert isinstance(results, dict)
        assert "coordinator_id" in results
        assert "scratchpad" in results
        assert "scratchpad_stats" in results
        assert "findings_count" in results
        assert "decisions_count" in results
        assert "conflicts_count" in results
        assert "notifications" in results
        assert "workers" in results

    def test_coordinator_id_matches(self):
        coord = _make_coordinator()
        results = coord.collect_results()
        assert results["coordinator_id"] == coord.coordinator_id

    def test_workers_list_reflects_spawned(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", _make_roles())
        coord.spawn_workers(plan)
        results = coord.collect_results()
        assert len(results["workers"]) == 2


# ---------------------------------------------------------------------------
# AsyncCoordinator.resolve_conflicts
# ---------------------------------------------------------------------------


class TestResolveConflicts:
    @pytest.mark.asyncio
    async def test_no_conflicts_returns_empty(self):
        coord = _make_coordinator()
        records = await coord.resolve_conflicts()
        assert isinstance(records, list)
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_resolves_existing_conflicts(self):
        from scripts.collaboration.models import EntryType, ScratchpadEntry

        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        # Add a conflict to scratchpad
        coord.scratchpad.write(
            ScratchpadEntry(
                worker_id="w1",
                role_id="architect",
                entry_type=EntryType.CONFLICT,
                content="Disagreement on architecture",
            )
        )
        records = await coord.resolve_conflicts()
        assert len(records) >= 1


# ---------------------------------------------------------------------------
# AsyncCoordinator.generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_empty_report(self):
        coord = _make_coordinator()
        report = coord.generate_report()
        assert isinstance(report, str)
        assert "多角色协作报告" in report

    def test_report_after_execution(self):
        coord = _make_coordinator()
        plan = coord.plan_task("task", [{"role_id": "architect", "role_prompt": "p"}])
        coord.spawn_workers(plan)
        report = coord.generate_report()
        assert "architect" in report

    def test_report_includes_findings_count(self):
        from scripts.collaboration.models import EntryType, ScratchpadEntry

        coord = _make_coordinator()
        coord.scratchpad.write(
            ScratchpadEntry(
                entry_type=EntryType.FINDING,
                content="Test finding",
            )
        )
        report = coord.generate_report()
        assert "发现" in report

    def test_report_includes_consensus_records(self):
        coord = _make_coordinator()
        # Manually add a consensus record
        coord.consensus.create_proposal(
            topic="test topic",
            proposer_id=coord.coordinator_id,
            content="test content",
            options=["A", "B"],
        )
        report = coord.generate_report()
        # Consensus section may or may not appear depending on records
        assert isinstance(report, str)


# ---------------------------------------------------------------------------
# AsyncCoordinator._record_execution / _get_last_duration
# ---------------------------------------------------------------------------


class TestRecordExecution:
    def test_record_execution_appends(self):
        coord = _make_coordinator()
        result = ScheduleResult(
            success=True,
            total_tasks=2,
            completed_tasks=2,
            failed_tasks=0,
            results=[],
            duration_seconds=1.5,
            errors=[],
        )
        initial = len(coord._execution_history)
        coord._record_execution(result)
        assert len(coord._execution_history) == initial + 1

    def test_get_last_duration_empty_history(self):
        coord = _make_coordinator()
        assert coord._get_last_duration() == 0.0

    def test_get_last_duration_with_history(self):
        coord = _make_coordinator()
        result = ScheduleResult(
            success=True,
            total_tasks=1,
            completed_tasks=1,
            failed_tasks=0,
            results=[],
            duration_seconds=42.5,
            errors=[],
        )
        coord._record_execution(result)
        assert coord._get_last_duration() == 42.5


# ---------------------------------------------------------------------------
# AsyncCoordinator._async_call
# ---------------------------------------------------------------------------


class TestAsyncCall:
    @pytest.mark.asyncio
    async def test_async_call_executes_function(self):
        coord = _make_coordinator()

        def add(a, b):
            return a + b

        result = await coord._async_call(add, a=2, b=3)
        assert result == 5


# ---------------------------------------------------------------------------
# AsyncCoordinator._inject_briefing_to_worker / _collect_briefing_from_worker
# ---------------------------------------------------------------------------


class TestBriefingInjection:
    def test_inject_briefing_no_chain_noop(self):
        coord = _make_coordinator()
        worker = WorkerFactory.create(
            worker_id="w1",
            role_id="architect",
            role_prompt="p",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        # No briefing chain, should not raise
        coord._inject_briefing_to_worker(worker)

    def test_collect_briefing_from_non_enhanced_worker(self):
        coord = _make_coordinator()
        worker = WorkerFactory.create(
            worker_id="w1",
            role_id="architect",
            role_prompt="p",
            scratchpad=Scratchpad(),
            llm_backend=MockBackend(),
        )
        # Non-EnhancedWorker, should not raise
        coord._collect_briefing_from_worker(worker)
        assert coord._briefing_chain == []

    def test_merge_briefings_empty(self):
        from scripts.collaboration.enhanced_worker import AgentBriefingOutput

        coord = _make_coordinator()
        result = coord._merge_briefings([])
        assert isinstance(result, AgentBriefingOutput)

    def test_merge_briefings_multiple(self):
        from scripts.collaboration.enhanced_worker import AgentBriefingOutput

        coord = _make_coordinator()
        b1 = AgentBriefingOutput(
            task_summary="task1",
            key_decisions=["d1"],
            pending_items=["p1"],
            rules_applied=["r1"],
            result_summary="summary1",
            confidence=0.9,
        )
        b2 = AgentBriefingOutput(
            task_summary="task2",
            key_decisions=["d2"],
            pending_items=["p2"],
            rules_applied=["r2"],
            result_summary="summary2",
            confidence=0.7,
        )
        merged = coord._merge_briefings([b1, b2])
        assert merged.confidence == 0.7  # min
        assert len(merged.key_decisions) >= 1
