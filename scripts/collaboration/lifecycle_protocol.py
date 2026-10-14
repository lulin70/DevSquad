#!/usr/bin/env python3
"""
Unified Lifecycle Architecture (Plan C Implementation)

Core abstractions:
  - LifecycleMode: SHORTCUT / FULL / CUSTOM enum
  - PhaseDefinition: Unified phase structure
  - ViewMapping: CLI command → 11-phase mapping
  - LifecycleProtocol: Abstract interface for lifecycle management

This module retains the abstract interface and core data models.
Implementations have been split into:
  - lifecycle_templates.py: SpecTemplate, SPEC_TEMPLATES, ViewMapping, VIEW_MAPPINGS
  - lifecycle_gate.py: Gate check helper functions
  - lifecycle_shortcut_adapter.py: ShortcutLifecycleAdapter, FullLifecycleAdapter, factories

All symbols are re-exported here for backward compatibility.

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .lifecycle_shortcut_adapter import (
        FullLifecycleAdapter,
        ShortcutLifecycleAdapter,
        create_lifecycle_protocol,
        get_shared_protocol,
    )
    from .lifecycle_templates import SPEC_TEMPLATES, VIEW_MAPPINGS, SpecTemplate, ViewMapping

from .document_scanner import (  # noqa: E402
    DocumentScanResult,
    scan_document,
    scan_phase_documents,
)
from .lifecycle_break_vuln import (  # noqa: E402
    BREAK_VULN_PHASES,
    categories_for_phase,
    lifecycle_finding_from_review,
    map_findings_to_phase,
    phases_for_category,
    review_finding_from_lifecycle,
)
from .lifecycle_evidence import findings_from_junit_xml, findings_from_runtime_evidence  # noqa: E402
from .lifecycle_finding_producers import PHASE_PRODUCERS, produce_phase_findings  # noqa: E402
from .models_lifecycle import LifecycleFinding  # noqa: E402
from .remediation import (  # noqa: E402
    ApprovalRecord,
    PatchPreview,
    RemediationProposal,
    apply_approved_patch,
    approve_proposal,
    create_patch_preview,
    proposal_from_finding,
    proposals_from_findings,
    render_proposals_json,
    render_proposals_markdown,
    resolve_finding_after_verification,
)


class LifecycleMode(Enum):
    """
    Three lifecycle modes for different usage scenarios.

    Modes:
      - SHORTCUT: CLI 6-command simplified view (spec/plan/build/test/review/ship)
      - FULL: Complete 11-phase project lifecycle (P1-P11)
      - CUSTOM: User-defined workflow with selected phases
    """

    SHORTCUT = "shortcut"
    FULL = "full"
    CUSTOM = "custom"


@dataclass
class PhaseDefinition:
    """Unified definition for a single lifecycle phase."""

    phase_id: str
    name: str
    description: str
    role_id: str
    dependencies: list[str] = field(default_factory=list)
    artifacts_in: str = ""
    artifacts_out: str = ""
    gate_condition: str = ""
    reviewers: list[str] = field(default_factory=list)
    optional: bool = False
    order: int = 0


class PhaseState(Enum):
    """Phase execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class GateResult:
    """Result of gate check for a phase."""

    passed: bool
    verdict: str  # APPROVE / CONDITIONAL / REJECT
    red_flags: list[dict[str, Any]] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    gap_report: str = ""
    lifecycle_findings: list[LifecycleFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the gate result to a dictionary.

        Returns:
            Dictionary with passed flag, verdict, red-flag and missing-evidence
            counts, and a truncated gap report.
        """
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "red_flags_count": len(self.red_flags),
            "missing_evidence_count": len(self.missing_evidence),
            "gap_report": self.gap_report[:200] if self.gap_report else "",
            "lifecycle_findings": [finding.to_dict() for finding in self.lifecycle_findings],
            "lifecycle_findings_count": len(self.lifecycle_findings),
        }


@dataclass
class PhaseResult:
    """Result of advancing to a phase."""

    success: bool
    phase_id: str
    previous_state: PhaseState
    new_state: PhaseState
    gate_result: GateResult | None = None
    error: str = ""


@dataclass
class LifecycleStatus:
    """Overall lifecycle status."""

    mode: LifecycleMode
    current_phase: str | None
    completed_phases: list[str]
    failed_phases: list[str]
    blocked_phases: list[str]
    progress_percent: float
    can_advance: bool
    next_phase: str | None

    def to_summary(self) -> str:
        """Build a human-readable multi-line summary of lifecycle status.

        Returns:
            Formatted string with mode, current phase, progress, completed
            count, and optional next phase / blocked warning.
        """
        lines = [
            f"Lifecycle Status ({self.mode.value.upper()} Mode)",
            f"Current: {self.current_phase or 'Not started'}",
            f"Progress: {self.progress_percent:.0f}%",
            f"Completed: {len(self.completed_phases)} phases",
        ]
        if self.next_phase:
            lines.append(f"Next: {self.next_phase}")
        if not self.can_advance:
            lines.append("⚠️ Blocked: Check gate conditions")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# P1-3 triage: category + state dual-label with HITL/AFK execution mode.
# Inspired by Matt Pocock's triage philosophy for the Requirements phase.
# ---------------------------------------------------------------------------


@dataclass
class TriageLabel:
    """Triage label for a requirement (P1 phase).

    Combines a category (feature/bug/tech_debt/security) with a state
    (new/triaged/in_progress/blocked/done) and an execution mode:
      - HITL: needs human-in-the-loop confirmation
      - AFK:  can execute asynchronously (away from keyboard)

    Attributes
    ----------
    category:
        Requirement category — ``feature`` | ``bug`` | ``tech_debt`` | ``security``.
    state:
        Lifecycle state — ``new`` | ``triaged`` | ``in_progress`` | ``blocked`` | ``done``.
    execution_mode:
        ``HITL`` (human confirmation required) or ``AFK`` (async autonomous).
    priority:
        ``P0`` | ``P1`` | ``P2`` | ``P3``.
    notes:
        Optional free-form notes.
    """

    category: str  # feature|bug|tech_debt|security
    state: str  # new|triaged|in_progress|blocked|done
    execution_mode: str  # HITL|AFK
    priority: str  # P0|P1|P2|P3
    notes: str = ""


def triage_requirement(requirement: str) -> TriageLabel:
    """Triage a requirement into a :class:`TriageLabel`.

    Uses keyword matching to derive category, execution mode and priority:
      - category: ``"bug"``/``"缺陷"`` → bug, ``"安全"``/``"security"`` → security,
        ``"技术债"``/``"tech debt"`` → tech_debt, otherwise feature.
      - execution_mode: ``"确认"``/``"审批"``/``"confirm"``/``"approve"`` → HITL,
        otherwise AFK.
      - priority: ``"紧急"``/``"urgent"``/``"P0"`` → P0,
        ``"重要"``/``"important"``/``"P1"`` → P1, otherwise P2.

    The state is always ``"new"`` for a freshly triaged requirement.

    Args:
        requirement: Natural-language requirement text.

    Returns:
        A :class:`TriageLabel` with the derived fields.
    """
    text = (requirement or "").lower()

    # Category detection (first match wins).
    bug_keywords = ["bug", "缺陷", "错误", "报错"]
    security_keywords = ["安全", "security", "漏洞", "vulnerability"]
    tech_debt_keywords = ["技术债", "tech debt", "tech_debt", "重构", "refactor"]
    if any(kw in text for kw in security_keywords):
        category = "security"
    elif any(kw in text for kw in bug_keywords):
        category = "bug"
    elif any(kw in text for kw in tech_debt_keywords):
        category = "tech_debt"
    else:
        category = "feature"

    # Execution mode detection.
    hitl_keywords = ["确认", "审批", "confirm", "approve"]
    execution_mode = "HITL" if any(kw in text for kw in hitl_keywords) else "AFK"

    # Priority detection.
    if any(kw in text for kw in ["紧急", "urgent", "p0"]):
        priority = "P0"
    elif any(kw in text for kw in ["重要", "important", "p1"]):
        priority = "P1"
    else:
        priority = "P2"

    return TriageLabel(
        category=category,
        state="new",
        execution_mode=execution_mode,
        priority=priority,
    )


class LifecycleProtocol(ABC):
    """
    Abstract interface for unified lifecycle management.

    This protocol decouples the view layer (CLI 6 commands) from the core engine
    (WorkflowEngine with 11 phases), enabling both SHORTCUT and FULL modes.
    """

    @abstractmethod
    def get_mode(self) -> LifecycleMode:
        """Return current lifecycle mode."""
        ...

    @abstractmethod
    def set_mode(self, mode: LifecycleMode) -> None:
        """Switch lifecycle mode."""
        ...

    @abstractmethod
    def get_all_phases(self) -> list[PhaseDefinition]:
        """Return all available phases in current mode."""
        ...

    @abstractmethod
    def get_active_phases(self) -> list[PhaseDefinition]:
        """Return phases active for the current task/context."""
        ...

    @abstractmethod
    def get_phase(self, phase_id: str) -> PhaseDefinition | None:
        """Return specific phase by ID, or None if not found."""
        ...

    @abstractmethod
    def get_current_phase(self) -> PhaseDefinition | None:
        """Return current phase, or None if not started."""
        ...

    @abstractmethod
    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        """Advance to specified phase, running gate checks."""
        ...

    @abstractmethod
    def check_gate(
        self,
        phase_id: str | None = None,
        *,
        artifacts: Mapping[str, Any] | None = None,
    ) -> GateResult:
        """Check gate conditions for phase (default: current)."""
        ...

    @abstractmethod
    def get_status(self) -> LifecycleStatus:
        """Return overall lifecycle status."""
        ...

    @abstractmethod
    def get_view_mapping(self, command: str) -> Any:
        """Get view mapping for a CLI command (SHORTCUT mode only)."""
        ...

    @abstractmethod
    def resolve_command_to_phases(self, command: str) -> list[PhaseDefinition]:
        """Resolve a CLI command to its underlying phase definitions."""
        ...


# ---------------------------------------------------------------------------
# Backward-compatible lazy re-exports
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> Any:
    """Load adapter and template re-exports without import cycles."""
    if name in {"FullLifecycleAdapter", "ShortcutLifecycleAdapter", "create_lifecycle_protocol", "get_shared_protocol"}:
        from . import lifecycle_shortcut_adapter

        return getattr(lifecycle_shortcut_adapter, name)
    if name in {"SPEC_TEMPLATES", "VIEW_MAPPINGS", "SpecTemplate", "ViewMapping"}:
        from . import lifecycle_templates

        return getattr(lifecycle_templates, name)
    raise AttributeError(name)


__all__ = [
    # Core types
    "LifecycleMode",
    "PhaseDefinition",
    "PhaseState",
    "GateResult",
    "LifecycleFinding",
    "DocumentScanResult",
    "scan_document",
    "scan_phase_documents",
    "ApprovalRecord",
    "PatchPreview",
    "RemediationProposal",
    "apply_approved_patch",
    "approve_proposal",
    "create_patch_preview",
    "proposal_from_finding",
    "resolve_finding_after_verification",
    "proposals_from_findings",
    "render_proposals_markdown",
    "render_proposals_json",
    "PhaseResult",
    "LifecycleStatus",
    "LifecycleProtocol",
    # P1-3 triage
    "TriageLabel",
    "triage_requirement",
    # Templates (re-exported)
    "SpecTemplate",
    "SPEC_TEMPLATES",
    "ViewMapping",
    "VIEW_MAPPINGS",
    # Adapters (re-exported)
    "ShortcutLifecycleAdapter",
    "FullLifecycleAdapter",
    "create_lifecycle_protocol",
    "get_shared_protocol",
    # BREAK/VULN lifecycle mapping
    "BREAK_VULN_PHASES",
    "phases_for_category",
    "categories_for_phase",
    "lifecycle_finding_from_review",
    "review_finding_from_lifecycle",
    "map_findings_to_phase",
    "PHASE_PRODUCERS",
    "produce_phase_findings",
    "findings_from_junit_xml",
    "findings_from_runtime_evidence",
]
