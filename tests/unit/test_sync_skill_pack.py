#!/usr/bin/env python3
"""Unit tests for ``scripts.sync_skill_pack`` (V1).

Iron Rules applied:

1. Documentation-first: source (``scripts/sync_skill_pack.py``) was read
   first. Documented contract: recursive mirror of a source skill pack
   into one or more target cache locations; SHA-256 verified after
   every write; ``--dry-run`` is non-destructive; by default destination-
   only files are **preserved**; never touches sibling packs under the
   target ``skills/`` root.
2. Failure-means-report: every assertion checks a real on-disk state
   (a unique ``tmp_path`` per test), no Mock.
3. Dimension-completeness: 8 tests across Happy / Error / Boundary /
   Config / Side-Effect dimensions.
4. Side-effect-verification: CLI exit codes are asserted by invoking
   the module's ``main()`` directly.
5. User-journey-first: mirrors the real sync journey (one source, two
   independent targets, ``--dry-run``, ``--clean-extra``).
6. e2e-release-gate: covers the safety-critical "don't touch sibling
   packs" guarantee that motivated this tool.

V4.5.16 P2.12 (M3 backlog closure): this module is dual-runnable as
both a ``pytest`` module (function-style tests with ``tmp_path``/
``monkeypatch`` fixtures) and a ``unittest`` module. The four
P2.12 focused tests at the bottom follow the same dual-runnable
convention so both the ``pytest`` and the
``python3 -m unittest tests.unit.test_sync_skill_pack`` entry points
discover and execute them.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts import sync_skill_pack  # noqa: E402


def _populate_source(root, files):
    """Write ``files`` (dict of relative path -> text) under ``root``."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Happy
# ---------------------------------------------------------------------------


class TestSyncSkillPackHappy(unittest.TestCase):
    """Happy-path sync tests (V1 contract). unittest-style so
    ``python3 -m unittest tests.unit.test_sync_skill_pack`` discovers
    them. Each test uses ``tempfile.TemporaryDirectory`` to mirror the
    ``pytest`` ``tmp_path`` fixture semantics."""

    def test_happy_sync_copies_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Library/fixture use (recursive mirror). For real pack-root CLI
            # sync, only SKILL.md + skill-manifest.yaml are part of the
            # whitelist — see ``test_pack_root_only_syncs_whitelisted_files``.
            src = _populate_source(td_path / "src", {"SKILL.md": "hello", "sub/note.md": "sub note"})
            tgt = td_path / "tgt"

            report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

            assert report.errors == []
            assert sorted([str(p) for p in report.copied]) == sorted(
                [str(tgt / "SKILL.md"), str(tgt / "sub" / "note.md")]
            )
            assert not report.verified_mismatch
            assert sorted([str(p) for p in report.verified_ok]) == sorted(
                [str(tgt / "SKILL.md"), str(tgt / "sub" / "note.md")]
            )
            assert (tgt / "SKILL.md").read_text(encoding="utf-8") == "hello"
            assert (tgt / "sub" / "note.md").read_text(encoding="utf-8") == "sub note"

    def test_happy_sync_skips_unchanged_via_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = _populate_source(td_path / "src", {"file.md": "same"})
            tgt = td_path / "tgt"
            (tgt / "file.md").parent.mkdir(parents=True, exist_ok=True)
            (tgt / "file.md").write_text("same", encoding="utf-8")

            report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

            assert report.copied == []
            assert report.overwritten == []
            assert len(report.skipped_unchanged) == 1

    def test_happy_overwrites_when_sha_differs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = _populate_source(td_path / "src", {"file.md": "new content"})
            tgt = td_path / "tgt"
            (tgt / "file.md").parent.mkdir(parents=True, exist_ok=True)
            (tgt / "file.md").write_text("OLD content", encoding="utf-8")

            report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

            assert report.errors == []
            assert len(report.overwritten) == 1
            assert (tgt / "file.md").read_text(encoding="utf-8") == "new content"


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write(tmp_path) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "preview"})
    tgt = tmp_path / "tgt"

    report = sync_skill_pack.sync_pack(
        src,
        tgt,
        dry_run=True,
        clean_extra=True,
    )

    assert len(report.copied) == 1
    assert not tgt.exists()
    assert report.verified_ok == []
    assert report.verified_mismatch == []


# ---------------------------------------------------------------------------
# Safety: do NOT touch sibling packs / files outside the pack root
# ---------------------------------------------------------------------------


