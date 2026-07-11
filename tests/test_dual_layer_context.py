"""Tests for scripts.collaboration.dual_layer_context.

Covers ContextEntry (TTL expiry) and DualLayerContextManager
(project/task layers, combined context, prompt building, eviction, cleanup).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from scripts.collaboration.dual_layer_context import ContextEntry, DualLayerContextManager

# ---------------------------------------------------------------------------
# ContextEntry
# ---------------------------------------------------------------------------


class TestContextEntry:
    def test_defaults(self):
        entry = ContextEntry(key="k", value="v")
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.layer == "task"
        assert entry.source == ""
        assert entry.timestamp != ""
        assert entry.ttl is None

    def test_custom_values(self):
        entry = ContextEntry(key="k", value="v", layer="project", source="arch", ttl=60)
        assert entry.layer == "project"
        assert entry.source == "arch"
        assert entry.ttl == 60

    def test_is_expired_no_ttl(self):
        entry = ContextEntry(key="k", value="v")
        assert entry.is_expired() is False

    def test_is_expired_not_yet(self):
        entry = ContextEntry(key="k", value="v", ttl=60)
        assert entry.is_expired() is False

    def test_is_expired_past_ttl(self):
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        entry = ContextEntry(key="k", value="v", ttl=60, timestamp=old_time)
        assert entry.is_expired() is True

    def test_is_expired_boundary(self):
        old_time = (datetime.now() - timedelta(seconds=61)).isoformat()
        entry = ContextEntry(key="k", value="v", ttl=60, timestamp=old_time)
        assert entry.is_expired() is True


# ---------------------------------------------------------------------------
# DualLayerContextManager — Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        mgr = DualLayerContextManager()
        assert mgr.project_context == {}
        assert mgr.task_context == {}
        assert mgr.max_project == 100
        assert mgr.max_task == 50

    def test_custom_limits(self):
        mgr = DualLayerContextManager(max_project_entries=10, max_task_entries=5)
        assert mgr.max_project == 10
        assert mgr.max_task == 5


# ---------------------------------------------------------------------------
# Project layer
# ---------------------------------------------------------------------------


class TestProjectLayer:
    def test_set_and_get(self):
        mgr = DualLayerContextManager()
        mgr.set_project("arch", "microservices")
        assert mgr.get_project("arch") == "microservices"

    def test_get_missing_returns_default(self):
        mgr = DualLayerContextManager()
        assert mgr.get_project("missing") is None
        assert mgr.get_project("missing", "default") == "default"

    def test_get_expired_returns_default_and_deletes(self):
        mgr = DualLayerContextManager()
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.project_context["k"] = ContextEntry(
            key="k", value="v", layer="project", ttl=60, timestamp=old_time
        )
        assert mgr.get_project("k", "default") == "default"
        assert "k" not in mgr.project_context

    def test_set_with_source(self):
        mgr = DualLayerContextManager()
        mgr.set_project("key", "val", source="architect")
        assert mgr.project_context["key"].source == "architect"

    def test_set_with_ttl(self):
        mgr = DualLayerContextManager()
        mgr.set_project("key", "val", ttl=60)
        assert mgr.project_context["key"].ttl == 60

    def test_set_overwrites(self):
        mgr = DualLayerContextManager()
        mgr.set_project("k", "v1")
        mgr.set_project("k", "v2")
        assert mgr.get_project("k") == "v2"


# ---------------------------------------------------------------------------
# Task layer
# ---------------------------------------------------------------------------


class TestTaskLayer:
    def test_set_and_get(self):
        mgr = DualLayerContextManager()
        mgr.set_task("result", "ok")
        assert mgr.get_task("result") == "ok"

    def test_get_missing_returns_default(self):
        mgr = DualLayerContextManager()
        assert mgr.get_task("missing") is None
        assert mgr.get_task("missing", 42) == 42

    def test_get_expired_returns_default_and_deletes(self):
        mgr = DualLayerContextManager()
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.task_context["k"] = ContextEntry(
            key="k", value="v", layer="task", ttl=60, timestamp=old_time
        )
        assert mgr.get_task("k", "default") == "default"
        assert "k" not in mgr.task_context

    def test_set_with_source(self):
        mgr = DualLayerContextManager()
        mgr.set_task("key", "val", source="coder")
        assert mgr.task_context["key"].source == "coder"

    def test_set_overwrites(self):
        mgr = DualLayerContextManager()
        mgr.set_task("k", "v1")
        mgr.set_task("k", "v2")
        assert mgr.get_task("k") == "v2"


# ---------------------------------------------------------------------------
# Combined context
# ---------------------------------------------------------------------------


class TestGetCombined:
    def test_empty_returns_empty(self):
        mgr = DualLayerContextManager()
        assert mgr.get_combined() == {}

    def test_project_only(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        assert mgr.get_combined() == {"a": 1}

    def test_task_only(self):
        mgr = DualLayerContextManager()
        mgr.set_task("b", 2)
        assert mgr.get_combined() == {"b": 2}

    def test_both_layers(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_task("b", 2)
        assert mgr.get_combined() == {"a": 1, "b": 2}

    def test_task_overrides_project(self):
        mgr = DualLayerContextManager()
        mgr.set_project("k", "project_val")
        mgr.set_task("k", "task_val")
        assert mgr.get_combined() == {"k": "task_val"}

    def test_filtered_keys(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_project("b", 2)
        mgr.set_task("c", 3)
        assert mgr.get_combined(keys=["a", "c"]) == {"a": 1, "c": 3}

    def test_excludes_expired(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.project_context["b"] = ContextEntry(
            key="b", value=2, layer="project", ttl=60, timestamp=old_time
        )
        assert mgr.get_combined() == {"a": 1}


# ---------------------------------------------------------------------------
# build_prompt_context
# ---------------------------------------------------------------------------


class TestBuildPromptContext:
    def test_empty_returns_empty_string(self):
        mgr = DualLayerContextManager()
        assert mgr.build_prompt_context() == ""

    def test_project_only(self):
        mgr = DualLayerContextManager()
        mgr.set_project("arch", "microservices")
        result = mgr.build_prompt_context()
        assert "## Project Context" in result
        assert "arch" in result
        assert "microservices" in result

    def test_task_only(self):
        mgr = DualLayerContextManager()
        mgr.set_task("result", "success")
        result = mgr.build_prompt_context()
        assert "## Task Context" in result
        assert "result" in result

    def test_both_layers(self):
        mgr = DualLayerContextManager()
        mgr.set_project("arch", "microservices")
        mgr.set_task("result", "success")
        result = mgr.build_prompt_context()
        assert "## Project Context" in result
        assert "## Task Context" in result

    def test_excludes_expired(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.project_context["b"] = ContextEntry(
            key="b", value=2, layer="project", ttl=60, timestamp=old_time
        )
        result = mgr.build_prompt_context()
        assert "a" in result
        assert "b" not in result


# ---------------------------------------------------------------------------
# Clear operations
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_task_context(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_task("b", 2)
        mgr.clear_task_context()
        assert mgr.task_context == {}
        assert mgr.project_context != {}

    def test_clear_all(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_task("b", 2)
        mgr.clear_all()
        assert mgr.project_context == {}
        assert mgr.task_context == {}


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------


class TestCleanupExpired:
    def test_no_expired_returns_zero(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_task("b", 2)
        assert mgr.cleanup_expired() == 0

    def test_cleans_expired_project(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.project_context["b"] = ContextEntry(
            key="b", value=2, layer="project", ttl=60, timestamp=old_time
        )
        assert mgr.cleanup_expired() == 1
        assert "b" not in mgr.project_context

    def test_cleans_expired_task(self):
        mgr = DualLayerContextManager()
        mgr.set_task("a", 1)
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.task_context["b"] = ContextEntry(
            key="b", value=2, layer="task", ttl=60, timestamp=old_time
        )
        assert mgr.cleanup_expired() == 1
        assert "b" not in mgr.task_context

    def test_cleans_both_layers(self):
        mgr = DualLayerContextManager()
        old_time = (datetime.now() - timedelta(seconds=120)).isoformat()
        mgr.project_context["p"] = ContextEntry(
            key="p", value=1, layer="project", ttl=60, timestamp=old_time
        )
        mgr.task_context["t"] = ContextEntry(
            key="t", value=2, layer="task", ttl=60, timestamp=old_time
        )
        assert mgr.cleanup_expired() == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        mgr = DualLayerContextManager()
        stats = mgr.get_stats()
        assert stats == {"project_entries": 0, "task_entries": 0, "total_entries": 0}

    def test_with_entries(self):
        mgr = DualLayerContextManager()
        mgr.set_project("a", 1)
        mgr.set_project("b", 2)
        mgr.set_task("c", 3)
        stats = mgr.get_stats()
        assert stats["project_entries"] == 2
        assert stats["task_entries"] == 1
        assert stats["total_entries"] == 3


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_project_eviction_removes_oldest(self):
        mgr = DualLayerContextManager(max_project_entries=2)
        mgr.set_project("a", 1)
        time.sleep(0.01)
        mgr.set_project("b", 2)
        time.sleep(0.01)
        mgr.set_project("c", 3)
        assert len(mgr.project_context) == 2
        assert "a" not in mgr.project_context

    def test_task_eviction_removes_oldest(self):
        mgr = DualLayerContextManager(max_task_entries=2)
        mgr.set_task("a", 1)
        time.sleep(0.01)
        mgr.set_task("b", 2)
        time.sleep(0.01)
        mgr.set_task("c", 3)
        assert len(mgr.task_context) == 2
        assert "a" not in mgr.task_context

    def test_no_eviction_within_limit(self):
        mgr = DualLayerContextManager(max_project_entries=5)
        for i in range(5):
            mgr.set_project(f"k{i}", i)
        assert len(mgr.project_context) == 5
