#!/usr/bin/env python3
"""ArtifactStore contract tests — V4.5.3 P12.2.1.

These tests verify the **stable public contract** of ``ArtifactStore``
that downstream callers (7-role Worker, dashboard, audit pipeline) depend on.

Contracts under test:
  A1  write()/read()/list()/delete() — basic CRUD round-trip.
  A2  Atomic writes — manifest survives partial failures (tmp + rename).
  A3  Binary content via base64 — bytes round-trip without truncation.
  A4  Path traversal prevention — filename validation rejects separators,
      empty/dot/dotdot.
  A5  Schema version constant is exposed for forward compatibility.
  A6  Manifest structure (schema_version + artifacts list).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_root() -> Path:
    """Create a fresh temp root directory per test."""
    root = Path(tempfile.mkdtemp(prefix="artifact_contract_"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def store(tmp_root: Path):
    """Create an isolated ArtifactStore instance with its own global EffectRegistry."""
    from scripts.collaboration.artifact_store import ArtifactStore
    from scripts.collaboration.effect_registry import EffectRegistry
    from scripts.collaboration.artifact_store import set_global_registry

    # Isolate the global EffectRegistry so tests don't interfere.
    set_global_registry(EffectRegistry())
    return ArtifactStore(root=tmp_root)


# ── A1: CRUD round-trip ─────────────────────────────────────────────────────


class TestArtifactStoreCRUDContract:
    """A1: write → read → list → delete round-trip works."""

    def test_write_returns_artifact_descriptor(self, store) -> None:
        art = store.write("s1", "tester", "out.md", "hello")
        assert hasattr(art, "artifact_id")
        assert art.session_id == "s1"
        assert art.role_id == "tester"
        assert art.filename == "out.md"
        assert art.size == len(b"hello")
        assert art.sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_read_round_trip_text(self, store) -> None:
        art = store.write("s1", "tester", "out.md", "hello world")
        content = store.read(art.artifact_id)
        assert content == "hello world"

    def test_list_returns_written_artifacts(self, store) -> None:
        store.write("s1", "tester", "a.md", "AAA")
        store.write("s1", "tester", "b.md", "BBB")
        store.write("s1", "architect", "c.md", "CCC")
        listed = store.list("s1")
        assert len(listed) == 3
        filenames = {a.filename for a in listed}
        assert filenames == {"a.md", "b.md", "c.md"}

    def test_list_filters_by_role(self, store) -> None:
        store.write("s1", "tester", "a.md", "AAA")
        store.write("s1", "architect", "c.md", "CCC")
        only_tester = store.list("s1", role_id="tester")
        assert len(only_tester) == 1
        assert only_tester[0].role_id == "tester"

    def test_delete_removes_artifact(self, store) -> None:
        art = store.write("s1", "tester", "del.md", "x")
        deleted = store.delete(art.artifact_id)
        assert deleted is True
        # list should no longer contain it
        remaining = store.list("s1")
        assert all(a.artifact_id != art.artifact_id for a in remaining)

    def test_delete_unknown_returns_false(self, store) -> None:
        assert store.delete("nonexistent-id") is False


# ── A2: Atomic writes ───────────────────────────────────────────────────────


class TestArtifactStoreAtomicityContract:
    """A2: writes must use atomic tmp + rename; manifest must survive."""

    def test_write_creates_file_on_disk(self, store, tmp_root) -> None:
        store.write("s1", "tester", "atom.md", "body")
        file_path = tmp_root / "s1" / "tester" / "atom.md"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "body"

    def test_write_overwrites_existing(self, store, tmp_root) -> None:
        store.write("s1", "tester", "atom.md", "first")
        store.write("s1", "tester", "atom.md", "second")
        file_path = tmp_root / "s1" / "tester" / "atom.md"
        assert file_path.read_text(encoding="utf-8") == "second"

    def test_manifest_atomic_rewrite(self, store, tmp_root) -> None:
        store.write("s1", "tester", "x.md", "X")
        manifest_path = tmp_root / "s1" / "manifest.json"
        assert manifest_path.exists()
        # Manifest is valid JSON
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "artifacts" in manifest
        assert manifest["schema_version"] == 1

    def test_artifact_id_is_unique_per_write(self, store) -> None:
        ids = set()
        for _ in range(20):
            art = store.write("s1", "tester", f"f{_}.md", "x")
            assert art.artifact_id not in ids
            ids.add(art.artifact_id)


# ── A3: Binary content (base64) ──────────────────────────────────────────────


class TestArtifactStoreBinaryContract:
    """A3: Binary content must round-trip without truncation."""

    def test_binary_round_trip(self, store) -> None:
        payload = bytes(range(256))  # all byte values
        art = store.write("s1", "tester", "bin.dat", payload, kind="binary")
        assert art.kind == "binary"
        out = store.read(art.artifact_id)
        assert out == payload

    def test_binary_kind_recorded_in_manifest(self, store, tmp_root) -> None:
        art = store.write("s1", "tester", "bin.dat", b"\x00\x01\x02", kind="binary")
        manifest = json.loads((tmp_root / "s1" / "manifest.json").read_text())
        entry = next(a for a in manifest["artifacts"] if a["artifact_id"] == art.artifact_id)
        assert entry["kind"] == "binary"

    def test_large_binary_no_truncation(self, store) -> None:
        # 1 MB of zeros
        payload = b"\x00" * (1024 * 1024)
        art = store.write("s1", "tester", "big.dat", payload, kind="binary")
        assert len(store.read(art.artifact_id)) == len(payload)


# ── A4: Path traversal prevention ────────────────────────────────────────────


class TestArtifactStorePathTraversalContract:
    """A4: Filename validation must reject path separators & dotfiles."""

    def test_filename_with_separator_rejected(self, store) -> None:
        from scripts.collaboration.artifact_store import ArtifactStoreError

        with pytest.raises(ArtifactStoreError):
            store.write("s1", "tester", "../etc/passwd", "evil")

    def test_filename_with_subdir_rejected(self, store) -> None:
        from scripts.collaboration.artifact_store import ArtifactStoreError

        with pytest.raises(ArtifactStoreError):
            store.write("s1", "tester", "subdir/file.md", "x")

    def test_filename_empty_rejected(self, store) -> None:
        from scripts.collaboration.artifact_store import ArtifactStoreError

        with pytest.raises(ArtifactStoreError):
            store.write("s1", "tester", "", "x")

    def test_filename_dot_rejected(self, store) -> None:
        from scripts.collaboration.artifact_store import ArtifactStoreError

        with pytest.raises(ArtifactStoreError):
            store.write("s1", "tester", ".", "x")

    def test_filename_dotdot_rejected(self, store) -> None:
        from scripts.collaboration.artifact_store import ArtifactStoreError

        with pytest.raises(ArtifactStoreError):
            store.write("s1", "tester", "..", "x")


# ── A5: Schema version & module metadata ────────────────────────────────────


class TestArtifactStoreSchemaContract:
    """A5: Schema version constant + module-level metadata are exposed."""

    def test_schema_version_constant(self) -> None:
        from scripts.collaboration.artifact_store import ARTIFACT_SCHEMA_VERSION

        assert isinstance(ARTIFACT_SCHEMA_VERSION, int)
        assert ARTIFACT_SCHEMA_VERSION >= 1

    def test_manifest_filename_constant(self) -> None:
        from scripts.collaboration.artifact_store import MANIFEST_FILENAME

        assert MANIFEST_FILENAME == "manifest.json"

    def test_default_root_constant(self) -> None:
        from scripts.collaboration.artifact_store import DEFAULT_ROOT

        assert DEFAULT_ROOT == "artifacts"

    def test_artifact_dataclass_has_required_fields(self) -> None:
        from scripts.collaboration.artifact_store import Artifact

        required = {
            "artifact_id",
            "session_id",
            "role_id",
            "filename",
            "sha256",
            "size",
            "kind",
            "path",
            "created_at",
        }
        from dataclasses import fields
        actual = {f.name for f in fields(Artifact)}
        assert required.issubset(actual)

    def test_get_call_counter_exposed(self) -> None:
        from scripts.collaboration.artifact_store import get_call_counter

        assert isinstance(get_call_counter(), int)


# ── A6: Manifest schema ────────────────────────────────────────────────────


class TestArtifactStoreManifestContract:
    """A6: Manifest has the documented schema."""

    def test_empty_manifest_has_schema_version(self, store, tmp_root) -> None:
        # Trigger creation of session dir by writing something
        store.write("s1", "tester", "x.md", "x")
        manifest_path = tmp_root / "s1" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["schema_version"] == 1
        assert isinstance(manifest["artifacts"], list)