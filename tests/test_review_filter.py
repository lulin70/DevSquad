from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collaboration.review_filter import (
    GATE_NAMES,
    DeterministicReviewFilter,
    ReviewFilterConfig,
)
from scripts.collaboration.rule_engine import RuleSources


@pytest.fixture
def rule_sources(tmp_path: Path) -> RuleSources:
    system = tmp_path / "system.json"
    system.write_text(
        json.dumps(
            {
                "rules": [
                    {"pattern": "**/*.py", "body": {"kind": "source"}},
                    {"pattern": "**/*.md", "body": {"kind": "document"}},
                    {"pattern": "**", "body": {"kind": "unclaimed"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    return RuleSources(system=system)


def run_filter(
    paths: list[str],
    rule_sources: RuleSources,
    *,
    contents: dict[str, bytes | str] | None = None,
    **kwargs: object,
):
    config = ReviewFilterConfig(rule_sources=rule_sources, **kwargs)
    return DeterministicReviewFilter(config, contents=contents).filter(paths)


def test_gate_names_are_exact_and_all_counts_are_present(rule_sources: RuleSources) -> None:
    result = run_filter(["src/app.py"], rule_sources, contents={"src/app.py": "print(1)"})
    assert GATE_NAMES == (
        "secret_exclude",
        "binary",
        "unsupported_ext",
        "too_large",
        "user_exclude",
        "user_include",
        "default_path",
        "deleted",
    )
    assert tuple(result.gate_counts) == GATE_NAMES


def test_secret_is_first_and_include_cannot_restore_it(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["config/.env"],
        rule_sources,
        contents={"config/.env": "TOKEN=not-for-review"},
        user_include=("**/.env",),
    )
    assert result.excluded_paths[0].gate == "secret_exclude"
    assert result.gate_counts["secret_exclude"] == 1
    assert not result.retained_paths


@pytest.mark.parametrize(
    "path",
    [".ssh/id_ed25519", "certs/server.pem", "keys/release.key", "ops/credentials.json"],
)
def test_rule_engine_sensitive_path_semantics_are_reused(path: str, rule_sources: RuleSources) -> None:
    result = run_filter([path], rule_sources, contents={path: "text"})
    assert result.excluded_paths[0].gate == "secret_exclude"


def test_binary_is_detected_from_content_not_extension(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["src/image.py"],
        rule_sources,
        contents={"src/image.py": b"valid\x00utf8"},
    )
    assert result.excluded_paths[0].gate == "binary"


def test_too_large_is_configurable(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["src/large.py"],
        rule_sources,
        contents={"src/large.py": "12345"},
        max_size_bytes=4,
    )
    assert result.excluded_paths[0].gate == "too_large"


def test_user_exclude_and_include_use_globs(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["src/generated.py", "src/keep.py"],
        rule_sources,
        contents={"src/generated.py": "x", "src/keep.py": "x"},
        user_exclude=("**/generated.py",),
        user_include=("src/keep.py",),
    )
    assert [item.path for item in result.excluded_paths] == ["src/generated.py"]
    assert result.excluded_paths[0].gate == "user_exclude"
    assert result.retained_paths == ["src/keep.py"]
    assert result.gate_counts["user_include"] == 1


def test_default_paths_are_excluded_without_secret_double_counting(rule_sources: RuleSources) -> None:
    result = run_filter(
        [".git/config", "__pycache__/cache.pyc", "node_modules/pkg/index.py", "dist/app.py", "build/app.py"],
        rule_sources,
        contents={
            ".git/config": "x",
            "__pycache__/cache.pyc": "x",
            "node_modules/pkg/index.py": "x",
            "dist/app.py": "x",
            "build/app.py": "x",
        },
    )
    assert all(item.gate == "default_path" for item in result.excluded_paths)
    assert ".git/config" in [item.path for item in result.excluded_paths]
    assert result.gate_counts["secret_exclude"] == 0


def test_deleted_paths_are_explicitly_passed_by_caller(rule_sources: RuleSources) -> None:
    result = DeterministicReviewFilter(
        ReviewFilterConfig(rule_sources=rule_sources), contents={"src/removed.py": "x"}
    ).filter(["src/removed.py"], deleted_paths=["src/removed.py"])
    assert result.excluded_paths[0].gate == "deleted"


def test_unclaimed_system_kind_is_unsupported(rule_sources: RuleSources) -> None:
    result = run_filter(["notes.txt"], rule_sources, contents={"notes.txt": "text"})
    assert result.excluded_paths[0].gate == "unsupported_ext"


def test_malformed_rule_resolution_fails_closed_as_unsupported(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    sources = RuleSources(system=malformed)
    result = run_filter(["src/app.py"], sources, contents={"src/app.py": "x"})
    assert result.excluded_paths[0].gate == "unsupported_ext"
    assert "failed closed" in result.excluded_paths[0].reason


def test_duplicate_candidates_have_one_final_decision(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["./src/app.py", "src/app.py", "src\\app.py"],
        rule_sources,
        contents={"src/app.py": "ok"},
    )
    assert result.candidate_count == 1
    assert result.retained_paths == ["src/app.py"]
    assert result.excluded_paths == []


def test_root_string_reads_real_file(tmp_path: Path, rule_sources: RuleSources) -> None:
    source = tmp_path / "src" / "app.py"
    source.parent.mkdir()
    source.write_text("print('ok')", encoding="utf-8")
    result = DeterministicReviewFilter(ReviewFilterConfig(root=str(tmp_path), rule_sources=rule_sources)).filter(
        ["src/app.py"]
    )
    assert result.retained_paths == ["src/app.py"]


def test_secret_path_is_redacted_in_serialized_output(rule_sources: RuleSources) -> None:
    result = run_filter(
        ["ops/credentials.json"],
        rule_sources,
        contents={"ops/credentials.json": "secret"},
    )
    serialized = result.to_dict()
    assert serialized["excluded_paths"][0]["path"] == "[REDACTED sensitive path]"
    assert serialized["excluded_paths"][0]["reason"] == ("sensitive path excluded before user configuration")
    assert "credentials.json" not in str(serialized)


def test_every_candidate_has_one_final_decision_and_counts_conserve(rule_sources: RuleSources) -> None:
    paths = ["src/app.py", "src/image.py", "notes.txt", "src/large.py", "src/removed.py"]
    result = DeterministicReviewFilter(
        ReviewFilterConfig(
            rule_sources=rule_sources,
            max_size_bytes=3,
            user_exclude=("src/large.py",),
        ),
        contents={
            "src/app.py": "ok",
            "src/image.py": b"x\x00",
            "notes.txt": "text",
            "src/large.py": "large",
            "src/removed.py": "ok",
        },
    ).filter(paths, deleted_paths=["src/removed.py"])
    assert len(result.retained_paths) + len(result.excluded_paths) == result.candidate_count
    exclusion_counts = sum(count for gate, count in result.gate_counts.items() if gate != "user_include")
    assert exclusion_counts + len(result.retained_paths) == result.candidate_count
    assert len({item.path for item in result.excluded_paths}) == len(result.excluded_paths)
