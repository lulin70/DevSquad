#!/usr/bin/env python3
import ast
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LanguageParser:
    """Base class for language-specific code parsers."""

    def file_patterns(self) -> list[str]:
        """Return the list of glob patterns this parser handles.

        Raises:
            NotImplementedError: Subclasses must override.
        """
        raise NotImplementedError

    def exclude_patterns(self) -> list[str]:
        """Return glob patterns for paths that should be skipped.

        Returns:
            List of exclude patterns; empty by default.
        """
        return []

    def parse_file(self, source: str, file_path: str) -> dict[str, Any] | None:
        """Parse a single source file into a structured description.

        Args:
            source: File contents as text.
            file_path: Path to the file (used for metadata and logging).

        Returns:
            Dictionary describing the file's nodes, or None when parsing fails.

        Raises:
            NotImplementedError: Subclasses must override.
        """
        raise NotImplementedError

    def extract_dependencies(self, source: str) -> list[str]:
        """Extract imported dependency module names from source text.

        Args:
            source: File contents as text.

        Returns:
            Sorted list of dependency module names.

        Raises:
            NotImplementedError: Subclasses must override.
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check whether this parser is available for use.

        Returns:
            True by default; overridden by NullLanguageParser to return False.
        """
        return True


class PythonParser(LanguageParser):
    """Python AST-based language parser."""

    def file_patterns(self) -> list[str]:
        """Return glob patterns handled by this parser.

        Returns:
            List containing "*.py".
        """
        return ["*.py"]

    def exclude_patterns(self) -> list[str]:
        """Return glob patterns for paths that should be skipped.

        Returns:
            List of Python-specific exclude patterns (cache dirs, tests, venv).
        """
        return ["__pycache__", "test_", "_test.py", ".venv"]

    def parse_file(self, source: str, file_path: str) -> dict[str, Any] | None:
        """Parse Python source into a structured description using the AST.

        Args:
            source: Python source code text.
            file_path: Path to the file (used for metadata and logging).

        Returns:
            Dictionary with file name, language, imports, top-level nodes,
            and class/function counts; None on SyntaxError or decode errors.
        """
        try:
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.debug("Python parse failed for %s: %s", file_path, e)
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

    def _parse_class(self, node, file_path: str) -> dict[str, Any]:
        docstring = ast.get_docstring(node) or ""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item, file_path))
        return {
            "name": node.name,
            "type": "class",
            "file": file_path,
            "lines": f"{node.lineno}-{node.end_lineno or node.lineno}",
            "docstring": docstring[:100],
            "children": methods,
        }

    def _parse_function(self, node, file_path: str) -> dict[str, Any]:
        docstring = ast.get_docstring(node) or ""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return {
            "name": node.name,
            "type": "function",
            "file": file_path,
            "lines": f"{node.lineno}-{node.end_lineno or node.lineno}",
            "docstring": docstring[:100],
            "calls": list(set(calls))[:10],
        }

    def extract_dependencies(self, source: str) -> list[str]:
        """Extract imported module names from Python source via the AST.

        Args:
            source: Python source code text.

        Returns:
            Sorted list of imported module names; empty list on parse errors.
        """
        try:
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.debug("Python dependency extraction failed: %s", e)
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

    _CLASS_RE = re.compile(r"(?:export\s+)?(?:default\s+)?class\s+(\w+)", re.MULTILINE)
    _FUNC_RE = re.compile(
        r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>",
        re.MULTILINE,
    )
    _IMPORT_RE = re.compile(
        r"""import\s+.*?\s+from\s+['"]([^'"]+)['"]|"""
        r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
        re.MULTILINE,
    )

    def file_patterns(self) -> list[str]:
        """Return glob patterns handled by this parser.

        Returns:
            List of JS/TS file extensions (.js, .jsx, .ts, .tsx).
        """
        return ["*.js", "*.jsx", "*.ts", "*.tsx"]

    def exclude_patterns(self) -> list[str]:
        """Return glob patterns for paths that should be skipped.

        Returns:
            List of JS build/dependency directories to exclude.
        """
        return ["node_modules", "dist", ".next", "coverage", "build"]

    def parse_file(self, source: str, file_path: str) -> dict[str, Any] | None:
        """Parse JavaScript/TypeScript source via regex into a description.

        Args:
            source: JavaScript/TypeScript source code text.
            file_path: Path to the file (used for metadata and logging).

        Returns:
            Dictionary with file name, language, imports, classes and
            functions; None when no classes or functions are found.
        """
        try:
            classes = []
            for m in self._CLASS_RE.finditer(source):
                classes.append(
                    {
                        "name": m.group(1),
                        "type": "class",
                        "file": file_path,
                        "lines": "",
                        "docstring": "",
                        "children": [],
                    }
                )

            functions = []
            for m in self._FUNC_RE.finditer(source):
                name = m.group(1) or m.group(2)
                if name:
                    functions.append(
                        {
                            "name": name,
                            "type": "function",
                            "file": file_path,
                            "lines": "",
                            "docstring": "",
                            "calls": [],
                        }
                    )

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
        except Exception as e:
            logger.debug("JavaScript parse failed for %s: %s", file_path, e)
            return None

    def extract_dependencies(self, source: str) -> list[str]:
        """Extract imported module paths from JavaScript/TypeScript source.

        Args:
            source: JavaScript/TypeScript source code text.

        Returns:
            Sorted list of imported module paths.
        """
        deps = set()
        for m in self._IMPORT_RE.finditer(source):
            dep = m.group(1) or m.group(2)
            if dep:
                deps.add(dep)
        return sorted(deps)


