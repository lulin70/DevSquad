#!/usr/bin/env python3
import re
from typing import Any

from .models import ROLE_REGISTRY

ROLE_TEMPLATES = {
    rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()
}

_I18N_SUMMARY: dict[str, dict[str, str]] = {
    "zh": {
        "task_done": "任务「{task}」已完成多Agent协作。",
        "roles": "参与角色: {roles} ({count}个)",
        "workers_ok": "执行结果: {done}/{total} 个Worker成功",
        "duration": "协作耗时: {dur:.2f}s",
        "sp_findings": "Scratchpad关键发现: {sp}",
    },
    "en": {
        "task_done": 'Task "{task}" completed with multi-agent collaboration.',
        "roles": "Roles: {roles} ({count})",
        "workers_ok": "Workers: {done}/{total} succeeded",
        "duration": "Duration: {dur:.2f}s",
        "sp_findings": "Scratchpad findings: {sp}",
    },
    "ja": {
        "task_done": "タスク「{task}」がマルチエージェントコラボレーションで完了しました。",
        "roles": "参加ロール: {roles} ({count})",
        "workers_ok": "実行結果: {done}/{total} Worker成功",
        "duration": "所要時間: {dur:.2f}s",
        "sp_findings": "スクラッチパッド発見: {sp}",
    },
}

_ROLE_I18N = {
    "zh": {
        "architect": "架构师",
        "product-manager": "产品经理",
        "security": "安全专家",
        "tester": "测试专家",
        "solo-coder": "开发者",
        "devops": "运维工程师",
        "ui-designer": "UI设计师",
    },
    "en": {
        "architect": "Architect",
        "product-manager": "Product Manager",
        "security": "Security Expert",
        "tester": "Tester",
        "solo-coder": "Coder",
        "devops": "DevOps",
        "ui-designer": "UI Designer",
    },
    "ja": {
        "architect": "アーキテクト",
        "product-manager": "プロダクトマネージャー",
        "security": "セキュリティ専門家",
        "tester": "テスター",
        "solo-coder": "コーダー",
        "devops": "DevOps",
        "ui-designer": "UIデザイナー",
    },
}

_CONSENSUS_OUTCOME_BADGES: dict[str, str] = {
    "APPROVED": "🟢 通过",
    "REJECTED": "🔴 否决",
    "SPLIT": "🟡 分歧",
    "ESCALATED": "🔵 升级",
}
_ACTION_PRIORITY_BADGES: dict[str, str] = {"H": "🔴高", "M": "🟡中", "L": "🟢低"}


