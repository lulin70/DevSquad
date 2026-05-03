#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad V3.5.0-C Quick Start Example

Demonstrates basic usage of the unified lifecycle architecture (Plan C).

This example shows:
  1. Creating a lifecycle adapter (SHORTCUT mode)
  2. Using CLI commands as view layer over 11-phase model
  3. Checking gate conditions
  4. Tracking progress

Run:
    cd /Users/lin/trae_projects/DevSquad
    python3 examples/quick_start.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def example_basic_shortcut_mode():
    """
    Example 1: Basic SHORTCUT mode usage

    Uses CLI-like commands (spec, build, test) mapped to 11-phase segments.
    Perfect for quick tasks and simple workflows.
    """
    print("=" * 60)
    print("📚 Example 1: Basic SHORTCUT Mode")
    print("=" * 60)

    from scripts.collaboration.lifecycle_protocol import (
        create_lifecycle_protocol,
        LifecycleMode,
        VIEW_MAPPINGS,
    )

    # Step 1: Create adapter in SHORTCUT mode (default)
    print("\n🔧 Step 1: Create lifecycle adapter")
    protocol = create_lifecycle_protocol(LifecycleMode.SHORTCUT)

    print(f"   Mode: {protocol.get_mode().value}")
    print(f"   Total phases available: {len(protocol.get_all_phases())}")

    # Step 2: Explore view mappings (CLI → Phases)
    print("\n🗺️  Step 2: View Layer Mappings (CLI commands → 11 phases)")
    for cmd, mapping in VIEW_MAPPINGS.items():
        print(f"   {cmd:8} → {', '.join(mapping.phases)}")

    # Step 3: Resolve a command to phases
    print("\n🎯 Step 3: Resolve 'build' command to phases")
    build_phases = protocol.resolve_command_to_phases("build")
    for phase in build_phases:
        print(f"   - {phase.phase_id}: {phase.name}")

    # Step 4: Advance through phases with gate checks
    print("\n⏭️  Step 4: Advance through 'spec' command phases")
    spec_phases = protocol.resolve_command_to_phases("spec")

    for phase_def in spec_phases[:2]:  # Just first 2 for demo
        print(f"\n   Trying to advance to {phase_def.phase_id}: {phase_def.name}...")

        # Check gate first
        gate_result = protocol.check_gate(phase_def.phase_id)
        print(f"      Gate check: {gate_result.verdict}")

        if gate_result.passed or gate_result.verdict != "REJECT":
            result = protocol.advance_to_phase(phase_def.phase_id)
            if result.success:
                print(f"      ✅ Advanced successfully!")
                protocol.complete_phase(phase_def.phase_id)
            else:
                print(f"      ❌ Failed: {result.error}")
        else:
            print(f"      🚫 Gate rejected: {gate_result.gap_report[:50]}...")

    # Step 5: Check final status
    print("\n📊 Step 5: Final Status")
    status = protocol.get_status()
    print(f"   Mode: {status.mode.value}")
    print(f"   Current Phase: {status.current_phase}")
    print(f"   Completed: {', '.join(status.completed_phases) if status.completed_phases else 'None'}")
    print(f"   Progress: {status.progress_percent:.1f}%")
    print(f"   Can Advance: {'Yes' if status.can_advance else 'No'}")
    print(f"   Next Phase: {status.next_phase}")


def example_basic_full_mode():
    """
    Example 2: Basic FULL mode usage

    Uses complete 11-phase lifecycle with dependency resolution.
    Best for complex projects requiring full control.
    """
    print("\n\n" + "=" * 60)
    print("📚 Example 2: Basic FULL Mode")
    print("=" * 60)

    from scripts.collaboration.lifecycle_protocol import (
        FullLifecycleAdapter,
        LifecycleMode,
    )

    # Step 1: Create adapter in FULL mode
    print("\n🔧 Step 1: Create FullLifecycleAdapter")
    adapter = FullLifecycleAdapter(use_unified_gate=False)

    print(f"   Mode: {adapter.get_mode().value}")
    print(f"   Execution order: {' → '.join(adapter._execution_order)}")

    # Step 2: Show all 11 phases
    print("\n📋 Step 2: All 11 Phases")
    for phase in adapter.get_all_phases():
        deps = f" (deps: {', '.join(phase.dependencies)})" if phase.dependencies else ""
        opt = " [optional]" if phase.optional else ""
        print(f"   {phase.phase_id}: {phase.name:<20} Role: {phase.role_id}{deps}{opt}")

    # Step 3: Auto-advance through first few phases
    print("\n⚡ Step 3: Auto-advance (first 3 phases)")
    for i in range(3):
        result = adapter.auto_advance()
        if result.success:
            print(f"   ✅ Advanced to {result.phase_id}")
            adapter.complete_phase(result.phase_id)
        else:
            print(f"   ⚠️  Stopped: {result.error}")
            break

    # Step 4: Get detailed progress
    print("\n📊 Step 4: Detailed Progress")
    progress = adapter.get_execution_progress()
    print(f"   Total phases: {progress['total_phases']}")
    print(f"   Completed: {progress['completed_phases']}/{progress['total_phases']}")
    print(f"   Progress: {progress['progress_percent']:.1f}%")
    print(f"   Current: {progress['current_phase']}")

    print("\n   Phase details:")
    for pinfo in progress["phases"][:6]:
        icon = "✅" if pinfo["completed"] else "⏳"
        print(f"     {icon} {pinfo['phase_id']}: {pinfo['name']:<18} [{pinfo['state']}]")

    # Step 5: Enable checkpoint integration
    print("\n💾 Step 5: Checkpoint Integration (optional)")
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="devsquad_example_")

    adapter.set_task_id("example-basic-full")
    enabled = adapter.enable_checkpoint_integration(storage_path=tmpdir)
    print(f"   Checkpoint enabled: {enabled}")

    saved = adapter.save_state()
    print(f"   State saved: {saved}")

    # Note: load_lifecycle_state is handled by CheckpointManager
    # For demo, we just verify save worked
    if adapter._checkpoint_manager:
        loaded = adapter._checkpoint_manager.load_lifecycle_state("example-basic-full")
        print(f"   State can be loaded: {loaded is not None}")
        if loaded:
            print(f"   Restored phase: {loaded.get('current_phase')}")