def test_default_preserves_destination_only_files(tmp_path) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "from source"})
    tgt = tmp_path / "tgt"
    tgt.mkdir(parents=True, exist_ok=True)
    # File not in source -> must be preserved by default.
    (tgt / "stale.md").write_text("destination only", encoding="utf-8")
    (tgt / "archive").mkdir(parents=True, exist_ok=True)
    (tgt / "archive" / "old.md").write_text("keep me", encoding="utf-8")

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

    assert report.removed == []
    assert report.errors == []
    assert (tgt / "stale.md").exists()
    assert (tgt / "archive" / "old.md").exists()
    assert (tgt / "SKILL.md").read_text(encoding="utf-8") == "from source"


def test_clean_extra_removes_destination_only(tmp_path) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "current"})
    tgt = tmp_path / "tgt"
    tgt.mkdir(parents=True, exist_ok=True)
    (tgt / "stale.md").write_text("old", encoding="utf-8")
    (tgt / "archive").mkdir(parents=True, exist_ok=True)
    (tgt / "archive" / "old.md").write_text("drop", encoding="utf-8")

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=False, clean_extra=True)

    assert not (tgt / "stale.md").exists()
    assert not (tgt / "archive").exists()
    assert (tgt / "SKILL.md").read_text(encoding="utf-8") == "current"
    names_removed = {p.name for p in report.removed}
    assert "stale.md" in names_removed
    assert "archive" in names_removed


def test_does_not_touch_sibling_packs_under_target_root(tmp_path) -> None:
    """Safety: sibling packs in the same ``skills/`` parent are never touched.

    Reproduces the explicit requirement: this tool must not clean up
    other packs under ``~/.trae-cn/skills`` (e.g. ``docs``, ``ima-skill``).
    """
    skills_root = tmp_path / "skills_root"
    src = skills_root / "_src_devsquad"
    tgt = skills_root / "devsquad"
    sibling = skills_root / "other_pack"
    tgt.mkdir(parents=True, exist_ok=True)
    sibling.mkdir(parents=True, exist_ok=True)

    _populate_source(src, {"SKILL.md": "new"})

    sibling_file = sibling / "important.md"
    sibling_file.write_text("sibling MUST survive", encoding="utf-8")
    sibling_sub = sibling / "nested" / "data.md"
    sibling_sub.parent.mkdir(parents=True, exist_ok=True)
    sibling_sub.write_text("nested MUST survive", encoding="utf-8")

    stale_in_devsquad = tgt / "stale.md"
    stale_in_devsquad.write_text("only this is pack-local stale", encoding="utf-8")

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=False, clean_extra=True)

    # Sibling pack files untouched.
    assert sibling_file.exists()
    assert sibling_file.read_text(encoding="utf-8") == "sibling MUST survive"
    assert sibling_sub.exists()
    assert sibling_sub.read_text(encoding="utf-8") == "nested MUST survive"
    # Pack-local stale removed.
    assert not stale_in_devsquad.exists()
    # Source synced.
    assert (tgt / "SKILL.md").read_text(encoding="utf-8") == "new"
    # The tool never reports sibling-pack paths in removed/skipped.
    removed_paths = {str(p) for p in report.removed}
    for must_keep in (sibling_file, sibling_sub):
        assert str(must_keep) not in removed_paths


# ---------------------------------------------------------------------------
# Error / symlink safety
# ---------------------------------------------------------------------------


def test_symlinked_target_refused(tmp_path) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "x"})
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir(parents=True, exist_ok=True)
    link = tmp_path / "tgt_link"
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks not supported on this platform")
    os.symlink(str(real_dir), str(link))

    report = sync_skill_pack.sync_pack(src, link, dry_run=False)
    assert report.errors
    assert any("refusing to sync" in e for e in report.errors), (
        f"expected refusal error, got: {report.errors}"
    )
    # Nothing was written into the symlink target.
    assert not (real_dir / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# CLI integration: exit codes
# ---------------------------------------------------------------------------


def test_cli_dry_run_exits_zero(tmp_path) -> None:
    """Side-Effect: ``main(['--dry-run'])`` exits 0 even with no source."""
    rc = sync_skill_pack.main(
        [
            "--dry-run",
            "--source",
            str(tmp_path / "no_such_src"),
            "--target",
            str(tmp_path / "any_tgt"),
            "--quiet",
        ]
    )
    assert rc == 0


def test_copy_mode_verifies_written_sha256(tmp_path) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "current"})
    tgt = tmp_path / "tgt"

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

    expected = hashlib.sha256(b"current").hexdigest()
    assert report.verified_ok == [tgt / "SKILL.md"]
    assert sync_skill_pack.sha256_file(tgt / "SKILL.md") == expected


