#!/usr/bin/env python3
"""
Dispatch data models and constants.

Extracted from dispatcher.py for modularity. Contains:
- PerformanceMetric: Single performance metric dataclass
- PerformanceThresholds: Threshold configuration dataclass
- DispatchResult: Dispatch result dataclass
- I18N: Internationalization dictionary
- ROLE_TEMPLATES: Backward-compatible role template aliases
- PLANNED_ROLES: Backward-compatible planned role aliases
"""

from dataclasses import dataclass, field
from typing import Any

from .models import (
    ROLE_REGISTRY,
    get_planned_roles,
)

# Backward-compatible aliases from models SSOT
ROLE_TEMPLATES = {
    rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()
}
PLANNED_ROLES = {
    rid: {"name": rdef.name, "status": rdef.status, "description": rdef.description}
    for rid, rdef in get_planned_roles().items()
}

I18N = {
    "zh": {
        "title": "# 🤖 Multi-Agent 协作结果",
        "task": "**任务**",
        "status_ok": "✅ 成功",
        "status_fail": "❌ 失败",
        "status_label": "状态",
        "duration": "**耗时**",
        "roles": "**参与角色**",
        "summary": "## 📋 执行摘要",
        "output": "## 👥 各角色产出",
        "scratchpad": "## 📝 Scratchpad 共享区",
        "consensus": "## 🗳️ 共识决策",
        "compression": "## 📦 上下文压缩",
        "memory": "## 🧠 记忆系统",
        "permission": "## 🔒 权限检查",
        "skill": "## ⚡ Skill 学习",
        "quality": "## 🛡️ 测试质量审计",
        "errors": "## ⚠️ 错误信息",
        "mock_banner": "> ⚠️ **MOCK 模式** — 这是模拟输出，未调用真实 LLM。",
        "mock_hint": "> 使用 `--backend openai`（或 `anthropic`）并提供有效 API Key 获取真实 AI 分析。",
        "no_output": "*(无输出)*",
        "no_summary": "(无摘要)",
        "next_steps": "## 🔄 建议下一步",
    },
    "en": {
        "title": "# 🤖 Multi-Agent Collaboration Result",
        "task": "**Task**",
        "status_ok": "✅ Success",
        "status_fail": "❌ Failed",
        "status_label": "Status",
        "duration": "**Duration**",
        "roles": "**Roles**",
        "summary": "## 📋 Executive Summary",
        "output": "## 👥 Role Outputs",
        "scratchpad": "## 📝 Scratchpad",
        "consensus": "## 🗳️ Consensus Decisions",
        "compression": "## 📦 Context Compression",
        "memory": "## 🧠 Memory System",
        "permission": "## 🔒 Permission Checks",
        "skill": "## ⚡ Skill Learning",
        "quality": "## 🛡️ Test Quality Audit",
        "errors": "## ⚠️ Errors",
        "mock_banner": "> ⚠️ **MOCK MODE** — This is simulated output. No real LLM was called.",
        "mock_hint": "> Use `--backend openai` (or `anthropic`) with a valid API key for real AI analysis.",
        "no_output": "*(no output)*",
        "no_summary": "(no summary)",
        "next_steps": "## 🔄 Suggested Next Steps",
    },
    "ja": {
        "title": "# 🤖 マルチエージェントコラボレーション結果",
        "task": "**タスク**",
        "status_ok": "✅ 成功",
        "status_fail": "❌ 失敗",
        "status_label": "ステータス",
        "duration": "**所要時間**",
        "roles": "**参加ロール**",
        "summary": "## 📋 実行サマリー",
        "output": "## 👥 ロール出力",
        "scratchpad": "## 📝 スクラッチパッド",
        "consensus": "## 🗳️ コンセンサス決定",
        "compression": "## 📦 コンテキスト圧縮",
        "memory": "## 🧠 メモリシステム",
        "permission": "## 🔒 権限チェック",
        "skill": "## ⚡ スキル学習",
        "quality": "## 🛡️ テスト品質監査",
        "errors": "## ⚠️ エラー",
        "mock_banner": "> ⚠️ **モックモード** — これはシミュレーション出力です。実際のLLMは呼び出されていません。",
        "mock_hint": "> 実際のAI分析には `--backend openai`（または `anthropic`）と有効なAPIキーを使用してください。",
        "no_output": "*(出力なし)*",
        "no_summary": "(サマリーなし)",
        "next_steps": "## 🔄 次のステップ",
    },
}


