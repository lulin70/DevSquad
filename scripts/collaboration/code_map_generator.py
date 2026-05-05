#!/usr/bin/env python3
import os
import json
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CodeNode:
    name: str
    node_type: str
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    docstring: str = ""
    children: List['CodeNode'] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name, 'type': self.node_type, 'file': self.file_path,
            'lines': f"{self.line_start}-{self.line_end}",
            'docstring': self.docstring[:100] if self.docstring else "",
            'children': [c.to_dict() for c in self.children],
            'imports': self.imports[:5], 'calls': self.calls[:5],
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

    def __init__(self, project_root: str = ".", parsers: Optional[List[Any]] = None):
        self.project_root = Path(project_root)
        self._parsers: List[Any] = parsers
        self._default_parser = _PythonCompatParser()

    def register_parser(self, parser: Any) -> None:
        if self._parsers is None:
            self._parsers = []
        self._parsers.append(parser)

    def generate_map(
        self,
        target_dir: str = None,
        output_format: str = "dict",
        languages: Optional[List[str]] = None,
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
            return {} if output_format != "markdown" else ""

        modules = {}

        if self._parsers:
            for parser in self._parsers:
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
                            source = file_path.read_text(encoding='utf-8')
                        except UnicodeDecodeError:
                            continue
                        rel_path = str(file_path.relative_to(self.project_root))
                        file_map = parser.parse_file(source, str(file_path))
                        if file_map:
                            modules[rel_path] = file_map
        else:
            for py_file in sorted(scan_dir.rglob("*.py")):
                if any(p in str(py_file) for p in ["__pycache__", "test_", "_test.py", ".venv"]):
                    continue
                rel_path = py_file.relative_to(self.project_root)
                module_map = self._default_parser.scan_file(py_file)
                if module_map:
                    modules[str(rel_path)] = module_map

        if output_format == "markdown":
            return self._to_markdown(modules)
        elif output_format == "json":
            return json.dumps(modules, indent=2, ensure_ascii=False)
        return modules

    def _detect_language(self, parser: Any) -> str:
        patterns = parser.file_patterns()
        if not patterns:
            return "unknown"
        ext = patterns[0].lstrip("*")
        lang_map = {".py": "python", ".js": "javascript", ".jsx": "javascript",
                    ".ts": "javascript", ".tsx": "javascript", ".go": "go"}
        return lang_map.get(ext, ext.lstrip("."))

    def _to_markdown(self, modules: Dict[str, Any]) -> str:
        lines = ["# Code Map", ""]
        for file_path, info in modules.items():
            lang = info.get("language", "python")
            lines.append(f"## {file_path} `{lang}`")
            lines.append(f"- Classes: {info.get('total_classes', 0)} | Functions: {info.get('total_functions', 0)}")
            if info.get('imports'):
                lines.append(f"- Imports: {', '.join(info['imports'][:10])}")
            for node in info.get('nodes', []):
                ntype = node.get('type', 'function')
                icon = {"class": "📦", "struct": "🏗️", "interface": "🔌"}.get(ntype, "⚡")
                lines.append(f"  - {icon} **{node['name']}** ({ntype})")
                if node.get('docstring'):
                    lines.append(f"    > {node['docstring']}")
                for child in node.get('children', []):
                    lines.append(f"    - ⚡ `{child['name']}`")
            lines.append("")
        return "\n".join(lines)

    def get_dependency_graph(self, target_dir: str = None) -> Dict[str, List[str]]:
        scan_dir = self.project_root / (target_dir or "")
        graph = {}

        if self._parsers:
            for parser in self._parsers:
                for pattern in parser.file_patterns():
                    for file_path in sorted(scan_dir.rglob(pattern)):
                        if any(p in str(file_path) for p in parser.exclude_patterns()):
                            continue
                        try:
                            source = file_path.read_text(encoding='utf-8')
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
                    source = py_file.read_text(encoding='utf-8')
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

    def scan_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            if file_path.stat().st_size > CodeMapGenerator.MAX_FILE_SIZE:
                return None
            source = file_path.read_text(encoding='utf-8')
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
            'file': str(file_path.name),
            'imports': file_imports[:20],
            'nodes': [n.to_dict() for n in top_level],
            'total_classes': sum(1 for n in top_level if n.node_type == 'class'),
            'total_functions': sum(1 for n in top_level if n.node_type == 'function'),
        }

    def _parse_class(self, node: ast.ClassDef, file_path: str) -> CodeNode:
        docstring = ast.get_docstring(node) or ""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item, file_path))
        return CodeNode(
            name=node.name, node_type="class", file_path=file_path,
            line_start=node.lineno, line_end=node.end_lineno or node.lineno,
            docstring=docstring, children=methods,
        )

    def _parse_function(self, node, file_path: str) -> CodeNode:
        docstring = ast.get_docstring(node) or ""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return CodeNode(
            name=node.name, node_type="function", file_path=file_path,
            line_start=node.lineno, line_end=node.end_lineno or node.lineno,
            docstring=docstring, calls=list(set(calls))[:10],
        )
