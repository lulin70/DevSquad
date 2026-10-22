# P1 工作流进场批复盘（V4.8.0 发布批）

> **日期**: 2026-10-22
> **批次**: P1 工作流进场批（执行计划 [2026-10-20_value_proposal_execution_plan.md](../planning/2026-10-20_value_proposal_execution_plan.md) §5，PRD [V4.8.0_workflow-entry_PRD.md](../prd/V4.8.0_workflow-entry_PRD.md)）
> **结果**: 全部工作项完成（W0/R1/R2/R3/R4/E1 + 发布），V4.8.0 已发布（tag `v4.8.0`、GitHub Release、PyPI 实测就位）；R1 验收①外部试装两段式闭环，T-2 dogfood 入仓
> **版本**: V4.8.0（MINOR：新分发形态 devsquad-gate + persona 通道 + dogfooding 报告 + MCP 文档）

## 1. 执行成果（全部实测）

| 工作项 | PR | 实测结果 |
|--------|-----|----------|
| P1-W0 acceptance 面一致性 | — | `acceptance_local.sh` 增补 dispatcher-size gate（P0 复盘改进候选闭环） |
| P1-R1 devsquad-gate | #50 | 可复用 workflow + diff 通道模式接线（`diff_pattern_scanner.py`，零新检查逻辑） |
| P1-R2 persona 通道 | #54 | QUICKSTART 三通道重写 + init 后端分流 + doc_command 门禁 36 条 |
| P1-R3 dogfooding 自证链 | #53 | 季度报告生成器 + 首期 2026-Q4 报告（配置一致性 7/7、9873 测试，数字可复现） |
| P1-R4 MCP 文档 | #52 | 集成指南单一事实源 + stdio e2e 证据 |
| TD-076 mcp 约束 | #55 | `>=1,<2` 收紧 |
| P1-E1 消费者审计 | #56/#58 | 六项裁定：teach/taste-dials=KEEP、prototype/meta-skill-layering=FREEZE、impeccable 接线 doctor、live-browser 移除——扩张冻结解除 |
| 版本升 4.8.0 + 试装修复 | #59 | 版本一致性 82/82；T-3 第一段两缺陷（F-1/F-2）修复并入 |
| T-3 外部试装（两段式） | zeroclaw #38 | 第一段 run 39734750597 机制面全过；第二段 run 39738128709 findings 面 fail/BREAK 2/exit 1（T-4 同场）；5 次运行 1 条评论幂等 |
| T-2 dogfood | #60 | 本仓自用 `@v4.8.0` gate：自触发 pass + 协议 v1 评论（run 39739886471） |

**发布链**: PR #59 squash merge（bade9bed）→ tag `v4.8.0` → release.yml 流水线 [run 39736569104](https://github.com/lulin70/DevSquad/actions/runs/39736569104) Build→Release E2E→Publish PyPI→GitHub Release 全绿 → 干净房安装（`--index-url https://pypi.org/simple/`，规避清华镜像滞后）+ `--version` + demo 冒烟通过。

**发布后验证（当日完成，不欠账）**: T-3 第二段 findings 面（注入 → BREAK 2 → fail → exit 1，fail-closed 失败路径真实生效）；T-2 dogfood（gate 跑在自己身上）；T-5 零 secrets 全程覆盖（无任何 secrets 配置，确定性层独立判定）。

## 2. 做得好的

1. **两段式试装裁定的价值被实证**：第一段（发布前）抓到两个真实缺陷（F-1 QUICKSTART 转 writing 丢失 permissions 契约、F-2 私有仓 diff 拉取恒 blocked），当日修复并入发布——首例外部消费即暴露文档转写缺陷与私有仓边界，结构防腐测试（T-1）无法覆盖 workflow_call 真实调用面。
2. **fail-closed 全路径诚实**：blocked 两次诚实披露（含 blocked_reason）、失败注入真实转红（exit 1）、零 secrets 不谎报——设计 §5 矩阵每一行都有对应实测 run。
3. **发布纪律不欠账**：发布后批次（第二段试装、T-2 dogfood、PROJECT_STATUS 实测刷新）发布当日全部完成，无一拖到发布后 1-2 周。
4. **幂等协议经久验证**：跨两段、跨 5 次运行（含二分诊断期）仅 1 条评论；`--edit-last --create-if-none` 形态经受住多次重触发。
5. **零新检查逻辑约束守住了**：diff 通道接线（§7.1 修正）全部复用 ReviewCheckers 既有正则与分类，实现即设计原义，无需范围重裁定。

## 3. 事件与处置

