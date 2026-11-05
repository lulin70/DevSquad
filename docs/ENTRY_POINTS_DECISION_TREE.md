# DevSquad Entry Points Decision Tree

## Overview

DevSquad provides 7 different entry points for invoking multi-agent collaboration. This guide helps you choose the right one for your use case.

---

## Quick Decision Tree

```
START: How do you want to use DevSquad?
│
├─ Inside an AI IDE (TRAE, Cursor, Claude Desktop)?
│  └─ YES → Use [Method 1: TRAE Skill](#method-1-trae-skill-recommended)
│
├─ Building an application that needs DevSquad?
│  ├─ Need IDE integration (LSP/MCP protocol)?
│  │  └─ YES → Use [Method 3: MCP Server](#method-3-mcp-server)
│  │
│  ├─ Need HTTP REST API?
│  │  └─ YES → Use [Method 5: REST API](#method-5-rest-api-server)
│  │
│  └─ Embedding in Python code?
│     └─ YES → Use [Method 2: Python API](#method-2-python-api)
│
├─ Running from command line / CI/CD?
│  └─ YES → Use [Method 4: CLI](#method-4-cli)
│
├─ Need web UI for team collaboration?
│  └─ YES → Use [Method 6: Dashboard](#method-6-web-dashboard)
│
└─ First time setup / production deployment?
   └─ YES → Use [Method 7: Startup Script](#method-7-startup-script-startsh)
```

---

## Method Comparison Table

| Method | Use Case | Complexity | Real AI | Best For |
|--------|----------|------------|---------|----------|
| **1. TRAE Skill** | AI IDE integration | Low | Host LLM | Interactive development, rapid prototyping |
| **2. Python API** | Programmatic access | Low | Optional¹ | Application embedding, automation scripts |
| **3. MCP Server** | IDE/tool integration | Medium | Optional¹ | IDE plugins, external tool orchestration |
| **4. CLI** | Command line / CI | Low | Optional¹ | Shell scripts, CI/CD pipelines, batch jobs |
| **5. REST API** | HTTP integration | Medium | Optional¹ | Microservices, webhooks, external systems |
| **6. Dashboard** | Visual monitoring | Medium | Optional¹ | Team collaboration, non-technical users |
| **7. start.sh** | One-click deployment | Low | N/A | Initial setup, production deployment |

¹ Real AI output requires API keys (OpenAI/Anthropic/Moka). Without keys, returns mock/template output.

---

## Detailed Method Descriptions

### Method 1: TRAE Skill (Recommended)

**When to use**:
- Working inside an AI IDE (TRAE, Cursor, Claude Desktop)
- Need real AI collaboration responses
- Want conversational multi-agent interaction

**How it works**:
- Invoked via `/skill devsquad <task description>`
- Uses host IDE's LLM for role responses
- Returns structured markdown reports

**Example**:
```
User: /skill devsquad Design a user authentication system --roles architect security
IDE: [DevSquad orchestrates architect and security roles, returns consensus report]
```

**Pros**:
- ✅ Seamless IDE integration
- ✅ Real AI output (uses host LLM)
- ✅ No API key management needed
- ✅ Interactive and conversational

**Cons**:
- ❌ Only works inside AI IDEs
- ❌ Cannot be embedded in applications

**Setup**: None (pre-installed in TRAE IDE)

---

### Method 2: Python API

**When to use**:
- Embedding DevSquad in Python applications
- Need programmatic control over dispatch
- Building automation scripts or workflows

**How it works**:
```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design auth system", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

**Pros**:
- ✅ Full programmatic control
- ✅ Easy to integrate in Python code
- ✅ Flexible configuration
- ✅ Supports both mock and real LLM modes

**Cons**:
- ❌ Requires Python 3.9+
- ❌ Real AI output needs API key setup

**Setup**:
```bash
pip install devsquad
```

---

### Method 3: MCP Server

**When to use**:
- Integrating DevSquad with IDEs via MCP protocol
- Building tool orchestration systems
- Need standardized protocol for AI tools

**How it works**:
- Starts MCP server (stdio or SSE transport)
- Exposes 9 MCP tools: dispatch, roles, status, analyze, etc.
- IDE/client calls tools via JSON-RPC

**Example**:
```bash
# Start server
python3 -m scripts.mcp_server

