# DevSquad — Installation Guide

> **⚠️ Path Placeholder Notice**: Throughout this guide, `/path/to/DevSquad` is a template.
> Replace it with your actual installation path before running any command:
> ```bash
> # Example: if you cloned to ~/projects/DevSquad
> # Replace /path/to/DevSquad → /Users/YOUR_USERNAME/projects/DevSquad
>
> # Quick check your actual path:
> pwd   # run this inside the DevSquad directory
> ```

## Prerequisites

- **Python 3.9+** (pure Python, no compiled dependencies)
- **OS**: macOS / Linux / **Windows 10+** (fully cross-platform)
- **Any AI coding environment**: Trae IDE / Claude Code / OpenClaw / Terminal
- **No external dependencies required** (all integrations use graceful degradation)

See [**Windows Support**](#windows-support) below for Windows-specific instructions.

## Quick Start (3 Methods)

### Method 1: CLI — Recommended for most users

```bash
# Clone or download DevSquad
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Run a task immediately
python3 scripts/cli.py dispatch --task "Design user authentication system" --roles architect coder tester

# Check status
python3 scripts/cli.py status

# List available roles
python3 scripts/cli.py roles
```

That's it. No environment variables, no installation steps.

### Method 2: Environment Variable + Wrapper Script

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export DSS_SKILL_PATH="/path/to/DevSquad"
```

Then use from anywhere:

```bash
python3 $DSS_SKILL_PATH/scripts/trae_agent.py --task "Analyze requirements" --agent architect
```

> **Note**: `trae_agent.py` uses legacy role names (`product-manager`, `solo-coder`, `ui-designer`).
> For the modern 10-role system, use `scripts/cli.py` (Method 1) instead.

### Method 3: Python Import

```python
import sys
sys.path.insert(0, '/path/to/DevSquad')

from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design REST API for user management")
print(result.to_markdown())
disp.shutdown()
```

## CLI Reference (`scripts/cli.py`)

```
Usage: cli.py {dispatch, status,roles} [options]

Commands:
  dispatch (run, d)   Execute a multi-agent collaboration task
  status (s)          Show system status and capabilities
  roles (ls)          List available agent roles

Dispatch Options:
  --task, -t TEXT       Task description (required)
  --roles, -r LIST      Roles: architect/pm/coder/tester/ui/devops/
                         security/data/reviewer/optimizer (default: auto-match)
  --mode, -m MODE       Execution mode: auto/parallel/sequential/consensus
  --format, -f FORMAT   Output: markdown/json/compact/structured/detailed
  --dry-run             Simulate without execution
  --quick, -q           Use quick_dispatch (3 format variants)
  --action-items        Include H/M/L priority action items
  --timing              Include execution timing data
  --no-warmup           Disable startup warmup
  --no-compression      Disable context compression
  --skip-permission      Skip permission checks
  --no-memory           Disable memory bridge
  --permission-level    PLAN/DEFAULT/AUTO/BYPASS
  --persist-dir        Custom scratchpad directory
  --no-skillify         Disable skill learning
```

### Usage Examples

```bash
# Basic dispatch (auto-matches roles)
python3 scripts/cli.py dispatch -t "Design microservices e-commerce backend"

# Specify roles explicitly
python3 scripts/cli.py dispatch -t "Review auth module" -r reviewer security tester

# JSON output for piping
python3 scripts/cli.py dispatch -t "Optimize database queries" -f json

# Quick compact output
python3 scripts/cli.py quick -t "Analyze API surface" -f compact

# Consensus mode (any veto blocks)
python3 scripts/cli.py dispatch -t "Architecture decision" -m consensus

# Dry run (analyze only, no execution)
python3 scripts/cli.py dispatch -t "Test task" --dry-run
```

## Available Roles (10)

| Role | Best For |
|------|----------|
| `architect` | System design, tech stack, API design |
| `pm` | Requirements, user stories, acceptance criteria |
| `coder` | Implementation, code generation, refactoring |
| `tester` | Test strategy, edge cases, coverage gaps |
| `ui` | UX flow, interaction design, accessibility |
| `devops` | CI/CD pipeline, deployment, monitoring |
| `security` | Threat modeling, vulnerability audit |
| `data` | Data modeling, analytics, migrations |
| `reviewer` | Code review, best practices |
| `optimizer` | Performance optimization, caching |

## Integration Guides

### Trae IDE (Native)

1. Open any project in Trae IDE
2. Ensure DevSquad is at a known path
3. Set `DSS_SKILL_PATH` in Trae's terminal settings, or use full path:

```bash
python3 /path/to/DevSquad/scripts/cli.py dispatch -t "your task"
```

The `skill-manifest.yaml` provides native Trae integration metadata.

### Claude Code

DevSquad includes `CLAUDE.md` at project root. When Claude Code opens this directory,
it automatically loads project context including architecture, entry points, and role system.

Custom skill available at `.claude/skills/multi-agent-team/SKILL.md`.

### OpenClaw (MCP Server)

Start the MCP server for tool-based integration:

```bash
pip install mcp  # optional, for MCP protocol support
python3 scripts/mcp_server.py            # stdio mode (default)
python3 scripts/mcp_server.py --port 8080  # SSE mode
```

Exposes 6 tools: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`.

## Verification

```bash
cd /path/to/DevSquad

# 1. Status check
python3 scripts/cli.py status
# Expected: {"name": "DevSquad", "status": "ready", ...}

# 2. Role listing
python3 scripts/cli.py roles
# Expected: 5 core roles + 5 planned roles listed

# 3. Dry-run test
python3 scripts/cli.py dispatch -t "test" -r architect --dry-run
# Expected: [DRY RUN] message

# 4. Core tests
python3 -m pytest scripts/collaboration/ -v
# Expected: ~825+ test cases (all passing)
```

## Troubleshooting

### "Module not found" errors

Ensure you're running from the DevSquad root directory, or add it to sys.path:

```bash
# Option A: cd first
cd /path/to/DevSquad && python3 scripts/cli.py ...

# Option B: set PYTHONPATH
PYTHONPATH=/path/to/DevSquad python3 scripts/cli.py ...
```

### MCE warnings on startup

The Memory Classification Engine (MCE) adapter uses lazy loading.
Warning messages about model/connection are normal — DevSquad degrades gracefully
when MCE is unavailable. No action needed.

### Permission denied

```bash
chmod +x scripts/*.py  # if needed
```

## Uninstalling

```bash
# Remove cloned directory
rm -rf /path/to/DevSquad

# Remove env var from ~/.zshrc or ~/.bashrc
# Delete the line: export DSS_SKILL_PATH="..."

# Remove symlink (if created)
rm /usr/local/bin/dss  # or whatever symlink name was used
```

## Project Structure

```
DevSquad/
├── scripts/
│   ├── cli.py                    # Primary CLI entry point
│   ├── mcp_server.py             # MCP server (OpenClaw/Cursor)
│   ├── trae_agent.py             # Legacy wrapper script
│   ├── trae_agent_dispatch_v2.py # Core dispatcher (legacy)
│   └── collaboration/            # ★ 16 core modules
│       ├── dispatcher.py         # MultiAgentDispatcher
│       ├── coordinator.py        # Global orchestrator
│       ├── scratchpad.py         # Shared blackboard
│       ├── worker.py             # Role executor
│       ├── consensus.py          # Weighted voting + veto
│       ├── memory_bridge.py      # Cross-session memory
│       ├── mce_adapter.py        # MCE v0.4 adapter
│       └── *_test.py             # Test suites (~825+ cases)
├── SKILL.md                      # English skill manual
├── SKILL-CN.md                   # Chinese skill manual
├── README.md                     # English readme
├── CLAUDE.md                     # Claude Code instructions
├── EXAMPLES.md                   # Usage examples
└── INSTALL.md                    # This file

---

## Windows Support

DevSquad is pure Python and fully compatible with Windows (10/11). Below are
Windows-specific instructions.

### Prerequisites on Windows

- **Python 3.9+** — Download from [python.org](https://python.org) or install via `winget`
- **PowerShell** or **CMD** — Both work; PowerShell recommended
- **Git for Windows** — For cloning the repo: [git-scm.com](https://git-scm.com)

```powershell
# Quick check (PowerShell)
python --version    # Should show Python 3.9+
git --version       # Should show git version
```

### Installation (Windows)

#### Option A: PowerShell (Recommended)

```powershell
# 1. Clone the repo
git clone https://github.com/lulin70/DevSquad.git C:\DevSquad
cd C:\DevSquad

# 2. Run a task immediately
python scripts\cli.py dispatch -t "Design user authentication system" -r architect coder tester

# 3. Check status
python scripts\cli.py status

# 4. List roles
python scripts\cli.py roles
```

> **Note**: On Windows, use `\` (backslash) as path separator in PowerShell/CMD,
> or use `/` (forward slash) — Python handles both correctly.

#### Option B: Set Environment Variable (Persistent)

**PowerShell** (persists across sessions):

```powershell
# Add to your PowerShell profile ($PROFILE)
[System.Environment]::SetEnvironmentVariable("DSS_SKILL_PATH", "C:\DevSquad", "User")

# Verify
echo $env:DSS_SKILL_PATH
```

**CMD** (add to System Properties → Environment Variables):

```cmd
setx DSS_SKILL_PATH "C:\DevSquad"
```

Then use from any directory:

```powershell
python $env:DSS_SKILL_PATH\scripts\trae_agent.py --task "Analyze requirements" --agent architect
```

> **Note**: `trae_agent.py` uses legacy role names. For the modern 10-role system,
> use `scripts\cli.py` (Option A above) instead.

#### Option C: Python Import

```python
import sys, os
sys.path.insert(0, r'C:\DevSquad')

from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design REST API for user management")
print(result.to_markdown())
disp.shutdown()
```

### Windows-Specific Notes

| Topic | Details |
|-------|---------|
| **Path separators** | Use `\\` in shell commands, but `/` also works in Python |
| **`.trae/` directory** | Works on Windows (visible folder, not hidden like Unix) |
| **`chmod +x`** | Not needed on Windows (no execute permission concept) |
| **Symlinks (`ln -s`)** | Requires Developer Mode on Windows 10/11. Not recommended — just set env var instead |
| **MCE Adapter** | Works if MCE installed in same Python environment. Graceful degradation otherwise |
| **WorkBuddy Claw** | Path defaults to Unix-style. Override via config if running on Windows |
| **Encoding** | All files use UTF-8. If you see encoding errors: `set PYTHONIOENCODING=utf-8` |

### Troubleshooting on Windows

#### `'python' is not recognized`

Python may be installed as `py` or `python3`:

```powershell
# Try these alternatives
py scripts\cli.py status
python3 scripts\cli.py status
```

Or add Python to PATH during installation (check "Add to PATH" in installer).

#### PermissionError / Access Denied

Windows may block scripts in some directories. Run as admin, or move to user directory:

```powershell
# Move to user home instead of C:\
move C:\DevSquad $HOME\DevSquad
```

#### ModuleNotFoundError

On Windows, current directory is not automatically in sys.path:

```powershell
# Option A: cd first
cd C:\DevSquad
python scripts\cli.py ...

# Option B: set PYTHONPATH
$env:PYTHONPATH="C:\DevSquad"
python scripts\cli.py ...
```

### Verification on Windows

```powershell
cd C:\DevSquad

# 1. Status check
python scripts\cli.py status
# Expected: {"name": "DevSquad", "status": "ready", ...}

# 2. Role listing
python scripts\cli.py roles
# Expected: 5 core roles + 5 planned roles listed

# 3. Dry-run test
python scripts\cli.py dispatch -t "test" -r architect --dry-run
# Expected: [DRY RUN] message

# 4. Core tests
python -m pytest scripts\collaboration\ -q
# Expected: ~825+ test cases (all passing)
```
