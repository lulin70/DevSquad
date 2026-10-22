# DevSquad MCP Integration Guide

> Connect any MCP-compatible IDE or tool (Cursor, Claude Desktop, TRAE, OpenClaw, etc.) to DevSquad.
> Server implementation: [scripts/mcp_server.py](../../scripts/mcp_server.py) | Verified e2e: [V4.8.0_R4_mcp_stdio_e2e](../e2e_evidence/V4.8.0_R4_mcp_stdio_e2e/README.md)
> This document is the single source of truth for MCP integration. Other docs (README, SKILL.md, QUICKSTART) link here.

---

## 1. Who is this for

You want to invoke DevSquad's multi-agent collaboration **from inside your IDE or AI tool** instead of the command line. Any client that speaks the Model Context Protocol (MCP) works.

Requirements:

- Python ≥ 3.10
- One of the two install forms below (PyPI or repo checkout)

## 2. Install

### Form A: PyPI install (recommended for tool users)

```bash
pip install "devsquad[mcp]" "mcp<2"
```

> **Known issue (TD-076)**: DevSquad's MCP server currently requires `mcp` SDK 1.x. The 2.x SDK renamed `FastMCP` to `MCPServer` and removed `mcp.server.fastmcp`, so a plain `pip install devsquad[mcp]` today resolves to `mcp` 2.x and the server exits with `MCP SDK required`. Pin `mcp<2` until the pyproject constraint is fixed (tracked as [TD-076](../TECH_DEBT.md)). Verified working: `mcp` 1.30.0.

### Form B: repo checkout (for DevSquad contributors)

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad
pip install -r requirements.lock
pip install "mcp<2"
```

Both forms start the server the same way (next section).

## 3. Connect (stdio transport — default)

The server speaks stdio by default. Add it to your MCP client config.

### Generic client config

```json
{
  "mcpServers": {
    "devsquad": {
      "command": "python3",
      "args": ["-m", "scripts.mcp_server"],
      "env": {
        "DEV_SQUAD_MCP_USER_ROLE": "operator"
      }
    }
  }
}
```

- `command` + `args`: starts the server via `python -m scripts.mcp_server` (works for both PyPI and repo installs — the `scripts` package ships with the wheel).
- `env.DEV_SQUAD_MCP_USER_ROLE`: **required for any tool call to succeed**. One of `admin` / `operator` / `viewer` (see §5). Without it, every call is denied (fail-closed).

### Cursor

`.cursor/mcp.json` (project scope) or global config — use the generic JSON above.

### Claude Desktop

`claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Use the same generic JSON above, then restart Claude Desktop.

### SSE transport (optional, remote access)

```bash
python3 -m scripts.mcp_server --port 8080
```

Binds to `127.0.0.1` by default (`--host` to change). If you expose SSE beyond localhost, you accept the network's risk: the SSE endpoint has no built-in authentication. Prefer stdio unless you need remote access.

## 4. Tool catalog (9 tools)

| Tool | Key parameters | Permission level | Purpose |
|---|---|---|---|
| `multiagent_dispatch` | `task` (required), `roles`, `mode`, `output_format`, `dry_run` | WRITE | Full multi-agent collaboration on a task |
| `multiagent_quick` | `task` (required), `output_format`, `include_action_items`, `include_timing` | WRITE | Quick dispatch, compact output |
| `multiagent_roles` | `format` (`text`/`json`) | READ_ONLY | List all agent roles with descriptions |
| `multiagent_status` | — | READ_ONLY | Version, backends, capabilities summary |
| `multiagent_analyze` | `task` (required) | READ_ONLY | Dry-run: suggested roles + complexity, no execution |
| `multiagent_shutdown` | — | ADMIN | Free dispatcher resources |
| `codegraph_explore` | `query` (required), `query_type` (`symbol`/`callers`/`callees`/`dependencies`/`graph`/`similar`) | READ_ONLY | Query the code knowledge graph |
| `codegraph_status` | — | READ_ONLY | Graph build status and stats |
| `codegraph_refresh` | `force` | WRITE | Incremental (default) or full graph rebuild |

## 5. RBAC and fail-closed behavior

Every tool call passes two gates before execution.

**Gate 1 — permission level.** Each tool requires a level (`READ_ONLY < WRITE < ADMIN`). Your role maps to a level:

| Role (`DEV_SQUAD_MCP_USER_ROLE`) | Level | Can call |
|---|---|---|
| `viewer` | READ_ONLY | roles / status / analyze / codegraph_explore / codegraph_status |
| `operator` | WRITE | all of the above + dispatch / quick / codegraph_refresh |
| `admin` | ADMIN | everything, including shutdown |

Optional `DEV_SQUAD_MCP_USER_ID` sets the caller identity (default `mcp_user`; only relevant when an auth_manager is configured).

**Gate 2 — RBAC (dispatch tools only).** `multiagent_dispatch` and `multiagent_quick` additionally check the requested `roles`/`mode` against the RBAC permission matrix. Without an auth_manager, this runs in open mode (Gate 1 remains the effective gate).

**Fail-closed: four denial cases.** A call is denied — never silently downgraded — when:

1. No caller identity: `DEV_SQUAD_MCP_USER_ROLE` is not set
2. The role value is empty
3. The role is not one of `admin`/`operator`/`viewer`
4. The role's level is below the tool's required level

Denied calls return a JSON body instead of a result:

```json
{"error": "No user context (fail-closed): caller identity unknown", "success": false, "denied": true}
```

## 6. Verify the connection

In your MCP client (or any MCP inspector):

1. `initialize` — handshake succeeds, server name is `DevSquad`
2. `tools/list` — expect the 9 tools of §4
3. Call `multiagent_roles` — expect a role list such as:

```
**arch** — System design, tech stack, API design, performance/security/data architecture
**pm** — Requirements analysis, user stories, acceptance criteria
...
```

The verification script used for the archived e2e run is at [collected/check_script.py](../e2e_evidence/V4.8.0_R4_mcp_stdio_e2e/collected/check_script.py).

## 7. Key boundary (honest scope)

- **Zero-key usable tools**: `multiagent_roles`, `multiagent_status`, `multiagent_analyze`, `codegraph_*` (read-only family). These run with the mock backend and need no provider key.
- **Real LLM output** from `multiagent_dispatch` / `multiagent_quick` requires a provider key (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, per the backend configured for the dispatcher). Without a key, dispatch runs on the mock backend.