@dataclass
class PerformanceMetric:
    """单次性能指标"""

    timestamp: str
    task_description: str
    total_duration: float
    step_timings: dict[str, float]
    success: bool
    error_count: int
    role_count: int

    def __post_init__(self) -> None:
        if len(self.task_description) > 50:
            self.task_description = self.task_description[:50] + "..."


@dataclass
class PerformanceThresholds:
    """Performance threshold configuration for monitoring.

    Defines warning and critical thresholds for total duration
    and individual pipeline step durations.

    Attributes:
        total_duration_warning: Warning threshold for total dispatch time (seconds)
        total_duration_critical: Critical threshold for total dispatch time (seconds)
        step_warnings: Per-step warning thresholds (step_name → seconds)
        step_criticals: Per-step critical thresholds (step_name → seconds)

    Default Steps:
        - analyze: Intent analysis phase
        - warmup: Startup warmup phase
        - plan: Task planning phase
        - spawn: Worker creation phase
        - execute: Main execution phase (longest)
        - collect: Result collection phase
        - consensus: Consensus decision phase
        - compress: Context compression phase
        - permission: Permission checking phase
        - memory: Memory bridge operations
        - skillify: Skill learning phase

    Example:
        >>> thresholds = PerformanceThresholds(
        ...     total_duration_warning=20.0,
        ...     total_duration_critical=45.0,
        ... )
    """

    total_duration_warning: float = 30.0
    total_duration_critical: float = 60.0
    step_warnings: dict[str, float] = field(
        default_factory=lambda: {
            "analyze": 2.0,
            "warmup": 1.0,
            "plan": 3.0,
            "spawn": 1.0,
            "execute": 20.0,
            "collect": 2.0,
            "consensus": 5.0,
            "compress": 1.0,
            "permission": 0.5,
            "memory": 2.0,
            "skillify": 2.0,
        }
    )
    step_criticals: dict[str, float] = field(
        default_factory=lambda: {
            "analyze": 5.0,
            "warmup": 3.0,
            "plan": 8.0,
            "spawn": 3.0,
            "execute": 45.0,
            "collect": 5.0,
            "consensus": 10.0,
            "compress": 3.0,
            "permission": 1.0,
            "memory": 5.0,
            "skillify": 5.0,
        }
    )


