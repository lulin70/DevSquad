#!/usr/bin/env python3
"""Tests for V39-01 CodeKnowledgeGraph — Persistent Code Knowledge Graph.

Covers: Happy path, error case, boundary, performance, integration, incremental update.
Follows Testing Iron Rules: documentation-first, no loose assertions, dimension completeness.
"""

import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from scripts.collaboration.code_graph_storage import (
    CallEdge,
    CodeGraphStorage,
    DependencyEdge,
    SymbolInfo,
)
from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph


def _make_project(root: Path) -> Path:
    """Create a test project with functions, classes, and call relationships.

    Structure:
        main.py    — main() calls helper() and process(); process() calls helper()
        utils.py   — helper() and helper_two(x, y)
        models.py  — class User with __init__(self, name) and get_name(self)
    """
    root.mkdir(parents=True, exist_ok=True)

    (root / "main.py").write_text(
        '''"""Main module."""
from utils import helper


def main():
    """Main entry point."""
    helper()
    process()


def process():
    """Process data."""
    helper()
''',
        encoding="utf-8",
    )

    (root / "utils.py").write_text(
        '''"""Utils module."""


def helper():
    """Helper function."""
    return True


def helper_two(x, y):
    """Second helper with two params."""
    return x + y
''',
        encoding="utf-8",
    )

    (root / "models.py").write_text(
        '''"""Models module."""


class User:
    """User model."""

    def __init__(self, name):
        """Initialize user."""
        self.name = name

    def get_name(self):
        """Get user name."""
        return self.name
''',
        encoding="utf-8",
    )

    return root


