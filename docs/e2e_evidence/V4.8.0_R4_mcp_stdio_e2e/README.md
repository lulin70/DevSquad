# V4.8.0 R4 — MCP stdio 接入 e2e 证据

> 日期：2026-10-22 | 对应文档：[docs/integrations/MCP.md](../../integrations/MCP.md) | 设计依据：[V4.8.0_R2-R4_DESIGN.md §3](../../planning/V4.8.0_R2-R4_DESIGN.md)
> 方法：干净 venv（Python 3.14）→ PyPI 安装 devsquad[mcp] → MCP SDK 客户端经 stdio 连接（initialize → tools/list → multiagent_roles）

## 结论

| # | 场景 | 结果 | 证据 |
|---|---|---|---|
| 1 | `pip install devsquad[mcp]`（解析到 mcp 2.3.0） | **失败**：server 启动即退出 "MCP SDK required"（mcp 2.x 移除 `mcp.server.fastmcp`） | [mcp_2.3.0_failure.txt](collected/mcp_2.3.0_failure.txt) |
| 2 | mcp 1.30.0 + 不设 `DEV_SQUAD_MCP_USER_ROLE` | **按设计拒绝**：9 工具可见，但调用返回 fail-closed 拒绝 JSON | [mcp_1.30_no_role_failclosed.txt](collected/mcp_1.30_no_role_failclosed.txt) |
| 3 | mcp 1.30.0 + `DEV_SQUAD_MCP_USER_ROLE=operator` | **通过**：initialize OK；tools/list = 9 工具；`multiagent_roles` 返回角色清单 | [mcp_1.30_operator_success.txt](collected/mcp_1.30_operator_success.txt) |

场景 1 是真实发现，登记为 **TD-076**（pyproject `mcp>0.9` 约束允许 2.x，但代码用 1.x API）。处置遵循设计文档 §3.4 裁定：R4 为纯文档项，不改代码；MCP.md 安装命令带 `"mcp<2"` pin，TD-076 记录修复方案（约束改 `mcp>=1,<2`），留待后续代码窗口实施。

## 环境与复现

```bash
python3 -m venv /tmp/r4_e2e_venv
/tmp/r4_e2e_venv/bin/pip install -i https://pypi.org/simple "devsquad[mcp]"          # 场景 1（装到 mcp 2.3.0）
/tmp/r4_e2e_venv/bin/pip install "mcp<2"                                              # 场景 2/3（降级到 1.30.0）
/tmp/r4_e2e_venv/bin/python collected/check_script.py                                # 默认 operator；unset 角色变量后重跑得场景 2
```

- 安装版本实测：devsquad 4.7.2（PyPI）+ mcp 2.3.0 / 1.30.0
- 验证脚本：[collected/check_script.py](collected/check_script.py)（mcp SDK `ClientSession` + `stdio_client`；断言 tools ≥ 9、期望工具集齐全、multiagent_roles 未被拒绝）

## 边界（如实声明）

- TRAE / Cursor 真实 IDE 界面内的连接截图属"发布前补充证据"（发布就绪清单"测试"面），本批以 SDK 客户端 stdio 全链路为准。
- 场景 3 的 `multiagent_roles` 走 mock 后端（READ_ONLY 工具零 key 可用，与 MCP.md §7 声明一致）。
