# DevSquad Usage Examples

> Last verified: 2026-05-03 with DevSquad V3.6.0-Prod, backend=openai, model=gpt-4
>
> **Production Ready**: Authentication ✅ | REST API ✅ | Alert System ✅ | Historical Data ✅

## Quick Start

```bash
# Mock mode (default) — returns assembled prompts, no API key needed
python3 scripts/cli.py dispatch -t "Design a user authentication system"

# Real AI output — set environment variables first
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.moka-ai.com/v1"
export OPENAI_MODEL="moka/claude-sonnet-4-6"
python3 scripts/cli.py dispatch -t "Design a user authentication system" --backend openai

# Specify roles explicitly (use short IDs: arch/pm/test/coder/ui/infra/sec)
python3 scripts/cli.py dispatch -t "Design a user authentication system" -r arch pm test --backend openai

# Stream output in real-time (V3.4.0)
python3 scripts/cli.py dispatch -t "Design a user authentication system" -r arch --backend openai --stream

# Dry-run (simulate without execution)
python3 scripts/cli.py dispatch -t "Design a user authentication system" --dry-run
```

## Real Output Examples

### Example 1: Architecture Design (Single Role)

```bash
python3 scripts/cli.py dispatch \
    -t "Design a user authentication system with OAuth2 and 2FA" \
    -r arch --backend openai
```

**Real output** (verified 2026-04-24, 91s, architect role):

```
# OAuth2 + 2FA Authentication System Architecture Design

## Key Findings

1. **Layered isolation is the security foundation** - OAuth2 authorization layer
   and 2FA verification layer must be independently deployed to avoid a single
   attack surface. Token storage and verification logic must be physically isolated.
2. **Performance-security balance** - Redis cluster caching tokens (TTL 15min) +
   database-persisted refresh tokens (30 days), with rate limiting to prevent
   brute force attacks.
```

### Example 2: Multi-Role Collaboration

```bash
python3 scripts/cli.py dispatch \
    -t "Build a real-time chat feature for a SaaS platform" \
    -r arch pm test --backend openai
```

**Real output** (verified 2026-04-24, 144s, 3 roles):

- **Architect**: WebSocket + Redis Pub/Sub architecture, supports million-level
  concurrent connections, latency <50ms, decoupled message persistence and
  real-time delivery
- **PM**: Real-time chat PRD, core business value (improve collaboration efficiency,
  increase platform stickiness), target users (B2B SaaS team collaboration)
- **Tester**: Test plan, key risk points (WebSocket stability, message latency <500ms,
  concurrent load), multi-layer data consistency verification, early security
  compliance involvement

### Example 3: Security Audit

```bash
python3 scripts/cli.py dispatch \
    -t "Security audit for a REST API that handles user payments and personal data" \
    -r sec --backend openai
```

**Real output** (verified 2026-04-24, 48s, security role):

```
I'll conduct a comprehensive security audit for your REST API handling
payments and personal data. Since I don't have access to your actual
codebase, I'll provide an executable audit framework with...
```

### Example 4: Streaming Output (V3.4.0 New)

```bash
python3 scripts/cli.py dispatch \
    -t "Design microservices e-commerce backend" \
    -r arch --backend openai --stream
```

In streaming mode, LLM responses are output chunk-by-chunk in real-time.
Ideal for long-running generations where you want to see results as they come.

### Example 5: Consensus Mode

```bash
python3 scripts/cli.py dispatch \
    -t "Choose database for analytics platform" \
    -r arch sec \
    --mode consensus
```

Consensus mode forces a vote when roles disagree. Each role casts a weighted vote,
veto power is respected, and human escalation is available for deadlocks.

### Example 6: JSON Output for Automation

```bash
python3 scripts/cli.py dispatch \
    -t "Review codebase for performance issues" \
    -r arch coder \
    --format json
```

JSON output is machine-readable, suitable for CI/CD pipelines or further processing.

## Docker Usage

```bash
# Build image
docker build -t devsquad .

# Run in mock mode
docker run devsquad dispatch -t "Design auth system"

# Run with API key
docker run -e OPENAI_API_KEY="sk-..." devsquad dispatch -t "Design auth system" --backend openai

# Interactive shell
docker run -it devsquad /bin/bash
```

## Configuration File

Create `~/.devsquad.yaml`:

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

Priority: environment variables > config file > defaults

```bash
# After setting config file, no need to specify --backend each time
python3 scripts/cli.py dispatch -t "Design auth system"
# Automatically uses openai backend from config
```

## System Commands

```bash
# List all available roles
python3 scripts/cli.py roles

# Show system status
python3 scripts/cli.py status

# List roles in JSON format
python3 scripts/cli.py roles --format json

# Show version
python3 scripts/cli.py --version    # 3.4.0
```

## Python API Examples

### Basic Dispatch (with real LLM backend)

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),
    model=os.environ.get("OPENAI_MODEL", "gpt-4"),
)

disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch(
    "Design a user authentication system",
    roles=["architect", "pm", "tester"],
    mode="auto",
)

print(result.summary)
print(result.to_markdown())
disp.shutdown()
```

### Mock Mode (no API key needed)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(
    "Design a user authentication system",
    roles=["architect", "pm", "tester"],
)

print(result.summary)
disp.shutdown()
```

### Streaming Output (Python API)

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend("openai", api_key=os.environ["OPENAI_API_KEY"])
disp = MultiAgentDispatcher(llm_backend=backend)

# Use streaming Worker
from scripts.collaboration.worker import Worker
worker = Worker(role="architect", backend=backend, stream=True)
# Worker prints LLM response chunks in real-time

result = disp.dispatch("Design auth system", roles=["architect"])
disp.shutdown()
```

### Using ConfigManager

```python
from scripts.collaboration.config_loader import ConfigManager

config_mgr = ConfigManager()
config = config_mgr.load()
print(f"Backend: {config.backend}")
print(f"Model: {config.model}")
print(f"Timeout: {config.timeout}")
```

### Using CheckpointManager

```python
from scripts.collaboration.checkpoint_manager import CheckpointManager

ckpt_mgr = CheckpointManager(storage_dir="/tmp/checkpoints")

# Create checkpoint from dispatch result
checkpoint = ckpt_mgr.create_checkpoint_from_dispatch(dispatch_result)

# List all checkpoints
checkpoints = ckpt_mgr.list_checkpoints()

# Restore from checkpoint
restored = ckpt_mgr.load_checkpoint(checkpoint.checkpoint_id)
```

## Role Reference

| Role | CLI ID | Aliases | Best For |
|------|--------|---------|----------|
| Architect | `arch` | `architect` | System design, tech stack, performance/security/data architecture |
| Product Manager | `pm` | `product-manager` | Requirements, user stories, acceptance criteria |
| Security Expert | `sec` | `security` | Threat modeling, vulnerability audit, compliance |
| Tester | `test` | `tester`, `qa` | Test strategy, quality assurance, edge cases |
| Coder | `coder` | `solo-coder`, `dev` | Implementation, code review, performance optimization |
| DevOps | `infra` | `devops` | CI/CD, containerization, monitoring, infrastructure |
| UI Designer | `ui` | `ui-designer` | UX flow, interaction design, accessibility |

## CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--task`, `-t` | string | required | Task description |
| `--roles`, `-r` | list | auto | Roles to involve (short IDs: arch/pm/test/coder/ui/infra/sec) |
| `--mode`, `-m` | enum | auto | Execution mode: auto/parallel/sequential/consensus |
| `--backend`, `-b` | enum | mock | LLM backend: mock/trae/openai/anthropic |
| `--base-url` | string | env | Custom API base URL (or OPENAI_BASE_URL env) |
| `--model` | string | env | Model name (or OPENAI_MODEL/ANTHROPIC_MODEL env) |
| `--stream` | flag | false | Stream LLM output in real-time (requires --backend) |
| `--format`, `-f` | enum | markdown | Output: markdown/json/compact/structured/detailed |
| `--dry-run` | flag | false | Simulate without execution |
| `--quick`, `-q` | flag | false | Use quick_dispatch (3 formats) |
| `--action-items` | flag | false | Include H/M/L action items |
| `--timing` | flag | false | Include timing info |
| `--persist-dir` | string | auto | Custom scratchpad directory |
| `--no-warmup` | flag | false | Disable startup warmup |
| `--no-compression` | flag | false | Disable context compression |
| `--skip-permission` | flag | false | Skip permission checks |
| `--no-memory` | flag | false | Disable memory bridge |
| `--no-skillify` | flag | false | Disable skill learning |
| `--permission-level` | enum | DEFAULT | PLAN/DEFAULT/AUTO/BYPASS |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | API key for OpenAI-compatible backends | For `--backend openai` |
| `OPENAI_BASE_URL` | Custom API endpoint (e.g., `https://api.moka-ai.com/v1`) | Optional |
| `OPENAI_MODEL` | Model name (e.g., `gpt-4`, `moka/claude-sonnet-4-6`) | Optional |
| `ANTHROPIC_API_KEY` | API key for Anthropic Claude | For `--backend anthropic` |
| `ANTHROPIC_MODEL` | Model name (e.g., `claude-sonnet-4-20250514`) | Optional |
| `DEVSQUAD_LLM_BACKEND` | Default backend (mock/openai/anthropic) | Optional |
| `DEVSQUAD_LOG_LEVEL` | Logging level | Optional |

## MCP Server (for OpenClaw / Cursor)

```bash
# Install MCP package (optional)
pip install mcp

# Start in stdio mode
python3 scripts/mcp_server.py

# Start in SSE mode
python3 scripts/mcp_server.py --port 8080
```

6 tools exposed: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`.
