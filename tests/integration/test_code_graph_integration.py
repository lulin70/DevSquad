#!/usr/bin/env python3
"""CodeKnowledgeGraph + CodeGraphQuery + CodeGraphStorage Integration Tests
(V4.2.1 P2-2 — Test Pyramid Lift).

End-to-end integration tests for the code-knowledge-graph trio. Verifies
CROSS-MODULE interactions among:

    scripts/collaboration/code_graph_storage.py    — CodeGraphStorage (SQLite
        backend storing symbols, call edges, dependency edges, file metadata)
    scripts/collaboration/code_knowledge_graph.py   — CodeKnowledgeGraph
        (AST-based incremental indexer; parses Python → storage)
    scripts/collaboration/code_graph_query.py       — CodeGraphQuery
        (read-only queries: find_symbol/callers/callees/similar/call_graph)

Flow:
    1. CodeKnowledgeGraph.build_from_project(root) → indexes symbols/edges
    2. CodeKnowledgeGraph.query() → CodeGraphQuery
    3. CodeGraphQuery.find_symbol/callers/callees/similar → dataclasses

Test categories:
    T1: CodeGraphStorage basic CRUD (symbol/edge/file upsert + query + delete)
    T2: CodeKnowledgeGraph incremental update (Python AST → storage)
    T3: CodeGraphQuery query chain (find_symbol/callers/callees/similar/graph)
    T4: End-to-end: parse real Python → index → query → verify
    T5: Boundary & exceptions (empty file, syntax error, dup upsert, threads)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.code_graph_query import CodeGraphQuery
from scripts.collaboration.code_graph_storage import (
    CallEdge,
    CodeGraphStorage,
    DependencyEdge,
    SymbolInfo,
)
from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_symbol(
    name: str = "foo",
    symbol_type: str = "function",
    file_path: str = "src/main.py",
    line_start: int = 1,
    line_end: int = 5,
    docstring: str = "",
    signature: str = "foo()",
) -> SymbolInfo:
    """Create a SymbolInfo with sensible defaults."""
    return SymbolInfo(
        name=name,
        symbol_type=symbol_type,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        docstring=docstring,
        signature=signature,
    )


def _make_call_edge(
    caller: str = "foo",
    callee: str = "bar",
    file_path: str = "src/main.py",
    line: int = 2,
) -> CallEdge:
    """Create a CallEdge with sensible defaults."""
    return CallEdge(caller=caller, callee=callee, file_path=file_path, line=line)


def _make_dependency(
    source_module: str = "src/main.py",
    target_module: str = "os",
    import_type: str = "import",
) -> DependencyEdge:
    """Create a DependencyEdge with sensible defaults."""
    return DependencyEdge(
        source_module=source_module,
        target_module=target_module,
        import_type=import_type,
    )


def _write_sample_project(root: Path) -> dict[str, Path]:
    """Write a small Python project tree under root for indexing.

    Returns a dict mapping logical name → file path.
    """
    root.mkdir(parents=True, exist_ok=True)
    main_py = root / "main.py"
    main_py.write_text(
        '"""Main module."""\n'
        "import os\n"
        "from helper import baz\n"
        "\n"
        "def alpha(a, b):\n"
        '    """Alpha function."""\n'
        "    beta()\n"
        "    return a + b\n"
        "\n"
        "def beta(x):\n"
        "    return x * 2\n"
        "\n"
        "class Widget:\n"
        '    """A widget."""\n'
        "    def render(self, ctx):\n"
        "        alpha(ctx, 1)\n"
        "        return ctx\n",
        encoding="utf-8",
    )
    helper_py = root / "helper.py"
    helper_py.write_text(
        '"""Helper module."""\n'
        "import sys\n"
        "\n"
        "def baz(y):\n"
        '    """Baz function."""\n'
        "    return y + 1\n"
        "\n"
        "def qux(z):\n"
        "    baz(z)\n"
        "    return z\n",
        encoding="utf-8",
    )
    return {"main": main_py, "helper": helper_py}


# ---------------------------------------------------------------------------
# T1: CodeGraphStorage basic CRUD
# ---------------------------------------------------------------------------


class T1_CodeGraphStorageCRUDIntegration(unittest.TestCase):
    """T1: CodeGraphStorage symbol/edge/file upsert + query + delete."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cgraph_t1_")
        self._db = Path(self._tmp) / "graph.db"
        self._store = CodeGraphStorage(self._db)

    def tearDown(self) -> None:
        self._store.close()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_upsert_symbol_then_query_by_name(self) -> None:
        """Verify: upsert_symbol stores a symbol retrievable by exact name."""
        sym = _make_symbol(name="compute", file_path="src/a.py", line_start=10)
        self.assertTrue(self._store.upsert_symbol(sym))
        results = self._store.query_symbol("compute")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_path, "src/a.py")
        self.assertEqual(results[0].line_start, 10)

    def test_02_upsert_symbols_batch_inserts_all(self) -> None:
        """Verify: upsert_symbols batch-inserts a list and returns its length."""
        syms = [
            _make_symbol(name="f1", file_path="a.py", line_start=1),
            _make_symbol(name="f2", file_path="a.py", line_start=5),
            _make_symbol(name="f3", file_path="b.py", line_start=1),
        ]
        self.assertEqual(self._store.upsert_symbols(syms), 3)
        self.assertEqual(self._store.get_stats()["symbols"], 3)

    def test_03_delete_symbols_for_file_removes_only_that_file(self) -> None:
        """Verify: delete_symbols_for_file removes symbols for one file only."""
        self._store.upsert_symbols([
            _make_symbol(name="f1", file_path="a.py", line_start=1),
            _make_symbol(name="f2", file_path="b.py", line_start=1),
        ])
        self.assertEqual(self._store.delete_symbols_for_file("a.py"), 1)
        self.assertEqual(self._store.get_stats()["symbols"], 1)

    def test_04_upsert_call_edge_and_query_callers_callees(self) -> None:
        """Verify: a call edge lets query_callers and query_callees resolve."""
        self._store.upsert_symbols([
            _make_symbol(name="caller_fn", file_path="m.py", line_start=1),
            _make_symbol(name="callee_fn", file_path="m.py", line_start=5),
        ])
        self.assertTrue(self._store.upsert_call_edge(
            _make_call_edge(caller="caller_fn", callee="callee_fn", file_path="m.py", line=2)
        ))
        self.assertEqual([s.name for s in self._store.query_callers("callee_fn")], ["caller_fn"])
        self.assertEqual([s.name for s in self._store.query_callees("caller_fn")], ["callee_fn"])

    def test_05_upsert_call_edges_batch(self) -> None:
        """Verify: upsert_call_edges batch-inserts edges and returns count."""
        self._store.upsert_symbols([
            _make_symbol(name="a", file_path="m.py", line_start=1),
            _make_symbol(name="b", file_path="m.py", line_start=2),
            _make_symbol(name="c", file_path="m.py", line_start=3),
        ])
        edges = [
            _make_call_edge(caller="a", callee="b", file_path="m.py", line=1),
            _make_call_edge(caller="a", callee="c", file_path="m.py", line=2),
        ]
        self.assertEqual(self._store.upsert_call_edges(edges), 2)
        self.assertEqual(self._store.get_stats()["call_edges"], 2)

    def test_06_upsert_dependency_and_query(self) -> None:
        """Verify: upsert_dependency stores an import edge queryable by source."""
        self.assertTrue(self._store.upsert_dependency(
            _make_dependency(source_module="src/main.py", target_module="os")
        ))
        deps = self._store.query_dependencies("src/main.py")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target_module, "os")

    def test_07_upsert_file_and_get_file_hash(self) -> None:
        """Verify: upsert_file stores metadata and get_file_hash returns it."""
        self.assertTrue(self._store.upsert_file("src/main.py", "abc123", 42))
        self.assertEqual(self._store.get_file_hash("src/main.py"), "abc123")
        self.assertIsNone(self._store.get_file_hash("untracked.py"))

    def test_08_query_symbols_by_type(self) -> None:
        """Verify: query_symbols_by_type filters by function/class/method."""
        self._store.upsert_symbols([
            _make_symbol(name="fn", symbol_type="function", file_path="m.py", line_start=1),
            _make_symbol(name="Cls", symbol_type="class", file_path="m.py", line_start=5),
            _make_symbol(name="m", symbol_type="method", file_path="m.py", line_start=7),
        ])
        self.assertEqual(len(self._store.query_symbols_by_type("function")), 1)
        self.assertEqual(len(self._store.query_symbols_by_type("class")), 1)
        self.assertEqual(len(self._store.query_symbols_by_type("method")), 1)

    def test_09_get_stats_reports_all_counts(self) -> None:
        """Verify: get_stats returns symbols/call_edges/dependencies/files keys."""
        stats = self._store.get_stats()
        self.assertEqual(stats["symbols"], 0)
        self.assertEqual(stats["call_edges"], 0)
        self.assertEqual(stats["dependencies"], 0)
        self.assertEqual(stats["files"], 0)
        self._store.upsert_symbol(_make_symbol(name="x"))
        self._store.upsert_call_edge(_make_call_edge())
        self._store.upsert_dependency(_make_dependency())
        self._store.upsert_file("f.py", "h", 1)
        stats = self._store.get_stats()
        self.assertEqual(stats["symbols"], 1)
        self.assertEqual(stats["call_edges"], 1)
        self.assertEqual(stats["dependencies"], 1)
        self.assertEqual(stats["files"], 1)


