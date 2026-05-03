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

## Quick Start (4 Methods)

### Method 1: CLI — Recommended for most users

```bash
# Clone or download DevSquad
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Option A: Run directly (no install needed)
# Zero dependencies, ready to use, config file features degraded
python3 scripts/cli.py dispatch -t "Design user authentication system"

# Option B: pip install (Recommended)
# Full functionality, including config file support (pyyaml auto-installed)
pip install -e .
devsquad dispatch -t "Design user authentication system"
```

> **Which option?** Option A is for quick trials — no dependencies needed, but `~/.devsquad.yaml` config files won't be loaded. Option B installs DevSquad as a package with all features enabled, including YAML config, `devsquad` CLI command, and optional integrations (CarryMem, OpenAI, Anthropic).

```bash
python3 scripts/cli.py status

# List available roles
python3 scripts/cli.py roles

# Show version
python3 scripts/cli.py --version   # 3.4.0
```

### LLM Backend Configuration (Optional — for real AI output)

By default, DevSquad runs in **mock mode** — Workers return assembled prompts without calling an LLM. To get real AI analysis output, configure a backend:

> **🔒 Security**: API keys are read from environment variables only. There is no `--api-key` command-line flag — this prevents keys from appearing in shell history or process listings.

```bash
# Option A: OpenAI (GPT-4)
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Design auth system" -r architect --backend openai

# Option B: Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-..."
python3 scripts/cli.py dispatch -t "Design auth system" -r architect --backend anthropic

# Option C: Set default backend via environment variable
export DEVSQUAD_LLM_BACKEND=openai
python3 scripts/cli.py dispatch -t "Design auth system" -r architect
# Uses OpenAI automatically (no --backend flag needed)

# Option D: Custom base URL / model (for OpenAI-compatible APIs)
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://your-api-endpoint.com"
export OPENAI_MODEL="your-model-name"
python3 scripts/cli.py dispatch -t "Design auth system" -r architect --backend openai
```

**Tip**: Add `export` lines to your `~/.zshrc` or `~/.bashrc` for persistence across sessions.

**Install optional dependencies:**

```bash
# For OpenAI backend
pip install openai

# For Anthropic backend
pip install anthropic

# For performance monitoring (CPU/memory tracking)
pip install psutil

# For CarryMem cross-session memory + rule injection (optional)
pip install carrymem[devsquad]>=0.2.8

# Or install all optional dependencies
pip install -e ".[openai,anthropic,carrymem,monitoring,dev]"
```

### Method 2: Docker

```bash
# Build and run
docker build -t devsquad .
docker run devsquad dispatch -t "Design auth system"

# With API key
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "Design auth system" --backend openai

# Interactive shell
docker run -it devsquad /bin/bash
```

### Method 3: Configuration File

Create `~/.devsquad.yaml` for persistent settings:

```yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
  strict_validation: false
  checkpoint_enabled: true
  cache_enabled: true
  log_level: WARNING
```

Environment variables override config file values. Priority: env > file > defaults.

### Method 4: Python Import

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
Usage: cli.py {dispatch, status, roles} [options]

Commands:
  dispatch (run, d)   Execute a multi-agent collaboration task
  status (s)          Show system status and capabilities
  roles (ls)          List available agent roles

Dispatch Options:
  --task, -t TEXT       Task description (required)
  --roles, -r LIST      Roles: arch/pm/test/coder/ui/infra/sec (default: auto-match)
  --mode, -m MODE       Execution mode: auto/parallel/sequential/consensus
  --format, -f FORMAT   Output: markdown/json/compact/structured/detailed
  --backend, -b TYPE    LLM backend: mock/trae/openai/anthropic (default: mock)
  --base-url URL        Custom API base URL (or OPENAI_BASE_URL env)
  --model NAME          Model name (or OPENAI_MODEL/ANTHROPIC_MODEL env)
  --stream              Stream LLM output in real-time (requires --backend)
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
python3 scripts/cli.py dispatch -t "Review auth module" -r sec test

# JSON output for piping
python3 scripts/cli.py dispatch -t "Optimize database queries" -f json

# Quick compact output
python3 scripts/cli.py quick -t "Analyze API surface" -f compact

# Consensus mode (any veto blocks)
python3 scripts/cli.py dispatch -t "Architecture decision" -m consensus

