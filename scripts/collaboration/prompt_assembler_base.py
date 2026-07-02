"""Shared base for PromptAssembler and its mixins.

Declares the :class:`TaskComplexity` enum, :class:`AssembledPrompt`
dataclass, and the :class:`PromptAssemblerBase` structural class so that
the split PromptAssembler mixins can be type-checked by mypy without
heavy casts or ``# type: ignore`` comments.

Public symbols (``TaskComplexity``, ``AssembledPrompt``) are re-exported
by :mod:`scripts.collaboration.prompt_assembler` for backward
compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskComplexity(Enum):
    """Task complexity level"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class AssembledPrompt:
    """
    Assembled prompt result

    Attributes:
        instruction: Final work instruction text
        complexity: Detected task complexity
        variant_used: Name of the template variant used
        tokens_estimate: Estimated token count
        metadata: Additional metadata (e.g., triggered keywords, trimming reasons)
    """

    instruction: str
    complexity: TaskComplexity
    variant_used: str
    tokens_estimate: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptAssemblerBase:
    """Structural base for PromptAssembler mixins.

    Attributes are declared as class-level annotations; concrete values are
    assigned by ``PromptAssembler.__init__``. Method stubs are provided so
    that cross-mixin calls can be type-checked; concrete implementations
    live in the individual mixins.
    """

    # Instance state assigned by PromptAssembler.__init__
    role_id: str
    base_prompt: str
    qc_config: dict
    qc_enabled: bool
    _qc_injection: str
    _ponytail_injection: str

    # Lazily-initialized collaborators (set by substitution mixin methods)
    _rule_storage: Any
    _skill_loader: Any
    _ar_engine: Any

    # --- Method stubs implemented by mixins ---

    def detect_complexity(self, task_description: str) -> TaskComplexity:
        """Return detected task complexity (implemented by validation mixin)."""
        raise NotImplementedError

    def _load_config(self, config_path: str | None = None) -> dict:
        """Load DevSquad configuration (implemented by template mixin)."""
        raise NotImplementedError

    def _build_quality_control_injection(self) -> str:
        """Build QC injection text (implemented by formatting mixin)."""
        raise NotImplementedError

    def _build_instruction(
        self,
        style: str,
        task_id: str,
        task_description: str,
        role_display: str,
        findings: list[str],
        include_constraints: bool,
        include_anti_patterns: bool,
        dial_fragment: str = "",
        code_graph_hints: list[dict[str, Any]] | None = None,
    ) -> str:
        """Assemble instruction text (implemented by formatting mixin)."""
        raise NotImplementedError

    def _get_user_rules_injection(self, task_description: str) -> str:
        """Query user rules (implemented by substitution mixin)."""
        raise NotImplementedError

    def _get_role_anti_patterns(self) -> list[str]:
        """Return role anti-patterns (implemented by substitution mixin)."""
        raise NotImplementedError

    def _get_skill_injection(self) -> str:
        """Inject methodology skills (implemented by substitution mixin)."""
        raise NotImplementedError

    def _get_anti_rationalization_injection(self) -> str:
        """Inject anti-rationalization content (implemented by substitution mixin)."""
        raise NotImplementedError

    def _get_ponytail_injection(self) -> str:
        """Return ponytail minimal-implementation injection text.

        Returns the pre-built ``_ponytail_injection`` string (may be empty
        if ``quality_control.minimal_implementation`` is disabled).
        """
        return getattr(self, "_ponytail_injection", "")

    def _get_learned_rules_injection(self) -> str:
        """Return learned-rules injection text (V3.10.0 Phase 4).

        Returns the pre-built ``_learned_rules_injection`` string (may be
        empty when no tier-1 learned rules are configured).
        """
        return getattr(self, "_learned_rules_injection", "")
