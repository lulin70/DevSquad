"""Formatting mixin for PromptAssembler.

Extracts output formatting (instruction assembly across styles), the
quality-control injection builder, and the token-estimation utility so
the main assembler file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Output formatting (style-aware instruction assembly)
    - Compression-aware section trimming (driven by config from facade)
    - QC config injection
"""

from typing import Any

from .prompt_assembler_base import PromptAssemblerBase


class PromptAssemblerFormattingMixin(PromptAssemblerBase):
    """Provides instruction formatting and QC injection for PromptAssembler."""

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
            parts.append("### AI Quality Control Rules:")

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

        asg = qc.get("ai_security_guard", {})
        if asg.get("enabled", False):
            parts.append("### Security Rules (PermissionGuard):")
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

        atc = qc.get("ai_team_collaboration", {})
        if atc.get("enabled", False):
            parts.append("### Collaboration Rules:")

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

        min_score = qc.get("min_quality_score", 85)
        parts.append("### Output Quality Gate:")
        parts.append(
            f"- Your output will be scored (0-{min_score - 1} REJECTED / {min_score}-99 CONDITIONAL / 100 ACCEPTED)"
        )
        parts.append("- Low score triggers specific improvement requirements")
        if strict:
            parts.append("- **In STRICT mode: Rejected outputs cannot proceed to next phase**")

        return "\n".join(parts)

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
        prefix = ""
        if dial_fragment:
            prefix = f"{dial_fragment}\n\n"

        if style == "ultra_minimal":
            base = f"[{self.role_id}] {task_description}\nOutput core conclusion."
            return prefix + base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        if style == "minimal":
            parts = [f"[{self.role_id}] Task: {task_description}"]
            if findings:
                parts.append(f"Reference: {findings[0][:50]}")
            user_rules = self._get_user_rules_injection(task_description)
            if user_rules:
                parts.append(f"Rules: {user_rules[:100]}")
            parts.append("Output key conclusion.")
            base = "\n".join(parts)
            return prefix + base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        if style == "direct":
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
            return prefix + base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        parts = []
        parts.append("=== Task ===")
        if task_id:
            parts.append(f"Task ID: {task_id}")
        parts.append(f"Description: {task_description}")
        parts.append(f"Role: {role_display}")
        parts.append("")

        # V3.9-02: Inject code-graph hints as a "Code Context" section so
        # the worker can reference existing symbols without Read/Grep.
        if code_graph_hints:
            parts.append("=== Code Context (from CodeKnowledgeGraph) ===")
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

        if include_anti_patterns:
            anti_patterns = self._get_role_anti_patterns()
            if anti_patterns:
                parts.append("=== Anti-Pattern Warnings ===")
                for ap in anti_patterns:
                    parts.append(f"- Avoid: {ap}")
                parts.append("")

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

        ar_content = self._get_anti_rationalization_injection()
        if ar_content:
            parts.append(ar_content)

        return prefix + "\n".join(parts)

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
