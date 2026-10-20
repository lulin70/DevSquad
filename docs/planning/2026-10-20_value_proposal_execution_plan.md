# DevSquad 价值方案推进计划（D1–D4 已裁定）

> 文档类型：执行计划（活文档，后续开发的唯一执行依据）| 日期：2026-10-20
> 依据：[2026-10-20_architecture_review_and_value_proposal.md](2026-10-20_architecture_review_and_value_proposal.md)（下称"方案文档"，范围细节与验收标准以其 §5 为准）
> 裁定记录：2026-10-20 用户批准 D1–D4 全部四项——D1：P0 卫生批立即执行（含跟踪文档入库）；D2：P1 立项 **V4.8.0 MINOR**；D3：P2 缺陷台账排入 **V4.9.0**；D4：认可"消费者审计先于功能扩张"。
> 执行纪律：文档先行、万事留痕；每步验证；发布前一切准备完成；版本纪律（PATCH 默认、MINOR 已裁定）。
> 变更协议：任何范围/优先级/版本号变更 → 用户重裁定 → 记录于本文 §10 → 同步对应 PRD。禁止跳步与事后改单。

---

## 1. 目标（一句话）

三个批次内，把 DevSquad 从"一次性任务报告器"升级为"工程师工作流常驻层"：治理漂移（P0）→ 分发触点就位（P1）→ 信号闭环（P2）；全程以消费者审计门控扩张（D4）。

## 2. 总体排期与依赖

```
P0 卫生批 ──→ v4.7.2 PATCH ──→ P1 工作流进场批 ──→ v4.8.0 MINOR ──→ P2 缺陷台账批 ──→ v4.9.0 MINOR
              （发布时机见 §4.2）        │
                                      └── P3-E1 消费者审计（P1 窗口并行，治理件）
                                          产出 keep/freeze/remove 三态清单 → 用户裁定 → 解除扩张冻结
```

- 依赖规则：P0 不阻塞 P1 的 PRD 撰写（可并行）；P0 必须先于 P1 发布（卫生批门控 P1 发布质量）；P2 的实现以 P1 发布+发布后验证完成、P2 PRD 共识为前置。
- D4 约束：P1/P2 期间禁止新增借鉴型大模块；扩张冻结至 E1 裁定完成。

## 3. 统一生命周期阶段（每批必经，不可裁剪）

| 阶段 | 入口条件 | 出口门禁 | 主责（DevSquad 角色） |
|---|---|---|---|
| 0 共识/PRD | 批次裁定（本文 §10） | PRD 独立完整 → 用户确认 | PM + Architect（7 角色共识门） |
| 1 技术设计 | PRD 确认 | 设计文档独立完整 + 跨角色评审通过 | Architect + Security + DevOps |
| 2 实现 | 设计确认 | 代码完成 + 单测绿（无跳过项） | Coder |
| 3 测试 | 实现完成 | 单测/集成/e2e 全绿 + **模拟真实用户测试通过** | Tester |
| 4 发布 | 测试全绿 + 文档同步 + 版本一致 | 权威 CI 全绿 → 单维护者合并 → tag → PyPI | DevOps |
| 5 发布后验证 | 发布完成 | pip 真实安装验证 + 全子命令 + TRAE 技能列表 + E2E | Tester + DevOps |
| 6 复盘 | 发布后验证完成 | 复盘文档（docs/assessments/）+ 教训入 project memory | PM（组织） |

铁律引用：测试铁律、交付工作流铁律、元铁律（[SUB_SKILLS.md](../reference/SUB_SKILLS.md)）。

## 4. P0 卫生批（v4.7.2 PATCH）

### 4.1 任务明细

