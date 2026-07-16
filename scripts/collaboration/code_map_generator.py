#!/usr/bin/env python3
import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


@dataclass
class CodeNode:
    name: str
    node_type: str
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    docstring: str = ""
    children: list["CodeNode"] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the code node to a dictionary.

        Returns:
            Dictionary with name, type, file, lines, docstring (truncated),
            children, imports, and calls (each truncated to 5 entries).
        """
        return {
            "name": self.name,
            "type": self.node_type,
            "file": self.file_path,
            "lines": f"{self.line_start}-{self.line_end}",
            "docstring": self.docstring[:100] if self.docstring else "",
            "children": [c.to_dict() for c in self.children],
            "imports": self.imports[:5],
            "calls": self.calls[:5],
        }


class CodeMapGenerator:
    """
    Code map generator for multi-language projects.

    Scans source files and generates a structured map of:
    - Modules, classes, functions
    - Import dependencies
    - Call relationships
    - Documentation strings

    Supports Python (AST), JavaScript/TypeScript (regex), Go (regex).
    """

    MAX_FILE_SIZE = 1 * 1024 * 1024

    def __init__(self, project_root: str = ".", parsers: list[Any] | None = None):
        self.project_root = Path(project_root)
        self._parsers: list[Any] | None = parsers
        self._default_parser = _PythonCompatParser()

    def register_parser(self, parser: Any) -> None:
        """Register an additional language parser with this generator.

        Args:
            parser: Parser instance exposing file_patterns, parse_file, and
                extract_dependencies methods.
        """
        if self._parsers is None:
            self._parsers = []
        self._parsers.append(parser)

    def generate_map(
        self,
        target_dir: str | None = None,
        output_format: str = "dict",
        languages: list[str] | None = None,
    ) -> Any:
        """
        Generate a code map for the target directory.

        Args:
            target_dir: Directory to scan (relative to project_root)
            output_format: "dict", "markdown", or "json"
            languages: Optional filter by language (e.g., ["python", "javascript"])

        Returns:
            Code map in the specified format
        """
        scan_dir = self.project_root / (target_dir or "")
        if not scan_dir.exists():
            logger.warning("Target directory does not exist: %s", scan_dir)
            return self._empty_map(output_format)

        if self._parsers:
            modules = self._collect_modules_with_parsers(scan_dir, languages)
        else:
            modules = self._collect_modules_default(scan_dir)

        return self._format_map(modules, output_format)

    @staticmethod
    def _empty_map(output_format: str) -> Any:
        """Return the format-appropriate empty code map."""
        return "" if output_format == "markdown" else {}

    def _collect_modules_with_parsers(
        self, scan_dir: Path, languages: list[str] | None
    ) -> dict[str, Any]:
        """Scan ``scan_dir`` using registered parsers, optionally filtered by language."""
        modules: dict[str, Any] = {}
        for parser in self._parsers or []:
            lang = self._detect_language(parser)
            if languages and lang not in languages:
                continue
            for pattern in parser.file_patterns():
                for file_path in sorted(scan_dir.rglob(pattern)):
                    if any(p in str(file_path) for p in parser.exclude_patterns()):
                        continue
                    if file_path.stat().st_size > self.MAX_FILE_SIZE:
                        continue
                    try:
                        source = file_path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    rel_path = str(file_path.relative_to(self.project_root))
                    file_map = parser.parse_file(source, str(file_path))
                    if file_map:
                        modules[rel_path] = file_map
        return modules

    def _collect_modules_default(self, scan_dir: Path) -> dict[str, Any]:
        """Scan ``scan_dir`` for Python files using the built-in default parser."""
        modules: dict[str, Any] = {}
        for py_file in sorted(scan_dir.rglob("*.py")):
            if any(p in str(py_file) for p in ["__pycache__", "test_", "_test.py", ".venv"]):
                continue
            rel_path = str(py_file.relative_to(self.project_root))
            module_map = self._default_parser.scan_file(py_file)
            if module_map:
                modules[rel_path] = module_map
        return modules

    def _format_map(self, modules: dict[str, Any], output_format: str) -> Any:
        """Render the collected modules in the requested output format."""
        if output_format == "markdown":
            return self._to_markdown(modules)
        if output_format == "json":
            return json.dumps(modules, indent=2, ensure_ascii=False)
        return modules

    def _detect_language(self, parser: Any) -> str:
        patterns = parser.file_patterns()
        if not patterns:
            return "unknown"
        ext = patterns[0].lstrip("*")
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
            ".go": "go",
        }
        return cast(str, lang_map.get(ext, ext.lstrip(".")))

    def _to_markdown(self, modules: dict[str, Any]) -> str:
        lines = ["# Code Map", ""]
        for file_path, info in modules.items():
            lang = info.get("language", "python")
            lines.append(f"## {file_path} `{lang}`")
            lines.append(f"- Classes: {info.get('total_classes', 0)} | Functions: {info.get('total_functions', 0)}")
            if info.get("imports"):
                lines.append(f"- Imports: {', '.join(info['imports'][:10])}")
            for node in info.get("nodes", []):
                ntype = node.get("type", "function")
                icon = {"class": "📦", "struct": "🏗️", "interface": "🔌"}.get(ntype, "⚡")
                lines.append(f"  - {icon} **{node['name']}** ({ntype})")
                if node.get("docstring"):
                    lines.append(f"    > {node['docstring']}")
                for child in node.get("children", []):
                    lines.append(f"    - ⚡ `{child['name']}`")
            lines.append("")
        return "\n".join(lines)

    def get_dependency_graph(self, target_dir: str | None = None) -> dict[str, list[str]]:
        """Build a file-level dependency graph for the target directory.

        Args:
            target_dir: Directory to scan (relative to project_root).
                When None the project root is used.

        Returns:
            Dictionary mapping relative file paths to sorted lists of
            imported module names.
        """
        scan_dir = self.project_root / (target_dir or "")
        graph = {}

        if self._parsers:
            for parser in self._parsers:
                for pattern in parser.file_patterns():
                    for file_path in sorted(scan_dir.rglob(pattern)):
                        if any(p in str(file_path) for p in parser.exclude_patterns()):
                            continue
                        try:
                            source = file_path.read_text(encoding="utf-8")
                        except UnicodeDecodeError:
                            continue
                        rel_path = str(file_path.relative_to(self.project_root))
                        deps = parser.extract_dependencies(source)
                        if deps:
                            graph[rel_path] = deps
        else:
            for py_file in sorted(scan_dir.rglob("*.py")):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source)
                except (SyntaxError, UnicodeDecodeError):
                    continue
                rel_path = str(py_file.relative_to(self.project_root))
                deps = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        deps.add(node.module)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            deps.add(alias.name)
                graph[rel_path] = sorted(deps)
        return graph


class _PythonCompatParser:
    """Internal Python parser maintaining backward compatibility with original CodeMapGenerator."""

    def scan_file(self, file_path: Path) -> dict[str, Any] | None:
        """Parse a Python source file and return its code map structure.

        Args:
            file_path: Path object pointing to the Python file to scan.

        Returns:
            Dictionary with file name, truncated imports, top-level nodes,
            and class/function counts, or None when the file cannot be parsed
            or exceeds the maximum file size.
        """
        try:
            if file_path.stat().st_size > CodeMapGenerator.MAX_FILE_SIZE:
                return None
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return None

        file_imports = []
        top_level = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                file_imports.append(module)

            if isinstance(node, ast.ClassDef):
                top_level.append(self._parse_class(node, str(file_path)))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top_level.append(self._parse_function(node, str(file_path)))

        return {
            "file": str(file_path.name),
            "imports": file_imports[:20],
            "nodes": [n.to_dict() for n in top_level],
            "total_classes": sum(1 for n in top_level if n.node_type == "class"),
            "total_functions": sum(1 for n in top_level if n.node_type == "function"),
        }

    def _parse_class(self, node: ast.ClassDef, file_path: str) -> CodeNode:
        docstring = ast.get_docstring(node) or ""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item, file_path))
        return CodeNode(
            name=node.name,
            node_type="class",
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            children=methods,
        )

    def _parse_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: str) -> CodeNode:
        docstring = ast.get_docstring(node) or ""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return CodeNode(
            name=node.name,
            node_type="function",
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            docstring=docstring,
            calls=list(set(calls))[:10],
        )
