"""R4 e2e verification: connect to devsquad MCP server via stdio.

Steps (per docs/integrations/MCP.md):
  1. initialize handshake
  2. tools/list -> expect >= 9 tools
  3. call multiagent_roles -> success with a role, fail-closed denial without

Modes (CHECK_ROLE env var):
  - unset  -> server gets no DEV_SQUAD_MCP_USER_ROLE: multiagent_roles MUST be
              denied (fail-closed evidence)
  - set (e.g. operator) -> server gets the role: multiagent_roles MUST succeed

Run inside a clean venv that has devsquad[mcp] and mcp 1.x installed.
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_MIN_TOOLS = 9
EXPECTED_TOOLS = {
    "multiagent_dispatch",
    "multiagent_quick",
    "multiagent_roles",
    "multiagent_status",
    "multiagent_analyze",
    "multiagent_shutdown",
    "codegraph_explore",
    "codegraph_status",
    "codegraph_refresh",
}


async def run() -> int:
    role = os.environ.get("CHECK_ROLE")
    env = {"DEV_SQUAD_MCP_USER_ROLE": role} if role else {}
    mode = role if role else "<unset — expect fail-closed denial>"
    print(f"[0] mode: role={mode}")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "scripts.mcp_server"],
        env=env,
    )
    failures: list[str] = []
    async with (
        stdio_client(server_params) as (read, write),
        ClientSession(read, write) as session,
    ):
        init = await session.initialize()
        print("[1] initialize OK")
        print(f"    server name={init.serverInfo.name} version={init.serverInfo.version}")

        tools_resp = await session.list_tools()
        tool_names = sorted(t.name for t in tools_resp.tools)
        print(f"[2] tools/list -> {len(tool_names)} tools")
        for name in tool_names:
            print(f"    - {name}")
        if len(tool_names) < EXPECTED_MIN_TOOLS:
            failures.append(f"tool count {len(tool_names)} < {EXPECTED_MIN_TOOLS}")
        missing = EXPECTED_TOOLS - set(tool_names)
        if missing:
            failures.append(f"missing expected tools: {sorted(missing)}")

        result = await session.call_tool("multiagent_roles", {})
        print(f"[3] multiagent_roles -> isError={result.isError}")
        text = ""
        for block in result.content or []:
            if getattr(block, "type", "") == "text":
                text = block.text
                break
        print(f"    text[:400]={text[:400]!r}")
        denied = '"denied": true' in text
        if role and denied:
            failures.append(f"expected success with role={role}, got denial: {text[:200]}")
        if not role and not denied:
            failures.append(f"expected fail-closed denial without role, got: {text[:200]}")
        if result.isError:
            failures.append("multiagent_roles returned isError=True")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: initialize + tools/list>=9 + multiagent_roles behaved as expected")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