def _make_deep_chain(root: Path) -> Path:
    """Create a project with deeply nested call chain: a->b->c->d."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "chain.py").write_text(
        '''"""Deep call chain module."""


def func_a():
    """Function A calls B."""
    func_b()


def func_b():
    """Function B calls C."""
    func_c()


def func_c():
    """Function C calls D."""
    func_d()


def func_d():
    """Function D is terminal."""
    pass
''',
        encoding="utf-8",
    )
    return root


class TestCodeGraphStorage(unittest.TestCase):
    """Tests for CodeGraphStorage — SQLite storage layer."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_storage.db"
        self.storage = CodeGraphStorage(self.db_path)

    def tearDown(self):
        self.storage.close()
        self.tmpdir.cleanup()

    # === Happy Path (≥50%) ===

    def test_upsert_symbol_and_query_happy(self):
        """Verify: upsert_symbol stores a symbol and query_symbol retrieves it.

        Scenario: A single SymbolInfo is upserted into storage.
        Expected: query_symbol returns a list containing the same symbol data.
        """
        # Arrange
        symbol = SymbolInfo(
            name="my_func",
            symbol_type="function",
            file_path="/tmp/test.py",
            line_start=10,
            line_end=20,
            docstring="A test function",
            signature="my_func(a, b)",
        )

        # Act
        inserted = self.storage.upsert_symbol(symbol)
        results = self.storage.query_symbol("my_func")

        # Assert
        self.assertTrue(inserted)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "my_func")
        self.assertEqual(results[0].symbol_type, "function")
        self.assertEqual(results[0].line_start, 10)
        self.assertEqual(results[0].line_end, 20)
        self.assertEqual(results[0].signature, "my_func(a, b)")

    def test_upsert_symbols_batch_happy(self):
        """Verify: upsert_symbols stores multiple symbols in one call.

        Scenario: A list of 3 SymbolInfo objects is batch-upserted.
        Expected: All 3 symbols are retrievable, return count is 3.
        """
        # Arrange
        symbols = [
            SymbolInfo("func_a", "function", "/tmp/a.py", 1, 5, "", "func_a()"),
            SymbolInfo("func_b", "function", "/tmp/b.py", 1, 5, "", "func_b()"),
            SymbolInfo("MyClass", "class", "/tmp/c.py", 1, 20, "A class", ""),
        ]

        # Act
        count = self.storage.upsert_symbols(symbols)

        # Assert
        self.assertEqual(count, 3)
        self.assertEqual(len(self.storage.query_symbol("func_a")), 1)
        self.assertEqual(len(self.storage.query_symbol("func_b")), 1)
        self.assertEqual(len(self.storage.query_symbol("MyClass")), 1)

    def test_upsert_call_edge_and_query_callers_happy(self):
        """Verify: upsert_call_edge stores edge and query_callers finds caller.

        Scenario: A call edge (caller=foo, callee=bar) is stored, plus both symbols.
        Expected: query_callers("bar") returns the foo symbol.
        """
        # Arrange
        self.storage.upsert_symbol(
            SymbolInfo("foo", "function", "/tmp/x.py", 1, 5, "", "foo()")
        )
        self.storage.upsert_symbol(
            SymbolInfo("bar", "function", "/tmp/y.py", 1, 5, "", "bar()")
        )
        edge = CallEdge(caller="foo", callee="bar", file_path="/tmp/x.py", line=3)

        # Act
        inserted = self.storage.upsert_call_edge(edge)
        callers = self.storage.query_callers("bar")

        # Assert
        self.assertTrue(inserted)
        self.assertEqual(len(callers), 1)
        self.assertEqual(callers[0].name, "foo")
        self.assertEqual(callers[0].file_path, "/tmp/x.py")

    def test_query_callees_happy(self):
        """Verify: query_callees returns symbols called by the given function.

        Scenario: foo calls bar and baz; all three symbols are stored.
        Expected: query_callees("foo") returns bar and baz.
        """
        # Arrange
        for name in ("foo", "bar", "baz"):
            self.storage.upsert_symbol(
                SymbolInfo(name, "function", f"/tmp/{name}.py", 1, 5, "", f"{name}()")
            )
        self.storage.upsert_call_edge(CallEdge("foo", "bar", "/tmp/foo.py", 2))
        self.storage.upsert_call_edge(CallEdge("foo", "baz", "/tmp/foo.py", 3))

        # Act
        callees = self.storage.query_callees("foo")

        # Assert
        callee_names = {s.name for s in callees}
        self.assertEqual(callee_names, {"bar", "baz"})

    def test_upsert_dependency_and_query_happy(self):
        """Verify: upsert_dependency stores dep and query_dependencies retrieves it.

        Scenario: A dependency edge (source=/tmp/a.py, target=os) is stored.
        Expected: query_dependencies("/tmp/a.py") returns the dependency.
        """
        # Arrange
        dep = DependencyEdge(
            source_module="/tmp/a.py", target_module="os", import_type="import"
        )

        # Act
        inserted = self.storage.upsert_dependency(dep)
        deps = self.storage.query_dependencies("/tmp/a.py")

        # Assert
        self.assertTrue(inserted)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target_module, "os")
        self.assertEqual(deps[0].import_type, "import")

    def test_upsert_file_and_get_hash_happy(self):
        """Verify: upsert_file stores hash and get_file_hash retrieves it.

        Scenario: A file record with path, hash, and line_count is stored.
        Expected: get_file_hash returns the same hash string.
        """
        # Arrange
        path = "/tmp/test.py"
        hash_val = "abc123def456"
        line_count = 42

        # Act
        inserted = self.storage.upsert_file(path, hash_val, line_count)
        retrieved = self.storage.get_file_hash(path)

        # Assert
        self.assertTrue(inserted)
        self.assertEqual(retrieved, hash_val)

    def test_get_file_hash_returns_none_for_untracked(self):
        """Verify: get_file_hash returns None for an untracked file.

        Scenario: No file record exists for the given path.
        Expected: get_file_hash returns None.
        """
        # Act
        result = self.storage.get_file_hash("/nonexistent/file.py")

        # Assert
        self.assertIsNone(result)

    def test_delete_symbols_for_file_happy(self):
        """Verify: delete_symbols_for_file removes all symbols for a file.

        Scenario: 2 symbols exist for /tmp/a.py, 1 for /tmp/b.py.
        Expected: delete_symbols_for_file("/tmp/a.py") returns 2, only b.py symbol remains.
        """
        # Arrange
        self.storage.upsert_symbols([
            SymbolInfo("f1", "function", "/tmp/a.py", 1, 5, "", ""),
            SymbolInfo("f2", "function", "/tmp/a.py", 6, 10, "", ""),
            SymbolInfo("f3", "function", "/tmp/b.py", 1, 5, "", ""),
        ])

        # Act
        deleted = self.storage.delete_symbols_for_file("/tmp/a.py")

        # Assert
        self.assertEqual(deleted, 2)
        self.assertEqual(len(self.storage.query_symbol("f1")), 0)
        self.assertEqual(len(self.storage.query_symbol("f2")), 0)
        self.assertEqual(len(self.storage.query_symbol("f3")), 1)

    def test_delete_edges_for_file_happy(self):
        """Verify: delete_edges_for_file removes all edges for a file.

        Scenario: 2 call edges exist for /tmp/a.py, 1 for /tmp/b.py.
        Expected: delete_edges_for_file("/tmp/a.py") returns 2.
        """
        # Arrange
        self.storage.upsert_call_edges([
            CallEdge("f1", "f2", "/tmp/a.py", 1),
            CallEdge("f1", "f3", "/tmp/a.py", 2),
            CallEdge("f4", "f5", "/tmp/b.py", 1),
        ])

        # Act
        deleted = self.storage.delete_edges_for_file("/tmp/a.py")

        # Assert
        self.assertEqual(deleted, 2)

    def test_get_stats_returns_correct_counts(self):
        """Verify: get_stats returns accurate counts for symbols, edges, deps, files.

        Scenario: 2 symbols, 1 call edge, 1 dependency, 1 file are stored.
        Expected: get_stats returns dict with matching counts.
        """
        # Arrange
        self.storage.upsert_symbols([
            SymbolInfo("f1", "function", "/tmp/a.py", 1, 5, "", ""),
            SymbolInfo("f2", "function", "/tmp/b.py", 1, 5, "", ""),
        ])
        self.storage.upsert_call_edge(CallEdge("f1", "f2", "/tmp/a.py", 2))
        self.storage.upsert_dependency(
            DependencyEdge("/tmp/a.py", "os", "import")
        )
        self.storage.upsert_file("/tmp/a.py", "hash123", 10)

        # Act
        stats = self.storage.get_stats()

        # Assert
        self.assertEqual(stats["symbols"], 2)
        self.assertEqual(stats["call_edges"], 1)
        self.assertEqual(stats["dependencies"], 1)
        self.assertEqual(stats["files"], 1)

    def test_query_symbols_by_type_happy(self):
        """Verify: query_symbols_by_type filters by symbol type.

        Scenario: 2 functions and 1 class are stored.
        Expected: query_symbols_by_type("function") returns 2, "class" returns 1.
        """
        # Arrange
        self.storage.upsert_symbols([
            SymbolInfo("f1", "function", "/tmp/a.py", 1, 5, "", ""),
            SymbolInfo("f2", "function", "/tmp/b.py", 1, 5, "", ""),
            SymbolInfo("Cls", "class", "/tmp/c.py", 1, 20, "", ""),
        ])

        # Act
        funcs = self.storage.query_symbols_by_type("function")
        classes = self.storage.query_symbols_by_type("class")

        # Assert
        self.assertEqual(len(funcs), 2)
        self.assertEqual(len(classes), 1)

    # === Error Case (≥15%) ===

    def test_invalid_db_path_raises_error(self):
        """Verify: Invalid db path (parent is a file) raises OSError.

        Scenario: The parent of the db path is a regular file, not a directory.
        Expected: CodeGraphStorage raises OSError on initialization.
        """
        # Arrange
        blocker = Path(self.tmpdir.name) / "blocker"
        blocker.write_text("I am a file")
        db_path = blocker / "subdir" / "db.sqlite"

        # Act / Assert
        with self.assertRaises(OSError):
            CodeGraphStorage(db_path)

    def test_corrupted_database_raises_error(self):
        """Verify: Corrupted database file raises sqlite3.DatabaseError.

        Scenario: A file exists at the db path but is not a valid SQLite database.
        Expected: CodeGraphStorage raises sqlite3.DatabaseError on table creation.
        """
        # Arrange
        db_path = Path(self.tmpdir.name) / "corrupted.db"
        db_path.write_text("not a sqlite database file content")

        # Act / Assert
        with self.assertRaises(sqlite3.DatabaseError):
            CodeGraphStorage(db_path)

    def test_empty_project_returns_zero_symbols(self):
        """Verify: Building from an empty project directory returns 0 symbols.

        Scenario: project_root points to an empty directory.
        Expected: build_from_project returns 0.
        """
        # Arrange
        empty_dir = Path(self.tmpdir.name) / "empty_project"
        empty_dir.mkdir()
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "empty.db")

        # Act
        count = graph.build_from_project(empty_dir)

        # Assert
        self.assertEqual(count, 0)
        graph.close()

    def test_update_nonexistent_file_returns_false(self):
        """Verify: update_file returns False for a file that does not exist.

        Scenario: file_path points to a nonexistent file.
        Expected: update_file returns False without raising an error.
        """
        # Arrange
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "test.db")

        # Act
        result = graph.update_file(Path("/nonexistent/file.py"))

        # Assert
        self.assertFalse(result)
        graph.close()

    def test_syntax_error_file_skipped_during_build(self):
        """Verify: Files with syntax errors are skipped during build without crashing.

        Scenario: A project contains a Python file with invalid syntax.
        Expected: build_from_project completes and returns symbols from valid files only.
        """
        # Arrange
        project = Path(self.tmpdir.name) / "syntax_project"
        project.mkdir()
        (project / "good.py").write_text(
            'def valid_func():\n    """Valid."""\n    return True\n', encoding="utf-8"
        )
        (project / "bad.py").write_text(
            "def broken(:\n    pass\n", encoding="utf-8"
        )
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "syntax.db")

        # Act
        count = graph.build_from_project(project)

        # Assert
        self.assertEqual(count, 1)  # Only valid_func from good.py
        self.assertEqual(len(graph.query().find_symbol("valid_func")), 1)
        self.assertEqual(len(graph.query().find_symbol("broken")), 0)
        graph.close()

    # === Boundary (≥10%) ===

    def test_empty_file_produces_no_symbols(self):
        """Verify: An empty Python file produces zero symbols.

        Scenario: A .py file with only a docstring and no functions/classes.
        Expected: build_from_project returns 0 symbols for this file.
        """
        # Arrange
        project = Path(self.tmpdir.name) / "empty_file_project"
        project.mkdir()
        (project / "empty.py").write_text(
            '"""Empty module."""\n', encoding="utf-8"
        )
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "empty_file.db")

        # Act
        count = graph.build_from_project(project)

        # Assert
        self.assertEqual(count, 0)
        graph.close()

    def test_single_function_file_indexed_correctly(self):
        """Verify: A file with a single function is indexed correctly.

        Scenario: A .py file contains exactly one function definition.
        Expected: build_from_project returns 1, and the function is queryable.
        """
        # Arrange
        project = Path(self.tmpdir.name) / "single_func_project"
        project.mkdir()
        (project / "single.py").write_text(
            'def only_func():\n    """The only function."""\n    return 42\n',
            encoding="utf-8",
        )
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "single.db")

        # Act
        count = graph.build_from_project(project)
        symbols = graph.query().find_symbol("only_func")

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0].name, "only_func")
        self.assertEqual(symbols[0].symbol_type, "function")
        graph.close()

    def test_deeply_nested_calls_respect_max_depth(self):
        """Verify: get_call_graph respects max_depth for deeply nested calls.

        Scenario: Call chain a->b->c->d, max_depth=2.
        Expected: Graph contains nodes a(0), b(1), c(2) but NOT d(3).
        """
        # Arrange
        project = Path(self.tmpdir.name) / "deep_project"
        _make_deep_chain(project)
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "deep.db")
        graph.build_from_project(project)

        # Act
        result = graph.query().get_call_graph("func_a", max_depth=2)

        # Assert
        node_names = {n["name"] for n in result["nodes"]}
        self.assertIn("func_a", node_names)
        self.assertIn("func_b", node_names)
        self.assertIn("func_c", node_names)
        self.assertNotIn("func_d", node_names)
        graph.close()

    # === Performance (≥5%) ===

    def test_query_performance_under_50ms(self):
        """Verify: Symbol query completes in under 50ms.

        Scenario: A project with multiple files is indexed, then queried.
        Expected: find_symbol completes in <50ms.
        """
        # Arrange
        project = Path(self.tmpdir.name) / "perf_project"
        _make_project(project)
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "perf.db")
        graph.build_from_project(project)
        query = graph.query()

        # Act
        start = time.perf_counter()
        for _ in range(10):
            query.find_symbol("helper")
            query.find_callers("helper")
            query.find_callees("main")
        elapsed = (time.perf_counter() - start) * 1000  # ms

        # Assert
        self.assertLess(elapsed, 50.0, f"Query took {elapsed:.2f}ms, expected <50ms")
        graph.close()

    def test_incremental_update_performance_under_500ms(self):
        """Verify: Incremental update of unchanged project completes in under 500ms.

        Scenario: A project is built, then update_project is called (all files unchanged).
        Expected: update_project completes in <500ms and returns 0 (no files changed).
        """
        # Arrange
        project = Path(self.tmpdir.name) / "incr_perf_project"
        _make_project(project)
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "incr_perf.db")
        graph.build_from_project(project)

        # Act
        start = time.perf_counter()
        updated = graph.update_project(project)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        # Assert
        self.assertEqual(updated, 0)
        self.assertLess(elapsed, 500.0, f"Update took {elapsed:.2f}ms, expected <500ms")
        graph.close()

    # === Integration (≥10%) ===

    def test_storage_persistence_across_instances(self):
        """Verify: Data persists across CodeGraphStorage instances.

        Scenario: Symbols are stored, storage is closed, a new instance opens the same db.
        Expected: The new instance can query the previously stored symbols.
        """
        # Arrange
        db_path = Path(self.tmpdir.name) / "persistence.db"
        storage1 = CodeGraphStorage(db_path)
        storage1.upsert_symbol(
            SymbolInfo("persistent_func", "function", "/tmp/p.py", 1, 5, "", "persistent_func()")
        )
        storage1.close()

        # Act
        storage2 = CodeGraphStorage(db_path)
        results = storage2.query_symbol("persistent_func")

        # Assert
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "persistent_func")
        storage2.close()

    def test_code_map_generator_compatibility(self):
        """Verify: CodeKnowledgeGraph correctly uses CodeMapGenerator output.

        Scenario: A project is built using CodeKnowledgeGraph which internally
        uses CodeMapGenerator for AST parsing.
        Expected: All functions and classes from the project are indexed.
        """
        # Arrange
        project = Path(self.tmpdir.name) / "compat_project"
        _make_project(project)
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "compat.db")

        # Act
        count = graph.build_from_project(project)
        query = graph.query()

        # Assert
        self.assertGreaterEqual(count, 5)  # main, process, helper, helper_two, User
        self.assertEqual(len(query.find_symbol("main")), 1)
        self.assertEqual(len(query.find_symbol("helper")), 1)
        self.assertEqual(len(query.find_symbol("helper_two")), 1)
        self.assertEqual(len(query.find_symbol("User")), 1)
        # Methods
        init_symbols = query.find_symbol("__init__")
        self.assertEqual(len(init_symbols), 1)
        self.assertEqual(init_symbols[0].symbol_type, "method")
        graph.close()

    def test_index_devsquad_collaboration_module(self):
        """Verify: Can index the actual DevSquad collaboration module.

        Scenario: Build graph from scripts/collaboration/ directory.
        Expected: Known symbols like CodeMapGenerator, Coordinator are found.
        """
        # Arrange
        devsquad_root = Path(__file__).parent.parent / "scripts" / "collaboration"
        if not devsquad_root.exists():
            self.skipTest("DevSquad collaboration module not found")
        graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "devsquad.db")

        # Act
        count = graph.build_from_project(devsquad_root)
        query = graph.query()

        # Assert
        self.assertGreater(count, 10)  # Should find many symbols
        self.assertGreaterEqual(len(query.find_symbol("CodeMapGenerator")), 1)
        self.assertGreaterEqual(len(query.find_symbol("Coordinator")), 1)
        graph.close()


