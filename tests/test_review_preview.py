"""Unit tests for the deterministic review preview (W1-4, contract C11-C13)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collaboration.review_preview import (
    PREVIEW_SCHEMA_VERSION,
    build_review_preview,
    print_review_preview,
)


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (tmp_path / "src" / "two.py").write_text("print('two')\n", encoding="utf-8")
    (tmp_path / "src" / "drop.py").write_text("print('drop')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    return tmp_path


def _build(repo: Path, *, verbose: bool = False, **overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "changeset": ["src/keep.py", "src/two.py", "src/drop.py", ".env"],
        "repo_root": str(repo),
        "exclude": ("src/drop.py",),
        "verbose": verbose,
    }
    kwargs.update(overrides)
    return build_review_preview("review these files", **kwargs)  # type: ignore[arg-type]


def test_summary_shape_is_default(tmp_path: Path) -> None:
    payload = _build(_make_repo(tmp_path))

    assert payload["schema_version"] == PREVIEW_SCHEMA_VERSION
    assert payload["preview"] is True
    assert payload["success"] is True
    assert payload["candidate_count"] == 4
    assert payload["retained_count"] == 2
    assert payload["excluded_count"] == 2
    assert payload["gate_counts"]["user_exclude"] == 1
    assert payload["gate_counts"]["secret_exclude"] == 1
    assert payload["bundle_count"] == 1
    # C12: per-path details require --verbose.
    assert "review_filter" not in payload
    assert all("files" not in bundle for bundle in payload["bundles"])


def test_verbose_contains_path_details(tmp_path: Path) -> None:
    payload = _build(_make_repo(tmp_path), verbose=True)

    details = payload["review_filter"]
    assert details["retained_paths"] == ["src/keep.py", "src/two.py"]
    gates = {item["gate"] for item in details["excluded_paths"]}
    assert gates == {"user_exclude", "secret_exclude"}
    assert payload["bundles"][0]["files"] == ["src/keep.py", "src/two.py"]


def test_secret_path_is_redacted_even_in_verbose(tmp_path: Path) -> None:
    payload = _build(_make_repo(tmp_path), verbose=True)

    serialized = json.dumps(payload, ensure_ascii=False)
    assert ".env" not in serialized
    assert "[REDACTED sensitive path]" in serialized
    assert "sensitive path excluded before user configuration" in serialized


def test_preview_is_deterministic(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    assert _build(repo) == _build(repo)
    assert _build(repo, verbose=True) == _build(repo, verbose=True)


def test_bundling_threshold_matches_production(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo / "src").mkdir(exist_ok=True)
    for index in range(12):
        (repo / "src" / f"mod{index:02d}.py").write_text(f"x = {index}\n", encoding="utf-8")

    payload = build_review_preview(
        "review many files",
        changeset=[f"src/mod{index:02d}.py" for index in range(12)],
        repo_root=str(repo),
    )

    assert payload["retained_count"] == 12
    assert payload["bundle_count"] == 2
    assert all(bundle["file_count"] == 10 or bundle["file_count"] == 2 for bundle in payload["bundles"])


def test_rule_source_is_honoured(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    rule_file = repo / "custom_rule.json"
    rule_file.write_text(
        json.dumps({"rules": [{"pattern": "**/*.py", "body": {"kind": "code"}}]}),
        encoding="utf-8",
    )

    payload = build_review_preview(
        "review with rules",
        changeset=["src/keep.py"],
        repo_root=str(repo),
        rule=str(rule_file),
        verbose=True,
    )

    assert payload["retained_count"] == 1


def test_empty_changeset_is_handled(tmp_path: Path) -> None:
    payload = build_review_preview("review nothing", changeset=None, repo_root=str(tmp_path))

    assert payload["candidate_count"] == 0
    assert payload["retained_count"] == 0
    assert payload["bundle_count"] == 0
    assert payload["success"] is True


def test_deleted_paths_are_excluded(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    payload = build_review_preview(
        "review with deletion",
        changeset=["src/keep.py", "src/two.py"],
        repo_root=str(repo),
        deleted_paths=("src/two.py",),
    )

    assert payload["gate_counts"]["deleted"] == 1
    assert payload["retained_count"] == 1


@pytest.mark.parametrize("output_format", ["json", "compact", "markdown"])
def test_print_review_preview_formats(tmp_path: Path, output_format: str, capsys: pytest.CaptureFixture[str]) -> None:
    payload = _build(_make_repo(tmp_path), verbose=(output_format == "markdown"))

    print_review_preview(payload, output_format)

    out = capsys.readouterr().out
    if output_format == "json":
        assert json.loads(out) == payload
    elif output_format == "compact":
        assert "candidates=4" in out and "retained=2" in out
    else:
        assert "Review Preview" in out
        assert "user_exclude: 1" in out
