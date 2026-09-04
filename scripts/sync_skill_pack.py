#!/usr/bin/env python3
"""sync_skill_pack.py — DevSquad skill pack sync tool (Python 3.10).

Synchronizes a source workspace skill pack directory (default:
``<repo>/.trae/skills/devsquad``) into one or more target cache locations
(default: ``~/.trae-cn/skills/devsquad`` and ``~/.trae/skills/devsquad``).

Design contract (V1):

* Only operates on the named pack subdirectory. **NEVER** touches files
  outside that subdirectory under the target's ``skills/`` root — e.g.
  other packs (``docs``, ``ima-skill``, ``memory-classification-engine``,
  ``trae-agency``, etc.) are strictly preserved.
* Default mode is **non-destructive merge**: missing destination files are
  added; existing files are overwritten **iff** their SHA-256 differs from
  the source. By default, files that exist in the destination but not in
  the source are **left alone** (no cleanup). An explicit
  ``--clean-extra`` flag is provided for callers that want to remove
  destination-only files; it is **off** by default.
* ``--dry-run`` previews every change without writing.
* Every written file is SHA-256 verified after copy (read back and
  compare) to catch transport-level corruption.
* Zero third-party dependencies — only the Python 3.10 standard library.

Typical usage::

    python3 scripts/sync_skill_pack.py                 # real sync, no cleanup
    python3 scripts/sync_skill_pack.py --dry-run       # preview only
    python3 scripts/sync_skill_pack.py --clean-extra   # also drop extras
    python3 scripts/sync_skill_pack.py --source <path> --target <path>  # custom

CLI exits 0 on success (including dry-run), 1 on any I/O / verification
failure (including target being a symlink — refused for safety).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "DEFAULT_PACK_NAME",
    "DEFAULT_REPO_RELATIVE_SOURCE",
    "DEFAULT_TARGETS",
    "SyncReport",
    "sync_pack",
    "iter_source_files",
    "sha256_file",
    "main",
]

# Repository root is the parent of this script's directory.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

DEFAULT_PACK_NAME = "devsquad"
DEFAULT_REPO_RELATIVE_SOURCE = Path(".trae") / "skills" / DEFAULT_PACK_NAME
DEFAULT_TARGETS: tuple[Path, ...] = (
    Path.home() / ".trae-cn" / "skills" / DEFAULT_PACK_NAME,
    Path.home() / ".trae" / "skills" / DEFAULT_PACK_NAME,
)

_CHUNK_SIZE = 1024 * 1024  # 1 MiB read chunks for hashing large files.


# ---------------------------------------------------------------------------
# Pure helpers (no I/O side effects beyond reading)
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of ``path``'s contents."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def iter_source_files(source_dir: Path) -> list[Path]:
    """Return a sorted list of regular files under ``source_dir`` (recursive).

    Symlinks are deliberately skipped — we only mirror real files to keep
    the sync output deterministic and avoid following arbitrary targets.
    """
    if not source_dir.is_dir():
        return []
    files: list[Path] = []
    for entry in sorted(source_dir.rglob("*")):
        if entry.is_symlink():
            continue
        if entry.is_file():
            files.append(entry)
    return files


# ---------------------------------------------------------------------------
# Sync engine
# ---------------------------------------------------------------------------


@dataclass
class SyncReport:
    """Aggregated outcome for syncing a single source -> target pair."""

    source: Path
    target: Path
    copied: list[Path] = field(default_factory=list)
    overwritten: list[Path] = field(default_factory=list)
    skipped_unchanged: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    verified_ok: list[Path] = field(default_factory=list)
    verified_mismatch: list[str] = field(default_factory=list)

    @property
    def total_actions(self) -> int:
        return (
            len(self.copied)
            + len(self.overwritten)
            + len(self.removed)
        )


def _resolve_target(target: Path, dry_run: bool) -> Path:
    """Resolve ``target`` and refuse symlinks unless dry_run.

    Symlinks are refused so a malicious or accidental symlink at the
    destination cannot cause us to write outside the intended pack
    directory. In dry-run mode we still flag the issue but don't fail
    the user hard — they may want to see what *would* happen.
    """
    if target.is_symlink():
        return target  # caller decides; we report the refusal below.
    return target


def _safe_rmtree_children(target_dir: Path, keep_names: set[str], dry_run: bool) -> list[Path]:
    """Remove children of ``target_dir`` whose names are not in ``keep_names``.

    Returns the list of paths that were (or would be) removed. Only direct
    children of the target pack directory are considered — we never
    recurse into ``target_dir``'s parent (which would risk touching other
    packs). Sub-directories inside the pack that are not present in the
    source are also removed wholesale.
    """
    removed: list[Path] = []
    if not target_dir.exists():
        return removed
    for child in sorted(target_dir.iterdir()):
        if child.name in keep_names:
            continue
        # Refuse to follow symlinks (defence in depth).
        if child.is_symlink():
            continue
        removed.append(child)
        if not dry_run:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    return removed


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy ``src`` to ``dst`` via a sibling tmp file + rename.

    The tmp file uses the same directory as ``dst`` so the final rename
    is atomic on POSIX. The tmp file is removed on any failure.
    """
    tmp = dst.with_name(dst.name + ".sync_tmp")
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()


