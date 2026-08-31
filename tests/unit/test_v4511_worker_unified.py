#!/usr/bin/env python3
"""V4.5.11 Worker.execute path tests — exercise the unified _do_work_async
without breaking the V4.5.9 aexecute contract (covered in
tests/unit/test_v459_worker_async.py).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from scripts.collaboration.async_llm_backend import (
    AsyncLLMBackendInterface,
)
from scripts.collaboration.llm_backend import MockBackend
from scripts.collaboration.models import (
    EntryType,
    ScratchpadEntry,
    TaskDefinition,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker


class _CounterAsyncBackend(AsyncLLMBackendInterface):
    """Async backend that records the number of generate() invocations."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.calls += 1
        return f"async#{self.calls}: {prompt}"

    async def is_available(self) -> bool:
        return True

    async def batch_generate(self, prompts: list[str], **kwargs: Any) -> list[str]:
        return [f"batch:{p}" for p in prompts]


def _task(task_id: str = "T-4511") -> TaskDefinition:
    return TaskDefinition(
        task_id=task_id,
        role_id="architect",
        # Unique description per call so the global cache doesn't pollute
        # results between tests (cached responses instead of live calls).
        description=f"V4.5.11 unified-path probe {uuid.uuid4().hex[:8]}",
    )


def _worker(backend: Any) -> Worker:
    sp = Scratchpad()
    sp.write(
        ScratchpadEntry(
            worker_id="w-4511",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="seed finding",
            confidence=0.5,
            tags=[_task().task_id],
        )
    )
    return Worker(
        worker_id="w-4511",
        role_id="architect",
        role_prompt="You are an architect.",
        scratchpad=sp,
        llm_backend=backend,
    )


def test_execute_with_sync_backend_runs_through_asyncio_run() -> None:
    worker = _worker(MockBackend())
    result = worker.execute(_task())
    assert result.success is True
    # MockBackend always returns the role-titled [MOCK MODE] block.
    assert "[MOCK MODE]" in result.output["finding_summary"]


def test_execute_with_async_backend_runs_through_asyncio_run() -> None:
    backend = _CounterAsyncBackend()
    worker = _worker(backend=backend)
    result = worker.execute(_task())
    assert result.success is True
    assert backend.calls == 1  # sync wrapper ran one async generate()


def test_execute_with_failing_async_backend_returns_failure() -> None:
    class _Boom(AsyncLLMBackendInterface):
        async def generate(self, prompt: str, **kwargs: Any) -> str:
            raise RuntimeError("kaboom")

        async def is_available(self) -> bool:
            return True

        async def batch_generate(self, prompts: list[str], **kwargs: Any) -> list[str]:
            return ["x" for _ in prompts]

    worker = _worker(_Boom())
    result = worker.execute(_task())
    assert result.success is False
    assert "kaboom" in (result.error or "")


def test_execute_returns_worker_result_consistent_with_aexecute() -> None:
    """R4 anti-drift smoke check: both paths produce the same shape."""
    sync_worker = _worker(MockBackend())
    async_worker = _worker(MockBackend())
    task = _task()
    sync_result = sync_worker.execute(task)
    async_result = asyncio.run(async_worker.aexecute(task))
    assert sync_result.output == async_result.output
    assert sync_result.success == async_result.success