class TestCodeKnowledgeGraphBuild(unittest.TestCase):
    """Tests for CodeKnowledgeGraph build and query operations."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project = _make_project(Path(self.tmpdir.name) / "project")
        self.graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "graph.db")
        self.graph.build_from_project(self.project)

    def tearDown(self):
        self.graph.close()
        self.tmpdir.cleanup()

    # === Happy Path ===

    def test_build_returns_correct_symbol_count(self):
        """Verify: build_from_project returns the correct number of symbols.

        Scenario: A project with 3 files (main.py, utils.py, models.py) is built.
        Expected: Symbol count includes all functions, classes, and methods.
        """
        # Act / Assert — build was done in setUp
        # main.py: main, process = 2 functions
        # utils.py: helper, helper_two = 2 functions
        # models.py: User class + __init__ + get_name = 3 symbols
        stats = self.graph.get_stats()
        self.assertEqual(stats["symbols"], 7)

    def test_find_symbol_returns_symbol_info(self):
        """Verify: find_symbol returns SymbolInfo with correct fields.

        Scenario: Querying for 'helper' after building the project.
        Expected: Returns SymbolInfo with name, type, file_path, lines, signature.
        """
        # Act
        symbols = self.graph.query().find_symbol("helper")

        # Assert
        self.assertEqual(len(symbols), 1)
        sym = symbols[0]
        self.assertEqual(sym.name, "helper")
        self.assertEqual(sym.symbol_type, "function")
        self.assertTrue(sym.file_path.endswith("utils.py"))
        self.assertGreater(sym.line_start, 0)
        self.assertGreaterEqual(sym.line_end, sym.line_start)
        self.assertEqual(sym.signature, "helper()")

    def test_find_callers_returns_correct_callers(self):
        """Verify: find_callers returns symbols that call the given function.

        Scenario: helper() is called by main() and process().
        Expected: find_callers("helper") returns main and process.
        """
        # Act
        callers = self.graph.query().find_callers("helper")

        # Assert
        caller_names = {s.name for s in callers}
        self.assertEqual(caller_names, {"main", "process"})

    def test_find_callees_returns_correct_callees(self):
        """Verify: find_callees returns symbols called by the given function.

        Scenario: main() calls helper() and process().
        Expected: find_callees("main") returns helper and process.
        """
        # Act
        callees = self.graph.query().find_callees("main")

        # Assert
        callee_names = {s.name for s in callees}
        self.assertEqual(callee_names, {"helper", "process"})

    def test_find_dependencies_returns_imports(self):
        """Verify: find_dependencies returns imported modules for a file.

        Scenario: main.py imports from utils.
        Expected: find_dependencies(main.py_path) returns a dependency on utils.
        """
        # Arrange
        main_path = str(self.project / "main.py")

        # Act
        deps = self.graph.query().find_dependencies(main_path)

        # Assert
        self.assertGreaterEqual(len(deps), 1)
        target_modules = {d.target_module for d in deps}
        self.assertIn("utils", target_modules)

    def test_get_call_graph_bfs_traversal(self):
        """Verify: get_call_graph performs BFS from entry point.

        Scenario: main() calls helper() and process(); process() calls helper().
        Expected: Graph contains main(0), helper(1), process(1) with correct edges.
        """
        # Act
        result = self.graph.query().get_call_graph("main", max_depth=3)

        # Assert
        node_names = {n["name"] for n in result["nodes"]}
        self.assertIn("main", node_names)
        self.assertIn("helper", node_names)
        self.assertIn("process", node_names)

        edge_pairs = {(e["caller"], e["callee"]) for e in result["edges"]}
        self.assertIn(("main", "helper"), edge_pairs)
        self.assertIn(("main", "process"), edge_pairs)

    def test_find_similar_by_signature(self):
        """Verify: find_similar returns functions with matching parameter names.

        Scenario: helper_two(x, y) exists. Searching for target(x, y).
        Expected: helper_two is returned (Jaccard similarity = 1.0).
        """
        # Act
        results = self.graph.query().find_similar("target(x, y)")

        # Assert
        result_names = {s.name for s in results}
        self.assertIn("helper_two", result_names)

    def test_find_similar_no_match_returns_empty(self):
        """Verify: find_similar returns empty list when no similar signatures exist.

        Scenario: Searching for target(z) when no function has param 'z'.
        Expected: Empty list returned.
        """
        # Act
        results = self.graph.query().find_similar("target(z)")

        # Assert
        self.assertEqual(len(results), 0)

    def test_get_call_graph_nonexistent_entry(self):
        """Verify: get_call_graph handles nonexistent entry point gracefully.

        Scenario: Entry point 'nonexistent' doesn't exist in the graph.
        Expected: Returns graph with just the entry node, no edges.
        """
        # Act
        result = self.graph.query().get_call_graph("nonexistent", max_depth=3)

        # Assert
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(result["nodes"][0]["name"], "nonexistent")
        self.assertEqual(result["nodes"][0]["depth"], 0)
        self.assertEqual(len(result["edges"]), 0)

    def test_class_and_method_indexed_correctly(self):
        """Verify: Class and its methods are indexed with correct types.

        Scenario: models.py has class User with methods __init__ and get_name.
        Expected: User has type 'class', __init__ and get_name have type 'method'.
        """
        # Act
        user_symbols = self.graph.query().find_symbol("User")
        init_symbols = self.graph.query().find_symbol("__init__")
        get_name_symbols = self.graph.query().find_symbol("get_name")

        # Assert
        self.assertEqual(len(user_symbols), 1)
        self.assertEqual(user_symbols[0].symbol_type, "class")
        self.assertEqual(len(init_symbols), 1)
        self.assertEqual(init_symbols[0].symbol_type, "method")
        self.assertEqual(len(get_name_symbols), 1)
        self.assertEqual(get_name_symbols[0].symbol_type, "method")

    def test_signature_extracted_for_functions(self):
        """Verify: Function signatures are extracted and stored correctly.

        Scenario: helper_two(x, y) is defined in utils.py.
        Expected: The stored signature is 'helper_two(x, y)'.
        """
        # Act
        symbols = self.graph.query().find_symbol("helper_two")

        # Assert
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0].signature, "helper_two(x, y)")


class TestIncrementalUpdate(unittest.TestCase):
    """Tests for incremental update correctness (T1)."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tmpdir.name) / "project"
        self.project.mkdir()
        self.source_file = self.project / "target.py"
        self.source_file.write_text(
            'def old_name():\n    """Old function."""\n    return helper()\n\ndef helper():\n    """Helper."""\n    return True\n',
            encoding="utf-8",
        )
        self.graph = CodeKnowledgeGraph(Path(self.tmpdir.name) / "incr.db")
        self.graph.build_from_project(self.project)

    def tearDown(self):
        self.graph.close()
        self.tmpdir.cleanup()

    def test_rename_function_old_name_returns_empty(self):
        """Verify: After renaming a function, the old name returns no results.

        Scenario: old_name is renamed to new_name in the file, update_file is called.
        Expected: find_symbol("old_name") returns empty list.
        """
        # Arrange — rename the function in the file
        self.source_file.write_text(
            'def new_name():\n    """New function."""\n    return helper()\n\ndef helper():\n    """Helper."""\n    return True\n',
            encoding="utf-8",
        )

        # Act
        updated = self.graph.update_file(self.source_file)

        # Assert
        self.assertTrue(updated)
        self.assertEqual(len(self.graph.query().find_symbol("old_name")), 0)

    def test_rename_function_new_name_returns_correct(self):
        """Verify: After renaming, the new name is queryable with correct data.

        Scenario: old_name is renamed to new_name, update_file is called.
        Expected: find_symbol("new_name") returns 1 symbol with correct file path.
        """
        # Arrange
        self.source_file.write_text(
            'def new_name():\n    """New function."""\n    return helper()\n\ndef helper():\n    """Helper."""\n    return True\n',
            encoding="utf-8",
        )

        # Act
        self.graph.update_file(self.source_file)
        symbols = self.graph.query().find_symbol("new_name")

        # Assert
        self.assertEqual(len(symbols), 1)
        self.assertEqual(symbols[0].name, "new_name")
        self.assertTrue(symbols[0].file_path.endswith("target.py"))

    def test_unchanged_file_skips_update(self):
        """Verify: update_file returns False when the file has not changed.

        Scenario: The file content is identical to what was indexed.
        Expected: update_file returns False (no update needed).
        """
        # Act
        result = self.graph.update_file(self.source_file)

        # Assert
        self.assertFalse(result)

    def test_update_project_detects_changed_files(self):
        """Verify: update_project re-indexes only changed files.

        Scenario: One file is modified, another is unchanged.
        Expected: update_project returns 1 (only the changed file was re-parsed).
        """
        # Arrange
        other_file = self.project / "other.py"
        other_file.write_text(
            'def other_func():\n    """Other."""\n    pass\n',
            encoding="utf-8",
        )
        self.graph.build_from_project(self.project)  # Rebuild with both files

        # Modify only target.py
        self.source_file.write_text(
            'def renamed_func():\n    """Renamed."""\n    pass\n',
            encoding="utf-8",
        )

        # Act
        updated = self.graph.update_project(self.project)

        # Assert
        self.assertEqual(updated, 1)  # Only target.py was changed
        self.assertEqual(len(self.graph.query().find_symbol("renamed_func")), 1)
        self.assertEqual(len(self.graph.query().find_symbol("other_func")), 1)

    def test_update_file_adds_new_symbols(self):
        """Verify: update_file adds new symbols when a function is added.

        Scenario: A new function is added to an existing file.
        Expected: After update, the new function is queryable.
        """
        # Arrange
        self.source_file.write_text(
            'def old_name():\n    """Old."""\n    return True\n\ndef added_func():\n    """Newly added."""\n    return False\n',
            encoding="utf-8",
        )

        # Act
        self.graph.update_file(self.source_file)

        # Assert
        self.assertEqual(len(self.graph.query().find_symbol("added_func")), 1)
        self.assertEqual(len(self.graph.query().find_symbol("old_name")), 1)


if __name__ == "__main__":
    unittest.main()
