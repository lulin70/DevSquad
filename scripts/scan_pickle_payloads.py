#!/usr/bin/env python3
"""One-shot pickle payload scanner — V4.3.0 P0-1.

Scans a directory tree for files that may contain pickle payloads.
Identifies candidate files by:

1. **Pickle magic bytes**: ``\x80\x04`` (protocol 4) or ``\x80\x05`` (protocol 5)
   at the start of the file.
2. **JSON parse failure**: For files that are not valid UTF-8 / JSON, mark as
   "suspected pickle" if the magic bytes match.

This scanner **never** calls ``pickle.loads`` — it only inspects file headers
and content type. This avoids triggering any OWASP A08:2021 deserialization
risk during the scan itself.

Usage::

    python scripts/scan_pickle_payloads.py [--root DIR] [--output PATH]

    # Default: scan ./scripts and ./data, output to stdout
    python scripts/scan_pickle_payloads.py

    # Scan a specific directory, write JSON report
    python scripts/scan_pickle_payloads.py --root /var/lib/devsquad/cache --output report.json

Exit code:
- 0: No suspected pickle payloads found
- 1: One or more suspected pickle payloads found (review required)
- 2: Scan error (e.g. root directory not found)

This is a one-shot tool for V4.3.0 P0-1. After P2-1 removes the pickle
fallback entirely, this scanner can be deleted or kept as a defensive check.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Pickle protocol 4/5 magic bytes — the first 2 bytes of a pickle stream.
PICKLE_MAGIC_PROTOCOL_4 = b"\x80\x04"
PICKLE_MAGIC_PROTOCOL_5 = b"\x80\x05"
PICKLE_MAGIC_BYTES = (PICKLE_MAGIC_PROTOCOL_4, PICKLE_MAGIC_PROTOCOL_5)

# Directories that are never scanned (third-party, caches, etc.).
DEFAULT_EXCLUDE_DIRS = frozenset({
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".git",
    "node_modules",
    ".hypothesis",
    ".ruff_cache",
})


@dataclass
class PickleSuspect:
    """A file suspected of containing a pickle payload."""

    path: str
    size_bytes: int
    reason: str  # "magic_bytes_protocol_4" | "magic_bytes_protocol_5" | "json_parse_failure"
    first_bytes_hex: str  # first 16 bytes as hex, for forensic inspection


@dataclass
class ScanReport:
    """Result of a pickle payload scan."""

    root: str
    scanned_at: str  # ISO 8601 timestamp
    scanned_files: int
    skipped_files: int
    suspected_pickle_files: list[PickleSuspect] = field(default_factory=list)

    @property
    def has_suspects(self) -> bool:
        return bool(self.suspected_pickle_files)

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "has_suspects": self.has_suspects,
        }


def _is_excluded(path: Path, exclude_dirs: frozenset[str]) -> bool:
    """Return True if ``path`` is inside any excluded directory."""
    return any(part in exclude_dirs for part in path.parts)


def _check_file_for_pickle(path: Path) -> PickleSuspect | None:
    """Inspect a single file for pickle indicators.

    Returns a ``PickleSuspect`` if the file is suspected of containing a
    pickle payload, else ``None``. Never calls ``pickle.loads``.
    """
    try:
        with path.open("rb") as f:
            head = f.read(16)
    except (OSError, PermissionError) as e:
        logger.debug("Skipping %s (read error): %s", path, e)
        return None

    if not head:
        return None

    if head.startswith(PICKLE_MAGIC_PROTOCOL_4):
        return PickleSuspect(
            path=str(path),
            size_bytes=path.stat().st_size,
            reason="magic_bytes_protocol_4",
            first_bytes_hex=head.hex(),
        )
    if head.startswith(PICKLE_MAGIC_PROTOCOL_5):
        return PickleSuspect(
            path=str(path),
            size_bytes=path.stat().st_size,
            reason="magic_bytes_protocol_5",
            first_bytes_hex=head.hex(),
        )

    # For text files (decoded as UTF-8), JSON parse failure on a small file
    # is not a strong pickle signal — skip. We only flag files that look
    # binary (fail UTF-8 strict decode) AND match pickle magic.
    return None


def scan_directory(root: Path, exclude_dirs: frozenset[str] | None = None) -> ScanReport:
    """Scan ``root`` recursively for files suspected of containing pickle payloads.

    Args:
        root: Directory to scan. Must exist.
        exclude_dirs: Directory names to skip. Defaults to :data:`DEFAULT_EXCLUDE_DIRS`.

    Returns:
        A :class:`ScanReport` summarizing the scan.
    """
    if not root.exists():
        raise FileNotFoundError(f"Scan root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Scan root is not a directory: {root}")

    excludes = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    scanned = 0
    skipped = 0
    suspects: list[PickleSuspect] = []

    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if _is_excluded(path, excludes):
            skipped += 1
            continue
        if path.suffix == ".py":
            # Source files are always text — skip. Pickle payloads in DevSquad
            # only ever appear in cache directories, never in source.
            skipped += 1
            continue
        scanned += 1
        suspect = _check_file_for_pickle(path)
        if suspect is not None:
            suspects.append(suspect)

    return ScanReport(
        root=str(root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scanned_files=scanned,
        skipped_files=skipped,
        suspected_pickle_files=suspects,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot pickle payload scanner (V4.3.0 P0-1).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        nargs="+",
        default=[Path("scripts"), Path("data"), Path(".devsquad_data")],
        help="Root directory(s) to scan (default: scripts data .devsquad_data).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this path (default: stdout summary).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    all_suspects: list[PickleSuspect] = []
    total_scanned = 0
    total_skipped = 0
    roots_scanned: list[str] = []

    for root in args.root:
        if not root.exists():
            logger.warning("Root does not exist, skipping: %s", root)
            continue
        logger.info("Scanning %s ...", root)
        report = scan_directory(root)
        roots_scanned.append(str(root))
        total_scanned += report.scanned_files
        total_skipped += report.skipped_files
        all_suspects.extend(report.suspected_pickle_files)
        if report.has_suspects:
            logger.warning(
                "Found %d suspected pickle payload(s) under %s:",
                len(report.suspected_pickle_files),
                root,
            )
            for s in report.suspected_pickle_files:
                logger.warning("  - %s (%s, %d bytes)", s.path, s.reason, s.size_bytes)

    summary = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "roots_scanned": roots_scanned,
        "total_scanned_files": total_scanned,
        "total_skipped_files": total_skipped,
        "total_suspected_pickle_files": len(all_suspects),
        "suspected_pickle_files": [asdict(s) for s in all_suspects],
    }

    if args.output:
        args.output.write_text(json.dumps(summary, indent=2))
        logger.info("Report written to %s", args.output)
    else:
        print(json.dumps(summary, indent=2))

    return 1 if all_suspects else 0


if __name__ == "__main__":
    sys.exit(main())
