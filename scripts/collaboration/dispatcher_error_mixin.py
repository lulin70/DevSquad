"""DEPRECATED shim — V4.2.0 will delete this file.

Import from ``dispatcher_mixins`` instead. The class definition now lives in
the merged module; this file only re-exports for backward compatibility.
"""

from .dispatcher_mixins import DispatcherErrorMixin

__all__ = ["DispatcherErrorMixin"]
