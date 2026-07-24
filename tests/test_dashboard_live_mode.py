"""V4.3+ Roadmap P2-UI-2: Dashboard Live Browser 模式单元测试。

覆盖 LiveBrowserMode 的会话生命周期、审查闭环、修复建议、复审对比、
会话总结、历史记录、边界条件与端到端流程（T1-T24）。
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dashboard_live_mode import (
    DEFAULT_REVIEW_AXES,
    DEFAULT_TARGET_VIEWS,
    LiveBrowserMode,
)

# ============================================================
# start_session 测试 (T1-T3)
# ============================================================


class TestStartSession:
    def test_t1_returns_valid_session(self):
        """T1: start_session() 返回有效 session（session_id/url/status="active"）。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        assert "session_id" in session
        assert isinstance(session["session_id"], str)
        assert session["session_id"].startswith("lbm-")
        assert session["url"] == "http://localhost:8501"
        assert session["status"] == "active"

    def test_t2_default_target_views_is_main(self):
        """T2: start_session() 默认 target_views=["main"]。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        assert session["target_views"] == list(DEFAULT_TARGET_VIEWS)
        assert session["target_views"] == ["main"]

    def test_t3_default_review_axes_has_four(self):
        """T3: start_session() 默认 review_axes 包含 4 个轴。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        axes = session["review_axes"]
        assert len(axes) == 4
        assert set(axes) == set(DEFAULT_REVIEW_AXES)
        assert "a11y" in axes
        assert "interaction" in axes
        assert "layout" in axes
        assert "ux_antipattern" in axes


# ============================================================
# review 测试 (T4-T10)
# ============================================================


class TestReview:
    def test_t4_returns_issues_list(self):
        """T4: review() 返回 issues 列表。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        assert isinstance(feedback["issues"], list)
        assert len(feedback["issues"]) > 0

    def test_t5_score_in_unit_range(self):
        """T5: review() 返回 score 在 [0,1]。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        assert 0.0 <= feedback["score"] <= 1.0

    def test_t6_summary_non_empty(self):
        """T6: review() 返回 summary 非空。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        assert isinstance(feedback["summary"], str)
        assert len(feedback["summary"]) > 0
        assert "Score" in feedback["summary"]

    def test_t7_returns_visual_changes_list(self):
        """T7: review() 返回 visual_changes 列表。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        assert isinstance(feedback["visual_changes"], list)
        # 无 baseline 时应有 no_baseline 占位项
        assert len(feedback["visual_changes"]) >= 1
        assert feedback["visual_changes"][0]["status"] == "no_baseline"

    def test_t8_returns_timestamp(self):
        """T8: review() 返回 timestamp。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        assert "timestamp" in feedback
        assert isinstance(feedback["timestamp"], str)
        assert len(feedback["timestamp"]) > 0

    def test_t9_increments_iteration_count(self):
        """T9: review() 增加 session iteration_count。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        assert session["iteration_count"] == 0
        feedback = mode.review(session)
        assert session["iteration_count"] == 1
        assert feedback["iteration"] == 1

    def test_t10_appends_to_session_history(self):
        """T10: review() 添加到 session history。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        assert len(session["history"]) == 0
        feedback = mode.review(session)
        assert len(session["history"]) == 1
        assert session["history"][0] is feedback


# ============================================================
# suggest_fixes 测试 (T11-T13)
# ============================================================


class TestSuggestFixes:
    def test_t11_returns_suggestions_list(self):
        """T11: suggest_fixes() 返回 suggestions 列表。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        fixes = mode.suggest_fixes(session, feedback["issues"])
        assert isinstance(fixes["suggestions"], list)
        assert len(fixes["suggestions"]) == len(feedback["issues"])
        for s in fixes["suggestions"]:
            assert "issue_id" in s
            assert "fix_description" in s
            assert "priority" in s
            assert "estimated_effort" in s

    def test_t12_distinguishes_auto_and_manual(self):
        """T12: suggest_fixes() 区分 auto_fixable 和 manual_fix_required。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        feedback = mode.review(session)
        fixes = mode.suggest_fixes(session, feedback["issues"])
        # 4 轴 mock 包含可自动修复（img_missing_alt/button_too_small/viewport_overflow）
        # 与需手动修复的 issues
        assert isinstance(fixes["auto_fixable"], list)
        assert isinstance(fixes["manual_fix_required"], list)
        assert len(fixes["auto_fixable"]) > 0
        assert len(fixes["manual_fix_required"]) > 0
        # 并集应覆盖所有 issues，且二者无交集
        all_ids = {s["issue_id"] for s in fixes["suggestions"]}
        auto_set = set(fixes["auto_fixable"])
        manual_set = set(fixes["manual_fix_required"])
        assert auto_set | manual_set == all_ids
        assert auto_set.isdisjoint(manual_set)

    def test_t13_empty_issues_returns_empty_suggestions(self):
        """T13: suggest_fixes() 空 issues 返回空 suggestions。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        fixes = mode.suggest_fixes(session, [])
        assert fixes["suggestions"] == []
        assert fixes["auto_fixable"] == []
        assert fixes["manual_fix_required"] == []


# ============================================================
# re_review 测试 (T14-T17)
# ============================================================


