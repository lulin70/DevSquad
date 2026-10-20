# P0 卫生批复盘（V4.7.2 发布批）

> **日期**: 2026-10-20
> **批次**: P0 卫生批（执行计划 [2026-10-20_value_proposal_execution_plan.md](../planning/2026-10-20_value_proposal_execution_plan.md)，D1-D4 裁定项）
> **结果**: 全部 6 个工作项完成，V4.7.2 已发布（tag `v4.7.2`、GitHub Release、PyPI 实测就位）
> **版本**: V4.7.2（PATCH：无新功能、无破坏性变更，卫生与文档真实性修复）

## 1. 执行成果（全部实测）

| 工作项 | Commit | 实测结果 |
|--------|--------|----------|
| P0-W4 四份文档入库 | `cc526a7` | 4 文档入库（D1 已授权） |
| P0-W1 六处过时版本串清除 + 门禁负向扫描 | `00806ca` | 用户可见面 6 处清除；版本一致性门禁 73→81 项（负向扫描 +1）；负向测试（植入假 `DevSquad V0.0` 证明扫描转红）通过 |
| P0-W2 状态文档治理 | `a16b1cd` | PROJECT_STATUS 刷新至发布现实；RELEASE_CHECKLIST §5/§8 增实测要求 |
| P0-W3 TD-071 api 路径真实测量 | `da765bb` | openai 后端 p50 869.54ms / p95 1234.56ms，记录为 `v470_baseline_api`（无 `_stub` 后缀）；host 路径保持诚实 `environment_blocked` stub |
| 版本升 4.7.2 + TRAE 四层缓存同步 | `66ec86a` | 门禁 81/81 全绿；TRAE 缓存同步 8/8（4 层）；26 文件版本链零伤历史 |
| T18 测试 ruff 格式修复 | `13dbf4c` | 55/55 测试通过；`ruff format --check` 全绿 |
| dispatcher-size 基线刷新 | `1a54de9` | 门禁 PASS（见 §3 事件） |

**发布链**: bump → 格式修复 → 预发布刷新 → 基线刷新（tag 目标）→ tag `v4.7.2` → Release 工作流 6/6 job 全绿（7m04s）→ 发布后刷新（`3cae4f5`）。

**发布前验证**: 本地全量验收（keyless 等价，凭据置空，镜像 release final-gate）9774 passed / 6 skipped / 0 failed；wheel 干净构建（清除 stale build/lib，V4.7.1 教训防线生效）+ 干净 venv 模拟真实用户预发布验证（--version / --help / demo）通过。

**发布后验证（PyPI 真实安装面）**: `pip install devsquad==4.7.2`（官方源）+ `--version` = `DevSquad 4.7.2` + `--help` 自述无过时版本串 + `demo` exit 0，全部通过。

## 2. 做得好的

1. **文档先行、万事留痕**: 执行计划先行且是唯一执行依据；每步实测数字入 CHANGELOG / PROJECT_STATUS / 本复盘，无一处沿用旧数字。
2. **门禁体系按设计生效**: V4.5.24 size gate 在 **PR 期**拦截基线越界（本次事件），而非 V4.5.24 时代的 tag 期两次失败——拦截点前移的价值得到实证。
3. **负向测试证明门禁不是摆设**: T18 植入假版本串证明负向扫描真的会转红，81 项含真实防御。
4. **版本链编辑零伤历史**: README×3 / CLAUDE / SPEC 的历史版本描述段全部保留，定点前插而非 replace_all（V4.5.24 教训防线生效）。
5. **诚实披露**: 镜像 pip 源装不到 4.7.2 时未谎称"本地安装验证通过"，改用官方源实测并披露镜像延迟事实；skip 测试逐个定位（6 个全部环境条件性）并留痕。

## 3. 事件与处置

**事件（无故障遗留，已闭环）**: P0-W1 负向扫描使 `check_version_consistency.py` 从 735 增至 872 LOC，超过 800 上限与 dispatcher-size 基线，CI lint job 在 PR 期拦截（`4a80a2f` / `13dbf4c` 两个 CI run 同因红）。
- **处置**: 按 test.yml 文档指定的同一 PR 意识性刷新工作流 `--write-baseline` 刷新快照（`1a54de9`）；刷新 diff 中的其余条目均为 800 以下阈值内历史漂移（不改变门禁行为），已在 commit message 披露；CHANGELOG 4.7.2 条目补记。
- **为何本地未拦**: `acceptance_local.sh` 镜像 release final-gate 的 pytest 面，不镜像 CI lint job 的 size gate——两个门禁面不同。
- **改进候选（记入 P1 池，不在本批扩散）**: `acceptance_local.sh` 增补 dispatcher-size gate 调用，使本地验收与 CI lint 面一致。

## 4. 教训（写入项目记忆）

1. **增长 scripts/*.py 文件后，push 前本地跑一次 `python scripts/check_dispatcher_size.py`**——超过 800 LOC 且超基线即被 CI 拦截；刷新基线必须与增长同一批意识性提交。
2. **发布后验证须指定官方源**：本机 pip 全局配置清华 TUNA 镜像（同步延迟），新版本发布后 `pip install devsquad==X.Y.Z` 在镜像就绪前会失败；验证用 `-i https://pypi.org/simple`，且 CI 内部已验证的安装不能替代本机实测。
3. **`--version` 实测格式为 `DevSquad X.Y.Z`（无 V 前缀）**——文档中的"预期输出"注释必须来自实测，不能想当然（本批修正了 README×3 / CLAUDE / SPEC 共 5 处错误注释）。
4. **sub-800 LOC 的静默增长不在门禁射程内**（如 `check_skill_contract.py` 257→470）：门禁只拦"超 800 且超基线"，阈值内漂移靠复盘与重构治理，属设计取舍而非缺陷。

## 5. 残留与移交

- **TD-071 host 路径**: 仍为诚实 `environment_blocked` stub，需 TRAE IDE 会话环境重测（P0-W3 已留痕，后续批处理）。
- **TRAE 技能列表确认**: 缓存已同步 8/8，但 `Cmd+Shift+P → Developer: Reload Window` 为用户手动步骤，技能列表版本以用户 Reload 后所见为准。
- **P1 池**（达成共识后按生命周期推进）: R1 devsquad-gate Action / R2 persona 通道 / R3 dogfooding / R4 MCP 文档 + E1 审计 + 本批复盘新增的 acceptance 面一致性改进候选。

## 6. 裁定执行核对（执行计划 §4.2）

- 默认裁定"独立小发布含 tag"**已执行**: tag `v4.7.2` 于 `1a54de9`，GitHub Release 与 PyPI 均由发布流水线自动就位，无事后改单。

---

*复盘依据全部来自本批实测命令输出（验收日志、CI run、PyPI JSON API、gh release view）；无推测数字。*