def test_cli_targets_mock_home_directories_and_clean_extra(tmp_path, monkeypatch) -> None:
    src = _populate_source(tmp_path / "src", {"SKILL.md": "current"})
    targets = (
        tmp_path / ".trae-cn" / "skills" / "devsquad",
        tmp_path / ".trae" / "skills" / "devsquad",
    )
    for target in targets:
        target.mkdir(parents=True)
        (target / "stale.md").write_text("remove me", encoding="utf-8")
    monkeypatch.setattr(sync_skill_pack, "DEFAULT_TARGETS", targets)

    rc = sync_skill_pack.main(["--source", str(src), "--clean-extra", "--quiet"])

    assert rc == 0
    for target in targets:
        assert (target / "SKILL.md").read_text(encoding="utf-8") == "current"
        assert not (target / "stale.md").exists()


# ---------------------------------------------------------------------------
# V4.5.16 P2.12: focused dimension-completeness tests.
# Iron Rule 3 (dimension-completeness): one assertion per dimension.
#   - Config dimension: --dry-run is purely non-destructive.
#   - Side-Effect dimension: copy mode writes real bytes with SHA-256
#     matching the source (verified via hashlib, not just the report).
#   - Config dimension (clean-extra): monkeypatched DEFAULT_TARGETS to a
#     tmp_path ensures no ~/.trae-cn / ~/.trae is touched; destination-
#     only files inside the pack are removed.
#   - CLI dimension: ``--help`` exits 0 (argparse contract).
#
# Each test is also exposed as a ``unittest.TestCase`` so the
# ``python3 -m unittest tests.unit.test_sync_skill_pack`` entry point
# in the V4.5.16 release gate discovers and exercises them.
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write_v4516(tmp_path) -> None:
    """Config/Side-Effect: ``dry_run=True`` must not touch the destination.

    Strengthens the existing boundary: target directory must not exist on
    disk *and* no ``verified_ok`` paths must be recorded (those are only
    populated after a real read-back hash check, which dry-run skips).
    """
    src = _populate_source(tmp_path / "src", {"SKILL.md": "preview", "sub/n.md": "n"})
    tgt = tmp_path / "tgt"

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=True)

    # No file landed on disk.
    assert not tgt.exists()
    assert not (tgt / "SKILL.md").exists()
    assert not (tgt / "sub" / "n.md").exists()
    # Verified-after-copy list is only populated by real writes.
    assert report.verified_ok == []
    # The two source files were *planned* for copy.
    assert len(report.copied) == 2


def test_copy_mode_writes_real_bytes_with_sha256_match(tmp_path) -> None:
    """Side-Effect: copy mode writes real bytes whose SHA-256 matches source.

    Uses :func:`hashlib.sha256` directly (not the module's own helper) to
    ensure the on-disk bytes are what the caller intends — independent of
    ``sync_skill_pack.sha256_file`` implementation.
    """
    payload = "DevSquad V4.5.16 sync_skill_pack copy-mode test payload"
    src = _populate_source(tmp_path / "src", {"SKILL.md": payload, "data.txt": "abc"})
    tgt = tmp_path / "tgt"

    report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

    expected_skill = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    expected_data = hashlib.sha256(b"abc").hexdigest()

    assert report.errors == []
    assert len(report.copied) == 2
    assert len(report.verified_ok) == 2
    assert report.verified_mismatch == []

    # On-disk bytes truly match the source content.
    on_disk_skill = (tgt / "SKILL.md").read_bytes()
    on_disk_data = (tgt / "data.txt").read_bytes()
    assert hashlib.sha256(on_disk_skill).hexdigest() == expected_skill
    assert hashlib.sha256(on_disk_data).hexdigest() == expected_data

    # The verified_ok list reports the destination paths that round-tripped.
    assert (tgt / "SKILL.md") in report.verified_ok
    assert (tgt / "data.txt") in report.verified_ok


def test_clean_extra_removes_destination_only_v4516(tmp_path, monkeypatch) -> None:
    """Config (clean-extra): monkeypatch ``DEFAULT_TARGETS`` to tmp_path so
    no real ``~/.trae-cn`` / ``~/.trae`` cache is touched. Files inside
    the pack that are NOT in source must be removed; source files must be
    synced.

    The monkeypatch isolates the test from the developer's real caches
    while still exercising the full ``main()`` -> ``sync_pack()`` ->
    ``_safe_rmtree_children()`` path.
    """
    src = _populate_source(tmp_path / "src", {"SKILL.md": "current"})
    targets = (
        tmp_path / ".trae-cn" / "skills" / "devsquad",
        tmp_path / ".trae" / "skills" / "devsquad",
    )
    for target in targets:
        target.mkdir(parents=True)
        (target / "stale.md").write_text("destination-only; must be removed", encoding="utf-8")
        (target / "keepme.md").write_text("not in source; must be removed", encoding="utf-8")
    monkeypatch.setattr(sync_skill_pack, "DEFAULT_TARGETS", targets)

    rc = sync_skill_pack.main(
        ["--source", str(src), "--clean-extra", "--quiet"]
    )

    # No real ~/.trae-cn or ~/.trae was used (monkeypatched).
    for target in targets:
        assert (target / "SKILL.md").read_text(encoding="utf-8") == "current"
        assert not (target / "stale.md").exists(), (
            f"destination-only file should be removed under {target}"
        )
        assert not (target / "keepme.md").exists(), (
            f"destination-only file should be removed under {target}"
        )
    assert rc == 0


