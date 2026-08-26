"""Unit tests for async_coeffect_resolver (V4.5.7 P12.5.1).

Coverage (25 cases):
- 6-state FSM: allowed transitions + terminal states + rejected transitions
- aresolve: happy path / value passthrough / timeout / executor error /
  missing executor / non-callable executor / cancellation
- asyncio.Semaphore concurrency cap
- uniform lock ordering (no deadlock under contention)
- sync bridge resolve(): no-loop path + running-loop rejection (L-V457-003)
- diagnostics: state / stats properties
- anti-ghost counter monotonicity
"""

from __future__ import annotations

import asyncio
import time

import pytest

from scripts.collaboration.async_coeffect_resolver import (
    ALLOWED_TRANSITIONS,
    AsyncCoeffectResolver,
    CoeffectRequest,
    CoeffectResult,
    CoeffectState,
    _can_transition,
    get_call_counter_er,
)


def _req(
    name: str = "test",
    executor: object = lambda: 42,  # noqa: E731 — test default
    timeout: float = 5.0,
) -> CoeffectRequest:
    return CoeffectRequest(
        name=name, payload={"executor": executor}, timeout=timeout
    )


# ── 1. FSM transition table ─────────────────────────────────────────────────


class TestFsmTransitions:
    def test_pending_to_ready_allowed(self):
        assert _can_transition(CoeffectState.PENDING, CoeffectState.READY)

    def test_ready_to_running_allowed(self):
        assert _can_transition(CoeffectState.READY, CoeffectState.RUNNING)

    def test_running_terminal_transitions_allowed(self):
        assert _can_transition(CoeffectState.RUNNING, CoeffectState.COMPLETED)
        assert _can_transition(CoeffectState.RUNNING, CoeffectState.FAILED)
        assert _can_transition(CoeffectState.RUNNING, CoeffectState.CANCELLED)

    def test_pending_to_cancelled_allowed(self):
        assert _can_transition(CoeffectState.PENDING, CoeffectState.CANCELLED)

    def test_terminal_states_have_no_outgoing(self):
        for terminal in (CoeffectState.COMPLETED, CoeffectState.FAILED, CoeffectState.CANCELLED):
            assert ALLOWED_TRANSITIONS[terminal] == frozenset()

    def test_invalid_transition_rejected(self):
        assert not _can_transition(CoeffectState.PENDING, CoeffectState.COMPLETED)
        assert not _can_transition(CoeffectState.PENDING, CoeffectState.RUNNING)
        assert not _can_transition(CoeffectState.READY, CoeffectState.COMPLETED)
        assert not _can_transition(CoeffectState.COMPLETED, CoeffectState.READY)

    def test_six_states_exist(self):
        assert {s.value for s in CoeffectState} == {
            "pending", "ready", "running", "completed", "failed", "cancelled",
        }


# ── 2. aresolve execution paths ─────────────────────────────────────────────


class TestAResolve:
    async def test_happy_path_completes(self):
        r = AsyncCoeffectResolver()
        result = await r.aresolve(_req())
        assert isinstance(result, CoeffectResult)
        assert result.state == CoeffectState.COMPLETED

    async def test_value_passthrough(self):
        r = AsyncCoeffectResolver()
        result = await r.aresolve(_req(executor=lambda: "hello-world"))
        assert result.value == "hello-world"
        assert result.error is None

    async def test_timeout_fails(self):
        r = AsyncCoeffectResolver()
        result = await r.aresolve(
            _req(executor=lambda: time.sleep(0.3), timeout=0.05)
        )
        assert result.state == CoeffectState.FAILED
        assert "timeout" in (result.error or "")

    async def test_executor_raises_fails(self):
        def boom():
            raise ValueError("boom")

        r = AsyncCoeffectResolver()
        result = await r.aresolve(_req(name="exploder", executor=boom))
        assert result.state == CoeffectState.FAILED
        assert "exploder" in (result.error or "")
        assert "boom" in (result.error or "")

    async def test_missing_executor_fails(self):
        r = AsyncCoeffectResolver()
        result = await r.aresolve(CoeffectRequest(name="noexec", payload={}))
        assert result.state == CoeffectState.FAILED
        assert "executor" in (result.error or "")

    async def test_non_callable_executor_fails(self):
        r = AsyncCoeffectResolver()
        result = await r.aresolve(
            CoeffectRequest(name="badexec", payload={"executor": 42})
        )
        assert result.state == CoeffectState.FAILED
        assert "callable" in (result.error or "")

    async def test_cancellation_via_task_cancel(self):
        r = AsyncCoeffectResolver()
        task = asyncio.ensure_future(
            r.aresolve(_req(executor=lambda: time.sleep(1.0)))
        )
        await asyncio.sleep(0.05)
        task.cancel()
        result = await task
        assert result.state == CoeffectState.CANCELLED
        assert "cancelled" in (result.error or "")


