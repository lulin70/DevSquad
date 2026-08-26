"""Integration tests for async coeffect pipeline (V4.5.7 P12.5.1).

Coverage (10 cases) — coordination with asyncio.gather and coexistence
with V4.5.4 sync CoeffectResolver (design §4.2: dispatcher is NOT
modified in V4.5.7; async resolver must cooperate with the existing
parallel-dispatch style).
"""

from __future__ import annotations

import asyncio
import time

import pytest

from scripts.collaboration.async_coeffect_resolver import (
    AsyncCoeffectResolver,
    CoeffectRequest,
    CoeffectState,
    get_call_counter_er,
)
from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider

pytestmark = pytest.mark.integration


def _req(name: str, executor, timeout: float = 5.0) -> CoeffectRequest:
    return CoeffectRequest(name=name, payload={"executor": executor}, timeout=timeout)


class TestGatherCoordination:
    async def test_gather_all_complete(self):
        r = AsyncCoeffectResolver()
        results = await asyncio.gather(
            *[r.aresolve(_req(f"m{i}", lambda i=i: i + 100)) for i in range(5)]
        )
        assert sorted(res.value for res in results) == [100, 101, 102, 103, 104]

    async def test_gather_mixed_success_and_failure(self):
        # aresolve never raises — failures are captured as FAILED results,
        # mirroring AsyncCoordinator's return_exceptions=True invariant.
        def boom():
            raise RuntimeError("planned failure")

        r = AsyncCoeffectResolver()
        results = await asyncio.gather(
            r.aresolve(_req("ok-1", lambda: "a")),
            r.aresolve(_req("fails", boom)),
            r.aresolve(_req("ok-2", lambda: "b")),
        )
        assert results[0].state == CoeffectState.COMPLETED
        assert results[1].state == CoeffectState.FAILED
        assert "planned failure" in results[1].error
        assert results[2].state == CoeffectState.COMPLETED

    async def test_timeout_isolation(self):
        # One slow coeffect times out; siblings still complete.
        r = AsyncCoeffectResolver(max_concurrent=3)
        results = await asyncio.gather(
            r.aresolve(_req("slow", lambda: time.sleep(0.5), timeout=0.05)),
            r.aresolve(_req("fast-1", lambda: 1)),
            r.aresolve(_req("fast-2", lambda: 2)),
        )
        assert results[0].state == CoeffectState.FAILED
        assert results[1].state == CoeffectState.COMPLETED
        assert results[2].state == CoeffectState.COMPLETED

    async def test_gather_zero_coeffects(self):
        # Gathering an empty fan-out returns [] without touching the resolver.
        results = await asyncio.gather(*[])
        assert results == []


class TestPipelinePatterns:
    async def test_chained_sequential_dependencies(self):
        # a → b → c: b only runs after a completes (result chaining).
        r = AsyncCoeffectResolver()
        step_a = await r.aresolve(_req("a", lambda: 10))
        step_b = await r.aresolve(_req("b", lambda: step_a.value + 5))
        step_c = await r.aresolve(_req("c", lambda: step_b.value * 2))
        assert step_a.value == 10
        assert step_b.value == 15
        assert step_c.value == 30

    async def test_dispatcher_style_parallel_workers(self):
        # Simulates MultiAgentDispatcher parallel workers (ThreadPoolExecutor
        # style fan-out) where each worker's setup is a coeffect.
        r = AsyncCoeffectResolver(max_concurrent=7)
        roles = ["architect", "security", "tester", "coder", "devops", "ui", "pm"]

        def setup(role_name):
            return f"ready:{role_name}"

        results = await asyncio.gather(
            *[r.aresolve(_req(f"setup-{role}", lambda rl=role: setup(rl)))
              for role in roles]
        )
        assert {res.value for res in results} == {f"ready:{role}" for role in roles}
        assert all(res.state == CoeffectState.COMPLETED for res in results)

    async def test_shared_resolver_reentry(self):
        # Same resolver instance used by many concurrent callers — per-call
        # FSM must stay independent (V4.5.7 refactor).
        r = AsyncCoeffectResolver(max_concurrent=4)
        tasks = [r.aresolve(_req(f"re-{i}", lambda i=i: i)) for i in range(8)]
        results = await asyncio.gather(*tasks)
        assert all(res.state == CoeffectState.COMPLETED for res in results)
        assert sorted(res.value for res in results) == list(range(8))

    async def test_call_counter_bumped_across_pipeline(self):
        before = get_call_counter_er()
        r = AsyncCoeffectResolver()
        await asyncio.gather(
            *[r.aresolve(_req(f"cnt-{i}", lambda i=i: i)) for i in range(4)]
        )
        assert get_call_counter_er() >= before + 5  # init + 4 aresolve


class TestSyncAsyncCoexistence:
    async def test_v454_sync_resolver_coexists(self):
        # V4.5.4 sync CoeffectResolver (topological sort) and V4.5.7
        # AsyncCoeffectResolver (execution concurrency) serve different
        # concerns and must work side by side in one process.
        sync_resolver = CoeffectResolver()
        sync_resolver.register(_StaticProvider("effect_registry", ()))
        sync_resolver.register(_StaticProvider("artifact_store", ("effect_registry",)))
        order = sync_resolver.resolve_activation_order()
        assert order == ["effect_registry", "artifact_store"]

        async_resolver = AsyncCoeffectResolver()
        result = await async_resolver.aresolve(_req("post-sort", lambda: order))
        assert result.state == CoeffectState.COMPLETED
        assert result.value == ["effect_registry", "artifact_store"]

    async def test_topological_order_then_parallel_execution(self):
        # Full pattern: resolve activation order (sync Kahn), then execute
        # each module's coeffect in parallel (async gather).
        sync_resolver = CoeffectResolver()
        deps = {
            "effect_registry": (),
            "artifact_store": ("effect_registry",),
            "audit_logger": ("effect_registry",),
            "risk_register": (),
        }
        for module_id, module_deps in deps.items():
            sync_resolver.register(_StaticProvider(module_id, module_deps))
        order = sync_resolver.resolve_activation_order()
        assert len(order) == 4

        async_resolver = AsyncCoeffectResolver(max_concurrent=4)
        results = await asyncio.gather(
            *[async_resolver.aresolve(
                _req(f"activate-{m}", lambda m=m: f"activated:{m}")
            ) for m in order]
        )
        assert all(res.state == CoeffectState.COMPLETED for res in results)
        assert {res.value for res in results} == {f"activated:{m}" for m in order}
