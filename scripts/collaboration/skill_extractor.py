#!/usr/bin/env python3
"""
SkillExtractor - Pattern extraction, skill generation, and validation logic

Stateless computation module that takes execution data and produces
patterns, skill proposals, and validation results.
"""

import re
from datetime import datetime
from typing import Any

from .skillifier import (
    PGActionType,
    PatternStep,
    ProposalStatus,
    SkillCategory,
    SkillProposal,
    SkillStepDef,
    SuccessPattern,
    ValidationResult,
    ExecutionRecord,
    ExecutionStep,
)


class SkillExtractor:
    """Extracts patterns from execution records, generates skill proposals, and validates them."""

    CATEGORY_KEYWORDS = {
        SkillCategory.CODE_GENERATION: [
            "create",
            "generate",
            "init",
            "setup",
            "build",
            "implement",
            "develop",
            "write",
            "new",
        ],
        SkillCategory.CODE_REVIEW: ["review", "audit", "inspect", "check", "analyze-code", "lint", "quality"],
        SkillCategory.TESTING: ["test", "spec", "verify", "assert", "coverage", "pytest", "unittest", "e2e"],
        SkillCategory.DEPLOYMENT: [
            "deploy",
            "release",
            "ship",
            "publish",
            "ci/cd",
            "docker",
            "kubernetes",
            "production",
        ],
        SkillCategory.REFACTORING: ["refactor", "cleanup", "optimize", "restructure", "simplify", "improve"],
        SkillCategory.DOCUMENTATION: ["document", "readme", "api-doc", "comment", "wiki", "guide", "manual"],
        SkillCategory.ANALYSIS: ["analyze", "diagnose", "investigate", "profile", "benchmark", "measure"],
        SkillCategory.INTEGRATION: ["integrate", "connect", "configure", "setup-env", "pipeline", "workflow"],
        SkillCategory.SECURITY: ["security", "vulnerability", "auth", "permission", "encrypt", "scan"],
        SkillCategory.PERFORMANCE: ["performance", "speed", "cache", "optimize-fast", "latency", "throughput"],
    }

    def __init__(self, min_occurrences: int = 2, min_confidence: float = 0.6):
        self.min_occurrences = min_occurrences
        self.min_confidence = min_confidence

    # ================================================================
    # Pattern Extraction
    # ================================================================

    def analyze_history(
        self,
        records: list[ExecutionRecord],
        existing_patterns: list[SuccessPattern] | None = None,
    ) -> list[SuccessPattern]:
        """Analyze execution records and extract success patterns.

        Args:
            records: Execution records to analyze.
            existing_patterns: Existing patterns to check for duplicates.

        Returns:
            List of extracted success patterns sorted by confidence.
        """
        if len(records) < self.min_occurrences:
            return []

        clusters = self._cluster_sequences(records)
        patterns = []
        existing_ids = {p.pattern_id for p in (existing_patterns or [])}

        for cluster_records in clusters.values():
            if len(cluster_records) < self.min_occurrences:
                continue
            pattern = self._build_pattern_from_cluster(cluster_records)
            if pattern.confidence >= self.min_confidence:
                patterns.append(pattern)
                if pattern.pattern_id not in existing_ids:
                    existing_ids.add(pattern.pattern_id)

        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    def _cluster_sequences(self, records: list[ExecutionRecord]) -> dict[int, list[ExecutionRecord]]:
        clusters: dict[int, list[ExecutionRecord]] = {}
        cluster_id = 0

        for record in records:
            if len(record.steps) == 0:
                continue
            best_cluster = -1
            best_similarity = -1.0

            for cid, members in clusters.items():
                rep = members[0]
                sim = self._sequence_similarity(record.steps, rep.steps)
                if sim > best_similarity and sim > 0.45:
                    best_similarity = sim
                    best_cluster = cid

            if best_cluster >= 0:
                clusters[best_cluster].append(record)
            else:
                clusters[cluster_id] = [record]
                cluster_id += 1

        return clusters

    def _sequence_similarity(self, seq_a: list[ExecutionStep], seq_b: list[ExecutionStep]) -> float:
        if not seq_a or not seq_b:
            return 0.0
        len_a, len_b = len(seq_a), len(seq_b)
        if abs(len_a - len_b) > max(len_a, len_b) * 0.7:
            return 0.0

        n = min(len_a, len_b)
        total_sim = 0.0
        match_count = 0
        for i in range(n):
            sim = self._step_similarity(seq_a[i], seq_b[i])
            total_sim += sim
            if sim > 0.3:
                match_count += 1

        base_score = total_sim / max(n, 1)
        length_penalty = 1.0 - abs(len_a - len_b) / max(len_a, len_b, 1)
        match_ratio = match_count / max(n, 1)
        return base_score * 0.5 + length_penalty * 0.25 + match_ratio * 0.25

    def _step_similarity(self, a: ExecutionStep, b: ExecutionStep) -> float:
        if a.action_type != b.action_type:
            return 0.0
        score = 0.4
        if self._extension_match(a.target, b.target):
            score += 0.3
        elif self._directory_match(a.target, b.target):
            score += 0.15
        word_overlap = self._word_overlap(a.description, b.description)
        score += 0.2 * word_overlap
        if a.outcome == b.outcome == "success":
            score += 0.1
        return min(1.0, score)

    def _extension_match(self, target_a: str, target_b: str) -> bool:
        ext_a = self._get_extension(target_a)
        ext_b = self._get_extension(target_b)
        return ext_a and ext_b and ext_a == ext_b

    def _directory_match(self, target_a: str, target_b: str) -> bool:
        parts_a = target_a.replace("\\", "/").rstrip("/").split("/")
        parts_b = target_b.replace("\\", "/").rstrip("/").split("/")
        if len(parts_a) < 2 or len(parts_b) < 2:
            return False
        return parts_a[:-1] == parts_b[:-1]

    @staticmethod
    def _get_extension(path: str) -> str:
        if "." in path:
            return path.rsplit(".", 1)[-1].lower()
        return ""

    @staticmethod
    def _word_overlap(text_a: str, text_b: str) -> float:
        words_a = set(re.findall(r"\w{2,}", text_a.lower()))
        words_b = set(re.findall(r"\w{2,}", text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _build_pattern_from_cluster(self, records: list[ExecutionRecord]) -> SuccessPattern:
        rep = records[0]
        all_steps = [r.steps for r in records if r.steps]
        if not all_steps:
            return SuccessPattern(name="empty-pattern")

        min_len = min(len(s) for s in all_steps)
        template_steps = []
        for i in range(min_len):
            step_samples = [s[i] for s in all_steps if i < len(s)]
            if step_samples:
                ps = self._generalize_step(step_samples)
                template_steps.append(ps)

        keywords = self._extract_trigger_keywords(rep.task_description, rep.steps)
        roles = list(set(r.role_id for r in records if r.role_id))
        success_rate = sum(1 for r in records if r.success) / max(len(records), 1)
        confidence = self._calculate_confidence(records, template_steps)

        name = self._generate_pattern_name(rep.task_description, template_steps)

        return SuccessPattern(
            name=name,
            description=f"Auto-extracted pattern from {len(records)} executions",
            source_records=[r.record_id for r in records],
            steps_template=template_steps,
            trigger_keywords=keywords,
            applicable_roles=roles,
            frequency=len(records),
            confidence=confidence,
            avg_success_rate=success_rate,
        )

    def _generalize_step(self, step_samples: list[ExecutionStep]) -> PatternStep:
        sample = step_samples[0]
        targets = [s.target for s in step_samples]
        generalized_target = self._generalize_target(targets)
        descriptions = [s.description for s in step_samples]
        desc_template = self._generalize_description(descriptions)

        has_error = any(s.outcome != "success" for s in step_samples)
        avg_duration = sum(s.duration_ms for s in step_samples) / max(len(step_samples), 1)

        return PatternStep(
            action_type=sample.action_type,
            target_pattern=generalized_target,
            description_template=desc_template,
            is_required=not has_error,
            estimated_risk=min(1.0, avg_duration / 5000.0),
        )

    def _generalize_target(self, targets: list[str]) -> str:
        if not targets:
            return "*"
        extensions = set(self._get_extension(t) for t in targets)
        directories = set(
            "/".join(t.replace("\\", "/").rstrip("/").split("/")[:-1]) for t in targets if "/" in t or "\\" in t
        )

        if len(extensions) == 1 and list(extensions)[0]:
            ext = list(extensions)[0]
            if len(directories) == 1:
                dir_part = list(directories)[0]
                return f"{dir_part}/*.{ext}"
            return f"*.{ext}"
        if len(directories) == 1:
            return f"{list(directories)[0]}/*"
        return "*"

    def _generalize_description(self, descriptions: list[str]) -> str:
        if not descriptions:
            return ""
        common_words = []
        if descriptions:
            word_counts: dict[str, int] = {}
            for desc in descriptions:
                for w in re.findall(r"\w{3,}", desc.lower()):
                    word_counts[w] = word_counts.get(w, 0) + 1
            threshold = max(len(descriptions) * 0.6, 1)
            common_words = [w for w, c in sorted(word_counts.items(), key=lambda x: -x[1]) if c >= threshold][:8]
        return " ".join(common_words) if common_words else descriptions[0]

    def _extract_trigger_keywords(self, task_desc: str, steps: list[ExecutionStep]) -> list[str]:
        keywords = set()
        text = (task_desc + " " + " ".join(s.description for s in steps)).lower()
        important = re.findall(r"\b\w{4,}\b", text)
        stop_words = {
            "that",
            "with",
            "from",
            "this",
            "they",
            "have",
            "been",
            "were",
            "their",
            "will",
            "would",
            "could",
            "should",
            "into",
        }
        for w in important:
            if w not in stop_words and len(w) >= 4:
                keywords.add(w)
        return sorted(list(keywords))[:10]

    def _calculate_confidence(self, records: list[ExecutionRecord], steps: list[PatternStep]) -> float:
        freq_factor = min(1.0, len(records) / 10.0)
        success_factor = sum(1 for r in records if r.success) / max(len(records), 1)
        consistency = 1.0
        if len(records) >= 2:
            lengths = [len(r.steps) for r in records]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            consistency = max(0.3, 1.0 - variance / (avg_len**2 + 1))
        step_quality = sum(1.0 - ps.estimated_risk for ps in steps) / max(len(steps), 1)
        return freq_factor * 0.3 + success_factor * 0.3 + consistency * 0.2 + step_quality * 0.2

    def _generate_pattern_name(self, task_desc: str, steps: list[PatternStep]) -> str:
        if task_desc:
            words = re.findall(r"[A-Za-z][A-Za-z0-9 ]{2,20}", task_desc)
            if words:
                return words[0].strip().title() + " Pattern"
        if steps:
            action_names = {s.action_type.value.replace("_", " ").title() for s in steps}
            return " & ".join(sorted(action_names)[:3]) + " Pattern"
        return "Unnamed Pattern"

    # ================================================================
    # Skill Generation
    # ================================================================

    def generate_skill(self, pattern: SuccessPattern) -> SkillProposal:
        """Generate a skill proposal from a success pattern."""
        steps = [
            SkillStepDef(
                step_number=i + 1,
                action_type=ps.action_type,
                target_pattern=ps.target_pattern,
                description=ps.description_template or ps.action_type.value,
                is_required=ps.is_required,
            )
            for i, ps in enumerate(pattern.steps_template)
        ]

        category = self._classify_category(pattern)
        slug = self._make_slug(pattern.name)
        desc = self._generate_description(pattern, steps)
        input_schema = self._infer_input_schema(steps)
        output_schema = self._infer_output_schema(pattern)
        acceptance = self._infer_acceptance_criteria(pattern)

        proposal = SkillProposal(
            name=pattern.name.replace(" Pattern", "").strip(),
            slug=slug,
            description=desc,
            category=category.value,
            trigger_conditions=list(pattern.trigger_keywords),
            steps=steps,
            required_roles=list(pattern.applicable_roles),
            input_schema=input_schema,
            output_schema=output_schema,
            acceptance_criteria=acceptance,
            source_pattern=pattern.pattern_id,
            quality_score=pattern.confidence * 100,
            status=ProposalStatus.DRAFT,
        )
        proposal.slug = proposal._generate_slug()

        return proposal

    def _classify_category(self, pattern: SuccessPattern) -> SkillCategory:
        text = (
            pattern.name
            + " "
            + " ".join(pattern.trigger_keywords)
            + " ".join(ps.description_template for ps in pattern.steps_template)
        ).lower()
        best_cat = SkillCategory.AUTO_GENERATED
        best_score = 0
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_cat = cat
        return best_cat

    def _make_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9\s-]", "", name.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        return slug or "auto-skill"

    def _generate_description(self, pattern: SuccessPattern, steps: list[SkillStepDef]) -> str:
        action_types = [s.action_type.value.replace("_", " ") for s in steps]
        unique_actions = list(dict.fromkeys(action_types))
        return (
            f"Auto-generated skill: {' → '.join(unique_actions[:5])}. "
            f"Based on {pattern.frequency} successful executions. "
            f"Confidence: {pattern.confidence:.0%}."
        )

    def _infer_input_schema(self, steps: list[SkillStepDef]) -> dict[str, Any]:
        schema: dict[str, Any] = {}
        has_wildcard = any("*" in s.target_pattern for s in steps)
        if has_wildcard:
            schema["target_path"] = {"type": "string", "description": "Target file/directory path"}
        has_shell = any(s.action_type == PGActionType.SHELL_EXECUTE for s in steps)
        if has_shell:
            schema["command_args"] = {"type": "string", "description": "Command arguments"}
        return schema

    def _infer_output_schema(self, pattern: SuccessPattern) -> dict[str, Any]:
        create_steps = [
            ps
            for ps in pattern.steps_template
            if ps.action_type in (PGActionType.FILE_CREATE, PGActionType.FILE_MODIFY)
        ]
        if create_steps:
            return {
                "created_files": {"type": "array", "description": "Files created/modified"},
                "artifacts": {"type": "array", "description": "Output artifacts"},
            }
        return {}

    def _infer_acceptance_criteria(self, pattern: SuccessPattern) -> list[str]:
        criteria = []
        if pattern.avg_success_rate >= 0.9:
            criteria.append(f"Historical success rate >= {pattern.avg_success_rate:.0%}")
        if pattern.frequency >= 3:
            criteria.append(f"Verified across {pattern.frequency}+ executions")
        if pattern.steps_template:
            criteria.append(f"All {len(pattern.steps_template)} steps completed successfully")
        return criteria

    # ================================================================
    # Quality Validation (5-Dimension Scoring)
    # ================================================================

    def validate_skill(self, proposal: SkillProposal, patterns: list[SuccessPattern] | None = None) -> ValidationResult:
        """Validate a skill proposal with 5-dimension scoring.

        Args:
            proposal: The skill proposal to validate.
            patterns: Available patterns for repeatability scoring.

        Returns:
            ValidationResult with scores and issues.
        """
        completeness = self._score_completeness(proposal)
        specificity = self._score_specificity(proposal)
        repeatability = self._score_repeatability(proposal, patterns)
        safety = self._score_safety(proposal)
        practicality = self._score_practicality(proposal)

        score = completeness * 0.25 + specificity * 0.20 + repeatability * 0.20 + safety * 0.20 + practicality * 0.15

        issues = []
        suggestions = []

        if completeness < 60:
            issues.append("步骤定义不完整，缺少关键信息")
        if len(proposal.steps) == 0:
            issues.append("无任何步骤定义")
        if len(proposal.steps) > 20:
            issues.append(f"步骤过多({len(proposal.steps)}步)，建议拆分")
        if safety < 50:
            issues.append("包含高风险操作")
        if len(proposal.trigger_conditions) < 3:
            issues.append("触发条件过于宽泛")
            suggestions.append("增加更多触发关键词以提高特异性")
        if repeatability < 50:
            suggestions.append("需要更多成功执行记录来提高可重复性")
        if completeness < 80:
            suggestions.append("补充输入输出Schema和验收标准")

        result = ValidationResult(
            score=round(score, 1),
            completeness=round(completeness, 1),
            specificity=round(specificity, 1),
            repeatability=round(repeatability, 1),
            safety=round(safety, 1),
            issues=issues,
            suggestions=suggestions,
        )
        proposal.validation_result = result
        return result

    def _score_completeness(self, p: SkillProposal) -> float:
        score = 100.0
        if not p.name:
            score -= 30
        if not p.description:
            score -= 15
        if not p.steps:
            score -= 40
        if not p.input_schema:
            score -= 10
        if not p.output_schema:
            score -= 5
        if not p.acceptance_criteria:
            score -= 10
        for s in p.steps:
            if not s.description or s.description == s.action_type.value:
                score -= 3
        return max(0.0, score)

    def _score_specificity(self, p: SkillProposal) -> float:
        score = 80.0
        kw_count = len(p.trigger_conditions)
        score += min(20, kw_count * 3)
        generic_patterns = sum(1 for s in p.steps if s.target_pattern == "*")
        score -= generic_patterns * 10
        return max(0.0, min(100.0, score))

    def _score_repeatability(self, p: SkillProposal, patterns: list[SuccessPattern] | None = None) -> float:
        score = 60.0
        if p.source_pattern and patterns:
            pattern = next((pat for pat in patterns if pat.pattern_id == p.source_pattern), None)
            if pattern:
                score += min(30, pattern.frequency * 5)
                score += pattern.avg_success_rate * 10
        return max(0.0, min(100.0, score))

    def _score_safety(self, p: SkillProposal) -> float:
        score = 100.0
        high_risk_types = {PGActionType.FILE_DELETE, PGActionType.SHELL_EXECUTE, PGActionType.PROCESS_SPAWN}
        for s in p.steps:
            if s.action_type in high_risk_types:
                score -= 15
            if "*" in s.target_pattern and s.action_type in high_risk_types:
                score -= 10
        return max(0.0, score)

    def _score_practicality(self, p: SkillProposal) -> float:
        score = 70.0
        n_steps = len(p.steps)
        if 3 <= n_steps <= 15:
            score += 20
        elif n_steps < 3:
            score -= 15
        elif n_steps <= 20:
            score += 5
        else:
            score -= 20
        return max(0.0, min(100.0, score))
