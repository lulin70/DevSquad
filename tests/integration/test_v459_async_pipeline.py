#!/usr/bin/env python3
"""V4.5.9 integration tests — true-async pipeline (AC-W5, AC-C4, AC-V4).

Covers:
- AsyncCoordinator + AsyncWorkerWrapper + AsyncMockBackend full chain in a
  single event loop with no thread growth (threading.active_count assertion)
- AsyncOpenAIBackend with httpx.MockTransport injected client (no network)
- 50-concurrency stress: no result loss, peak concurrency <= cap
- Coordinator sync bridge end-to-end + running-loop raise + empty batch
"""

import asyncio
import threading
import time
from typing import Any

import httpx
import pytest

from scripts.collaboration.async_coordinator import AsyncCoordinator
from scripts.collaboration.async_llm_backend import (
    AsyncLLMBackendInterface,
    AsyncMockBackend,
    AsyncOpenAIBackend,
)
from scripts.collaboration.gather_core import get_call_counter_gather
from scripts.collaboration.llm_backend import MockBackend
from scripts.collaboration.models import BatchMode, TaskBatch, TaskDefinition
from scripts.collaboration.scratchpad import Scratchpad


class CountingAsyncBackend(AsyncLLMBackendInterface):
    """Async backend tracking in-flight calls to assert semaphore caps."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.completed = 0

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.002)
            self.completed += 1
            return f"resp-{self.completed}"
        finally:
            self.active -= 1

    async def is_available(self) -> bool:
        return True

    async def batch_generate(self, prompts: list[str], **kwargs: Any) -> list[str]:
        return [await self.generate(p, **kwargs) for p in prompts]


def _openai_backend_with_mock_transport() -> AsyncOpenAIBackend:
    """AsyncOpenAIBackend with a mock httpx transport injected into _client."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-mock",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "mock-llm analysis"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    backend = AsyncOpenAIBackend(api_key="test-key", model="gpt-mock")
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    from openai import AsyncOpenAI

    backend._client = AsyncOpenAI(api_key="test-key", http_client=http_client)
    return backend


class TestTrueAsyncPipeline:
    def test_full_async_pipeline_no_thread_growth(self):
        """AC-W5: whole chain completes in a single event loop, no thread leak."""

        async def run_pipeline():
            coord = AsyncCoordinator(
                scratchpad=Scratchpad(),
                enable_compression=False,
                llm_backend=AsyncMockBackend(),
            )
            plan = coord.plan_task(
                "design system",
                [
                    {"role_id": "architect", "role_prompt": "p"},
                    {"role_id": "tester", "role_prompt": "p"},
                ],
            )
            coord.spawn_workers(plan)
            return await coord.execute_plan(plan)

        before = threading.active_count()
        result = asyncio.run(run_pipeline())
        time.sleep(0.05)  # allow default-executor teardown if any
        after = threading.active_count()
        assert result.completed_tasks == 2
        assert result.failed_tasks == 0
        assert after <= before, f"Thread leak: {before} -> {after}"

    def test_async_pipeline_with_sync_mock_bridge(self):
        """AC-C6: sync backend still completes through the executor bridge."""

        async def run_pipeline():
            coord = AsyncCoordinator(
                scratchpad=Scratchpad(),
                enable_compression=False,
                llm_backend=MockBackend(),
            )
            plan = coord.plan_task(
                "design system",
                [
                    {"role_id": "architect", "role_prompt": "p"},
                    {"role_id": "tester", "role_prompt": "p"},
                ],
            )
            coord.spawn_workers(plan)
            return await coord.execute_plan(plan)

        result = asyncio.run(run_pipeline())
        assert result.completed_tasks == 2
        assert all(r.success for r in result.results)

    def test_async_openai_backend_mock_transport_end_to_end(self):
        """AsyncOpenAIBackend (httpx.MockTransport) drives Worker.aexecute natively."""
        from scripts.collaboration.worker import WorkerFactory

        backend = _openai_backend_with_mock_transport()
        worker = WorkerFactory.create(
            worker_id="arch-mock",
            role_id="architect",
            role_prompt="p",
            scratchpad=Scratchpad(),
            llm_backend=backend,
        )
        task = TaskDefinition(description="analyze auth", role_id="architect")

        async def drive():
            return await worker.aexecute(task)

        result = asyncio.run(drive())
        assert result.success is True
        assert "mock-llm analysis" in result.output["finding_summary"]

    def test_async_openai_backend_via_async_coordinator(self):
        backend = _openai_backend_with_mock_transport()

        async def run_pipeline():
            coord = AsyncCoordinator(
                scratchpad=Scratchpad(),
                enable_compression=False,
                llm_backend=backend,
            )
            plan = coord.plan_task(
                "design system",
                [{"role_id": "architect", "role_prompt": "p"}],
            )
            coord.spawn_workers(plan)
            return await coord.execute_plan(plan)

        result = asyncio.run(run_pipeline())
        assert result.completed_tasks == 1
        assert "mock-llm analysis" in result.results[0].output["finding_summary"]


