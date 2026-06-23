#!/usr/bin/env python3
"""CodeKnowledgeGraph — Persistent code structure knowledge graph.

Inspired by colbymchenry/codegraph. Pre-indexes code structure so Workers
can query the graph instead of scanning files with Read/Grep.

Usage:
    graph = CodeKnowledgeGraph(Path(".codegraph.db"))
    graph.build_from_project(Path("scripts/"))
    query = graph.query()
    callers = query.find_callers("dispatch")
"""

import ast
import hashlib
import logging
from pathlib import Path

from .code_graph_query import CodeGraphQuery
from .code_graph_storage import CallEdge, CodeGraphStorage, DependencyEdge, SymbolInfo
from .code_map_generator import CodeMapGenerator

logger = logging.getLogger(__name__)


class CodeKnowledgeGraph:
    """Persistent code knowledge graph with incremental update support."""

    def __init__(self, db_path: Path):
        """Initialize the code knowledge graph.

        Args:
            db_path: Path to the SQLite database file for persistent storage.
        """
        self._storage = CodeGraphStorage(db_path)
        self._map_gen = CodeMapGenerator()

    def build_from_project(self, project_root: Path, file_pattern: str = "**/*.py") -> int:
        """Full build from project root. Returns number of symbols indexed.

        Scans all Python files matching file_pattern, parses each file using
        CodeMapGenerator's AST parser, and stores symbols, call edges, and
        dependency edges in the SQLite database.

        Args:
            project_root: Root directory of the project to index.
            file_pattern: Glob pattern for matching files (default: all Python files).

        Returns:
            Total number of symbols indexed across all files.
        """
        project_root = Path(project_root)
        symbol_count = 0

        for py_file in sorted(project_root.glob(file_pattern)):
            if "__pycache__" in str(py_file):
                continue
            if not py_file.is_file():
                continue
            symbols, call_edges, deps = self._parse_file(py_file)
            file_path_str = str(py_file)

            self._storage.delete_symbols_for_file(file_path_str)
            self._storage.delete_edges_for_file(file_path_str)

            self._storage.upsert_symbols(symbols)
            self._storage.upsert_call_edges(call_edges)
            for dep in deps:
                self._storage.upsert_dependency(dep)

            hash_val, line_count = self._compute_file_hash(py_file)
            self._storage.upsert_file(file_path_str, hash_val, line_count)

            symbol_count += len(symbols)

        logger.info("Built graph from %s: %d symbols indexed", project_root, symbol_count)
        return symbol_count

    def update_file(self, file_path: Path) -> bool:
        """Incremental update for a single file.

        1. Check file hash — skip if unchanged
        2. Delete old symbols/edges for this file
        3. Parse AST and store new symbols/edges

        Args:
            file_path: Path to the Python file to update.

        Returns:
            True if the graph was updated (file changed or new), False if unchanged.
        """
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            return False

        hash_val, line_count = self._compute_file_hash(file_path)
        file_path_str = str(file_path)

        stored_hash = self._storage.get_file_hash(file_path_str)
        if stored_hash == hash_val:
            return False

        self._storage.delete_symbols_for_file(file_path_str)
        self._storage.delete_edges_for_file(file_path_str)

        symbols, call_edges, deps = self._parse_file(file_path)

        self._storage.upsert_symbols(symbols)
        self._storage.upsert_call_edges(call_edges)
        for dep in deps:
            self._storage.upsert_dependency(dep)

        self._storage.upsert_file(file_path_str, hash_val, line_count)
        logger.info("Updated file %s: %d symbols", file_path_str, len(symbols))
        return True

    def update_project(self, project_root: Path) -> int:
        """Incremental update — only scan changed files. Returns number of files updated.

        Args:
            project_root: Root directory of the project to update.

        Returns:
            Number of files that were actually re-parsed (changed or new).
        """
        project_root = Path(project_root)
        updated = 0

        for py_file in sorted(project_root.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            if not py_file.is_file():
                continue
            if self.update_file(py_file):
                updated += 1

        logger.info("Incremental update from %s: %d files updated", project_root, updated)
        return updated

    def query(self) -> "CodeGraphQuery":
        """Get a query interface for the code knowledge graph.

        Returns:
            CodeGraphQuery instance bound to this graph's storage.
        """
        return CodeGraphQuery(self._storage)

    def get_stats(self) -> dict:
        """Get statistics about the indexed graph.

        Returns:
            Dictionary with counts: symbols, call_edges, dependencies, files.
        """
        return self._storage.get_stats()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._storage.close()

    def _parse_file(self, file_path: Path) -> tuple[list[SymbolInfo], list[CallEdge], list[DependencyEdge]]:
        """Parse a single Python file using CodeMapGenerator's parser.

        Args:
            file_path: Path to the Python file to parse.

        Returns:
            Tuple of (symbols, call_edges, dependencies) extracted from the file.
        """
        module_info = self._map_gen._default_parser.scan_file(file_path)
        if not module_info:
            return [], [], []

        file_path_str = str(file_path)
        symbols, call_edges = self._extract_from_module_info(module_info, file_path_str)

        signatures = self._extract_signatures(file_path)
        for sym in symbols:
            if sym.name in signatures:
                sym.signature = signatures[sym.name]

        deps: list[DependencyEdge] = []
        for imp in module_info.get("imports", []):
            deps.append(
                DependencyEdge(
                    source_module=file_path_str,
                    target_module=imp,
                    import_type="import",
                )
            )

        return symbols, call_edges, deps

    def _extract_from_module_info(
        self, module_info: dict, file_path: str
    ) -> tuple[list[SymbolInfo], list[CallEdge]]:
        """Extract symbols and call edges from CodeMapGenerator output.

        Args:
            module_info: Dictionary from CodeMapGenerator's scan_file().
            file_path: Absolute file path for the module.

        Returns:
            Tuple of (symbols, call_edges) extracted from the module info.
        """
        symbols: list[SymbolInfo] = []
        call_edges: list[CallEdge] = []

        for node_dict in module_info.get("nodes", []):
            line_start, line_end = self._parse_line_range(node_dict.get("lines", "0-0"))

            symbol_type = "class" if node_dict.get("type") == "class" else "function"
            symbols.append(
                SymbolInfo(
                    name=node_dict["name"],
                    symbol_type=symbol_type,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    docstring=node_dict.get("docstring", ""),
                    signature="",
                )
            )

            for call_name in node_dict.get("calls", []):
                call_edges.append(
                    CallEdge(
                        caller=node_dict["name"],
                        callee=call_name,
                        file_path=file_path,
                        line=line_start,
                    )
                )

            for child_dict in node_dict.get("children", []):
                child_start, child_end = self._parse_line_range(child_dict.get("lines", "0-0"))
                symbols.append(
                    SymbolInfo(
                        name=child_dict["name"],
                        symbol_type="method",
                        file_path=file_path,
                        line_start=child_start,
                        line_end=child_end,
                        docstring=child_dict.get("docstring", ""),
                        signature="",
                    )
                )
                for call_name in child_dict.get("calls", []):
                    call_edges.append(
                        CallEdge(
                            caller=child_dict["name"],
                            callee=call_name,
                            file_path=file_path,
                            line=child_start,
                        )
                    )

        return symbols, call_edges

    def _extract_signatures(self, file_path: Path) -> dict[str, str]:
        """Extract function signatures from a Python file via AST.

        Args:
            file_path: Path to the Python file.

        Returns:
            Dictionary mapping function name to signature string (e.g. "foo(a, b)").
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            return {}

        signatures: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signatures[node.name] = self._format_signature(node)
        return signatures

    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format a function signature from an AST node.

        Args:
            node: FunctionDef or AsyncFunctionDef AST node.

        Returns:
            Signature string like "func_name(arg1, arg2, *args, **kwargs)".
        """
        args = node.args
        parts: list[str] = []

        for arg in args.posonlyargs:
            parts.append(arg.arg)
        if args.posonlyargs:
            parts.append("/")

        for arg in args.args:
            parts.append(arg.arg)

        if args.vararg:
            parts.append(f"*{args.vararg.arg}")
        elif args.kwonlyargs:
            parts.append("*")

        for arg in args.kwonlyargs:
            parts.append(arg.arg)

        if args.kwarg:
            parts.append(f"**{args.kwarg.arg}")

        return f"{node.name}({', '.join(parts)})"

    def _parse_line_range(self, lines_str: str) -> tuple[int, int]:
        """Parse a line range string like '10-20' into (10, 20).

        Args:
            lines_str: Line range string from CodeMapGenerator output.

        Returns:
            Tuple of (line_start, line_end). Returns (0, 0) if parsing fails.
        """
        try:
            parts = lines_str.split("-")
            start = int(parts[0])
            end = int(parts[1]) if len(parts) > 1 else start
            return start, end
        except (ValueError, IndexError):
            return 0, 0

    def _compute_file_hash(self, file_path: Path) -> tuple[str, int]:
        """Compute SHA256 hash and line count of a file.

        Args:
            file_path: Path to the file to hash.

        Returns:
            Tuple of (hash_hex, line_count). Returns ("", 0) on error.
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            hash_val = hashlib.sha256(source.encode("utf-8")).hexdigest()
            line_count = source.count("\n") + 1 if source else 0
            return hash_val, line_count
        except (OSError, UnicodeDecodeError):
            return "", 0

