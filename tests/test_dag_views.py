"""P2-2 DAG 依赖图可视化单元测试。"""

from __future__ import annotations

import pytest

from scripts.dashboard.dag_views import (
    DEFAULT_LIFECYCLE_PHASES,
    DAGEdge,
    DAGGraph,
    DAGNode,
    DAGVisualizer,
)

# ============================================================
# 数据模型测试
# ============================================================


class TestDAGModels:
    def test_node_creation(self):
        node = DAGNode(node_id="P1", label="Requirements", status="pending")
        assert node.node_id == "P1"
        assert node.optional is False

    def test_edge_creation(self):
        edge = DAGEdge(source="P1", target="P2")
        assert edge.label == ""

    def test_graph_add_node(self):
        graph = DAGGraph()
        graph.add_node(DAGNode("P1", "Phase 1"))
        assert len(graph.nodes) == 1

    def test_graph_add_edge(self):
        graph = DAGGraph()
        graph.add_edge("P1", "P2")
        assert len(graph.edges) == 1

    def test_graph_find_node(self):
        graph = DAGGraph()
        node = DAGNode("P1", "Phase 1")
        graph.add_node(node)
        assert graph.find_node("P1") is node
        assert graph.find_node("P99") is None


# ============================================================
# DAGVisualizer 构建测试
# ============================================================


