#!/usr/bin/env python3
"""Tests for ArtifactStore — V4.5.3 P12.2.1.

ArtifactStore persists Worker output (PRD / patches / tests / reports) to
disk under artifacts/{session_id}/{role_id}/{filename} namespace with a
JSON manifest. Anti-ghost `_call_counter_er` proves wiring.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure repo root on path
sys.path.insert(0, ".")

from scripts.collaboration.artifact_store import (  # noqa: E402
    Artifact,
    ArtifactStore,
    ArtifactStoreError,
    get_call_counter_er,
)


class TestArtifactStoreConstants(unittest.TestCase):
    """Verify schema version + path conventions are stable."""

    def test_schema_version_constant(self):
        from scripts.collaboration.artifact_store import ARTIFACT_SCHEMA_VERSION

        self.assertIsInstance(ARTIFACT_SCHEMA_VERSION, int)
        self.assertEqual(ARTIFACT_SCHEMA_VERSION, 1)

    def test_manifest_filename_constant(self):
        from scripts.collaboration.artifact_store import MANIFEST_FILENAME

        self.assertEqual(MANIFEST_FILENAME, "manifest.json")

    def test_default_root_name(self):
        from scripts.collaboration.artifact_store import DEFAULT_ROOT

        self.assertEqual(DEFAULT_ROOT, "artifacts")


class TestArtifactStoreInit(unittest.TestCase):
    """Verify ArtifactStore initialization."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_creates_root_directory(self):
        self.assertTrue(Path(self.tmp).exists())

    def test_init_with_custom_root(self):
        custom = os.path.join(self.tmp, "custom-root")
        store = ArtifactStore(root=custom)  # noqa: F841
        self.assertTrue(Path(custom).exists())

    def test_root_attribute_is_resolved(self):
        # root is stored as absolute Path
        self.assertEqual(self.store.root, Path(self.tmp).resolve())


class TestArtifactStoreWrite(unittest.TestCase):
    """Verify ArtifactStore.write() persists content + manifest."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_text_artifact(self):
        artifact = self.store.write(
            session_id="sess-1",
            role_id="architect",
            filename="prd.md",
            content="# Hello World",
        )
        self.assertIsInstance(artifact, Artifact)
        self.assertEqual(artifact.role_id, "architect")
        self.assertEqual(artifact.filename, "prd.md")
        self.assertEqual(artifact.session_id, "sess-1")
        self.assertEqual(artifact.kind, "text")
        self.assertEqual(artifact.size, len("# Hello World"))

    def test_write_creates_file_on_disk(self):
        artifact = self.store.write("s1", "coder", "patch.diff", "--- a/x\n+++ b/x\n")  # noqa: F841
        full_path = Path(self.tmp) / "s1" / "coder" / "patch.diff"
        self.assertTrue(full_path.exists())
        self.assertEqual(full_path.read_text(), "--- a/x\n+++ b/x\n")

    def test_write_returns_sha256_in_artifact(self):
        content = "deterministic content"
        artifact = self.store.write("s1", "tester", "report.md", content)
        import hashlib

        expected = hashlib.sha256(content.encode()).hexdigest()
        self.assertEqual(artifact.sha256, expected)

    def test_write_binary_artifact(self):
        binary = b"\x00\x01\x02\xff\xfe"
        artifact = self.store.write("s1", "deployer", "blob.bin", binary, kind="binary")
        self.assertEqual(artifact.kind, "binary")
        self.assertEqual(artifact.size, 5)

    def test_write_updates_manifest(self):
        self.store.write("s1", "architect", "prd.md", "content")
        manifest_path = Path(self.tmp) / "s1" / "manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(len(manifest["artifacts"]), 1)
        self.assertEqual(manifest["artifacts"][0]["filename"], "prd.md")

    def test_write_multiple_artifacts_keeps_manifest_consistent(self):
        for i in range(3):
            self.store.write("s1", "coder", f"file_{i}.txt", f"content-{i}")
        manifest = json.loads((Path(self.tmp) / "s1" / "manifest.json").read_text())
        self.assertEqual(len(manifest["artifacts"]), 3)
        filenames = {a["filename"] for a in manifest["artifacts"]}
        self.assertEqual(filenames, {"file_0.txt", "file_1.txt", "file_2.txt"})

    def test_write_empty_content_is_allowed(self):
        artifact = self.store.write("s1", "coder", "empty.md", "")
        self.assertEqual(artifact.size, 0)

    def test_write_overwrites_existing(self):
        self.store.write("s1", "coder", "file.md", "v1")
        self.store.write("s1", "coder", "file.md", "v2-longer")
        full_path = Path(self.tmp) / "s1" / "coder" / "file.md"
        self.assertEqual(full_path.read_text(), "v2-longer")
        # Manifest should have single entry (latest)
        manifest = json.loads((Path(self.tmp) / "s1" / "manifest.json").read_text())
        self.assertEqual(len(manifest["artifacts"]), 1)


class TestArtifactStoreRead(unittest.TestCase):
    """Verify ArtifactStore.read() returns content + metadata."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_returns_text(self):
        artifact = self.store.write("s1", "coder", "x.txt", "hello")
        content = self.store.read(artifact.artifact_id)
        self.assertEqual(content, "hello")

    def test_read_returns_bytes_for_binary(self):
        artifact = self.store.write("s1", "coder", "x.bin", b"\xff\x00", kind="binary")
        content = self.store.read(artifact.artifact_id)
        self.assertEqual(content, b"\xff\x00")

    def test_read_unknown_id_raises(self):
        with self.assertRaises(ArtifactStoreError):
            self.store.read("nonexistent-artifact-id")


