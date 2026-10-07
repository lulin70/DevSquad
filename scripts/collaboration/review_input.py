#!/usr/bin/env python3
"""Deterministic normalization for review file and diff inputs."""

from __future__ import annotations

import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


class ReviewInputError(ValueError):
    """Raised when review inputs violate the C18 contract."""


@dataclass(frozen=True)
class ReviewInput:
    """Normalized review paths and non-public diff context."""

    paths: tuple[str, ...]
    deleted_paths: tuple[str, ...]
    diff: str | None = None


def _strip_diff_prefix(path: str) -> str:
    path = path.strip().strip('"')
    if path == "/dev/null":
        return path
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _header_path(line: str) -> str | None:
    value = line[4:].strip()
    if value == "/dev/null":
        return value
    if "\t" in value:
        value = value.split("\t", 1)[0]
    elif value.startswith('"'):
        try:
            value = shlex.split(value, posix=True)[0]
        except ValueError as exc:
            raise ReviewInputError(f"malformed diff path: {line}") from exc
    else:
        parts = value.split(" ", 1)
        if len(parts) == 2 and parts[1][:1].isdigit():
            value = parts[0]
    return _strip_diff_prefix(value)


def _git_paths(line: str) -> tuple[str, str] | None:
    try:
        parts = shlex.split(line[11:], posix=True)
    except ValueError as exc:
        raise ReviewInputError(f"malformed diff header: {line}") from exc
    if len(parts) != 2:
        raise ReviewInputError(f"malformed diff header: {line}")
    return _strip_diff_prefix(parts[0]), _strip_diff_prefix(parts[1])


def parse_unified_diff(diff: str) -> ReviewInput:
    """Extract changed and deleted paths from a unified diff."""
    if not isinstance(diff, str) or not diff.strip():
        raise ReviewInputError("diff must be a non-empty string")

    paths: list[str] = []
    deleted: list[str] = []
    pending_git: tuple[str, str] | None = None
    old_path: str | None = None
    new_path: str | None = None
    saw_file_marker = False
    saw_rename = False

    def add(path: str | None) -> None:
        if path and path != "/dev/null" and path not in paths:
            paths.append(path)

    def mark_deleted(path: str | None) -> None:
        if path and path != "/dev/null" and path not in deleted:
            deleted.append(path)

    def finish_block() -> None:
        nonlocal pending_git, old_path, new_path, saw_file_marker, saw_rename
        if pending_git is None:
            return
        git_old, git_new = pending_git
        resolved_old = old_path or git_old
        resolved_new = new_path or git_new
        if resolved_old == "/dev/null":
            add(resolved_new)
        elif resolved_new == "/dev/null":
            add(resolved_old)
            mark_deleted(resolved_old)
        elif resolved_old != resolved_new and (saw_rename or not saw_file_marker):
            mark_deleted(resolved_old)
            add(resolved_new)
        else:
            add(resolved_new)
        pending_git = None
        old_path = new_path = None
        saw_file_marker = False
        saw_rename = False

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            finish_block()
            pending_git = _git_paths(line)
            continue
        if pending_git is None:
            continue
        if line.startswith("rename from "):
            old_path = _strip_diff_prefix(line[12:])
            saw_rename = True
            continue
        if line.startswith("rename to "):
            new_path = _strip_diff_prefix(line[10:])
            saw_rename = True
            continue
        if line.startswith("--- "):
            if pending_git is None:
                pending_git = ("", "")
            old_path = _header_path(line)
            saw_file_marker = True
            continue
        if line.startswith("+++ "):
            new_path = _header_path(line)
            saw_file_marker = True

    finish_block()

    if not paths:
        raise ReviewInputError("diff contains no file paths")

    return ReviewInput(
        paths=tuple(paths),
        deleted_paths=tuple(deleted),
        diff=diff,
    )


def normalize_review_input(
    *,
    changeset: Iterable[str] | None = None,
    diff: str | None = None,
    deleted_paths: Iterable[str] = (),
) -> ReviewInput:
    """Normalize path-list and diff inputs; the two public forms are exclusive."""
    path_values = tuple(_normalize_input_path(path) for path in (changeset or ()))
    deleted_values = tuple(_normalize_input_path(path) for path in (deleted_paths or ()))
    if path_values and diff is not None:
        raise ReviewInputError("changeset and diff are mutually exclusive")
    if diff is not None:
        parsed = parse_unified_diff(diff)
        merged_deleted = tuple(dict.fromkeys((*parsed.deleted_paths, *deleted_values)))
        return ReviewInput(parsed.paths, merged_deleted, parsed.diff)
    return ReviewInput(tuple(dict.fromkeys(path_values)), tuple(dict.fromkeys(deleted_values)))


def _normalize_input_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def read_diff_file(path: str | Path) -> str:
    """Read a user-supplied diff file at the CLI boundary."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ReviewInputError(f"cannot read diff file: {path}") from exc