# Or with SSE transport for remote access
python3 -m scripts.mcp_server --port 8080
```

**MCP Tools Exposed**:
- `multiagent_dispatch`: Full collaboration (WRITE)
- `multiagent_roles`: List available roles (READ_ONLY)
- `multiagent_status`: System capabilities (READ_ONLY)
- `multiagent_analyze`: Dry-run analysis (READ_ONLY)
- `codegraph_explore`: Query code graph (READ_ONLY)
- And 4 more...

**Pros**:
- ✅ Standardized protocol
- ✅ IDE-agnostic integration
- ✅ RBAC and permissions support
- ✅ Both stdio and HTTP transports

**Cons**:
- ❌ Requires MCP-compatible client
- ❌ More complex setup

**Setup**: See [docs/integrations/MCP.md](../integrations/MCP.md)

---

### Method 4: CLI

**When to use**:
- Running DevSquad from terminal
- CI/CD pipeline integration
- Shell script automation
- Session management and replay

**How it works**:
```bash
# Basic dispatch
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec

# With real LLM backend
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Task" -r arch --backend openai

# Session management
python3 scripts/cli.py sessions list
python3 scripts/cli.py sessions show <session-id>
python3 scripts/cli.py dispatch --resume <session-id>
```

**Pros**:
- ✅ No IDE required
- ✅ Perfect for CI/CD
- ✅ Session persistence and replay
- ✅ Dry-run mode available

**Cons**:
- ❌ Text-only output
- ❌ Less interactive than IDE

**Setup**: None (part of repo)

---

### Method 5: REST API Server

**When to use**:
- Integrating with external systems via HTTP
- Building custom UIs on top of DevSquad
- Monitoring and metrics collection
- Microservices architecture

**How it works**:
```bash
# Install dependencies
pip install -e ".[api]"

# Start FastAPI server
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000

# Access Swagger UI
open http://localhost:8000/docs
```

**Key Endpoints**:
```bash
# Lifecycle management
GET /api/v1/lifecycle/phases
GET /api/v1/lifecycle/status

# Metrics & monitoring
GET /api/v1/metrics/current
GET /api/v1/gates/status

# Health check
GET /api/v1/health
```

**Pros**:
- ✅ HTTP REST interface
- ✅ Swagger documentation
- ✅ Easy external integration
- ✅ Prometheus metrics support

**Cons**:
- ❌ Requires FastAPI dependencies
- ❌ Network overhead

**Setup**: Requires `pip install -e ".[api]"`

---

### Method 6: Web Dashboard

**When to use**:
- Team collaboration and monitoring
- Non-technical stakeholders need access
- Visual project lifecycle tracking
- Role-based access control needed

**How it works**:
```bash
# Start Streamlit dashboard
streamlit run scripts/dashboard.py

# Or using new package path (recommended)
streamlit run scripts/dashboard/app.py

# Open browser
open http://localhost:8501
```

**Features**:
- Real-time lifecycle phase monitoring
- CLI command mapping visualization
- Gate status tracking
- Performance metrics display
- RBAC (Admin/Operator/Viewer roles)

**Pros**:
- ✅ Visual and intuitive
- ✅ No coding required
- ✅ Multi-user collaboration
- ✅ Role-based permissions

**Cons**:
- ❌ Requires Streamlit dependencies
- ❌ Not suitable for automation

**Setup**: Requires `pip install -e ".[api]"` (includes Streamlit)

**Note**: `scripts/dashboard.py` is deprecated (V4.10.1). Use `scripts/dashboard/app.py` directly.

---

### Method 7: Startup Script (start.sh)

**When to use**:
- First-time setup
- Production deployment
- Unified environment initialization
- Running API + Dashboard together

**How it works**:
```bash
# One-click startup (4 phases: env check → DB init → frontend build → service start)
./scripts/start.sh

# Launch API and Dashboard together
./scripts/start.sh --dashboard

