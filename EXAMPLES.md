# DevSquad Usage Examples

> Last verified: 2026-04-24 with DevSquad V3.3, backend=openai, model=moka/claude-sonnet-4-6

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
# OAuth2 + 2FA 用户认证系统架构设计

## 核心发现

1. **分层隔离是安全基础** - OAuth2 授权层与 2FA 验证层必须独立部署，
   避免单点攻击面，token 存储与验证逻辑物理隔离
2. **性能与安全的平衡点** - Redis 集群缓存 token（TTL 15min）+
   数据库持久化 refresh token（30天），配合 rate limiting 防暴力破解
```

### Example 2: Multi-Role Collaboration

```bash
python3 scripts/cli.py dispatch \
    -t "Build a real-time chat feature for a SaaS platform" \
    -r arch pm test --backend openai
```

**Real output** (verified 2026-04-24, 144s, 3 roles):

- **Architect**: WebSocket + Redis Pub/Sub 架构方案，支持百万级并发，
  延迟 <50ms，消息持久化与实时传输解耦
- **PM**: 实时聊天功能 PRD，核心业务价值（提升协作效率、增强平台粘性），
  目标用户（B端SaaS团队协作场景）
- **Tester**: 测试方案，核心风险点（WebSocket 稳定性、消息延迟 <500ms、
  并发负载），数据一致性多层验证，安全合规早期介入

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

### Example 4: Consensus Mode

```bash
python3 scripts/cli.py dispatch \
    -t "Choose database for analytics platform" \
    -r arch sec \
    --mode consensus
```

Consensus mode forces a vote when roles disagree. Each role casts a weighted vote, veto power is respected, and human escalation is available for deadlocks.

### Example 5: JSON Output for Automation

```bash
python3 scripts/cli.py dispatch \
    -t "Review codebase for performance issues" \
    -r arch coder \
    --format json
```

JSON output is machine-readable, suitable for CI/CD pipelines or further processing.

## System Commands

```bash
# List all available roles
python3 scripts/cli.py roles

# Show system status
python3 scripts/cli.py status

# List roles in JSON format
python3 scripts/cli.py roles --format json

# Show version
python3 scripts/cli.py --version
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

## MCP Server (for OpenClaw / Cursor)

```bash
# Install MCP package (optional)
pip install mcp

# Start in stdio mode
python3 scripts/mcp_server.py

# Start in SSE mode
python3 scripts/mcp_server.py --port 8080
```

6 tools exposed: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`, `multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`.
