#!/usr/bin/env python3
"""
DevSquad CLI dispatch 子命令模块。

本模块包含与任务派发相关的子命令处理函数：
- cmd_dispatch: 执行多智能体任务派发
- cmd_status: 输出系统状态 JSON
- cmd_roles: 列出可用角色
- cmd_demo: 演示 DevSquad 能力（mock 模式，无需 API key）
"""

import json
import sys

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.input_validator import InputValidator
from scripts.collaboration.models import ROLE_REGISTRY, resolve_role_id
from scripts.collaboration.multi_host_adapter import HostType, MultiHostAdapter
from scripts.collaboration.permission_guard import PermissionLevel

from .cli_utils import (
    MODES,
    ROLES,
    VERSION,
    _create_backend,
)


def cmd_demo(args):
    """
    Demo command — show DevSquad capabilities in mock mode (no API key needed).

    Scenarios:
      intent     - Intent detection & role auto-matching
      security   - Security scanning with permission checks
      dispatch   - Dispatch dry-run simulation
      all        - Run all scenarios (default)
    """
    import time as _time

    scenario = getattr(args, "scenario", "all")

    print("\n" + "=" * 60)
    print("  🚀 DevSquad V3.7.0 Quick Demo")
    print("=" * 60)
    print("  Mode: Mock (no API key required)\n")

    results = []

    if scenario in ("all", "intent"):
        print("▶️ Scenario 1: Intent Detection")
        print("-" * 40)
        start = _time.time()
        try:
            from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper

            mapper = IntentWorkflowMapper()
            task = "修复用户登录模块中的认证失败问题，报错信息显示token验证异常"
            result = mapper.detect_intent(task)

            print(f"  Task: {task}")
            print(f"  Intent: {result.intent_type}")
            print(f"  Confidence: {result.confidence:.1%}")
            print(f"  Required roles: {', '.join(result.required_roles)}")
            if result.optional_roles:
                print(f"  Optional roles: {', '.join(result.optional_roles)}")
            print(f"  ✅ Completed in {_time.time() - start:.2f}s\n")
            results.append({"scenario": "Intent Detection", "success": True, "duration": _time.time() - start})
        except (RuntimeError, ValueError, ImportError, AttributeError) as e:
            print(f"  ❌ Failed: {e}\n")
            results.append({"scenario": "Intent Detection", "success": False, "duration": _time.time() - start})

    if scenario in ("all", "security"):
        print("▶️ Scenario 2: Security Scan")
        print("-" * 40)
        start = _time.time()
        try:
            from scripts.collaboration.input_validator import InputValidator

            validator = InputValidator()
            test_inputs = [
                ("DROP TABLE users;", "SQL Injection"),
                ("<script>alert('xss')</script>", "XSS"),
                ("rm -rf / && format C:", "Command Injection"),
                ("$(cat /etc/passwd)", "OS Command Injection"),
            ]
            for inp, label in test_inputs:
                result = validator.validate_task(inp)
                status = (
                    "🚫 BLOCKED" if not result.valid else ("⚠️ WARNING" if result.sanitized_input != inp else "✅ OK")
                )
                print(f"  [{status}] {label}: {inp[:40]}")
            print(f"  ✅ Completed in {_time.time() - start:.2f}s\n")
            results.append({"scenario": "Security Scan", "success": True, "duration": _time.time() - start})
        except (RuntimeError, ValueError, ImportError, AttributeError) as e:
            print(f"  ❌ Failed: {e}\n")
            results.append({"scenario": "Security Scan", "success": False, "duration": _time.time() - start})

    if scenario in ("all", "dispatch"):
        print("▶️ Scenario 3: Dispatch Dry-Run")
        print("-" * 40)
        start = _time.time()
        try:
            disp = MultiAgentDispatcher(enable_warmup=False)
            result = disp.dispatch(
                "设计一个微服务架构的用户认证系统",
                dry_run=True,
            )
            print("  Task: 设计一个微服务架构的用户认证系统")
            print("  Mode: Dry-run (simulation)")
            if hasattr(result, "matched_roles"):
                print(f"  Matched roles: {', '.join(result.matched_roles)}")
            if hasattr(result, "summary"):
                print(f"  Summary: {result.summary[:100]}...")
            print(f"  ✅ Completed in {_time.time() - start:.2f}s\n")
            disp.shutdown()
            results.append({"scenario": "Dispatch Dry-Run", "success": True, "duration": _time.time() - start})
        except (RuntimeError, ValueError, ImportError, ConnectionError) as e:
            print(f"  ❌ Failed: {e}\n")
            results.append({"scenario": "Dispatch Dry-Run", "success": False, "duration": _time.time() - start})

    # Summary
    print("=" * 60)
    print("  📊 Demo Summary")
    print("=" * 60)
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["duration"] for r in results)
    print(f"  Scenarios run: {len(results)}")
    print(f"  Successful: {success_count}/{len(results)}")
    print(f"  Total time: {total_time:.2f}s")
    print()
    print("💡 Next steps:")
    print("  devsquad init          # Interactive setup")
    print('  devsquad dispatch -t "your task"')
    print("  devsquad --help        # All commands\n")

    return 0 if all(r["success"] for r in results) else 1


