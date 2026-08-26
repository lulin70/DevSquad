#!/usr/bin/env python3
"""Role-Specific Mock Backend (V4.3.2).

An independent Mock backend that produces role-specific mock output.
Unlike the generic MockBackend, this produces differentiated content
per role (architect/security/tester/coder/devops/pm/ui) when
``role_specific=True``. When ``role_specific=False`` (default), it
behaves identically to MockBackend for backward compatibility.

This module does NOT modify the existing MockBackend — it is a new,
independent class used as the second arm in the three-arm comparison
(frozen_mock vs role_specific_mock vs llm).

Usage:
    from scripts.collaboration.role_specific_mock_backend import RoleSpecificMockBackend

    # Compatible mode (same as MockBackend)
    backend = RoleSpecificMockBackend(role_specific=False)

    # Role-specific mode
    backend = RoleSpecificMockBackend(role_specific=True)
    output = backend.generate("design auth", role_name="Architect")
"""

from typing import Any

from .llm_backend import MOCK_SEPARATOR_WIDTH, LLMBackend

# Anti-phantom-feature counter
_call_counter_er: int = 0

# Role-specific template fragments (appended to base mock output)
_ROLE_TEMPLATES: dict[str, str] = {
    "architect": (
        "## Architecture Analysis\n"
        "- Component decomposition: identify bounded contexts\n"
        "- Data flow: request → controller → service → repository\n"
        "- Tech selection: prefer stdlib > installed dep > new dep\n"
        "- NFRs: scalability, availability, latency budget\n"
    ),
    "product-manager": (
        "## Product Requirements\n"
        "- User story: As a <role>, I want <action>, so that <value>\n"
        "- Acceptance criteria: GIVEN/WHEN/THEN format\n"
        "- Priority: MoSCoW (Must/Should/Could/Won't)\n"
        "- Success metric: activation rate, retention, NPS\n"
    ),
    "security": (
        "## Security Review\n"
        "- Threat model: STRIDE (Spoofing/Tampering/Repudiation/Info/DoS/Elevation)\n"
        "- OWASP Top 10 check: injection, broken auth, XSS, CSRF\n"
        "- Secrets: no hardcoded keys, use env vars / vault\n"
        "- Input validation: whitelist > blacklist, parameterized queries\n"
    ),
    "tester": (
        "## Test Strategy\n"
        "- Test pyramid: unit ≥70% / integration ≥20% / e2e ≤10%\n"
        "- Coverage targets: line ≥85%, branch ≥75%\n"
        "- Dimension coverage: Happy/Error/Boundary/Performance/Config\n"
        "- Anti-patterns: no assertTrue bypass, no bare except\n"
    ),
    "solo-coder": (
        "## Implementation Plan\n"
        "- Approach: TDD red-green-refactor\n"
        "- Structure: extract helpers for complexity < C(20)\n"
        "- Error handling: specific exceptions, no bare except\n"
        "- Dependencies: check stdlib first, then installed, then new\n"
    ),
    "devops": (
        "## DevOps Plan\n"
        "- CI pipeline: lint → test → build → deploy\n"
        "- Container: multi-stage build, distroless base\n"
        "- Monitoring: P95/P99 latency, error rate, saturation\n"
        "- Rollback: blue-green or canary, auto-rollback on SLO breach\n"
    ),
    "ui-designer": (
        "## UI/UX Design\n"
        "- Layout: 4pt grid, consistent spacing scale\n"
        "- Color: OKLCH space, 3:1 contrast for data series\n"
        "- Interaction: affordance > instruction, feedback <100ms\n"
        "- Accessibility: WCAG AA, keyboard nav, screen reader\n"
    ),
}


class RoleSpecificMockBackend(LLMBackend):
    """Mock backend with optional role-specific template differentiation.

    When ``role_specific=False`` (default), output is identical to
    :class:`MockBackend`. When ``role_specific=True``, a role-specific
    template fragment is appended to the base mock output.

    This class does NOT inherit from or modify :class:`MockBackend`.
    """

    def __init__(self, role_specific: bool = False) -> None:
        """Initialize the backend.

        Args:
            role_specific: If True, append role-specific template to output.
                If False, behave identically to MockBackend.
        """
        self.role_specific = role_specific

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a mock response, optionally role-specific.

        Args:
            prompt: User prompt text.
            **kwargs: ``role_name`` and ``task_description`` for the mock header.

        Returns:
            Multi-line mock analysis string. When ``role_specific=True``
            and ``role_name`` matches a known role, a role-specific
            template fragment is appended.
        """
        global _call_counter_er
        _call_counter_er += 1

        role_name = kwargs.get("role_name", "AI Assistant")
        task_desc = kwargs.get("task_description", "")
        lines = [
            f"[MOCK MODE] {role_name} Analysis",
            "=" * MOCK_SEPARATOR_WIDTH,
            "",
            f"Task: {task_desc}" if task_desc else "Task: (auto-detected)",
            "",
            "This is a mock response. To get real AI analysis,",
            "set --backend openai (or anthropic) with a valid API key.",
            "",
            f"Prompt length: {len(prompt)} chars",
        ]

        if self.role_specific:
            # Normalize role name for lookup
            role_key = role_name.lower().replace(" ", "-")
            template = _ROLE_TEMPLATES.get(role_key)
            if template is None:
                # Try partial match
                for key, tmpl in _ROLE_TEMPLATES.items():
                    if key in role_key or role_key in key:
                        template = tmpl
                        break
            if template:
                lines.append("")
                lines.append(template)

        return "\n".join(lines)

    def is_available(self) -> bool:
        """Check whether this backend is available.

        Returns:
            Always True; the mock backend requires no external dependencies.
        """
        return True