# ── 3. Concurrency control ──────────────────────────────────────────────────


class TestConcurrency:
    async def test_semaphore_caps_concurrency(self):
        max_concurrent = 2
        r = AsyncCoeffectResolver(max_concurrent=max_concurrent)
        active = 0
        peak = 0

        def tracked_executor():
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            time.sleep(0.05)
            active -= 1
            return peak

        results = await asyncio.gather(
            *[r.aresolve(_req(name=f"m{i}", executor=tracked_executor))
              for i in range(6)]
        )
        assert all(res.state == CoeffectState.COMPLETED for res in results)
        assert peak <= max_concurrent

    async def test_gather_many_all_complete(self):
        r = AsyncCoeffectResolver(max_concurrent=4)
        results = await asyncio.gather(
            *[r.aresolve(_req(name=f"n{i}", executor=lambda i=i: i * 2))
              for i in range(10)]
        )
        assert all(res.state == CoeffectState.COMPLETED for res in results)
        assert sorted(res.value for res in results) == [i * 2 for i in range(10)]

    async def test_no_deadlock_under_lock_contention(self):
        # Uniform lock order (sem → lock, L-V457-004): concurrent runs must
        # finish well within the generous 3s bound instead of deadlocking.
        r = AsyncCoeffectResolver(max_concurrent=3)
        results = await asyncio.wait_for(
            asyncio.gather(
                *[r.aresolve(_req(name=f"c{i}", executor=lambda i=i: i))
                  for i in range(12)]
            ),
            timeout=3.0,
        )
        assert len(results) == 12
        assert all(res.state == CoeffectState.COMPLETED for res in results)

    async def test_reentry_per_call_fsm(self):
        # Instance state is diagnostics-only; concurrent re-entry must not
        # raise "Invalid FSM transition" (V4.5.7 refactor invariant).
        r = AsyncCoeffectResolver(max_concurrent=4)
        mix = [
            r.aresolve(_req(name="ok", executor=lambda: 1)),
            r.aresolve(_req(name="slow", executor=lambda: time.sleep(0.1))),
            r.aresolve(_req(name="fails", executor=lambda: 1 / 0)),
        ]
        results = await asyncio.gather(*mix)
        states = {res.state for res in results}
        assert CoeffectState.COMPLETED in states
        assert CoeffectState.FAILED in states


# ── 4. Sync bridge (L-V457-003) ─────────────────────────────────────────────


class TestSyncBridge:
    def test_resolve_without_running_loop(self):
        r = AsyncCoeffectResolver()
        result = r.resolve(_req(name="sync", executor=lambda: "from-sync"))
        assert result.state == CoeffectState.COMPLETED
        assert result.value == "from-sync"

    async def test_resolve_inside_running_loop_raises_informative(self):
        r = AsyncCoeffectResolver()
        with pytest.raises(RuntimeError, match="aresolve"):
            r.resolve(_req())

    def test_resolve_failure_path(self):
        def kaboom():
            raise KeyError("missing")

        r = AsyncCoeffectResolver()
        result = r.resolve(_req(name="kaboom", executor=kaboom))
        assert result.state == CoeffectState.FAILED
        assert "kaboom" in (result.error or "")


# ── 5. Diagnostics + anti-ghost ─────────────────────────────────────────────


class TestDiagnostics:
    async def test_state_property_after_completion(self):
        r = AsyncCoeffectResolver()
        await r.aresolve(_req())
        assert r.state == CoeffectState.COMPLETED

    async def test_state_property_after_failure(self):
        r = AsyncCoeffectResolver()
        await r.aresolve(_req(executor=lambda: 1 / 0))
        assert r.state == CoeffectState.FAILED

    async def test_stats_property(self):
        r = AsyncCoeffectResolver(max_concurrent=3)
        await r.aresolve(_req())
        stats = r.stats
        assert stats["current_state"] == CoeffectState.COMPLETED.value
        assert stats["max_concurrent"] == 3
        assert stats["call_counter_er"] >= 1

    def test_call_counter_monotonic(self):
        before = get_call_counter_er()
        r = AsyncCoeffectResolver()
        r.resolve(_req(name="first"))
        r.resolve(_req(name="second"))
        assert get_call_counter_er() >= before + 3  # init + resolve + resolve

    def test_request_dataclass_defaults(self):
        req = CoeffectRequest(name="d", payload={"executor": lambda: None})
        assert req.timeout == 5.0

    def test_result_dataclass_defaults(self):
        res = CoeffectResult(state=CoeffectState.PENDING)
        assert res.value is None
        assert res.error is None
