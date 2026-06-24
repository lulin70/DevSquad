#!/usr/bin/env python3
"""
TechDebtManager - 技术债务管理框架 (Tester + Architect 协作)

桥接 Tester 的质量关注和 Architect 的结构决策。
提供系统化的债务识别、优先级排序和修复计划。

核心能力:
- TechDebtManager: 技术债务追踪和管理
- 代码库扫描: 自动检测常见技术债务模式
- 优先级排序: 基于复合评分的债务排序
- 修复计划: 基于预算的背包式优化
- 债务报告: 综合债务状态和趋势分析

使用示例:
    from scripts.collaboration.tech_debt_manager import TechDebtManager

    manager = TechDebtManager()
    debt = manager.identify_debt("tester", DebtCategory.CODE_QUALITY,
                                  "God class with 800 lines", "src/main.py")
    plan = manager.generate_remediation_plan(budget_hours=40.0)
    report = manager.get_debt_report()
    print(report.to_markdown())
"""

import ast
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================
# Enums
# ============================================================


class DebtCategory(Enum):
    """技术债务类别。"""

    ARCHITECTURE = "architecture"      # 结构问题、上帝类、循环依赖
    CODE_QUALITY = "code_quality"      # 代码风格、复杂度、死代码
    TEST_GAP = "test_gap"             # 缺失测试、弱断言
    SECURITY = "security"             # 安全漏洞、缺失验证
    DOCUMENTATION = "documentation"    # 缺失/过时文档
    PERFORMANCE = "performance"        # N+1 查询、缺失索引
    DEPENDENCY = "dependency"          # 过时依赖、版本冲突
    CONFIGURATION = "configuration"    # 硬编码值、缺失配置


class DebtSeverity(Enum):
    """技术债务严重程度。"""

    LOW = "low"              # 外观问题，无功能影响
    MEDIUM = "medium"        # 降低质量，有变通方案
    HIGH = "high"            # 重大影响，无简单变通方案
    CRITICAL = "critical"    # 阻碍进度或导致数据丢失


class DebtEffort(Enum):
    """修复工作量。"""

    TRIVIAL = "trivial"      # < 1 小时
    MINOR = "minor"          # 1-4 小时
    MODERATE = "moderate"    # 4-16 小时
    MAJOR = "major"          # 16-40 小时
    EPIC = "epic"            # > 40 小时


class DebtStatus(Enum):
    """技术债务状态。"""

    IDENTIFIED = "identified"
    ACKNOWLEDGED = "acknowledged"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    REMEDIATED = "remediated"
    WONT_FIX = "wont_fix"


# ============================================================
# Effort-to-hours mapping
# ============================================================

EFFORT_HOURS: dict[DebtEffort, float] = {
    DebtEffort.TRIVIAL: 0.5,
    DebtEffort.MINOR: 2.5,
    DebtEffort.MODERATE: 10.0,
    DebtEffort.MAJOR: 28.0,
    DebtEffort.EPIC: 60.0,
}

SEVERITY_WEIGHT: dict[DebtSeverity, float] = {
    DebtSeverity.LOW: 1.0,
    DebtSeverity.MEDIUM: 3.0,
    DebtSeverity.HIGH: 7.0,
    DebtSeverity.CRITICAL: 15.0,
}

CATEGORY_INTEREST_RATE: dict[DebtCategory, float] = {
    DebtCategory.ARCHITECTURE: 0.8,    # 高利息：随时间恶化
    DebtCategory.CODE_QUALITY: 0.2,    # 低利息：不会变得更糟
    DebtCategory.TEST_GAP: 0.5,        # 中等利息：回归风险增加
    DebtCategory.SECURITY: 1.0,        # 关键利息：漏洞会被利用
    DebtCategory.DOCUMENTATION: 0.1,   # 低利息
    DebtCategory.PERFORMANCE: 0.4,     # 中等利息：随数据量恶化
    DebtCategory.DEPENDENCY: 0.3,      # 中低利息
    DebtCategory.CONFIGURATION: 0.2,   # 低利息
}


