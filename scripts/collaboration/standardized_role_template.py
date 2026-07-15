#!/usr/bin/env python3
"""
Standardized Role Template (V2) — Agent Skills SKILL.md Anatomy

Aligns with Google Agent Skills SKILL.md structure:
  overview (What) → when_to_use/when_not_to_use (When)
  → process_steps (How) → rationalizations/red_flags (Warnings)
  → verification_requirements (Proof)

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.1
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    triggers: list[str] = field(default_factory=list)
    version: str = "2.0.0"
    author: str = ""
    category: str = "general"
    tags: list[str] = field(default_factory=list)

    # === Context Fields (NEW in V2) ===
    overview: str = ""  # What this template does (1-2 sentences)
    when_to_use: str = ""  # Positive scenarios when to apply
    when_not_to_use: str = ""  # Negative scenarios when NOT to apply

    # === Process Field (Structured steps) ===
    process_steps: list[str] = field(default_factory=list)  # Step-by-step guide

    # === Quality Guardrails (NEW in V2, from P0-1 AntiRationalization) ===
    rationalizations: list[dict[str, str]] = field(default_factory=list)
    # Format: [{"excuse": "...", "reality": "..."}]

    # === Warning Flags (NEW in V2, from P0-2 VerificationGate) ===
    red_flags: list[dict[str, str]] = field(default_factory=list)
    # Format: [{"flag": "...", "severity": "critical/warning", "description": "..."}]

    # === Verification Requirements (NEW in V2) ===
    verification_requirements: list[str] = field(default_factory=list)
    # Format: ["Must have test output", "Build must succeed", ...]

    # === Execution Field ===
    prompt_template: str = ""  # The actual prompt injected into Worker

    # === Metadata (Auto-generated) ===
    template_id: str = field(default="")
    created_at: str = field(default="")
    updated_at: str = field(default="")
    rating: float = 0.0
    install_count: int = 0

    def __post_init__(self) -> None:
        now = datetime.now().isoformat()
        if not self.created_at:
            object.__setattr__(self, "created_at", now)
        if not self.updated_at:
            object.__setattr__(self, "updated_at", now)

        if not self.template_id:
            raw = f"{self.name}:{self.role_id}:{self.author}:{now}"
            tid = f"std-tpl-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
            object.__setattr__(self, "template_id", tid)

    def validate(self) -> list[str]:
        """Validate all required fields. Returns list of error messages."""
        errors = []

        if not self.name or len(self.name) < 2:
            errors.append("name must be at least 2 characters")
        if not self.role_id or len(self.role_id) < 2:
            errors.append("role_id must be at least 2 characters")
        if not self.author:
            errors.append("author is required")

        required_v2_fields = [
            ("overview", "overview is required for V2 templates"),
            ("when_to_use", "when_to_use is required for V2 templates"),
            ("process_steps", "process_steps must have at least 1 step"),
            ("prompt_template", "prompt_template is required"),
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {}
        for key in self.__dataclass_fields__:
            value = getattr(self, key)
            if not key.startswith("_"):
                result[key] = value
        return result

    @classmethod
    def from_legacy(cls, legacy_data: dict[str, Any]) -> "StandardizedRoleTemplate":
        """
        Convert legacy RoleTemplate format to V2 standardized format.

        Legacy format: {name, description, role_id, role_prompt, ...}
        V2 format:     Adds overview, when_to_use, process_steps, etc.
        """
        instance = cls(
            name=legacy_data.get("name", ""),
            description=legacy_data.get("description", ""),
            role_id=legacy_data.get("role_id", ""),
            triggers=legacy_data.get("triggers", []),
            version=legacy_data.get("version", "2.0.0"),
            author=legacy_data.get("author", ""),
            category=legacy_data.get("category", "general"),
            tags=legacy_data.get("tags", []),
            prompt_template=legacy_data.get("role_prompt", legacy_data.get("prompt_template", "")),
            overview=legacy_data.get("description", ""),  # Fallback
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
    def from_dict(cls, data: dict[str, Any]) -> "StandardizedRoleTemplate":
        """Deserialize from dictionary."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys and not k.startswith("_")}
        return cls(**filtered)

    def to_markdown(self) -> str:
        """Generate SKILL.md-style markdown representation."""
        lines = [
            f"# {self.name}",
            "",
            f"> **Version**: {self.version} | **Author**: {self.author} | **Category**: {self.category}",
            "",
            "## Overview",
            "",
            f"{self.overview}",
            "",
            "## When to Use",
            "",
            f"- ✅ {self.when_to_use}",
            f"- ❌ {self.when_not_to_use}",
            "",
        ]

        if self.process_steps:
            lines.extend(
                [
                    "## Process Steps",
                    "",
                ]
            )
            for i, step in enumerate(self.process_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if self.rationalizations:
            lines.extend(
                [
                    "## Common Rationalizations (Anti-Patterns)",
                    "",
                    "| Excuse | Reality |",
                    "|-------|--------|",
                ]
            )
            for r in self.rationalizations:
                lines.append(f"| {r.get('excuse', '')} | {r.get('reality', '')} |")
            lines.append("")

        if self.red_flags:
            lines.extend(
                [
                    "## Red Flags (Warnings)",
                    "",
                ]
            )
            for rf in self.red_flags:
                severity = rf.get("severity", "warning").upper()
                lines.append(f"- ⚠️ [{severity}] {rf.get('description', rf.get('flag', ''))}")
            lines.append("")

        if self.verification_requirements:
            lines.extend(
                [
                    "## Verification Requirements",
                    "",
                ]
            )
            for vr in self.verification_requirements:
                lines.append(f"- [ ] {vr}")
            lines.append("")

        if self.tags:
            lines.extend(
                [
                    f"**Tags**: {', '.join(self.tags)}",
                    "",
                ]
            )

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


# ------------------------------------------------------------------
# Module 9 (Matt P0-6): No-op test + failure modes
# ------------------------------------------------------------------


@dataclass
class NoOpFinding:
    """A single no-op finding from ``apply_no_op_test``.

    A "no-op" line is one that sounds like an instruction but doesn't
    actually change the default behavior of the model or agent.

    Attributes:
        line_number: 1-based line number in the input content.
        line_content: The offending line (stripped).
        reason: Why this line is a no-op.
    """

    line_number: int
    line_content: str
    reason: str


# Patterns that indicate no-op lines. Each entry is (regex, reason).
# Patterns use \b word boundary (not ^) to allow numbered/bullet prefixes.
_NO_OP_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?i)\b(always\s+)?be\s+(helpful|thorough|careful|precise|concise)\b",
        "Tautological virtue — 'be helpful' is the default, not an instruction",
    ),
    (
        r"(?i)\bdo\s+your\s+best\b",
        "'Do your best' is not actionable — specify what 'best' means",
    ),
    (
        r"(?i)\bfollow\s+best\s+practices?\b",
        "'Follow best practices' without specifying which practices is a no-op",
    ),
    (
        r"(?i)\b(remember\s+to\s+)?use\s+(python|javascript|typescript|java|go|rust)\b",
        "Restates language default — the project already uses this language",
    ),
    (
        r"(?i)\b(always\s+)?write\s+(clean|readable|maintainable)\s+code\b",
        "'Write clean code' is a universal aspiration, not an instruction",
    ),
    (
        r"(?i)\btry\s+your\s+hardest\b",
        "'Try your hardest' is not measurable or actionable",
    ),
    (
        r"(?i)\b(always\s+)?be\s+professional\b",
        "'Be professional' is the default expectation, not an instruction",
    ),
    (
        r"(?i)\bmake\s+sure\s+(everything\s+)?works?\b",
        "'Make sure it works' is the goal, not an instruction — specify how",
    ),
]