class TestArtifactStoreList(unittest.TestCase):
    """Verify ArtifactStore.list() filters by session + role."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_returns_all_artifacts_in_session(self):
        self.store.write("s1", "coder", "a.md", "x")
        self.store.write("s1", "tester", "b.md", "y")
        artifacts = self.store.list("s1")
        self.assertEqual(len(artifacts), 2)

    def test_list_filters_by_role(self):
        self.store.write("s1", "coder", "a.md", "x")
        self.store.write("s1", "tester", "b.md", "y")
        artifacts = self.store.list("s1", role_id="coder")
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].role_id, "coder")

    def test_list_empty_session_returns_empty(self):
        self.assertEqual(self.store.list("nonexistent"), [])


class TestArtifactStoreDelete(unittest.TestCase):
    """Verify ArtifactStore.delete() removes file + manifest entry."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_delete_removes_file(self):
        artifact = self.store.write("s1", "coder", "x.md", "content")
        full_path = Path(self.tmp) / "s1" / "coder" / "x.md"
        self.assertTrue(full_path.exists())
        result = self.store.delete(artifact.artifact_id)
        self.assertTrue(result)
        self.assertFalse(full_path.exists())

    def test_delete_updates_manifest(self):
        a1 = self.store.write("s1", "coder", "a.md", "x")
        self.store.write("s1", "coder", "b.md", "y")
        self.store.delete(a1.artifact_id)
        manifest = json.loads((Path(self.tmp) / "s1" / "manifest.json").read_text())
        self.assertEqual(len(manifest["artifacts"]), 1)

    def test_delete_unknown_id_returns_false(self):
        self.assertFalse(self.store.delete("nonexistent"))


class TestArtifactStoreAntiGhost(unittest.TestCase):
    """Verify _call_counter_er increments on every operation (anti-ghost gate)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.store = ArtifactStore(root=self.tmp)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_call_counter_starts_at_zero(self):
        # Module-level counter is shared across instances; reset before check
        from scripts.collaboration import artifact_store as mod

        mod._call_counter_er = 0
        self.assertEqual(get_call_counter_er(), 0)

    def test_write_increments_counter(self):
        before = get_call_counter_er()
        self.store.write("s1", "coder", "x.md", "y")
        self.assertGreater(get_call_counter_er(), before)

    def test_read_increments_counter(self):
        artifact = self.store.write("s1", "coder", "x.md", "y")
        before = get_call_counter_er()
        self.store.read(artifact.artifact_id)
        self.assertGreater(get_call_counter_er(), before)

    def test_list_increments_counter(self):
        before = get_call_counter_er()
        self.store.list("s1")
        self.assertGreater(get_call_counter_er(), before)

    def test_delete_increments_counter(self):
        artifact = self.store.write("s1", "coder", "x.md", "y")
        before = get_call_counter_er()
        self.store.delete(artifact.artifact_id)
        self.assertGreater(get_call_counter_er(), before)


class TestArtifactDataclass(unittest.TestCase):
    """Verify Artifact dataclass shape + immutability-ish behavior."""

    def test_artifact_required_fields(self):
        from scripts.collaboration.artifact_store import Artifact

        a = Artifact(
            artifact_id="art-1",
            session_id="s1",
            role_id="coder",
            filename="x.md",
            sha256="abc",
            size=10,
            kind="text",
            path="/tmp/s1/coder/x.md",
        )
        self.assertEqual(a.artifact_id, "art-1")
        self.assertEqual(a.kind, "text")


if __name__ == "__main__":
    unittest.main()
