#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
"""

import re
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

_RE_NUMBERING = re.compile(r'\d+[.\)、]')
_RE_MULTI_REQ = re.compile(r'[;；\n]')

_config_cache: Dict = {}
_config_cache_path: Optional[str] = None


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
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptAssembler:
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

    _COMPLEXITY_KEYWORDS = {
        TaskComplexity.SIMPLE: {
            "positive": ["write a", "create", "add", "fix bug",
                        "change a", "simple", "quick", "single function", "one line of code",
                        "small change", "complete", "format", "rename", "hello",
                        "utility class", "minor bug", "sort function", "logging",
                        "写个", "快速", "简单", "小修改", "修复", "添加", "工具函数",
                        "排序函数", "日志", "格式化", "重命名"],
            "negative": ["architecture", "system design", "distributed", "refactor", "migration",
                        "multi-module", "full-stack", "end-to-end", "complete solution",
                        "high availability", "disaster recovery", "microservice architecture",
                        "架构", "分布式", "重构", "迁移", "微服务", "高可用", "容灾",
                        "全链路", "端到端", "完整方案"],
        },
        TaskComplexity.COMPLEX: {
            "positive": ["architecture", "design pattern", "microservice", "distributed",
                        "refactor", "migration", "security audit", "performance optimization",
                        "complete solution", "system design", "tech selection",
                        "end-to-end", "full pipeline", "high availability", "disaster recovery",
                        "CI/CD", "pipeline", "comprehensive optimization",
                        "架构", "设计模式", "微服务", "分布式", "重构", "迁移",
                        "安全审计", "性能优化", "完整方案", "系统设计", "技术选型",
                        "端到端", "流水线", "高可用", "容灾", "负载均衡",
                        "服务发现", "全面优化", "全链路", "监控告警"],
            "negative": ["write a function", "simple modification", "minor adjustment", "add a test",
                        "quick fix", "hello world",
                        "写个函数", "简单修改", "小调整", "添加测试", "快速修复"],
        },
    }

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

    def __init__(self, role_id: str, base_prompt: str, config_path: str = None):
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

    def _load_config(self, config_path: str = None) -> Dict:
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
                    if os.path.exists(os.path.join(search_dir, "pyproject.toml")) or \
                       os.path.exists(os.path.join(search_dir, ".git")):
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
                with open(resolved, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                _config_cache = config
                _config_cache_path = resolved
                return config
            except Exception as e:
                logger.warning("Failed to load config from %s: %s", resolved, e)
                return {}
        else:
            return {"quality_control": {"enabled": False}}

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
                parts.append(f"  . Every technical decision MUST present >={oc.get('require_alternatives_min', 2)} alternatives with pros/cons")
                parts.append(f"  . Must list >={oc.get('require_failure_scenarios_min', 3)} potential failure scenarios")
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
                "BYPASS": "Full skip (manual authorization required)"
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
                parts.append(f"- **Consensus Mechanism** (threshold: {consensus.get('threshold', 0.7)*100:.0f}%):")
                parts.append("  . Weighted voting by role importance")
                if consensus.get("veto_enabled"):
                    veto_roles = consensus.get("veto_allowed_roles", [])
                    parts.append(f"  . Veto power: {', '.join(veto_roles) if veto_roles else 'None'}")
                parts.append("  . Deadlock: Auto-escalate to user after timeout")

            parts.append("")

        min_score = qc.get("min_quality_score", 85)
        parts.append("### Output Quality Gate:")
        parts.append(f"- Your output will be scored (0-{min_score-1} REJECTED / {min_score}-99 CONDITIONAL / 100 ACCEPTED)")
        parts.append("- Low score triggers specific improvement requirements")
        if strict:
            parts.append("- **In STRICT mode: Rejected outputs cannot proceed to next phase**")

        return "\n".join(parts)

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
        desc_lower = task_description.lower()
        desc_len = len(task_description)

        score_simple = 0.0
        score_complex = 0.0

        length_score = 0.0
        if desc_len < 15:
            length_score = -0.5
        elif desc_len < 30:
            length_score = -0.3
        elif desc_len < 150:
            length_score = 0.0
        else:
            length_score = 0.3

        simple_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.SIMPLE]
        complex_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.COMPLEX]

        def _word_match(keyword: str, text: str) -> bool:
            if '\u4e00' <= keyword[0] <= '\u9fff':
                return keyword in text
            return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))

        for kw in simple_kw["positive"]:
            if _word_match(kw, desc_lower):
                score_simple += 0.15
        for kw in simple_kw["negative"]:
            if _word_match(kw, desc_lower):
                score_simple -= 0.2

        for kw in complex_kw["positive"]:
            if _word_match(kw, desc_lower):
                score_complex += 0.2
        for kw in complex_kw["negative"]:
            if _word_match(kw, desc_lower):
                score_complex -= 0.15

        has_numbering = bool(_RE_NUMBERING.search(task_description))
        has_multi_question = task_description.count('?') >= 2
        has_multi_requirement = len(_RE_MULTI_REQ.split(task_description)) >= 3

        structure_bonus = 0.0
        if has_numbering:
            structure_bonus += 0.1
        if has_multi_question:
            structure_bonus += 0.15
        if has_multi_requirement:
            structure_bonus += 0.1

        final_simple = score_simple + length_score * 0.5
        final_complex = score_complex + length_score * 0.5 + structure_bonus

        if not task_description.strip():
            return TaskComplexity.SIMPLE
        if desc_len < 15:
            return TaskComplexity.SIMPLE
        if final_complex > 0.3 and final_complex > final_simple + 0.1:
            return TaskComplexity.COMPLEX
        if final_simple > 0.15 and final_simple > final_complex + 0.05:
            return TaskComplexity.SIMPLE
        return TaskComplexity.MEDIUM

    def assemble(self,
                 task_description: str,
                 related_findings: List[str] = None,
                 task_id: str = "",
                 compression_level=None) -> AssembledPrompt:
        """
        Assemble the final prompt

        Complete flow:
        1. Detect task complexity
        2. Select base template variant
        3. Apply compression level overrides (if any)
        4. Trim each section according to configuration
        5. Assemble final instruction

        Args:
            task_description: Task description
            related_findings: Related findings list (from Scratchpad)
            task_id: Task ID (for instruction header)
            compression_level: ContextCompressor compression level (optional)

        Returns:
            AssembledPrompt: Assembly result, containing instruction/complexity/variant/metadata
        """
        complexity = self.detect_complexity(task_description)
        config = dict(self._TEMPLATE_VARIANTS[complexity])

        if compression_level is not None:
            override_key = compression_level.name if hasattr(compression_level, 'name') else str(compression_level).upper()
            override = self._COMPRESSION_OVERRIDES.get(override_key, {})
            config.update(override)

        role_display = self.base_prompt[:config["role_truncate"]]
        findings_to_include = (related_findings or [])[:config["findings_limit"]]
        truncated_findings = [
            f[:config["findings_truncate"]] for f in findings_to_include
        ]

        style = config.get("instruction_style", "structured")
        instruction = self._build_instruction(
            style=style,
            task_id=task_id,
            task_description=task_description,
            role_display=role_display,
            findings=truncated_findings,
            include_constraints=config.get("include_constraints", False),
            include_anti_patterns=config.get("include_anti_patterns", False),
        )

        token_est = len(instruction) // 3

        return AssembledPrompt(
            instruction=instruction,
            complexity=complexity,
            variant_used=config.get("name", f"{complexity.value}_custom"),
            tokens_estimate=token_est,
            metadata={
                "compression_applied": compression_level is not None,
                "compression_level": str(compression_level),
                "original_base_length": len(self.base_prompt),
                "assembled_length": len(instruction),
                "findings_included": len(truncated_findings),
                "findings_total": len(related_findings or []),
            },
        )

    def _build_instruction(self,
                           style: str,
                           task_id: str,
                           task_description: str,
                           role_display: str,
                           findings: List[str],
                           include_constraints: bool,
                           include_anti_patterns: bool) -> str:
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

        Returns:
            str: Assembled instruction text
        """
        if style == "ultra_minimal":
            base = (
                f"[{self.role_id}] {task_description}\n"
                f"Output core conclusion."
            )
            return base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        if style == "minimal":
            parts = [f"[{self.role_id}] Task: {task_description}"]
            if findings:
                parts.append(f"Reference: {findings[0][:50]}")
            user_rules = self._get_user_rules_injection(task_description)
            if user_rules:
                parts.append(f"Rules: {user_rules[:100]}")
            parts.append("Output key conclusion.")
            base = "\n".join(parts)
            return base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        if style == "direct":
            user_rules = self._get_user_rules_injection(task_description)
            base = (
                f"=== Task ===\n"
                f"Description: {task_description}\n"
                f"Role: {role_display}...\n\n"
                + (f"=== Related Findings ===\n" +
                   "\n".join(f"- {f}" for f in findings) + "\n\n" if findings else "") +
                (f"=== User Rules ===\n{user_rules}\n\n" if user_rules else "") +
                "Complete your work, output core conclusion."
            )
            return base + (self._qc_injection if self.qc_enabled and self._qc_injection else "")

        parts = []
        parts.append(f"=== Task ===")
        if task_id:
            parts.append(f"Task ID: {task_id}")
        parts.append(f"Description: {task_description}")
        parts.append(f"Role: {role_display}")
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

        return "\n".join(parts)

    def _get_user_rules_injection(self, task_description: str) -> str:
        """Query user rules from RuleCollector storage and format as prompt text."""
        try:
            from scripts.collaboration.rule_collector import RuleStorage
            if not hasattr(self, '_rule_storage'):
                self._rule_storage = RuleStorage.get_shared()
            keywords = self._extract_keywords(task_description)
            rules = self._rule_storage.query(
                trigger_keywords=keywords, min_confidence=0.5
            )
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
        except Exception:
            return ""

    _STOP_WORDS = frozenset({
        "the", "is", "to", "of", "it", "in", "on", "at", "by", "an", "be",
        "do", "or", "as", "if", "so", "no", "not", "but", "and", "for",
        "with", "this", "that", "from", "are", "was", "were", "been", "have",
        "has", "had", "will", "would", "could", "should", "may", "might",
        "can", "shall", "a", "i", "you", "he", "she", "we", "they", "me",
        "him", "her", "us", "them", "my", "your", "his", "its", "our",
    })

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 8) -> List[str]:
        """Extract keywords from text, supporting both CJK and Latin scripts."""
        keywords = []
        for w in text.split():
            if len(w) > 1 and w.lower() not in PromptAssembler._STOP_WORDS:
                keywords.append(w)
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in text)
        if has_cjk:
            cjk_segments = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            for seg in cjk_segments:
                for i in range(0, len(seg) - 1, 2):
                    keywords.append(seg[i:i + 2])
        return keywords[:max_keywords]

    def _get_role_anti_patterns(self) -> List[str]:
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
            if not hasattr(self, '_ar_engine'):
                self._ar_engine = get_shared_engine()
            return self._ar_engine.format_for_prompt(self.role_id)
        except Exception as e:
            logger.debug("AntiRationalizationEngine not available: %s", e)
            return ""

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