class TestReReview:
    def test_t14_returns_previous_score(self):
        """T14: re_review() 返回 previous_score。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        first = mode.review(session)
        second = mode.re_review(session)
        assert "previous_score" in second
        assert second["previous_score"] == first["score"]

    def test_t15_returns_score_delta(self):
        """T15: re_review() 返回 score_delta。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        second = mode.re_review(session)
        assert "score_delta" in second
        assert isinstance(second["score_delta"], float)
        # delta 应等于 current - previous
        assert second["score_delta"] == round(second["score"] - second["previous_score"], 4)

    def test_t16_returns_improvement_bool(self):
        """T16: re_review() 返回 improvement bool。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        second = mode.re_review(session)
        assert "improvement" in second
        assert isinstance(second["improvement"], bool)
        # mock 模式移除了 auto_fixable issues，score 应提升
        assert second["improvement"] is True
        assert second["score_delta"] > 0

    def test_t17_increments_iteration_count(self):
        """T17: re_review() 增加 iteration_count。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        assert session["iteration_count"] == 1
        mode.re_review(session)
        assert session["iteration_count"] == 2


# ============================================================
# end_session 测试 (T18-T21)
# ============================================================


class TestEndSession:
    def test_t18_returns_total_iterations(self):
        """T18: end_session() 返回 total_iterations。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        mode.re_review(session)
        summary = mode.end_session(session)
        assert summary["total_iterations"] == 2

    def test_t19_returns_initial_and_final_score(self):
        """T19: end_session() 返回 initial_score 和 final_score。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        first = mode.review(session)
        second = mode.re_review(session)
        summary = mode.end_session(session)
        assert summary["initial_score"] == round(first["score"], 4)
        assert summary["final_score"] == round(second["score"], 4)

    def test_t20_returns_issues_resolved_and_remaining(self):
        """T20: end_session() 返回 issues_resolved 和 issues_remaining。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        mode.re_review(session)
        summary = mode.end_session(session)
        assert isinstance(summary["issues_resolved"], int)
        assert isinstance(summary["issues_remaining"], int)
        # re_review 移除了 auto_fixable issues，应有部分 resolved
        assert summary["issues_resolved"] > 0
        assert summary["issues_remaining"] > 0

    def test_t21_sets_status_completed(self):
        """T21: end_session() 设置 status="completed"。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        summary = mode.end_session(session)
        assert session["status"] == "completed"
        assert summary["status"] == "completed"


# ============================================================
# get_session_history 测试 (T22)
# ============================================================


class TestSessionHistory:
    def test_t22_returns_full_history(self):
        """T22: get_session_history() 返回完整历史。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        mode.re_review(session)
        history = mode.get_session_history(session)
        assert isinstance(history, list)
        assert len(history) == 2
        assert history[0]["iteration"] == 1
        assert history[1]["iteration"] == 2


# ============================================================
# 边界条件测试 (T23)
# ============================================================


class TestEdgeCases:
    def test_t23a_empty_session_raises(self):
        """T23a: 空 session（缺 session_id）触发 ValueError。"""
        mode = LiveBrowserMode()
        with pytest.raises(ValueError, match="missing 'session_id'"):
            mode.end_session({})

    def test_t23b_non_dict_session_raises(self):
        """T23b: 非 dict session 触发 ValueError。"""
        mode = LiveBrowserMode()
        with pytest.raises(ValueError, match="expected dict"):
            mode.get_session_history("not-a-session")  # type: ignore[arg-type]

    def test_t23c_duplicate_end_session_is_idempotent(self):
        """T23c: 重复 end_session 返回缓存的 summary（幂等）。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        first_summary = mode.end_session(session)
        second_summary = mode.end_session(session)
        assert second_summary is first_summary

    def test_t23d_review_after_end_raises(self):
        """T23d: completed 会话再 review 触发 RuntimeError。"""
        mode = LiveBrowserMode()
        session = mode.start_session(url="http://localhost:8501")
        mode.review(session)
        mode.end_session(session)
        with pytest.raises(RuntimeError, match="not active"):
            mode.review(session)

    def test_t23e_unknown_session_id_format_rejected(self):
        """T23e: 伪造 session（无 session_id）被拒绝。"""
        mode = LiveBrowserMode()
        fake = {"url": "x", "status": "active"}  # 缺 session_id
        with pytest.raises(ValueError, match="missing 'session_id'"):
            mode.review(fake)


# ============================================================
# 端到端测试 (T24)
# ============================================================


class TestEndToEnd:
    def test_t24_full_iteration_loop(self):
        """T24: 端到端 — start → review → suggest → re_review → end 完整闭环。"""
        mode = LiveBrowserMode()

        # 1. start
        session = mode.start_session(
            url="http://localhost:8501",
            target_views=["main", "sidebar"],
            review_axes=["a11y", "interaction", "layout", "ux_antipattern"],
        )
        assert session["status"] == "active"
        assert session["target_views"] == ["main", "sidebar"]

        # 2. review
        feedback = mode.review(session)
        assert feedback["iteration"] == 1
        assert len(feedback["issues"]) > 0
        initial_score = feedback["score"]

        # 3. suggest
        fixes = mode.suggest_fixes(session, feedback["issues"])
        assert len(fixes["suggestions"]) == len(feedback["issues"])
        assert len(fixes["auto_fixable"]) > 0

        # 4. re_review（模拟应用修复后）
        re_feedback = mode.re_review(session)
        assert re_feedback["iteration"] == 2
        assert re_feedback["previous_score"] == initial_score
        assert re_feedback["improvement"] is True
        assert re_feedback["score"] > initial_score
        # re_review 后 issues 数应少于初次（auto_fixable 已移除）
        assert len(re_feedback["issues"]) < len(feedback["issues"])

        # 5. end
        summary = mode.end_session(session)
        assert summary["status"] == "completed"
        assert summary["total_iterations"] == 2
        assert summary["initial_score"] == round(initial_score, 4)
        assert summary["final_score"] == round(re_feedback["score"], 4)
        assert summary["total_improvement"] > 0
        assert summary["issues_resolved"] > 0

        # 6. 历史可追溯
        history = mode.get_session_history(session)
        assert len(history) == 2
