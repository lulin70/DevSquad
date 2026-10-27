# P2 缺陷台账批复盘（V4.9.0 发布批）

> **日期**: 2026-10-27
> **批次**: P2 缺陷台账批（执行计划 [2026-10-20_value_proposal_execution_plan.md](../planning/2026-10-20_value_proposal_execution_plan.md) §6，PRD [V4.9.0_defect-ledger_PRD.md](../prd/V4.9.0_defect-ledger_PRD.md)）
> **结果**: 四波 W1-W4 全部完成 + 发布（tag `v4.9.0`、GitHub Release、PyPI 实测就位）；发布收尾链当日全链完成；本 PR（复盘批）补齐 PRD §8 就绪清单欠账并启用 dogfood 登记闸
> **版本**: V4.9.0（MINOR：缺陷台账核心 + 信号写入端 + 登记闸 + 特性门，全部 opt-in 默认关闭，disabled 时与 4.8.x 逐字节一致）

## 1. 执行成果（全部实测）

| 工作项 | PR | 实测结果 |
|--------|-----|----------|
| M2.1 PRD 共识 | #69 | PRD 冻结（四波范围 + §4.2 映射表 + §8 发布就绪清单） |
| W1 设计冻结 | #70 | 状态机/两坑防护/signal_ref 契约；§10 预留台账契约文档随收尾 |
| W1 缺陷台账核心 | #71 `b08062a` | `defect_ledger.py` + `cli_defect.py` 六子命令 + 39 单测（真实 sqlite 夹具）；rebase 后 CI 全绿 |
| 4.8.2 PATCH（dogfood 解锁） | #72/#73/#74 | print_debug CLI 层窄豁免（+4 边界单测）→ 4.8.2 发布链（run 40155189331）→ wrapper `@v4.8.2` |
| W2 设计 | #76 `be0f4be` | 写入端设计冻结 + §3.1/§8 Erratum（grep 假阴性勘误留痕） |
| W2 实现 | #77 `e2a7c22` | `log_dispatch_end` keyword-only + 终态接线 + Step 24 终态重算 + 映射表 + `mandatory_signal_types()` SSOT；定向+受影响面 216 测 |
| W4 设计 | #80 `3a00aa3` | D1-D12 十二裁定（D1 载体改机读清单——PRD 建议载体实测恒 None） |
| W4 实现 | #81 `d2f594c` | `feature_gate.py` + 六处接线 + D7 五面零痕迹 + D8 双侧交叉；24 单测 + 5 集成 + e2e ⑩ |
| W3 设计 | #83 `0b5e882` | D1-D14 十四裁定 |
| W3 实现 | #84 `9a5cc4b` | `registration_gate.py` + 11 处接线 + 三态判定 + advisory；25 单测 + 4 集成 + e2e ⑭（含 CI 修复两条留痕） |
| 全量 bump 4.9.0 | #86 `6e040c5` | 29 文件（4.8.2 先例 PR #73 清单逐文件复刻）；83/83 + 定向 116 测 + smoke `DevSquad 4.9.0` |
| tag + release | — | release run [40443836341](https://github.com/lulin70/DevSquad/actions/runs/40443836341) 一次全绿（Build/E2E 门/PyPI/GitHub Release） |
| wrapper `@v4.9.0` | #87 `400626e` | dogfood gate 以发布 4.9.0 扫描器一次通过（CI 12 pass + 2 release-tag-only skip） |
| 发布后验证 + 状态刷新 | #88 `c302e57` | PyPI JSON API `info.version=4.9.0` + `pip download` wheel 实测 + PROJECT_STATUS 五行发布态 |
| 契约文档 + 能力面 + 勘误 + dogfood 启用 | #89（本 PR） | [DEFECT_LEDGER.md](../reference/DEFECT_LEDGER.md)（PRD §8 / W1 §10 预留项）+ SKILL.md/QUICKSTART 能力面 + CHANGELOG/VERSION_HISTORY 勘误 + `.devsquad.yaml` 启用 + dispatch 直连实测（verdict 面 + Markdown 面） |

**发布链**: PR #86 squash merge（6e040c5）→ tag `v4.9.0` → release run 40443836341 一次全绿 → wrapper PR #87（400626e）→ 发布后验证当日完成（PyPI JSON API 权威 + `pip download devsquad==4.9.0 -i https://pypi.org/simple/` 取得 wheel + `gh release view v4.9.0` 资产核对）→ PROJECT_STATUS 刷新 PR #88（c302e57）。

## 2. 做得好的

1. **四波串行"PRD 共识 → 设计冻结（D 编号裁定）→ 实现 → CI 全绿 → squash 合入"**：每波两 PR 粒度（设计/实现分离），裁定全部编号留痕（W4 十二条、W3 十四条），实现即设计原义可核对。
2. **dogfood gate 持续产出真实发现**：本批两例——print_debug 对 CLI 命令族 8 处误报（→ 4.8.2 PATCH 解锁 W1 合入）、e2e runner print 误报（→ stdout=产品接口裁定 + wrapper 排除）。累计第五、六个 dogfood 真实发现，闭环价值持续验证。
3. **keyword-only 同位扩展模式三波复用**：W2 `findings`/`failure_class`、W4 `feature_gate`、W3 `registration_gate` 均以 keyword-only 参数扩展 `log_dispatch_end`——不传时 details 与 4.8.x 逐 key 一致，审计链不破；模式一次设计三次复用。
4. **发布收尾复刻先例高效**：29 文件 bump 逐文件对齐 4.8.2 先例清单（diff stat 与先例一致）；release 一次全绿；发布当日完成全部验证与状态刷新，不欠账（P1 复盘 §2.3 纪律延续）。
5. **e2e 证据覆盖负向路径**：W3 三场景 31 断言（unregistered→立案→tracked→修复；regressed→reopen→tracked；disabled 零痕迹）、W4 三场景（disabled 零痕迹/pass 矩阵/tamper 打红）——fail-closed 语义每条都有真实 run。
6. **设计勘误文化**：W2 Erratum（假阴性结论修正）、W4 §10 移交教训（载体可达性）、W3 明示"本文无新增勘误"——设计文档把错误当一等公民留痕。

## 3. 事件与处置

| 事件 | 处置 | 教训去向 |
|---|---|---|
| W2 设计调研：grep `head_limit` 截断 → "`details['failure_class']` 零写入方"错误结论进入设计初版 | 实现期发现真实写入点 `dispatch_result_assembler.py:105-126`（组装时刻）；设计文档 §3.1/§8 Erratum 留痕 | §4.1 |
| W4 实现首跑 CI 4 项 fail：`shell=True` 触发 bandit B602（HIGH）；本地"全量绿"为假象（skipif 用 `which bandit` 查 PATH，bandit 在 `.venv/bin`） | D11 裁定行内 `# nosec B602`（命令文本来自人写验收清单 = CI 配置同级信任，设计 §9 Security 已裁定）；`f5b8215` CI 12 项全绿 | §4.3 |
| W4 设计载体：PRD 建议 `StructuredGoal.acceptance_criteria` 作清单载体，实测 `getattr` 恒 None（无生产方） | D1 改为项目级机读清单文件 `.devsquad/acceptance_checklist.json` | §4.4 |
| W3 实现首跑 CI 2 项 fail：① radon D(23)——内联 Step 23.6 把 `PostDispatchPipeline.execute` 从 C(20) 推到 D(23) 破零 D+ 硬门禁；② dogfood BREAK-2——e2e runner 10 处断言 print | ① 提取 `_apply_registration_gate` 到 steps mixin（execute 回 C(20)，模式写入 helper docstring）；② 裁定 stdout 即 e2e runner 产品接口 → dogfood wrapper 增排 `docs/e2e_evidence/**`（真实秘密泄漏仍由独立 "No secrets in repo" CI job 全树覆盖） | §4.8 / §4.9 |
| 收尾补契约文档时实测发现：CHANGELOG/VERSION_HISTORY 4.9.0 表述与代码不符——"SQLite(-backed) state machine"（ledger 实为 JSON 文件 `.devsquad/defects.json`，sqlite3 只读消费 audit db）；子命令名单 `add/show/.../export`（argparse 实注册 `add/update/close/reopen/list/audit`） | 本 PR 勘误修正（两文件三处）；契约文档以 argparse 注册与实现实测为准（`cli.py defect --help` 探针） | §4.10 |
| PRD §8 发布就绪清单两项欠账：台账契约文档（W1 §10 预留"随收尾一并"）+ QUICKSTART/README×3/SKILL.md 能力表同步——bump PR #86 只做了版本面 | 本 PR 补齐：`docs/reference/DEFECT_LEDGER.md` + SKILL.md Reference 表行 + QUICKSTART 质量保障段 | §4.11 |
| dogfood 实测：CLI 全管线 mock dispatch 在本机挂起（8 分钟 0.96s CPU，栈采样 = kevent 空等，asyncio loop 无就绪事件）；W3 e2e 先例的直连路径（直接构造 dispatcher + 单角色 + 注入 audit logger）0.1s 正常 | 规避路径已验证：dogfood 接线实测走直连路径（config → kwargs → result 面），CLI 全管线挂起根因未深挖，如实留痕 | §5 残留 |

## 4. 教训（写入项目记忆）

1. **否定性结论须无截断检索复核**：grep `head_limit` 截断输出只能支撑存在性证明，不能支撑"不存在"结论（W2：真实写入点被截断隐藏，"零写入方"错误结论进入设计初版）。
2. **审计字段生命周期须覆盖时序全链**：写入时刻（组装）与消费时刻（终态）之间的状态变迁（review gate 追加 errors 翻转 success）会使中间态字段过时——终态消费须终态重算（W2 Step 24 重算的由来）。
3. **门禁工具存在性检测须用模块可导入性**（`importlib.util.find_spec`）而非 `which` PATH 查找：bandit 在 `.venv/bin` 不在 PATH，skipif 假 skip 造成本地"全量绿"假象，CI 首跑 4 项 fail 才暴露（W4）。
4. **PRD 建议载体无生产方时须先实测数据流可达性再锁定**（W4 D1：`acceptance_criteria` getattr 恒 None——否则设计出永远空转的门；W4 设计 §10 移交原文）。
5. **注入依赖的所有权语义须显式**：`dispatcher.shutdown()` 会关闭注入的 audit logger（`dispatcher_mixins.py:401` 调 `close()` 置 `_conn=None`）——多 run 工作区须每次 dispatch 新建 logger；`AuditEntry` 不携带 sqlite 行 id，事件 id 须直查数据库（W3 运维发现）。
6. **size 基线有意增长与实现同 PR 有意识刷新**：dispatcher.py 1129→1138→1155→1165 三波接线，每波设计锚定行数同批提交（P0 教训"与增长同批意识性提交"的延续）。
7. **Mock 断言随 keyword-only 参数演进**：`log_dispatch_end` 三波扩展（`findings`/`failure_class` → `+feature_gate` → `+registration_gate`）每次都须演进 mixins 断言（W4 首现 `test_log_end_calls_logger`，W3 再现——同一测试两次演进）。
8. **新 gate 接线直接走提取模式**：内联挂点把宿主方法推破 radon 零 D+ 硬门禁（W3：`execute` C(20)→D(23)）——提取 helper 到 mixin 行为等价（已写入 helper docstring 成为后续 gate wave 模式）。
9. **扫描器误报按"stdout 是否产品接口"分类裁定**：e2e runner 断言 print 即产品接口（4.8.2 CLI 层同类判断）——豁免走 dogfood wrapper exclude（保持外部消费者语义不变），真实秘密泄漏仍由独立 CI job 全树覆盖。
10. **发布文档的能力描述须与 argparse 注册与存储实现实测核对**：CHANGELOG"SQLite-backed"与子命令名单 `add/show/export` 均与代码不符——收尾补契约文档时 CLI help 探针抓出（文档数字真实性的最后一道防线是实测探针，不是评审记忆）。
11. **发布就绪清单须逐项销项，不能被版本面 bump 覆盖**：PRD §8 两项（能力表同步 + 契约文档）在收尾 bump PR 中遗漏——bump 只做版本一致性检查，就绪清单是独立检查单，须单独过一遍。

## 5. 残留与移交

- **CLI 全管线 mock dispatch 本机挂起（根因未明）**：直连路径（W3 e2e 先例：直接构造 dispatcher + 单角色）0.1s 正常；CLI 层差异（warmup/host adapter/async 全管线）待后续批根因——如实登记不混修。
- **feature_gate dogfood 暂不启用**：须先有 `.devsquad/acceptance_checklist.json` 的真实产能流程（哪个特性需要验收清单时哪个批次启用）。
- **unfiled_signal_report advisory 实际价值待观察**：本仓 dogfood 启用后首个产生 warning/spec 信号的真实 dispatch 才能检验 advisory 面的可用性。
- **TD-071 host 路径**：仍为诚实 `environment_blocked` stub（跨批复现，移交不变）。
- **W3 dogfood 已知限制（backlog）**：coverage 计数按 diff 文件数非 filter 保留数（P1 复盘 §5 已录，未修）。

## 6. 裁定执行核对（执行计划 §6 + PRD 裁定链）

- SemVer MINOR（四波全 opt-in、disabled 时 4.8.x 逐字节一致）**已执行**：tag `v4.9.0` 发布就位。
- PRD §8 发布就绪清单 **已销项**（本 PR 补齐后）：版本面（PR #86）+ 能力表同步 + 台账契约文档（本 PR）。
- dogfood 启用裁定（W3 D5 预留"发布后启用"）**已执行**：`.devsquad.yaml` `defect_ledger.enabled: true`，dispatch 实测 verdict 面 + Markdown 面真实接线。

---

*复盘依据全部来自本批实测命令输出（CI run API、PR squash SHA、PyPI JSON API、`pip download`、`gh release view`、`cli.py defect --help` 探针、直连 dispatch verdict/Markdown 探针、`sample` 栈采样）；无推测数字。*