class TestConcurrencyStress:
    def test_fifty_concurrent_async_no_loss_and_capped(self):
        """AC-V4: 50 tasks, no result loss, peak concurrency <= max_concurrency."""
        import uuid

        backend = CountingAsyncBackend()

        async def run_pipeline():
            coord = AsyncCoordinator(
                scratchpad=Scratchpad(),
                enable_compression=False,
                llm_backend=backend,
                max_concurrency=10,
            )
            roles = [{"role_id": f"role-{i}", "role_prompt": "p"} for i in range(50)]
            plan = coord.plan_task("stress task", roles)
            # Unique per-task descriptions: the global LLM cache is keyed by
            # the assembled instruction, so identical descriptions would let
            # cache hits bypass the backend (defeating the peak measurement).
            uid = uuid.uuid4().hex[:8]
            for batch in plan.batches:
                for i, t in enumerate(batch.tasks):
                    t.description = f"stress task {uid}-{i}"
            coord.spawn_workers(plan)
            return await coord.execute_plan(plan)

        result = asyncio.run(run_pipeline())
        assert result.completed_tasks == 50
        assert result.failed_tasks == 0
        assert len({r.task_id for r in result.results}) == 50
        assert backend.completed == 50
        assert backend.peak <= 10

    def test_fifty_concurrent_sync_mock_bridge_no_loss(self):
        async def run_pipeline():
            coord = AsyncCoordinator(
                scratchpad=Scratchpad(),
                enable_compression=False,
                llm_backend=MockBackend(),
                max_concurrency=10,
            )
            roles = [{"role_id": f"role-{i}", "role_prompt": "p"} for i in range(50)]
            plan = coord.plan_task("stress task", roles)
            coord.spawn_workers(plan)
            return await coord.execute_plan(plan)

        result = asyncio.run(run_pipeline())
        assert result.completed_tasks == 50
        assert result.failed_tasks == 0


class TestCoordinatorSyncBridge:
    def test_sync_bridge_end_to_end_and_executor_tag(self):
        """AC-C1: Coordinator parallel batch runs through the shared gather core."""
        from scripts.collaboration.coordinator import Coordinator

        coord = Coordinator(
            scratchpad=Scratchpad(), enable_compression=False, llm_backend=MockBackend()
        )
        plan = coord.plan_task(
            "design auth",
            [
                {"role_id": "architect", "role_prompt": "p"},
                {"role_id": "tester", "role_prompt": "p"},
            ],
        )
        coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        assert result.completed_tasks == 2
        assert all(r.success for r in result.results)
        # V4.5.9 (DESIGN §6): gather-executor evidence on WorkerResult output.
        assert all(r.output.get("executor") == "gather" for r in result.results)

        before = get_call_counter_gather()
        coord.execute_plan(plan)
        assert get_call_counter_gather() > before

    def test_sync_bridge_raises_inside_running_loop(self):
        """AC-C4: informative raise (message mentions async_dispatch)."""
        from scripts.collaboration.coordinator import Coordinator

        coord = Coordinator(scratchpad=Scratchpad(), enable_compression=False)
        batch = TaskBatch(
            mode=BatchMode.PARALLEL,
            tasks=[TaskDefinition(description="t", role_id="architect")],
            max_concurrency=1,
        )

        async def inner():
            with pytest.raises(RuntimeError, match="async_dispatch"):
                coord._execute_parallel(batch)

        asyncio.run(inner())

    def test_sync_bridge_empty_batch_returns_empty(self):
        from scripts.collaboration.coordinator import Coordinator

        coord = Coordinator(scratchpad=Scratchpad(), enable_compression=False)
        batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[], max_concurrency=1)
        assert coord._execute_parallel(batch) == []
