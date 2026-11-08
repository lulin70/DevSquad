#!/usr/bin/env python3
"""
Backward-compatible dashboard entry point (DEPRECATED).

**Deprecation Notice (V4.10.1):**
This file is deprecated and will be removed in V5.0.0 (scheduled for 2027-Q1).

**Migration Path:**
- Direct execution: Use ``python -m scripts.dashboard.app`` or
  ``streamlit run scripts/dashboard/app.py``
- Import usage: Replace ``from scripts.dashboard import X`` with
  ``from scripts.dashboard.app import X``

**Rationale:**
The dashboard module was refactored into a proper package (scripts/dashboard/)
in V3.6.0. This top-level proxy file creates path ambiguity and should be
removed once all consumers migrate to the package path.

**Timeline:**
- V4.10.1 (2026-11-05): Deprecation warning added
- V4.11.0 (2026-12): Warning escalated to stderr
- V5.0.0 (2027-Q1): File removed

See: docs/DEPRECATION_POLICY.md
"""

import warnings

warnings.warn(
    "scripts/dashboard.py is deprecated and will be removed in V5.0.0. "
    "Use 'python -m scripts.dashboard.app' or import from scripts.dashboard.app directly.",
    DeprecationWarning,
    stacklevel=2,
)

from scripts.dashboard.app import main  # noqa: E402 - the deprecation warning must fire before the import

if __name__ == "__main__":
    main()
