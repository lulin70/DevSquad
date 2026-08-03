#!/usr/bin/env python3
"""
FileBundler — Deterministic file bundling for review mode (V4.5.0 PRD §10.1.3).

Inspired by alibaba/open-code-review's smart file bundling. Groups related
files into review units so a large changeset can be reviewed in
divide-and-conquer fashion (each bundle → one Worker with isolated context).

DETERMINISTIC — no LLM is involved in bundling decisions. Only the Python
stdlib ``ast`` module is used to parse imports. All ``ast`` parsing failures
(syntax errors, non-Python files, encoding issues, anything) are caught so a
single bad file never breaks the whole bundle.

Bundling rules (PRD §10.1.3):
  1. Same parent directory → same bundle.
  2. Import chain (file A imports file B) → same bundle.
  3. Max ``max_per_bundle`` files per bundle (overflow → split).
  4. A single input file → a single bundle.

Anti-ghost: module-level ``_call_counter`` increments on every public call.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

__all__ = ["FileBundler"]

logger = logging.getLogger(__name__)

# V4.5.0 Anti-ghost call counter (module-level). Incremented on every public
# FileBundler method call so ``check_module_activation.py`` can verify the
# module is wired into the review-mode pipeline (not a ghost feature).
_call_counter: int = 0


class FileBundler:
    """Deterministic file bundling for review mode (V4.5.0).

    Inspired by alibaba/open-code-review's smart file bundling. Groups
    related files into review units for divide-and-conquer review.
    DETERMINISTIC — no LLM involved in bundling decisions.
    """

    def bundle(self, files: list[str], max_per_bundle: int = 10) -> list[list[str]]:
        """Group files by path prefix + import relationship.

        Rules:
        - Same directory → same bundle
        - Import chain (file A imports file B) → same bundle
        - Max ``max_per_bundle`` files per bundle (overflow → split)
        - Single file → single bundle

        Args:
            files: List of file paths (POSIX or mixed). Need not exist on disk
                for directory grouping; import merging reads file contents and
                silently skips files that cannot be parsed.
            max_per_bundle: Maximum files per bundle. Must be >= 1; values < 1
                are clamped to 1.

        Returns:
            List of bundles, each a list of file paths (sorted for determinism).
            Empty input → empty list. Order of bundles is deterministic.
        """
        global _call_counter
        _call_counter += 1

        if not files:
            return []
        if max_per_bundle < 1:
            max_per_bundle = 1

        # Step 1: group by parent directory.
        dir_groups = self._group_by_directory(files)
        # Step 2: merge groups connected by import relationships.
        merged = self._merge_by_imports(dir_groups)
        # Step 3: split any bundle exceeding the max size.
        split = self._split_oversized(merged, max_per_bundle)
        # Deterministic output: sort within each bundle and sort bundles.
        return [sorted(b) for b in sorted(split, key=lambda b: b[0] if b else "")]

    def _group_by_directory(self, files: list[str]) -> dict[str, list[str]]:
        """Group files by parent directory.

        Returns a dict mapping ``directory path`` → ``list of file paths``.
        Files with no parent (bare filenames) are grouped under the empty
        string key. The original file strings are preserved (no normalization)
        so callers get back exactly what they passed in.
        """
        groups: dict[str, list[str]] = {}
        for f in files:
            parent = str(Path(f).parent) if f else ""
            # Path("x.py").parent == "." — normalize bare-cwd to "" for a
            # single consistent bucket, but keep subdirectory paths intact.
            if parent == ".":
                parent = ""
            groups.setdefault(parent, []).append(f)
        return groups

    def _merge_by_imports(self, groups: dict[str, list[str]]) -> list[list[str]]:
        """Merge groups that have import relationships using the ``ast`` module.

        Builds a file→imported-modules map by parsing each Python file with
        ``ast`` (ALL exceptions caught — syntax errors / non-Python / encoding
        failures simply yield no imports for that file). Then performs a
        union-find over groups: if any file in group X imports a module that
        maps to a file in group Y, X and Y merge into one bundle.
        """
        # Flatten all files and build a module-name → file-path index.
        all_files: list[str] = []
        for grp in groups.values():
            all_files.extend(grp)

        # Map a file to candidate module names it could be imported as:
        #   - the stem (basename without .py): "auth/login.py" -> "login"
        #   - the dotted path from cwd: "auth/login.py" -> "auth.login"
        stem_to_file: dict[str, str] = {}
        dotted_to_file: dict[str, str] = {}
        for f in all_files:
            p = Path(f)
            if p.suffix == ".py":
                stem_to_file.setdefault(p.stem, f)
                dotted = self._path_to_dotted(f)
                if dotted:
                    dotted_to_file.setdefault(dotted, f)

        # Parse imports for each file (catch ALL exceptions per file).
        file_to_imported_files: dict[str, set[str]] = {}
        for f in all_files:
            imported = self._extract_imported_files(f, stem_to_file, dotted_to_file)
            if imported:
                file_to_imported_files[f] = imported

        # Union-find over group membership.
        # Each file → its current bundle root (a representative file).
        parent: dict[str, str] = {f: f for f in all_files}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # First, union all files that share a parent directory (directory
        # grouping from _group_by_directory). This preserves the "same
        # directory → same bundle" rule before import-based merging adds
        # cross-directory merges.
        for grp_files in groups.values():
            if len(grp_files) > 1:
                anchor = grp_files[0]
                for other in grp_files[1:]:
                    union(anchor, other)

        # Then, union files connected by import relationships (may merge
        # across directory boundaries).
        for src, targets in file_to_imported_files.items():
            for tgt in targets:
                if tgt in parent:  # only merge files in our input set
                    union(src, tgt)

        # Collect merged bundles keyed by root.
        bundles: dict[str, list[str]] = {}
        for f in all_files:
            root = find(f)
            bundles.setdefault(root, []).append(f)
        return list(bundles.values())

    def _split_oversized(self, bundles: list[list[str]], max_size: int) -> list[list[str]]:
        """Split bundles exceeding ``max_size`` into chunks of at most ``max_size``.

        Preserves file order within each split chunk. A bundle at or below
        ``max_size`` is returned unchanged.
        """
        result: list[list[str]] = []
        for b in bundles:
            if len(b) <= max_size:
                result.append(list(b))
                continue
            for i in range(0, len(b), max_size):
                result.append(list(b[i : i + max_size]))
        return result

    # ------------------------------------------------------------------
    # Import-parsing helpers (all exception-safe)
    # ------------------------------------------------------------------

    @staticmethod
    def _path_to_dotted(file_path: str) -> str:
        """Convert a file path to a dotted module path.

        ``"auth/login.py"`` → ``"auth.login"``. ``"login.py"`` → ``"login"``.
        Returns "" for non-.py files.
        """
        p = Path(file_path)
        if p.suffix != ".py":
            return ""
        parts = list(p.with_suffix("").parts)
        if parts and parts[0] == ".":
            parts = parts[1:]
        return ".".join(parts)

    @staticmethod
    def _extract_imported_files(
        file_path: str,
        stem_to_file: dict[str, str],
        dotted_to_file: dict[str, str],
    ) -> set[str]:
        """Parse ``file_path`` with ``ast`` and return the set of input files
        it imports.

        Catches ALL exceptions — a file that cannot be read or parsed
        (syntax error, binary, non-Python, encoding issue, permission denied)
        simply contributes no imports. This guarantees one bad file never
        breaks bundling for the whole changeset.
        """
        imported: set[str] = set()
        # Catch ALL exceptions during ast parsing (per the task requirement).
        try:
            with open(file_path, encoding="utf-8") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=file_path)
        except Exception:  # noqa: BLE001 — intentionally broad: any parse failure
            return imported

        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names if alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.append(node.module)
                # Relative imports (level > 0): resolve against the file's own
                # dotted path prefix as a best-effort heuristic.
                if node.level and node.level > 0:
                    base = FileBundler._path_to_dotted(file_path)
                    if base:
                        parts = base.split(".")
                        # level=1 means same package; drop `level` parts from the end.
                        if node.level <= len(parts):
                            prefix = parts[: len(parts) - node.level]
                            if node.module:
                                modules.append(".".join(prefix + [node.module]))
                            else:
                                modules.append(".".join(prefix))

            for mod in modules:
                # Exact dotted-path match.
                if mod in dotted_to_file:
                    target = dotted_to_file[mod]
                    if target != file_path:
                        imported.add(target)
                # Match by the final segment's stem (e.g. ``from pkg import login``
                # or ``import pkg.login`` → match ``login`` stem).
                tail = mod.split(".")[-1]
                if tail in stem_to_file:
                    target = stem_to_file[tail]
                    if target != file_path:
                        imported.add(target)
        return imported
