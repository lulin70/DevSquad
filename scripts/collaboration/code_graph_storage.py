#!/usr/bin/env python3
"""SQLite storage layer for CodeKnowledgeGraph.

Stores code symbols, call edges, and dependency edges in three tables.
Uses append-only pattern for audit trail.

Tables:
    symbols  - code symbols (functions, classes, methods)
    edges    - call edges and dependency edges (discriminated by edge_type)
    files    - file metadata with content hash for incremental updates
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Represents a code symbol (function, class, method, or module)."""

    name: str
    symbol_type: str  # function|class|method|module
    file_path: str
    line_start: int
    line_end: int
    docstring: str
    signature: str


@dataclass
class CallEdge:
    """Represents a call relationship between two symbols."""

    caller: str
    callee: str
    file_path: str
    line: int


@dataclass
class DependencyEdge:
    """Represents an import dependency between modules."""

    source_module: str
    target_module: str
    import_type: str  # import|from_import|relative


class CodeGraphStorage:
    """SQLite-backed storage for code knowledge graph."""

    def __init__(self, db_path: Path):
        """Initialize storage. Create tables if not exist.

        Args:
            db_path: Path to the SQLite database file. Parent directories
                are created automatically if they do not exist.

        Raises:
            sqlite3.Error: If the database cannot be opened or tables cannot be created.
            OSError: If the parent directory cannot be created.
        """
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables and indexes if they don't exist."""
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                symbol_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                docstring TEXT DEFAULT '',
                signature TEXT DEFAULT '',
                UNIQUE(name, file_path, line_start)
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_type TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line INTEGER DEFAULT 0,
                import_type TEXT DEFAULT '',
                UNIQUE(edge_type, source, target, file_path, line)
            );

            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                line_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
            CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(edge_type, source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(edge_type, target);
            CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_path);
            """
        )
        self._conn.commit()

    def upsert_symbol(self, symbol: SymbolInfo) -> bool:
        """Insert or update a single symbol.

        Args:
            symbol: SymbolInfo dataclass with symbol metadata.

        Returns:
            True if the symbol was inserted or updated.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO symbols (name, symbol_type, file_path, line_start, line_end, docstring, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, file_path, line_start) DO UPDATE SET
                symbol_type=excluded.symbol_type,
                line_end=excluded.line_end,
                docstring=excluded.docstring,
                signature=excluded.signature
            """,
            (
                symbol.name,
                symbol.symbol_type,
                symbol.file_path,
                symbol.line_start,
                symbol.line_end,
                symbol.docstring,
                symbol.signature,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def upsert_symbols(self, symbols: list[SymbolInfo]) -> int:
        """Batch upsert symbols in a single transaction.

        Args:
            symbols: List of SymbolInfo dataclasses to upsert.

        Returns:
            Number of symbols upserted.
        """
        if not symbols:
            return 0
        cur = self._conn.cursor()
        count = 0
        for symbol in symbols:
            cur.execute(
                """
                INSERT INTO symbols (name, symbol_type, file_path, line_start, line_end, docstring, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, file_path, line_start) DO UPDATE SET
                    symbol_type=excluded.symbol_type,
                    line_end=excluded.line_end,
                    docstring=excluded.docstring,
                    signature=excluded.signature
                """,
                (
                    symbol.name,
                    symbol.symbol_type,
                    symbol.file_path,
                    symbol.line_start,
                    symbol.line_end,
                    symbol.docstring,
                    symbol.signature,
                ),
            )
            if cur.rowcount > 0:
                count += 1
        self._conn.commit()
        return count

    def delete_symbols_for_file(self, file_path: str) -> int:
        """Delete all symbols associated with a file.

        Args:
            file_path: Absolute path of the file.

        Returns:
            Number of symbols deleted.
        """
        cur = self._conn.cursor()
        cur.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
        self._conn.commit()
        return cur.rowcount

    def upsert_call_edge(self, edge: CallEdge) -> bool:
        """Insert or update a single call edge.

        Args:
            edge: CallEdge dataclass with caller, callee, file, and line.

        Returns:
            True if the edge was inserted or updated.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO edges (edge_type, source, target, file_path, line, import_type)
            VALUES ('call', ?, ?, ?, ?, '')
            ON CONFLICT(edge_type, source, target, file_path, line) DO UPDATE SET
                target=excluded.target
            """,
            (edge.caller, edge.callee, edge.file_path, edge.line),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def upsert_call_edges(self, edges: list[CallEdge]) -> int:
        """Batch upsert call edges in a single transaction.

        Args:
            edges: List of CallEdge dataclasses to upsert.

        Returns:
            Number of edges upserted.
        """
        if not edges:
            return 0
        cur = self._conn.cursor()
        count = 0
        for edge in edges:
            cur.execute(
                """
                INSERT INTO edges (edge_type, source, target, file_path, line, import_type)
                VALUES ('call', ?, ?, ?, ?, '')
                ON CONFLICT(edge_type, source, target, file_path, line) DO UPDATE SET
                    target=excluded.target
                """,
                (edge.caller, edge.callee, edge.file_path, edge.line),
            )
            if cur.rowcount > 0:
                count += 1
        self._conn.commit()
        return count

    def delete_edges_for_file(self, file_path: str) -> int:
        """Delete all edges associated with a file.

        Args:
            file_path: Absolute path of the file.

        Returns:
            Number of edges deleted.
        """
        cur = self._conn.cursor()
        cur.execute("DELETE FROM edges WHERE file_path = ?", (file_path,))
        self._conn.commit()
        return cur.rowcount

    def upsert_dependency(self, dep: DependencyEdge) -> bool:
        """Insert or update a dependency edge.

        Args:
            dep: DependencyEdge dataclass with source/target modules and import type.

        Returns:
            True if the dependency was inserted or updated.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO edges (edge_type, source, target, file_path, line, import_type)
            VALUES ('dependency', ?, ?, '', 0, ?)
            ON CONFLICT(edge_type, source, target, file_path, line) DO UPDATE SET
                import_type=excluded.import_type
            """,
            (dep.source_module, dep.target_module, dep.import_type),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def upsert_file(self, path: str, hash: str, line_count: int) -> bool:
        """Insert or update file metadata (path, hash, line count).

        Args:
            path: Absolute file path.
            hash: SHA256 content hash of the file.
            line_count: Number of lines in the file.

        Returns:
            True if the file record was inserted or updated.
        """
        cur = self._conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """
            INSERT INTO files (path, hash, line_count, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                hash=excluded.hash,
                line_count=excluded.line_count,
                updated_at=excluded.updated_at
            """,
            (path, hash, line_count, now),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_file_hash(self, path: str) -> str | None:
        """Get the stored content hash for a file.

        Args:
            path: Absolute file path.

        Returns:
            The SHA256 hash string, or None if the file is not tracked.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT hash FROM files WHERE path = ?", (path,))
        row = cur.fetchone()
        return row[0] if row else None

    def query_symbol(self, name: str) -> list[SymbolInfo]:
        """Query symbols by exact name.

        Args:
            name: Symbol name to search for.

        Returns:
            List of matching SymbolInfo objects (may span multiple files).
        """
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM symbols WHERE name = ?", (name,))
        return [self._row_to_symbol(row) for row in cur.fetchall()]

    def query_callers(self, function_name: str) -> list[SymbolInfo]:
        """Find symbols that call the given function.

        Args:
            function_name: Name of the callee function.

        Returns:
            List of SymbolInfo objects for caller symbols.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT s.* FROM symbols s
            JOIN edges e ON s.name = e.source AND s.file_path = e.file_path
            WHERE e.edge_type = 'call' AND e.target = ?
            """,
            (function_name,),
        )
        return [self._row_to_symbol(row) for row in cur.fetchall()]

    def query_callees(self, function_name: str) -> list[SymbolInfo]:
        """Find symbols called by the given function.

        Args:
            function_name: Name of the caller function.

        Returns:
            List of SymbolInfo objects for callee symbols that exist in the codebase.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT s.* FROM symbols s
            JOIN edges e ON s.name = e.target
            WHERE e.edge_type = 'call' AND e.source = ?
            """,
            (function_name,),
        )
        return [self._row_to_symbol(row) for row in cur.fetchall()]

    def query_dependencies(self, module_path: str) -> list[DependencyEdge]:
        """Query dependency edges for a module.

        Args:
            module_path: Source module path to query dependencies for.

        Returns:
            List of DependencyEdge objects.
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM edges WHERE edge_type = 'dependency' AND source = ?",
            (module_path,),
        )
        return [
            DependencyEdge(
                source_module=row["source"],
                target_module=row["target"],
                import_type=row["import_type"],
            )
            for row in cur.fetchall()
        ]

    def query_symbols_by_type(self, symbol_type: str) -> list[SymbolInfo]:
        """Query symbols by type (function, class, method, module).

        Args:
            symbol_type: Type of symbols to query.

        Returns:
            List of matching SymbolInfo objects.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM symbols WHERE symbol_type = ?", (symbol_type,))
        return [self._row_to_symbol(row) for row in cur.fetchall()]

    def get_stats(self) -> dict:
        """Get storage statistics.

        Returns:
            Dictionary with counts: symbols, call_edges, dependencies, files.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM symbols")
        symbol_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type = 'call'")
        call_edge_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE edge_type = 'dependency'")
        dep_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]
        return {
            "symbols": symbol_count,
            "call_edges": call_edge_count,
            "dependencies": dep_count,
            "files": file_count,
        }

    def _row_to_symbol(self, row: sqlite3.Row) -> SymbolInfo:
        """Convert a database row to a SymbolInfo dataclass.

        Args:
            row: sqlite3.Row from the symbols table.

        Returns:
            SymbolInfo dataclass populated from the row.
        """
        return SymbolInfo(
            name=row["name"],
            symbol_type=row["symbol_type"],
            file_path=row["file_path"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            docstring=row["docstring"],
            signature=row["signature"],
        )

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
