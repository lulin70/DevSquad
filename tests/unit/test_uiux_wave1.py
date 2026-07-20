"""Wave 1 UI/UX Enhancement tests.

Tests for:
- W1-T1: Dispatch real-time visualization helpers (_predict_auto_roles, _render_role_pipeline)
- W1-T2: Interactive performance charts (_safe_float, _render_performance_charts, _MORANDI_CHART_COLORS)
- W1-T3: DAG node interactivity (_build_interactive_dot, _render_graphviz_interactive, _GRAPHVIZ_STATUS_FILL)
"""

import pytest

from scripts.dashboard.dag_views import (
    _GRAPHVIZ_STATUS_FILL,
    _GRAPHVIZ_STATUS_FONT,
    DEFAULT_LIFECYCLE_PHASES,
    DAGVisualizer,
    _build_interactive_dot,
)
from scripts.dashboard.dispatch_views import (
    _ROLE_PIPELINE_COLORS,
    _ROLE_PIPELINE_ICONS,
    _predict_auto_roles,
)
from scripts.dashboard.metrics_views import (
    _MORANDI_CHART_COLORS,
    _safe_float,
)

# ── W1-T1: Dispatch real-time visualization ──


class TestPredictAutoRoles:
    """Verify: _predict_auto_roles returns 2-4 role IDs based on task keywords."""

    def test_security_keyword_triggers_security_role(self):
        """Security-related keywords should match security role."""
        roles = _predict_auto_roles("Audit security vulnerability in auth", None)
        assert "security" in roles

    def test_test_keyword_triggers_tester_role(self):
        """Test-related keywords should match tester role."""
        roles = _predict_auto_roles("Write test cases for login flow", None)
        assert "tester" in roles

    def test_architecture_keyword_triggers_architect_role(self):
        """Architecture keywords should match architect role."""
        roles = _predict_auto_roles("Design system architecture for scalability", None)
        assert "architect" in roles

    def test_chinese_keywords_match(self):
        """Chinese keywords should also match correctly."""
        roles = _predict_auto_roles("设计一个安全的认证架构", None)
        assert "security" in roles or "architect" in roles

    def test_empty_falls_back_to_default(self):
        """Empty/generic task should fall back to default 3 roles."""
        roles = _predict_auto_roles("hello world", None)
        assert len(roles) >= 1
        assert len(roles) <= 4

    def test_caps_at_4_roles(self):
        """Result should never exceed 4 roles (for compact viz)."""
        text = "security test deploy ui architecture requirement"
        roles = _predict_auto_roles(text, None)
        assert len(roles) <= 4

    def test_dispatcher_analyze_task_preferred_over_fallback(self):
        """When dispatcher.analyze_task() returns valid roles, use them."""

        class MockDispatcher:
            def analyze_task(self, task):
                return [
                    {"name": "architect", "confidence": 0.9, "reason": "design"},
                    {"name": "tester", "confidence": 0.7, "reason": "test"},
                ]

        roles = _predict_auto_roles("any task", MockDispatcher())
        assert roles == ["architect", "tester"]

    def test_dispatcher_failure_falls_back_gracefully(self):
        """When dispatcher.analyze_task() raises, fall back to keywords."""

        class BrokenDispatcher:
            def analyze_task(self, task):
                raise RuntimeError("LLM unavailable")

        roles = _predict_auto_roles("security audit", BrokenDispatcher())
        assert "security" in roles


class TestRolePipelineColors:
    """Verify: pipeline colors follow Morandi palette (per user_profile)."""

    def test_all_states_have_icons(self):
        """All 5 pipeline states must have icons."""
        for state in ("pending", "matching", "executing", "completed", "failed"):
            assert state in _ROLE_PIPELINE_ICONS, f"Missing icon: {state}"

    def test_all_states_have_colors(self):
        """All 5 pipeline states must have colors."""
        for state in ("pending", "matching", "executing", "completed", "failed"):
            assert state in _ROLE_PIPELINE_COLORS, f"Missing color: {state}"

    def test_completed_color_is_morandi_sage(self):
        """Completed state should use Morandi sage green (#8FA886)."""
        assert _ROLE_PIPELINE_COLORS["completed"] == "#8FA886"

    def test_failed_color_is_morandi_rose(self):
        """Failed state should use Morandi rose (#B58484)."""
        assert _ROLE_PIPELINE_COLORS["failed"] == "#B58484"


# ── W1-T2: Performance charts ──


