# V4.8.0 R2 — persona 三通道 e2e 证据

> 日期：2026-10-22 | 对应文档：[QUICKSTART.md](../../../QUICKSTART.md)（三通道重构） | 设计依据：[V4.8.0_R2-R4_DESIGN.md §1](../../planning/V4.8.0_R2-R4_DESIGN.md)
> 方法：每通道一个干净 venv（Python 3.14），模拟真实用户从安装到第一份产出的完整路径

## 结论

| # | 通道 | 场景 | 结果 | 证据 |
|---|---|---|---|---|
| A | IDE 用户 | 干净 venv → `pip install "devsquad[mcp]" "mcp<2"` → MCP stdio 探活（operator 角色） | **通过**：initialize OK；tools/list = 9 工具；`multiagent_roles` 返回角色清单 | [channel_a_mcp_operator_success.txt](collected/channel_a_mcp_operator_success.txt) |
| B1 | CLI 用户（当前发布） | 干净 venv → PyPI devsquad 4.7.2 → 管道默认输入跑 `devsquad init`（mock）→ `devsquad demo` | **通过**：向导走完并保存配置；demo 3 场景 3/3 成功 | [channel_b_pypi4472_init_baseline.txt](collected/channel_b_pypi4472_init_baseline.txt) / [demo](collected/channel_b_pypi4472_demo_baseline.txt) |
| B2 | CLI 用户（本 PR 分支构建） | 同上 venv 重装分支构建 → init → demo | **通过**：init 新增分流输出（mock → "Zero-key mode" + `devsquad demo` 指引；完成横幅差异化）；demo 3/3 成功 | [channel_b_branch_init_zerokey_branching.txt](collected/channel_b_branch_init_zerokey_branching.txt) / [demo](collected/channel_b_branch_demo.txt) |
| C | 仓库维护者 | QUICKSTART 通道 C wrapper YAML 静态校验 + doc_command 门禁 | **通过**：YAML 可解析、`uses:` 路径在仓库存在（首个含该 workflow 的 tag 为 v4.8.0）、doc_command 36 条命令全绿 | [channel_c_wrapper_yaml_validation.txt](collected/channel_c_wrapper_yaml_validation.txt) |
| D | 门禁负向演示（PRD 验收） | 临时植入 `devsquad nosuchcmd --demo-check` → 运行门禁 → 移除 → 再运行 | **按预期**：植入 → FAIL（exit 1，附 QUICKSTART.md:81 定位）；移除 → PASS（exit 0，36 条全绿） | [red](collected/doc_command_negative_red.txt) / [green](collected/doc_command_negative_green.txt) |

## 环境与复现

```bash
# 通道 A（复用 R4 验证脚本）
python3 -m venv /tmp/r2_e2e_a
/tmp/r2_e2e_a/bin/pip install "devsquad[mcp]" "mcp<2"
CHECK_ROLE=operator /tmp/r2_e2e_a/bin/python docs/e2e_evidence/V4.8.0_R4_mcp_stdio_e2e/collected/check_script.py

# 通道 B（先基线后分支构建）
python3 -m venv /tmp/r2_e2e_b
/tmp/r2_e2e_b/bin/pip install devsquad                       # B1：PyPI 4.7.2 基线
printf '\n\n\n\n\n\n' | devsquad init && devsquad demo
/tmp/r2_e2e_b/bin/pip install --force-reinstall --no-deps /path/to/DevSquad   # B2：本 PR 工作树构建
printf '\n\n\n\n\n\n' | devsquad init && devsquad demo        # 观察分流输出

# 通道 C + 门禁负向
python3 scripts/check_config_consistency.py                  # doc_command 全绿（exit 0）
# 在 QUICKSTART.md 任一代码块植入 devsquad nosuchcmd → 重跑（exit 1，FAIL 带文件:行号）
```

- 通道 B 管道输入 `\n`×6 即向导全默认（Generic 项目 + mock 后端 + 语言 auto + 功能默认），等价零 key 用户一路回车
- B2 分支构建：`pip install --no-deps` 指向本 PR 工作树（版本号仍为 4.7.2，代码含 R2 分流改动）

## 边界（如实声明）

- 通道 C 的**完整外部 PR e2e**（真实 fork 仓库挂 wrapper → PR → 收到协议 v1 评论）属发布后 T-3 批次（zeroclaw）：gate 安装的 PyPI 版本须为 4.8.0 才含 diff findings 接线，本批仅静态校验 YAML 语法、`uses:` 路径与 doc_command 门禁，不谎报覆盖。
- 通道 A 的 TRAE / Cursor IDE 界面内截图同 R4 边界声明，以 SDK 客户端 stdio 全链路为准。
- 通道 B2 的 key 缺失分流（openai/anthropic 无 key → 警告 + 过渡指引）由单测矩阵覆盖（`tests/test_cli_deep_v362.py` TestInitWizard，后端 × key 有无 5 组），e2e 不重复注入真实 key。