def example_unified_gate_engine():
    """
    Example 3: UnifiedGateEngine basics

    Shows how the unified gate engine works for both phase transitions
    and worker output validation.
    """
    print("\n\n" + "=" * 60)
    print("📚 Example 3: UnifiedGateEngine Basics")
    print("=" * 60)

    from scripts.collaboration.unified_gate_engine import (
        UnifiedGateEngine,
        UnifiedGateConfig,
        GateType,
        GateSeverity,
        PhaseGateContext,
        WorkerOutputContext,
    )

    # Step 1: Create engine with custom config
    print("\n🔧 Step 1: Configure and create gate engine")
    config = UnifiedGateConfig(
        strict_mode=True,
        allowed_critical_flags=0,
        max_output_lines=100,
        min_test_coverage=0.8,
    )
    engine = UnifiedGateEngine(config=config)
    print(f"   Strict mode: {engine.config.strict_mode}")
    print(f"   Max output lines: {engine.config.max_output_lines}")
    print(f"   Min test coverage: {engine.config.min_test_coverage*100:.0f}%")

    # Step 2: Check a phase transition gate
    print("\n🚪 Step 2: Phase Transition Gate Check")
    context = PhaseGateContext(
        phase_id="P8",
        phase_name="Implementation",
        current_state="pending",
        target_state="running",
        dependencies_met=True,  # Dependencies satisfied
        completed_phases=["P1", "P2", "P3", "P7"],
    )
    result = engine.check(GateType.PHASE_TRANSITION, context)
    print(f"   Result: {result.verdict}")
    print(f"   Passed: {result.passed}")
    print(f"   Checks: {result.checks_passed}/{result.checks_run}")
    print(f"   Severity: {result.severity.value}")

    if result.warnings:
        print(f"   Warnings ({len(result.warnings)}):")
        for w in result.warnings[:3]:
            print(f"      - {w.get('message', '')}")

    # Step 3: Check a worker output gate
    print("\n👷 Step 3: Worker Output Gate Check")
    worker_context = WorkerOutputContext(
        role_id="solo-coder",
        task_description="Implement user authentication module",
        output="""
# User Authentication Module

class Authenticator:
    def __init__(self):
        self.users = {}

    def authenticate(self, username, password):
        if username in self.users:
            return self.users[username] == password
        return False
""",
        has_code_changes=True,
        has_test_changes=True,
        test_results={
            "all_passed": True,
            "total": 15,
            "passed": 15,
            "failed": 0,
        },
        claims_complete=False,
    )
    worker_result = engine.check(GateType.WORKER_OUTPUT, worker_context)
    print(f"   Result: {worker_result.verdict}")
    print(f"   Passed: {worker_result.passed}")
    print(f"   Evidence required: {len(worker_result.evidence_required)} items")

    # Step 4: View summary
    print("\n📄 Step 4: Result Summary")
    print(result.to_summary())
    print("\n" + worker_result.to_summary())

    # Step 5: Statistics
    print("\n📈 Step 5: Engine Statistics")
    stats = engine.get_statistics()
    print(f"   Total checks run: {stats['total_checks']}")
    print(f"   Passed: {stats['passed']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Conditional: {stats['conditional']}")
    print(f"   Pass rate: {stats['pass_rate']:.1f}%")


def main():
    """Run all quick start examples."""
    print("🚀 DevSquad V3.5.0-C Quick Start Examples")
    print("=" * 60)
    print("This demonstrates the unified lifecycle architecture (Plan C)")
    print()

    try:
        example_basic_shortcut_mode()
        example_basic_full_mode()
        example_unified_gate_engine()

        print("\n\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run examples/full_project_workflow.py for complete project example")
        print("  2. Read docs/USAGE_GUIDE.md for detailed documentation")
        print("  3. Check tests/ for comprehensive test coverage examples")
        print()

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
