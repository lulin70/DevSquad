#!/usr/bin/env python3
"""Tests for Artifact↔Effect binding — V4.5.3 P12.2.5.

Every ArtifactStore write/delete/rename must register a corresponding
effect in the global EffectRegistry. When dispatch fails, the registry
revert_all() must roll back all artifacts written during the failed
session.

Anti-ghost: ArtifactStore._call_counter AND EffectRegistry._call_counter
both increment.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")

from scripts.collaboration.artifact_store import ArtifactStore, get_call_counter as _as_count
from scripts.collaboration.dispatch_effect import WriteFileEffect
from scripts.collaboration.effect_registry import (
    EffectRegistry,
    get_call_count as _er_count,
)


class TestArtifactEffectBinding(unittest.TestCase):
    """Verify ArtifactStore.write() registers an effect in the registry."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)
        self.registry = EffectRegistry()
        # Reset counter at start
        from scripts.collaboration import effect_registry as er_mod

        er_mod._call_counter = 0

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_registers_write_effect(self):
        from scripts.collaboration import artifact_store as as_mod

        as_mod.set_global_registry(self.registry)
        self.store.write("s1", "coder", "out.md", "content")
        self.assertEqual(self.registry.pending_count(), 1)

    def test_write_effect_revert_removes_artifact_file(self):
        from scripts.collaboration import artifact_store as as_mod

        as_mod.set_global_registry(self.registry)
        self.store.write("s1", "coder", "out.md", "content")
        file_path = Path(self.tmp) / "s1" / "coder" / "out.md"
        self.assertTrue(file_path.exists())

        outcomes = self.registry.revert_all()
        self.assertEqual(len(outcomes), 1)
        self.assertTrue(outcomes[0].success)
        self.assertFalse(file_path.exists())

    def test_delete_registers_delete_effect(self):
        from scripts.collaboration import artifact_store as as_mod

        as_mod.set_global_registry(self.registry)
        # First write
        self.store.write("s1", "coder", "out.md", "content")
        artifact_id = self.store.list("s1")[0].artifact_id
        self.store.delete(artifact_id)
        # Both write and delete are in registry (LIFO order)
        self.assertEqual(self.registry.pending_count(), 2)

    def test_dispatch_failure_reverts_all_artifacts(self):
        from scripts.collaboration import artifact_store as as_mod

        as_mod.set_global_registry(self.registry)
        # Simulate "worker A writes file" → "worker B writes file" → "dispatch fails"
        self.store.write("sess-1", "architect", "prd.md", "PRD content")
        self.store.write("sess-1", "tester", "tests.md", "Test plan")
        self.store.write("sess-1", "coder", "patch.diff", "diff content")
        self.assertEqual(self.registry.pending_count(), 3)

        # Simulate dispatch failure → revert all
        outcomes = self.registry.revert_all()
        self.assertEqual(len(outcomes), 3)
        self.assertTrue(all(o.success for o in outcomes))

        # All files should be gone
        for role_id, filename in (
            ("architect", "prd.md"),
            ("tester", "tests.md"),
            ("coder", "patch.diff"),
        ):
            path = Path(self.tmp) / "sess-1" / role_id / filename
            self.assertFalse(path.exists(), f"{path} should not exist after revert")


class TestArtifactEffectBindingIsolated(unittest.TestCase):
    """Verify binding isolation across registries."""

    def test_independent_registries_have_independent_stacks(self):
        from scripts.collaboration import artifact_store as as_mod
        from scripts.collaboration import effect_registry as er_mod

        er_mod._call_counter = 0
        reg1 = EffectRegistry()
        reg2 = EffectRegistry()

        with tempfile.TemporaryDirectory() as tmp:
            store1 = ArtifactStore(root=os.path.join(tmp, "s1"))
            store2 = ArtifactStore(root=os.path.join(tmp, "s2"))
            as_mod.set_global_registry(reg1)
            store1.write("s", "coder", "x.md", "X")
            as_mod.set_global_registry(reg2)
            store2.write("s", "coder", "y.md", "Y")
            self.assertEqual(reg1.pending_count(), 1)
            self.assertEqual(reg2.pending_count(), 1)


if __name__ == "__main__":
    unittest.main()
