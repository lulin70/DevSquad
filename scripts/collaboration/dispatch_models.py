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
from datetime import datetime
from typing import Any, Dict, List, Optional

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


@dataclass
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
    retrospective_report: dict[str, Any] | None = None
    intent_match: dict[str, Any] | None = None
    five_axis_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
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
            "retrospective_report": self.retrospective_report,
            "intent_match": self.intent_match,
            "five_axis_result": self.five_axis_result,
        }

    def to_markdown(self) -> str:
        t = I18N.get(self.lang, I18N["zh"])
        is_mock = any("[MOCK MODE]" in (wr.get("output", "") or "") for wr in (self.worker_results or []))
        lines = []
        if is_mock:
            lines.extend([t["mock_banner"], t["mock_hint"], ""])
        lines.extend(
            [
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
        )
        if self.worker_results:
            lines.append("")
            lines.append(t["output"])
            role_icons = {
                "architect": "🏗️",
                "product-manager": "📋",
                "security": "🔒",
                "tester": "🧪",
                "solo-coder": "💻",
                "devops": "⚙️",
                "ui-designer": "🎨",
            }
            for wr in self.worker_results:
                role_id = wr.get("role_id", wr.get("role", "unknown"))
                role_name = wr.get("role_name", wr.get("role", "unknown"))
                status_icon = "✅" if wr.get("success") else "❌"
                icon = role_icons.get(role_id, "🤖")
                output = wr.get("output", "") or ""
                lines.append("")
                lines.append(f"### {icon} {role_name} [{status_icon}]")
                lines.append("---")
                if output:
                    lines.append(output)
                else:
                    lines.append(t["no_output"])
        if self.scratchpad_summary:
            lines.extend(["", t["scratchpad"], self.scratchpad_summary])
        if self.consensus_records:
            lines.append("")
            lines.append(t["consensus"])
            for cr in self.consensus_records:
                icon = "✅" if cr.get("outcome") == "APPROVED" else "⚠️"
                lines.append(f"- [{icon}] {cr.get('topic', '')}: {cr.get('outcome', '')}")
        if self.compression_info:
            ci = self.compression_info
            lines.extend(
                [
                    "",
                    t["compression"],
                    f"- {t['duration'].replace('**', '')}: {ci.get('level', 'N/A')}",
                    f"- {ci.get('original_tokens', 0)} tokens → {ci.get('compressed_tokens', 0)} tokens ({ci.get('reduction_pct', 0)}%)",
                ]
            )
        if self.memory_stats:
            ms = self.memory_stats
            lines.extend(
                [
                    "",
                    t["memory"],
                    f"- Total: {ms.get('total_memories', 0)}",
                    f"- Knowledge: {ms.get('knowledge_count', 0)}",
                    f"- Episodic: {ms.get('episodic_count', 0)}",
                ]
            )
        if self.permission_checks:
            lines.append("")
            lines.append(t["permission"])
            for pc in self.permission_checks:
                icon = "✅" if pc.get("allowed") else "🚫"
                lines.append(f"- [{icon}] {pc.get('action', '')}: {pc.get('decision', '')}")
        if self.skill_proposals:
            lines.append("")
            lines.append(t["skill"])
            for sp in self.skill_proposals:
                lines.append(f"- 📌 {sp.get('title', 'New Skill')}: {sp.get('confidence', 0):.0%}")
        if self.quality_report:
            lines.extend(["", t["quality"]])
            lines.append(self.quality_report)
        if self.errors:
            lines.extend(["", t["errors"]])
            for e in self.errors:
                lines.append(f"- {e}")
        if self.concern_packs:
            lines.extend(["", "## 🧩 关注点增强包"])
            for cp in self.concern_packs:
                lines.append(f"- **{cp.get('name', '')}**: {cp.get('description', '')}")
        if self.anchor_result:
            lines.extend(["", "## ⚓ Anchor 对齐检查"])
            ar = self.anchor_result
            lines.append(f"- 对齐状态: {'✅ 通过' if ar.get('aligned') else '⚠️ 偏移'}")
            if ar.get('details'):
                lines.append(f"- 详情: {ar['details']}")
        if self.intent_match:
            lines.extend(["", "## 🎯 意图匹配"])
            im = self.intent_match
            lines.append(f"- 意图: {im.get('intent', 'N/A')}")
            lines.append(f"- 置信度: {im.get('confidence', 0):.0%}")
        if self.five_axis_result:
            lines.extend(["", "## 🌟 五轴共识审查"])
            fr = self.five_axis_result
            for axis, result in fr.items() if isinstance(fr, dict) else []:
                lines.append(f"- {axis}: {result}")
        if self.retrospective_report:
            lines.extend(["", "## 📊 回顾分析"])
            rr = self.retrospective_report
            if isinstance(rr, dict):
                for key, val in rr.items():
                    lines.append(f"- {key}: {val}")
            else:
                lines.append(str(rr))
        return "\n".join(lines)
