#!/usr/bin/env python3
"""
PromptAssembler - Dynamic Prompt Assembly Engine

Inspired by three prompt optimization mechanisms in the Claude Code architecture:

  Inspired① Feature Flag-driven dynamic trimming:
    Automatically select template variants with different verbosity levels
    based on task complexity (Simple/Medium/Complex).
    Simple tasks use 3-line concise instructions; complex tasks use enhanced
    templates (+constraints +anti-patterns +references).

  Inspired③ Compression-aware adaptation:
    ContextCompressor's compression level (NONE/SNIP/SESSION_MEMORY/FULL_COMPACT)
    directly influences the prompt's style and detail level, achieving
    "more compression, more concise" self-adaptation.

Design principles:
    - No new standalone service; embedded as an assembler within Worker._do_work()
    - All variants derived from ROLE_TEMPLATES (original templates unchanged)
    - Fully automatic complexity detection (based on description length/keywords/structural signals)

Implementation notes:
    - This module is a facade. The class body keeps only ``__init__`` and the
      core ``assemble()`` orchestration method.
    - Auxiliary concerns are split into single-responsibility mixins under
      ``prompt_assembler_*_mixin.py`` and the shared structural base in
      ``prompt_assembler_base.py`` (same package).
    - Public API (``PromptAssembler``, ``AssembledPrompt``, ``TaskComplexity``)
      remains importable from this module for backward compatibility.
"""

from __future__ import annotations

from typing import Any, cast

from .prompt_assembler_base import AssembledPrompt, TaskComplexity
from .prompt_assembler_formatting_mixin import PromptAssemblerFormattingMixin
from .prompt_assembler_substitution_mixin import PromptAssemblerSubstitutionMixin
from .prompt_assembler_template_mixin import PromptAssemblerTemplateMixin
from .prompt_assembler_validation_mixin import PromptAssemblerValidationMixin

# Re-export public API symbols for backward compatibility.
# ``AssembledPrompt`` and ``TaskComplexity`` are imported above and intentionally
# re-exported so that ``from .prompt_assembler import AssembledPrompt`` keeps
# working after the split.
__all__ = ["PromptAssembler", "AssembledPrompt", "TaskComplexity"]


