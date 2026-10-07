"""Deterministic review preview without dispatcher or LLM initialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .file_bundler import FileBundler
from .review_filter import ReviewFilterConfig, filter_review_paths
from .review_input import normalize_review_input
from .rule_engine import default_sources

PREVIEW_SCHEMA_VERSION = "w1-5"


def build_review_preview(
    task: str,
    *,
    changeset: list[str] | tuple[str, ...] | None,
    repo_root: str | Path | None = None,
    include: tuple[str, ...] | list[str] = (),
    exclude: tuple[str, ...] | list[str] = (),
    max_file_size: int | None = 10 * 1024 * 1024,
    rule: str | Path | None = None,
    deleted_paths: tuple[str, ...] | list[str] = (),
    verbose: bool = False,
    diff: str | None = None,
) -> dict[str, Any]:
    """Build the review plan using only deterministic local operations."""
    normalized = normalize_review_input(
        changeset=changeset,
        diff=diff,
        deleted_paths=deleted_paths,
    )
    candidates = list(normalized.paths)
    config = ReviewFilterConfig(
        max_size_bytes=max_file_size,
        user_include=tuple(include),
        user_exclude=tuple(exclude),
        root=repo_root,
        rule_sources=default_sources(repo_root, rule),
    )

    result = filter_review_paths(candidates, deleted_paths=normalized.deleted_paths, config=config)
    bundles = FileBundler().bundle(result.retained_paths, root=repo_root)
    output: dict[str, Any] = {
        "schema_version": PREVIEW_SCHEMA_VERSION,
        "command": "review",
        "preview": True,
        "success": True,
        "task": task,
        "candidate_count": result.candidate_count,
        "retained_count": len(result.retained_paths),
        "excluded_count": len(result.excluded_paths),
        "gate_counts": dict(result.gate_counts),
        "bundle_count": len(bundles),
        "bundles": [{"index": index, "file_count": len(bundle)} for index, bundle in enumerate(bundles, start=1)],
    }
    if verbose:
        output["review_filter"] = result.to_dict()
        output["bundles"] = [
            {"index": index, "file_count": len(bundle), "files": bundle}
            for index, bundle in enumerate(bundles, start=1)
        ]
    return output


def print_review_preview(payload: dict[str, Any], output_format: str = "markdown") -> None:
    """Render a preview payload without adding dispatcher report content."""
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if output_format == "compact":
        print(
            f"preview: candidates={payload['candidate_count']} "
            f"retained={payload['retained_count']} excluded={payload['excluded_count']} "
            f"bundles={payload['bundle_count']}"
        )
        return

    print("Review Preview")
    print(f"Task: {payload['task']}")
    print(f"Candidates: {payload['candidate_count']}")
    print(f"Retained: {payload['retained_count']}")
    print(f"Excluded: {payload['excluded_count']}")
    print(f"Bundles: {payload['bundle_count']}")
    print("Gate counts:")
    for gate, count in payload["gate_counts"].items():
        print(f"  {gate}: {count}")
    if "review_filter" in payload:
        print("Excluded paths:")
        for item in payload["review_filter"]["excluded_paths"]:
            print(f"  {item['path']} [{item['gate']}] {item['reason']}")
        print("Bundles:")
        for bundle in payload["bundles"]:
            files = ", ".join(bundle["files"])
            print(f"  {bundle['index']}: {files}")
