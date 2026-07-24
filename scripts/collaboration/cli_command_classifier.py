#!/usr/bin/env python3
"""
CLI Command Classifier — DevSquad CLI 命令词表分类评估 (ROADMAP P2-UI-1).

来源学习点: pbakaus/impeccable — 23 Commands 词表。impeccable 定义了一套分类
命令词，作为 CLI 交互的统一词汇框架。本模块将 DevSquad 现有 CLI 命令与该词表
进行对齐评估，借鉴分类思路（不直接照搬），为命令命名一致性提供可量化的审计能力。

==============================================================================
评估报告 (Evaluation Report)
==============================================================================

1. DevSquad 现有 CLI 命令清单 (源自 scripts/cli.py 静态分析)
------------------------------------------------------------------------------
通过对 scripts/cli.py 中 ``subparsers.add_parser(...)`` 调用与
scripts/cli_utils.py 中 ``LIFECYCLE_COMMANDS`` 的 AST 解析，枚举出 12 个规范
命令（不含别名）:

| # | 命令       | 别名           | 语义类别   | 对齐 impeccable |
|---|-----------|----------------|-----------|-----------------|
| 1 | init      | setup, i       | 创建类     | ✅ init          |
| 2 | demo      | play, try      | 执行类     | ❌ (建议 run)     |
| 3 | dispatch  | run, d         | 执行类     | ✅ dispatch      |
| 4 | status    | s              | 导航类     | ❌ (建议 show)    |
| 5 | roles     | ls             | 导航类     | ❌ (建议 list)    |
| 6 | lifecycle | lc             | 执行类     | ❌ (建议 run)     |
| 7 | spec      | -              | 创建类     | ❌ (建议 create)  |
| 8 | plan      | -              | 创建类     | ❌ (建议 scaffold)|
| 9 | build     | -              | 创建类     | ❌ (建议 generate)|
|10 | test      | -              | 审查类     | ❌ (建议 audit)   |
|11 | review    | -              | 审查类     | ✅ review         |
|12 | ship      | -              | 执行类     | ❌ (建议 start)   |

2. 与 impeccable 词表的对齐情况
------------------------------------------------------------------------------
- 规范命令总数: 12
- 对齐命令数:   3  (init, dispatch, review)
- 对齐率:       25.0%
- 未对齐命令数: 9

impeccable 原始词表为 23 个分类命令词。本分类器为实现更广覆盖，采用 27 词扩展
同义词集（7 类 × 3~4 词 = 27），见下方 ``COMMAND_CATEGORIES``。对齐判定以命令
是否命中该扩展词表为准。

3. 未对齐命令的改进建议
------------------------------------------------------------------------------
- demo      → 建议增加别名 ``run``（demo 为 DevSquad 专属演示命令）
- status    → 建议增加别名 ``show``
- roles     → 建议增加别名 ``list``
- lifecycle → 元命令（调度子生命周期命令），保留原名，建议文档标注等价 ``run``
- spec      → 建议增加别名 ``create``
- plan      → 建议增加别名 ``scaffold``
- build     → 建议增加别名 ``generate``
- test      → 建议增加别名 ``audit``（impeccable 用 audit 表达测试/检查意图）
- ship      → 建议增加别名 ``start``（启动发布流程）

4. 是否需要重命名现有命令的评估
------------------------------------------------------------------------------
结论: **不建议重命名**现有规范命令，理由如下:

(a) 向后兼容: DevSquad 已发布至 v4.2.1，重命名会破坏现有用户脚本与文档。
(b) 语义清晰: spec/plan/build/test/review/ship 是 SDLC 领域动词，比 impeccable
    的通用词汇（create/scaffold/generate/audit/start）更能表达软件交付阶段意图。
(c) 低成本对齐: 通过 argparse ``aliases=`` 增加 impeccable 同义别名即可达成
    词表对齐，无需改动调度逻辑或 handler 函数。
(d) 别名策略: 建议在 ``subparsers.add_parser("demo", aliases=["run"])`` 等
    位置补齐别名，使 ``devsquad run`` 与 ``devsquad demo`` 等价。注意 dispatch
    已占用 ``run`` 别名，需做冲突消解（demo 建议改用 ``try`` 已有别名）。

综上，P2-UI-1 落地方式为: 保留规范命令 + 增加 impeccable 对齐别名 + 文档标注
映射关系，而非重命名。
==============================================================================

Spec reference: ROADMAP P2-UI-1
"""

from __future__ import annotations

import ast
from pathlib import Path


