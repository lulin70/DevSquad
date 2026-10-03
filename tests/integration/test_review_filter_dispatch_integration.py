from __future__ import annotations

import asyncio
from pathlib import Path

from scripts.collaboration.dispatcher import MultiAgentDispatcher


def _make_review_repo(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (tmp_path / "src" / "drop.py").write_text("print('drop')\n", encoding="utf-8")
    (tmp_path / "src" / "deleted.py").write_text("print('deleted')\n", encoding="utf-8")


def _dispatch_kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "mode": "review",
        "changeset": ["src/keep.py", "src/drop.py", "src/deleted.py", ".env"],
        "repo_root": str(tmp_path),
        "include": ("src/keep.py",),
        "exclude": ("src/drop.py",),
        "deleted_paths": ("src/deleted.py",),
        "enable_warmup": False,
    }


def test_sync_review_dispatch_filters_before_task_planning(tmp_path: Path) -> None:
    _make_review_repo(tmp_path)
    dispatcher = MultiAgentDispatcher(enable_warmup=False)
    try:
        result = dispatcher.dispatch("review the changeset", **_dispatch_kwargs(tmp_path))
    finally:
        dispatcher.shutdown()

    assert result.success
    details = result.details["review_filter"]
    assert details["retained_paths"] == ["src/keep.py"]
    assert {item["gate"] for item in details["excluded_paths"]} == {
        "user_exclude",
        "deleted",
        "secret_exclude",
    }
    assert details["excluded_paths"][-1]["path"] != ".env"
    assert result.details["review_bundles"] == [["src/keep.py"]]
    report = result.to_markdown()
    assert "Review Filter" in report
    assert "user_exclude" in report
    assert "secret_exclude" in report
    assert ".env" not in report


def test_async_review_dispatch_uses_the_same_filter_chain(tmp_path: Path) -> None:
    _make_review_repo(tmp_path)
    dispatcher = MultiAgentDispatcher(enable_warmup=False)
    try:
        result = asyncio.run(dispatcher.async_dispatch("review the changeset", **_dispatch_kwargs(tmp_path)))
    finally:
        dispatcher.shutdown()

    assert result.success
    details = result.details["review_filter"]
    assert details["retained_paths"] == ["src/keep.py"]
    assert details["gate_counts"]["user_exclude"] == 1
    assert details["gate_counts"]["deleted"] == 1
    assert details["gate_counts"]["secret_exclude"] == 1
    assert result.details["review_bundles"] == [["src/keep.py"]]


def _diff_for_repo() -> str:
    return """diff --git a/src/keep.py b/src/keep.py
--- a/src/keep.py
+++ b/src/keep.py
@@ -1 +1 @@
-print('keep')
+print('updated')
diff --git a/src/deleted.py b/src/deleted.py
--- a/src/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-print('deleted')
"""


def test_sync_and_async_dispatch_accept_the_same_diff_input(tmp_path: Path) -> None:
    _make_review_repo(tmp_path)
    kwargs = {
        "mode": "review",
        "diff": _diff_for_repo(),
        "repo_root": str(tmp_path),
        "enable_warmup": False,
    }
    dispatcher = MultiAgentDispatcher(enable_warmup=False)
    try:
        sync_result = dispatcher.dispatch("review the diff", **kwargs)
        async_result = asyncio.run(dispatcher.async_dispatch("review the diff", **kwargs))
    finally:
        dispatcher.shutdown()

    assert sync_result.success
    assert async_result.success
    assert sync_result.details["review_filter"] == async_result.details["review_filter"]
    assert sync_result.details["review_filter"]["retained_paths"] == ["src/keep.py"]
    assert sync_result.details["review_filter"]["gate_counts"]["deleted"] == 1
    assert sync_result.details["review_bundles"] == async_result.details["review_bundles"]
