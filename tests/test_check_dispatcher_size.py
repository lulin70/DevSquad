#!/usr/bin/env python3
"""V4.6.0-doc-governance P2: tests for scripts/check_dispatcher_size.py.

These tests pin the contract:

  1. Snapshot captures {rel_path: loc} for every .py under source.
  2. --write-baseline creates a JSON file at the baseline path.
  3. main() exits 0 when no file exceeds the threshold AND no net growth.
  4. main() exits 1 when a tracked file grows past its baseline.
  5. _load_baseline returns None for missing/malformed JSON.
  6. Empty files and __pycache__ are excluded.
  7. Line counts ignore blank lines (non-empty LOC).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_dispatcher_size as gate  # noqa: E402

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_source(tmp_path: Path) -> Path:
    """Build a small fake source tree with deterministic file sizes."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "small.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    (src / "medium.py").write_text("\n".join(f"x_{i} = {i}" for i in range(50)) + "\n", encoding="utf-8")
    (src / "big.py").write_text("\n".join(f"y_{i} = {i}" for i in range(900)) + "\n", encoding="utf-8")
    (src / "blank_lines.py").write_text("\n\n\na = 1\n\n\nb = 2\n\n", encoding="utf-8")
    # Hidden / pycache must be excluded
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "should_skip.py").write_text("ignored", encoding="utf-8")
    (src / ".hidden").mkdir()
    (src / ".hidden" / "hidden.py").write_text("ignored", encoding="utf-8")
    return src


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------


class TestSnapshot:
    """Snapshot excludes __pycache__/.hidden and counts non-empty lines only."""

    def test_snapshot_includes_py_files(self, fake_source):
        snap = gate._snapshot(fake_source)
        names = {Path(p).name for p in snap}
        assert "small.py" in names
        assert "medium.py" in names
        assert "big.py" in names

    def test_snapshot_excludes_pycache_and_hidden(self, fake_source):
        snap = gate._snapshot(fake_source)
        for rel in snap:
            assert "__pycache__" not in rel
            assert "/.hidden/" not in rel

    def test_blank_lines_not_counted(self, fake_source):
        snap = gate._snapshot(fake_source)
        # blank_lines.py has 2 non-empty lines (a=1, b=2) out of 9 raw
        rel = next(p for p in snap if p.endswith("blank_lines.py"))
        assert snap[rel] == 2

    def test_line_count_basic(self, fake_source):
        assert gate._line_count(fake_source / "small.py") == 2


# ---------------------------------------------------------------------------
# Baseline IO tests
# ---------------------------------------------------------------------------


class TestBaselineIO:
    """_load_baseline returns dict on valid JSON, None on missing/malformed."""

    def test_missing_file_returns_none(self, tmp_path):
        assert gate._load_baseline(tmp_path / "missing.json") is None

    def test_valid_json_returns_dict(self, tmp_path):
        p = tmp_path / "b.json"
        p.write_text(json.dumps({"a.py": 100, "b.py": 50}), encoding="utf-8")
        result = gate._load_baseline(p)
        assert result == {"a.py": 100, "b.py": 50}

    def test_malformed_json_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json at all {{{", encoding="utf-8")
        assert gate._load_baseline(p) is None

    def test_non_dict_json_returns_none(self, tmp_path):
        p = tmp_path / "list.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        assert gate._load_baseline(p) is None


# ---------------------------------------------------------------------------
# main() exit-code tests
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    """End-to-end behavior of check_dispatcher_size.main()."""

    def test_write_baseline_creates_file_and_exits_zero(self, fake_source, tmp_path):
        baseline = tmp_path / "out" / "snap.json"
        rc = gate.main([
            "--source", str(fake_source),
            "--baseline", str(baseline),
            "--write-baseline",
        ])
        assert rc == 0
        assert baseline.exists()
        data = json.loads(baseline.read_text(encoding="utf-8"))
        assert "files" in data
        assert "generated_at" in data
        assert "max_lines" in data
        assert data["version"] == "v4.6.0-doc-governance"

    def test_no_growth_exits_zero(self, fake_source, tmp_path):
        baseline = tmp_path / "b.json"
        # Write baseline matching current sizes
        gate.main(["--source", str(fake_source), "--baseline", str(baseline), "--write-baseline"])
        # Re-run with same tree → no growth → exit 0
        rc = gate.main(["--source", str(fake_source), "--baseline", str(baseline)])
        assert rc == 0

    def test_net_growth_blocks(self, fake_source, tmp_path):
        baseline = tmp_path / "b.json"
        # Write baseline that under-reports big.py (e.g., 500 instead of 900).
        # The snapshot keys use paths relative to gate.REPO_ROOT, so we
        # patch REPO_ROOT to tmp_path so the keys line up.
        baseline.write_text(json.dumps({
            "version": "v4.6.0-doc-governance",
            "max_lines": 800,
            "generated_at": "2026-09-05T00:00:00Z",
            "files": {
                "src/small.py": 2,
                "src/medium.py": 50,
                "src/big.py": 500,  # under-report (current is 900)
                "src/blank_lines.py": 2,
            },
        }), encoding="utf-8")

        original_root = gate.REPO_ROOT
        gate.REPO_ROOT = tmp_path
        try:
            rc = gate.main(["--source", str(fake_source), "--baseline", str(baseline)])
        finally:
            gate.REPO_ROOT = original_root
        # big.py grew from 500 → 900 (net growth), blocks
        assert rc == 1

    def test_missing_baseline_falls_back_to_absolute_threshold(self, fake_source, tmp_path):
        # No baseline file → gate warns but does not block on existing oversize.
        rc = gate.main([
            "--source", str(fake_source),
            "--baseline", str(tmp_path / "no_baseline.json"),
            "--max-lines", "1000",  # high ceiling so existing files don't trip
        ])
        assert rc == 0
