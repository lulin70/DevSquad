"""R4 e2e verification: connect to devsquad MCP server via stdio.

Steps (per docs/integrations/MCP.md design):
  1. initialize handshake
  2. tools/list -> expect >= 9 tools
  3. call multiagent_roles (READ_ONLY, zero key) -> expect success

Run inside a clean venv that has devsquad[mcp] installed.
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
    role = os.environ.get("CHECK_ROLE", "operator")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "scripts.mcp_server"],
        env={"DEV_SQUAD_MCP_USER_ROLE": role},
    )
    failures: list[str] = []
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
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
            if result.isError:
                failures.append("multiagent_roles returned isError=True")
            if '"denied": true' in text:
                failures.append(f"multiagent_roles denied: {text[:200]}")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: initialize + tools/list>=9 + multiagent_roles all OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
