#!/usr/bin/env python3
"""V4.5.9 — Worker.aexecute unit tests (AC-W1/W2/W3/W6, PRD §4 test matrix).

Covers:
- path matrix: async backend -> native await (NO run_in_executor);
  sync/None backend -> run_in_executor bridge (AC-C6)
- execute/aexecute behavior consistency (same fields except duration)
- failure semantics: aexecute returns WorkerResult(success=False), never raises
- stream path via generate_stream
- shared finalize/failure helpers (single implementation, AC-W1)
- anti-ghost counter unaffected by direct aexecute
"""

import asyncio
import inspect
import uuid
from typing import Any

import pytest

from scripts.collaboration.async_llm_backend import (
    AsyncLLMBackendInterface,
    AsyncMockBackend,
)
from scripts.collaboration.gather_core import get_call_counter_gather
from scripts.collaboration.llm_backend import MockBackend
from scripts.collaboration.models import TaskDefinition, WorkerResult
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker, WorkerFactory


class ExplodingAsyncBackend(AsyncLLMBackendInterface):
    """Async backend that always raises on generate."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("async boom")

    async def is_available(self) -> bool:
        return True

    async def batch_generate(self, prompts: list[str], **kwargs: Any) -> list[str]:
        raise RuntimeError("async boom")


class StreamingAsyncBackend(AsyncMockBackend):
    """Async backend with deterministic chunked streaming."""

    async def generate_stream(self, prompt: str, **kwargs: Any):
        for chunk in ["chunk-1|", "chunk-2|", "chunk-3"]:
            yield chunk


class ExplodingSyncBackend(MockBackend):
    """Sync backend that always raises on generate."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("sync boom")


def _task() -> TaskDefinition:
    # Unique description per call: the global LLM cache is keyed by the
    # assembled instruction text, so identical descriptions would cross-
    # pollute results between tests (cached responses instead of live calls).
    uid = uuid.uuid4().hex[:8]
    return TaskDefinition(
        task_id="task-fixed",
        description=f"Design auth system {uid}",
        role_id="architect",
        role_prompt="You are an architect.",
    )


def _make_worker(backend: Any = None, stream: bool = False) -> Worker:
    return WorkerFactory.create(
        worker_id="arch-x1",
        role_id="architect",
        role_prompt="You are an architect.",
        scratchpad=Scratchpad(),
        llm_backend=backend,
        stream=stream,
    )


@pytest.fixture
async def executor_calls(monkeypatch):
    """Spy on the running loop's run_in_executor; returns recorded callables.

    Async fixture so it runs inside the per-test event loop.
    """
    loop = asyncio.get_running_loop()
    calls: list[Any] = []
    orig = loop.run_in_executor

    def _spy(executor: Any, func: Any, *args: Any) -> Any:
        calls.append(func)
        return orig(executor, func, *args)

    monkeypatch.setattr(loop, "run_in_executor", _spy)
    return calls