def test_cli_help_exits_zero() -> None:
    """CLI: ``--help`` exits 0 and prints the program description.

    argparse normally calls ``sys.exit(0)`` on ``--help``; calling
    ``main(["--help"])`` would raise ``SystemExit(0)`` instead of
    returning a normal exit code. We assert ``SystemExit.code == 0``
    to honor the documented ``--help`` contract.
    """
    with pytest.raises(SystemExit) as exc_info:
        sync_skill_pack.main(["--help"])

    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# unittest.TestCase mirror of the four P2.12 tests so the
# ``python3 -m unittest tests.unit.test_sync_skill_pack`` entry point
# in the V4.5.16 release gate discovers and runs them too.
# ---------------------------------------------------------------------------


class TestSyncSkillPackV4516P212(unittest.TestCase):
    """V4.5.16 P2.12 mirror of the four dimension-completeness tests."""

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Library/fixture mode: no repo-root indicators, so the recursive
            # mirror is engaged (both top-level + nested files copy).
            src = _populate_source(td_path / "src", {"SKILL.md": "preview", "sub/n.md": "n"})
            tgt = td_path / "tgt"

            report = sync_skill_pack.sync_pack(src, tgt, dry_run=True)

            assert not tgt.exists()
            assert not (tgt / "SKILL.md").exists()
            assert not (tgt / "sub" / "n.md").exists()
            assert report.verified_ok == []
            assert len(report.copied) == 2
            self.assertEqual(sorted([str(p) for p in report.copied]),
                             sorted([str(tgt / "SKILL.md"), str(tgt / "sub" / "n.md")]))

    def test_copy_mode_writes_real_bytes_with_sha256_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            payload = "DevSquad V4.5.16 sync_skill_pack copy-mode test payload"
            src = _populate_source(
                td_path / "src",
                {"SKILL.md": payload, "data.txt": "abc"},
            )
            tgt = td_path / "tgt"

            report = sync_skill_pack.sync_pack(src, tgt, dry_run=False)

            expected_skill = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            expected_data = hashlib.sha256(b"abc").hexdigest()

            assert report.errors == []
            assert len(report.copied) == 2
            assert len(report.verified_ok) == 2
            assert report.verified_mismatch == []

            on_disk_skill = (tgt / "SKILL.md").read_bytes()
            on_disk_data = (tgt / "data.txt").read_bytes()
            self.assertEqual(hashlib.sha256(on_disk_skill).hexdigest(), expected_skill)
            self.assertEqual(hashlib.sha256(on_disk_data).hexdigest(), expected_data)
            self.assertIn(tgt / "SKILL.md", report.verified_ok)
            self.assertIn(tgt / "data.txt", report.verified_ok)

    def test_clean_extra_removes_destination_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = _populate_source(td_path / "src", {"SKILL.md": "current"})
            targets = (
                td_path / ".trae-cn" / "skills" / "devsquad",
                td_path / ".trae" / "skills" / "devsquad",
            )
            for target in targets:
                target.mkdir(parents=True)
                (target / "stale.md").write_text("destination-only", encoding="utf-8")
                (target / "keepme.md").write_text("not in source", encoding="utf-8")

            # Patch DEFAULT_TARGETS for the duration of main() only.
            original = sync_skill_pack.DEFAULT_TARGETS
            sync_skill_pack.DEFAULT_TARGETS = targets
            try:
                rc = sync_skill_pack.main(
                    ["--source", str(src), "--clean-extra", "--quiet"]
                )
            finally:
                sync_skill_pack.DEFAULT_TARGETS = original

            self.assertEqual(rc, 0)
            for target in targets:
                self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "current")
                self.assertFalse((target / "stale.md").exists())
                self.assertFalse((target / "keepme.md").exists())

    def test_cli_help_exits_zero(self) -> None:
        # ``main(["--help"])`` triggers argparse's ``sys.exit(0)``; capture
        # via SystemExit rather than letting it propagate.
        try:
            rc = sync_skill_pack.main(["--help"])
        except SystemExit as exc:
            self.assertEqual(exc.code, 0)
        else:
            # Defensive: argparse may also return without exiting if its
            # exit_on_error config is altered — accept 0 either way.
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
