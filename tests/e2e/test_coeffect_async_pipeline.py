"""E2E tests — async coeffect pipeline real-user simulation (V4.5.7 P5).

Simulates a realistic user workflow: a solo-coder dispatches a task, the
dispatcher fans out role setup as parallel coeffects, tolerates a failing
role, enforces timeouts on hung coeffects, and bridges from a sync script
context — exactly how the feature is consumed in production.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from scripts.collaboration.async_coeffect_resolver import (
    AsyncCoeffectResolver,
    CoeffectRequest,
    CoeffectState,
)

pytestmark = pytest.mark.e2e


def _req(name: str, executor, timeout: float = 5.0) -> CoeffectRequest:
    return CoeffectRequest(name=name, payload={"executor": executor}, timeout=timeout)


class TestRealUserWorkflowE2E:
    async def test_user_dispatches_parallel_role_setup(self):
        """User dispatches a task; 7-role setup runs concurrently and reports
        a per-role readiness map."""
        resolver = AsyncCoeffectResolver(max_concurrent=7)
        roles = ["architect", "security", "tester", "coder", "devops", "ui", "pm"]

        results = await asyncio.gather(
            *[resolver.aresolve(
                _req(f"setup-{r}", lambda role=r: {"role": role, "ready": True})
            ) for r in roles]
        )

        readiness = {res.value["role"]: res.value["ready"] for res in results}
        assert readiness == dict.fromkeys(roles, True)
        assert all(res.state == CoeffectState.COMPLETED for res in results)

    async def test_user_workflow_survives_role_failure(self):
        """One role's setup crashes; the workflow still finishes and reports
        the failure instead of aborting everything (fail-isolated)."""
        def broken_security_setup():
            raise ConnectionError("security scanner unreachable")

        resolver = AsyncCoeffectResolver(max_concurrent=3)
        results = await asyncio.gather(
            resolver.aresolve(_req("setup-architect", lambda: "ok")),
            resolver.aresolve(_req("setup-security", broken_security_setup)),
            resolver.aresolve(_req("setup-coder", lambda: "ok")),
        )

        states = [res.state for res in results]
        assert states.count(CoeffectState.COMPLETED) == 2
        failed = [res for res in results if res.state == CoeffectState.FAILED][0]
        assert "security scanner unreachable" in failed.error
        # Workflow summary the user would see:
        assert "setup-security" in failed.error

    async def test_user_workflow_hung_coeffect_times_out(self):
        """A hung coeffect (e.g. deadlocked external call) is cut off at the
        configured timeout; the workflow returns within bounded time."""
        def hang_forever():
            time.sleep(3.0)  # would stall the workflow without timeout

        resolver = AsyncCoeffectResolver(max_concurrent=2)
        start = time.monotonic()
        results = await asyncio.gather(
            resolver.aresolve(_req("hung-provider", hang_forever, timeout=0.2)),
            resolver.aresolve(_req("fast-provider", lambda: "done", timeout=1.0)),
        )
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"workflow hung for {elapsed:.1f}s"
        assert results[0].state == CoeffectState.FAILED
        assert "hung-provider" in results[0].error
        assert results[1].state == CoeffectState.COMPLETED

    def test_user_runs_sync_script_bridge(self):
        """A user's plain sync script (no asyncio in their code) calls
        resolve() and gets a result without adopting async style."""
        resolver = AsyncCoeffectResolver()

        def load_config():
            return {"backend": "mock", "mode": "consensus"}

        result = resolver.resolve(_req("load-config", load_config))
        assert result.state == CoeffectState.COMPLETED
        assert result.value == {"backend": "mock", "mode": "consensus"}

    async def test_user_cancels_long_running_workflow(self):
        """User aborts a long-running dispatch; in-flight coeffects land in
        CANCELLED instead of leaking or corrupting the resolver."""
        resolver = AsyncCoeffectResolver(max_concurrent=2)
        task = asyncio.ensure_future(asyncio.gather(
            resolver.aresolve(_req("long-analysis", lambda: time.sleep(2.0))),
            resolver.aresolve(_req("quick-check", lambda: "done")),
        ))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Resolver remains usable after cancellation (no leaked lock/sem).
        follow_up = await resolver.aresolve(_req("after-cancel", lambda: "recovered"))
        assert follow_up.state == CoeffectState.COMPLETED
        assert follow_up.value == "recovered"