# Override API port
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# Show help
./scripts/start.sh --help
```

**What it does**:
1. Validates environment (Python version, dependencies)
2. Initializes database schema
3. Builds frontend assets (if dashboard enabled)
4. Starts services (API server + optional dashboard)

**Pros**:
- ✅ One command setup
- ✅ Environment validation
- ✅ Reproducible builds (with requirements.lock)
- ✅ Production-ready

**Cons**:
- ❌ Less granular control
- ❌ Overkill for simple tasks

**Setup**: None (script included in repo)

---

## Decision Scenarios

### Scenario 1: "I'm developing in TRAE IDE"
→ **Use Method 1: TRAE Skill**

You're already in an AI IDE with LLM access. The skill integrates seamlessly and provides real AI collaboration without API key setup.

---

### Scenario 2: "I need to automate DevSquad in my Python app"
→ **Use Method 2: Python API**

Direct Python integration gives you full control. Configure LLM backend if you need real AI output, or use mock mode for deterministic testing.

---

### Scenario 3: "I want to add DevSquad to my IDE plugin"
→ **Use Method 3: MCP Server**

MCP provides a standardized protocol. Start the server once, and any MCP-compatible client can call it. Supports both stdio (local) and HTTP (remote) transports.

---

### Scenario 4: "I need to run DevSquad in GitHub Actions"
→ **Use Method 4: CLI**

CLI is perfect for CI/CD. No GUI, no IDE, just command-line input and structured output. Supports session replay for debugging.

---

### Scenario 5: "I'm building a microservice that calls DevSquad"
→ **Use Method 5: REST API**

REST API provides HTTP endpoints. Your microservice can POST tasks, GET results, and monitor metrics. Language-agnostic integration.

---

### Scenario 6: "My product manager wants to see DevSquad progress"
→ **Use Method 6: Dashboard**

Web UI is visual and requires no coding. PMs and stakeholders can track lifecycle phases, gate status, and metrics in real-time.

---

### Scenario 7: "I'm deploying DevSquad to production for the first time"
→ **Use Method 7: start.sh**

The startup script handles all initialization steps in correct order. Use with `requirements.lock` for reproducible deployments.

---

## Common Combinations

### Development Workflow
1. **Local iteration**: TRAE Skill (Method 1) for interactive development
2. **Automated testing**: Python API (Method 2) in test suite
3. **CI validation**: CLI (Method 4) in GitHub Actions

### Team Collaboration
1. **Developers**: TRAE Skill (Method 1) or Python API (Method 2)
2. **DevOps**: CLI (Method 4) for deployment automation
3. **Stakeholders**: Dashboard (Method 6) for monitoring

### Production Deployment
1. **Initial setup**: start.sh (Method 7) for environment preparation
2. **Service layer**: REST API (Method 5) for external integration
3. **Monitoring**: Dashboard (Method 6) + Prometheus metrics

---

## Migration Guide

### From CLI to Python API
```python
# Before (CLI)
# python3 scripts/cli.py dispatch -t "Task" -r arch

# After (Python API)
from scripts.collaboration.dispatcher import MultiAgentDispatcher
disp = MultiAgentDispatcher()
result = disp.dispatch("Task", roles=["architect"])
print(result.to_markdown())
disp.shutdown()
```

### From Python API to MCP
```python
# Before (Python API - direct call)
result = disp.dispatch("Task", roles=["architect"])

# After (MCP - via JSON-RPC)
# Client sends MCP tool call:
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "multiagent_dispatch",
    "arguments": {
      "task_description": "Task",
      "roles": ["architect"]
    }
  }
}
```

### From MCP to REST API
```bash
# Before (MCP - protocol-specific)
# Requires MCP client library

# After (REST API - standard HTTP)
curl -X POST http://localhost:8000/api/v1/dispatch \
  -H "Content-Type: application/json" \
  -d '{"task": "Task", "roles": ["architect"]}'
```

---

## FAQs

### Q: Which method gives real AI output without API keys?
**A**: Only Method 1 (TRAE Skill) uses the host IDE's LLM. All other methods require API keys for real AI output (or return mock responses).

### Q: Can I use multiple methods together?
**A**: Yes. For example, use TRAE Skill for development, Python API for testing, and REST API for production integration.

### Q: Which method is fastest?
**A**: Method 2 (Python API) has lowest overhead. Method 1 (TRAE Skill) depends on host LLM speed. Method 5 (REST API) adds network latency.

### Q: Which method requires least setup?
**A**: Method 1 (TRAE Skill) - pre-installed in TRAE IDE, no setup needed.

### Q: Can I switch methods mid-project?
**A**: Yes, all methods produce the same structured output. You can use CLI for prototyping, then migrate to Python API for production.

### Q: Which method supports RBAC?
**A**: Method 3 (MCP Server) and Method 6 (Dashboard) have built-in RBAC support.

---

## Next Steps

1. **Choose your method** based on the decision tree above
2. **Follow the quickstart** in [SKILL.md](../SKILL.md) or [QUICKSTART.md](../QUICKSTART.md)
3. **Configure API keys** if using real LLM backends (see [docs/configuration/LLM_BACKENDS.md](../configuration/LLM_BACKENDS.md))
4. **Review examples** in [examples/](../../examples/) directory

---

## References

- [SKILL.md](../SKILL.md) - Main documentation and all 7 methods
- [QUICKSTART.md](../QUICKSTART.md) - 5-minute getting started guide
- [MCP Integration Guide](../integrations/MCP.md) - Detailed MCP setup
- [API Documentation](../api/REST_API.md) - REST API reference
- [Deployment Guide](../deployment/PRODUCTION.md) - Production setup with start.sh
