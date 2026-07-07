"""V4.0.0 P2-2: DAG 依赖图可视化。

借鉴 TraeMultiAgentSkill 的 dag_visualizer.py 理念：
- 将生命周期 11 阶段 + 依赖关系渲染为 DAG 图
- 三种格式输出: Mermaid / JSON / DOT
- 节点状态实时更新 (pending/running/completed/failed/skipped/blocked)

集成到 Dashboard "DAG View" 页面 (使用 st.mermaid 渲染)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    """DAG 节点。"""

    node_id: str
    label: str
    status: str = "pending"  # pending/running/completed/failed/skipped/blocked
    role: str = ""
    description: str = ""
    optional: bool = False
    order: int = 0


@dataclass
class DAGEdge:
    """DAG 边。"""

    source: str
    target: str
    label: str = ""


@dataclass
class DAGGraph:
    """DAG 图数据结构。"""

    nodes: list[DAGNode] = field(default_factory=list)
    edges: list[DAGEdge] = field(default_factory=list)

    def add_node(self, node: DAGNode) -> None:
        self.nodes.append(node)

    def add_edge(self, source: str, target: str, label: str = "") -> None:
        self.edges.append(DAGEdge(source=source, target=target, label=label))

    def find_node(self, node_id: str) -> DAGNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None


# Mermaid 节点状态样式
_MERMAID_STATUS_STYLE: dict[str, str] = {
    "pending": "fill:#f0f0f0,stroke:#999,color:#333",
    "running": "fill:#fff4e0,stroke:#ff9800,color:#000",
    "completed": "fill:#e0f0e0,stroke:#4caf50,color:#000",
    "failed": "fill:#fde0e0,stroke:#f44336,color:#000",
    "skipped": "fill:#f5f5f5,stroke:#bbb,color:#999,stroke-dasharray: 5 5",
    "blocked": "fill:#eee0ff,stroke:#9c27b0,color:#000",
}


class DAGVisualizer:
    """DAG 依赖图可视化器。

    支持三种输出格式：
    - Mermaid: 用于 Dashboard st.mermaid() 渲染
    - JSON: 用于 API 端点 /api/v1/dag
    - DOT: 用于 Graphviz 渲染

    Usage:
        viz = DAGVisualizer()
        graph = viz.build_from_lifecycle(phases)
        mermaid_text = viz.to_mermaid(graph)
    """

    def build_from_lifecycle(self, phases: list[Any]) -> DAGGraph:
        """从生命周期阶段列表构建 DAG 图。

        Args:
            phases: PhaseDefinition 列表（或 dict 列表），每个包含:
                - phase_id / id
                - name
                - description (optional)
                - role_id / role (optional)
                - dependencies (list of phase IDs)
                - optional (bool)
                - order (int)

        Returns:
            DAGGraph 包含节点和边。
        """
        graph = DAGGraph()

        # 添加节点
        for phase in phases:
            node = self._phase_to_node(phase)
            graph.add_node(node)

        # 添加边（基于 dependencies）
        node_ids = {n.node_id for n in graph.nodes}
        for phase in phases:
            phase_id = self._get_attr(phase, "phase_id", "id", "")
            deps = self._get_attr(phase, "dependencies", "deps", []) or []
            for dep in deps:
                if dep in node_ids:
                    graph.add_edge(source=dep, target=phase_id)

        return graph

    def to_mermaid(self, graph: DAGGraph) -> str:
        """生成 Mermaid 格式 DAG 图。"""
        lines: list[str] = ["graph TD"]

        # 节点定义
        for node in graph.nodes:
            safe_label = self._sanitize_mermaid_label(node.label)
            lines.append(f'    {node.node_id}["{safe_label}"]')

        # 边定义
        for edge in graph.edges:
            if edge.label:
                safe_label = self._sanitize_mermaid_label(edge.label)
                lines.append(f"    {edge.source} -->|{safe_label}| {edge.target}")
            else:
                lines.append(f"    {edge.source} --> {edge.target}")

        # 状态样式
        lines.append("")
        lines.append("    %% Node status styling")
        for node in graph.nodes:
            style = _MERMAID_STATUS_STYLE.get(node.status)
            if style:
                lines.append(f"    style {node.node_id} {style}")

        # classDef
        lines.append("    classDef optional stroke-dasharray: 5 5;")
        for node in graph.nodes:
            if node.optional:
                lines.append(f"    class {node.node_id} optional;")

        return "\n".join(lines)

    def to_json(self, graph: DAGGraph) -> dict[str, Any]:
        """生成 JSON 格式 DAG 数据。"""
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "status": n.status,
                    "role": n.role,
                    "description": n.description,
                    "optional": n.optional,
                    "order": n.order,
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "label": e.label,
                }
                for e in graph.edges
            ],
            "metadata": {
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "status_summary": self._status_summary(graph),
            },
        }

    def to_dot(self, graph: DAGGraph) -> str:
        """生成 DOT 格式 DAG 图 (Graphviz)。"""
        lines: list[str] = ["digraph lifecycle {", "    rankdir=TB;", "    node [shape=box, style=filled];"]

        # 节点
        status_fillcolor = {
            "pending": "#f0f0f0",
            "running": "#fff4e0",
            "completed": "#e0f0e0",
            "failed": "#fde0e0",
            "skipped": "#f5f5f5",
            "blocked": "#eee0ff",
        }
        for node in graph.nodes:
            fillcolor = status_fillcolor.get(node.status, "#f0f0f0")
            safe_label = self._sanitize_dot_label(node.label)
            attrs = [
                f'label="{safe_label}"',
                f'fillcolor="{fillcolor}"',
            ]
            if node.optional:
                attrs.append('style="filled,dashed"')
            lines.append(f'    {node.node_id} [{", ".join(attrs)}];')

        # 边
        for edge in graph.edges:
            if edge.label:
                safe_label = self._sanitize_dot_label(edge.label)
                lines.append(f'    {edge.source} -> {edge.target} [label="{safe_label}"];')
            else:
                lines.append(f"    {edge.source} -> {edge.target};")

        lines.append("}")
        return "\n".join(lines)

    def update_node_status(self, graph: DAGGraph, node_id: str, status: str) -> bool:
        """更新节点状态。

        Args:
            graph: DAG 图。
            node_id: 节点 ID。
            status: 新状态 (pending/running/completed/failed/skipped/blocked)。

        Returns:
            True 如果节点存在并更新成功。
        """
        node = graph.find_node(node_id)
        if node is None:
            return False
        node.status = status
        return True

    def _phase_to_node(self, phase: Any) -> DAGNode:
        """将 PhaseDefinition（dataclass 或 dict）转换为 DAGNode。"""
        return DAGNode(
            node_id=self._get_attr(phase, "phase_id", "id", ""),
            label=self._get_attr(phase, "name", "label", "unnamed"),
            status="pending",
            role=self._get_attr(phase, "role_id", "role", ""),
            description=self._get_attr(phase, "description", "desc", ""),
            optional=self._get_attr(phase, "optional", "", False),
            order=self._get_attr(phase, "order", "", 0),
        )

    @staticmethod
    def _get_attr(obj: Any, primary: str, fallback: str, default: Any) -> Any:
        """从 dataclass 或 dict 获取属性，支持主备字段名。"""
        if hasattr(obj, primary):
            return getattr(obj, primary)
        if fallback and hasattr(obj, fallback):
            return getattr(obj, fallback)
        if isinstance(obj, dict):
            if primary in obj:
                return obj[primary]
            if fallback and fallback in obj:
                return obj[fallback]
        return default

    @staticmethod
    def _status_summary(graph: DAGGraph) -> dict[str, int]:
        """统计各状态节点数。"""
        summary: dict[str, int] = {}
        for node in graph.nodes:
            summary[node.status] = summary.get(node.status, 0) + 1
        return summary

    @staticmethod
    def _sanitize_mermaid_label(label: str) -> str:
        """转义 Mermaid 标签中的特殊字符。"""
        return label.replace('"', "'").replace("[", "(").replace("]", ")")

    @staticmethod
    def _sanitize_dot_label(label: str) -> str:
        """转义 DOT 标签中的特殊字符。"""
        return label.replace('"', "'").replace("\n", " ")


def render_dag_view(protocol_data: dict[str, Any] | None) -> None:
    """渲染 DAG 依赖图页面（Dashboard 集成入口）。

    Args:
        protocol_data: load_lifecycle_protocol() 返回的字典，可为 None。
    """
    import streamlit as st  # noqa: E402 — 软依赖

    st.subheader("🔗 DAG 依赖图可视化")

    viz = DAGVisualizer()

    # 优先从 protocol_data 加载阶段，否则使用默认 11 阶段
    phases = protocol_data["phases"] if protocol_data and "phases" in protocol_data else DEFAULT_LIFECYCLE_PHASES

    graph = viz.build_from_lifecycle(phases)

    # 从 protocol 状态更新节点状态
    if protocol_data and "protocol" in protocol_data:
        try:
            protocol = protocol_data["protocol"]
            status = protocol.get_status()
            for phase_id in getattr(status, "completed_phases", []) or []:
                viz.update_node_status(graph, phase_id, "completed")
            for phase_id in getattr(status, "failed_phases", []) or []:
                viz.update_node_status(graph, phase_id, "failed")
        except (AttributeError, RuntimeError) as e:
            st.warning(f"Failed to load phase status: {e}")

    # 格式选择
    fmt = st.radio("Format", ["Mermaid", "JSON", "DOT"], horizontal=True, label_visibility="collapsed")

    if fmt == "Mermaid":
        mermaid_text = viz.to_mermaid(graph)
        try:
            st.mermaid(mermaid_text)
        except (AttributeError, RuntimeError):
            # Streamlit < 1.29 不支持 st.mermaid
            st.code(mermaid_text, language="mermaid")
        with st.expander("Raw Mermaid"):
            st.code(mermaid_text, language="mermaid")

    elif fmt == "JSON":
        data = viz.to_json(graph)
        st.json(data)
        st.download_button(
            label="Download JSON",
            data=str(data).encode(),
            file_name="lifecycle_dag.json",
            mime="application/json",
        )

    else:  # DOT
        dot_text = viz.to_dot(graph)
        st.code(dot_text, language="dot")
        st.download_button(
            label="Download DOT",
            data=dot_text.encode(),
            file_name="lifecycle_dag.dot",
            mime="text/plain",
        )

    # 状态图例
    st.divider()
    st.caption("**状态图例**")
    cols = st.columns(6)
    legends = [
        ("Pending", "#f0f0f0"),
        ("Running", "#fff4e0"),
        ("Completed", "#e0f0e0"),
        ("Failed", "#fde0e0"),
        ("Skipped", "#f5f5f5"),
        ("Blocked", "#eee0ff"),
    ]
    for col, (label, color) in zip(cols, legends):
        col.markdown(
            f'<div style="background:{color};padding:8px;border-radius:4px;'
            f'border:1px solid #999;text-align:center;">{label}</div>',
            unsafe_allow_html=True,
        )


# 默认 11 阶段生命周期 DAG（与 dispatch_lifecycle.py 一致）
DEFAULT_LIFECYCLE_PHASES: list[dict[str, Any]] = [
    {"phase_id": "P1", "name": "Requirements", "role_id": "product-manager", "dependencies": [], "order": 1},
    {"phase_id": "P2", "name": "Architecture", "role_id": "architect", "dependencies": ["P1"], "order": 2},
    {"phase_id": "P3", "name": "Implementation", "role_id": "solo-coder", "dependencies": ["P2"], "order": 3},
    {"phase_id": "P4", "name": "Review", "role_id": "solo-coder", "dependencies": ["P3"], "order": 4},
    {"phase_id": "P5", "name": "Integration", "role_id": "devops", "dependencies": ["P4"], "order": 5},
    {"phase_id": "P6", "name": "Security", "role_id": "security", "dependencies": ["P2"], "order": 6},
    {"phase_id": "P7", "name": "TestPlanning", "role_id": "tester", "dependencies": ["P2"], "order": 7},
    {"phase_id": "P8", "name": "Optimization", "role_id": "solo-coder", "dependencies": ["P5"], "order": 8},
    {"phase_id": "P9", "name": "TestExecution", "role_id": "tester", "dependencies": ["P7", "P8"], "order": 9},
    {"phase_id": "P10", "name": "Delivery", "role_id": "devops", "dependencies": ["P9"], "order": 10},
    {"phase_id": "P11", "name": "Monitoring", "role_id": "devops", "dependencies": ["P10"], "order": 11},
]


__all__ = [
    "DEFAULT_LIFECYCLE_PHASES",
    "DAGEdge",
    "DAGGraph",
    "DAGNode",
    "DAGVisualizer",
    "render_dag_view",
]
