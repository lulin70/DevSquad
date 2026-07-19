#!/usr/bin/env python3
"""
DevSquad CLI lifecycle 子命令模块。

本模块包含生命周期子命令（spec / plan / build / test / review / ship）的
处理函数 cmd_lifecycle，作为 11-phase 生命周期协议的 View Layer。
"""

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.input_validator import InputValidator
from scripts.collaboration.lifecycle_protocol import LifecycleProtocol
from scripts.collaboration.lifecycle_templates import ViewMapping

from .cli_utils import LIFECYCLE_COMMANDS, LIFECYCLE_PRESETS, LifecyclePreset, _create_backend


def _render_lifecycle_visual(
    command: str,
    mapping: ViewMapping | None,
    preset: LifecyclePreset,
    task: str,
    use_verbose: bool,
    get_shared_protocol: Callable[[], LifecycleProtocol],
) -> None:
    """Render lifecycle command output using the enhanced visual formatter."""
    # Use enhanced visual output
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "cli"))

    try:
        from cli_visual import Colors, Icons, get_visual_formatter

        vf = get_visual_formatter(use_color=True)

        vf.print_lifecycle_header(command, mapping, preset)

        # Show resolved phases with details
        protocol = get_shared_protocol()
        if mapping:
            phases = protocol.resolve_command_to_phases(command)
            if phases:
                vf.print_phase_list(phases)

                # Show progress overview
                completed_phases = getattr(protocol, "_completed_phases", None) or []
                completed_count = len([p for p in phases if p.phase_id in completed_phases])
                vf.print_progress_overview(completed_count, len(phases), f"Command '{command}' Coverage")

        # Show gate status
        gate_name = preset.get("gate", "Unknown")
        vf.print_gate_status(None, gate_name)

        # Verbose mode: show additional info
        if use_verbose:
            status = protocol.get_status()
            vf.print_status_summary(status)

            # Show all available phases info
            all_phases = protocol.get_all_phases()
            vf.print_info_box(
                "All Available Phases",
                [f"{p.phase_id}: {p.name} ({p.role_id})" for p in all_phases[:8]],
                icon="📋",
                color=Colors.BLUE,
            )

        # Print action prompt
        vf.print_info_box(
            "Ready to Execute",
            [
                f"Task: {task[:60]}{'...' if len(task) > 60 else ''}",
                f"Command: {command.upper()}",
                "Next step: Run dispatch or view examples",
            ],
            icon=Icons.ROCKET,
            color=Colors.GREEN,
        )

        vf.print_footer()

    except ImportError as ve:
        print(f"\n⚠️  Visual module not available: {ve}")
        print("Falling back to standard output...\n")


def _render_lifecycle_verbose(
    command: str,
    mapping: ViewMapping | None,
    preset: LifecyclePreset,
    get_shared_protocol: Callable[[], LifecycleProtocol],
) -> None:
    """Render lifecycle command output in verbose text mode (no colors but detailed)."""
    print(f"\n{'=' * 60}")
    print("🔄 DevSquad Lifecycle [Verbose Mode]")
    print(f"{'=' * 60}")
    print(f"📌 Command: {command.upper()}")
    if mapping:
        print(f"📋 Maps to Phases: {', '.join(mapping.phases)}")
        print("🎯 Mode: SHORTCUT (simplified view of 11-phase lifecycle)")

        # Show phase details
        protocol = get_shared_protocol()
        phases = protocol.resolve_command_to_phases(command)
        if phases:
            print("\n📝 Phase Details:")
            for p in phases:
                print(f"   • {p.phase_id}: {p.name}")
                print(f"     Role: {p.role_id}")
                if p.dependencies:
                    print(f"     Dependencies: {', '.join(p.dependencies)}")

    print(f"\n📝 Description: {preset['description']}")
    print(f"👥 Roles: {', '.join(preset['required_roles'])}")
    print(f"⚙️  Mode: {preset['mode']}")
    print(f"🚧 Gate: {preset['gate']}")
    print(f"\n{preset['pre_dispatch_message']}\n")
    print(f"{'=' * 60}\n")