def cmd_dispatch(args):
    """Execute the ``dispatch`` subcommand: validate and run a task.

    Args:
        args: Parsed argparse namespace. Expected attributes include
            ``task``/``task_positional``, optional ``roles``, ``mode``,
            ``format``, ``backend``, and ``quick``.

    Returns:
        0 on success, 1 on validation or dispatch failure.
    """
    task_text = args.task if args.task is not None else args.task_positional
    if not task_text:
        import logging

        logging.getLogger(__name__).error(
            'Error: Task description required. Usage: devsquad dispatch "your task" or devsquad dispatch -t "your task"'
        )
        return 1

    validator = InputValidator()

    task_result = validator.validate_task(task_text)
    if not task_result.valid:
        import logging

        logging.getLogger(__name__).error("Error: Invalid task - %s", task_result.reason)
        return 1

    task = task_result.sanitized_input or task_text

    # 验证角色列表（如果提供）
    if args.roles:
        args.roles = [resolve_role_id(r) for r in args.roles]
        roles_result = validator.validate_roles(args.roles)
        if not roles_result.valid:
            print(f"Error: Invalid roles - {roles_result.reason}", file=sys.stderr)
            return 1

    # 检查可疑模式（警告但不阻止）
    warnings = validator.check_suspicious_patterns(task)
    if warnings:
        print(f"Warning: Suspicious patterns detected: {', '.join(warnings)}", file=sys.stderr)
        print("Proceeding anyway...", file=sys.stderr)

    kwargs = {
        "persist_dir": args.persist_dir,
        "enable_warmup": not args.no_warmup,
        "enable_compression": not args.no_compression,
        "enable_permission": not args.skip_permission,
        "enable_memory": not args.no_memory,
        "enable_skillify": not args.no_skillify,
        "stream": getattr(args, "stream", False),
        "lang": getattr(args, "lang", "auto"),
    }
    if args.permission_level:
        kwargs["permission_level"] = PermissionLevel(args.permission_level.upper())

    backend = _create_backend(args.backend, args.base_url, args.model)
    if backend is None and args.backend not in ("mock", None):
        print(f"\nError: Failed to create '{args.backend}' backend.", file=sys.stderr)
        print("Falling back to mock mode is NOT allowed when a backend is explicitly specified.", file=sys.stderr)
        print("Please check your API key and configuration.", file=sys.stderr)
        return 1
    if backend is not None:
        kwargs["llm_backend"] = backend

    disp = MultiAgentDispatcher(**kwargs)

    # V3.9.1: Wrap with MultiHostAdapter when --host is specified
    host_type_str = getattr(args, "host", None)
    adapter = None
    if host_type_str:
        host_map = {
            "claude-code": HostType.CLAUDE_CODE,
            "cursor": HostType.CURSOR,
            "codex": HostType.CODEX,
            "cline": HostType.CLINE,
            "trae": HostType.TRAE,
            "generic": HostType.GENERIC,
        }
        adapter = MultiHostAdapter(
            host_type=host_map[host_type_str],
            dispatcher=disp,
        )

    try:
        if args.quick:
            result = disp.quick_dispatch(
                task,  # 使用验证后的任务
                output_format=args.format if args.format in ("structured", "compact", "detailed") else "structured",
                include_action_items=args.action_items,
                include_timing=args.timing,
            )
        elif adapter is not None:
            host_result = adapter.dispatch(
                task,
                roles=args.roles,
                mode=args.mode,
                dry_run=args.dry_run,
            )
            # MultiHostAdapter returns a dict; print the host-formatted report
            if args.format == "json":
                print(json.dumps(host_result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"[Host: {host_result['host']}]")
                print(host_result["report"])
            return 0 if host_result["success"] else 1
        else:
            result = disp.dispatch(
                task,  # 使用验证后的任务
                roles=args.roles,
                mode=args.mode,
                dry_run=args.dry_run,
            )

        if args.format == "json":
            output = {
                "success": result.success,
                "matched_roles": getattr(result, "matched_roles", None),
                "summary": result.summary,
                "report": result.to_markdown(),
                "timing": getattr(result, "timing", None),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        elif args.format == "compact":
            print(result.summary)
        else:
            print(result.to_markdown())

        return 0 if result.success else 1
    finally:
        disp.shutdown()


def cmd_status(args):
    """Execute the ``status`` subcommand: print system status as JSON.

    Args:
        args: Parsed argparse namespace (unused but required by CLI
            signature).

    Returns:
        0 on success.
    """
    disp = MultiAgentDispatcher(enable_warmup=False)
    try:
        stats = disp.get_status() if hasattr(disp, "get_status") else {}
        status = {
            "name": "DevSquad",
            "version": VERSION,
            "status": "ready",
            "available_roles": ROLES,
            "available_modes": MODES,
            "modules_loaded": list(stats.keys()) if stats else "unknown",
        }
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    finally:
        disp.shutdown()


def cmd_roles(args):
    """Execute the ``roles`` subcommand: list available roles.

    Args:
        args: Parsed argparse namespace. Uses ``args.format`` to select
            ``"json"`` or plain-text output.

    Returns:
        0 on success.
    """
    role_descriptions = {}
    for rid, rdef in ROLE_REGISTRY.items():
        display_id = rdef.aliases[0] if rdef.aliases else rid
        status_tag = " [planned]" if rdef.status == "planned" else ""
        role_descriptions[display_id] = f"{rdef.description}{status_tag}"
    if args.format == "json":
        print(json.dumps(role_descriptions, ensure_ascii=False, indent=2))
    else:
        for role, desc in role_descriptions.items():
            print(f"  {role:<12} — {desc}")
    return 0
