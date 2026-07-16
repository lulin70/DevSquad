#!/usr/bin/env python3
"""
Tests for P1-4 to-issues — vertical slice + HITL/AFK + dependency ordering.

Covers new MicroTask fields (execution_mode, slice_type), the existing
dependencies field, MicroTaskPlanner.classify_execution_mode() and
MicroTaskPlanner.order_by_dependencies().

Spec reference: V4.1.0 PRD P1-4 (Matt Pocock to-issues philosophy).
"""

from __future__ import annotations

import logging

import pytest

from scripts.collaboration.micro_task_planner import (
    MicroTask,
    MicroTaskPlanner,
)


def _make_task(
    task_id: str,
    title: str = "do something",
    description: str = "a task",
    dependencies: list[str] | None = None,
) -> MicroTask:
    """Helper: build a minimal MicroTask with an id."""
    return MicroTask(
        id=task_id,
        title=title,
        description=description,
        dependencies=list(dependencies) if dependencies else [],
    )


class TestMicroTaskNewFields:
    """Test the new execution_mode and slice_type fields on MicroTask."""

    def test_microtask_default_execution_mode_is_afk(self):
        """MicroTask.execution_mode defaults to AFK."""
        mt = _make_task("t1")
        assert mt.execution_mode == "AFK"

    def test_microtask_default_slice_type_is_horizontal(self):
        """MicroTask.slice_type defaults to horizontal."""
        mt = _make_task("t1")
        assert mt.slice_type == "horizontal"

    def test_microtask_default_dependencies_is_empty_list(self):
        """MicroTask.dependencies defaults to an empty list (not None)."""
        mt = _make_task("t1")
        assert mt.dependencies == []
        assert isinstance(mt.dependencies, list)

    def test_microtask_to_dict_includes_new_fields(self):
        """MicroTask.to_dict() serializes execution_mode and slice_type."""
        mt = _make_task("t1")
        mt.execution_mode = "HITL"
        mt.slice_type = "vertical"
        d = mt.to_dict()
        assert d["execution_mode"] == "HITL"
        assert d["slice_type"] == "vertical"

    def test_microtask_slice_type_can_be_set_to_vertical(self):
        """MicroTask.slice_type can be annotated as vertical (end-to-end slice)."""
        mt = _make_task("t1")
        mt.slice_type = "vertical"
        assert mt.slice_type == "vertical"


class TestClassifyExecutionMode:
    """Test MicroTaskPlanner.classify_execution_mode()."""

    def setup_method(self):
        self.planner = MicroTaskPlanner()

    def test_classify_execution_mode_deploy_keyword_is_hitl(self):
        """English 'deploy' keyword yields HITL."""
        mt = _make_task("t1", title="Deploy to production", description="ship it")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_chinese_bushu_is_hitl(self):
        """Chinese '部署' keyword yields HITL."""
        mt = _make_task("t1", title="部署到生产环境", description="上线")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_release_keyword_is_hitl(self):
        """English 'release' keyword yields HITL."""
        mt = _make_task("t1", title="Publish", description="release the new version")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_chinese_fabu_is_hitl(self):
        """Chinese '发布' keyword yields HITL."""
        mt = _make_task("t1", title="发布功能", description="上线新版本")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_approve_keyword_is_hitl(self):
        """English 'approve' keyword yields HITL."""
        mt = _make_task("t1", title="Review", description="approve the change")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_chinese_shenpi_is_hitl(self):
        """Chinese '审批' keyword yields HITL."""
        mt = _make_task("t1", title="审批流程", description="需要人工确认")
        assert self.planner.classify_execution_mode(mt) == "HITL"

    def test_classify_execution_mode_normal_task_is_afk(self):
        """A normal implementation task yields AFK."""
        mt = _make_task("t1", title="Implement login", description="add login endpoint")
        assert self.planner.classify_execution_mode(mt) == "AFK"

    def test_classify_execution_mode_case_insensitive(self):
        """Execution-mode classification is case-insensitive."""
        mt = _make_task("t1", title="DEPLOY to prod", description="release now")
        assert self.planner.classify_execution_mode(mt) == "HITL"