| 事件 | 处置 | 教训去向 |
|---|---|---|
| F-1：caller 未授予 `pull-requests: write` → startup_failure（无 job 创建、GitHub 文档无此错误文本） | 实证二分定位（远程✗→本地✗→最小✓→逐项加回 permissions✗）；QUICKSTART 通道 C 补 permissions + 失败说明 | §4.1 |
| F-2：私有仓 diff 拉取匿名 404 → 第一次修复（认证 curl diff_url）仍败——302 跨域重定向剥离 Authorization 头 | REST pulls 端点（`Accept: application/vnd.github.v3.diff`）直返无重定向；token 走 env | §4.2 |
| V-1：`review --diff-file` 退出码恒 0、无 findings——模式扫描未接线 diff 通道（设计期发现） | rev2 §7.1 接线既有正则（PRD 原义，非范围变更）；探针教训：CLI 行为探针必须凭据置空 | §4.3 |
| 发布后本机 pip 装不到 4.8.0 | 清华镜像同步滞后（P0 教训防线生效）：`--index-url https://pypi.org/simple/` 绕过 | P0 复盘已录，防线复验有效 |
| F-D1：dogfood 后首个 docs 批（P1 closeout）被自己的 gate 打红——证据文档引用注入物原文（字面标记词/调试调用）计入 finding；预扫 3 处命中 | 本地预扫（`diff_pattern_scan_to_dicts` 直跑 closeout diff）提前发现，文档改以模式名转述（原文以 PR #38 diff/run 日志为锚）；根因 = diff 模式扫描绕过 include/exclude 且扩展名盲扫——**dogfood 第三个真实发现** | §4.7 + §5（修复提案：findings 按 `file_path` 过滤，随 4.8.1） |

## 4. 教训（写入项目记忆）

1. **workflow_call 权限语义**：被调方声明的 `permissions` 不得超过调用方授予——超出即 startup_failure（无 job 创建、check-suite 无 check-run、文档难查）；消费方 wrapper 必须显式授予被调方声明的最小集。该契约已写入 QUICKSTART 通道 C。
2. **私有仓 PR diff 认证拉取**：匿名 curl 私有仓 404；认证 curl `github.com/.../N.diff` 因 302 跨域重定向（→ patch-diff.githubusercontent.com）被剥离 Authorization 头——正确做法是 REST pulls 端点直返（`Accept: application/vnd.github.v3.diff`）。
3. **CLI 行为探针必须凭据置空**：首次 V-1 探针误用本地 `moka_ai.json` 走真实后端 60s（作废重跑）——探针结论的效力取决于环境纯净性。
4. **结构防腐测试有射程边界**：YAML 结构断言防不了跨仓真实调用面缺陷；对外分发物必须配真实外部试装（两段式 = 机制面提前、findings 面发布后，兼顾拦截与成本）。
5. **同身份评论竞态（backlog）**：同一 bot 身份 + `--edit-last` 的多个评论协议会互相覆盖（仅失败 PR 显现）——后续版本改锚点定位评论。
6. **逐行扫描的精度边界（如实记录）**：跨行反模式形态（如 `except:` 换行 `pass`）不匹配单行正则——第二段注入 3 种反模式实得 BREAK 2，不虚报。
7. **F-D1：diff 模式扫描绕过 include/exclude 且扩展名盲扫**（dogfood 发现）：`--include/--exclude` 仅过滤 changeset 面，模式扫描扫原始 diff 全部新增行（含 `.md`）；证据文档引用反模式原文即被计入 finding。修复：findings 按 `file_path` 过滤（`rule_engine.matches`，与 review_filter 同一语义）随 4.8.1；修复 PR 自身的测试夹具含字面模式、gate（旧行为）会如实打红——该红即缺陷自身症状，说明后合并。dogfood 闭环价值再证：发布当日 dogfood 即抓到发布版的行为缺陷。

## 5. 残留与移交

- **F-D1 修复（最高优先移交，建议 4.8.1 PATCH 即刻启动）**: diff 模式扫描接入 include/exclude 过滤（findings 按 `file_path` 以 `rule_engine.matches` 过滤，语义与 review_filter 一致）+ 单元测试；修复 PR 的 gate 红为已知症状（见 §4.7）。当前 wrapper 的 `exclude: tests/**` 在修复发布前仅为 changeset 面声明。
- **TD-071 host 路径**: 仍为诚实 `environment_blocked` stub，需 TRAE IDE 会话环境重测（跨批复现，移交不变）。
- **dogfood 已知限制（backlog）**: ① coverage 计数按 diff 文件数非 filter 保留数（显示粒度）；② 同身份评论竞态（§4.5）。
- **zeroclaw 常设消费仓**: wrapper 保留 `@v4.8.0`，后续任意 zeroclaw PR 自然续证（休眠仓零成本）。
- **P2/P3**（执行计划 §5 后续批）: 按"方案共识后推进"流程另启，不在本批扩散。

## 6. 裁定执行核对（执行计划 §10 裁定链）

- D2 版本 MINOR **已执行**: V4.8.0 发布就位。
- 两段式试装裁定（2026-10-22 用户确认）**已执行**: 第一段发布前完成且缺陷修复入发布；第二段发布后当日完成。
- E1 审计窗口 **已执行**: 六项三态清单经用户裁定落 §10，扩张冻结已解除（remove 项 live-browser 已删）。

---

*复盘依据全部来自本批实测命令输出（CI run API、PR 评论 JSON、PyPI JSON API、gh release view、试装证据文档）；无推测数字。*
