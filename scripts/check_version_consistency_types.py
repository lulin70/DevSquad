#!/usr/bin/env python3
"""Shared result model for the version-consistency gate.

Extracted from ``check_version_consistency.py`` (V4.5.20 size-gate refactor) so
the individual check helpers can live in their own modules without a
back-import to the gate entry point (which would be circular).

``VersionCheck`` is re-exported from ``check_version_consistency`` so its
public import path is unchanged.
"""

from __future__ import annotations

from typing import NamedTuple


class VersionCheck(NamedTuple):
    """Result of a single file version check."""

    file: str
    expected: str
    found: str | None
    passed: bool
    detail: str = ""
