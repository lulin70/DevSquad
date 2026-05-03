#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standardized Role Template (V2) — Agent Skills SKILL.md Anatomy

Aligns with Google Agent Skills SKILL.md structure:
  overview (What) → when_to_use/when_not_to_use (When)
  → process_steps (How) → rationalizations/red_flags (Warnings)
  → verification_requirements (Proof)

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.1
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class StandardizedRoleTemplate:
    """
    Standardized role template following Agent Skills SKILL.md anatomy.

    Structure:
      1. Identity: name, description, role_id, triggers
      2. Context: overview (what), when_to_use (+), when_not_to_use (-)
      3. Process: process_steps (how to execute)
      4. Quality: rationalizations (anti-patterns), red_flags (warnings)
      5. Verification: verification_requirements (proof needed)
      6. Execution: prompt_template (actual LLM prompt)
    """

    # === Identity Fields (Required) ===
    name: str = ""
    description: str = ""
    role_id: str = ""
    triggers: List[str] = field(default_factory=list)
    version: str = "2.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    # === Context Fields (NEW in V2) ===
    overview: str = ""  # What this template does (1-2 sentences)
    when_to_use: str = ""  # Positive scenarios when to apply
    when_not_to_use: str = ""  # Negative scenarios when NOT to apply

    # === Process Field (Structured steps) ===
    process_steps: List[str] = field(default_factory=list)  # Step-by-step guide

    # === Quality Guardrails (NEW in V2, from P0-1 AntiRationalization) ===
    rationalizations: List[Dict[str, str]] = field(default_factory=list)
    # Format: [{"excuse": "...", "reality": "..."}]

    # === Warning Flags (NEW in V2, from P0-2 VerificationGate) ===
    red_flags: List[Dict[str, str]] = field(default_factory=list)
    # Format: [{"flag": "...", "severity": "critical/warning", "description": "..."}]

    # === Verification Requirements (NEW in V2) ===
    verification_requirements: List[str] = field(default_factory=list)
    # Format: ["Must have test output", "Build must succeed", ...]

    # === Execution Field ===
    prompt_template: str = ""  # The actual prompt injected into Worker

    # === Metadata (Auto-generated) ===
    template_id: str = field(default="")
    created_at: str = field(default="")
    updated_at: str = field(default="")
    rating: float = 0.0
    install_count: int = 0

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            object.__setattr__(self, 'created_at', now)
        if not self.updated_at:
            object.__setattr__(self, 'updated_at', now)

        if not self.template_id:
            raw = f"{self.name}:{self.role_id}:{self.author}:{now}"
            tid = f"std-tpl-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
            object.__setattr__(self, 'template_id', tid)

    def validate(self) -> List[str]:
        """Validate all required fields. Returns list of error messages."""
        errors = []

        if not self.name or len(self.name) < 2:
            errors.append("name must be at least 2 characters")
        if not self.role_id or len(self.role_id) < 2:
            errors.append("role_id must be at least 2 characters")
        if not self.author:
            errors.append("author is required")

        required_v2_fields = [
            ('overview', 'overview is required for V2 templates'),
            ('when_to_use', 'when_to_use is required for V2 templates'),
            ('process_steps', 'process_steps must have at least 1 step'),
            ('prompt_template', 'prompt_template is required'),
        ]

        for field_name, error_msg in required_v2_fields:
            value = getattr(self, field_name)
            if isinstance(value, list):
                if len(value) == 0:
                    errors.append(error_msg)
            elif not value:
                errors.append(error_msg)

        return errors

    def is_valid(self) -> bool:
        """Quick validity check."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {}
        for key in self.__dataclass_fields__:
            value = getattr(self, key)
            if not key.startswith('_'):
                result[key] = value
        return result

    @classmethod
    def from_legacy(cls, legacy_data: Dict[str, Any]) -> 'StandardizedRoleTemplate':
        """
        Convert legacy RoleTemplate format to V2 standardized format.

        Legacy format: {name, description, role_id, role_prompt, ...}
        V2 format:     Adds overview, when_to_use, process_steps, etc.
        """
        instance = cls(
            name=legacy_data.get('name', ''),
            description=legacy_data.get('description', ''),
            role_id=legacy_data.get('role_id', ''),
            triggers=legacy_data.get('triggers', []),
            version=legacy_data.get('version', '2.0.0'),
            author=legacy_data.get('author', ''),
            category=legacy_data.get('category', 'general'),
            tags=legacy_data.get('tags', []),
            prompt_template=legacy_data.get('role_prompt', legacy_data.get('prompt_template', '')),
            overview=legacy_data.get('description', ''),  # Fallback
            when_to_use=f"When working on tasks related to {legacy_data.get('category', 'general')}",
            when_not_to_use="When the task does not match this role's expertise",
            process_steps=[
                f"Analyze task requirements as {legacy_data.get('role_id', 'this role')}",
                f"Apply {legacy_data.get('name', 'this')} expertise to the problem",
                "Document findings and recommendations",
            ],
            rationalizations=[],
            red_flags=[],
            verification_requirements=[
                "Output must address the specific task requirements",
                "Recommendations must be actionable and specific",
            ],
        )
        return instance

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StandardizedRoleTemplate':
        """Deserialize from dictionary."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys and not k.startswith('_')}
        return cls(**filtered)

    def to_markdown(self) -> str:
        """Generate SKILL.md-style markdown representation."""
        lines = [
            f"# {self.name}",
            f"",
            f"> **Version**: {self.version} | **Author**: {self.author} | **Category**: {self.category}",
            f"",
            f"## Overview",
            f"",
            f"{self.overview}",
            f"",
            f"## When to Use",
            f"",
            f"- ✅ {self.when_to_use}",
            f"- ❌ {self.when_not_to_use}",
            f"",
        ]

        if self.process_steps:
            lines.extend([
                f"## Process Steps",
                f"",
            ])
            for i, step in enumerate(self.process_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if self.rationalizations:
            lines.extend([
                f"## Common Rationalizations (Anti-Patterns)",
                f"",
                "| Excuse | Reality |",
                "|-------|--------|",
            ])
            for r in self.rationalizations:
                lines.append(f"| {r.get('excuse', '')} | {r.get('reality', '')} |")
            lines.append("")

        if self.red_flags:
            lines.extend([
                f"## Red Flags (Warnings)",
                f"",
            ])
            for rf in self.red_flags:
                severity = rf.get('severity', 'warning').upper()
                lines.append(f"- ⚠️ [{severity}] {rf.get('description', rf.get('flag', ''))}")
            lines.append("")

        if self.verification_requirements:
            lines.extend([
                f"## Verification Requirements",
                f"",
            ])
            for vr in self.verification_requirements:
                lines.append(f"- [ ] {vr}")
            lines.append("")

        if self.tags:
            lines.extend([
                f"**Tags**: {', '.join(self.tags)}",
                f"",
            ])

        return "\n".join(lines)


def create_example_template() -> StandardizedRoleTemplate:
    """Create an example standardized template for testing/documentation."""
    return StandardizedRoleTemplate(
        name="OWASP Security Auditor",
        description="Security auditor with OWASP Top 10 focus",
        role_id="security",
        triggers=["security", "vulnerability", "audit", "OWASP"],
        version="2.0.0",
        author="DevSquad Team",
        category="security",
        tags=["owasp", "audit", "compliance", "web-security"],
        overview=(
            "Performs systematic security review following OWASP Top 10 guidelines. "
            "Identifies vulnerabilities, assesses risk levels, and provides remediation guidance."
        ),
        when_to_use=(
            "When reviewing code for security vulnerabilities, "
            "conducting security audits, or assessing compliance with OWASP standards"
        ),
        when_not_to_use=(
            "When the task is purely functional (no security implications), "
            "or when a quick syntax check is sufficient without deep analysis"
        ),
        process_steps=[
            "Map application components to OWASP categories (A01-A10)",
            "Review each component against relevant OWASP checks",
            "Document findings with severity (Critical/High/Medium/Low)",
            "Provide specific remediation code examples",
            "Summarize risk assessment and recommend priorities",
        ],
        rationalizations=[
            {
                "excuse": "This is internal tool, no need for full audit",
                "reality": "Internal tools often face production exposure. Audit thoroughly.",
            },
            {
                "excuse": "No known vulnerabilities in this codebase",
                "reality": "Unknown vulnerabilities are the most dangerous. Systematic review finds hidden issues.",
            },
            {
                "excuse": "Security review will slow down delivery",
                "reality": "Security debt compounds faster than technical debt. Early review prevents costly rewrites.",
            },
        ],
        red_flags=[
            {
                "flag": "no_input_validation",
                "severity": "critical",
                "description": "User input not validated/sanitized before processing",
            },
            {
                "flag": "hardcoded_secrets",
                "severity": "critical",
                "description": "API keys, passwords, or tokens found in source code",
            },
            {
                "flag": "sql_injection_risk",
                "severity": "critical",
                "description": "Dynamic SQL queries without parameterized statements",
            },
            {
                "flag": "no_authentication_check",
                "severity": "warning",
                "description": "Endpoint lacks authentication verification",
            },
        ],
        verification_requirements=[
            "All OWASP A01-A10 categories reviewed",
            "Each finding has severity classification",
            "Remediation examples provided for Critical/High findings",
            "Summary report includes risk score",
        ],
        prompt_template=(
            "You are an OWASP Security Auditor. Follow these instructions:\n\n"
            "1. Review the provided code against OWASP Top 10\n"
            "2. For each vulnerability found:\n"
            "   - Classify severity (Critical/High/Medium/Low)\n"
            "   - Provide CVE/CWE reference if applicable\n"
            "   - Show vulnerable code and fixed code\n"
            "3. Output structured report with findings table\n\n"
            "Remember: Security is never 'good enough'. Be thorough."
        ),
    )
