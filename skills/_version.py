"""Single source of truth for skills layer version.

This module provides the canonical version string for the skills package.
All skill handlers and registry should import __version__ from here instead
of hardcoding version strings, preventing version drift across the skills layer.

The canonical project version lives in scripts/collaboration/_version.py;
this file mirrors that value for the skills layer to avoid cross-package imports.
"""

from scripts.collaboration._version import __version__

__all__ = ["__version__"]