# ---------------------------------------------------------------------------
# T2: CodeKnowledgeGraph incremental update (Python AST → storage)
# ---------------------------------------------------------------------------


class T2_CodeKnowledgeGraphIncrementalUpdate(unittest.TestCase):
    """T2: CodeKnowledgeGraph build_from_project / update_file / update_project."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cgraph_t2_")
        self._db = Path(self._tmp) / "kg.db"
        self._proj = Path(self._tmp) / "proj"
        _write_sample_project(self._proj)
        self._graph = CodeKnowledgeGraph(self._db)

    def tearDown(self) -> None:
        self._graph.close()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_build_from_project_returns_symbol_count(self) -> None:
        """Verify: build_from_project indexes symbols and returns a positive count."""
        count = self._graph.build_from_project(self._proj)
        self.assertGreater(count, 0)
        self.assertEqual(self._graph.get_stats()["symbols"], count)

    def test_02_build_indexes_files_with_hash(self) -> None:
        """Verify: after build, both files are tracked with a non-empty hash."""
        self._graph.build_from_project(self._proj)
        main_hash = self._graph._storage.get_file_hash(str(self._proj / "main.py"))
        helper_hash = self._graph._storage.get_file_hash(str(self._proj / "helper.py"))
        self.assertIsNotNone(main_hash)
        self.assertIsNotNone(helper_hash)
        self.assertNotEqual(main_hash, "")

    def test_03_update_file_unchanged_returns_false(self) -> None:
        """Verify: re-running update_file on an unchanged file is a no-op."""
        self._graph.build_from_project(self._proj)
        self.assertFalse(self._graph.update_file(self._proj / "main.py"))

    def test_04_update_file_changed_returns_true_and_reindexes(self) -> None:
        """Verify: modifying a file triggers re-indexing."""
        self._graph.build_from_project(self._proj)
        main_py = self._proj / "main.py"
        main_py.write_text(
            '"""Changed main."""\n'
            "def new_func(n):\n"
            "    return n\n",
            encoding="utf-8",
        )
        self.assertTrue(self._graph.update_file(main_py))
        self.assertGreaterEqual(len(self._graph.query().find_symbol("new_func")), 1)

    def test_05_update_file_nonexistent_returns_false(self) -> None:
        """Verify: update_file on a missing path returns False without crashing."""
        self.assertFalse(self._graph.update_file(self._proj / "does_not_exist.py"))

    def test_06_update_project_only_reindexes_changed_files(self) -> None:
        """Verify: update_project after a single change reports exactly one update."""
        self._graph.build_from_project(self._proj)
        (self._proj / "helper.py").write_text(
            '"""Changed helper."""\n'
            "def brand_new():\n"
            "    return 0\n",
            encoding="utf-8",
        )
        self.assertEqual(self._graph.update_project(self._proj), 1)

    def test_07_build_extracts_call_edges(self) -> None:
        """Verify: build stores call edges extracted from the AST."""
        self._graph.build_from_project(self._proj)
        self.assertGreater(self._graph.get_stats()["call_edges"], 0)


# ---------------------------------------------------------------------------
# T3: CodeGraphQuery query chain
# ---------------------------------------------------------------------------


class T3_CodeGraphQueryChain(unittest.TestCase):
    """T3: CodeGraphQuery find_symbol/callers/callees/dependencies/similar/graph."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cgraph_t3_")
        self._db = Path(self._tmp) / "q.db"
        self._store = CodeGraphStorage(self._db)
        self._store.upsert_symbols([
            _make_symbol(name="entry", file_path="m.py", line_start=1, signature="entry(a, b)"),
            _make_symbol(name="worker", file_path="m.py", line_start=5, signature="worker(a, b)"),
            _make_symbol(name="util", file_path="m.py", line_start=10, signature="util(c)"),
        ])
        self._store.upsert_call_edges([
            _make_call_edge(caller="entry", callee="worker", file_path="m.py", line=2),
            _make_call_edge(caller="entry", callee="util", file_path="m.py", line=3),
            _make_call_edge(caller="worker", callee="util", file_path="m.py", line=6),
        ])
        self._store.upsert_dependency(
            _make_dependency(source_module="m.py", target_module="os")
        )
        self._query = CodeGraphQuery(self._store)

    def tearDown(self) -> None:
        self._store.close()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_find_symbol_exact_name(self) -> None:
        """Verify: find_symbol returns the matching symbol."""
        results = self._query.find_symbol("entry")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "entry")

    def test_02_find_symbol_unknown_returns_empty(self) -> None:
        """Verify: find_symbol for a missing name returns an empty list."""
        self.assertEqual(self._query.find_symbol("nope"), [])

    def test_03_find_callers_resolves_caller_symbols(self) -> None:
        """Verify: find_callers returns symbols that call the given function."""
        callers = self._query.find_callers("util")
        self.assertEqual(sorted(s.name for s in callers), ["entry", "worker"])

    def test_04_find_callees_resolves_callee_symbols(self) -> None:
        """Verify: find_callees returns symbols called by the given function."""
        callees = self._query.find_callees("entry")
        self.assertEqual(sorted(s.name for s in callees), ["util", "worker"])

    def test_05_find_dependencies_returns_edges(self) -> None:
        """Verify: find_dependencies returns dependency edges for a module."""
        deps = self._query.find_dependencies("m.py")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target_module, "os")

    def test_06_get_call_graph_bfs_traversal(self) -> None:
        """Verify: get_call_graph BFS from entry includes reachable nodes/edges."""
        graph = self._query.get_call_graph("entry", max_depth=3)
        self.assertEqual(graph["entry_point"], "entry")
        node_names = {n["name"] for n in graph["nodes"]}
        self.assertIn("entry", node_names)
        self.assertIn("worker", node_names)
        self.assertIn("util", node_names)
        self.assertGreater(len(graph["edges"]), 0)

    def test_07_get_call_graph_respects_max_depth(self) -> None:
        """Verify: max_depth=0 yields only the entry node with no edges."""
        graph = self._query.get_call_graph("entry", max_depth=0)
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["nodes"][0]["name"], "entry")
        self.assertEqual(graph["nodes"][0]["depth"], 0)
        self.assertEqual(len(graph["edges"]), 0)

    def test_08_find_similar_by_signature_overlap(self) -> None:
        """Verify: find_similar returns symbols with >=50% param overlap."""
        # entry(a, b) and worker(a, b) share params {a, b} → Jaccard 1.0.
        results = self._query.find_similar("target(a, b)")
        names = {s.name for s in results}
        self.assertIn("entry", names)
        self.assertIn("worker", names)
        # util(c) has no overlap with (a, b) → excluded.
        self.assertNotIn("util", names)

    def test_09_find_similar_empty_signature_returns_empty(self) -> None:
        """Verify: find_similar with no params returns an empty list."""
        self.assertEqual(self._query.find_similar("nothing()"), [])

    def test_10_query_get_stats_matches_storage(self) -> None:
        """Verify: CodeGraphQuery.get_stats delegates to storage counts."""
        stats = self._query.get_stats()
        self.assertEqual(stats["symbols"], 3)
        self.assertEqual(stats["call_edges"], 3)
        self.assertEqual(stats["dependencies"], 1)