| 项 | 内容 | 主责 | 验证 |
|---|---|---|---|
| P0-W4 文档入库（先行） | commit 四份文档：10-12 跟踪（M）、10-20 跟踪（新）、方案文档（新）、本文（新） | PM | git log 可见；main 干净 |
| P0-W1 过时版本串清除 + 门禁负向扫描 | 6 处修复：[cli.py:341](../../scripts/cli.py#L341)、[cli_metrics.py:217](../../scripts/cli_metrics.py#L217)、[cli_visual.py:3](../../scripts/cli_visual.py#L3)、[dashboard/components.py:505](../../scripts/dashboard/components.py#L505)、[workflow_engine_mixins.py:213](../../scripts/collaboration/workflow_engine_mixins.py#L213)、[benchmark_ponytail_smart.py:384](../../scripts/benchmark_ponytail_smart.py#L384)。修复方式：删除硬编码版本自述或改为引用动态 VERSION 常量（版本只经 `--version` 出口），杜绝同类复发。门禁：check_version_consistency 增负向扫描——用户可见面禁止 `DevSquad V<数字>` 硬编码自述 | Coder + Security | 新增负向测试：人为植入 `DevSquad V0.0` → 门禁变红；移除后变绿。版本一致性 80/80 维持 |
| P0-W2 状态文档治理 | PROJECT_STATUS.md 刷新至 V4.7.1 现实（版本/发布状态/PyPI 实测链接）；[RELEASE_CHECKLIST.md](../../RELEASE_CHECKLIST.md) 增加"发布时必须刷新状态文档"步骤 | PM | 文档声明与 PyPI 一致（采集命令附文档内）；check_skill_contract 通过 |
| P0-W3 TD-071 真实测量（环境依赖，可并行不阻塞） | host/api 性能基线在可用环境真实测量，关闭 stub。环境不可用时：保持诚实 stub + environment_blocked 记录，不阻塞 P0 发布 | DevOps | snapshot_id 无 `_stub`；性能门禁全绿；或 environment_blocked 留痕 |

### 4.2 执行顺序与收尾

W4 → W1 → W2（W3 并行）→ 版本号升 **4.7.2**（VERSION/pyproject/manifests/README×3 等，一致性 80/80）→ TRAE 缓存三处同步（~/.trae-cn、~/.trae、trae_projects/.trae）→ 全量回归 → 发布。

**发布时机裁定（默认建议，可一句话否决）**：P0 建议独立 tag v4.7.2 小规模发布（版本串修复直接作用于用户可见面，尽快面客）。若用户选"入库不发布"，则随 v4.8.0 一并面客，需在 §10 记录。

### 4.3 批次出口标准（全绿才关批）

1. 版本一致性 80/80 + 新负向门禁绿；2. PROJECT_STATUS 与 PyPI 现实一致；3. 全量测试回归无新增失败；4. 模拟真实用户：`pip install --upgrade devsquad` → `devsquad --help` 首行自述正确、`devsquad --version` = 4.7.2。

## 5. P1 工作流进场批（V4.8.0 MINOR）

### 5.1 PRD 范围（四项 + 一审计）

| 项 | PRD 要点 | 验收（摘要，全表见方案文档 §5.2） |
|---|---|---|
| P1-R1 devsquad-gate GitHub Action（核心） | 触发 pull_request；权限最小（contents:read + pull-requests:write）；复用 4 字段 PR 评论协议 + run URL + 协议版本号 v1；fail-closed 非零退出；judge 沿用 `DEVSQUAD_JUDGE_*` 环境隔离；secrets 不回显；`--preview` 定价输出；分发形态：本仓 `.github/` + 外部仓 `uses:` 引用 | 外部真实仓库试装 e2e（PR 开→评论现→幂等 `--edit-last`）；失败注入→非零退出；secrets 缺失时行为按文档（不谎报） |
| P1-R2 persona 五分钟通道 | QUICKSTART 重构为三条最短路径（IDE host 委托零 key / CLI init 向导分流 / 维护者 Action 一行接入）；init 向导按后端分流；config consistency 扩展覆盖新文档命令一致性 | 三 persona 各一条模拟真实用户 e2e（安装→第一份产出）；每条路径起点命令唯一 |
| P1-R3 dogfooding 自证链 | `scripts/generate_dogfooding_report.py`：数字全部采集自本仓门禁/审计链输出，附可复现命令；首期季度报告入库 | 首期报告产出；任一数字可按文档命令复现（TD-074 教训：无不可复现断言） |
| P1-R4 MCP 通道文档 | 外部 IDE（Cursor 等）经 MCP 接入的安装与工具清单文档（RBAC/fail-closed 行为写明） | 按文档在外部 IDE 完成连接的 e2e 证据 |
| P1-E1 消费者审计（并行治理件） | 对象：teach / prototype / live-browser / meta-skill-layering / impeccable 词表 / taste-dials；逐项回答"谁在什么场景用"；产出 keep/freeze/remove 三态清单 | 清单 + 用户裁定记录 → §10 留痕；裁定后解除扩张冻结 |

### 5.2 执行顺序

R1 PRD 共识 → 设计 → 实现 → 外部试装测试；R1 设计冻结后，R2/R3/R4 并行分头 PR；E1 全程并行。每项独立 PR + 权威 CI + 单维护者合并。

### 5.3 发布就绪清单（发布前一切完成，不欠账）

文档（QUICKSTART/README×3/SKILL.md 能力表同步）｜代码｜测试（e2e×3 persona + 外部试装）｜安全（secrets 边界评审）｜DevOps（Action workflow 入仓）｜版本 4.8.0 全量一致 80/80｜TRAE 缓存三处同步。

## 6. P2 缺陷台账批（V4.9.0 MINOR）

### 6.1 PRD 要点（设计依据：方案文档 §5.3 + 10-20 跟踪文档 §3.1/§3.2）

defects.json 全局台账（DEF-NNN；工单必须挂真实信号，禁凭空立案）；封闭状态机 open→fixed→closed + regressed→open（reopen 强制 reason）；登记闸 fail-closed（发现未立案 → gate FAIL）；ID 复用防护含 history 扫描；feature_gate 现算覆盖矩阵 + 清单 SHA256 锚定；FailureClass → 信号类型映射。上游已踩两坑（转移丢失/ID 复用）在 PRD 阶段直接写为实现要求。

### 6.2 测试要求

状态机全转移覆盖；负向测试先行（无信号立案被拒 / 未立案发现打红 gate / 清单篡改打红 gate）；全生命周期 e2e（发现→立案→修复→回归→关闭→reopen）。

### 6.3 入口条件

P1 发布且发布后验证完成；P2 PRD 经用户确认。

## 7. 里程碑与验证汇总

| 里程碑 | 出口验证 |
|---|---|
| M0.1 P0 文档入库 | git log 四份文档可见 |
| M0.2 负向门禁上线 | 植入假版本串门禁变红的演示记录 |
| M0.3 v4.7.2 发布（或"入库不发布"裁定记录） | PyPI/Release 链接或 §10 记录 |
| M1.1 P1 PRD 用户确认 | PRD 文档 + §10 记录 |
| M1.2 R1 外部试装 e2e 通过 | e2e 证据（PR 评论截图/日志） |
| M1.3 E1 三态清单裁定 | §10 记录 |
| M1.4 v4.8.0 发布 + 发布后验证 | 发布就绪清单全勾 + 发布后验证记录 |
| M2.1 P2 PRD 共识 | PRD 文档 + 用户确认 |
| M2.2 台账状态机全测试绿 | 测试输出 |
| M2.3 v4.9.0 发布 + 发布后验证 | 同 M1.4 |

## 8. 风险与回退

| 风险 | 回退/缓解 |
|---|---|
| W3 环境不可用 | 诚实 stub + environment_blocked 留痕，不阻塞 P0（不假造数据） |
| R1 跨仓维护负担 | 评论协议保持 4 字段极简 + 协议版本号 + 行为边界文档化 |
| R2 文档-实现再漂移 | config consistency 扩展门禁化，不留人治 |
| P2 状态机复杂度失控 | 封闭状态集 + 负向测试先行 + 上游教训直写 PRD |
| 全批次范围蔓延 | §10 变更协议：先裁定后动手 |

## 9. 复盘机制

每批关批时执行 retrospective 子技能流程：复盘文档入 docs/assessments/；可固化教训写入 project memory；下批开工前回顾上批复盘结论。

## 10. 裁定与变更记录

| 日期 | 事项 |
|---|---|
| 2026-10-20 | 用户批准 D1–D4；本文档形成，作为 P0/P1/P2 唯一执行依据 |
| 2026-10-20 | P0 发布时机默认建议"独立 v4.7.2 小发布"；待执行到 §4.2 收尾时按默认执行，用户可随时否决改记"入库不发布" |
