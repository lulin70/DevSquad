"""DEPRECATED shim — V4.2.0 will delete this file.

Import from ``workflow_engine_mixins`` instead. The class definition now lives in
the merged module; this file only re-exports for backward compatibility.
"""

from .workflow_engine_mixins import WorkflowEngineTransitionMixin

__all__ = ["WorkflowEngineTransitionMixin"]
