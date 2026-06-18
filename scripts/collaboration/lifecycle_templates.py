#!/usr/bin/env python3
"""
Lifecycle Templates - 11-phase 模板定义

包含:
  - SpecTemplate: 规范文档模板数据类
  - SPEC_TEMPLATES: 预定义规范模板 (requirements/architecture/technical)
  - ViewMapping: CLI 命令 → 11-phase 映射数据类
  - VIEW_MAPPINGS: 预定义 CLI 命令到阶段的映射 (spec/plan/build/test/review/ship)

从 lifecycle_protocol.py 拆分而来，lifecycle_protocol.py 会 re-export 以保持向后兼容。

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

from dataclasses import dataclass, field
from typing import Any

from .lifecycle_protocol import LifecycleMode


@dataclass
class ViewMapping:
    """Maps a CLI command to underlying 11-phase segments."""

    command: str
    phases: list[str]  # Phase IDs this command covers
    mode: LifecycleMode = LifecycleMode.SHORTCUT
    description: str = ""
    required_roles: list[str] = field(default_factory=list)
    gate: str = ""
    pre_dispatch_message: str = ""

    def covers_phase(self, phase_id: str) -> bool:
        """Check whether this command template covers a given phase.

        Args:
            phase_id: Identifier of the phase to check.

        Returns:
            True if the phase is in this command's phase list, False otherwise.
        """
        return phase_id in self.phases


@dataclass
class SpecTemplate:
    """Specification document template."""

    template_id: str
    name: str
    phase_id: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    validation_rules: list[dict[str, Any]] = field(default_factory=list)


SPEC_TEMPLATES: dict[str, SpecTemplate] = {
    "requirements": SpecTemplate(
        template_id="requirements",
        name="Requirements Specification",
        phase_id="P1",
        sections=[
            {"title": "Objectives", "description": "Project goals and success criteria"},
            {"title": "User Stories", "description": "User stories with acceptance criteria"},
            {"title": "Non-Functional Requirements", "description": "Performance, security, scalability"},
            {"title": "Constraints", "description": "Technical and business constraints"},
            {"title": "Boundaries", "description": "In-scope and out-of-scope items"},
        ],
        required_fields=["objectives", "user_stories"],
        validation_rules=[
            {"field": "objectives", "check": "not_empty", "severity": "critical"},
            {"field": "user_stories", "check": "min_count", "value": 1, "severity": "critical"},
        ],
    ),
    "architecture": SpecTemplate(
        template_id="architecture",
        name="Architecture Specification",
        phase_id="P2",
        sections=[
            {"title": "System Overview", "description": "High-level architecture diagram"},
            {"title": "Tech Stack", "description": "Technology selection and rationale"},
            {"title": "Service Boundaries", "description": "Module/service decomposition"},
            {"title": "Quality Attributes", "description": "Performance, security, reliability targets"},
        ],
        required_fields=["system_overview", "tech_stack"],
        validation_rules=[
            {"field": "tech_stack", "check": "not_empty", "severity": "critical"},
        ],
    ),
    "technical": SpecTemplate(
        template_id="technical",
        name="Technical Specification",
        phase_id="P3",
        sections=[
            {"title": "API Specifications", "description": "Endpoint definitions"},
            {"title": "Interface Definitions", "description": "Internal interfaces"},
            {"title": "Data Models", "description": "Schema definitions"},
            {"title": "Error Handling", "description": "Error codes and recovery"},
        ],
        required_fields=["api_specifications"],
        validation_rules=[
            {"field": "api_specifications", "check": "not_empty", "severity": "critical"},
        ],
    ),
}


# Predefined view mappings (CLI → 11 phases)
VIEW_MAPPINGS: dict[str, ViewMapping] = {
    "spec": ViewMapping(
        command="spec",
        phases=["P1", "P2"],
        description="Define requirements and architecture before implementation",
        required_roles=["architect", "product-manager"],
        gate="spec_first",
        pre_dispatch_message=(
            "📋 Generating specification (P1: Requirements + P2: Architecture). "
            "Output will include objectives, structure, testing plan, and boundaries."
        ),
    ),
    "plan": ViewMapping(
        command="plan",
        phases=["P7"],
        description="Break down work into verifiable tasks and test plans",
        required_roles=["architect", "product-manager"],
        gate="task_breakdown_complete",
        pre_dispatch_message=(
            "📝 Decomposing into atomic tasks (P7: Test Planning). Output includes test plan with acceptance criteria."
        ),
    ),
    "build": ViewMapping(
        command="build",
        phases=["P8"],
        description="Implement incrementally with TDD discipline",
        required_roles=["architect", "solo-coder", "tester"],
        gate="incremental_verification",
        pre_dispatch_message=(
            "🔨 Building in thin vertical slices (P8: Implementation). "
            "Each slice: implement → test → verify. ~100 lines per slice max."
        ),
    ),
    "test": ViewMapping(
        command="test",
        phases=["P9"],
        description="Run tests with mandatory evidence requirements",
        required_roles=["tester", "solo-coder"],
        gate="evidence_required",
        pre_dispatch_message=(
            "🧪 Running tests with verification gate (P9: Test Execution). "
            "Evidence required: test output, build status, diff summary."
        ),
    ),
    "review": ViewMapping(
        command="review",
        phases=["P8_review_embedded", "P6_partial"],
        description="Five-axis code review and security checks",
        required_roles=["solo-coder", "security", "tester", "architect"],
        gate="change_size_limit",
        pre_dispatch_message=(
            "🔍 Conducting multi-dimensional review. "
            "Change size target: ~100 lines. Severity labels: Critical/Required/Nit."
        ),
    ),
    "ship": ViewMapping(
        command="ship",
        phases=["P10"],
        description="Pre-launch verification and deployment preparation",
        required_roles=["devops", "security", "architect"],
        gate="pre_launch_checklist",
        pre_dispatch_message=("🚀 Running pre-launch checklist across 6 dimensions. Rollback plan required."),
    ),
    "spec-init": ViewMapping(
        command="spec-init",
        phases=["P1"],
        description="Initialize specification document from template",
        required_roles=["architect", "product-manager"],
        gate="spec_template_complete",
        pre_dispatch_message=(
            "📋 Initializing specification document from template. "
            "Choose template: requirements / architecture / technical."
        ),
    ),
    "spec-analyze": ViewMapping(
        command="spec-analyze",
        phases=["P1", "P2"],
        description="Analyze existing codebase to generate specification draft",
        required_roles=["architect"],
        gate="code_analysis_complete",
        pre_dispatch_message=(
            "🔍 Analyzing codebase structure to generate specification draft. "
            "Uses CodeMapGenerator for multi-language analysis."
        ),
    ),
    "spec-validate": ViewMapping(
        command="spec-validate",
        phases=["P1", "P2", "P3"],
        description="Validate specification completeness and consistency",
        required_roles=["architect", "tester"],
        gate="spec_validation_passed",
        pre_dispatch_message=(
            "✅ Validating specification against completeness rules. Checks required fields, consistency, and coverage."
        ),
    ),
}
