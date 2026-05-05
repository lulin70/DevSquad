#!/usr/bin/env python3
import re
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LanguageParser:
    """Base class for language-specific code parsers."""

    def file_patterns(self) -> List[str]:
        raise NotImplementedError

    def exclude_patterns(self) -> List[str]:
        return []

    def parse_file(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def extract_dependencies(self, source: str) -> List[str]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class PythonParser(LanguageParser):
    """Python AST-based language parser."""

    def file_patterns(self) -> List[str]:
        return ["*.py"]

    def exclude_patterns(self) -> List[str]:
        return ["__pycache__", "test_", "_test.py", ".venv"]

    def parse_file(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        import ast
        try:
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return None

        file_imports = []
        top_level_nodes = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                file_imports.append(module)

            if isinstance(node, ast.ClassDef):
                top_level_nodes.append(self._parse_class(node, file_path))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top_level_nodes.append(self._parse_function(node, file_path))

        return {
            "file": Path(file_path).name,
            "language": "python",
            "imports": file_imports[:20],
            "nodes": top_level_nodes,
            "total_classes": sum(1 for n in top_level_nodes if n["type"] == "class"),
            "total_functions": sum(1 for n in top_level_nodes if n["type"] in ("function", "method")),
        }

    def _parse_class(self, node, file_path: str) -> Dict[str, Any]:
        import ast
        docstring = ast.get_docstring(node) or ""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item, file_path))
        return {
            "name": node.name, "type": "class", "file": file_path,
            "lines": f"{node.lineno}-{node.end_lineno or node.lineno}",
            "docstring": docstring[:100], "children": methods,
        }

    def _parse_function(self, node, file_path: str) -> Dict[str, Any]:
        import ast
        docstring = ast.get_docstring(node) or ""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return {
            "name": node.name, "type": "function", "file": file_path,
            "lines": f"{node.lineno}-{node.end_lineno or node.lineno}",
            "docstring": docstring[:100], "calls": list(set(calls))[:10],
        }

    def extract_dependencies(self, source: str) -> List[str]:
        import ast
        try:
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return []
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                deps.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    deps.add(alias.name)
        return sorted(deps)


class JavaScriptParser(LanguageParser):
    """JavaScript/TypeScript regex-based parser."""

    _CLASS_RE = re.compile(
        r'(?:export\s+)?(?:default\s+)?class\s+(\w+)', re.MULTILINE
    )
    _FUNC_RE = re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)|'
        r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>',
        re.MULTILINE,
    )
    _IMPORT_RE = re.compile(
        r"""import\s+.*?\s+from\s+['"]([^'"]+)['"]|"""
        r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
        re.MULTILINE,
    )

    def file_patterns(self) -> List[str]:
        return ["*.js", "*.jsx", "*.ts", "*.tsx"]

    def exclude_patterns(self) -> List[str]:
        return ["node_modules", "dist", ".next", "coverage", "build"]

    def parse_file(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            classes = []
            for m in self._CLASS_RE.finditer(source):
                classes.append({
                    "name": m.group(1), "type": "class", "file": file_path,
                    "lines": "", "docstring": "", "children": [],
                })

            functions = []
            for m in self._FUNC_RE.finditer(source):
                name = m.group(1) or m.group(2)
                if name:
                    functions.append({
                        "name": name, "type": "function", "file": file_path,
                        "lines": "", "docstring": "", "calls": [],
                    })

            if not classes and not functions:
                return None

            return {
                "file": Path(file_path).name,
                "language": "javascript",
                "imports": self.extract_dependencies(source)[:20],
                "nodes": classes + functions,
                "total_classes": len(classes),
                "total_functions": len(functions),
            }
        except Exception:
            return None

    def extract_dependencies(self, source: str) -> List[str]:
        deps = set()
        for m in self._IMPORT_RE.finditer(source):
            dep = m.group(1) or m.group(2)
            if dep:
                deps.add(dep)
        return sorted(deps)


class GoParser(LanguageParser):
    """Go regex-based parser."""

    _FUNC_RE = re.compile(
        r'func\s+(?:\([^)]+\)\s*)?(\w+)\s*\(', re.MULTILINE
    )
    _TYPE_STRUCT_RE = re.compile(
        r'type\s+(\w+)\s+struct\s*\{', re.MULTILINE
    )
    _TYPE_INTERFACE_RE = re.compile(
        r'type\s+(\w+)\s+interface\s*\{', re.MULTILINE
    )
    _IMPORT_RE = re.compile(
        r'import\s+(?:\(\s*([^)]+)\s*\)|"([^"]+)")', re.MULTILINE | re.DOTALL
    )
    _IMPORT_LINE_RE = re.compile(r'"([^"]+)"')

    def file_patterns(self) -> List[str]:
        return ["*.go"]

    def exclude_patterns(self) -> List[str]:
        return ["vendor"]

    def parse_file(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        try:
            structs = []
            for m in self._TYPE_STRUCT_RE.finditer(source):
                structs.append({
                    "name": m.group(1), "type": "struct", "file": file_path,
                    "lines": "", "docstring": "", "children": [],
                })

            interfaces = []
            for m in self._TYPE_INTERFACE_RE.finditer(source):
                interfaces.append({
                    "name": m.group(1), "type": "interface", "file": file_path,
                    "lines": "", "docstring": "", "children": [],
                })

            functions = []
            for m in self._FUNC_RE.finditer(source):
                functions.append({
                    "name": m.group(1), "type": "function", "file": file_path,
                    "lines": "", "docstring": "", "calls": [],
                })

            if not structs and not interfaces and not functions:
                return None

            return {
                "file": Path(file_path).name,
                "language": "go",
                "imports": self.extract_dependencies(source)[:20],
                "nodes": structs + interfaces + functions,
                "total_classes": len(structs) + len(interfaces),
                "total_functions": len(functions),
            }
        except Exception:
            return None

    def extract_dependencies(self, source: str) -> List[str]:
        deps = set()
        for m in self._IMPORT_RE.finditer(source):
            block = m.group(1)
            single = m.group(2)
            if block:
                for lm in self._IMPORT_LINE_RE.finditer(block):
                    deps.add(lm.group(1))
            elif single:
                deps.add(single)
        return sorted(deps)


class NullLanguageParser(LanguageParser):
    """Null parser for graceful degradation."""

    def file_patterns(self) -> List[str]:
        return []

    def parse_file(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        return None

    def extract_dependencies(self, source: str) -> List[str]:
        return []

    def is_available(self) -> bool:
        return False


DEFAULT_PARSERS = [PythonParser(), JavaScriptParser(), GoParser()]
