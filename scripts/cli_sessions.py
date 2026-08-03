#!/usr/bin/env python3
"""
DevSquad CLI sessions 子命令模块 (V4.5.0 SessionResume — PRD §10.1.2).

本模块提供 dispatch 会话恢复与查询能力，复用 CheckpointManager 现有的
checkpoint 存储层（无新增存储）：

- ``devsquad sessions list``               列出最近 dispatch 会话及状态
- ``devsquad sessions show <session-id>``  查看某个会话的 checkpoint 详情
- ``devsquad dispatch --resume <id>``      恢复被中断的 dispatch（本模块提供
  ``load_resumable_task`` 辅助函数，由 ``cli_dispatch.cmd_dispatch`` 调用）

安全 (Security A6)：所有展示给用户的任务描述文本均经过
``OutputValidator.redact()`` 过滤，API key / token 等敏感信息不会泄露到 CLI
输出。CheckpointManager 内部已做 redact，本模块仅负责渲染。

容错原则：checkpoint 缺失或损坏时返回友好错误信息 + 非零退出码，绝不崩溃。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from scripts.collaboration.checkpoint_manager import CheckpointManager


def _get_manager(persist_dir: str | None = None) -> CheckpointManager:
    """Construct a CheckpointManager rooted at ``persist_dir`` (or CWD)."""
    return CheckpointManager(storage_path=persist_dir or ".")


def cmd_sessions(args: argparse.Namespace) -> int:
    """Execute the ``sessions`` subcommand: ``list`` or ``show``.

    Args:
        args: Parsed argparse namespace. Expected attributes:
            ``sessions_command`` (``"list"`` / ``"show"``),
            ``session_id`` (for ``show``), ``limit`` (for ``list``),
            ``format`` (``"text"`` / ``"json"``), optional ``persist_dir``.

    Returns:
        0 on success, 1 when the requested session is not found or on error.
    """
    sub = getattr(args, "sessions_command", "list")
    fmt = getattr(args, "format", "text")
    persist_dir = getattr(args, "persist_dir", None)
    manager = _get_manager(persist_dir)

    if sub == "list":
        limit = getattr(args, "limit", 20)
        sessions = manager.list_sessions(limit=limit)
        if fmt == "json":
            print(json.dumps(sessions, ensure_ascii=False, indent=2))
        else:
            if not sessions:
                print("No dispatch sessions found.")
            else:
                print(f"{'SESSION ID':<20} {'STATUS':<14} {'CREATED':<26} SUMMARY")
                print("-" * 90)
                for s in sessions:
                    print(
                        f"{s['session_id']:<20} {s['status']:<14} "
                        f"{s['created_at']:<26} {s['task_summary']}"
                    )
        return 0

    if sub == "show":
        session_id = getattr(args, "session_id", None)
        if not session_id:
            print("Error: session-id required. Usage: devsquad sessions show <session-id>", file=sys.stderr)
            return 1
        status = manager.get_session_status(session_id)
        if not status:
            print(
                f"Error: session '{session_id}' not found or checkpoint corrupted.",
                file=sys.stderr,
            )
            return 1
        if fmt == "json":
            print(json.dumps(status, ensure_ascii=False, indent=2))
        else:
            print(f"Session: {status['session_id']}")
            print(f"  Status:          {status['status']} ({status['checkpoint_status']})")
            print(f"  Task ID:         {status['task_id']}")
            print(f"  Step:            {status['step_name']}")
            print(f"  Summary:         {status['task_summary']}")
            print(f"  Progress:        {status['progress_percentage']:.1%}")
            print(f"  Agent:           {status['agent_id']}")
            print(f"  Created:         {status['created_at']}")
            print(f"  Updated:         {status['updated_at']}")
            print(f"  Completed steps: {status['completed_steps']}")
            print(f"  Remaining steps: {status['remaining_steps']}")
        return 0

    print(f"Error: unknown sessions subcommand '{sub}'", file=sys.stderr)
    return 1


def load_resumable_task(session_id: str, persist_dir: str | None = None) -> tuple[str | None, dict[str, Any] | None, str | None]:
    """Load a checkpoint and reconstruct the task for ``dispatch --resume``.

    Used by :func:`scripts.cli_dispatch.cmd_dispatch` when ``--resume`` is set.
    Returns ``(task, status, error)``:

    - On success: ``task`` is the reconstructed task string (from
      ``context_snapshot.task`` / ``task_description``), ``status`` is the
      detailed session status dict (for logging), ``error`` is ``None``.
    - On failure (missing / corrupted / no task text): ``task`` and ``status``
      are ``None`` and ``error`` is a human-readable message.

    Graceful: never raises — callers receive the error string to print.
    """
    try:
        manager = _get_manager(persist_dir)
        status = manager.get_session_status(session_id)
        if not status:
            return None, None, f"session '{session_id}' not found or checkpoint corrupted"
        # Reconstruct task text from the raw checkpoint (status dict already
        # redacts; we need the original task to re-dispatch). Load the raw
        # checkpoint to access context_snapshot.
        cp = manager.load_checkpoint(session_id)
        if cp is None:
            return None, None, f"session '{session_id}' checkpoint could not be loaded"
        ctx = cp.context_snapshot or {}
        task_text = ctx.get("task") or ctx.get("task_description")
        if not task_text:
            return None, status, (
                f"session '{session_id}' has no task description in its checkpoint "
                "(cannot resume — original task text not persisted)"
            )
        return str(task_text), status, None
    except Exception as e:  # noqa: BLE001 — graceful: never crash CLI
        return None, None, f"failed to resume session '{session_id}': {e}"
