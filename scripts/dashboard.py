#!/usr/bin/env python3
"""
Backward-compatible dashboard entry point.

``scripts/dashboard.py`` now delegates to the ``scripts.dashboard`` package.
New code should import from ``scripts.dashboard.*`` or run
``scripts/dashboard/app.py`` directly.
"""

from scripts.dashboard.app import main

if __name__ == "__main__":
    main()
