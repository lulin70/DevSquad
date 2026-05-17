"""Retrospective Skill - V3.6.0"""

from skills.registry import BaseSkill
from scripts.collaboration.retrospective import RetrospectiveEngine
from scripts.collaboration.models import (
    StructuredGoal,
    GoalItem,
    GoalItemStatus,
    AnchorResult,
    AnchorTrigger,
)


class RetrospectiveSkill(BaseSkill):
    name = "retrospective"
    description = "项目复盘 - 提取改进模式/生成可执行建议/复盘摘要"
    version = "3.6.0"

    CAPABILITIES = [
        "post_dispatch_analysis",
        "pattern_extraction",
        "improvement_suggestion",
    ]

    OUTPUT_FORMATS = ["findings", "patterns", "improvements", "summary"]

    def run(self, action="info", **kwargs):
        actions = {
            "run_retrospective": self.run_retrospective,
            "extract_patterns": self.extract_patterns,
            "generate_improvements": self.generate_improvements,
            "summary": self.summary,
        }
        fn = actions.get(action)
        if not fn:
            return {"error": f"Unknown action: {action}. Available: {list(actions.keys())}"}
        return fn(**kwargs)

    def _mock_goal(self, task: str = "") -> StructuredGoal:
        desc = task or "模拟任务：完成功能开发并修复已知问题"
        return StructuredGoal(
            goal_id="retro_mock_001",
            original_description=desc,
            items=[
                GoalItem(item_id="item_001", description=desc, status=GoalItemStatus.FULLY_COVERED, coverage_score=1.0),
            ],
        )

    def _mock_anchor_history(self) -> list:
        return [
            AnchorResult(aligned=True, trigger=AnchorTrigger.MILESTONE, coverage=0.8, drift_score=0.05),
            AnchorResult(aligned=True, trigger=AnchorTrigger.PHASE_GATE, coverage=0.9, drift_score=0.02),
            AnchorResult(aligned=False, trigger=AnchorTrigger.DIRECTION_CHANGE, coverage=0.7, drift_score=0.35),
            AnchorResult(aligned=True, trigger=AnchorTrigger.STEP_COMPLETE, coverage=0.95, drift_score=0.01),
        ]

    def run_retrospective(self, dispatch_result: dict = None, task: str = "") -> dict:
        engine = RetrospectiveEngine()
        goal = self._mock_goal(task)
        history = self._mock_anchor_history()
        report = engine.run(goal=goal, anchor_history=history)
        result = report.to_dict() if hasattr(report, 'to_dict') else {
            "task_goal": report.task_goal,
            "deviations": [d.__dict__ for d in report.deviations],
            "redundant_steps": report.redundant_steps,
            "improvements": report.improvements,
            "summary": report.summary,
        }
        if dispatch_result:
            result["dispatch_context"] = dispatch_result
        return result

    def extract_patterns(self, history_items: list = None) -> dict:
        items = history_items or [
            {"type": "goal_drift", "count": 3},
            {"type": "redundant_step", "count": 2},
            {"type": "late_error_detection", "count": 4},
        ]
        patterns = {}
        for item in items:
            t = item.get("type", "unknown")
            patterns[t] = patterns.get(t, 0) + item.get("count", 1)
        top_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "total_items": len(items),
            "patterns": [{"type": t, "occurrences": c} for t, c in top_patterns],
            "insight": f"最频繁模式: {top_patterns[0][0] if top_patterns else 'N/A'} ({top_patterns[0][1] if top_patterns else 0}次)",
        }

    def generate_improvements(self, findings: list) -> dict:
        if not findings:
            findings = ["goal_drift", "missing_anchor_checks"]
        improvement_map = {
            "goal_drift": "增加中间锚点检查以尽早发现目标偏移",
            "missing_anchor_checks": "在关键决策点添加 AnchorCheck 验证",
            "redundant_steps": "优化工作流消除重复步骤",
            "late_error_detection": "前置错误检测点，缩短反馈循环",
            "low_coverage": "补充缺失的测试维度和边界用例",
        }
        improvements = [improvement_map.get(f, f"针对 {f} 的改进建议") for f in findings]
        return {
            "findings_count": len(findings),
            "improvements": improvements,
            "priority": "high" if len(findings) > 3 else "medium",
        }

    def summary(self, retro_result: dict = None) -> dict:
        if retro_result:
            deviations = retro_result.get("deviations", [])
            improvements = retro_result.get("improvements", [])
            s = retro_result.get("summary", "")
        else:
            full = self.run_retrospective()
            deviations = full.get("deviations", [])
            improvements = full.get("improvements", [])
            s = full.get("summary", "")
        went_well = [f"目标覆盖率达标" if not deviations else "任务已完成"]
        to_improve = improvements[:5] if improvements else ["保持当前流程"]
        return {
            "what_went_well": went_well,
            "what_to_improve": to_improve,
            "deviation_count": len(deviations),
            "improvement_count": len(improvements),
            "raw_summary": s,
        }