class ReportFormatter:
    """Report formatting engine for DispatchResult."""

    def __init__(self, lang: str = "zh"):
        self.lang = lang
        self._t = _I18N_SUMMARY.get(lang, _I18N_SUMMARY["zh"])
        self._role_names = _ROLE_I18N.get(lang, _ROLE_I18N["zh"])

    def build_summary(self, task: str, roles: list[str], exec_result: Any, sp_summary: str) -> str:
        """Build a localized plain-text summary of a dispatch execution.

        Args:
            task: The task description string.
            roles: List of role identifiers that participated.
            exec_result: Execution result object with ``results`` and
                ``duration_seconds`` attributes.
            sp_summary: Scratchpad findings summary string.

        Returns:
            Newline-joined summary string with task, roles, worker status,
            duration, and scratchpad findings.
        """
        t = self._t
        role_names = [str(self._role_names.get(r, ROLE_TEMPLATES.get(r, {}).get("name", r))) for r in roles]
        parts = [
            t["task_done"].format(task=task[:80]),
            t["roles"].format(roles=", ".join(role_names), count=len(roles)),
        ]
        if exec_result.results:
            done = sum(1 for r in exec_result.results if r.success)
            parts.append(t["workers_ok"].format(done=done, total=len(exec_result.results)))
        if exec_result.duration_seconds:
            parts.append(t["duration"].format(dur=exec_result.duration_seconds))
        if sp_summary:
            parts.append(t["sp_findings"].format(sp=sp_summary[:200]))
        return "\n".join(parts)

    def format_structured_report(self, result: Any, include_action_items: bool = True, include_timing: bool = False) -> str:
        """
        Generate structured report (v3.2 UI Designer spec).

        Report hierarchy: Summary card -> Role assignments -> Key findings
                          -> Conflict resolution -> Action items
        """
        lines: list[str] = []
        sections = [
            self._format_summary_card(result),
            self._format_role_assignments(result),
            self._format_findings_section(result),
            self._format_consensus_section(result),
            self._format_action_items_section(result, include_action_items),
            self._format_system_info(result),
            self._format_timing_section(result, include_timing),
            self._format_errors_section(result),
        ]
        for section in sections:
            lines.extend(section)
        return "\n".join(lines)

    def _format_summary_card(self, result: Any) -> list[str]:
        status_icon = "✅" if result.success else "❌"
        status_text = "协作完成" if result.success else "协作异常"
        lines = [
            f"# {status_icon} Multi-Agent 协作报告",
            "",
            "---",
            "## 📋 任务摘要",
            "",
            "| 项目 | 内容 |",
            "|------|------|",
            f"| **任务** | {result.task_description[:100]} |",
            f"| **状态** | {status_text} |",
            f"| **参与角色** | {len(result.matched_roles)} 个 ({', '.join(result.matched_roles)}) |",
            f"| **总耗时** | {result.duration_seconds:.2f}s |",
        ]
        if result.worker_results:
            success_count = sum(1 for w in result.worker_results if w.get("success"))
            total_count = len(result.worker_results)
            lines.append(
                f"| **执行成功率** | {success_count}/{total_count} ({success_count / total_count * 100:.0f}%) |"
            )
        if result.errors:
            lines.append(f"| **错误数** | {len(result.errors)} |")
        lines.extend(["", "---", ""])
        return lines

    def _format_role_assignments(self, result: Any) -> list[str]:
        if not result.worker_results:
            return []
        lines = [
            "## 👥 角色分配与产出",
            "",
            "| 角色 | 状态 | 核心产出 (预览) |",
            "|------|------|----------------|",
        ]
        for wr in result.worker_results:
            role_name = wr.get("role", "unknown")
            role_display = ROLE_TEMPLATES.get(role_name, {}).get("name", role_name)
            status_icon = "✅" if wr.get("success") else "❌"
            output_preview = (wr.get("output") or "(无输出)")[:80].replace("\n", " ")
            lines.append(f"| **{role_display}** | {status_icon} | {output_preview} |")
        lines.extend(["", "---", ""])
        return lines

    def _format_findings_section(self, result: Any) -> list[str]:
        if not result.scratchpad_summary:
            return []
        lines = ["## 🔍 关键发现", ""]
        findings = self.extract_findings(result.scratchpad_summary)
        if findings:
            for i, finding in enumerate(findings[:8], 1):
                lines.append(f"{i}. {finding}")
        else:
            lines.append(f"> {result.scratchpad_summary[:300]}")
        lines.extend(["", "---", ""])
        return lines

    def _format_consensus_section(self, result: Any) -> list[str]:
        if not result.consensus_records:
            return []
        lines = ["## 🗳️ 共识决策与冲突解决", ""]
        for cr in result.consensus_records:
            topic = cr.get("topic", "未知议题")
            outcome = cr.get("outcome", "")
            decision = cr.get("final_decision", "")
            badge = _CONSENSUS_OUTCOME_BADGES.get(outcome, "⏪ 超时")
            votes_for = cr.get("votes_for", 0)
            votes_against = cr.get("votes_against", 0)
            votes_abstain = cr.get("votes_abstain", 0)
            lines.append(f"- **{topic}** `{badge}`")
            lines.append(f"  - 投票: ✅{votes_for} ❌{votes_against} ⚪{votes_abstain}")
            if decision:
                lines.append(f"  - 决策: {decision[:100]}")
            lines.append("")
        lines.extend(["---", ""])
        return lines

    def _format_action_items_section(self, result: Any, include_action_items: bool) -> list[str]:
        if not include_action_items:
            return []
        action_items = self.generate_action_items(result)
        if not action_items:
            return []
        lines = ["## 📌 行动项建议", ""]
        for i, item in enumerate(action_items, 1):
            priority = item.get("priority", "M")
            priority_badge = _ACTION_PRIORITY_BADGES.get(priority, "⚪")
            lines.append(f"{i}. [{priority_badge}] {item['text']}")
        lines.append("")
        return lines

    def _format_system_info(self, result: Any) -> list[str]:
        ext_sections: list[str] = []
        if result.compression_info:
            ci = result.compression_info
            ext_sections.append(
                f"**上下文压缩**: 级别={ci.get('level', 'N/A')} | "
                f"{ci.get('original_tokens', 0)}→{ci.get('compressed_tokens', 0)} tokens | "
                f"节省 {ci.get('reduction_pct', 0)}%"
            )
        if result.memory_stats:
            ms = result.memory_stats
            ext_sections.append(
                f"**记忆系统**: 总记忆={ms.get('total_memories', 0)} | 捕获次数={ms.get('total_captures', 0)}"
            )
        if result.skill_proposals:
            proposals = [f"{p.get('title', '')}({p.get('confidence', 0):.0%})" for p in result.skill_proposals[:3]]
            ext_sections.append(f"**技能提案**: {', '.join(proposals)}")
        if result.permission_checks:
            allowed = sum(1 for pc in result.permission_checks if pc.get("allowed"))
            total_pc = len(result.permission_checks)
            ext_sections.append(f"**权限检查**: {allowed}/{total_pc} 通过")
        if not ext_sections:
            return []
        lines = ["---", "", "> **系统信息**"]
        for section in ext_sections:
            lines.append(f"> {section}")
        lines.append("")
        return lines

    def _format_timing_section(self, result: Any, include_timing: bool) -> list[str]:
        if not (include_timing and result.details.get("timing")):
            return []
        timing = result.details["timing"]
        lines = [
            "",
            "<details>",
            "<summary>⏱️ 各阶段耗时详情</summary>",
            "",
            "| 阶段 | 耗时(s) |",
            "|------|---------|",
        ]
        for stage, duration in timing.items():
            if duration > 0.001:
                lines.append(f"| {stage} | {duration:.3f} |")
        lines.extend(["", "</details>", ""])
        return lines

    def _format_errors_section(self, result: Any) -> list[str]:
        if not result.errors:
            return []
        lines = ["", "> ⚠️ **错误/警告**:"]
        for err in result.errors[:5]:
            lines.append(f"> - {err[:150]}")
        return lines

    def format_compact_report(self, result: Any) -> str:
        """Generate compact report suitable for terminal quick view."""
        status = "✅" if result.success else "❌"
        roles_str = ", ".join(result.matched_roles) if result.matched_roles else "无"

        parts = [
            f"[{status}] 任务: {result.task_description[:60]}",
            f"角色: {roles_str} ({len(result.matched_roles)}个)",
            f"耗时: {result.duration_seconds:.2f}s",
        ]

        if result.worker_results:
            done = sum(1 for w in result.worker_results if w.get("success"))
            parts.append(f"Worker: {done}/{len(result.worker_results)} 成功")

        if result.scratchpad_summary:
            parts.append(f"发现: {result.scratchpad_summary[:120]}")

        if result.consensus_records:
            approved = sum(1 for c in result.consensus_records if c.get("outcome") == "APPROVED")
            parts.append(f"共识: {approved}/{len(result.consensus_records)} 通过")

        if result.errors:
            parts.append(f"错误: {len(result.errors)} 个")

        return "\n".join(parts)

    def extract_findings(self, scratchpad_summary: str) -> list[str]:
        """
        Extract key findings from Scratchpad summary text.

        Supports: numbered lists, bullet lists, semicolon-separated, sentence splitting.
        """
        if not scratchpad_summary:
            return []

        findings = []
        text = scratchpad_summary.strip()

        numbered = re.findall(r"(?:^|\n)\s*(\d+)[\.\、\)]\s*(.+?)(?=\n\s*\d+[\.\、\)]|\Z)", text, re.MULTILINE)
        if numbered and len(numbered) >= 2:
            findings = [item.strip() for _, item in numbered]
            return [f for f in findings if f]

        bulleted = re.findall(r"(?:^|\n)\s*[-*•]\s*(.+?)(?=\n\s*[-*•]|\Z)", text, re.MULTILINE)
        if bulleted and len(bulleted) >= 2:
            findings = [item.strip() for item in bulleted]
            return [f for f in findings if f]

        if ";" in text and text.count(";") >= 2:
            findings = [f.strip() for f in text.split(";") if f.strip()]
            return findings[:10]

        sentences = re.split(r"[。！？.!?\n]+", text)
        findings = [s.strip() for s in sentences if len(s.strip()) >= 10]
        return findings[:8]

    def generate_action_items(self, result: Any) -> list[dict[str, str]]:
        """
        Auto-generate action item suggestions based on dispatch result.

        Rules:
        - Errors -> High priority fix suggestions
        - Unresolved conflicts -> Medium priority manual review
        - All success -> Low priority follow-up optimization
        - Memory data -> Suggest reviewing historical decisions
        """
        items = []

        if result.errors:
            items.append(
                {"priority": "H", "text": f"修复 {len(result.errors)} 个执行错误，首要关注: {result.errors[0][:80]}"}
            )

        unresolved = [c for c in result.consensus_records if c.get("outcome") in ("SPLIT", "ESCALATED", "TIMEOUT")]
        if unresolved:
            items.append(
                {
                    "priority": "H" if len(unresolved) > 2 else "M",
                    "text": f"人工审核 {len(unresolved)} 个未决共识议题: {', '.join([u.get('topic', '') for u in unresolved[:3]])}",
                }
            )

        failed_workers = [w for w in result.worker_results if not w.get("success")]
        if failed_workers:
            roles_failed = [
                ROLE_TEMPLATES.get(w.get("role", ""), {}).get("name", w.get("role", "")) for w in failed_workers
            ]
            items.append({"priority": "M", "text": f"排查以下角色执行失败原因: {', '.join(roles_failed[:3])}"})

        if result.success and not result.errors:
            if result.memory_stats and result.memory_stats.get("total_memories", 0) > 0:
                items.append(
                    {
                        "priority": "L",
                        "text": f"回顾历史记忆 (共{result.memory_stats['total_memories']}条)，提取可复用经验",
                    }
                )

            if result.skill_proposals and len(result.skill_proposals) > 0:
                top_proposal = result.skill_proposals[0]
                items.append(
                    {
                        "priority": "L",
                        "text": f"评估新技能提案「{top_proposal.get('title', '')}」(置信度{top_proposal.get('confidence', 0):.0%})是否值得固化",
                    }
                )

            items.append({"priority": "L", "text": "任务已完成，可归档此协作记录供未来参考"})

        if not items:
            items.append({"priority": "M", "text": "审查各角色产出内容，确认是否符合预期"})

        return items[:6]