class CLICommandClassifier:
    """Classify DevSquad CLI commands against the impeccable command vocabulary.

    Provides alignment assessment between DevSquad's current CLI commands
    and the impeccable command classification framework.

    The impeccable framework canonically defines 23 classified command words.
    This classifier expands that to a 27-word synonym set across 7 categories
    for broader coverage when auditing DevSquad's domain-specific verbs.
    """

    #: impeccable 扩展命令词表（7 类，27 词）。
    #: 原始 impeccable 词表为 23 词；本表在每类内补充近义词以覆盖 DevSquad
    #: 领域动词，故总计 27 词。``classify`` 的对齐判定基于此表。
    COMMAND_CATEGORIES: dict[str, list[str]] = {
        "create": ["create", "generate", "init", "scaffold"],
        "review": ["review", "audit", "inspect", "analyze"],
        "navigate": ["list", "show", "find", "search"],
        "configure": ["config", "set", "enable", "disable"],
        "execute": ["run", "dispatch", "execute", "start"],
        "maintain": ["clean", "fix", "update", "upgrade"],
        "stop": ["stop", "cancel", "abort"],
    }

    #: DevSquad CLI 规范命令静态清单（AST 解析失败时的回退来源）。
    #: 源自 scripts/cli.py 的 ``subparsers.add_parser()`` 调用 +
    #: scripts/cli_utils.py 的 ``LIFECYCLE_COMMANDS``。
    DEVSQUAD_CLI_COMMANDS: list[str] = [
        "init",
        "demo",
        "dispatch",
        "status",
        "roles",
        "lifecycle",
        "spec",
        "plan",
        "build",
        "test",
        "review",
        "ship",
    ]

    #: DevSquad 领域命令 → impeccable 同义词的映射（用于未对齐命令的建议）。
    DEVSQUAD_ALIAS_SUGGESTIONS: dict[str, str] = {
        "demo": "run",
        "status": "show",
        "roles": "list",
        "lifecycle": "run",
        "spec": "create",
        "plan": "scaffold",
        "build": "generate",
        "test": "audit",
        "ship": "start",
    }

    #: 自然语言意图关键词 → 命令类别的映射（用于 ``suggest_command``）。
    INTENT_KEYWORDS: dict[str, list[str]] = {
        "create": ["create", "generate", "init", "setup", "new", "make", "scaffold", "spec", "plan", "build"],
        "review": ["review", "audit", "inspect", "analyze", "check", "quality", "examine", "scan", "test", "verify"],
        "navigate": ["list", "show", "find", "search", "lookup", "available", "display", "status", "roles", "view"],
        "configure": ["config", "set", "enable", "disable", "configure", "setting", "preference"],
        "execute": ["run", "dispatch", "execute", "start", "launch", "begin", "trigger", "demo", "ship", "deploy"],
        "maintain": ["clean", "fix", "update", "upgrade", "maintain", "repair", "patch", "refactor"],
        "stop": ["stop", "cancel", "abort", "terminate", "halt", "kill", "end"],
    }

    def classify(self, command: str) -> dict[str, object]:
        """Classify a CLI command into an impeccable category.

        Args:
            command: The CLI command word to classify.

        Returns:
            Dict with keys:
                - command: str — the original command (stripped/lowered for matching)
                - category: str — one of COMMAND_CATEGORIES keys, or "unknown"
                - aligned: bool — True if command is in the impeccable vocabulary
                - suggested_alias: str | None — impeccable synonym if not aligned
        """
        normalized = command.strip().lower()
        for category, words in self.COMMAND_CATEGORIES.items():
            if normalized in words:
                return {
                    "command": normalized,
                    "category": category,
                    "aligned": True,
                    "suggested_alias": None,
                }
        return {
            "command": normalized,
            "category": "unknown",
            "aligned": False,
            "suggested_alias": self._suggest_alias(normalized),
        }

    def audit_cli(self) -> dict[str, object]:
        """Audit all DevSquad CLI commands against the impeccable vocabulary.

        Enumerates DevSquad CLI commands via AST parsing of ``scripts/cli.py``
        (falling back to ``DEVSQUAD_CLI_COMMANDS``), classifies each, and
        produces an alignment report.

        Returns:
            Dict with keys:
                - total_commands: int
                - aligned_count: int
                - aligned_percentage: float — range [0.0, 100.0]
                - by_category: dict[str, list[str]] — commands grouped by category
                  (always includes all 7 impeccable categories plus "unknown")
                - unaligned: list[dict] — commands not in impeccable vocabulary
                - recommendations: list[str]
        """
        commands = self._discover_cli_commands()
        results = [self.classify(c) for c in commands]

        by_category: dict[str, list[str]] = {cat: [] for cat in self.COMMAND_CATEGORIES}
        by_category["unknown"] = []
        for res in results:
            category = str(res["category"])
            by_category.setdefault(category, []).append(str(res["command"]))

        unaligned = [res for res in results if not bool(res["aligned"])]
        aligned_count = len(results) - len(unaligned)
        total = len(results)
        percentage = (aligned_count / total * 100.0) if total else 0.0

        return {
            "total_commands": total,
            "aligned_count": aligned_count,
            "aligned_percentage": round(percentage, 2),
            "by_category": by_category,
            "unaligned": unaligned,
            "recommendations": self._build_recommendations(unaligned),
        }

    def suggest_command(self, intent: str) -> list[str]:
        """Suggest impeccable-aligned commands for a user intent.

        Matches the intent text (case-insensitive, substring match) against
        ``INTENT_KEYWORDS`` and returns the union of command words from every
        matched category, preserving category order then word order.

        Args:
            intent: Natural language intent (e.g., "I want to check code quality").

        Returns:
            List of suggested command words from the impeccable vocabulary.
            Empty list when no keyword matches (unknown intent).
        """
        text = intent.lower()
        matched_categories: list[str] = []
        for category in self.COMMAND_CATEGORIES:
            keywords = self.INTENT_KEYWORDS.get(category, [])
            if any(kw in text for kw in keywords):
                matched_categories.append(category)

        suggestions: list[str] = []
        seen: set[str] = set()
        for category in matched_categories:
            for word in self.COMMAND_CATEGORIES[category]:
                if word not in seen:
                    seen.add(word)
                    suggestions.append(word)
        return suggestions

    # ----------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------

    def _suggest_alias(self, command: str) -> str | None:
        """Return the suggested impeccable synonym for an unaligned command."""
        return self.DEVSQUAD_ALIAS_SUGGESTIONS.get(command)

    def _build_recommendations(self, unaligned: list[dict[str, object]]) -> list[str]:
        """Build human-readable improvement recommendations for unaligned commands."""
        recs: list[str] = []
        for res in unaligned:
            cmd = str(res["command"])
            alias = res.get("suggested_alias")
            if alias:
                recs.append(
                    f"Add impeccable alias '{alias}' for command '{cmd}' to improve vocabulary alignment."
                )
            else:
                recs.append(
                    f"Command '{cmd}' has no direct impeccable synonym; consider documenting its category."
                )
        if recs:
            recs.append(
                "Do NOT rename canonical commands (backward compatibility). "
                "Use argparse aliases to add impeccable-aligned synonyms."
            )
        return recs

    def _discover_cli_commands(self) -> list[str]:
        """Enumerate DevSquad CLI commands by AST-parsing ``scripts/cli.py``.

        Extracts command names from ``subparsers.add_parser("name", ...)`` calls
        and the ``LIFECYCLE_COMMANDS`` list in ``scripts/cli_utils.py``. Falls
        back to ``DEVSQUAD_CLI_COMMANDS`` when parsing fails or yields nothing.
        This avoids importing ``scripts.cli`` (which has module-level side
        effects) while still reflecting the live argparse structure.
        """
        cli_path = Path(__file__).resolve().parent.parent / "cli.py"
        utils_path = Path(__file__).resolve().parent.parent / "cli_utils.py"
        discovered: list[str] = []
        discovered.extend(self._extract_add_parser_commands(cli_path))
        discovered.extend(self._extract_lifecycle_commands(utils_path))
        if not discovered:
            return list(self.DEVSQUAD_CLI_COMMANDS)
        return discovered

    @staticmethod
    def _extract_add_parser_commands(cli_path: Path) -> list[str]:
        """Extract command names from ``add_parser("name", ...)`` calls in cli.py."""
        try:
            tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
        except (OSError, SyntaxError):
            return []
        found: list[str] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr != "add_parser" or not node.args:
                continue
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value not in found
            ):
                found.append(first.value)
        return found

    @staticmethod
    def _extract_lifecycle_commands(utils_path: Path) -> list[str]:
        """Extract command names from the ``LIFECYCLE_COMMANDS`` list in cli_utils.py."""
        try:
            utils_tree = ast.parse(
                utils_path.read_text(encoding="utf-8"), filename=str(utils_path)
            )
        except (OSError, SyntaxError):
            return []
        found: list[str] = []
        for node in ast.walk(utils_tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(t, ast.Name) and t.id == "LIFECYCLE_COMMANDS" for t in node.targets
            ):
                continue
            if not isinstance(node.value, ast.List):
                continue
            for elt in node.value.elts:
                if (
                    isinstance(elt, ast.Constant)
                    and isinstance(elt.value, str)
                    and elt.value not in found
                ):
                    found.append(elt.value)
        return found