# Dry run (analyze only, no execution)
python3 scripts/cli.py dispatch -t "Test task" --dry-run
```

## Available Roles (7 Core)

| Role | ID | Best For |
|------|----|----------|
| Architect | `arch` | System design, tech stack, performance/security/data architecture |
| Product Manager | `pm` | Requirements, user stories, acceptance criteria |
| Security Expert | `sec` | Threat modeling, vulnerability audit, compliance |
| Tester | `test` | Test strategy, quality assurance, edge cases |
| Coder | `coder` | Implementation, code review, performance optimization |
| DevOps | `infra` | CI/CD, containerization, monitoring, infrastructure |
| UI Designer | `ui` | UX flow, interaction design, accessibility |

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
# Expected: 7 core roles listed

# 3. Dry-run test
python3 scripts/cli.py dispatch -t "test" -r architect --dry-run
# Expected: [DRY RUN] message

# 4. Core tests
python3 -m pytest scripts/collaboration/ tests/ test_v35_integration.py -v
# Expected: 560+ tests all passing
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

### CarryMem warnings on startup

The CarryMem adapter uses lazy loading.
Warning messages about model/connection are normal — DevSquad degrades gracefully
when CarryMem is unavailable. No action needed.

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
│   └── collaboration/            # ★ 45 core modules
│       ├── _version.py           # Version SSOT (3.4.0)
│       ├── dispatcher.py         # MultiAgentDispatcher
│       ├── coordinator.py        # Global orchestrator
│       ├── scratchpad.py         # Shared blackboard
│       ├── worker.py             # Role executor (with streaming)
│       ├── consensus.py          # Weighted voting + veto
│       ├── llm_backend.py        # Mock/OpenAI/Anthropic + streaming
│       ├── role_matcher.py       # Keyword-based role matching
│       ├── report_formatter.py   # Structured/compact/detailed reports
│       ├── input_validator.py    # Security + prompt injection detection
│       ├── ai_semantic_matcher.py # LLM-powered semantic matching
│       ├── checkpoint_manager.py  # State persistence + handoff
│       ├── workflow_engine.py     # Task-to-workflow auto-split
│       ├── task_completion_checker.py # Completion tracking
│       ├── code_map_generator.py  # AST-based code analysis
│       ├── dual_layer_context.py  # Project + task context with TTL
│       ├── skill_registry.py     # Skill registration + discovery
│       ├── config_loader.py      # YAML config + env var overrides
│       ├── memory_bridge.py      # Cross-session memory
│       ├── mce_adapter.py        # CarryMem integration adapter
│       ├── agent_briefing.py     # Context-aware task briefing
│       ├── confidence_score.py   # 5-factor quality assessment
│       ├── enhanced_worker.py    # Worker with auto QA
│       ├── performance_monitor.py # P95/P99 monitoring
│       ├── protocols.py          # Interface definitions
│       ├── null_providers.py     # Graceful degradation providers
│       ├── prompt_assembler.py   # Dynamic prompt assembly + QC injection
│       ├── role_template_market.py # Role template marketplace
│       └── *_test.py             # Test suites (560+ tests)
├── .github/workflows/test.yml    # CI: Python 3.9-3.12 matrix
├── Dockerfile                    # Docker support
├── pyproject.toml                # pip-installable package
├── SKILL.md                      # Skill manual (EN/CN/JP)
├── GUIDE.md                      # User guide (Chinese)
├── README.md                     # English readme
├── CLAUDE.md                     # Claude Code instructions
├── CHANGELOG.md                  # Version history
├── INSTALL.md                    # This file
└── docs/
    └── i18n/                     # International docs
        ├── README_CN.md          # 中文说明
        ├── README_JP.md          # 日本語説明
        ├── SKILL_CN.md           # 中文技能手册
        ├── SKILL_JP.md           # 日本語スキルマニュアル
        ├── GUIDE_EN.md           # English user guide
        └── GUIDE_JP.md           # 日本語ユーザーガイド

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
python scripts\cli.py dispatch -t "Analyze requirements" -r arch
```

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
| **CarryMem** | Works if CarryMem installed in same Python environment. Graceful degradation otherwise |
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
# Expected: 7 core roles listed

# 3. Dry-run test
python scripts\cli.py dispatch -t "test" -r architect --dry-run
# Expected: [DRY RUN] message

# 4. Core tests
python -m pytest scripts\collaboration\ tests\ test_v35_integration.py -q
# Expected: 560+ tests all passing
```
