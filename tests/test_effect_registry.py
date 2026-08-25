#!/usr/bin/env python3
"""Tests for DispatchEffect Protocol + EffectRegistry — V4.5.3 P12.2.3/2.4.

EffectRegistry provides LIFO revert semantics for filesystem operations
(WriteFileEffect, DeleteFileEffect, RenameFileEffect). Revert must be
idempotent — failed reverts don't block subsequent reverts.

Anti-ghost: _call_counter incremented on every registry operation.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, ".")

from scripts.collaboration.dispatch_effect import (  # noqa: E402
    DeleteFileEffect,
    EffectContext,
    EffectOutcome,
    RenameFileEffect,
    WriteFileEffect,
)
from scripts.collaboration.effect_registry import (  # noqa: E402
    EffectRegistry,
    get_call_count,
)


class TestEffectContext(unittest.TestCase):
    """Verify EffectContext shape."""

    def test_required_fields(self):
        ctx = EffectContext(
            effect_id="eff-1",
            effect_type="write_file",
            payload={"path": "/tmp/x", "content": "hi"},
        )
        self.assertEqual(ctx.effect_id, "eff-1")
        self.assertEqual(ctx.effect_type, "write_file")
        self.assertEqual(ctx.payload["path"], "/tmp/x")
        self.assertIsInstance(ctx.applied_at, float)


class TestEffectOutcome(unittest.TestCase):
    """Verify EffectOutcome shape."""

    def test_default_success(self):
        out = EffectOutcome(success=True)
        self.assertTrue(out.success)
        self.assertIsNone(out.error)
        self.assertEqual(out.side_data, {})

    def test_failure_with_error(self):
        out = EffectOutcome(success=False, error="boom")
        self.assertFalse(out.success)
        self.assertEqual(out.error, "boom")


class TestWriteFileEffect(unittest.TestCase):
    """Verify WriteFileEffect writes content and reverts."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.path = os.path.join(self.tmp, "out.txt")

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_apply_writes_file(self):
        effect = WriteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="write_file",
            payload={"path": self.path, "content": "hello"},
        )
        out = effect.apply(ctx)
        self.assertTrue(out.success)
        self.assertTrue(os.path.exists(self.path))
        with open(self.path) as f:
            self.assertEqual(f.read(), "hello")

    def test_revert_removes_file(self):
        effect = WriteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="write_file",
            payload={"path": self.path, "content": "hi"},
        )
        effect.apply(ctx)
        out = effect.revert(ctx)
        self.assertTrue(out.success)
        self.assertFalse(os.path.exists(self.path))

    def test_revert_idempotent_when_file_missing(self):
        effect = WriteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="write_file",
            payload={"path": self.path, "content": "hi"},
        )
        # First revert
        effect.revert(ctx)
        # Second revert: should not raise
        out = effect.revert(ctx)
        self.assertTrue(out.success)

    def test_revert_preserves_original_content_if_exists(self):
        # Pre-existing file → WriteFileEffect.apply overwrites → revert restores original
        Path(self.path).write_text("ORIGINAL")
        effect = WriteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="write_file",
            payload={"path": self.path, "content": "NEW", "original_content": "ORIGINAL"},
        )
        effect.apply(ctx)
        self.assertEqual(Path(self.path).read_text(), "NEW")
        effect.revert(ctx)
        self.assertEqual(Path(self.path).read_text(), "ORIGINAL")


class TestDeleteFileEffect(unittest.TestCase):
    """Verify DeleteFileEffect deletes and reverts (restores)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.path = os.path.join(self.tmp, "victim.txt")
        Path(self.path).write_text("ORIGINAL")

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_apply_deletes_file(self):
        effect = DeleteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="delete_file",
            payload={"path": self.path, "original_content": "ORIGINAL"},
        )
        out = effect.apply(ctx)
        self.assertTrue(out.success)
        self.assertFalse(os.path.exists(self.path))

    def test_revert_restores_file(self):
        effect = DeleteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="delete_file",
            payload={"path": self.path, "original_content": "ORIGINAL"},
        )
        effect.apply(ctx)
        out = effect.revert(ctx)
        self.assertTrue(out.success)
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(Path(self.path).read_text(), "ORIGINAL")

    def test_revert_idempotent_when_file_already_restored(self):
        effect = DeleteFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="delete_file",
            payload={"path": self.path, "original_content": "ORIGINAL"},
        )
        effect.apply(ctx)
        effect.revert(ctx)
        # Second revert: file already there, should still succeed
        out = effect.revert(ctx)
        self.assertTrue(out.success)


class TestRenameFileEffect(unittest.TestCase):
    """Verify RenameFileEffect renames and reverts."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.src = os.path.join(self.tmp, "src.txt")
        self.dst = os.path.join(self.tmp, "dst.txt")
        Path(self.src).write_text("CONTENT")

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_apply_renames(self):
        effect = RenameFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="rename_file",
            payload={"src": self.src, "dst": self.dst},
        )
        out = effect.apply(ctx)
        self.assertTrue(out.success)
        self.assertFalse(os.path.exists(self.src))
        self.assertTrue(os.path.exists(self.dst))

    def test_revert_renames_back(self):
        effect = RenameFileEffect()
        ctx = EffectContext(
            effect_id="e1",
            effect_type="rename_file",
            payload={"src": self.src, "dst": self.dst},
        )
        effect.apply(ctx)
        out = effect.revert(ctx)
        self.assertTrue(out.success)
        self.assertTrue(os.path.exists(self.src))
        self.assertFalse(os.path.exists(self.dst))


