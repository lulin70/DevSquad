#!/usr/bin/env python3
"""Tests for Worker ArtifactStore integration — V4.5.3 P12.2.2.

After Worker.execute() completes successfully, the finding must be persisted
to ArtifactStore (best-effort: artifact write failures do NOT fail the
worker). Anti-ghost: ArtifactStore._call_counter_er must increment.

Integration:
    Worker → write_finding(scratchpad) → ArtifactStore.write()
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, ".")

from scripts.collaboration.artifact_store import ArtifactStore, get_call_counter_er
from scripts.collaboration.effect_registry import EffectRegistry
from scripts.collaboration.models import TaskDefinition
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker


class _StubBackend:
    """Minimal LLM backend stub (no network)."""

    def __init__(self, response: str = "Worker output") -> None:
        self.response = response

    def generate(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self.response

    async def agenerate(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self.response


class TestWorkerArtifactPersistence(unittest.TestCase):
    """Verify Worker.execute() persists findings to ArtifactStore."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)
        self.registry = EffectRegistry()

        from scripts.collaboration import artifact_store as as_mod
        from scripts.collaboration import effect_registry as er_mod

        as_mod.set_global_registry(self.registry)
        er_mod._call_counter_er = 0

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_worker(self, session_id: str = "sess-1") -> Worker:
        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="w-arch-1",
            role_id="architect",
            role_prompt="You are an architect",
            scratchpad=scratchpad,
            llm_backend=_StubBackend("Architect findings"),
        )
        # Stash session_id for artifact persistence
        worker._session_id = session_id  # type: ignore[attr-defined]
        return worker

    def test_execute_persists_artifact(self):
        worker = self._make_worker(session_id="sess-1")
        task = TaskDefinition(
            task_id="t-1",
            description="Design the system",
            role_id="architect",
        )
        worker._session_id = "sess-1"  # type: ignore[attr-defined]
        before = get_call_counter_er()
        result = worker.execute(task)
        self.assertTrue(result.success)
        # ArtifactStore was called → counter incremented
        self.assertGreater(get_call_counter_er(), before)

    def test_execute_writes_artifact_file(self):
        worker = self._make_worker(session_id="sess-1")
        task = TaskDefinition(
            task_id="t-1",
            description="Design the system",
            role_id="architect",
        )
        worker.execute(task)
        # Check artifact file exists
        role_dir = Path(self.tmp) / "sess-1" / "architect"
        if role_dir.exists():
            files = list(role_dir.iterdir())
            self.assertGreater(len(files), 0)
            content = files[0].read_text(encoding="utf-8")
            self.assertIn("Architect findings", content)

    def test_execute_failure_does_not_write_artifact(self):
        """If worker crashes, no artifact should be written."""

        class CrashingBackend:
            def generate(self, *args, **kwargs):  # noqa: ANN002, ANN003
                raise RuntimeError("simulated failure")

            async def agenerate(self, *args, **kwargs):  # noqa: ANN002, ANN003
                raise RuntimeError("simulated failure")

        scratchpad = Scratchpad()
        worker = Worker(
            worker_id="w-coder-1",
            role_id="coder",
            role_prompt="crash",
            scratchpad=scratchpad,
            llm_backend=CrashingBackend(),
        )
        worker._session_id = "sess-crash"  # type: ignore[attr-defined]
        task = TaskDefinition(
            task_id="t-2",
            description="crash",
            role_id="coder",
        )
        result = worker.execute(task)
        self.assertFalse(result.success)
        # Check no files written
        role_dir = Path(self.tmp) / "sess-crash" / "coder"
        if role_dir.exists():
            files = list(role_dir.iterdir())
            self.assertEqual(len(files), 0)


if __name__ == "__main__":
    unittest.main()