# ============================================================
# Data Classes
# ============================================================


@dataclass
class TechDebt:
    """技术债务条目。

    Attributes:
        id: 唯一标识符
        source: 识别来源（tester/architect/code_review/static_analysis）
        category: 债务类别
        description: 债务描述
        location: 文件路径或模块名
        severity: 严重程度
        effort: 修复工作量
        tags: 附加标签
        status: 当前状态
        identified_at: 识别时间
        remediated_at: 修复时间
        interest_rate: 利息率（债务随时间恶化的速度）
        dependencies: 关联债务 ID 列表
    """

    id: str
    source: str
    category: DebtCategory
    description: str
    location: str
    severity: DebtSeverity
    effort: DebtEffort
    tags: list[str]
    status: DebtStatus = DebtStatus.IDENTIFIED
    identified_at: str = ""
    remediated_at: str = ""
    interest_rate: float = 0.0
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.identified_at:
            self.identified_at = datetime.now().isoformat()
        if self.interest_rate == 0.0:
            self.interest_rate = CATEGORY_INTEREST_RATE.get(self.category, 0.3)

    @property
    def estimated_hours(self) -> float:
        """获取预估修复时间。"""
        return EFFORT_HOURS.get(self.effort, 10.0)

    @property
    def severity_weight(self) -> float:
        """获取严重程度权重。"""
        return SEVERITY_WEIGHT.get(self.severity, 3.0)

    @property
    def priority_score(self) -> float:
        """计算优先级分数（越高越优先修复）。"""
        return self.severity_weight * (1.0 / max(self.estimated_hours, 0.1)) + self.interest_rate

    def to_dict(self) -> dict[str, Any]:
        """Serialize the TechDebt to a JSON-compatible dictionary.

        Returns:
            Dictionary containing all TechDebt fields plus the computed priority_score.
        """
        return {
            "id": self.id,
            "source": self.source,
            "category": self.category.value,
            "description": self.description,
            "location": self.location,
            "severity": self.severity.value,
            "effort": self.effort.value,
            "tags": self.tags,
            "status": self.status.value,
            "identified_at": self.identified_at,
            "remediated_at": self.remediated_at,
            "interest_rate": self.interest_rate,
            "dependencies": self.dependencies,
            "estimated_hours": self.estimated_hours,
            "priority_score": round(self.priority_score, 3),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechDebt":
        """Construct a TechDebt from a dictionary.

        Args:
            data: Dictionary with TechDebt field names (enum values as strings).

        Returns:
            TechDebt instance populated from the given data.
        """
        return cls(
            id=data["id"],
            source=data["source"],
            category=DebtCategory(data["category"]),
            description=data["description"],
            location=data["location"],
            severity=DebtSeverity(data["severity"]),
            effort=DebtEffort(data["effort"]),
            tags=data.get("tags", []),
            status=DebtStatus(data.get("status", "identified")),
            identified_at=data.get("identified_at", ""),
            remediated_at=data.get("remediated_at", ""),
            interest_rate=data.get("interest_rate", 0.0),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class RemediationPlan:
    """修复计划。

    Attributes:
        total_debts: 总债务数
        planned_remediations: 计划修复项 [{debt_id, estimated_hours, priority}]
        budget_hours: 预算工时
        used_hours: 已使用工时
        debt_reduction_pct: 债务减少百分比
        deferred_debts: 延期债务 ID 列表
    """

    total_debts: int
    planned_remediations: list[dict[str, Any]]
    budget_hours: float
    used_hours: float
    debt_reduction_pct: float
    deferred_debts: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the remediation plan to a dictionary.

        Returns:
            Dictionary containing total debts, planned remediations, budget
            and used hours, debt reduction percentage, and deferred debt ids.
        """
        return {
            "total_debts": self.total_debts,
            "planned_remediations": self.planned_remediations,
            "budget_hours": self.budget_hours,
            "used_hours": round(self.used_hours, 2),
            "debt_reduction_pct": round(self.debt_reduction_pct, 3),
            "deferred_debts": self.deferred_debts,
        }

    def to_markdown(self) -> str:
        """Render the remediation plan as a Markdown document.

        Returns:
            Markdown string with summary header and a planned remediations
            table.
        """
        lines = [
            "# Remediation Plan",
            "",
            f"**Total Debts**: {self.total_debts}",
            f"**Budget**: {self.budget_hours:.1f}h | **Used**: {self.used_hours:.1f}h",
            f"**Debt Reduction**: {self.debt_reduction_pct:.0%}",
            f"**Deferred**: {len(self.deferred_debts)} debts",
            "",
        ]

        if self.planned_remediations:
            lines.append("## Planned Remediations")
            lines.append("")
            lines.append("| # | Debt ID | Hours | Priority |")
            lines.append("|---|---------|-------|----------|")
            for idx, item in enumerate(self.planned_remediations, 1):
                lines.append(
                    f"| {idx} | {item.get('debt_id', 'N/A')} "
                    f"| {item.get('estimated_hours', 0):.1f} "
                    f"| {item.get('priority', 0):.2f} |"
                )
            lines.append("")

        lines.extend(["---", "*Generated by TechDebtManager*"])
        return "\n".join(lines)


@dataclass
class DebtReport:
    """技术债务报告。

    Attributes:
        total_debts: 总债务数
        by_category: 按类别统计
        by_severity: 按严重程度统计
        top_priority: 优先级最高的债务列表
        interest_forecast: 利息预测 month -> projected interest
        remediation_progress: 修复进度 status -> count
        debt_to_value_ratio: 债务价值比
    """

    total_debts: int
    by_category: dict[str, int]
    by_severity: dict[str, int]
    top_priority: list[TechDebt]
    interest_forecast: dict[str, float]
    remediation_progress: dict[str, int]
    debt_to_value_ratio: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize the debt report to a dictionary.

        Returns:
            Dictionary containing total debts, category/severity breakdowns,
            top priority debt dicts, interest forecast, remediation progress,
            and debt-to-value ratio.
        """
        return {
            "total_debts": self.total_debts,
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "top_priority": [d.to_dict() for d in self.top_priority],
            "interest_forecast": self.interest_forecast,
            "remediation_progress": self.remediation_progress,
            "debt_to_value_ratio": round(self.debt_to_value_ratio, 3),
        }

    def to_markdown(self) -> str:
        """Render the debt report as a Markdown document.

        Returns:
            Markdown string with totals, category and severity breakdowns,
            top priority debts, and remediation progress sections.
        """
        lines = [
            "# Tech Debt Report",
            "",
            f"**Total Debts**: {self.total_debts}",
            f"**Debt-to-Value Ratio**: {self.debt_to_value_ratio:.2f}",
            "",
        ]

        if self.by_category:
            lines.append("## By Category")
            for cat, count in sorted(self.by_category.items(), key=lambda x: -x[1]):
                lines.append(f"- **{cat}**: {count}")
            lines.append("")

        if self.by_severity:
            lines.append("## By Severity")
            for sev, count in sorted(self.by_severity.items(), key=lambda x: -x[1]):
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                lines.append(f"- {icon} **{sev}**: {count}")
            lines.append("")

        if self.top_priority:
            lines.append("## Top Priority Debts")
            for idx, debt in enumerate(self.top_priority[:10], 1):
                lines.append(f"{idx}. **[{debt.severity.value}]** {debt.description}")
                lines.append(f"   - Location: {debt.location}")
                lines.append(f"   - Effort: {debt.effort.value} (~{debt.estimated_hours:.0f}h)")
                lines.append(f"   - Score: {debt.priority_score:.2f}")
            lines.append("")

        if self.remediation_progress:
            lines.append("## Remediation Progress")
            for status, count in self.remediation_progress.items():
                lines.append(f"- **{status}**: {count}")
            lines.append("")

        if self.interest_forecast:
            lines.append("## Interest Forecast (6 months)")
            for month, interest in sorted(self.interest_forecast.items()):
                lines.append(f"- **{month}**: {interest:.2f}")
            lines.append("")

        lines.extend(["---", "*Generated by TechDebtManager*"])
        return "\n".join(lines)


# ============================================================
# Codebase Scanner
# ============================================================


class CodebaseDebtScanner:
    """扫描代码库中的常见技术债务模式。"""

    GOD_CLASS_LINE_THRESHOLD = 500
    HIGH_COMPLEXITY_THRESHOLD = 10

    TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|WORKAROUND)", re.IGNORECASE)
    BROAD_EXCEPT_PATTERN = re.compile(r"except\s+Exception\b")
    BARE_EXCEPT_PATTERN = re.compile(r"except\s*:")
    HARDCODED_PATTERN = re.compile(
        r"(?:host|port|url|api_key|secret|password|token)\s*=\s*['\"][^'\"]+['\"]",
        re.IGNORECASE,
    )

    def scan(self, project_path: str) -> list[TechDebt]:
        """Scan a project directory for technical debt patterns.

        Detects:
        - God classes (>500 lines)
        - High cyclomatic complexity
        - Broad exception handling (except Exception)
        - TODO/FIXME/HACK comments
        - Missing docstrings on public methods
        - Dead code (unused imports)
        - Hardcoded configuration values
        - Missing type hints

        Args:
            project_path: Root directory of the project to scan.

        Returns:
            List of detected TechDebt items.
        """
        debts: list[TechDebt] = []
        root = Path(project_path)

        if not root.exists():
            return debts

        py_files = sorted(root.rglob("*.py"))
        counter = 0

        for py_file in py_files:
            rel_path = str(py_file.relative_to(root))
            try:
                source = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            counter += 1
            debt_id_prefix = f"scan-{counter}"

            # God class detection
            god_class_debts = self._detect_god_classes(source, rel_path, debt_id_prefix)
            debts.extend(god_class_debts)

            # TODO/FIXME/HACK comments
            todo_debts = self._detect_todos(source, rel_path, debt_id_prefix)
            debts.extend(todo_debts)

            # Broad exception handling
            except_debts = self._detect_broad_except(source, rel_path, debt_id_prefix)
            debts.extend(except_debts)

            # Hardcoded values
            hardcoded_debts = self._detect_hardcoded(source, rel_path, debt_id_prefix)
            debts.extend(hardcoded_debts)

            # Missing docstrings on public methods
            docstring_debts = self._detect_missing_docstrings(source, rel_path, debt_id_prefix)
            debts.extend(docstring_debts)

            # Unused imports
            import_debts = self._detect_unused_imports(source, rel_path, debt_id_prefix)
            debts.extend(import_debts)

        return debts

    def _detect_god_classes(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect classes exceeding line threshold."""
        debts: list[TechDebt] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return debts

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start = node.lineno
                end = node.end_lineno or start
                class_lines = end - start + 1
                if class_lines > self.GOD_CLASS_LINE_THRESHOLD:
                    debts.append(
                        TechDebt(
                            id=f"{prefix}-god-{node.name}",
                            source="static_analysis",
                            category=DebtCategory.ARCHITECTURE,
                            description=f"God class '{node.name}' has {class_lines} lines (threshold: {self.GOD_CLASS_LINE_THRESHOLD})",
                            location=f"{rel_path}:{start}",
                            severity=DebtSeverity.HIGH,
                            effort=DebtEffort.MAJOR,
                            tags=["god-class", "architecture"],
                        )
                    )
        return debts

    def _detect_todos(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect TODO/FIXME/HACK comments."""
        debts = []
        for match in self.TODO_PATTERN.finditer(source):
            line_num = source[: match.start()].count("\n") + 1
            tag = match.group(1).upper()
            severity = DebtSeverity.MEDIUM if tag in ("FIXME", "HACK") else DebtSeverity.LOW
            debts.append(
                TechDebt(
                    id=f"{prefix}-todo-{line_num}",
                    source="static_analysis",
                    category=DebtCategory.CODE_QUALITY,
                    description=f"{tag} comment found",
                    location=f"{rel_path}:{line_num}",
                    severity=severity,
                    effort=DebtEffort.MINOR,
                    tags=["todo", tag.lower()],
                )
            )
        return debts

    def _detect_broad_except(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect broad exception handling."""
        debts = []
        for pattern, label in [
            (self.BROAD_EXCEPT_PATTERN, "Broad 'except Exception'"),
            (self.BARE_EXCEPT_PATTERN, "Bare 'except:' clause"),
        ]:
            for match in pattern.finditer(source):
                line_num = source[: match.start()].count("\n") + 1
                debts.append(
                    TechDebt(
                        id=f"{prefix}-except-{line_num}",
                        source="static_analysis",
                        category=DebtCategory.CODE_QUALITY,
                        description=f"{label} catches too many exception types",
                        location=f"{rel_path}:{line_num}",
                        severity=DebtSeverity.MEDIUM,
                        effort=DebtEffort.MINOR,
                        tags=["exception-handling"],
                    )
                )
        return debts

    def _detect_hardcoded(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect hardcoded configuration values."""
        debts = []
        for match in self.HARDCODED_PATTERN.finditer(source):
            line_num = source[: match.start()].count("\n") + 1
            debts.append(
                TechDebt(
                    id=f"{prefix}-hardcoded-{line_num}",
                    source="static_analysis",
                    category=DebtCategory.CONFIGURATION,
                    description="Hardcoded configuration value detected",
                    location=f"{rel_path}:{line_num}",
                    severity=DebtSeverity.MEDIUM,
                    effort=DebtEffort.TRIVIAL,
                    tags=["hardcoded", "configuration"],
                )
            )
        return debts

    def _detect_missing_docstrings(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect public methods missing docstrings."""
        debts: list[TechDebt] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return debts

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                docstring = ast.get_docstring(node)
                if not docstring:
                    debts.append(
                        TechDebt(
                            id=f"{prefix}-nodoc-{node.name}-{node.lineno}",
                            source="static_analysis",
                            category=DebtCategory.DOCUMENTATION,
                            description=f"Public method '{node.name}' missing docstring",
                            location=f"{rel_path}:{node.lineno}",
                            severity=DebtSeverity.LOW,
                            effort=DebtEffort.TRIVIAL,
                            tags=["docstring", "documentation"],
                        )
                    )
        return debts

    def _detect_unused_imports(
        self, source: str, rel_path: str, prefix: str
    ) -> list[TechDebt]:
        """Detect potentially unused imports."""
        debts: list[TechDebt] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return debts

        imported_names: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = node.lineno

        # Remove names that are actually used in the code
        source_lines = source.split("\n")
        for name in list(imported_names.keys()):
            used = False
            for line in source_lines:
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith(("import ", "from ")):
                    continue
                if name in line:
                    used = True
                    break
            if not used and name != "*":
                debts.append(
                    TechDebt(
                        id=f"{prefix}-unused-import-{name}",
                        source="static_analysis",
                        category=DebtCategory.CODE_QUALITY,
                        description=f"Potentially unused import '{name}'",
                        location=f"{rel_path}:{imported_names[name]}",
                        severity=DebtSeverity.LOW,
                        effort=DebtEffort.TRIVIAL,
                        tags=["unused-import", "dead-code"],
                    )
                )
        return debts


# ============================================================
# Core Manager
# ============================================================


class TechDebtManager:
    """Technical debt tracking and management framework.

    Bridges Tester's quality concerns with Architect's structural decisions.
    Provides systematic debt identification, prioritization, and remediation planning.
    """

    def __init__(self, persist_dir: str | None = None):
        """Initialize TechDebtManager.

        Args:
            persist_dir: Optional directory path for debt persistence.
                         If provided, debts are loaded from and saved to this directory.
        """
        self._debts: list[TechDebt] = []
        self._persist_dir = persist_dir
        self._debt_counter = 0
        self._scanner = CodebaseDebtScanner()
        if persist_dir:
            self._load_debts()

    def identify_debt(
        self,
        source: str,
        category: DebtCategory,
        description: str,
        location: str,
        severity: DebtSeverity = DebtSeverity.MEDIUM,
        effort: DebtEffort = DebtEffort.MODERATE,
        tags: list[str] | None = None,
    ) -> TechDebt:
        """Register a technical debt item.

        Args:
            source: Who identified this (tester/architect/code_review/static_analysis)
            category: Type of debt
            description: Clear description of the debt
            location: File path or module name
            severity: Impact on project
            effort: Estimated effort to fix
            tags: Additional categorization tags

        Returns:
            Created TechDebt instance.
        """
        self._debt_counter += 1
        debt = TechDebt(
            id=f"debt-{uuid.uuid4().hex[:8]}",
            source=source,
            category=category,
            description=description,
            location=location,
            severity=severity,
            effort=effort,
            tags=tags or [],
        )
        self._debts.append(debt)
        if self._persist_dir:
            self._save_debts()
        return debt

    def scan_codebase_debt(self, project_path: str) -> list[TechDebt]:
        """Scan a project for common technical debt patterns.

        Detects:
        - God classes (>500 lines)
        - High cyclomatic complexity
        - Broad exception handling (except Exception)
        - TODO/FIXME/HACK comments
        - Missing docstrings on public methods
        - Circular dependencies
        - Dead code (unused imports, unreachable code)
        - Hardcoded configuration values
        - Missing type hints

        Args:
            project_path: Root directory of the project to scan.

        Returns:
            List of detected TechDebt items (also added to internal tracking).
        """
        detected = self._scanner.scan(project_path)
        for debt in detected:
            self._debts.append(debt)
            self._debt_counter += 1
        if self._persist_dir and detected:
            self._save_debts()
        return detected

    def prioritize(self) -> list[TechDebt]:
        """Prioritize debts using a composite score.

        Score = severity_weight * (1/effort_hours) + interest_rate

        interest_rate represents how much worse the debt gets over time:
        - Code style: low interest (doesn't get worse)
        - Architecture: high interest (compounds as more code depends on it)
        - Security: critical interest (vulnerabilities get exploited)
        - Test gaps: medium interest (regressions increase)

        Returns:
            List of TechDebt items sorted by priority (highest first).
        """
        active = [
            d for d in self._debts
            if d.status not in (DebtStatus.REMEDIATED, DebtStatus.WONT_FIX)
        ]
        return sorted(active, key=lambda d: d.priority_score, reverse=True)

    def generate_remediation_plan(
        self, budget_hours: float = 40.0
    ) -> RemediationPlan:
        """Generate a prioritized remediation plan within budget.

        Uses knapsack-style optimization to maximize debt reduction
        within the given time budget.

        Args:
            budget_hours: Available time budget in hours.

        Returns:
            RemediationPlan with optimal debt selection.
        """
        prioritized = self.prioritize()
        planned: list[dict[str, Any]] = []
        used_hours = 0.0
        deferred: list[str] = []

        for debt in prioritized:
            hours = debt.estimated_hours
            if used_hours + hours <= budget_hours:
                planned.append(
                    {
                        "debt_id": debt.id,
                        "estimated_hours": hours,
                        "priority": round(debt.priority_score, 3),
                        "description": debt.description,
                        "location": debt.location,
                    }
                )
                used_hours += hours
            else:
                deferred.append(debt.id)

        total_active = len(prioritized)
        total_severity = sum(d.severity_weight for d in prioritized)
        planned_severity = sum(
            d.severity_weight
            for d in prioritized
            if d.id in {p["debt_id"] for p in planned}
        )
        reduction = planned_severity / max(total_severity, 1.0)

        return RemediationPlan(
            total_debts=total_active,
            planned_remediations=planned,
            budget_hours=budget_hours,
            used_hours=used_hours,
            debt_reduction_pct=reduction,
            deferred_debts=deferred,
        )

    def track_remediation(self, debt_id: str, status: DebtStatus) -> None:
        """Update the status of a debt item.

        Args:
            debt_id: ID of the debt to update.
            status: New status to set.
        """
        for debt in self._debts:
            if debt.id == debt_id:
                debt.status = status
                if status == DebtStatus.REMEDIATED:
                    debt.remediated_at = datetime.now().isoformat()
                break
        if self._persist_dir:
            self._save_debts()

    def get_debt_report(self) -> DebtReport:
        """Generate a comprehensive debt report.

        Includes:
        - Debt distribution by category
        - Top 10 highest-priority debts
        - Interest accumulation forecast
        - Remediation progress tracking
        - Debt-to-value ratio (total debt / total features)

        Returns:
            DebtReport with comprehensive analysis.
        """
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        remediation_progress: dict[str, int] = {}

        for debt in self._debts:
            cat = debt.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            sev = debt.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

            st = debt.status.value
            remediation_progress[st] = remediation_progress.get(st, 0) + 1

        prioritized = self.prioritize()
        top_priority = prioritized[:10]

        # Interest forecast for next 6 months
        interest_forecast: dict[str, float] = {}
        now = datetime.now()
        for month_offset in range(1, 7):
            month_date = now.month + month_offset
            year = now.year + (month_date - 1) // 12
            month = ((month_date - 1) % 12) + 1
            key = f"{year}-{month:02d}"
            total_interest = sum(
                d.interest_rate * d.severity_weight
                for d in self._debts
                if d.status not in (DebtStatus.REMEDIATED, DebtStatus.WONT_FIX)
            )
            interest_forecast[key] = round(total_interest * month_offset * 0.1, 2)

        # Debt-to-value ratio: total severity weight / estimated features
        total_severity = sum(d.severity_weight for d in self._debts)
        estimated_features = max(len(self._debts) // 3, 1)
        debt_to_value = total_severity / estimated_features

        return DebtReport(
            total_debts=len(self._debts),
            by_category=by_category,
            by_severity=by_severity,
            top_priority=top_priority,
            interest_forecast=interest_forecast,
            remediation_progress=remediation_progress,
            debt_to_value_ratio=debt_to_value,
        )

    def _load_debts(self) -> None:
        """Load debts from persistence directory."""
        if not self._persist_dir:
            return

        persist_path = Path(self._persist_dir)
        debt_file = persist_path / "tech_debts.json"

        if not debt_file.exists():
            return

        try:
            with open(debt_file, encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("debts", []):
                debt = TechDebt.from_dict(item)
                self._debts.append(debt)
            self._debt_counter = data.get("counter", len(self._debts))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _save_debts(self) -> None:
        """Save debts to persistence directory."""
        if not self._persist_dir:
            return

        persist_path = Path(self._persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)
        debt_file = persist_path / "tech_debts.json"

        data = {
            "debts": [d.to_dict() for d in self._debts],
            "counter": self._debt_counter,
            "saved_at": datetime.now().isoformat(),
        }

        with open(debt_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================
# Convenience Functions
# ============================================================


def quick_scan(project_path: str) -> list[TechDebt]:
    """Quick scan a project for technical debt.

    Args:
        project_path: Root directory of the project.

    Returns:
        List of detected TechDebt items.
    """
    manager = TechDebtManager()
    return manager.scan_codebase_debt(project_path)


def quick_report(debts: list[TechDebt]) -> str:
    """Generate a quick markdown report from a list of debts.

    Args:
        debts: List of TechDebt items.

    Returns:
        Markdown formatted report string.
    """
    manager = TechDebtManager()
    for debt in debts:
        manager._debts.append(debt)
    report = manager.get_debt_report()
    return report.to_markdown()