class TestOrderByDependencies:
    """Test MicroTaskPlanner.order_by_dependencies()."""

    def setup_method(self):
        self.planner = MicroTaskPlanner()

    def test_order_no_dependencies_preserves_order(self):
        """Tasks without dependencies keep their original order."""
        a = _make_task("a", title="A")
        b = _make_task("b", title="B")
        c = _make_task("c", title="C")
        result = self.planner.order_by_dependencies([a, b, c])
        assert [t.id for t in result] == ["a", "b", "c"]

    def test_order_dependency_comes_before_dependent(self):
        """A dependency must precede its dependent."""
        # b depends on a, so a should come first.
        a = _make_task("a", title="A")
        b = _make_task("b", title="B", dependencies=["a"])
        result = self.planner.order_by_dependencies([b, a])
        ids = [t.id for t in result]
        assert ids.index("a") < ids.index("b")

    def test_order_chain_a_b_c(self):
        """A dependency chain c->b->a is ordered a, b, c."""
        a = _make_task("a", title="A")
        b = _make_task("b", title="B", dependencies=["a"])
        c = _make_task("c", title="C", dependencies=["b"])
        result = self.planner.order_by_dependencies([c, b, a])
        assert [t.id for t in result] == ["a", "b", "c"]

    def test_order_cycle_preserves_original_order(self, caplog):
        """A dependency cycle keeps the original order and logs a warning."""
        a = _make_task("a", title="A", dependencies=["b"])
        b = _make_task("b", title="B", dependencies=["a"])
        original = [a, b]
        with caplog.at_level(logging.WARNING):
            result = self.planner.order_by_dependencies(original)
        # Original order preserved.
        assert [t.id for t in result] == ["a", "b"]
        # A warning was logged.
        assert any("cycle" in rec.message.lower() for rec in caplog.records)

    def test_order_returns_new_list_not_same_object(self):
        """order_by_dependencies returns a new list instance."""
        a = _make_task("a", title="A")
        original = [a]
        result = self.planner.order_by_dependencies(original)
        assert result is not original

    def test_order_independent_groups_interleaved_stably(self):
        """Two independent chains are sorted stably (no deps first)."""
        a = _make_task("a", title="A")
        b = _make_task("b", title="B", dependencies=["a"])
        c = _make_task("c", title="C")
        d = _make_task("d", title="D", dependencies=["c"])
        result = self.planner.order_by_dependencies([b, d, a, c])
        ids = [t.id for t in result]
        # a before b, c before d.
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")


class TestVerticalSliceAnnotation:
    """Test vertical vs horizontal slice annotation on MicroTask."""

    def test_vertical_slice_task_marked_vertical(self):
        """An end-to-end slice task can be annotated slice_type='vertical'."""
        mt = _make_task(
            "t1",
            title="Add login (DB + API + UI)",
            description="vertical slice covering all layers",
        )
        mt.slice_type = "vertical"
        assert mt.slice_type == "vertical"

    def test_horizontal_slice_default_kept(self):
        """A layer-only task keeps the default horizontal slice_type."""
        mt = _make_task(
            "t1",
            title="Add DB migration",
            description="database layer only",
        )
        assert mt.slice_type == "horizontal"

    def test_vertical_slice_with_hitl_execution_mode(self):
        """A vertical slice can combine slice_type=vertical and execution_mode=HITL."""
        mt = _make_task(
            "t1",
            title="Deploy login feature end-to-end",
            description="vertical slice that needs deploy approval",
        )
        mt.slice_type = "vertical"
        mt.execution_mode = "HITL"
        assert mt.slice_type == "vertical"
        assert mt.execution_mode == "HITL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