class TestSafeFloat:
    """Verify: _safe_float handles all input types gracefully."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, 0.0),
            (0, 0.0),
            (0.0, 0.0),
            (100, 100.0),
            (99.5, 99.5),
            ("250", 250.0),
            ("99.9", 99.9),
            ("invalid", 0.0),
            ("", 0.0),
            ([], 0.0),
            ({}, 0.0),
        ],
    )
    def test_safe_float_conversions(self, value, expected):
        """All inputs should convert to expected float without raising."""
        result = _safe_float(value)
        assert result == expected, f"_safe_float({value!r}) = {result}, expected {expected}"

    def test_return_type_is_always_float(self):
        """Return type must always be float, never int or None."""
        assert isinstance(_safe_float(100), float)
        assert isinstance(_safe_float("100"), float)
        assert isinstance(_safe_float(None), float)


class TestMorandiChartColors:
    """Verify: chart colors follow Morandi palette."""

    def test_primary_is_morandi_blue_gray(self):
        """Primary chart color should be Morandi blue-gray (#7B9EA8)."""
        assert _MORANDI_CHART_COLORS["primary"] == "#7B9EA8"

    def test_success_is_morandi_sage(self):
        assert _MORANDI_CHART_COLORS["success"] == "#8FA886"

    def test_warning_is_morandi_tan(self):
        assert _MORANDI_CHART_COLORS["warning"] == "#C9A87C"

    def test_danger_is_morandi_rose(self):
        assert _MORANDI_CHART_COLORS["danger"] == "#B58484"

    def test_all_colors_are_hex(self):
        """All colors must be valid hex strings."""
        for name, color in _MORANDI_CHART_COLORS.items():
            assert color.startswith("#"), f"{name} color {color} is not hex"
            assert len(color) == 7, f"{name} color {color} has wrong length"


# ── W1-T3: DAG node interactivity ──


class TestBuildInteractiveDot:
    """Verify: _build_interactive_dot produces valid DOT with Morandi colors."""

    def setup_method(self):
        self.viz = DAGVisualizer()
        self.graph = self.viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)

    def test_returns_dot_string(self):
        """Result must be a string."""
        dot = _build_interactive_dot(self.graph)
        assert isinstance(dot, str)

    def test_contains_digraph_header(self):
        """DOT must start with digraph declaration."""
        dot = _build_interactive_dot(self.graph)
        assert "digraph lifecycle" in dot

    def test_contains_all_11_nodes(self):
        """All 11 lifecycle phases must appear in DOT."""
        dot = _build_interactive_dot(self.graph)
        for i in range(1, 12):
            assert f"P{i}" in dot, f"P{i} missing from DOT"

    def test_default_status_uses_morandi_background(self):
        """Pending nodes should use Morandi background color."""
        dot = _build_interactive_dot(self.graph)
        assert _GRAPHVIZ_STATUS_FILL["pending"] in dot

    def test_completed_status_uses_morandi_sage(self):
        """Completed nodes should use Morandi sage (#8FA886)."""
        # Update one node to completed
        self.viz.update_node_status(self.graph, "P1", "completed")
        dot = _build_interactive_dot(self.graph)
        assert _GRAPHVIZ_STATUS_FILL["completed"] in dot

    def test_failed_status_uses_morandi_rose(self):
        """Failed nodes should use Morandi rose (#B58484)."""
        self.viz.update_node_status(self.graph, "P2", "failed")
        dot = _build_interactive_dot(self.graph)
        assert _GRAPHVIZ_STATUS_FILL["failed"] in dot

    def test_role_included_in_label(self):
        """Node labels should include role information."""
        dot = _build_interactive_dot(self.graph)
        # P1 has role "product-manager" in DEFAULT_LIFECYCLE_PHASES
        assert "product-manager" in dot

    def test_edges_present(self):
        """DOT must include dependency edges."""
        dot = _build_interactive_dot(self.graph)
        # P2 depends on P1
        assert "P1 -> P2" in dot or "P1 -> P2;" in dot


class TestGraphvizStatusStyles:
    """Verify: all 6 status states have Morandi-aligned fill + font colors."""

    def test_all_6_statuses_have_fill_colors(self):
        """All 6 lifecycle states must have fill colors defined."""
        expected = {"pending", "running", "completed", "failed", "skipped", "blocked"}
        assert expected.issubset(set(_GRAPHVIZ_STATUS_FILL.keys()))

    def test_all_6_statuses_have_font_colors(self):
        """All 6 lifecycle states must have font colors defined."""
        expected = {"pending", "running", "completed", "failed", "skipped", "blocked"}
        assert expected.issubset(set(_GRAPHVIZ_STATUS_FONT.keys()))

    def test_pending_uses_morandi_background(self):
        """Pending fill should use Morandi background (#F5F3F0)."""
        assert _GRAPHVIZ_STATUS_FILL["pending"] == "#F5F3F0"

    def test_completed_uses_morandi_sage(self):
        """Completed fill should use Morandi sage (#8FA886)."""
        assert _GRAPHVIZ_STATUS_FILL["completed"] == "#8FA886"

    def test_failed_uses_morandi_rose(self):
        """Failed fill should use Morandi rose (#B58484)."""
        assert _GRAPHVIZ_STATUS_FILL["failed"] == "#B58484"

    def test_blocked_uses_morandi_muted_purple(self):
        """Blocked fill should use Morandi muted purple (#9B8AA4)."""
        assert _GRAPHVIZ_STATUS_FILL["blocked"] == "#9B8AA4"

    def test_all_colors_are_valid_hex(self):
        """All fill colors must be valid 7-char hex strings."""
        for status, color in _GRAPHVIZ_STATUS_FILL.items():
            assert color.startswith("#"), f"{status} fill {color} not hex"
            assert len(color) == 7, f"{status} fill {color} wrong length"


class TestDAGVisualizerUpdateNodeStatus:
    """Verify: node status updates propagate to interactive rendering."""

    def setup_method(self):
        self.viz = DAGVisualizer()
        self.graph = self.viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)

    def test_update_existing_node(self):
        """Updating an existing node should return True."""
        result = self.viz.update_node_status(self.graph, "P1", "completed")
        assert result is True
        assert self.graph.find_node("P1").status == "completed"

    def test_update_nonexistent_node(self):
        """Updating a non-existent node should return False."""
        result = self.viz.update_node_status(self.graph, "P99", "completed")
        assert result is False

    def test_all_statuses_assignable(self):
        """All 6 lifecycle statuses should be assignable."""
        for status in ("pending", "running", "completed", "failed", "skipped", "blocked"):
            assert self.viz.update_node_status(self.graph, "P3", status) is True
            assert self.graph.find_node("P3").status == status