def sync_pack(
    source_dir: Path,
    target_dir: Path,
    *,
    dry_run: bool = False,
    clean_extra: bool = False,
) -> SyncReport:
    """Synchronize ``source_dir`` into ``target_dir``.

    Returns a :class:`SyncReport`. I/O failures populate
    ``report.errors`` rather than raising, so callers can decide whether
    to abort or continue.
    """
    report = SyncReport(source=source_dir, target=target_dir)

    if not source_dir.is_dir():
        report.errors.append(f"source directory not found: {source_dir}")
        return report

    # Refuse symlinked target pack dir for safety.
    if target_dir.exists() and target_dir.is_symlink():
        report.errors.append(
            f"refusing to sync: target is a symlink: {target_dir}"
        )
        return report

    # Collect source files (relative paths for comparison).
    src_files = iter_source_files(source_dir)
    src_index = {p.relative_to(source_dir): p for p in src_files}

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Track which top-level entries we will keep under target_dir so we
    # never wipe out something that wasn't part of our source. This
    # collection is namespaced to the *contents* of target_dir only —
    # never its siblings or ancestors.
    keep_names: set[str] = set()

    for relpath, src_path in src_index.items():
        dst_path = target_dir / relpath
        # ``relpath`` is a ``pathlib.PurePath``; use ``.parts`` for
        # cross-platform top-level-name extraction. Empty parts (leading
        # ``/``) are skipped.
        keep_names.add(relpath.parts[0])
        try:
            if dst_path.exists() and dst_path.is_symlink():
                report.errors.append(
                    f"refusing to overwrite symlink: {dst_path}"
                )
                continue

            src_sha = sha256_file(src_path)

            if dst_path.exists():
                if not dst_path.is_file():
                    report.errors.append(
                        f"destination exists but is not a regular file: {dst_path}"
                    )
                    continue
                try:
                    dst_sha = sha256_file(dst_path)
                except OSError as exc:
                    report.errors.append(
                        f"failed to read destination for sha256: {dst_path}: {exc}"
                    )
                    continue
                if dst_sha == src_sha:
                    report.skipped_unchanged.append(dst_path)
                    continue
                bucket = report.overwritten
            else:
                bucket = report.copied

            if dry_run:
                bucket.append(dst_path)
                continue

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                _atomic_copy(src_path, dst_path)
            except OSError as exc:
                report.errors.append(
                    f"failed to copy {src_path} -> {dst_path}: {exc}"
                )
                continue

            # Verify by reading back.
            try:
                verified_sha = sha256_file(dst_path)
            except OSError as exc:
                report.errors.append(
                    f"failed to verify sha256 after copy: {dst_path}: {exc}"
                )
                continue
            if verified_sha != src_sha:
                report.verified_mismatch.append(
                    f"{dst_path} (expected {src_sha}, got {verified_sha})"
                )
                continue
            bucket.append(dst_path)
            report.verified_ok.append(dst_path)
        except OSError as exc:
            report.errors.append(f"unexpected I/O error for {relpath}: {exc}")

    # Optional cleanup of destination-only entries. Disabled by default.
    if clean_extra:
        removed = _safe_rmtree_children(
            target_dir, keep_names=keep_names, dry_run=dry_run
        )
        report.removed.extend(removed)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync_skill_pack.py",
        description=(
            "Sync the DevSquad skill pack from the workspace source "
            "directory into one or more TRAE skill cache locations. "
            "Default targets are ~/.trae-cn/skills/devsquad and "
            "~/.trae/skills/devsquad. By default, files not present "
            "in the source are preserved (no cleanup); pass "
            "--clean-extra to remove them."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=_REPO_ROOT / DEFAULT_REPO_RELATIVE_SOURCE,
        help=(
            "Path to the source skill pack directory (default: "
            "<repo>/.trae/skills/devsquad)."
        ),
    )
    parser.add_argument(
        "--target",
        action="append",
        type=Path,
        default=None,
        help=(
            "Destination directory. May be specified multiple times. "
            "Defaults to ~/.trae-cn/skills/devsquad and "
            "~/.trae/skills/devsquad if not provided."
        ),
    )
    parser.add_argument(
        "--pack-name",
        default=DEFAULT_PACK_NAME,
        help=(
            "Pack name used for documentation only; does not change "
            "paths. Default: 'devsquad'."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the sync without writing any files.",
    )
    parser.add_argument(
        "--clean-extra",
        action="store_true",
        help=(
            "Remove files in the destination that are not present in "
            "the source. Off by default — destination-only files are "
            "preserved."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-file output; only print summary and errors.",
    )
    return parser


def _format_report(report: SyncReport, *, dry_run: bool, quiet: bool) -> str:
    tag = "[DRY-RUN] " if dry_run else ""
    lines: list[str] = []
    lines.append(
        f"{tag}Source: {report.source}\n"
        f"{tag}Target: {report.target}"
    )
    if not quiet:
        if report.copied:
            lines.append(f"{tag}  copy ({len(report.copied)}):")
            for p in report.copied:
                lines.append(f"    + {p}")
        if report.overwritten:
            lines.append(f"{tag}  overwrite ({len(report.overwritten)}):")
            for p in report.overwritten:
                lines.append(f"    ~ {p}")
        if report.skipped_unchanged:
            lines.append(
                f"{tag}  unchanged ({len(report.skipped_unchanged)}): "
                "(sha256 match)"
            )
        if report.removed:
            lines.append(f"{tag}  remove ({len(report.removed)}):")
            for p in report.removed:
                lines.append(f"    - {p}")
    lines.append(
        f"{tag}  copied={len(report.copied)} "
        f"overwritten={len(report.overwritten)} "
        f"unchanged={len(report.skipped_unchanged)} "
        f"removed={len(report.removed)} "
        f"errors={len(report.errors)}"
    )
    if report.errors:
        lines.append(f"{tag}  errors:")
        for err in report.errors:
            lines.append(f"    ! {err}")
    if report.verified_mismatch:
        lines.append(f"{tag}  sha256 mismatches after copy:")
        for line in report.verified_mismatch:
            lines.append(f"    ! {line}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    targets: tuple[Path, ...] = tuple(args.target) if args.target else DEFAULT_TARGETS

    any_error = False
    for target in targets:
        report = sync_pack(
            args.source,
            target,
            dry_run=args.dry_run,
            clean_extra=args.clean_extra,
        )
        print(_format_report(report, dry_run=args.dry_run, quiet=args.quiet))
        print()
        if report.errors or report.verified_mismatch:
            any_error = True

    return 1 if any_error and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
