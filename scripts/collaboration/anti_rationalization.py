#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AntiRationalizationEngine - Per-role "excuse -> rebuttal" table system

Prevents Workers from skipping critical steps by injecting pre-written
anti-rationalization pairs into role prompts.

Design borrowed from Agent Skills (addyosmani/agent-skills):
  - Each role has domain-specific rationalizations (AI excuses)
  - Universal rationalizations apply to all roles
  - Format: table of (excuse, reality) pairs injected as markdown

Integration point: Called by PromptAssembler._build_instruction()
to inject anti-rationalization content into each Worker's system prompt.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RationalizationRow:
    """Single excuse-reality pair for anti-rationalization."""
    excuse: str
    reality: str


class AntiRationalizationEngine:
    """
    Stores and retrieves anti-rationalization tables per role.

    Universal table applies to ALL roles. Role-specific tables
    are merged on top. Total: 8 universal + 42 role-specific = 50 entries.
    """

    _UNIVERSAL_TABLE: List[RationalizationRow] = [
        RationalizationRow(
            excuse="This is a small change, no need for full process",
            reality="Small changes compound. Skip quality steps now, pay debt later",
        ),
        RationalizationRow(
            excuse="I'll clean this up later",
            reality="Later never comes. Clean now or file explicit tech debt",
        ),
        RationalizationRow(
            excuse="The user didn't ask for this specifically",
            reality="Professional quality is implicit. Deliver excellence always",
        ),
        RationalizationRow(
            excuse="This is already good enough",
            reality="'Good enough' is the enemy of great. Iterate until excellent",
        ),
        RationalizationRow(
            excuse="Nobody will notice this detail",
            reality="Details compound. 10 unnoticed issues = degraded experience",
        ),
        RationalizationRow(
            excuse="This is just a quick fix",
            reality="Quick fixes become permanent code. Do it right or track as debt",
        ),
        RationalizationRow(
            excuse="The existing code already does this poorly",
            reality="Two wrongs don't make a right. Fix properly or document the gap",
        ),
        RationalizationRow(
            excuse="Refactoring can wait until later",
            reality="If you don't refactor now while you understand it, you never will",
        ),
    ]

    _ROLE_SPECIFIC_TABLES: Dict[str, List[RationalizationRow]] = {
        "architect": [
            RationalizationRow(
                excuse="This architecture is good enough",
                reality=(
                    "'Good enough' without peer review hides technical debt "
                    "that compounds exponentially"
                ),
            ),
            RationalizationRow(
                excuse="I'll optimize performance later",
                reality=(
                    "Architecture decisions lock in performance characteristics. "
                    "Optimize now or document explicit trade-off"
                ),
            ),
            RationalizationRow(
                excuse="Over-engineering shows thoroughness",
                reality=(
                    "YAGNI (You Aren't Gonna Need It). Solve the actual problem, "
                    "not hypothetical futures"
                ),
            ),
            RationalizationRow(
                excuse="The current design handles our needs",
                reality=(
                    "Design for the next 2x scale, not just today's load. "
                    "Future-you will thank present-you"
                ),
            ),
            RationalizationRow(
                excuse="This pattern is standard in the industry",
                reality=(
                    "Standard doesn't mean optimal. Evaluate if this pattern fits "
                    "our specific constraints"
                ),
            ),
            RationalizationRow(
                excuse="Adding abstraction improves flexibility",
                reality=(
                    "Every abstraction adds complexity. Don't generalize until "
                    "the third use case demands it"
                ),
            ),
        ],
        "product-manager": [
            RationalizationRow(
                excuse="Requirements are clear enough from context",
                reality=(
                    "Ambiguous requirements cause 70% of project failures. "
                    "Write explicit acceptance criteria"
                ),
            ),
            RationalizationRow(
                excuse="User will tell us if we got it wrong",
                reality=(
                    "Late discovery costs 100x early validation. "
                    "Clarify assumptions upfront"
                ),
            ),
            RationalizationRow(
                excuse="We can iterate on the spec",
                reality=(
                    "Iteration without a baseline wastes effort. "
                    "Establish the baseline first"
                ),
            ),
            RationalizationRow(
                excuse="Edge cases can be handled later",
                reality=(
                    "Edge cases are where production systems fail. "
                    "Define them in acceptance criteria"
                ),
            ),
            RationalizationRow(
                excuse="The competitor does it this way",
                reality=(
                    "Competitor decisions reflect their constraints, not ours. "
                    "Evaluate independently"
                ),
            ),
        ],
        "security": [
            RationalizationRow(
                excuse="This is an internal tool, security doesn't matter",
                reality=(
                    "Internal tools get compromised. Attackers target the weakest link. "
                    "Security habits apply everywhere"
                ),
            ),
            RationalizationRow(
                excuse="We'll add security later",
                reality=(
                    "Security retrofitting is 10x harder than building it in. "
                    "Add it now"
                ),
            ),
            RationalizationRow(
                excuse="No one would try to exploit this",
                reality=(
                    "Automated scanners find everything. "
                    "Security by obscurity is not security"
                ),
            ),
            RationalizationRow(
                excuse="The framework handles security",
                reality=(
                    "Frameworks provide tools, not guarantees. "
                    "You must use them correctly"
                ),
            ),
            RationalizationRow(
                excuse="It's just a prototype",
                reality=(
                    "Prototypes become production code. "
                    "Security habits from day one prevent 'test debt'"
                ),
            ),
            RationalizationRow(
                excuse="Authentication is out of scope",
                reality=(
                    "Auth is the foundation of security. "
                    "Define auth requirements even if implementation is deferred"
                ),
            ),
        ],
        "tester": [
            RationalizationRow(
                excuse="I'll write tests after the code works",
                reality="You won't. Post-hoc tests test implementation, not behavior",
            ),
            RationalizationRow(
                excuse="This is too simple to test",
                reality="Simple code gets complicated. Tests document expected behavior",
            ),
            RationalizationRow(
                excuse="Tests slow me down",
                reality="Tests slow you NOW. They speed every future change",
            ),
            RationalizationRow(
                excuse="I tested it manually",
                reality=(
                    "Manual testing doesn't persist. Tomorrow's change breaks it silently"
                ),
            ),
            RationalizationRow(
                excuse="The code is self-explanatory",
                reality="Tests ARE the specification. They define what code SHOULD do",
            ),
            RationalizationRow(
                excuse="It's just a prototype",
                reality=(
                    "Prototypes become production. Tests from day one prevent crisis"
                ),
            ),
            RationalizationRow(
                excuse="Mocking is too much overhead",
                reality=(
                    "Without mocks you test framework behavior, not your logic. "
                    "Use the simplest double that proves your point"
                ),
            ),
        ],
        "solo-coder": [
            RationalizationRow(
                excuse="It works, that's good enough",
                reality=(
                    "Working but unreadable/insecure/architecturally wrong code "
                    "creates compound technical debt"
                ),
            ),
            RationalizationRow(
                excuse="I wrote it, so I know it's correct",
                reality=(
                    "Authors are blind to their own assumptions. "
                    "Every change benefits from another perspective"
                ),
            ),
            RationalizationRow(
                excuse="AI-generated code is probably fine",
                reality=(
                    "AI code needs MORE scrutiny, not less. "
                    "It's confident and plausible, even when wrong. "
                    "This is the most dangerous rationalization in multi-AI systems"
                ),
            ),
            RationalizationRow(
                excuse="The tests pass, so it's good",
                reality=(
                    "Tests are necessary but insufficient. "
                    "They don't catch architecture, security, or readability issues"
                ),
            ),
            RationalizationRow(
                excuse="We'll clean it up later",
                reality=(
                    "Later never comes. The review IS the quality gate — use it now"
                ),
            ),
            RationalizationRow(
                excuse="Fewer lines is simpler",
                reality=(
                    "A 1-line nested ternary is NOT simpler than 5-line if/else. "
                    "Simplicity = comprehension speed, not line count"
                ),
            ),
            RationalizationRow(
                excuse="This follows established patterns",
                reality=(
                    "Following patterns blindly leads to over-engineering. "
                    "Evaluate whether each pattern serves THIS specific need"
                ),
            ),
        ],
        "devops": [
            RationalizationRow(
                excuse="CI is too slow, let's skip it",
                reality=(
                    "Optimize pipeline, don't skip it. 5-min pipeline prevents hours debugging"
                ),
            ),
            RationalizationRow(
                excuse="This change is trivial, no need for full pipeline",
                reality=(
                    "Trivial changes break builds. CI catches what humans miss, consistently"
                ),
            ),
            RationalizationRow(
                excuse="We'll add CI later",
                reality=(
                    "Projects without CI accumulate broken states. Day one setup"
                ),
            ),
            RationalizationRow(
                excuse="The test is flaky, just re-run",
                reality=(
                    "Flaky tests mask real bugs and waste everyone's time. "
                    "Fix the flakiness"
                ),
            ),
            RationalizationRow(
                excuse="Manual testing is enough",
                reality=(
                    "Manual testing doesn't scale and isn't repeatable. Automate what you can"
                ),
            ),
        ],
        "ui-designer": [
            RationalizationRow(
                excuse="It looks fine on my screen",
                reality=(
                    "Test on real devices, screen readers, and slow networks. "
                    "'Fine on my screen' excludes most users"
                ),
            ),
            RationalizationRow(
                excuse="Accessibility can wait",
                reality=(
                    "Retrofitting accessibility is 10x harder than building it in. "
                    "WCAG 2.1 AA from day one"
                ),
            ),
            RationalizationRow(
                excuse="Users won't notice this detail",
                reality=(
                    "Details compound. 10 'unnoticeable' issues = unusable product"
                ),
            ),
            RationalizationRow(
                excuse="The design matches the mockup",
                reality=(
                    "Mockups don't show edge cases, error states, or loading scenarios. "
                    "Design for all states"
                ),
            ),
            RationalizationRow(
                excuse="This animation enhances UX",
                reality=(
                    "Unnecessary animations distract and hurt performance. "
                    "Every animation must serve a functional purpose"
                ),
            ),
        ],
    }

    def __init__(self, max_entries_per_role: int = 0):
        """
        Initialize engine.

        Args:
            max_entries_per_role: Max entries to include per role (0 = all).
                                 Useful for token budget control.
        """
        self._max_entries = max_entries_per_role
        self._cache: Dict[str, str] = {}
        self._MAX_CACHE_SIZE = 64

    def get_table(self, role_id: str) -> List[RationalizationRow]:
        """
        Get combined universal + role-specific anti-rationalization table.

        Args:
            role_id: Role identifier (e.g., 'architect', 'solo-coder')

        Returns:
            Combined list of RationalizationRow entries
        """
        specific = self._ROLE_SPECIFIC_TABLES.get(role_id, [])
        combined = self._UNIVERSAL_TABLE + specific
        if self._max_entries > 0:
            return combined[: self._max_entries]
        return combined

    def get_table_size(self, role_id: str) -> int:
        """Return number of entries for a given role."""
        return len(self.get_table(role_id))

    def format_for_prompt(self, role_id: str) -> str:
        """
        Format anti-rationalization table as markdown for prompt injection.

        Args:
            role_id: Role identifier

        Returns:
            Formatted markdown string ready for prompt injection,
            or empty string if no entries found
        """
        cache_key = f"{role_id}_{self._max_entries}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        rows = self.get_table(role_id)
        if not rows:
            return ""

        lines = [
            "\n## Quality Guardrails\n",
            (
                "The following thoughts are **incorrect** and must be ignored. "
                "If you catch yourself thinking any left-column thought, "
                "stop and follow the right-column guidance instead.\n"
            ),
            "| Excuse (DO NOT think this) | Reality (follow this instead) |",
            "|---|---|",
        ]
        for row in rows:
            escaped_excuse = row.excuse.replace("|", "\\|")
            escaped_reality = row.reality.replace("|", "\\|")
            lines.append(f"| {escaped_excuse} | {escaped_reality} |")

        lines.append("\n**Rule**: Quality guardrails are non-negotiable.\n")
        result = "\n".join(lines)
        if len(self._cache) >= self._MAX_CACHE_SIZE:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = result
        return result

    def has_role(self, role_id: str) -> bool:
        """Check if a role has any specific entries."""
        return role_id in self._ROLE_SPECIFIC_TABLES

    def list_all_roles(self) -> List[str]:
        """Return all roles with specific tables."""
        return sorted(self._ROLE_SPECIFIC_TABLES.keys())

    @property
    def universal_count(self) -> int:
        """Number of universal entries."""
        return len(self._UNIVERSAL_TABLE)

    @property
    def total_entries(self) -> int:
        """Total entries across all roles (union of universal + max specific)."""
        max_specific = max(
            len(v) for v in self._ROLE_SPECIFIC_TABLES.values()
        ) if self._ROLE_SPECIFIC_TABLES else 0
        return len(self._UNIVERSAL_TABLE) + max_specific


def get_shared_engine(max_entries_per_role: int = 0) -> AntiRationalizationEngine:
    """
    Get or create shared singleton instance.

    Args:
        max_entries_per_role: Max entries per role (0 = all)

    Returns:
        Shared AntiRationalizationEngine instance
    """
    if not hasattr(get_shared_engine, "_instance"):
        get_shared_engine._instance = AntiRationalizationEngine(
            max_entries_per_role=max_entries_per_role
        )
    return get_shared_engine._instance
