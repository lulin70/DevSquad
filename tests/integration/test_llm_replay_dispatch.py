#!/usr/bin/env python3
"""Integration tests: LLM replay cache wired into the real dispatch path.

V4.6.0 P1-a (PRD §7.2). Verifies the two-run replay journey through the
production pipeline (not just the cache class):

- Run 1 (read-write): real backend called once per role, responses recorded.
- Run 2 (read): the same instruction replays from the cache — the backend is
  NOT called again — and ``details["replay_cache"]`` discloses the hit.
- Verification gate: a backend that raises never leaves a cache entry.
- OFF mode: dispatch results carry no ``replay_cache`` key (reports stay
  byte-identical to V4.5.24).
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_cache import reset_cache
from scripts.collaboration.llm_replay_policy import REPLAY_ENV_VAR, ReplayMode


class _CountingBackend:
    """Minimal deterministic backend that counts generate() calls.

    Deliberately NOT a MockBackend subclass — the worker caches only when the
    backend is real (non-mock), which is the path under test. Calls are
    tagged by ``role_id``: Worker calls carry it, direct dispatcher calls
    (role matching) do not — the replay cache covers the Worker path (PRD
    scope), the matcher's direct call is expected to stay live.
    """

    def __init__(self) -> None:
        self.generate_calls = 0
        self.worker_calls = 0
        self.model = "replay-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        self.generate_calls += 1
        if kwargs.get("role_id") is not None:
            self.worker_calls += 1
        return f"REPLAYED-RESPONSE-{self.generate_calls}: {prompt[:40]}"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield self.generate(prompt, **kwargs)


@pytest.fixture
def replay_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Isolate the LLM cache singleton: temp dir + reset, per test."""
    import scripts.collaboration.llm_cache as lcm

    monkeypatch.setenv(REPLAY_ENV_VAR, "read-write")
    original_init = lcm.LLMCache.__init__

    def _init_with_tmp(self, *args: Any, **kwargs: Any):
        kwargs["cache_dir"] = str(tmp_path / "replay")
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(lcm.LLMCache, "__init__", _init_with_tmp)
    reset_cache()
    yield monkeypatch
    reset_cache()


def _set_mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv(REPLAY_ENV_VAR, mode)
    reset_cache()


# ── Two-run replay journey (same process, production dispatch path) ──


class TestReplayDispatchJourney:
    def test_second_dispatch_replays_without_backend_call(self, replay_env):
        monkeypatch = replay_env

        backend = _CountingBackend()
        # enable_memory=False + one dispatcher instance per run: the anchor
        # checker records goal-drift findings that a later dispatch of the
        # SAME instance would legitimately inject into its prompts ("Related
        # Findings"), changing the prompt on purpose. The replay journey
        # tests the cache, so all cross-dispatch state is isolated off.
        # enable_memory=False: retrospective injection likewise changes the
        # run2 prompt by design.
        disp1 = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
        try:
            r1 = disp1.dispatch("Write a haiku about caches", roles=["architect"])
            assert r1.success, f"run1 failed: {r1.errors}"
            worker_calls_after_run1 = backend.worker_calls
            assert worker_calls_after_run1 >= 1, "run1 must call the real backend via the worker path"
        finally:
            disp1.shutdown()

        _set_mode(monkeypatch, ReplayMode.READ.value)

        disp2 = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
        try:
            r2 = disp2.dispatch("Write a haiku about caches", roles=["architect"])
            assert r2.success, f"run2 failed: {r2.errors}"
            assert backend.worker_calls == worker_calls_after_run1, (
                "run2 must replay worker calls from cache — zero worker-path backend calls"
            )
            replay_info = r2.details.get("replay_cache")
            assert replay_info is not None, "replay disclosure missing in run2 details"
            assert replay_info["mode"] == "read"
            assert replay_info["hits"] >= 1
            assert "Replay cache" in r2.to_markdown()
        finally:
            disp2.shutdown()

    def test_off_mode_details_carry_no_replay_key(self, replay_env):
        monkeypatch = replay_env
        _set_mode(monkeypatch, "off")

        backend = _CountingBackend()
        disp = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
        try:
            r = disp.dispatch("Off-mode disclosure probe", roles=["architect"])
            assert r.success, f"dispatch failed: {r.errors}"
            assert "replay_cache" not in r.details, "OFF mode must not add replay disclosure"
            assert "Replay cache" not in r.to_markdown()
        finally:
            disp.shutdown()


# ── Verification gate: exceptions never reach the cache ──


class TestVerificationGate:
    def test_backend_exception_leaves_no_replay_entry(self, replay_env):
        class _ExplodingBackend(_CountingBackend):
            def generate(self, prompt: str, **kwargs: Any) -> str:
                self.generate_calls += 1
                raise RuntimeError("simulated provider outage")

        backend = _ExplodingBackend()
        disp = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
        try:
            # Worker catches and re-raises; the coordinator converts the role
            # failure into a failed dispatch result (fail-closed contract).
            result = disp.dispatch("This will fail at the backend", roles=["architect"])
        finally:
            disp.shutdown()

        assert not result.success, "a backend outage must fail the dispatch"
        # The worker only caches successful backend responses — the exploding
        # role's prompt must have no recording. With a single exploding role
        # there are no successful calls at all, so the disk layer stays empty.
        from scripts.collaboration.llm_cache import get_llm_cache

        singleton = get_llm_cache()
        written = list(singleton.cache_dir.glob("*.json"))
        assert not written, f"a backend exception must never produce a replay recording; found {written}"
        reset_cache()