class GoParser(LanguageParser):
    """Go regex-based parser."""

    _FUNC_RE = re.compile(r"func\s+(?:\([^)]+\)\s*)?(\w+)\s*\(", re.MULTILINE)
    _TYPE_STRUCT_RE = re.compile(r"type\s+(\w+)\s+struct\s*\{", re.MULTILINE)
    _TYPE_INTERFACE_RE = re.compile(r"type\s+(\w+)\s+interface\s*\{", re.MULTILINE)
    _IMPORT_RE = re.compile(r'import\s+(?:\(\s*([^)]+)\s*\)|"([^"]+)")', re.MULTILINE | re.DOTALL)
    _IMPORT_LINE_RE = re.compile(r'"([^"]+)"')

    def file_patterns(self) -> list[str]:
        """Return glob patterns handled by this parser.

        Returns:
            List containing "*.go".
        """
        return ["*.go"]

    def exclude_patterns(self) -> list[str]:
        """Return glob patterns for paths that should be skipped.

        Returns:
            List containing "vendor".
        """
        return ["vendor"]

    def parse_file(self, source: str, file_path: str) -> dict[str, Any] | None:
        """Parse Go source via regex into a structured description.

        Args:
            source: Go source code text.
            file_path: Path to the file (used for metadata and logging).

        Returns:
            Dictionary with file name, language, imports, structs, interfaces
            and functions; None when none of those are found.
        """
        try:
            structs = []
            for m in self._TYPE_STRUCT_RE.finditer(source):
                structs.append(
                    {
                        "name": m.group(1),
                        "type": "struct",
                        "file": file_path,
                        "lines": "",
                        "docstring": "",
                        "children": [],
                    }
                )

            interfaces = []
            for m in self._TYPE_INTERFACE_RE.finditer(source):
                interfaces.append(
                    {
                        "name": m.group(1),
                        "type": "interface",
                        "file": file_path,
                        "lines": "",
                        "docstring": "",
                        "children": [],
                    }
                )

            functions = []
            for m in self._FUNC_RE.finditer(source):
                functions.append(
                    {
                        "name": m.group(1),
                        "type": "function",
                        "file": file_path,
                        "lines": "",
                        "docstring": "",
                        "calls": [],
                    }
                )

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
        except Exception as e:
            logger.debug("Go parse failed for %s: %s", file_path, e)
            return None

    def extract_dependencies(self, source: str) -> list[str]:
        """Extract imported package paths from Go source.

        Args:
            source: Go source code text.

        Returns:
            Sorted list of imported package paths.
        """
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

    def file_patterns(self) -> list[str]:
        """Return glob patterns handled by this parser.

        Returns:
            Empty list (the null parser handles no files).
        """
        return []

    def parse_file(self, _source: str, _file_path: str) -> dict[str, Any] | None:
        """Always return None; the null parser parses nothing.

        Args:
            _source: Unused source text.
            _file_path: Unused file path.

        Returns:
            Always None.
        """
        return None

    def extract_dependencies(self, _source: str) -> list[str]:
        """Always return an empty list; the null parser extracts nothing.

        Args:
            _source: Unused source text.

        Returns:
            Always an empty list.
        """
        return []

    def is_available(self) -> bool:
        """Return False; the null parser is never available.

        Returns:
            Always False.
        """
        return False


DEFAULT_PARSERS = [PythonParser(), JavaScriptParser(), GoParser()]