class PromptAssembler(
    PromptAssemblerTemplateMixin,
    PromptAssemblerSubstitutionMixin,
    PromptAssemblerFormattingMixin,
    PromptAssemblerValidationMixin,
):
    """
    Dynamic prompt assembler

    Core flow:
        task_description → detect_complexity() → select_template()
            → assemble(related_findings) → AssembledPrompt

    Relationship with existing components:
    - Worker._do_work(): Caller, passes context and gets AssembledPrompt
    - ROLE_TEMPLATES: Variant baseline source (defined in dispatcher.py)
    - ContextCompressor.CompressionLevel: Compression-aware input (optional)

    Usage example:
        assembler = PromptAssembler(role_id="architect", base_prompt=role_template)
        result = assembler.assemble(task_description="Design microservice architecture",
                                    related_findings=["Finding A"],
                                    compression_level=CompressionLevel.NONE)
        print(result.instruction)
    """

    def __init__(self, role_id: str, base_prompt: str, config_path: str | None = None):
        """
        Initialize the prompt assembler

        Args:
            role_id: Role identifier (for role-specific trimming strategies)
            base_prompt: Base role prompt template (from ROLE_TEMPLATES)
            config_path: Configuration file path (optional, defaults to searching for .devsquad.yaml)
        """
        self.role_id = role_id
        self.base_prompt = base_prompt

        self.qc_config = self._load_config(config_path)
        self.qc_enabled = self.qc_config.get("quality_control", {}).get("enabled", False)

        self._qc_injection = ""
        if self.qc_enabled:
            self._qc_injection = self._build_quality_control_injection()

        from .ponytail_rule_injector import PonytailRuleInjector

        self._ponytail_injector = PonytailRuleInjector(self.qc_config)
        self._ponytail_injection = self._ponytail_injector.build_injection()

    def assemble(
        self,
        task_description: str,
        related_findings: list[str] | None = None,
        task_id: str = "",
        compression_level: Any = None,
        dials: Any = None,
        variant: str | None = None,
        code_graph_hints: list[dict[str, Any]] | None = None,
    ) -> AssembledPrompt:
        """Assemble the final prompt.

        Complete flow:
        1. Detect task complexity
        2. Select base template variant
        3. Apply compression level overrides (if any)
        4. Trim each section according to configuration
        5. Assemble final instruction

        V3.9-04: When ``dials`` (a :class:`PromptDials`) is provided, the
        dial fragment is prepended to the instruction. When ``variant`` is
        provided but ``dials`` is not, the variant is converted to dials
        via :meth:`PromptDials.from_variant`. Backward compatible: when
        neither is provided, behavior is unchanged.

        V3.9-02: When ``code_graph_hints`` is provided (a list of symbol
        dicts from :class:`CodeKnowledgeGraph`), they are injected as a
        "Code Context" section so the worker can reference existing
        symbols without Read/Grep.

        Args:
            task_description: Task description
            related_findings: Related findings list (from Scratchpad)
            task_id: Task ID (for instruction header)
            compression_level: ContextCompressor compression level (optional)
            dials: Optional :class:`PromptDials` instance (V3.9-04).
            variant: Optional legacy variant string ("concise"/"balanced"/"detailed").
                When ``dials`` is None and ``variant`` is provided, converted
                via :meth:`PromptDials.from_variant`.
            code_graph_hints: Optional list of symbol dicts from the code
                knowledge graph (V3.9-02).

        Returns:
            AssembledPrompt: Assembly result, containing instruction/complexity/variant/metadata
        """
        complexity = self.detect_complexity(task_description)
        config: dict[str, Any] = dict(self._TEMPLATE_VARIANTS[complexity])

        if compression_level is not None:
            override_key = (
                compression_level.name if hasattr(compression_level, "name") else str(compression_level).upper()
            )
            override: dict[str, Any] = cast(dict[str, Any], self._COMPRESSION_OVERRIDES.get(override_key, {}))
            config.update(override)

        role_display = self.base_prompt[: config["role_truncate"]]
        findings_to_include = (related_findings or [])[: config["findings_limit"]]
        truncated_findings = [f[: config["findings_truncate"]] for f in findings_to_include]

        # V3.9-04: Resolve PromptDials — explicit dials take precedence;
        # otherwise convert a legacy variant string.
        resolved_dials = dials
        if resolved_dials is None and variant is not None:
            try:
                from .prompt_dials import PromptDials

                resolved_dials = PromptDials.from_variant(variant)
            except (ImportError, AttributeError, TypeError):
                resolved_dials = None
        dial_fragment = ""
        if resolved_dials is not None:
            try:
                dial_fragment = resolved_dials.to_prompt_fragment()
            except (AttributeError, TypeError, RuntimeError):
                dial_fragment = ""

        style = config.get("instruction_style", "structured")
        instruction = self._build_instruction(
            style=style,
            task_id=task_id,
            task_description=task_description,
            role_display=role_display,
            findings=truncated_findings,
            include_constraints=config.get("include_constraints", False),
            include_anti_patterns=config.get("include_anti_patterns", False),
            dial_fragment=dial_fragment,
            code_graph_hints=code_graph_hints,
        )

        token_est = len(instruction) // 3

        metadata: dict[str, Any] = {
            "compression_applied": compression_level is not None,
            "compression_level": str(compression_level),
            "original_base_length": len(self.base_prompt),
            "assembled_length": len(instruction),
            "findings_included": len(truncated_findings),
            "findings_total": len(related_findings or []),
        }
        if resolved_dials is not None:
            metadata["dials_applied"] = True
            try:
                metadata["dials_variant"] = resolved_dials.to_variant()
                metadata["dials"] = {
                    "verbosity": resolved_dials.verbosity,
                    "creativity": resolved_dials.creativity,
                    "risk_tolerance": resolved_dials.risk_tolerance,
                }
            except (AttributeError, TypeError, RuntimeError):
                metadata["dials_applied"] = False
        else:
            metadata["dials_applied"] = False
        if code_graph_hints:
            metadata["code_graph_hints_count"] = len(code_graph_hints)

        return AssembledPrompt(
            instruction=instruction,
            complexity=complexity,
            variant_used=config.get("name", f"{complexity.value}_custom"),
            tokens_estimate=token_est,
            metadata=metadata,
        )
