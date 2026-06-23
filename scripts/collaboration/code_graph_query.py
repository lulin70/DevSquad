#!/usr/bin/env python3
"""CodeGraphQuery — Query interface for the code knowledge graph.

Extracted from code_knowledge_graph.py to keep that module under 500 lines.
Provides read-only queries (symbols, callers, callees, dependencies, call
graph traversal, and similar-signature search) against a CodeGraphStorage
instance. All methods return dataclasses or plain dicts.

Usage:
    graph = CodeKnowledgeGraph(Path(".codegraph.db"))
    query = graph.query()  # returns a CodeGraphQuery
    callers = query.find_callers("dispatch")
"""

from .code_graph_storage import CodeGraphStorage, DependencyEdge, SymbolInfo


class CodeGraphQuery:
    """Query interface for code knowledge graph. Returns dataclasses."""

    def __init__(self, storage: CodeGraphStorage):
        """Initialize the query interface.

        Args:
            storage: CodeGraphStorage instance to query against.
        """
        self._storage = storage

    def find_symbol(self, name: str) -> list[SymbolInfo]:
        """Find symbols by exact name.

        Args:
            name: Symbol name to search for.

        Returns:
            List of matching SymbolInfo objects (may span multiple files).
        """
        return self._storage.query_symbol(name)

    def find_callers(self, function_name: str) -> list[SymbolInfo]:
        """Find symbols that call the given function.

        Args:
            function_name: Name of the callee function.

        Returns:
            List of SymbolInfo objects for caller symbols.
        """
        return self._storage.query_callers(function_name)

    def find_callees(self, function_name: str) -> list[SymbolInfo]:
        """Find symbols called by the given function.

        Args:
            function_name: Name of the caller function.

        Returns:
            List of SymbolInfo objects for callee symbols in the codebase.
        """
        return self._storage.query_callees(function_name)

    def find_dependencies(self, module_path: str) -> list[DependencyEdge]:
        """Find dependencies of a module.

        Args:
            module_path: Source module path to query dependencies for.

        Returns:
            List of DependencyEdge objects.
        """
        return self._storage.query_dependencies(module_path)

    def get_call_graph(self, entry_point: str, max_depth: int = 3) -> dict:
        """Get call graph starting from entry_point via BFS traversal.

        Traverses the call graph breadth-first up to max_depth levels,
        collecting all reachable nodes and edges.

        Args:
            entry_point: Name of the function to start traversal from.
            max_depth: Maximum traversal depth (default: 3).

        Returns:
            Dictionary with keys: entry_point, max_depth, nodes (list of
            {name, depth}), edges (list of {caller, callee}).
        """
        nodes: list[dict] = []
        edges: list[dict] = []
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(entry_point, 0)]

        while queue:
            name, depth = queue.pop(0)
            if name in visited:
                continue
            if depth > max_depth:
                continue
            visited.add(name)
            nodes.append({"name": name, "depth": depth})

            if depth < max_depth:
                callees = self._storage.query_callees(name)
                for callee in callees:
                    edges.append({"caller": name, "callee": callee.name})
                    if callee.name not in visited:
                        queue.append((callee.name, depth + 1))

        return {
            "entry_point": entry_point,
            "max_depth": max_depth,
            "nodes": nodes,
            "edges": edges,
        }

    def find_similar(self, signature: str) -> list[SymbolInfo]:
        """Find symbols with similar signatures.

        Compares parameter names using Jaccard similarity. Returns symbols
        whose parameter set overlaps by at least 50% with the input signature.

        Args:
            signature: Signature string like "func_name(a, b, c)".

        Returns:
            List of SymbolInfo objects with similar signatures.
        """
        target_params = self._extract_param_names(signature)
        if not target_params:
            return []

        results: list[SymbolInfo] = []
        for sym_type in ("function", "method"):
            for sym in self._storage.query_symbols_by_type(sym_type):
                if not sym.signature:
                    continue
                sym_params = self._extract_param_names(sym.signature)
                if not sym_params:
                    continue
                intersection = len(target_params & sym_params)
                union = len(target_params | sym_params)
                if union > 0 and intersection / union >= 0.5:
                    results.append(sym)
        return results

    def get_stats(self) -> dict:
        """Get statistics about the indexed graph.

        Returns:
            Dictionary with counts: symbols, call_edges, dependencies, files.
        """
        return self._storage.get_stats()

    def _extract_param_names(self, signature: str) -> set[str]:
        """Extract parameter names from a signature string.

        Args:
            signature: Signature string like "func(a, b, *args, **kwargs)".

        Returns:
            Set of parameter names (without * or ** prefixes).
        """
        if not signature or "(" not in signature:
            return set()
        try:
            start = signature.index("(")
            end = signature.rindex(")")
            params_str = signature[start + 1 : end]
            if not params_str.strip():
                return set()
            params: set[str] = set()
            for p in params_str.split(","):
                p = p.strip()
                if not p or p in ("/", "*"):
                    continue
                p = p.lstrip("*")
                if "=" in p:
                    p = p.split("=")[0].strip()
                if p:
                    params.add(p)
            return params
        except (ValueError, IndexError):
            return set()
