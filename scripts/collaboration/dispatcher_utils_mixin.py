"""DEPRECATED shim — V4.2.0 will delete this file.

Import from ``dispatcher_mixins`` instead. The class definition now lives in
the merged module; this file only re-exports for backward compatibility.

Note: ``import locale`` is kept here because tests patch
``scripts.collaboration.dispatcher_utils_mixin.locale.getlocale`` — removing
it would break ``mock.patch`` target resolution.
"""

import locale  # noqa: F401 — re-exported for mock.patch target compat

from .dispatcher_mixins import DispatcherUtilsMixin

__all__ = ["DispatcherUtilsMixin"]
