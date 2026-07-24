"""V4.3+ Roadmap P2-UI-2: Dashboard Live Browser 模式评估与最小实现。

本模块为 DevSquad Dashboard 提供"实时浏览器迭代模式"的抽象层，
借鉴 pbakaus/impeccable 的 live browser 理念：边审查边修改，实时反馈，
形成 审查→反馈→修改→复审 的闭环。

==============================================================================
评估报告（ROADMAP P2-UI-2）
==============================================================================

1. 架构对比：DevSquad Dashboard (Streamlit) vs impeccable (Playwright)
----------------------------------------------------------------------
| 维度        | impeccable              | DevSquad Dashboard          |
|------------|-------------------------|------------------------------|
| 渲染层      | Playwright 驱动真实浏览器 | Streamlit 服务端渲染         |
| 热重载      | 浏览器内 CSS/JS 即时热替换 | st.rerun() 全量重跑脚本      |
| DOM 探针    | page.evaluate() 单次采集  | 需 Playwright 旁路采集 DOM   |
| 迭代反馈    | 浏览器视口实时可见        | 用户手动刷新 / auto-refresh  |
| 视觉回归    | 同浏览器截图像素 Diff     | PIL ImageChops Diff（已有）  |

impeccable 的核心优势在于"浏览器即画布"——修改 CSS 后无需刷新即可在真实
浏览器视口看到效果。Streamlit 的服务端模型不具备这种能力：每次状态变更都
触发脚本全量重跑，DOM 在请求-响应周期中重建，无法做到 CSS 级热替换。

2. Live browser 模式在 Streamlit 下的可行性分析
------------------------------------------------
- **完全照搬不可行**：Streamlit 没有持久浏览器视口，无法做 CSS 热替换。
  Playwright 的 `page.evaluate()` 探针需要绑定到真实浏览器会话，而
  Streamlit 的 server-side rendering 让 DOM 探针只能通过旁路（另起
  Playwright 实例访问 localhost:8501）实现，引入额外复杂度与硬依赖。
- **可借鉴的是"实时反馈"理念**：把 审查→反馈→修改→复审 的迭代闭环
  抽象出来，由 LiveBrowserMode 统一编排 UIUXAnalyzer（4 大维度检测 +
  DeterministicRuleEngine 46 条规则）与 VisualRegressionChecker（像素
  Diff）+ TasteDials（视觉品味阈值），让用户在 Dashboard 迭代 UI 时
  获得与 impeccable 同构的"边改边审"体验，只是反馈粒度从"CSS 热替换"
  降级为"会话级复审"。
- **Mock 模式保底**：无 Playwright/Pillow 时，review() 返回基于
  review_axes 的模板化 issues，保证迭代闭环可演示、可测试。

3. 推荐的集成路径
-----------------
(a) UIUXAnalyzer 协同（已落地）：当会话提供 dom_data 或 playwright_page
    时，LiveBrowserMode 调用 UIUXAnalyzer.audit_dom_data() / audit()
    执行真实巡检。注意：原 ROADMAP 描述的 UIUXAnalyzer.qa_audit_url()
    方法在当前代码库中不存在（实测确认），实际可用入口为 audit(page, url)
    与 audit_dom_data(data, url)。本模块据此对接，未修改现有源码。
(b) 热重载方案（可选增强）：在 Dashboard 侧引入 streamlit-autorefresh
    或 st.rerun() 触发的轮询，配合 LiveBrowserMode.re_review() 在每次
    迭代后自动复审；这是 Streamlit 下最接近"热重载"的可行路径，无需
    Playwright。
(c) 用户工作流：start_session → review → (查看 issues) → suggest_fixes
    → (应用修复) → re_review → end_session，全程在 Dashboard UI 内驱动，
    历史持久化到 session["history"]，可渲染为迭代趋势图。

4. 不照搬 Playwright 的理由
---------------------------
- Playwright 是重量级依赖（~300MB 浏览器二进制），与 DevSquad "Mock
  模式默认、软依赖"原则冲突；强制引入会破坏 CI 轻量化。
- Streamlit 架构下 Playwright 只能作为旁路探针，无法复用 impeccable
  的"浏览器即画布"热替换能力，投入产出比低。
- 已有 UIUXAnalyzer + VisualRegressionChecker + TasteDials 三件套覆盖
  检测能力，缺的只是"迭代闭环编排"，这正是 LiveBrowserMode 补齐的部分。
- Playwright 作为可选软依赖保留：会话提供 playwright_page 时自动启用
  真实模式，否则降级 Mock，二者平滑切换。

==============================================================================

Usage:
    mode = LiveBrowserMode()
    session = mode.start_session(url="http://localhost:8501", target_views=["main", "sidebar"])
    feedback = mode.review(session)
    if feedback["issues"]:
        fixes = mode.suggest_fixes(session, feedback["issues"])
        # ... user applies fixes ...
        mode.re_review(session)  # Re-review after fixes
    mode.end_session(session)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# 默认审查轴（与 UIUXAnalyzer 4 大维度一致）
DEFAULT_REVIEW_AXES: tuple[str, ...] = ("a11y", "interaction", "layout", "ux_antipattern")
DEFAULT_TARGET_VIEWS: tuple[str, ...] = ("main",)

# 可自动修复的规则集合（基于规则 ID 判定）
# 这些规则的修复通常是机械的、可脚本化的（加 alt、调尺寸、修溢出等）
_AUTO_FIXABLE_RULES: frozenset[str] = frozenset({
    "img_missing_alt",
    "input_missing_label",
    "button_too_small",
    "viewport_overflow",
    "form_no_validation",
    "spacing_4pt_grid",
})

# severity → 修复优先级
_SEVERITY_PRIORITY: dict[str, str] = {
    "critical": "P0",
    "warning": "P1",
    "info": "P2",
}

# severity → score 扣分权重
_SEVERITY_PENALTY: dict[str, float] = {
    "critical": 0.15,
    "warning": 0.08,
    "info": 0.03,
}

# 各规则的修复建议模板（Mock 模式与真实模式共用）
_FIX_SUGGESTIONS: dict[str, dict[str, str]] = {
    "img_missing_alt": {
        "fix_description": "Add alt attribute describing the image purpose",
        "estimated_effort": "low",
    },
    "input_missing_label": {
        "fix_description": "Add <label for=...> or aria-label attribute",
        "estimated_effort": "low",
    },
    "wcag_contrast": {
        "fix_description": "Increase color contrast between text and background to meet WCAG AA",
        "estimated_effort": "medium",
    },
    "button_too_small": {
        "fix_description": "Increase button size to at least 44x44 pixels for touch targets",
        "estimated_effort": "low",
    },
    "focus_outline_removed": {
        "fix_description": "Provide alternative focus indicator (box-shadow, border, etc.)",
        "estimated_effort": "medium",
    },
    "viewport_overflow": {
        "fix_description": "Ensure content fits within viewport or use responsive layout",
        "estimated_effort": "medium",
    },
    "text_truncation": {
        "fix_description": "Ensure truncated text has tooltip or expandable view",
        "estimated_effort": "low",
    },
    "destructive_no_confirm": {
        "fix_description": "Add confirm dialog or data-confirm attribute before destructive action",
        "estimated_effort": "medium",
    },
    "purple_blue_gradient": {
        "fix_description": "Replace purple-blue gradient with a brand-aligned color pair",
        "estimated_effort": "medium",
    },
    "border_left_accent_stripes": {
        "fix_description": "Replace left-accent stripe with a structured callout/banner component",
        "estimated_effort": "medium",
    },
    "gradient_text": {
        "fix_description": "Use a solid color or a subtle text-shadow instead of gradient text",
        "estimated_effort": "medium",
    },
    "glassmorphism_overuse": {
        "fix_description": "Limit backdrop-filter: blur() to at most 2 instances per page",
        "estimated_effort": "low",
    },
    "overused_fonts": {
        "fix_description": "Choose a more distinctive font family that matches the brand",
        "estimated_effort": "low",
    },
    "nested_cards": {
        "fix_description": "Use distinct component types (e.g. .card > .panel) instead of nested cards",
        "estimated_effort": "medium",
    },
    "form_no_validation": {
        "fix_description": "Add required attribute or client-side validation to form inputs",
        "estimated_effort": "low",
    },
    "spacing_4pt_grid": {
        "fix_description": "Use 4pt grid values: 4, 8, 12, 16, 20, 24, 28, 32, ...",
        "estimated_effort": "low",
    },
    "__default__": {
        "fix_description": "Review the issue and apply the appropriate fix",
        "estimated_effort": "medium",
    },
}

# Mock 模式模板化 issues：每个审查轴产出代表性问题（确定性，无随机）
_MOCK_ISSUE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "a11y": [
        {
            "issue_id": "a11y-1",
            "severity": "critical",
            "category": "a11y",
            "rule": "img_missing_alt",
            "element": "img[src='logo.png']",
            "description": "Image missing alt attribute (mock)",
        },
        {
            "issue_id": "a11y-2",
            "severity": "warning",
            "category": "a11y",
            "rule": "wcag_contrast",
            "element": "text: 'Read more'",
            "description": "Contrast ratio 3.20 below WCAG AA 4.5 (mock)",
        },
    ],
    "interaction": [
        {
            "issue_id": "int-1",
            "severity": "warning",
            "category": "interaction",
            "rule": "button_too_small",
            "element": "button: 'OK'",
            "description": "Button size 32x28 below 44x44 (mock)",
        },
        {
            "issue_id": "int-2",
            "severity": "warning",
            "category": "interaction",
            "rule": "focus_outline_removed",
            "element": ":focus",
            "description": "Focus outline removed without replacement (mock)",
        },
    ],
    "layout": [
        {
            "issue_id": "lay-1",
            "severity": "critical",
            "category": "layout",
            "rule": "viewport_overflow",
            "element": "body",
            "description": "Horizontal viewport overflow detected (mock)",
        },
        {
            "issue_id": "lay-2",
            "severity": "info",
            "category": "layout",
            "rule": "text_truncation",
            "element": "span: 'long text...'",
            "description": "Text truncation in use — verify content is not hidden (mock)",
        },
    ],
    "ux_antipattern": [
        {
            "issue_id": "ux-1",
            "severity": "critical",
            "category": "ux_antipattern",
            "rule": "destructive_no_confirm",
            "element": "button: 'Delete'",
            "description": "Destructive action without confirmation (mock)",
        },
        {
            "issue_id": "ux-2",
            "severity": "warning",
            "category": "ux_antipattern",
            "rule": "purple_blue_gradient",
            "element": "linear-gradient(purple, blue)",
            "description": "Purple-blue gradient is the signature AI-generated UI pattern (mock)",
        },
    ],
}


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _compute_score(issues: list[dict[str, Any]]) -> float:
    """根据 issues 的 severity 计算质量分（0.0-1.0，越高越好）。

    扣分权重：critical=0.15, warning=0.08, info=0.03，下限 0.0。
    """
    penalty = sum(_SEVERITY_PENALTY.get(i.get("severity", "info"), 0.03) for i in issues)
    return max(0.0, min(1.0, 1.0 - penalty))


def _issue_key(issue: dict[str, Any]) -> str:
    """生成 issue 的唯一键（rule + element），用于 resolved 判定。"""
    return f"{issue.get('rule', '')}::{issue.get('element', '')}"


def _severity_to_priority(severity: str) -> str:
    """severity 映射到修复优先级 P0/P1/P2。"""
    return _SEVERITY_PRIORITY.get(severity, "P2")


class LiveBrowserMode:
    """Live browser iteration mode for Dashboard UI review.

    Inspired by impeccable's live browser pattern: review UI in real-time,
    provide feedback, iterate changes, re-review — all in a continuous loop.

    Unlike impeccable (which uses Playwright + hot reload), DevSquad Dashboard
    is Streamlit-based. This class provides the iteration loop abstraction
    that coordinates UIUXAnalyzer + VisualRegressionChecker + TasteDials
    for real-time UI quality feedback.

    两种运行模式：
    - **Mock 模式（默认）**：无 Playwright/浏览器时，review() 返回基于
      review_axes 的模板化 issues，保证迭代闭环可演示、可测试。
    - **真实模式**：当 session 提供 ``dom_data`` 或 ``playwright_page`` 时，
      调用 UIUXAnalyzer.audit_dom_data() / audit() 执行真实巡检；
      当提供 ``visual_baseline`` + ``visual_current`` 时，调用
      VisualRegressionChecker 执行像素 Diff。

    Usage:
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501", target_views=["main", "sidebar"])
        feedback = mode.review(session)
        if feedback["issues"]:
            mode.suggest_fixes(session, feedback["issues"])
            # ... user applies fixes ...
            mode.re_review(session)  # Re-review after fixes
        mode.end_session(session)
    """

    def __init__(
        self,
        analyzer: Any | None = None,
        visual_checker: Any | None = None,
    ) -> None:
        """初始化 LiveBrowserMode。

        Args:
            analyzer: 可选的 UIUXAnalyzer 实例（软依赖；为 None 时延迟创建）。
            visual_checker: 可选的 VisualRegressionChecker 实例（软依赖）。
        """
        self._analyzer: Any | None = analyzer
        self._visual_checker: Any | None = visual_checker

    # ── 会话生命周期 ──────────────────────────────────────────────────────

    def start_session(
        self,
        url: str,
        target_views: list[str] | None = None,
        review_axes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Start a live browser review session.

        Args:
            url: Target URL to review (e.g., "http://localhost:8501").
            target_views: List of view names to review (default: ["main"]).
            review_axes: UIUX axes to check
                (default: ["a11y", "interaction", "layout", "ux_antipattern"]).

        Returns:
            Session dict with keys:
                - session_id: str
                - url: str
                - target_views: list[str]
                - review_axes: list[str]
                - started_at: str (ISO timestamp)
                - iteration_count: int (0)
                - history: list (empty)
                - status: "active"
        """
        views = list(target_views) if target_views is not None else list(DEFAULT_TARGET_VIEWS)
        axes = list(review_axes) if review_axes is not None else list(DEFAULT_REVIEW_AXES)
        return {
            "session_id": f"lbm-{uuid.uuid4().hex[:12]}",
            "url": url,
            "target_views": views,
            "review_axes": axes,
            "started_at": _now_iso(),
            "iteration_count": 0,
            "history": [],
            "status": "active",
        }

    def review(self, session: dict[str, Any]) -> dict[str, Any]:
        """Perform a UIUX review on the session's target URL.

        Mock 模式返回基于 review_axes 的模板化 issues；真实模式协调
        UIUXAnalyzer 执行巡检。

        Returns:
            Feedback dict with keys:
                - session_id: str
                - iteration: int
                - issues: list[dict] — UIUXIssue list with severity/category/description
                - summary: str
                - score: float (0.0-1.0)
                - visual_changes: list[dict] — visual regression diff results
                - timestamp: str
        """
        self._require_active(session)
        session["iteration_count"] = session.get("iteration_count", 0) + 1
        axes = session.get("review_axes", list(DEFAULT_REVIEW_AXES))

        dom_data = session.get("dom_data")
        page = session.get("playwright_page")
        if dom_data is not None or page is not None:
            issues = self._review_real(session, dom_data, page)
        else:
            issues = self._review_mock(axes)

        feedback = self._build_feedback(session, issues)
        session.setdefault("history", []).append(feedback)
        session["last_feedback"] = feedback
        return feedback

    def suggest_fixes(
        self,
        session: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Suggest fixes for identified UIUX issues.

        Args:
            session: 当前会话（用于上下文；本方法不修改会话状态）。
            issues: review() 返回的 issues 列表。

        Returns:
            Dict with keys:
                - suggestions: list[dict] — {issue_id, fix_description, priority, estimated_effort}
                - auto_fixable: list[str] — issue_ids that can be auto-fixed
                - manual_fix_required: list[str] — issue_ids needing manual intervention
        """
        self._validate_session(session)
        suggestions: list[dict[str, Any]] = []
        auto_fixable: list[str] = []
        manual: list[str] = []
        for issue in issues:
            rule = issue.get("rule", "unknown")
            issue_id = issue.get("issue_id", rule)
            template = _FIX_SUGGESTIONS.get(rule, _FIX_SUGGESTIONS["__default__"])
            suggestions.append({
                "issue_id": issue_id,
                "fix_description": template["fix_description"],
                "priority": _severity_to_priority(issue.get("severity", "info")),
                "estimated_effort": template["estimated_effort"],
            })
            if rule in _AUTO_FIXABLE_RULES:
                auto_fixable.append(issue_id)
            else:
                manual.append(issue_id)
        return {
            "suggestions": suggestions,
            "auto_fixable": auto_fixable,
            "manual_fix_required": manual,
        }

    def re_review(self, session: dict[str, Any]) -> dict[str, Any]:
        """Re-review after fixes applied. Increments iteration_count.

        在 Mock 模式下，模拟"自动可修复的 issue 已被修复"：从上次 review 的
        issues 中移除 auto_fixable 项，重新计分并与上次对比。

        Returns:
            Same structure as review(), plus:
                - previous_score: float
                - score_delta: float (current - previous)
                - improvement: bool (score_delta > 0)
        """
        self._require_active(session)
        history = session.get("history", [])
        last = session.get("last_feedback") or (history[-1] if history else None)
        if last is None:
            # 无历史复审记录：退化为普通 review
            return self.review(session)

        previous_score = last["score"]
        # 模拟修复：移除上次 review 中可自动修复的 issues
        prior_issues = last.get("issues", [])
        remaining = [i for i in prior_issues if i.get("rule", "") not in _AUTO_FIXABLE_RULES]

        session["iteration_count"] = session.get("iteration_count", 0) + 1
        feedback = self._build_feedback(session, remaining)
        feedback["previous_score"] = previous_score
        feedback["score_delta"] = round(feedback["score"] - previous_score, 4)
        feedback["improvement"] = feedback["score_delta"] > 0
        session.setdefault("history", []).append(feedback)
        session["last_feedback"] = feedback
        return feedback

    def end_session(self, session: dict[str, Any]) -> dict[str, Any]:
        """End the review session and generate summary.

        幂等：对已 completed 的会话重复调用返回缓存的 summary。

        Returns:
            Dict with keys:
                - session_id: str
                - total_iterations: int
                - initial_score: float
                - final_score: float
                - total_improvement: float
                - issues_resolved: int
                - issues_remaining: int
                - duration_seconds: float
                - status: "completed"
        """
        self._validate_session(session)
        if session.get("status") == "completed":
            cached = session.get("end_summary")
            if isinstance(cached, dict):
                return cached
        session["status"] = "completed"
        session["ended_at"] = _now_iso()
        summary = self._build_end_summary(session)
        session["end_summary"] = summary
        return summary

    def get_session_history(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        """Get full review history for a session."""
        self._validate_session(session)
        return list(session.get("history", []))

    # ── 内部辅助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _validate_session(session: dict[str, Any]) -> None:
        """校验 session 结构：必须是 dict 且包含 session_id。"""
        if not isinstance(session, dict):
            raise ValueError(f"Invalid session: expected dict, got {type(session).__name__}")
        if "session_id" not in session:
            raise ValueError("Invalid session: missing 'session_id' (not created by start_session)")

    @classmethod
    def _require_active(cls, session: dict[str, Any]) -> None:
        """校验 session 处于 active 状态（可继续 review/re_review）。"""
        cls._validate_session(session)
        if session.get("status") != "active":
            raise RuntimeError(
                f"Session {session.get('session_id', '?')} is not active "
                f"(status={session.get('status', '?')}); start a new session instead."
            )

    def _build_feedback(
        self,
        session: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """构建标准 feedback dict（review 与 re_review 共用）。"""
        axes = session.get("review_axes", list(DEFAULT_REVIEW_AXES))
        score = _compute_score(issues)
        return {
            "session_id": session.get("session_id", "unknown"),
            "iteration": session.get("iteration_count", 0),
            "issues": issues,
            "summary": self._build_summary(issues, score, axes),
            "score": score,
            "visual_changes": self._collect_visual_changes(session),
            "timestamp": _now_iso(),
        }

    @staticmethod
    def _build_summary(
        issues: list[dict[str, Any]],
        score: float,
        axes: list[str],
    ) -> str:
        """生成可读的 review 摘要。"""
        critical = sum(1 for i in issues if i.get("severity") == "critical")
        warning = sum(1 for i in issues if i.get("severity") == "warning")
        info = sum(1 for i in issues if i.get("severity") == "info")
        return (
            f"Live review on {len(axes)} axes: {len(issues)} issues "
            f"({critical} critical, {warning} warning, {info} info). "
            f"Score: {score:.2f}."
        )

    @staticmethod
    def _review_mock(axes: list[str]) -> list[dict[str, Any]]:
        """Mock 模式：基于 review_axes 生成模板化 issues（确定性）。"""
        issues: list[dict[str, Any]] = []
        for axis in axes:
            templates = _MOCK_ISSUE_TEMPLATES.get(axis, [])
            issues.extend(dict(t) for t in templates)
        return issues

    def _review_real(
        self,
        session: dict[str, Any],
        dom_data: Any,
        page: Any,
    ) -> list[dict[str, Any]]:
        """真实模式：协调 UIUXAnalyzer 执行巡检。

        优先使用 audit_dom_data(dom_data)（无需 Playwright）；否则使用
        audit(page)（需 Playwright Page 对象）。任一异常降级为 Mock。
        """
        analyzer = self._get_analyzer()
        axes = session.get("review_axes", list(DEFAULT_REVIEW_AXES))
        if analyzer is None:
            logger.debug("UIUXAnalyzer unavailable; falling back to mock review")
            return self._review_mock(axes)

        url = session.get("url", "")
        try:
            if dom_data is not None:
                report = analyzer.audit_dom_data(dom_data, url=url)
            else:
                report = analyzer.audit(page, url=url)
        except Exception as exc:  # noqa: BLE001 — 任意巡检异常都应降级而非中断闭环
            logger.warning("LiveBrowserMode real review failed: %s", exc)
            return self._review_mock(axes)

        return [self._uiux_issue_to_dict(i) for i in report.issues]

    @staticmethod
    def _uiux_issue_to_dict(issue: Any) -> dict[str, Any]:
        """将 UIUXIssue dataclass 实例转为 feedback 用的 dict。"""
        rule = getattr(issue, "rule", "unknown")
        category = getattr(issue, "category", "unknown")
        return {
            "issue_id": f"{category}-{rule}",
            "severity": getattr(issue, "severity", "info"),
            "category": category,
            "rule": rule,
            "element": getattr(issue, "element", ""),
            "description": getattr(issue, "message", ""),
            "fix": getattr(issue, "fix", ""),
        }

    def _collect_visual_changes(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        """收集视觉回归 Diff 结果（协调 VisualRegressionChecker）。

        无 baseline 时返回 no_baseline 占位；checker 不可用时返回 unavailable；
        Diff 异常时返回 error。三者均保证返回 list[dict]。
        """
        baseline = session.get("visual_baseline")
        current = session.get("visual_current")
        if baseline is None or current is None:
            return [{
                "status": "no_baseline",
                "message": "No visual baseline established; visual regression skipped",
            }]

        checker = self._get_visual_checker()
        if checker is None:
            return [{
                "status": "unavailable",
                "message": "VisualRegressionChecker unavailable (Pillow not installed)",
            }]

        try:
            result = checker.compare(baseline, current)
            return [{
                "status": "regression" if checker.is_regression(result) else "ok",
                "pixel_diff_ratio": result.pixel_diff_ratio,
                "has_display_error": result.has_display_error,
                "changed_regions": len(result.changed_regions),
            }]
        except Exception as exc:  # noqa: BLE001 — Diff 异常不应中断 review 闭环
            logger.warning("Visual regression failed: %s", exc)
            return [{"status": "error", "message": str(exc)}]

    def _get_analyzer(self) -> Any | None:
        """延迟获取 UIUXAnalyzer 实例（软依赖）。"""
        if self._analyzer is not None:
            return self._analyzer
        try:
            from scripts.qa import UIUXAnalyzer
        except ImportError as exc:
            logger.debug("UIUXAnalyzer unavailable: %s", exc)
            return None
        self._analyzer = UIUXAnalyzer()
        return self._analyzer

    def _get_visual_checker(self) -> Any | None:
        """延迟获取 VisualRegressionChecker 实例（软依赖）。"""
        if self._visual_checker is not None:
            return self._visual_checker
        try:
            from scripts.qa import VisualRegressionChecker
        except ImportError as exc:
            logger.debug("VisualRegressionChecker unavailable: %s", exc)
            return None
        self._visual_checker = VisualRegressionChecker()
        return self._visual_checker

    @staticmethod
    def _build_end_summary(session: dict[str, Any]) -> dict[str, Any]:
        """构建 end_session 的总结 dict。"""
        history = session.get("history", [])
        total_iterations = session.get("iteration_count", 0)
        initial_score = history[0]["score"] if history else 0.0
        final_score = history[-1]["score"] if history else 0.0
        initial_issues = history[0]["issues"] if history else []
        final_issues = history[-1]["issues"] if history else []
        initial_keys = {_issue_key(i) for i in initial_issues}
        final_keys = {_issue_key(i) for i in final_issues}
        issues_resolved = len(initial_keys - final_keys)
        issues_remaining = len(final_keys)
        started_at = session.get("started_at", "")
        ended_at = session.get("ended_at", "")
        return {
            "session_id": session.get("session_id", "unknown"),
            "total_iterations": total_iterations,
            "initial_score": round(initial_score, 4),
            "final_score": round(final_score, 4),
            "total_improvement": round(final_score - initial_score, 4),
            "issues_resolved": issues_resolved,
            "issues_remaining": issues_remaining,
            "duration_seconds": LiveBrowserMode._duration_seconds(started_at, ended_at),
            "status": "completed",
        }

    @staticmethod
    def _duration_seconds(started_at: str, ended_at: str) -> float:
        """计算会话时长（秒），解析失败返回 0.0。"""
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(ended_at)
            return max(0.0, (end - start).total_seconds())
        except (ValueError, TypeError):
            return 0.0


__all__ = ["LiveBrowserMode"]