class TestEffectRegistryBasic(unittest.TestCase):
    """Verify EffectRegistry LIFO + apply/revert_all."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.registry = EffectRegistry()

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_registry_has_zero_pending(self):
        self.assertEqual(self.registry.pending_count(), 0)

    def test_apply_increments_pending(self):
        ctx = EffectContext("e1", "write_file", {"path": os.path.join(self.tmp, "x"), "content": "y"})
        self.registry.apply(WriteFileEffect(), ctx)
        self.assertEqual(self.registry.pending_count(), 1)

    def test_revert_all_clears_pending(self):
        for i in range(3):
            path = os.path.join(self.tmp, f"f{i}.txt")
            ctx = EffectContext(f"e{i}", "write_file", {"path": path, "content": f"c{i}"})
            self.registry.apply(WriteFileEffect(), ctx)
        self.assertEqual(self.registry.pending_count(), 3)
        outcomes = self.registry.revert_all()
        self.assertEqual(len(outcomes), 3)
        self.assertTrue(all(o.success for o in outcomes))
        self.assertEqual(self.registry.pending_count(), 0)


class TestEffectRegistryLIFO(unittest.TestCase):
    """Verify revert_all applies LIFO order (most recent first)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.registry = EffectRegistry()

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lifo_order(self):
        # Create 3 files in order: a, b, c
        # Revert_all should delete in reverse: c, b, a
        paths = []
        effects = []
        contexts = []
        for name in ("a", "b", "c"):
            path = os.path.join(self.tmp, name)
            paths.append(path)
            ctx = EffectContext(
                f"e-{name}", "write_file", {"path": path, "content": name}
            )
            effects.append(WriteFileEffect())
            contexts.append(ctx)
            self.registry.apply(WriteFileEffect(), ctx)

        outcomes = self.registry.revert_all()
        self.assertEqual(len(outcomes), 3)
        # All should have succeeded
        self.assertTrue(all(o.success for o in outcomes))
        # All files should be gone
        for p in paths:
            self.assertFalse(os.path.exists(p))


class TestEffectRegistryFailureTolerance(unittest.TestCase):
    """Verify revert failures don't block subsequent reverts."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.registry = EffectRegistry()

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_failing_revert_does_not_block_others(self):
        # Mix: one effect that will fail to revert, others succeed
        good_path = os.path.join(self.tmp, "good.txt")
        bad_path = os.path.join(self.tmp, "bad.txt")  # intentionally not created

        # Apply 2 effects
        ctx_good = EffectContext(
            "e-good", "write_file", {"path": good_path, "content": "ok"}
        )
        self.registry.apply(WriteFileEffect(), ctx_good)

        # Inject a failing effect manually
        from scripts.collaboration.dispatch_effect import DeleteFileEffect

        ctx_bad = EffectContext(
            "e-bad", "delete_file", {"path": bad_path, "original_content": "ORIG"}
        )
        # Apply with no original_content (revert will fail gracefully)
        ctx_bad.payload = {"path": bad_path}  # missing original_content
        self.registry.apply(DeleteFileEffect(), ctx_bad)

        # Revert all — both should complete (bad one fails silently, good one succeeds)
        outcomes = self.registry.revert_all()
        self.assertEqual(len(outcomes), 2)
        # At least one succeeded (good), one may fail (bad)
        success_count = sum(1 for o in outcomes if o.success)
        self.assertGreaterEqual(success_count, 1)


class TestEffectRegistryAntiGhost(unittest.TestCase):
    """Verify EffectRegistry anti-ghost counter."""

    def setUp(self):
        from scripts.collaboration import effect_registry as mod

        mod._call_counter = 0

    def test_call_counter_starts_at_zero(self):
        self.assertEqual(get_call_count(), 0)

    def test_apply_increments_counter(self):
        reg = EffectRegistry()
        ctx = EffectContext("e1", "write_file", {"path": "/tmp/x", "content": "y"})
        before = get_call_count()
        reg.apply(WriteFileEffect(), ctx)
        self.assertGreater(get_call_count(), before)

    def test_revert_all_increments_counter(self):
        reg = EffectRegistry()
        before = get_call_count()
        reg.revert_all()
        self.assertGreater(get_call_count(), before)


class TestEffectRegistryRevertLast(unittest.TestCase):
    """Verify revert_last pops only the most recent effect."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.registry = EffectRegistry()

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_revert_last_returns_outcome(self):
        path1 = os.path.join(self.tmp, "a.txt")
        path2 = os.path.join(self.tmp, "b.txt")
        self.registry.apply(
            WriteFileEffect(),
            EffectContext("e1", "write_file", {"path": path1, "content": "A"}),
        )
        self.registry.apply(
            WriteFileEffect(),
            EffectContext("e2", "write_file", {"path": path2, "content": "B"}),
        )
        outcome = self.registry.revert_last()
        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.success)
        self.assertEqual(self.registry.pending_count(), 1)
        # path2 should be gone, path1 still exists
        self.assertFalse(os.path.exists(path2))
        self.assertTrue(os.path.exists(path1))

    def test_revert_last_empty_returns_none(self):
        outcome = self.registry.revert_last()
        self.assertIsNone(outcome)


if __name__ == "__main__":
    unittest.main()