def apply_no_op_test(skill_content: str) -> list[NoOpFinding]:
    """Run Matt Pocock's no-op test on skill content.

    Scans each line for patterns that sound like instructions but don't
    actually change default behavior. These are "no-ops" — lines that
    waste prompt tokens without adding value.

    Args:
        skill_content: The skill text to analyze (SKILL.md content,
            prompt_template, or any instruction text).

    Returns:
        List of :class:`NoOpFinding` for each no-op line detected.
    """
    if not skill_content:
        return []
    findings: list[NoOpFinding] = []
    for i, line in enumerate(skill_content.split("\n"), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern, reason in _NO_OP_PATTERNS:
            if re.search(pattern, stripped):
                findings.append(
                    NoOpFinding(
                        line_number=i,
                        line_content=stripped,
                        reason=reason,
                    )
                )
                break  # One finding per line is enough.
    return findings


# ------------------------------------------------------------------
# Failure modes (Matt Pocock's writing-great-skills)
# ------------------------------------------------------------------


@dataclass
class FailureModeFinding:
    """A failure mode detected in skill content.

    Matt Pocock identifies 5 failure modes for skills:
    1. premature_completion — skill ends too early, missing steps
    2. duplication — skill repeats content from other skills
    3. sediment — outdated instructions that accumulate over time
    4. sprawl — skill grows too large, loses focus
    5. no_op — instructions that don't change behavior

    Attributes:
        mode: One of "premature_completion", "duplication", "sediment",
            "sprawl", "no_op".
        severity: "high" / "medium" / "low".
        description: Human-readable explanation.
    """

    mode: str
    severity: str
    description: str


def detect_failure_modes(
    skill_content: str,
    *,
    max_lines: int = 200,
    min_steps: int = 3,
) -> list[FailureModeFinding]:
    """Detect Matt Pocock's 5 failure modes in skill content.

    Args:
        skill_content: The skill text to analyze.
        max_lines: Threshold for "sprawl" detection (default 200).
        min_steps: Minimum numbered steps before "premature_completion"
            is checked (default 3).

    Returns:
        List of :class:`FailureModeFinding` for each detected mode.
    """
    findings: list[FailureModeFinding] = []
    if not skill_content or not skill_content.strip():
        return findings

    lines = skill_content.split("\n")

    # 1. Sprawl — too many lines.
    if len(lines) > max_lines:
        findings.append(
            FailureModeFinding(
                mode="sprawl",
                severity="medium",
                description=f"Skill has {len(lines)} lines (threshold: {max_lines}). Consider splitting.",
            )
        )

    # 2. No-op — delegate to apply_no_op_test.
    no_op_findings = apply_no_op_test(skill_content)
    if no_op_findings:
        findings.append(
            FailureModeFinding(
                mode="no_op",
                severity="low",
                description=f"{len(no_op_findings)} no-op line(s) detected (e.g., line {no_op_findings[0].line_number})",
            )
        )

    # 3. Premature completion — too few numbered steps.
    numbered_steps = len(re.findall(r"^\s*\d+\.\s", skill_content, re.MULTILINE))
    if 0 < numbered_steps < min_steps:
        findings.append(
            FailureModeFinding(
                mode="premature_completion",
                severity="high",
                description=f"Only {numbered_steps} numbered step(s) found (minimum: {min_steps}). Skill may end too early.",
            )
        )

    # 4. Sediment — outdated markers.
    sediment_markers = re.findall(r"(?i)\b(TODO|FIXME|DEPRECATED|OUTDATED)\b", skill_content)
    if sediment_markers:
        findings.append(
            FailureModeFinding(
                mode="sediment",
                severity="medium",
                description=f"{len(sediment_markers)} sediment marker(s) found (TODO/FIXME/DEPRECATED/OUTDATED)",
            )
        )

    # 5. Duplication — repeated 3+ word phrases.
    findings.extend(_detect_duplication(skill_content))

    return findings


def _detect_duplication(content: str) -> list[FailureModeFinding]:
    """Detect duplicated 4+ word phrases in skill content."""
    # Extract sentences/phrases of 4+ words.
    words = re.findall(r"[A-Za-z]+", content.lower())
    if len(words) < 8:
        return []
    # Build 4-word phrases and count.
    phrases: dict[str, int] = {}
    for i in range(len(words) - 3):
        phrase = " ".join(words[i : i + 4])
        phrases[phrase] = phrases.get(phrase, 0) + 1
    duplicated = [p for p, c in phrases.items() if c >= 2]
    if duplicated:
        return [
            FailureModeFinding(
                mode="duplication",
                severity="low",
                description=f"{len(duplicated)} duplicated 4-word phrase(s) detected (e.g., '{duplicated[0]}')",
            )
        ]
    return []