# ---------------------------------------------------------------------------
# T4: End-to-end — parse real Python → index → query → verify
# ---------------------------------------------------------------------------


class T4_EndToEndParseIndexQuery(unittest.TestCase):
    """T4: Real Python source → build → query → verify results."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cgraph_t4_")
        self._db = Path(self._tmp) / "e2e.db"
        self._proj = Path(self._tmp) / "proj"
        _write_sample_project(self._proj)
        self._graph = CodeKnowledgeGraph(self._db)
        self._graph.build_from_project(self._proj)

    def tearDown(self) -> None:
        self._graph.close()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_parsed_function_symbols_findable(self) -> None:
        """Verify: functions defined in source are findable after build."""
        q = self._graph.query()
        for name in ("alpha", "beta", "baz", "qux"):
            self.assertGreaterEqual(
                len(q.find_symbol(name)), 1,
                f"symbol {name!r} should be indexed after build",
            )

    def test_02_parsed_class_and_method_findable(self) -> None:
        """Verify: class and its method are indexed as separate symbols."""
        q = self._graph.query()
        self.assertGreaterEqual(len(q.find_symbol("Widget")), 1)
        self.assertGreaterEqual(len(q.find_symbol("render")), 1)

    def test_03_callers_resolved_across_ast_calls(self) -> None:
        """Verify: callers of beta (alpha calls beta) resolve end-to-end."""
        q = self._graph.query()
        callers = {s.name for s in q.find_callers("beta")}
        self.assertIn("alpha", callers)

    def test_04_callees_resolved_for_alpha(self) -> None:
        """Verify: callees of alpha include beta (alpha calls beta)."""
        q = self._graph.query()
        callees = {s.name for s in q.find_callees("alpha")}
        self.assertIn("beta", callees)

    def test_05_call_graph_from_alpha_reaches_beta(self) -> None:
        """Verify: call graph from alpha reaches beta via BFS."""
        q = self._graph.query()
        graph = q.get_call_graph("alpha", max_depth=2)
        node_names = {n["name"] for n in graph["nodes"]}
        self.assertIn("alpha", node_names)
        self.assertIn("beta", node_names)

    def test_06_dependencies_indexed_for_modules(self) -> None:
        """Verify: import dependencies are indexed per source file."""
        q = self._graph.query()
        deps = q.find_dependencies(str(self._proj / "main.py"))
        targets = {d.target_module for d in deps}
        self.assertIn("os", targets)


# ---------------------------------------------------------------------------
# T5: Boundary & exceptions
# ---------------------------------------------------------------------------


class T5_BoundaryAndExceptions(unittest.TestCase):
    """T5: Empty file, syntax error, duplicate upsert, thread-safety."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="cgraph_t5_")
        self._db = Path(self._tmp) / "edge.db"

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_01_empty_python_file_indexed_without_error(self) -> None:
        """Verify: an empty .py file is handled gracefully (zero symbols)."""
        proj = Path(self._tmp) / "empty_proj"
        proj.mkdir()
        (proj / "empty.py").write_text("", encoding="utf-8")
        graph = CodeKnowledgeGraph(self._db)
        try:
            count = graph.build_from_project(proj)
            self.assertEqual(count, 0)
            self.assertEqual(graph.get_stats()["files"], 1)
        finally:
            graph.close()

    def test_02_syntax_error_file_skipped_gracefully(self) -> None:
        """Verify: a file with a SyntaxError produces no symbols but doesn't crash."""
        proj = Path(self._tmp) / "bad_proj"
        proj.mkdir()
        (proj / "broken.py").write_text("def broken(\n", encoding="utf-8")
        graph = CodeKnowledgeGraph(self._db)
        try:
            count = graph.build_from_project(proj)
            self.assertEqual(count, 0)
        finally:
            graph.close()

    def test_03_duplicate_upsert_is_idempotent(self) -> None:
        """Verify: upserting the same symbol twice does not duplicate rows."""
        store = CodeGraphStorage(self._db)
        try:
            sym = _make_symbol(name="dup", file_path="m.py", line_start=1)
            store.upsert_symbol(sym)
            store.upsert_symbol(sym)
            self.assertEqual(store.get_stats()["symbols"], 1)
            self.assertEqual(len(store.query_symbol("dup")), 1)
        finally:
            store.close()

    def test_04_duplicate_call_edge_is_idempotent(self) -> None:
        """Verify: upserting the same call edge twice does not duplicate rows."""
        store = CodeGraphStorage(self._db)
        try:
            store.upsert_symbols([
                _make_symbol(name="a", file_path="m.py", line_start=1),
                _make_symbol(name="b", file_path="m.py", line_start=2),
            ])
            edge = _make_call_edge(caller="a", callee="b", file_path="m.py", line=1)
            store.upsert_call_edge(edge)
            store.upsert_call_edge(edge)
            self.assertEqual(store.get_stats()["call_edges"], 1)
        finally:
            store.close()

    def test_05_concurrent_upsert_symbols_thread_safe(self) -> None:
        """Verify: concurrent symbol upserts from many threads do not corrupt."""
        store = CodeGraphStorage(self._db)
        errors: list[Exception] = []
        barrier = threading.Barrier(20)
        try:
            def worker(idx: int) -> None:
                try:
                    barrier.wait()
                    store.upsert_symbol(_make_symbol(
                        name=f"fn_{idx}", file_path=f"f_{idx}.py", line_start=1
                    ))
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(store.get_stats()["symbols"], 20)
        finally:
            store.close()

    def test_06_get_file_hash_untracked_returns_none(self) -> None:
        """Verify: get_file_hash for an untracked path returns None."""
        store = CodeGraphStorage(self._db)
        try:
            self.assertIsNone(store.get_file_hash("never_seen.py"))
        finally:
            store.close()

    def test_07_in_memory_db_round_trip(self) -> None:
        """Verify: CodeGraphStorage works with an in-memory SQLite database."""
        store = CodeGraphStorage(Path(":memory:"))
        try:
            store.upsert_symbol(_make_symbol(name="mem", file_path="m.py", line_start=1))
            self.assertEqual(len(store.query_symbol("mem")), 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
