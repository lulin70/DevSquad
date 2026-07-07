"""自动 git 操作驱动器。

封装 git 命令，提供安全的自动提交/分支/标签操作。
所有操作经过 SmartConfirmation 审核。
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .smart_confirmation import ConfirmationDecision, ConfirmationVerdict, SmartConfirmation

logger = logging.getLogger(__name__)


@dataclass
class GitResult:
    """git 操作结果。"""

    success: bool
    command: str
    output: str
    error: str = ""
    confirmed: bool = False  # 是否经过人类确认


class GitDriver:
    """自动 git 操作驱动器。

    所有写操作经过 SmartConfirmation 审核，高风险操作需人类确认。

    Usage:
        driver = GitDriver(repo_path="/path/to/repo")
        result = driver.commit("fix: resolve issue", allow_push=False)
    """

    def __init__(
        self,
        repo_path: str | Path = ".",
        confirmer: SmartConfirmation | None = None,
        auto_confirm: bool = False,
    ) -> None:
        self._repo_path = str(repo_path)
        self._confirmer = confirmer or SmartConfirmation()
        self._auto_confirm = auto_confirm  # 调试模式：跳过确认（仅测试用）

    def commit(
        self,
        message: str,
        files: list[str] | None = None,
        allow_push: bool = False,
    ) -> GitResult:
        """提交更改。"""
        op = f"git commit: {message}"
        decision = self._check_permission(op)

        if decision.verdict != ConfirmationVerdict.APPROVE and not self._auto_confirm:
            return GitResult(
                success=False,
                command=op,
                output="",
                error=f"Operation requires confirmation: {decision.reason}",
                confirmed=False,
            )

        # git add
        if files:
            add_cmd = ["git", "add"] + files
            add_result = self._run(add_cmd)
            if not add_result.success:
                return add_result

        # git commit
        commit_cmd = ["git", "commit", "-m", message]
        commit_result = self._run(commit_cmd)
        if not commit_result.success:
            return commit_result

        # git push (optional)
        if allow_push:
            push_result = self._run(["git", "push"])
            if not push_result.success:
                return push_result

        return GitResult(
            success=True,
            command=op,
            output=commit_result.output,
            confirmed=True,
        )

    def create_branch(self, branch_name: str) -> GitResult:
        """创建并切换到新分支。"""
        op = f"git branch: {branch_name}"
        decision = self._check_permission(op)
        if decision.verdict != ConfirmationVerdict.APPROVE and not self._auto_confirm:
            return GitResult(
                success=False,
                command=op,
                output="",
                error=f"Requires confirmation: {decision.reason}",
            )
        return self._run(["git", "checkout", "-b", branch_name])

    def tag(self, tag_name: str, message: str = "") -> GitResult:
        """创建标签。"""
        op = f"git tag: {tag_name}"
        decision = self._check_permission(op)
        if decision.verdict != ConfirmationVerdict.APPROVE and not self._auto_confirm:
            return GitResult(
                success=False,
                command=op,
                output="",
                error=f"Requires confirmation: {decision.reason}",
            )
        cmd = ["git", "tag", tag_name]
        if message:
            cmd = ["git", "tag", "-a", tag_name, "-m", message]
        return self._run(cmd)

    def status(self) -> GitResult:
        """获取仓库状态（只读，无需确认）。"""
        return self._run(["git", "status", "--porcelain"])

    def current_branch(self) -> str | None:
        """获取当前分支名。"""
        result = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if result.success:
            return result.output.strip()
        return None

    def has_uncommitted_changes(self) -> bool:
        """是否有未提交的更改。"""
        result = self.status()
        return result.success and bool(result.output.strip())

    def _check_permission(self, operation: str) -> ConfirmationDecision:
        """检查操作是否需要确认。"""
        return self._confirmer.evaluate(operation)

    def _run(self, cmd: list[str]) -> GitResult:
        """执行 git 命令。"""
        try:
            result = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return GitResult(
                success=result.returncode == 0,
                command=" ".join(cmd),
                output=result.stdout.strip(),
                error=result.stderr.strip() if result.returncode != 0 else "",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return GitResult(
                success=False,
                command=" ".join(cmd),
                output="",
                error=str(e),
            )