class TestDAGBuilder:
    def test_build_from_dict_phases(self):
        phases = [
            {"phase_id": "P1", "name": "Requirements", "dependencies": []},
            {"phase_id": "P2", "name": "Architecture", "dependencies": ["P1"]},
            {"phase_id": "P3", "name": "Implementation", "dependencies": ["P2"]},
        ]
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 2  # P1→P2, P2→P3

    def test_build_with_multiple_dependencies(self):
        phases = [
            {"phase_id": "P1", "name": "A", "dependencies": []},
            {"phase_id": "P2", "name": "B", "dependencies": ["P1"]},
            {"phase_id": "P3", "name": "C", "dependencies": ["P1"]},
            {"phase_id": "P4", "name": "D", "dependencies": ["P2", "P3"]},
        ]
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        assert len(graph.nodes) == 4
        # P1→P2, P1→P3, P2→P4, P3→P4 = 4 edges
        assert len(graph.edges) == 4

    def test_build_ignores_missing_dependencies(self):
        phases = [
            {"phase_id": "P1", "name": "A", "dependencies": ["P0_missing"]},
        ]
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 0  # P0_missing not in graph

    def test_build_preserves_optional_flag(self):
        phases = [
            {"phase_id": "P1", "name": "A", "dependencies": [], "optional": True},
        ]
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        assert graph.nodes[0].optional is True

    def test_build_from_dataclass_phases(self):
        from dataclasses import dataclass, field

        @dataclass
        class Phase:
            phase_id: str
            name: str
            dependencies: list = field(default_factory=list)

        phases = [
            Phase(phase_id="P1", name="A"),
            Phase(phase_id="P2", name="B", dependencies=["P1"]),
        ]
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_build_default_lifecycle(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        assert len(graph.nodes) == 11
        # P9 depends on P7 and P8
        p9_deps = [e for e in graph.edges if e.target == "P9"]
        assert len(p9_deps) == 2


# ============================================================
# Mermaid 输出测试
# ============================================================


class TestMermaidOutput:
    def test_mermaid_has_graph_directive(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        mermaid = viz.to_mermaid(graph)
        assert mermaid.startswith("graph TD")

    def test_mermaid_has_nodes(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        mermaid = viz.to_mermaid(graph)
        assert 'P1["Requirements"]' in mermaid
        assert 'P11["Monitoring"]' in mermaid

    def test_mermaid_has_edges(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        mermaid = viz.to_mermaid(graph)
        assert "P1 --> P2" in mermaid
        assert "P2 --> P3" in mermaid

    def test_mermaid_has_status_style(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        viz.update_node_status(graph, "P1", "completed")
        mermaid = viz.to_mermaid(graph)
        assert "style P1" in mermaid
        assert "#4caf50" in mermaid  # completed color

    def test_mermaid_sanitizes_labels(self):
        viz = DAGVisualizer()
        phases = [
            {"phase_id": "P1", "name": 'Phase [with] "quotes"', "dependencies": []},
        ]
        graph = viz.build_from_lifecycle(phases)
        mermaid = viz.to_mermaid(graph)
        assert "[" not in mermaid.split('P1["')[1].split('"]')[0]
        assert '"' not in mermaid.split('P1["')[1].split('"]')[0]


# ============================================================
# JSON 输出测试
# ============================================================


class TestJSONOutput:
    def test_json_structure(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        data = viz.to_json(graph)
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data

    def test_json_node_count(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        data = viz.to_json(graph)
        assert data["metadata"]["node_count"] == 11
        assert len(data["nodes"]) == 11

    def test_json_edge_count(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        data = viz.to_json(graph)
        assert data["metadata"]["edge_count"] == len(graph.edges)

    def test_json_status_summary(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        viz.update_node_status(graph, "P1", "completed")
        viz.update_node_status(graph, "P2", "running")
        data = viz.to_json(graph)
        summary = data["metadata"]["status_summary"]
        assert summary.get("completed") == 1
        assert summary.get("running") == 1
        assert summary.get("pending") == 9

    def test_json_node_fields(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        data = viz.to_json(graph)
        node = data["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "status" in node
        assert "role" in node


# ============================================================
# DOT 输出测试
# ============================================================


class TestDOTOutput:
    def test_dot_has_digraph_directive(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        dot = viz.to_dot(graph)
        assert dot.startswith("digraph lifecycle {")

    def test_dot_has_nodes(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        dot = viz.to_dot(graph)
        assert 'P1 [label="Requirements"' in dot

    def test_dot_has_edges(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        dot = viz.to_dot(graph)
        assert "P1 -> P2" in dot

    def test_dot_status_fillcolor(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        viz.update_node_status(graph, "P1", "completed")
        dot = viz.to_dot(graph)
        assert "#e0f0e0" in dot  # completed fillcolor

    def test_dot_optional_style(self):
        viz = DAGVisualizer()
        phases = [
            {"phase_id": "P1", "name": "A", "dependencies": [], "optional": True},
        ]
        graph = viz.build_from_lifecycle(phases)
        dot = viz.to_dot(graph)
        assert "filled,dashed" in dot


# ============================================================
# 节点状态更新测试
# ============================================================


class TestNodeStatusUpdate:
    def test_update_existing_node(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        result = viz.update_node_status(graph, "P1", "completed")
        assert result is True
        assert graph.find_node("P1").status == "completed"

    def test_update_nonexistent_node(self):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        result = viz.update_node_status(graph, "P99", "completed")
        assert result is False

    @pytest.mark.parametrize("status", ["pending", "running", "completed", "failed", "skipped", "blocked"])
    def test_all_status_types(self, status):
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(DEFAULT_LIFECYCLE_PHASES)
        result = viz.update_node_status(graph, "P3", status)
        assert result is True
        assert graph.find_node("P3").status == status


# ============================================================
# 默认 11 阶段生命周期完整性测试
# ============================================================


class TestDefaultLifecycle:
    def test_default_has_11_phases(self):
        assert len(DEFAULT_LIFECYCLE_PHASES) == 11

    def test_default_phase_ids_sequential(self):
        ids = [p["phase_id"] for p in DEFAULT_LIFECYCLE_PHASES]
        assert ids == [f"P{i}" for i in range(1, 12)]

    def test_default_p9_has_two_dependencies(self):
        p9 = next(p for p in DEFAULT_LIFECYCLE_PHASES if p["phase_id"] == "P9")
        assert len(p9["dependencies"]) == 2
        assert "P7" in p9["dependencies"]
        assert "P8" in p9["dependencies"]

    def test_default_p1_has_no_dependencies(self):
        p1 = next(p for p in DEFAULT_LIFECYCLE_PHASES if p["phase_id"] == "P1")
        assert p1["dependencies"] == []

    def test_default_all_phases_have_role(self):
        for phase in DEFAULT_LIFECYCLE_PHASES:
            assert phase["role_id"], f"Phase {phase['phase_id']} missing role_id"
