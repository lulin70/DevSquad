"""Merged prompt-assembler mixins.

This module is the V4.1.2 Phase 3 Wave 3 consolidation of the following 4
previously-separate mixin files:

- ``prompt_assembler_formatting_mixin.py``     -> ``PromptAssemblerFormattingMixin``
- ``prompt_assembler_substitution_mixin.py``   -> ``PromptAssemblerSubstitutionMixin``
- ``prompt_assembler_template_mixin.py``       -> ``PromptAssemblerTemplateMixin``
- ``prompt_assembler_validation_mixin.py``     -> ``PromptAssemblerValidationMixin``

The original files have been converted to thin shims that re-export from this
module for backward compatibility; they will be deleted in V4.2.0.
"""

import logging
import os
import re
from typing import Any, cast

from .prompt_assembler_base import PromptAssemblerBase, TaskComplexity

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

# Module-level config cache. ``_load_config`` mutates these via ``global``
# statements, so they must live in the same module as the method.
_config_cache: dict = {}
_config_cache_path: str | None = None

_RE_NUMBERING = re.compile(r"\d+[.\)、]")
_RE_MULTI_REQ = re.compile(r"[;；\n]")


class PromptAssemblerFormattingMixin(PromptAssemblerBase):
    """Provides instruction formatting and QC injection for PromptAssembler."""

    def _concat_injections(self, style: str = "") -> str:
        """Concatenate QC + ponytail injections for short-style instructions.

        Used by ultra_minimal/minimal/direct styles where the injection is
        appended as a single block rather than as separate ``parts.append``
        calls.

        Args:
            style: The instruction style. Ponytail rules are skipped for
                compressed styles (``ultra_minimal``, ``minimal``) to avoid
                defeating the purpose of context compression.
        """
        chunks: list[str] = []
        if self.qc_enabled and self._qc_injection:
            chunks.append(self._qc_injection)
        if style not in ("ultra_minimal", "minimal"):
            ponytail = self._get_ponytail_injection()
            if ponytail:
                chunks.append(ponytail)
        learned = self._get_learned_rules_injection()
        if learned:
            chunks.append(learned)
        return "\n\n".join(chunks) if chunks else ""

    def _build_quality_control_injection(self) -> str:
        """
        Build quality control system prompt injection based on configuration.

        This creates a comprehensive set of rules that will be injected into
        every Worker's prompt, ensuring consistent quality standards.

        Returns:
            str: Formatted quality control instructions
        """
        qc = self.qc_config.get("quality_control", {})
        strict = qc.get("strict_mode", False)

        parts = []
        parts.append("\n\n## Quality Control System (ACTIVE)")
        parts.append(f"Strict Mode: {'ON' if strict else 'OFF (warnings only)'}")
        parts.append(f"Minimum Score: {qc.get('min_quality_score', 85)}/100")
        parts.append("")

        aqc = qc.get("ai_quality_control", {})
        if aqc.get("enabled", False):
            parts.extend(self._qc_ai_quality_section(aqc))

        asg = qc.get("ai_security_guard", {})
        if asg.get("enabled", False):
            parts.extend(self._qc_security_section(asg))

        atc = qc.get("ai_team_collaboration", {})
        if atc.get("enabled", False):
            parts.extend(self._qc_collaboration_section(atc))

        parts.extend(self._qc_output_quality_gate(qc, strict))

        return "\n".join(parts)

    def _qc_ai_quality_section(self, aqc: dict[str, Any]) -> list[str]:
        """Build the AI Quality Control rules section (header through trailing blank line)."""
        parts = ["### AI Quality Control Rules:"]

        hc = aqc.get("hallucination_check", {})
        if hc.get("enabled", False):
            parts.append("- **Hallucination Prevention**:")
            if hc.get("require_traceable_references"):
                parts.append("  . All API/library references MUST include official URL or version")
            if hc.get("require_signature_verification"):
                parts.append("  . Verify function signatures via `import + dir()` before using")
            if hc.get("forbid_absolute_certainty"):
                parts.append("  . FORBIDDEN: 'obviously', 'clearly', 'undoubtedly' - provide evidence instead")

        oc = aqc.get("overconfidence_check", {})
        if oc.get("enabled", False):
            parts.append("- **Overconfidence Prevention**:")
            parts.append(
                f"  . Every technical decision MUST present >={oc.get('require_alternatives_min', 2)} alternatives with pros/cons"
            )
            parts.append(
                f"  . Must list >={oc.get('require_failure_scenarios_min', 3)} potential failure scenarios"
            )
            if oc.get("acknowledge_tradeoffs"):
                parts.append("  . Always acknowledge limitations and trade-offs")

        pd = aqc.get("pattern_diversity", {})
        if pd.get("enabled", False):
            parts.append("- **Pattern Diversity**:")
            parts.append("  . Consider current state-of-the-art (last 6 months)")
            parts.append("  . Evaluate multiple approaches before recommending")
            parts.append("  . Flag repeated/solutions from recent tasks")

        sv = aqc.get("self_verification_prevention", {})
        if sv.get("enabled", False):
            parts.append("- **Self-Verification Trap Avoidance**:")
            if sv.get("enforce_creator_tester_separation"):
                parts.append("  . Code creator and test creator MUST be different roles")
            if sv.get("require_spec_based_testing"):
                parts.append("  . Tests based on specification (PRD), NOT implementation details")
            parts.append(f"  . Error case coverage >={sv.get('min_error_coverage_percent', 15)}%")
        parts.append("")
        return parts

    def _qc_security_section(self, asg: dict[str, Any]) -> list[str]:
        """Build the Security Rules (PermissionGuard) section (header through trailing blank line)."""
        parts = ["### Security Rules (PermissionGuard):"]
        perm_level = asg.get("permission_level", "DEFAULT")
        level_desc = {
            "PLAN": "Read-only mode (no file modifications)",
            "DEFAULT": "Write ops require confirmation",
            "AUTO": "AI auto-judges safe operations (trusted context)",
            "BYPASS": "Full skip (manual authorization required)",
        }
        parts.append(f"- Current Level: **L1/L2/L3/L4[{perm_level}]**: {level_desc.get(perm_level, 'Unknown')}")

        iv = asg.get("input_validation", {})
        if iv.get("enabled", False):
            parts.append("- **Input Validation (16 patterns active)**:")
            if iv.get("block_high_severity"):
                parts.append("  . BLOCK: SQL/Command/XSS/SSRF/Path injection -> immediate rejection")
            if iv.get("warn_and_sanitize_medium"):
                parts.append("  . SANITIZE: LDAP/XPath/Header/Email injection -> cleaned + warning")
            if iv.get("flag_low_severity"):
                parts.append("  . FLAG: Template/ReDoS/Format/XXE -> advisory warning")

        parts.append("- **Sensitive Data Rules**:")
        parts.append("  . FORBIDDEN: Write passwords/keys/tokens to Scratchpad SHARED zone")
        parts.append("  . FORBIDDEN: Include secrets in error messages or logs")
        parts.append("  . REQUIRED: Use environment variables or secret managers for credentials")
        parts.append("")
        return parts

    def _qc_collaboration_section(self, atc: dict[str, Any]) -> list[str]:
        """Build the Collaboration Rules section (header through trailing blank line)."""
        parts = ["### Collaboration Rules:"]

        raci = atc.get("raci", {})
        if raci.get("mode") == "strict":
            parts.append("- **RACI Matrix (STRICT mode)**:")
            parts.append("  . One Responsible (R) per task - the primary doer")
            parts.append("  . One Accountable (A) per task - final owner/approver")
            parts.append("  . Consulted (C) roles must be asked BEFORE decisions")
            parts.append("  . Informed (I) roles notified AFTER decisions")

        scratchpad = atc.get("scratchpad", {})
        if scratchpad.get("protocol") == "zoned":
            parts.append("- **Scratchpad Zoned Protocol**:")
            parts.append("  . READONLY zone: Other roles' outputs (read-only, no modify)")
            parts.append("  . WRITE zone: Your output only (isolated namespace)")
            parts.append("  . SHARED zone: Consensus-approved conclusions (requires vote)")
            parts.append("  . PRIVATE zone: Sensitive data (invisible to others)")

        consensus = atc.get("consensus", {})
        if consensus.get("enabled", False):
            parts.append(f"- **Consensus Mechanism** (threshold: {consensus.get('threshold', 0.7) * 100:.0f}%):")
            parts.append("  . Weighted voting by role importance")
            if consensus.get("veto_enabled"):
                veto_roles = consensus.get("veto_allowed_roles", [])
                parts.append(f"  . Veto power: {', '.join(veto_roles) if veto_roles else 'None'}")
            parts.append("  . Deadlock: Auto-escalate to user after timeout")

        parts.append("")
        return parts

    def _qc_output_quality_gate(self, qc: dict[str, Any], strict: bool) -> list[str]:
        """Build the Output Quality Gate section (no trailing blank line)."""
        min_score = qc.get("min_quality_score", 85)
        parts = ["### Output Quality Gate:"]
        parts.append(
            f"- Your output will be scored (0-{min_score - 1} REJECTED / {min_score}-99 CONDITIONAL / 100 ACCEPTED)"
        )
        parts.append("- Low score triggers specific improvement requirements")
        if strict:
            parts.append("- **In STRICT mode: Rejected outputs cannot proceed to next phase**")
        return parts

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
        """
        Build work instruction in the specified style

        Args:
            style: Instruction style (direct/structured/comprehensive/minimal/ultra_minimal)
            task_id: Task ID
            task_description: Task description
            role_display: Trimmed role prompt
            findings: Trimmed related findings list
            include_constraints: Whether to include constraint reminders
            include_anti_patterns: Whether to include anti-pattern warnings
            dial_fragment: V3.9-04 PromptDials fragment to prepend (may be empty).
            code_graph_hints: V3.9-02 code-graph symbol dicts to inject as context.

        Returns:
            str: Assembled instruction text
        """
        # V3.9-04: Prepend the dial fragment (when non-empty) to every style.
        prefix = f"{dial_fragment}\n\n" if dial_fragment else ""

        if style == "ultra_minimal":
            return prefix + self._build_ultra_minimal(task_description, style)
        if style == "minimal":
            return prefix + self._build_minimal(task_description, findings, style)
        if style == "direct":
            return prefix + self._build_direct(task_description, role_display, findings, style)
        return prefix + self._build_structured(
            style,
            task_id,
            task_description,
            role_display,
            findings,
            include_constraints,
            include_anti_patterns,
            code_graph_hints,
        )

    def _build_ultra_minimal(self, task_description: str, style: str) -> str:
        """Build the ultra_minimal-style instruction body (with injections)."""
        base = f"[{self.role_id}] {task_description}\nOutput core conclusion."
        return base + self._concat_injections(style)

    def _build_minimal(self, task_description: str, findings: list[str], style: str) -> str:
        """Build the minimal-style instruction body (with injections)."""
        parts = [f"[{self.role_id}] Task: {task_description}"]
        if findings:
            parts.append(f"Reference: {findings[0][:50]}")
        user_rules = self._get_user_rules_injection(task_description)
        if user_rules:
            parts.append(f"Rules: {user_rules[:100]}")
        parts.append("Output key conclusion.")
        base = "\n".join(parts)
        return base + self._concat_injections(style)

    def _build_direct(
        self, task_description: str, role_display: str, findings: list[str], style: str
    ) -> str:
        """Build the direct-style instruction body (with injections)."""
        user_rules = self._get_user_rules_injection(task_description)
        base = (
            f"=== Task ===\n"
            f"Description: {task_description}\n"
            f"Role: {role_display}...\n\n"
            + ("=== Related Findings ===\n" + "\n".join(f"- {f}" for f in findings) + "\n\n" if findings else "")
            + (f"=== User Rules ===\n{user_rules}\n\n" if user_rules else "")
            + (self._get_skill_injection() if self._get_skill_injection() else "")
            + "Complete your work, output core conclusion."
        )
        return base + self._concat_injections(style)

    def _build_structured(
        self,
        style: str,
        task_id: str,
        task_description: str,
        role_display: str,
        findings: list[str],
        include_constraints: bool,
        include_anti_patterns: bool,
        code_graph_hints: list[dict[str, Any]] | None,
    ) -> str:
        """Build the structured/comprehensive-style instruction body."""
        parts = []
        parts.append("=== Task ===")
        if task_id:
            parts.append(f"Task ID: {task_id}")
        parts.append(f"Description: {task_description}")
        parts.append(f"Role: {role_display}")
        parts.append("")

        parts.extend(self._build_code_context_section(code_graph_hints))

        if findings:
            parts.append("=== Related Findings (from other Workers) ===")
            for i, f in enumerate(findings, 1):
                parts.append(f"  {i}. {f}")
            parts.append("")

        if include_constraints:
            parts.append("=== Constraints ===")
            parts.append("- Output must be actionable and verifiable")
            parts.append("- Mark assumptions and risk points")
            parts.append("")

        parts.extend(self._build_anti_patterns_section(include_anti_patterns))

        skill_injection = self._get_skill_injection()
        if skill_injection:
            parts.append(skill_injection)

        parts.append("Please complete your work based on the above information.")
        if style == "comprehensive":
            parts.append("Output should include: analysis process, key decisions, specific plan, risk assessment.")
        else:
            parts.append("Output your core findings (1-3 key conclusions).")

        user_rules = self._get_user_rules_injection(task_description)
        if user_rules:
            parts.append("")
            parts.append("=== User Rules (from natural language collection) ===")
            parts.append(user_rules)

        if self.qc_enabled and self._qc_injection:
            parts.append(self._qc_injection)

        ponytail = self._get_ponytail_injection()
        if ponytail:
            parts.append(ponytail)

        learned = self._get_learned_rules_injection()
        if learned:
            parts.append(learned)

        # V4.1.0 (Matt P0-7): Inject grilling discipline for structured/
        # comprehensive styles (MEDIUM/COMPLEX tasks). Simple tasks (direct
        # style) skip grilling — they don't need Q&A discipline.
        grilling = getattr(self, "_grilling_injection", "")
        if grilling:
            parts.append(grilling)

        ar_content = self._get_anti_rationalization_injection()
        if ar_content:
            parts.append(ar_content)

        return "\n".join(parts)

    def _build_code_context_section(self, code_graph_hints: list[dict[str, Any]] | None) -> list[str]:
        """Build the Code Context section from code-graph hints (empty when no hints)."""
        # V3.9-02: Inject code-graph hints as a "Code Context" section so
        # the worker can reference existing symbols without Read/Grep.
        if not code_graph_hints:
            return []
        parts = ["=== Code Context (from CodeKnowledgeGraph) ==="]
        for hint in code_graph_hints[:8]:  # Cap at 8 hints to limit prompt size.
            name = hint.get("name", "?")
            sym_type = hint.get("type", "unknown")
            file_path = hint.get("file", "")
            signature = hint.get("signature", "")
            line_start = hint.get("line_start", 0)
            line_end = hint.get("line_end", 0)
            loc = f"{file_path}:{line_start}-{line_end}" if file_path else ""
            sig_str = f"  signature: {signature}" if signature else ""
            parts.append(f"- {name} ({sym_type}) {loc}{sig_str}")
        parts.append("")
        return parts

    def _build_anti_patterns_section(self, include_anti_patterns: bool) -> list[str]:
        """Build the Anti-Pattern Warnings section (empty when disabled or none)."""
        if not include_anti_patterns:
            return []
        anti_patterns = self._get_role_anti_patterns()
        if not anti_patterns:
            return []
        parts = ["=== Anti-Pattern Warnings ==="]
        for ap in anti_patterns:
            parts.append(f"- Avoid: {ap}")
        parts.append("")
        return parts

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Roughly estimate the token count of text

        In mixed Chinese/English scenarios, approximately 3 characters = 1 token.

        Args:
            text: Text to estimate

        Returns:
            int: Estimated token count
        """
        return max(1, len(text) // 3)


class PromptAssemblerSubstitutionMixin(PromptAssemblerBase):
    """Provides context-injection helpers for PromptAssembler."""

    _STOP_WORDS = frozenset(
        {
            "the",
            "is",
            "to",
            "of",
            "it",
            "in",
            "on",
            "at",
            "by",
            "an",
            "be",
            "do",
            "or",
            "as",
            "if",
            "so",
            "no",
            "not",
            "but",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "are",
            "was",
            "were",
            "been",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "shall",
            "a",
            "i",
            "you",
            "he",
            "she",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
        }
    )

    def _get_user_rules_injection(self, task_description: str) -> str:
        """Query user rules from RuleCollector storage and format as prompt text."""
        try:
            from scripts.collaboration.rule_collector import RuleStorage

            if not hasattr(self, "_rule_storage"):
                self._rule_storage = RuleStorage.get_shared()
            keywords = self._extract_keywords(task_description)
            rules = self._rule_storage.query(trigger_keywords=keywords, min_confidence=0.5)
            if not rules:
                return ""
            lines = []
            for r in rules[:10]:
                rtype = r.get("type", "always")
                trigger = r.get("trigger", "")
                action = r.get("action", "")
                if rtype == "forbid":
                    lines.append(f"FORBIDDEN: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "avoid":
                    lines.append(f"AVOID: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "always":
                    lines.append(f"ALWAYS: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "prefer":
                    lines.append(f"PREFER: {trigger + ' -> ' if trigger else ''}{action}")
            return "\n".join(lines)
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            logger.warning("format_rules_as_prompt failed: %s", e)
            return ""

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 8) -> list[str]:
        """Extract keywords from text, supporting both CJK and Latin scripts."""
        keywords = []
        for w in text.split():
            if len(w) > 1 and w.lower() not in PromptAssemblerSubstitutionMixin._STOP_WORDS:
                keywords.append(w)
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
        if has_cjk:
            cjk_segments = re.findall(r"[\u4e00-\u9fff]{2,}", text)
            for seg in cjk_segments:
                for i in range(0, len(seg) - 1, 2):
                    keywords.append(seg[i : i + 2])
        return keywords[:max_keywords]

    def _get_role_anti_patterns(self) -> list[str]:
        """
        Get role-specific anti-pattern warning list

        Different roles have different common anti-patterns.

        Returns:
            List[str]: List of anti-patterns this role should avoid
        """
        patterns = {
            "architect": [
                "Over-engineering (YAGNI violation)",
                "Ignoring non-functional requirements (performance/security/ops)",
                "Tech selection based only on popularity without considering team capability",
            ],
            "tester": [
                "Only writing happy path tests",
                "Tests disconnected from business requirements",
                "Excessive mocking making tests meaningless",
            ],
            "solo-coder": [
                "Skipping design and jumping to coding",
                "Not handling edge cases",
                "Hardcoded configuration and magic numbers",
            ],
            "product_manager": [
                "Vague requirements leading to repeated changes",
                "Priority confusion",
                "Ignoring technical feasibility",
            ],
            "ui-designer": [
                "Only creating visual mockups without considering interaction states",
                "Ignoring responsive design and accessibility",
                "Inconsistent design system",
            ],
        }
        return patterns.get(self.role_id, [])

    def _get_skill_injection(self) -> str:
        """
        Inject role-specific methodology skills from SKILL.md files.

        Loaded via RoleSkillLoader, these provide structured frameworks
        (e.g., PRD template, Opportunity Solution Tree) that the role
        should follow step-by-step.

        Returns:
            str: Formatted skill instructions, or empty string if none
        """
        try:
            from scripts.collaboration.role_skill_loader import get_shared_loader

            if not hasattr(self, "_skill_loader"):
                self._skill_loader = get_shared_loader()

            skills = self._skill_loader.load_skills(self.role_id)
            if not skills:
                return ""

            parts = ["\n\n## Methodology Frameworks (Follow these step-by-step)"]
            for skill in skills:
                parts.append(skill.to_prompt_text(max_length=1500))
            parts.append("")

            return "\n".join(parts)
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug("RoleSkillLoader not available: %s", e)
            return ""

    def _get_anti_rationalization_injection(self) -> str:
        """
        Inject AntiRationalizationEngine content into prompt (P0-1).

        Loads per-role excuse->rebuttal table and formats as markdown.
        This is the primary defense against Workers skipping quality steps.

        Returns:
            str: Formatted AR table, or empty string if unavailable
        """
        try:
            from scripts.collaboration.anti_rationalization import get_shared_engine

            if not hasattr(self, "_ar_engine"):
                self._ar_engine = get_shared_engine()
            return cast(str, self._ar_engine.format_for_prompt(self.role_id))
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug("AntiRationalizationEngine not available: %s", e)
            return ""


class PromptAssemblerTemplateMixin(PromptAssemblerBase):
    """Provides template variant tables and DevSquad config loading."""

    _TEMPLATE_VARIANTS = {
        TaskComplexity.SIMPLE: {
            "name": "compact",
            "role_truncate": 80,
            "findings_limit": 2,
            "findings_truncate": 60,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "direct",
        },
        TaskComplexity.MEDIUM: {
            "name": "standard",
            "role_truncate": 200,
            "findings_limit": 5,
            "findings_truncate": 150,
            "include_constraints": True,
            "include_anti_patterns": False,
            "instruction_style": "structured",
        },
        TaskComplexity.COMPLEX: {
            "name": "enhanced",
            "role_truncate": 500,
            "findings_limit": 8,
            "findings_truncate": 200,
            "include_constraints": True,
            "include_anti_patterns": True,
            "instruction_style": "comprehensive",
        },
    }

    _COMPRESSION_OVERRIDES = {
        "NONE": {},
        "SNIP": {
            "role_truncate": 120,
            "findings_limit": 3,
            "findings_truncate": 100,
            "include_constraints": False,
            "include_anti_patterns": False,
        },
        "SESSION_MEMORY": {
            "role_truncate": 60,
            "findings_limit": 1,
            "findings_truncate": 50,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "minimal",
        },
        "FULL_COMPACT": {
            "role_truncate": 40,
            "findings_limit": 0,
            "findings_truncate": 0,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "ultra_minimal",
        },
    }

    def _load_config(self, config_path: str | None = None) -> dict:
        """
        Load DevSquad configuration from YAML file.

        Search order:
        1. Explicit config_path parameter
        2. .devsquad.yaml in current directory
        3. .devsquad.yaml in project root (directory with pyproject.toml/.git)
        4. Default empty config (quality control disabled)

        Args:
            config_path: Explicit path to config file

        Returns:
            Dict: Parsed configuration dictionary
        """
        if not _YAML_AVAILABLE:
            return {"quality_control": {"enabled": False}}

        global _config_cache, _config_cache_path

        search_paths = []

        if config_path and os.path.exists(config_path):
            search_paths.append(config_path)
        else:
            current_dir = os.getcwd()
            candidate = os.path.join(current_dir, ".devsquad.yaml")
            if os.path.exists(candidate):
                search_paths.append(candidate)
            else:
                search_dir = current_dir
                for _ in range(5):
                    if os.path.exists(os.path.join(search_dir, "pyproject.toml")) or os.path.exists(
                        os.path.join(search_dir, ".git")
                    ):
                        project_config = os.path.join(search_dir, ".devsquad.yaml")
                        if os.path.exists(project_config):
                            search_paths.append(project_config)
                        break
                    parent = os.path.dirname(search_dir)
                    if parent == search_dir:
                        break
                    search_dir = parent

        if search_paths:
            resolved = os.path.realpath(search_paths[0])
            if _config_cache_path == resolved and _config_cache:
                return _config_cache
            try:
                with open(resolved, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                _config_cache = config
                _config_cache_path = resolved
                return config
            except (OSError, PermissionError, ValueError, TypeError) as e:
                logger.warning("Failed to load config from %s: %s", resolved, e)
                return {}
        else:
            return {"quality_control": {"enabled": False}}


class PromptAssemblerValidationMixin(PromptAssemblerBase):
    """Provides task-complexity detection for PromptAssembler."""

    _COMPLEXITY_KEYWORDS = {
        TaskComplexity.SIMPLE: {
            "positive": [
                "write a",
                "create",
                "add",
                "fix bug",
                "change a",
                "simple",
                "quick",
                "single function",
                "one line of code",
                "small change",
                "complete",
                "format",
                "rename",
                "hello",
                "utility class",
                "minor bug",
                "sort function",
                "logging",
                "写个",
                "快速",
                "简单",
                "小修改",
                "修复",
                "添加",
                "工具函数",
                "排序函数",
                "日志",
                "格式化",
                "重命名",
            ],
            "negative": [
                "architecture",
                "system design",
                "distributed",
                "refactor",
                "migration",
                "multi-module",
                "full-stack",
                "end-to-end",
                "complete solution",
                "high availability",
                "disaster recovery",
                "microservice architecture",
                "架构",
                "分布式",
                "重构",
                "迁移",
                "微服务",
                "高可用",
                "容灾",
                "全链路",
                "端到端",
                "完整方案",
            ],
        },
        TaskComplexity.COMPLEX: {
            "positive": [
                "architecture",
                "design pattern",
                "microservice",
                "distributed",
                "refactor",
                "migration",
                "security audit",
                "performance optimization",
                "complete solution",
                "system design",
                "tech selection",
                "end-to-end",
                "full pipeline",
                "high availability",
                "disaster recovery",
                "CI/CD",
                "pipeline",
                "comprehensive optimization",
                "架构",
                "设计模式",
                "微服务",
                "分布式",
                "重构",
                "迁移",
                "安全审计",
                "性能优化",
                "完整方案",
                "系统设计",
                "技术选型",
                "端到端",
                "流水线",
                "高可用",
                "容灾",
                "负载均衡",
                "服务发现",
                "全面优化",
                "全链路",
                "监控告警",
            ],
            "negative": [
                "write a function",
                "simple modification",
                "minor adjustment",
                "add a test",
                "quick fix",
                "hello world",
                "写个函数",
                "简单修改",
                "小调整",
                "添加测试",
                "快速修复",
            ],
        },
    }

    def detect_complexity(self, task_description: str) -> TaskComplexity:
        """
        Automatically detect task complexity

        Three-dimensional scoring model:
          1. Length dimension: <30 chars -> Simple, 30~150 chars -> Medium, >150 chars -> Complex
          2. Keyword dimension: Match SIMPLE/COMPLEX keyword groups
          3. Structure dimension: Whether it contains numbered lists/multiple questions/multi-layer requirements

        Args:
            task_description: Task description text

        Returns:
            TaskComplexity: Detected complexity level
        """
        if not task_description.strip():
            return TaskComplexity.SIMPLE
        desc_lower = task_description.lower()
        desc_len = len(task_description)

        length_score = self._length_score(desc_len)
        score_simple, score_complex = self._keyword_scores(desc_lower)
        structure_bonus = self._structure_bonus(task_description)

        final_simple = score_simple + length_score * 0.5
        final_complex = score_complex + length_score * 0.5 + structure_bonus
        return self._classify_by_scores(final_simple, final_complex, desc_len)

    def _length_score(self, desc_len: int) -> float:
        """Return the length-dimension score for a task description."""
        if desc_len < 15:
            return -0.5
        if desc_len < 30:
            return -0.3
        if desc_len < 150:
            return 0.0
        return 0.3

    @staticmethod
    def _word_match(keyword: str, text: str) -> bool:
        """Match a complexity keyword against text (substring for CJK, word-boundary otherwise)."""
        if "\u4e00" <= keyword[0] <= "\u9fff":
            return keyword in text
        return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))

    def _keyword_scores(self, desc_lower: str) -> tuple[float, float]:
        """Return ``(simple_score, complex_score)`` from keyword matching."""
        simple_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.SIMPLE]
        complex_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.COMPLEX]
        score_simple = 0.0
        score_complex = 0.0
        for kw in simple_kw["positive"]:
            if self._word_match(kw, desc_lower):
                score_simple += 0.15
        for kw in simple_kw["negative"]:
            if self._word_match(kw, desc_lower):
                score_simple -= 0.2
        for kw in complex_kw["positive"]:
            if self._word_match(kw, desc_lower):
                score_complex += 0.2
        for kw in complex_kw["negative"]:
            if self._word_match(kw, desc_lower):
                score_complex -= 0.15
        return score_simple, score_complex

    def _structure_bonus(self, task_description: str) -> float:
        """Return the structure-dimension bonus (numbering/questions/multi-requirement)."""
        bonus = 0.0
        if _RE_NUMBERING.search(task_description):
            bonus += 0.1
        if task_description.count("?") >= 2:
            bonus += 0.15
        if len(_RE_MULTI_REQ.split(task_description)) >= 3:
            bonus += 0.1
        return bonus

    def _classify_by_scores(
        self, final_simple: float, final_complex: float, desc_len: int
    ) -> TaskComplexity:
        """Classify complexity from the final simple/complex scores and length."""
        if desc_len < 15:
            return TaskComplexity.SIMPLE
        if final_complex > 0.3 and final_complex > final_simple + 0.1:
            return TaskComplexity.COMPLEX
        if final_simple > 0.15 and final_simple > final_complex + 0.05:
            return TaskComplexity.SIMPLE
        return TaskComplexity.MEDIUM
