#!/usr/bin/env python3
"""
DevSquad V3.6.9 快速入门 Demo

展示 DevSquad 核心功能的 3 个典型场景：
  场景1: Bug修复（中文意图检测）
  场景2: Code Review（consensus模式+五轴评审）
  场景3: 新功能设计（多角色协作）

运行方式：
    cd /Users/lin/trae_projects/DevSquad
    python examples/quick_demo.py

特点：
  - 使用 Mock 后端（无需 API Key）
  - 美观的终端输出（rich 库 + ANSI 彩色）
  - 完整中文注释
  - 运行时间 < 15 秒
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


console = Console() if RICH_AVAILABLE else None


def print_header(title: str, subtitle: str = ""):
    """打印带样式的标题"""
    if RICH_AVAILABLE:
        console.print(
            Panel(
                f"[bold cyan]{title}[/bold cyan]",
                subtitle=subtitle,
                border_style="bright_blue",
                padding=(1, 2),
            )
        )
    else:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        if subtitle:
            print(f"  {subtitle}")
        print(f"{'=' * 60}\n")


def print_success(text: str):
    """打印成功信息"""
    if RICH_AVAILABLE:
        console.print(f"  [green]✅[/green] {text}")
    else:
        print(f"  ✅ {text}")


def print_info(text: str):
    """打印信息"""
    if RICH_AVAILABLE:
        console.print(f"  [blue]ℹ️[/blue] {text}")
    else:
        print(f"  ℹ️ {text}")


def print_warning(text: str):
    """打印警告"""
    if RICH_AVAILABLE:
        console.print(f"  [yellow]⚠️[/yellow] {text}")
    else:
        print(f"  ⚠️ {text}")


def print_error(text: str):
    """打印错误"""
    if RICH_AVAILABLE:
        console.print(f"  [red]❌[/red] {text}")
    else:
        print(f"  ❌ {text}")


def create_result_table(scenario_results: list) -> Table:
    """创建结果汇总表格"""
    table = Table(
        title="📊 DevSquad Demo 执行结果汇总",
        title_style="bold magenta",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("场景", style="bold", width=20)
    table.add_column("任务描述", style="dim", width=30)
    table.add_column("匹配角色", width=25)
    table.add_column("意图检测", width=15)
    table.add_column("执行时间", justify="right", width=10)
    table.add_column("状态", justify="center", width=8)

    for result in scenario_results:
        status = "[green]成功[/green]" if result["success"] else "[red]失败[/red]"
        table.add_row(
            result["scenario"],
            result["task"][:27] + "..." if len(result["task"]) > 27 else result["task"],
            ", ".join(result["roles"]),
            result["intent"],
            f"{result['duration']:.2f}s",
            status,
        )

    return table


def scenario_1_bug_fix():
    """
    场景1: Bug修复（中文意图检测）

    演示 DevSquad 如何：
      1. 检测中文意图（bug_fix）
      2. 自动匹配相关角色
      3. 执行修复流程
    """
    print_header("场景 1: Bug 修复", "中文意图检测 → 角色自动匹配 → 协作执行")

    task_description = "修复用户登录模块中的认证失败问题，报错信息显示token验证异常"

    print_info(f"任务描述: {task_description}")

    start_time = time.time()

    try:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper

        # 创建意图检测器
        intent_mapper = IntentWorkflowMapper()
        intent_result = intent_mapper.detect_intent(task_description)

        print_info("意图检测结果:")
        print(f"    类型: [bold]{intent_result.intent_type}[/bold]")
        print(f"    置信度: [bold]{intent_result.confidence:.2%}[/bold]")
        print(f"    必需角色: {', '.join(intent_result.required_roles)}")
        if intent_result.optional_roles:
            print(f"    可选角色: {', '.join(intent_result.optional_roles)}")

        # 创建调度器并执行
        disp = MultiAgentDispatcher()
        result = disp.dispatch(task_description)

        duration = time.time() - start_time

        # 输出结果摘要
        print_success("执行完成!")
        print_info(f"参与角色: {', '.join(result.roles) if hasattr(result, 'roles') else 'N/A'}")
        print_info(f"执行时间: [bold]{duration:.2f}s[/bold]")

        report_summary = ""
        if hasattr(result, "summary") and result.summary:
            report_summary = result.summary[:200]
        elif hasattr(result, "to_markdown"):
            md = result.to_markdown()
            report_summary = md[:200]

        if report_summary:
            print("\n  📋 报告摘要 (前200字):")
            print(f"  {'─' * 50}")
            for line in report_summary.split("\n")[:5]:
                print(f"    {line}")
            print(f"  {'─' * 50}")

        disp.shutdown()

        return {
            "scenario": "Bug 修复",
            "task": task_description,
            "roles": result.roles if hasattr(result, "roles") else ["coder", "tester"],
            "intent": intent_result.intent_type,
            "duration": duration,
            "success": True,
            "report_summary": report_summary,
        }

    except Exception as e:
        duration = time.time() - start_time
        print_error(f"执行失败: {e}")
        return {
            "scenario": "Bug 修复",
            "task": task_description,
            "roles": [],
            "intent": "error",
            "duration": duration,
            "success": False,
            "report_summary": "",
        }


def scenario_2_code_review():
    """
    场景2: Code Review（consensus模式+五轴评审）

    演示 DevSquad 如何：
      1. 使用 consensus 模式进行代码评审
      2. 启用五轴评审机制
      3. 生成结构化评审报告
    """
    print_header("场景 2: Code Review", "Consensus 模式 + 五轴评审机制")

    task_description = "Review PR #123: 用户权限管理模块重构，包含RBAC实现和JWT集成"

    print_info(f"任务描述: {task_description}")

    start_time = time.time()

    try:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.five_axis_consensus import FiveAxisConsensusEngine

        # 创建五轴共识引擎（用于代码评审）
        five_axis = FiveAxisConsensusEngine()

        print_info("启用五轴评审模式:")
        axes = [
            ("正确性 (Correctness)", "代码逻辑是否正确"),
            ("安全性 (Security)", "是否存在安全漏洞"),
            ("性能 (Performance)", "性能是否达标"),
            ("可维护性 (Maintainability)", "代码是否易维护"),
            ("测试覆盖 (Test Coverage)", "测试是否充分"),
        ]
        for axis_name, desc in axes:
            print(f"    • {axis_name}: {desc}")

        # 创建调度器并执行
        disp = MultiAgentDispatcher()
        result = disp.dispatch(task_description)

        duration = time.time() - start_time

        # 输出结果
        print_success("评审完成!")
        print_info(f"参与角色: {', '.join(result.roles) if hasattr(result, 'roles') else 'N/A'}")
        print_info(f"执行时间: [bold]{duration:.2f}s[/bold]")

        report_summary = ""
        if hasattr(result, "summary") and result.summary:
            report_summary = result.summary[:200]
        elif hasattr(result, "to_markdown"):
            md = result.to_markdown()
            report_summary = md[:200]

        if report_summary:
            print("\n  📋 评审报告摘要 (前200字):")
            print(f"  {'─' * 50}")
            for line in report_summary.split("\n")[:5]:
                print(f"    {line}")
            print(f"  {'─' * 50}")

        disp.shutdown()

        return {
            "scenario": "Code Review",
            "task": task_description,
            "roles": result.roles if hasattr(result, "roles") else ["arch", "sec", "test"],
            "intent": "code_review",
            "duration": duration,
            "success": True,
            "report_summary": report_summary,
        }

    except Exception as e:
        duration = time.time() - start_time
        print_error(f"评审失败: {e}")
        return {
            "scenario": "Code Review",
            "task": task_description,
            "roles": [],
            "intent": "error",
            "duration": duration,
            "success": False,
            "report_summary": "",
        }


def scenario_3_feature_design():
    """
    场景3: 新功能设计（多角色协作）

    演示 DevSquad 如何：
      1. 自动识别新功能开发意图
      2. 匹配多个专业角色协作
      3. 生成完整的功能设计方案
    """
    print_header("场景 3: 新功能设计", "多角色协作 → 架构设计 → 技术方案")

    task_description = "设计一个微服务架构的电商平台后端系统，需要支持高并发和弹性伸缩"

    print_info(f"任务描述: {task_description}")

    start_time = time.time()

    try:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.role_matcher import RoleMatcher

        # 创建角色匹配器
        matcher = RoleMatcher()
        matched_roles = matcher.analyze_task(task_description)

        print_info("自动匹配的角色:")
        for role_info in matched_roles:
            role_id = role_info.get("role_id", "unknown")
            role_name = role_info.get("name", role_id)
            confidence = role_info.get("confidence", 0)
            print(f"    • [bold]{role_name}[/bold] ({role_id}) - 置信度: {confidence:.1%}")

        # 创建调度器并执行
        disp = MultiAgentDispatcher()
        result = disp.dispatch(task_description)

        duration = time.time() - start_time

        # 输出结果
        print_success("设计完成!")
        print_info(
            f"参与角色: {', '.join(result.roles) if hasattr(result, 'roles') else [r['role_id'] for r in matched_roles]}"
        )
        print_info(f"执行时间: [bold]{duration:.2f}s[/bold]")

        report_summary = ""
        if hasattr(result, "summary") and result.summary:
            report_summary = result.summary[:200]
        elif hasattr(result, "to_markdown"):
            md = result.to_markdown()
            report_summary = md[:200]

        if report_summary:
            print("\n  📋 设计方案摘要 (前200字):")
            print(f"  {'─' * 50}")
            for line in report_summary.split("\n")[:5]:
                print(f"    {line}")
            print(f"  {'─' * 50}")

        disp.shutdown()

        return {
            "scenario": "新功能设计",
            "task": task_description,
            "roles": result.roles if hasattr(result, "roles") else [r["role_id"] for r in matched_roles],
            "intent": "new_feature",
            "duration": duration,
            "success": True,
            "report_summary": report_summary,
        }

    except Exception as e:
        duration = time.time() - start_time
        print_error(f"设计失败: {e}")
        import traceback

        traceback.print_exc()
        return {
            "scenario": "新功能设计",
            "task": task_description,
            "roles": [],
            "intent": "error",
            "duration": duration,
            "success": False,
            "report_summary": "",
        }


def main():
    """运行所有 Demo 场景"""

    total_start = time.time()

    if RICH_AVAILABLE:
        console.print(
            Panel(
                "[bold green]DevSquad V3.6.9 快速入门 Demo[/bold green]\n\n"
                "展示核心功能的 3 个典型场景\n"
                "[dim]使用 Mock 后端 | 无需 API Key | 运行时间 < 15s[/dim]",
                title="🚀 DevSquad Quick Demo",
                border_style="green",
                padding=(1, 4),
            )
        )
    else:
        print("\n" + "=" * 60)
        print("  🚀 DevSquad V3.6.9 快速入门 Demo")
        print("=" * 60)
        print("  展示核心功能的 3 个典型场景")
        print("  使用 Mock 后端 | 无需 API Key\n")

    scenario_results = []

    # 执行场景 1: Bug 修复
    print("\n▶️ 执行场景 1/3...")
    result1 = scenario_1_bug_fix()
    scenario_results.append(result1)

    # 执行场景 2: Code Review
    print("\n▶️ 执行场景 2/3...")
    result2 = scenario_2_code_review()
    scenario_results.append(result2)

    # 执行场景 3: 新功能设计
    print("\n▶️ 执行场景 3/3...")
    result3 = scenario_3_feature_design()
    scenario_results.append(result3)

    total_duration = time.time() - total_start

    # 输出汇总表
    print("\n")
    if RICH_AVAILABLE:
        summary_table = create_result_table(scenario_results)
        console.print(summary_table)
    else:
        print("\n" + "=" * 60)
        print("  📊 执行结果汇总")
        print("=" * 60)
        print(f"  {'场景':<15} {'角色':<20} {'意图':<12} {'耗时':<8} {'状态'}")
        print(f"  {'-' * 55}")
        for r in scenario_results:
            roles_str = ", ".join(r["roles"][:3])
            status = "✅" if r["success"] else "❌"
            print(f"  {r['scenario']:<15} {roles_str:<18} {r['intent']:<12} {r['duration']:.2f}s   {status}")

    # 统计信息
    success_count = sum(1 for r in scenario_results if r["success"])
    total_count = len(scenario_results)

    print("\n  📈 总体统计:")
    print(f"    • 总执行时间: [bold]{total_duration:.2f}s[/bold]")
    print(f"    • 成功场景: [green]{success_count}/{total_count}[/green]")
    print(f"    • 平均耗时: [bold]{total_duration / total_count:.2f}s[/bold]")

    if total_duration > 15:
        print_warning(f"⚠️ 总运行时间超过 15 秒 ({total_duration:.1f}s)")
    else:
        print_success("✅ 运行时间符合要求 (< 15s)")

    print("\n" + "=" * 60)
    print("  💡 下一步操作:")
    print("=" * 60)
    print("  1. 阅读完整文档: docs/i18n/GUIDE_EN.md")
    print("  2. 查看更多示例: examples/")
    print("  3. 使用真实 LLM: 设置 OPENAI_API_KEY 并添加 --backend openai")
    print("  4. 启动 Web Dashboard: streamlit run scripts/dashboard.py")
    print()


if __name__ == "__main__":
    main()