@dataclass(slots=True)
class DispatchResult:
    """调度结果"""

    success: bool
    task_description: str
    matched_roles: list[str] = field(default_factory=list)
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    scratchpad_summary: str = ""
    consensus_records: list[dict[str, Any]] = field(default_factory=list)
    compression_info: dict[str, Any] | None = None
    memory_stats: dict[str, Any] | None = None
    permission_checks: list[dict[str, Any]] = field(default_factory=list)
    skill_proposals: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    worker_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    quality_report: str | None = None
    lang: str = "zh"
    concern_packs: list[dict[str, Any]] = field(default_factory=list)
    anchor_result: dict[str, Any] | None = None
    suggested_next_steps: list[str] = field(default_factory=list)
    retrospective_report: dict[str, Any] | None = None
    intent_match: dict[str, Any] | None = None
    five_axis_result: dict[str, Any] | None = None
    # V3.8 #2: Two-stage review gate result
    two_stage_review: dict[str, Any] | None = None
    # V3.8 #3: Severity router auto-fix result
    auto_fix_result: dict[str, Any] | None = None
    # V3.8 #4: Judge agent consolidation result
    judge_result: dict[str, Any] | None = None
    # V3.8 #7: Micro-task plan (when use_micro_tasks=True)
    micro_task_plan: dict[str, Any] | None = None
    # V3.9-02: RBAC permission check result (when DispatchRBAC is configured)
    permission_result: dict[str, Any] | None = None
    # V3.9-02: Audit log entries collected during dispatch (when
    # DispatchAuditLogger is configured)
    audit_entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the dispatch result to a dictionary.

        Returns:
            Dictionary containing all dispatch result fields with rounded duration.
        """
        return {
            "success": self.success,
            "task_description": self.task_description,
            "matched_roles": self.matched_roles,
            "summary": self.summary,
            "details": self.details,
            "scratchpad_summary": self.scratchpad_summary,
            "consensus_records": self.consensus_records,
            "compression_info": self.compression_info,
            "memory_stats": self.memory_stats,
            "permission_checks": self.permission_checks,
            "skill_proposals": self.skill_proposals,
            "duration_seconds": round(self.duration_seconds, 2),
            "worker_results": self.worker_results,
            "errors": self.errors,
            "quality_report": self.quality_report,
            "concern_packs": self.concern_packs,
            "anchor_result": self.anchor_result,
            "suggested_next_steps": self.suggested_next_steps,
            "retrospective_report": self.retrospective_report,
            "intent_match": self.intent_match,
            "five_axis_result": self.five_axis_result,
            "two_stage_review": self.two_stage_review,
            "auto_fix_result": self.auto_fix_result,
            "judge_result": self.judge_result,
            "micro_task_plan": self.micro_task_plan,
            "permission_result": self.permission_result,
            "audit_entries": self.audit_entries,
        }

    def to_markdown(self) -> str:
        """Render the dispatch result as a localized Markdown report.

        Returns:
            Markdown string with task status, duration, roles, summary, and worker outputs.
        """
        t = I18N.get(self.lang, I18N["zh"])
        sections = [
            self._format_mock_banner(t),
            self._format_header(t),
            self._format_worker_results(t),
            self._format_scratchpad(t),
            self._format_consensus(t),
            self._format_compression(t),
            self._format_memory(t),
            self._format_permission(t),
            self._format_skill(t),
            self._format_quality(t),
            self._format_next_steps(t),
            self._format_errors(t),
            self._format_concern_packs(),
            self._format_anchor(),
            self._format_intent_match(),
            self._format_five_axis(),
            self._format_retrospective(),
        ]
        lines: list[str] = []
        for section in sections:
            lines.extend(section)
        return "\n".join(lines)

    def _format_mock_banner(self, t: dict[str, str]) -> list[str]:
        is_mock = any("[MOCK MODE]" in (wr.get("output", "") or "") for wr in (self.worker_results or []))
        if not is_mock:
            return []
        return [t["mock_banner"], t["mock_hint"], ""]

    def _format_header(self, t: dict[str, str]) -> list[str]:
        return [
            t["title"],
            "",
            f"{t['task']}: {self.task_description}",
            f"**{t['status_label']}**: {t['status_ok'] if self.success else t['status_fail']}",
            f"{t['duration']}: {self.duration_seconds:.2f}s",
            f"{t['roles']}: {', '.join(self.matched_roles)}",
            "",
            t["summary"],
            self.summary or t["no_summary"],
        ]

    def _format_worker_results(self, t: dict[str, str]) -> list[str]:
        if not self.worker_results:
            return []
        role_icons = {
            "architect": "🏗️",
            "product-manager": "📋",
            "security": "🔒",
            "tester": "🧪",
            "solo-coder": "💻",
            "devops": "⚙️",
            "ui-designer": "🎨",
        }
        lines = ["", t["output"]]
        for wr in self.worker_results:
            role_id = wr.get("role_id", wr.get("role", "unknown"))
            role_name = wr.get("role_name", wr.get("role", "unknown"))
            status_icon = "✅" if wr.get("success") else "❌"
            icon = role_icons.get(role_id, "🤖")
            output = wr.get("output", "") or ""
            lines.append("")
            lines.append(f"### {icon} {role_name} [{status_icon}]")
            lines.append("---")
            lines.append(output if output else t["no_output"])
        return lines

    def _format_scratchpad(self, t: dict[str, str]) -> list[str]:
        if not self.scratchpad_summary:
            return []
        return ["", t["scratchpad"], self.scratchpad_summary]

    def _format_consensus(self, t: dict[str, str]) -> list[str]:
        if not self.consensus_records:
            return []
        lines = ["", t["consensus"]]
        for cr in self.consensus_records:
            icon = "✅" if cr.get("outcome") == "APPROVED" else "⚠️"
            lines.append(f"- [{icon}] {cr.get('topic', '')}: {cr.get('outcome', '')}")
        return lines

    def _format_compression(self, t: dict[str, str]) -> list[str]:
        if not self.compression_info:
            return []
        ci = self.compression_info
        return [
            "",
            t["compression"],
            f"- {t['duration'].replace('**', '')}: {ci.get('level', 'N/A')}",
            f"- {ci.get('original_tokens', 0)} tokens → {ci.get('compressed_tokens', 0)} tokens ({ci.get('reduction_pct', 0)}%)",
        ]

    def _format_memory(self, t: dict[str, str]) -> list[str]:
        if not self.memory_stats:
            return []
        ms = self.memory_stats
        return [
            "",
            t["memory"],
            f"- Total: {ms.get('total_memories', 0)}",
            f"- Knowledge: {ms.get('knowledge_count', 0)}",
            f"- Episodic: {ms.get('episodic_count', 0)}",
        ]

    def _format_permission(self, t: dict[str, str]) -> list[str]:
        if not self.permission_checks:
            return []
        lines = ["", t["permission"]]
        for pc in self.permission_checks:
            icon = "✅" if pc.get("allowed") else "🚫"
            lines.append(f"- [{icon}] {pc.get('action', '')}: {pc.get('decision', '')}")
        return lines

    def _format_skill(self, t: dict[str, str]) -> list[str]:
        if not self.skill_proposals:
            return []
        lines = ["", t["skill"]]
        for sp in self.skill_proposals:
            lines.append(f"- 📌 {sp.get('title', 'New Skill')}: {sp.get('confidence', 0):.0%}")
        return lines

    def _format_quality(self, t: dict[str, str]) -> list[str]:
        if not self.quality_report:
            return []
        return ["", t["quality"], self.quality_report]

    def _format_next_steps(self, t: dict[str, str]) -> list[str]:
        # Suggested next steps
        if not self.suggested_next_steps:
            return []
        i18n_next = t.get("next_steps", "## 🔄 Suggested Next Steps")
        lines = ["", i18n_next]
        for i, step in enumerate(self.suggested_next_steps, 1):
            lines.append(f"{i}. {step}")
        return lines

    def _format_errors(self, t: dict[str, str]) -> list[str]:
        if not self.errors:
            return []
        lines = ["", t["errors"]]
        for e in self.errors:
            lines.append(f"- {e}")
        return lines

    def _format_concern_packs(self) -> list[str]:
        if not self.concern_packs:
            return []
        lines = ["", "## 🧩 关注点增强包"]
        for cp in self.concern_packs:
            lines.append(f"- **{cp.get('name', '')}**: {cp.get('description', '')}")
        return lines

    def _format_anchor(self) -> list[str]:
        if not self.anchor_result:
            return []
        ar = self.anchor_result
        lines = ["", "## ⚓ Anchor 对齐检查", f"- 对齐状态: {'✅ 通过' if ar.get('aligned') else '⚠️ 偏移'}"]
        if ar.get("details"):
            lines.append(f"- 详情: {ar['details']}")
        return lines

    def _format_intent_match(self) -> list[str]:
        if not self.intent_match:
            return []
        im = self.intent_match
        return [
            "",
            "## 🎯 意图匹配",
            f"- 意图: {im.get('intent', 'N/A')}",
            f"- 置信度: {im.get('confidence', 0):.0%}",
        ]

    def _format_five_axis(self) -> list[str]:
        if not self.five_axis_result:
            return []
        fr = self.five_axis_result
        lines = ["", "## 🌟 五轴共识审查"]
        for axis, result in fr.items() if isinstance(fr, dict) else []:
            lines.append(f"- {axis}: {result}")
        return lines

    def _format_retrospective(self) -> list[str]:
        if not self.retrospective_report:
            return []
        rr = self.retrospective_report
        lines = ["", "## 📊 回顾分析"]
        if isinstance(rr, dict):
            for key, val in rr.items():
                lines.append(f"- {key}: {val}")
        else:
            lines.append(str(rr))
        return lines
