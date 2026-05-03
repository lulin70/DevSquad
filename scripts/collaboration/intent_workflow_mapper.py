#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IntentWorkflowMapper - Maps user intent to workflow chains

Extends RoleMatcher with semantic understanding of WHAT user wants to do,
not just WHICH keywords they used.

When user says "fix the login bug", system should know this requires
debugging workflow, not generic coding.

Integration point: Called by MultiAgentDispatcher.dispatch() before role matching.
The detected IntentMatch is stored and passed to Coordinator/Workers.

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.3
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowChainDef:
    """Definition of a workflow chain for a specific intent type."""
    trigger_keywords: Dict[str, List[str]]
    workflow_chain: List[str]
    required_roles: List[str]
    optional_roles: List[str] = field(default_factory=list)
    gate: Optional[str] = None
    gate_description: str = ""
    anti_skip_message: str = ""


@dataclass
class IntentMatch:
    """Result of intent detection against task description."""
    intent_type: str
    confidence: float
    workflow_chain: List[str] = field(default_factory=list)
    required_roles: List[str] = field(default_factory=list)
    optional_roles: List[str] = field(default_factory=list)
    gate: Optional[str] = None
    gate_description: str = ""
    anti_skip_message: str = ""


class IntentWorkflowMapper:
    """
    Maps user intent to workflow chains and required roles.

    Extends RoleMatcher with semantic understanding of user INTENT.
    Supports 3 languages (zh/en/ja) for keyword detection.

    Inspired by AGENTS.md intent mapping from Agent Skills (addyosmani/agent-skills).
    """

    WORKFLOW_CHAINS: Dict[str, WorkflowChainDef] = {
        "bug_fix": WorkflowChainDef(
            trigger_keywords={
                "zh": [
                    "修复", "修", "bug", "错误", "报错", "失败",
                    "异常", "崩溃", "缺陷", "问题",
                ],
                "en": [
                    "fix", "bug", "error", "fail", "crash", "broken",
                    "issue", "defect", "problem", "exception",
                ],
                "ja": [
                    "修正", "バグ", "エラー", "失敗", "異常", "クラッシュ",
                    "欠陥", "問題",
                ],
            },
            workflow_chain=[
                "debugging_and_error_recovery",
                "test_driven_development",
            ],
            required_roles=["solo-coder", "tester"],
            optional_roles=["security"],
            gate="prove_it_pattern",
            gate_description=(
                "Must have a failing reproduction test before implementing fix"
            ),
            anti_skip_message=(
                "Do NOT implement the fix first. "
                "Write the test that demonstrates the bug."
            ),
        ),
        "new_feature": WorkflowChainDef(
            trigger_keywords={
                "zh": [
                    "实现", "开发", "新增", "添加", "创建", "构建",
                    "功能", "特性", "做一个", "写一个",
                ],
                "en": [
                    "implement", "develop", "add", "create", "build",
                    "feature", "new", "make a", "write a",
                ],
                "ja": [
                    "実装", "開発", "追加", "作成", "構築", "機能",
                    "新規", "作る",
                ],
            },
            workflow_chain=[
                "spec_driven_development",
                "planning_and_task_breakdown",
                "incremental_implementation",
                "test_driven_development",
            ],
            required_roles=["architect", "solo-coder", "tester"],
            optional_roles=["product-manager", "ui-designer"],
            gate="spec_first",
            gate_description=(
                "Must produce or validate a spec before writing implementation code"
            ),
            anti_skip_message=(
                "Do NOT start coding until the spec is reviewed and approved."
            ),
        ),
        "security_review": WorkflowChainDef(
            trigger_keywords={
                "zh": [
                    "安全", "漏洞", "渗透", "审计", "加固", "注入",
                    "XSS", "SQL注入", "越权", "CSRF",
                ],
                "en": [
                    "security", "vulnerability", "penetration", "audit",
                    "harden", "injection", "XSS", "SQL injection",
                    "OWASP", "CSRF", "auth bypass",
                ],
                "ja": [
                    "セキュリティ", "脆弱性", "侵入", "監査", "強化",
                    "インジェクション", "OWASP", "認証バイパス",
                ],
            },
            workflow_chain=[
                "security_and_hardening",
                "code_review_and_quality",
            ],
            required_roles=["security", "architect"],
            optional_roles=["solo-coder"],
            gate="owasp_checklist",
            gate_description=(
                "Must complete OWASP Top 10 checklist before approving"
            ),
            anti_skip_message=(
                "Do NOT mark as secure without systematic vulnerability assessment."
            ),
        ),
        "code_review": WorkflowChainDef(
            trigger_keywords={
                "zh": ["审查", "review", "代码质量", "重构", "优化", "简化", "走查"],
                "en": [
                    "review", "code quality", "refactor", "optimize",
                    "simplify", "walkthrough", "inspect",
                ],
                "ja": [
                    "レビュー", "コード品質", "リファクタ", "最適化",
                    "単純化", "ウォークスルー",
                ],
            },
            workflow_chain=[
                "code_review_and_quality",
                "code_simplification",
            ],
            required_roles=["solo-coder", "security", "tester"],
            optional_roles=["architect"],
            gate="change_size_limit",
            gate_description="Changes must be ~100 lines or split into smaller reviews",
            anti_skip_message="Do NOT approve large changesets without splitting.",
        ),
        "performance_optimization": WorkflowChainDef(
            trigger_keywords={
                "zh": [
                    "性能", "优化", "慢", "加速", "延迟", "吞吐",
                    "瓶颈", "卡顿", "超时",
                ],
                "en": [
                    "performance", "optimize", "slow", "speedup", "latency",
                    "throughput", "bottleneck", "timeout",
                ],
                "ja": [
                    "パフォーマンス", "最適化", "遅い", "高速化",
                    "レイテンシ", "スループット", "ボトルネック",
                ],
            },
            workflow_chain=[
                "performance_optimization",
                "code_review_and_quality",
            ],
            required_roles=["architect", "devops"],
            optional_roles=["solo-coder"],
            gate="measure_first",
            gate_description="Must have baseline measurements before optimizing",
            anti_skip_message=(
                "Do NOT optimize without measurements. "
                "You're likely optimizing the wrong thing."
            ),
        ),
        "deployment": WorkflowChainDef(
            trigger_keywords={
                "zh": ["部署", "发布", "上线", "部署", "CI", "CD", "发布", "部署到"],
                "en": [
                    "deploy", "release", "ship", "launch", "CI", "CD",
                    "publish", "rollout",
                ],
                "ja": ["デプロイ", "リリース", "公開", "CI", "CD"],
            },
            workflow_chain=[
                "ci_cd_and_automation",
                "shipping_and_launch",
            ],
            required_roles=["devops", "security"],
            optional_roles=["architect"],
            gate="pre_launch_checklist",
            gate_description="Complete all 6 categories of pre-launch checks",
            anti_skip_message=(
                "Do NOT deploy without rollback plan and monitoring setup."
            ),
        ),
    }

    def __init__(self, confidence_threshold: float = 0.3):
        self._confidence_threshold = confidence_threshold
        self._cache: Dict[str, Optional[IntentMatch]] = {}
        self._MAX_CACHE_SIZE = 128

    def detect_intent(
        self,
        task_description: str,
        lang: str = "zh"
    ) -> Optional[IntentMatch]:
        """
        Detect user intent from task description.

        Args:
            task_description: The user's task text
            lang: Language code ("zh", "en", or "ja")

        Returns:
            IntentMatch if confidence >= threshold, else None
        """
        cache_key = f"{lang}:{task_description[:100]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        task_lower = task_description.lower()

        best_match = None
        best_score = 0.0

        for intent_type, chain_def in self.WORKFLOW_CHAINS.items():
            score = self._calculate_score(task_lower, chain_def, lang)

            if score > 0 and score > best_score:
                best_score = score
                best_match = IntentMatch(
                    intent_type=intent_type,
                    confidence=score,
                    workflow_chain=list(chain_def.workflow_chain),
                    required_roles=list(chain_def.required_roles),
                    optional_roles=list(chain_def.optional_roles),
                    gate=chain_def.gate,
                    gate_description=chain_def.gate_description,
                    anti_skip_message=chain_def.anti_skip_message,
                )

        if best_match and best_match.confidence >= self._confidence_threshold:
            if len(self._cache) >= self._MAX_CACHE_SIZE:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[cache_key] = best_match
            logger.info(
                "Intent detected: type=%s confidence=%.2f roles=%s",
                best_match.intent_type,
                best_match.confidence,
                best_match.required_roles,
            )
            return best_match

        if len(self._cache) >= self._MAX_CACHE_SIZE:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = None
        return None

    def _calculate_score(
        self,
        task_lower: str,
        chain_def: WorkflowChainDef,
        lang: str,
    ) -> float:
        """Calculate match score as keyword overlap ratio."""
        keywords = list(chain_def.trigger_keywords.get(lang, []))
        keywords += list(chain_def.trigger_keywords.get("en", []))

        if not keywords:
            return 0.0

        matches = sum(1 for kw in keywords if kw.lower() in task_lower)
        return min(matches / max(len(keywords), 1), 1.0)

    def get_available_intents(self) -> List[str]:
        """Return all available intent types."""
        return sorted(self.WORKFLOW_CHAINS.keys())

    def get_intent_details(self, intent_type: str) -> Optional[Dict[str, Any]]:
        """Get full details for an intent type."""
        chain_def = self.WORKFLOW_CHAINS.get(intent_type)
        if not chain_def:
            return None
        return {
            "intent_type": intent_type,
            "trigger_keywords": chain_def.trigger_keywords,
            "workflow_chain": chain_def.workflow_chain,
            "required_roles": chain_def.required_roles,
            "optional_roles": chain_def.optional_roles,
            "gate": chain_def.gate,
            "gate_description": chain_def.gate_description,
            "anti_skip_message": chain_def.anti_skip_message,
        }


def get_shared_mapper(confidence_threshold: float = 0.3) -> IntentWorkflowMapper:
    """
    Get or create shared singleton instance.

    Args:
        confidence_threshold: Minimum confidence to accept intent match

    Returns:
        Shared IntentWorkflowMapper instance
    """
    if not hasattr(get_shared_mapper, "_instance"):
        get_shared_mapper._instance = IntentWorkflowMapper(
            confidence_threshold=confidence_threshold
        )
    return get_shared_mapper._instance
