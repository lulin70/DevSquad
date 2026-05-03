#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI Visual Enhancement Module for DevSquad V3.5.0-C

Provides rich visual output for lifecycle commands including:
  - Colored progress bars
  - Phase status icons
  - Percentage displays
  - Gate status visualization
  - Beautiful formatted tables

Usage:
    from scripts.cli.cli_visual import VisualFormatter
    
    vf = VisualFormatter()
    vf.print_lifecycle_header(command, mapping, preset)
    vf.print_phase_progress(phases, current_phase)
    vf.print_gate_status(gate_result)
"""

import sys
from typing import Any, Dict, List, Optional


class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class Icons:
    """Unicode icons for visual enhancement."""
    # Phase states
    CHECK = '✅'
    CROSS = '❌'
    ARROW_RIGHT = '▶'
    CIRCLE = '⭕'
    SKIP = '⏭️'
    BLOCKED = '🚫'
    RUNNING = '🔄'
    
    # Status
    SUCCESS = '✓'
    FAIL = '✗'
    WARNING = '⚠'
    INFO = 'ℹ'
    
    # Objects
    FILE = '📄'
    FOLDER = '📁'
    GEAR = '⚙️'
    ROCKET = '🚀'
    CHART = '📊'
    LOCK = '🔒'
    KEY = '🔑'
    
    # People
    USER = '👤'
    USERS = '👥'
    ROBOT = '🤖'
    
    # Misc
    STAR = '★'
    SPARKLE = '✨'
    FIRE = '🔥'
    BULB = '💡'
    TARGET = '🎯'
    FLAG = '🚩'


class ProgressBar:
    """Animated progress bar for terminal output."""
    
    def __init__(
        self,
        total: int = 100,
        width: int = 40,
        fill_char: str = '█',
        empty_char: str = '░',
        prefix: str = '',
        suffix: str = '',
    ):
        self.total = total
        self.width = width
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.prefix = prefix
        self.suffix = suffix
    
    def render(self, current: int) -> str:
        """Render progress bar at given position."""
        if self.total == 0:
            percent = 100
        else:
            percent = int(current / self.total * 100)
        
        filled = int(self.width * current / self.total)
        bar = self.fill_char * filled + self.empty_char * (self.width - filled)
        
        # Color based on percentage
        if percent >= 80:
            color = Colors.GREEN
        elif percent >= 50:
            color = Colors.YELLOW
        elif percent >= 25:
            color = Colors.CYAN
        else:
            color = Colors.RED
        
        return f"{color}{self.prefix}[{bar}]{Colors.RESET}{self.suffix} {percent}%"
    
    @staticmethod
    def simple(current: int, total: int, width: int = 20) -> str:
        """Quick static progress bar."""
        if total == 0:
            return f"[{'█' * width}] 100%"
        
        percent = int(current / total * 100)
        filled = int(width * current / total)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percent}%"


class VisualFormatter:
    """
    Main formatter class for CLI visual enhancement.
    
    Provides methods to format and display lifecycle information
    in a visually appealing way.
    """
    
    def __init__(self, use_color: bool = True):
        self.use_color = use_color
        self.icons = Icons()
        self.colors = Colors()
    
    def _c(self, text: str, color: str) -> str:
        """Apply color to text (if enabled)."""
        if self.use_color:
            return f"{color}{text}{self.colors.RESET}"
        return text
    
    def print_separator(
        self,
        char: str = '=',
        length: int = 60,
        color: Optional[str] = None,
    ) -> None:
        """Print a separator line."""
        line = char * length
        if color:
            print(self._c(line, color))
        else:
            print(line)
    
    def print_title(self, title: str, subtitle: str = '') -> None:
        """Print a formatted title."""
        self.print_separator('=', 60, Colors.CYAN)
        
        main = self._c(f"  {title}", Colors.BOLD + Colors.CYAN)
        print(main)
        
        if subtitle:
            sub = self._c(f"  {subtitle}", Colors.DIM)
            print(sub)
        
        self.print_separator('=', 60, Colors.CYAN)
        print()
    
    def print_lifecycle_header(
        self,
        command: str,
        mapping: Optional[Any] = None,
        preset: Optional[Dict] = None,
    ) -> None:
        """Print enhanced lifecycle command header."""
        self.print_title(
            f"🔄 DevSquad Lifecycle [{command.upper()}]",
            "View Layer Mode (Plan C Architecture)"
        )
        
        # Command info box
        print(self._c("  ┌─────────────────────────────────────────┐", Colors.CYAN))
        print(self._c("  │", Colors.CYAN) + 
              f" 📌 Command: ".ljust(15) + 
              self._c(command.upper(), Colors.BOLD + Colors.YELLOW))
        print(self._c("  │", Colors.CYAN))
        
        if mapping:
            phases_str = ', '.join(mapping.phases[:4])
            if len(mapping.phases) > 4:
                phases_str += f" (+{len(mapping.phases)-4} more)"
            
            print(self._c("  │", Colors.CYAN) + 
                  f" 📋 Phases: ".ljust(15) +
                  self._c(phases_str, Colors.GREEN))
        
        if preset:
            roles_str = ', '.join(preset.get('required_roles', [])[:3])
            print(self._c("  │", Colors.CYAN) + 
                  f" 👥 Roles: ".ljust(15) +
                  self._c(roles_str, Colors.BLUE))
            
            mode = preset.get('mode', 'unknown')
            gate = preset.get('gate', 'unknown')
            print(self._c("  │", Colors.CYAN) + 
                  f" ⚙️  Mode: ".ljust(15) +
                  self._c(mode, Colors.MAGENTA) +
                  " | ".ljust(5) +
                  f"🚧 Gate: {gate}")
        
        print(self._c("  └─────────────────────────────────────────┘", Colors.CYAN))
        print()
    
    def print_phase_list(
        self,
        phases: List[Any],
        current_phase: Optional[str] = None,
        completed_phases: Optional[List[str]] = None,
    ) -> None:
        """Print formatted phase list with status icons."""
        completed_phases = completed_phases or []
        
        print(self._c("  📋 Lifecycle Phases:", Colors.BOLD))
        print()
        
        for i, phase in enumerate(phases, 1):
            phase_id = getattr(phase, 'phase_id', str(phase))
            name = getattr(phase, 'name', phase_id)
            optional = getattr(phase, 'optional', False)
            
            # Determine status icon and color
            if phase_id in completed_phases:
                icon = Icons.CHECK
                color = Colors.GREEN
                status_text = "COMPLETED"
            elif phase_id == current_phase:
                icon = Icons.ARROW_RIGHT
                color = Colors.YELLOW
                status_text = "RUNNING"
            elif optional:
                icon = Icons.SKIP
                color = Colors.DIM
                status_text = "OPTIONAL"
            else:
                icon = Icons.CIRCLE
                color = Colors.DIM
                status_text = "PENDING"
            
            # Format line
            num = self._c(f"{i:2}.", Colors.DIM)
            pid = self._c(f"[{phase_id}]", color)
            pname = self._c(name.ljust(25), color if phase_id == current_phase else '')
            picon = f" {icon}"
            pstatus = self._c(f"<{status_text}>", Colors.DIM)
            
            opt_tag = ""
            if optional:
                opt_tag = self._c(" [opt]", Colors.DIM)
            
            print(f"  {num} {pid} {pname}{picon}{pstatus}{opt_tag}")
        
        print()
    
    def print_progress_overview(
        self,
        current: int,
        total: int,
        label: str = "Progress",
    ) -> None:
        """Print progress overview with bar and stats."""
        percent = int(current / total * 100) if total > 0 else 0
        
        print(self._c(f"  {Icons.CHART} {label}:", Colors.BOLD))
        print()
        
        # Progress bar
        bar = ProgressBar.simple(current, total, 35)
        colored_bar = self._colorize_bar(bar, percent)
        print(f"    {colored_bar}")
        print()
        
        # Stats
        stats_line = (
            f"    {Icons.CHECK} Completed: "
            f"{self._c(str(current), Colors.GREEN)} / "
            f"{self._c(str(total), Colors.WHITE)} "
            f"({self._c(f'{percent}%', Colors.BOLD)})"
        )
        print(stats_line)
        print()
    
    def _colorize_bar(self, bar: str, percent: int) -> str:
        """Colorize progress bar based on percentage."""
        if percent >= 80:
            return self._c(bar, Colors.GREEN)
        elif percent >= 50:
            return self._c(bar, Colors.YELLOW)
        elif percent >= 25:
            return self._c(bar, Colors.CYAN)
        else:
            return self._c(bar, Colors.RED)
    
    def print_gate_status(
        self,
        gate_result: Optional[Any] = None,
        gate_type: str = "Phase",
    ) -> None:
        """Print gate check result with visual indicators."""
        print(self._c(f"  {Icons.LOCK} {gate_type} Gate Status:", Colors.BOLD))
        print()
        
        if gate_result is None:
            print(f"    {self._c(Icons.INFO, Colors.BLUE)} No gate result available")
            print()
            return
        
        passed = getattr(gate_result, 'passed', False)
        verdict = getattr(gate_result, 'verdict', 'UNKNOWN')
        checks_run = getattr(gate_result, 'checks_run', 0)
        checks_passed = getattr(gate_result, 'checks_passed', 0)
        
        # Verdict display
        if verdict.upper() == 'APPROVE':
            verdict_icon = Icons.CHECK
            verdict_color = Colors.GREEN
            verdict_text = "APPROVED"
        elif verdict.upper() == 'REJECT':
            verdict_icon = Icons.CROSS
            verdict_color = Colors.RED
            verdict_text = "REJECTED"
        elif verdict.upper() == 'CONDITIONAL':
            verdict_icon = Icons.WARNING
            verdict_color = Colors.YELLOW
            verdict_text = "CONDITIONAL"
        else:
            verdict_icon = Icons.INFO
            verdict_color = Colors.BLUE
            verdict_text = verdict.upper()
        
        verdict_line = (
            f"    {self._c(verdict_icon, verdict_color)} "
            f"Verdict: "
            f"{self._c(verdict_text, Colors.BOLD + verdict_color)}"
        )
        print(verdict_line)
        
        # Checks summary
        if checks_run > 0:
            check_percent = int(checks_passed / checks_run * 100)
            check_line = (
                f"    {Icons.GEAR} Checks: "
                f"{self._c(str(checks_passed), Colors.GREEN)}/"
                f"{self._c(str(checks_run), Colors.WHITE)} "
                f"({check_percent}%)"
            )
            print(check_line)
        
        # Issues summary
        critical_issues = getattr(gate_result, 'critical_issues', [])
        warnings = getattr(gate_result, 'warnings', [])
        evidence_required = getattr(gate_result, 'evidence_required', [])
        
        if critical_issues:
            print(f"\n    {self._c(Icons.CROSS + ' Critical Issues:', Colors.RED)}")
            for issue in critical_issues[:3]:
                msg = issue.get('message', str(issue))[:60]
                print(f"      {self._c('•', Colors.RED)} {msg}")
            if len(critical_issues) > 3:
                print(f"      ... and {len(critical_issues)-3} more")
        
        if warnings:
            print(f"\n    {self._c(Icons.WARNING + ' Warnings:', Colors.YELLOW)}")
            for warning in warnings[:3]:
                msg = warning.get('message', str(warning))[:60]
                print(f"      {self._c('•', Colors.YELLOW)} {msg}")
            if len(warnings) > 3:
                print(f"      ... and {len(warnings)-3} more")
        
        if evidence_required:
            print(f"\n    {self._c(Icons.KEY + ' Evidence Required:', Colors.CYAN)}")
            for ev in evidence_required[:5]:
                print(f"      {self._c('•', Colors.CYAN)} {ev}")
        
        print()
    
    def print_status_summary(
        self,
        status: Any,
    ) -> None:
        """Print comprehensive status summary."""
        mode = getattr(status, 'mode', None)
        current_phase = getattr(status, 'current_phase', None)
        completed = getattr(status, 'completed_phases', [])
        failed = getattr(status, 'failed_phases', [])
        blocked = getattr(status, 'blocked_phases', [])
        progress = getattr(status, 'progress_percent', 0)
        can_advance = getattr(status, 'can_advance', True)
        next_phase = getattr(status, 'next_phase', None)
        
        self.print_title(
            f"📊 Lifecycle Status Summary",
            f"Mode: {mode.value if hasattr(mode, 'value') else mode}" if mode else ''
        )
        
        # Overview stats
        print(self._c("  ┌─ Overview ─────────────────────────────┐", Colors.CYAN))
        print(self._c("  │", Colors.CYAN))
        
        mode_str = mode.value if hasattr(mode, 'value') else str(mode)
        print(self._c("  │", Colors.CYAN) + 
              f" Mode: ".ljust(12) + 
              self._c(mode_str, Colors.BOLD + Colors.MAGENTA))
        
        progress_str = f"{progress:.1f}%"
        print(self._c("  │", Colors.CYAN) + 
              f" Progress: ".ljust(12) + 
              self._c(progress_str, Colors.BOLD + self._progress_color(progress)))
        
        can_advance_str = "Yes ✅" if can_advance else "No ❌"
        print(self._c("  │", Colors.CYAN) + 
              f" Can Advance: ".ljust(12) + 
              self._c(can_advance_str, Colors.GREEN if can_advance else Colors.RED))
        
        print(self._c("  └────────────────────────────────────────┘", Colors.CYAN))
        print()
        
        # Phase counts
        total_phases = len(completed) + len(failed) + len(blocked)
        print(f"  {Icons.CHART} Phase Statistics:")
        print(f"    {Icons.CHECK} Completed: {self._c(str(len(completed)), Colors.GREEN)}")
        print(f"    {Icons.CROSS} Failed: {self._c(str(len(failed)), Colors.RED)}")
        print(f"    {Icons.BLOCKED} Blocked: {self._c(str(len(blocked)), Colors.YELLOW)}")
        print(f"    {Icons.ARROW_RIGHT} Current: {current_phase or 'None'}")
        print(f"    {Icons.TARGET} Next: {next_phase or 'N/A'}")
        print()
    
    def _progress_color(self, percent: float) -> str:
        """Get color for progress percentage."""
        if percent >= 80:
            return Colors.GREEN
        elif percent >= 50:
            return Colors.YELLOW
        elif percent >= 25:
            return Colors.CYAN
        else:
            return Colors.RED
    
    def print_footer(self, version: str = "V3.5.0-C") -> None:
        """Print footer with version and timestamp."""
        from datetime import datetime
        
        self.print_separator('-', 40, Colors.DIM)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footer = (
            f"  DevSquad {version} | "
            f"{timestamp} | "
            f"{Icons.SPARKLE} Plan C Layered Architecture"
        )
        print(self._c(footer, Colors.DIM))
        self.print_separator('-', 40, Colors.DIM)
    
    def print_success_message(self, message: str = "Operation completed successfully!") -> None:
        """Print success message with icon."""
        print()
        print(f"  {self._c(Icons.CHECK + ' ' + message, Colors.GREEN + Colors.BOLD)}")
        print()
    
    def print_error_message(self, message: str) -> None:
        """Print error message with icon."""
        print()
        print(f"  {self._c(Icons.CROSS + ' Error: ' + message, Colors.RED + Colors.BOLD)}")
        print()
    
    def print_info_box(
        self,
        title: str,
        content: List[str],
        icon: str = Icons.INFO,
        color: str = Colors.BLUE,
    ) -> None:
        """Print an info box with title and content."""
        print(f"\n  {self._c(icon + ' ' + title, color + Colors.BOLD)}")
        print(f"  {'─' * (len(title) + 4)}")
        for line in content:
            print(f"  {self._c('•', color)} {line}")
        print()


def get_visual_formatter(use_color: bool = True) -> VisualFormatter:
    """Get a VisualFormatter instance (factory function)."""
    return VisualFormatter(use_color=use_color)


def print_enhanced_lifecycle_command(
    command: str,
    task: str,
    use_visual: bool = True,
) -> int:
    """
    Print enhanced lifecycle command output.
    
    This is the main entry point for visual CLI output.
    
    Args:
        command: Lifecycle command (spec/plan/build/test/review/ship)
        task: Task description
        use_visual: Whether to use visual formatting
    
    Returns:
        Exit code (0 for success)
    """
    if not use_visual:
        return 0  # Let normal output proceed
    
    try:
        from scripts.collaboration.lifecycle_protocol import (
            VIEW_MAPPINGS,
            create_lifecycle_protocol,
            LifecycleMode,
        )
        
        vf = VisualFormatter(use_color=True)
        
        # Get mapping and protocol
        mapping = VIEW_MAPPINGS.get(command)
        protocol = create_lifecycle_protocol(LifecycleMode.SHORTCUT)
        preset = _get_preset(command)
        
        # Print enhanced header
        vf.print_lifecycle_header(command, mapping, preset)
        
        # Show resolved phases
        if mapping:
            phases = protocol.resolve_command_to_phases(command)
            if phases:
                vf.print_phase_list(phases)
                
                # Show progress placeholder
                vf.print_progress_overview(0, len(phases), "Command Coverage")
        
        # Show gate info
        gate_name = preset.get('gate', 'Unknown') if preset else 'Unknown'
        vf.print_gate_status(None, gate_name)
        
        # Print next steps
        vf.print_info_box(
            "Next Steps",
            [
                f"Run: python3 scripts/cli.py dispatch -t \"{task}\" --roles architect solo-coder",
                f"Or use: python3 examples/quick_start.py",
                f"View guide: cat docs/USAGE_GUIDE.md",
            ],
            icon=Icons.ROCKET,
            color=Colors.GREEN,
        )
        
        vf.print_footer()
        vf.print_success_message("Ready to execute!")
        
        return 0
        
    except Exception as e:
        print(f"\nVisual enhancement error: {e}\n")
        return 0  # Don't block normal operation


def _get_preset(command: str) -> Optional[Dict]:
    """Get preset configuration for a command."""
    presets = {
        "spec": {
            "description": "Define and refine requirements before implementation",
            "required_roles": ["architect", "product-manager"],
            "mode": "sequential",
            "gate": "spec_first",
        },
        "plan": {
            "description": "Break down work into small, verifiable tasks",
            "required_roles": ["architect", "product-manager"],
            "mode": "auto",
            "gate": "task_breakdown_complete",
        },
        "build": {
            "description": "Implement incrementally with TDD discipline",
            "required_roles": ["architect", "solo-coder", "tester"],
            "mode": "parallel",
            "gate": "incremental_verification",
        },
        "test": {
            "description": "Run tests with mandatory evidence requirements",
            "required_roles": ["tester", "solo-coder"],
            "mode": "consensus",
            "gate": "evidence_required",
        },
        "review": {
            "description": "Five-axis code review (correctness/readability/arch/security/performance)",
            "required_roles": ["solo-coder", "security", "tester", "architect"],
            "mode": "consensus",
            "gate": "change_size_limit",
        },
        "ship": {
            "description": "Pre-launch verification and deployment preparation",
            "required_roles": ["devops", "security", "architect"],
            "mode": "sequential",
            "gate": "pre_launch_checklist",
        },
    }
    return presets.get(command)


if __name__ == "__main__":
    # Quick demo of visual formatter
    vf = VisualFormatter()
    
    vf.print_title("Visual Formatter Demo", "Testing all features")
    
    # Demo progress bars
    for i in [0, 25, 50, 75, 100]:
        bar = ProgressBar.simple(i, 100, 30)
        print(f"  {vf._colorize_bar(bar, i)}")
    
    print()
    vf.print_success_message("Demo complete!")