def _render_lifecycle_simple(
    command: str,
    mapping: ViewMapping | None,
    preset: LifecyclePreset,
) -> None:
    """Render lifecycle command output in the original simple backward-compatible mode."""
    print(f"\n{'=' * 60}")
    print("🔄 DevSquad Lifecycle [View Layer Mode]")
    print(f"{'=' * 60}")
    print(f"📌 Command: {command.upper()}")
    if mapping:
        print(f"📋 Maps to Phases: {', '.join(mapping.phases)}")
        print("🎯 Mode: SHORTCUT (simplified view of 11-phase lifecycle)")
    print(f"📝 Description: {preset['description']}")
    print(f"👥 Roles: {', '.join(preset['required_roles'])}")
    print(f"🚧 Gate: {preset['gate']}")
    print(f"\n{preset['pre_dispatch_message']}\n")
    print("💡 Tip: Use --visual for enhanced output, --verbose for details\n")


def _render_lifecycle_error(
    command: str,
    preset: LifecyclePreset,
    error: BaseException,
) -> None:
    """Render fallback output when view mapping info is unavailable."""
    print(f"\n{'=' * 60}")
    print(f"🔄 DevSquad Lifecycle: {command.upper()}")
    print(f"{'=' * 60}")
    print(f"📌 Description: {preset['description']}")
    print(f"👥 Roles: {', '.join(preset['required_roles'])}")
    print(f"(View mapping info unavailable: {error})\n")


def _build_lifecycle_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    """Build MultiAgentDispatcher kwargs for a lifecycle command from parsed args."""
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

    backend = _create_backend(args.backend, args.base_url, args.model)
    if backend is not None:
        kwargs["llm_backend"] = backend

    return kwargs


def _print_lifecycle_result(
    args: argparse.Namespace,
    command: str,
    preset: LifecyclePreset,
    result: DispatchResult,
) -> None:
    """Print lifecycle dispatch result according to args.format."""
    if args.format == "json":
        output = {
            "lifecycle_command": command,
            "gate": preset["gate"],
            "success": result.success,
            "matched_roles": getattr(result, "matched_roles", None),
            "summary": result.summary,
            "report": result.to_markdown(),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.format == "compact":
        print(result.summary)
    else:
        print(result.to_markdown())


def cmd_lifecycle(args: argparse.Namespace) -> int:
    """Handle lifecycle commands (spec/plan/build/test/review/ship) as View Layer over 11-phase lifecycle."""
    command = args.lifecycle_command
    preset = LIFECYCLE_PRESETS.get(command)

    if not preset:
        print(f"Error: Unknown lifecycle command '{command}'", file=sys.stderr)
        print(f"Available: {', '.join(LIFECYCLE_COMMANDS)}", file=sys.stderr)
        return 1

    task_text = args.task if args.task is not None else args.task_positional
    if not task_text:
        print(f"Error: Task description required for '{command}' command.", file=sys.stderr)
        print(f'Usage: devsquad {command} "your task"', file=sys.stderr)
        return 1

    validator = InputValidator()
    task_result = validator.validate_task(task_text)
    if not task_result.valid:
        print(f"Error: Invalid task - {task_result.reason}", file=sys.stderr)
        return 1

    task = task_result.sanitized_input or task_text

    # Check for visual mode
    use_visual = getattr(args, "visual", False)
    use_verbose = getattr(args, "verbose", False)

    # Show view layer mapping information (Plan C: CLI as View Layer)
    try:
        from scripts.collaboration.lifecycle_protocol import VIEW_MAPPINGS, get_shared_protocol

        mapping = VIEW_MAPPINGS.get(command)

        if use_visual:
            _render_lifecycle_visual(command, mapping, preset, task, use_verbose, get_shared_protocol)
        elif use_verbose:
            _render_lifecycle_verbose(command, mapping, preset, get_shared_protocol)
        else:
            _render_lifecycle_simple(command, mapping, preset)
    except (KeyError, ValueError, AttributeError, RuntimeError) as e:
        _render_lifecycle_error(command, preset, e)

    kwargs = _build_lifecycle_kwargs(args)

    disp = MultiAgentDispatcher(**kwargs)

    try:
        result = disp.dispatch(
            task,
            roles=preset["required_roles"],
            mode=preset["mode"],
            dry_run=args.dry_run,
        )

        _print_lifecycle_result(args, command, preset, result)

        return 0 if result.success else 1
    finally:
        disp.shutdown()