class TestAexecutePathMatrix:
    @pytest.mark.asyncio
    async def test_worker_has_aexecute(self):
        worker = _make_worker()
        assert callable(worker.aexecute)
        assert inspect.iscoroutinefunction(worker.aexecute)

    @pytest.mark.asyncio
    async def test_aexecute_async_backend_bypasses_executor(self, executor_calls):
        """AC-W2: async backend -> native await, zero run_in_executor calls."""
        worker = _make_worker(AsyncMockBackend())
        result = await worker.aexecute(_task())
        assert executor_calls == []
        assert isinstance(result, WorkerResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_aexecute_sync_backend_uses_executor(self, executor_calls):
        """AC-W3/AC-C6: sync backend bridges through the default executor."""
        worker = _make_worker(MockBackend())
        result = await worker.aexecute(_task())
        assert len(executor_calls) == 1
        assert executor_calls[0] == worker.execute
        assert result.success is True

    @pytest.mark.asyncio
    async def test_aexecute_none_backend_uses_executor(self, executor_calls):
        worker = _make_worker(None)
        result = await worker.aexecute(_task())
        assert len(executor_calls) == 1
        assert result.success is True

    @pytest.mark.asyncio
    async def test_aexecute_async_backend_output_fields(self):
        worker = _make_worker(AsyncMockBackend())
        result = await worker.aexecute(_task())
        assert result.worker_id == "arch-x1"
        assert result.task_id == "task-fixed"
        assert isinstance(result.output, dict)
        assert result.output["finding_summary"]
        assert result.output["role_id"] == "architect"
        assert result.output["agent_id"]


class TestAexecuteBehaviorConsistency:
    @pytest.mark.asyncio
    async def test_execute_and_aexecute_consistent_mock_backend(self):
        """R4 anti-drift: identical WorkerResult fields (except duration)."""
        worker_sync = _make_worker(MockBackend())
        worker_async = _make_worker(MockBackend())
        task = _task()

        r1 = worker_sync.execute(task)
        r2 = await worker_async.aexecute(task)

        assert r1.success == r2.success
        assert r1.worker_id == r2.worker_id
        assert r1.task_id == r2.task_id
        assert r1.error == r2.error
        assert r1.scratchpad_entries_written == r2.scratchpad_entries_written
        assert r1.notifications_sent == r2.notifications_sent
        assert r1.output == r2.output

    @pytest.mark.asyncio
    async def test_aexecute_writes_scratchpad(self):
        worker = _make_worker(AsyncMockBackend())
        await worker.aexecute(_task())
        entries = worker.scratchpad.read()
        assert len(entries) > 0
        assert any(e.content for e in entries)

    @pytest.mark.asyncio
    async def test_aexecute_shares_finalize_helper(self, monkeypatch):
        """AC-W1: aexecute routes success results through _finalize_finding."""
        worker = _make_worker(AsyncMockBackend())
        orig = Worker._finalize_finding
        calls: list[Any] = []

        # Worker uses __slots__ — patch at class level, not instance level.
        def _spy(self: Worker, task: TaskDefinition, finding: str, start_time: float) -> WorkerResult:
            calls.append(finding)
            return orig(self, task, finding, start_time)

        monkeypatch.setattr(Worker, "_finalize_finding", _spy)
        await worker.aexecute(_task())
        assert len(calls) == 1


class TestAexecuteFailureSemantics:
    @pytest.mark.asyncio
    async def test_aexecute_async_backend_failure_returns_result(self):
        """AC-W6: backend exception -> WorkerResult(success=False), never raises."""
        worker = _make_worker(ExplodingAsyncBackend())
        result = await worker.aexecute(_task())
        assert isinstance(result, WorkerResult)
        assert result.success is False
        assert "async boom" in (result.error or "")

    @pytest.mark.asyncio
    async def test_aexecute_sync_backend_failure_returns_result(self):
        worker = _make_worker(ExplodingSyncBackend())
        result = await worker.aexecute(_task())
        assert isinstance(result, WorkerResult)
        assert result.success is False
        assert "sync boom" in (result.error or "")

    @pytest.mark.asyncio
    async def test_aexecute_failure_output_fields(self):
        worker = _make_worker(ExplodingAsyncBackend())
        result = await worker.aexecute(_task())
        assert isinstance(result.output, dict)
        assert result.output["error_detail"] == "Execution failed"
        assert result.duration_seconds >= 0


class TestAexecuteStreamPath:
    @pytest.mark.asyncio
    async def test_aexecute_stream_joins_chunks(self):
        worker = _make_worker(StreamingAsyncBackend(), stream=True)
        result = await worker.aexecute(_task())
        assert result.success is True
        assert result.output["finding_summary"] == "chunk-1|chunk-2|chunk-3"

    @pytest.mark.asyncio
    async def test_aexecute_non_stream_ignores_generate_stream(self):
        worker = _make_worker(StreamingAsyncBackend(), stream=False)
        result = await worker.aexecute(_task())
        assert result.success is True
        assert "chunk-1" not in result.output["finding_summary"]


class TestAexecuteCounter:
    @pytest.mark.asyncio
    async def test_aexecute_does_not_bump_gather_counter(self):
        """gather_core counter only bumps via execute_batch_gather, not aexecute."""
        before = get_call_counter_gather()
        worker = _make_worker(AsyncMockBackend())
        await worker.aexecute(_task())
        assert get_call_counter_gather() == before
