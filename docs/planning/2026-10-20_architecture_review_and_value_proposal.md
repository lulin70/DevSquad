# DevSquad 架构与功能评审 + 软件工程落地价值建议方案

> 文档类型：架构评审与价值方案 | 日期：2026-10-20 | 评审基线：DevSquad V4.7.1
> 评审范围：整体架构、全部已加入功能、全部待加入/在途项；目标：让 DevSquad 在真实软件工程落地中给用户更大帮助
> 本文独立完整，不依赖会话上下文。证据采集方式（2026-10-20）：
> ① 文档通读：ROADMAP.md / TECH_DEBT.md / PROJECT_STATUS.md / VISION.md / SKILL.md / project memory
> ② 代码证据：`scripts/cli.py`（入口面）、`scripts/collaboration/dispatch{er,_pre_steps,_steps}.py`（管线）、`scripts/collaboration/review_checkers.py`、grep 过时版本串
> ③ 外部核实：`curl pypi.org/pypi/devsquad/json` → latest = **4.7.1**（2026-10-20 实测）
> ④ 上游对照：[2026-10-20_upstream_traemultiagentskill_v2.12-v2.14_tracking.md](../analysis/2026-10-20_upstream_traemultiagentskill_v2.12-v2.14_tracking.md)
> 纪律：结论必须挂证据；批判优先于赞美；不虚报；本文档为讨论稿，任何立项以用户裁定为准。

---

## 1. 结论速览

1. **核心资产健康**：两层架构（prompt 编排 + 确定性脚本层）、fail-closed 门禁族、反幽灵（anti-ghost）保证、SHA256 审计链、约 9800 项测试的工程纪律——这些是护城河，本方案不推翻任何一项。
2. **最大价值断层不在功能数量，在"持续在场"**：DevSquad 当前是"一次性任务报告器"。真实软件工程的价值时刻是 PR 打开、CI 红、发布前检查。DevSquad 的确定性门禁族已经具备这些时刻需要的全部检查能力，但没有打包成工程师能在工作流内消费的形态（GitHub Action / pre-commit / 外部 IDE 的 MCP 文档）。
3. **第二个断层是"信号蒸发"**：review 发现、疑似缺陷、失败分类（FailureClass）都是 run 内产物，run 结束即蒸发。缺一个跨 run 的缺陷台账（信号→工单→修复→回归→关闭）。上游 v2.14 已验证此设计，吸收成本低。
4. **治理面存在三类漂移实锤**：PROJECT_STATUS.md 落后两个发布版本（仍称"V4.7.0 未打 tag、PyPI 最新 4.6.0"，实测 PyPI 已是 4.7.1）；用户可见面存在 6 处过时版本串（含 `devsquad --help` 第一行的 "DevSquad V3.6"）；两份上游跟踪文档未入库。版本一致性门禁管"当前版本必须一致"，不管"过时版本串必须清除"——存在门禁盲区。
5. **建议分三批**：P0 卫生批（漂移修复+状态文档治理，PATCH 级）→ P1 价值主张批"DevSquad 进入工程师工作流"（分发触点打包+persona 快速通道+落地自证，建议立项 V4.8.0 MINOR，需批准）→ P2 工程闭环批（跨 run 缺陷台账，吸收上游 v2.14）。
6. **同时建议做减法**：对 219 个模块中借鉴型低频功能启动消费者审计；anti-ghost 证明的是"被调用"，不证明"被需要"。防 feature bloat 比加新模块更紧迫。

---

## 2. 架构现状评审（证据锚定）

### 2.1 分层架构

```
┌─ 用户入口层 ─────────────────────────────────────────────┐
│ TRAE/Claude skill(宿主委托,零key) │ CLI │ MCP(RBAC) │ REST API │ Dashboard │
├─ 编排层（宿主 LLM 执行 prompt；脚本层确定性驱动）─────────┤
│ InputValidator → 规则链 → IntentMapper(LLM/TF-IDF/Hashing三级降级) │
│ → 角色匹配 → Sync/Async Workers → Scratchpad 共享 → 共识引擎 │
│ → 两阶段 review gate → 结构化报告(+审计链)                  │
├─ 确定性资产层 ────────────────────────────────────────────┤
│ 门禁族 / 失败分类学 / 审计 / 测试基建 / 生命周期 CLI        │
└───────────────────────────────────────────────────────────┘
```

证据：入口面 [cli.py:330-444](../../scripts/cli.py#L330-L444)（init/demo/dispatch/spec/plan/build/test/review/ship/roles/status）；MCP 工具面 [mcp_server.py:80-106](../../scripts/mcp_server.py#L80-L106)（multiagent_dispatch/quick/analyze + codegraph，含 fail-closed 权限）；REST 调度接口 [api/routes/dispatch.py:179-272](../../scripts/api/routes/dispatch.py#L179-L272)；管线 [dispatcher.py:422-503](../../scripts/collaboration/dispatcher.py#L422-L503) → [dispatch_pre_steps.py:114-291](../../scripts/collaboration/dispatch_pre_steps.py#L114-L291)（输入校验/规则收集/意图/角色/安全）→ [dispatch_steps.py:446-677](../../scripts/collaboration/dispatch_steps.py#L446-L677)（worker 结果/共识/记忆/回顾/技术债扫描/两阶段 review gate/结果组装）。

### 2.2 质量与门禁资产盘点（护城河，保持）

| 资产 | 职责 | 状态 |
|---|---|---|
| AntiGhostChecker（`_call_counter`） | 模块必须被真实调用，杜绝"存在即生效"的幽灵功能 | 生产+CI |
| TestQualityGuard（[test_quality_guard.py](../../scripts/collaboration/test_quality_guard.py)） | 测试反模式检测（status-code-only 等），接入组件工厂 | 生产+CI |
| ReviewCheckers（[review_checkers.py:107-125](../../scripts/collaboration/review_checkers.py#L107-L125)） | Stage 1 规格合规：planned files/functions、计划完成度、必需角色、验收标准；+ 代码模式检查（TODO 残留/print 调试等） | 生产 |
| review_taxonomy.py（V4.7.0 W1） | BREAK/VULN 十类确定性发现分类（吸收上游 v2.11） | 生产（PR #34/#35） |
| failure_taxonomy.py（V4.6.0） | product_failed / environment_blocked 两分类 + exit 0/1/2 契约（C19） | 生产 |
| 四层规则链 + `review --preview` | 系统>项目>用户>默认规则；preview 零 LLM 调用定价审查 | 生产 |
| 共识门 / ApprovalGate | fail-closed 共识 + 用户级审批 | 生产 |
| 文档-实现守卫族 | 版本一致性 80/80、配置一致性 7/7、check_skill_contract、dispatcher size gate、module activation | 生产+CI |
| 测试基建（V4.6.0） | LLM 回放缓存、judge 环境隔离（`DEVSQUAD_JUDGE_*` 绝不回落作者命名空间）、PR 4 字段结构化评论（幂等 `--edit-last`） | 生产（本仓 CI 实证） |

### 2.3 工程基线（PROJECT_STATUS.md 记录的 V4.7.0 基线）

9794 tests / 403 文件，金字塔 unit 73.7% / integration 15.0% / e2e 5.0%；ruff + mypy 0 错、Bandit 0 HIGH/0 MEDIUM、pip-audit 净、覆盖率 79.48%。实测 PyPI latest = 4.7.1（2026-10-20）。

### 2.4 优势结论（三条，均有实证）

1. **诚实边界披露是差异化**：SKILL.md 明确声明"prompt 层由宿主 LLM 执行、脚本层确定性、无 key 不产出真 LLM 结果"——同类工具普遍虚写，本仓写实。
2. **确定性侧可复现**：同一输入下门禁/分类/审计输出可复现，不随宿主 LLM 波动。这是"AI 产物可信"的根基。
3. **dogfooding 有实绩**：本仓自身的 PR 评论工作流、TD 债务批次、上游跟踪纪律都是这套方法论的运行证据——只是尚未对外产品化（见 F5）。

---

## 3. 批判性评估：五个价值断层

### F1 状态漂移——门禁盲区（严重度：中，修复成本低）

- 现象：`devsquad --help` 第一行自述 "DevSquad **V3.6**"（[cli.py:341](../../scripts/cli.py#L341)），实测 6 处过时版本串（V3.6/V3.8/V3.10.0/V4.1.0/V4.1.1/V4.5.2，grep 2026-10-20）；PROJECT_STATUS.md 停留在"V4.7.0 未打 tag、PyPI 最新 4.6.0"，落后两个发布版本。
- 根因：版本一致性门禁（80/80）校验"当前版本号在各处一致"，不校验"用户可见面不存在过时版本串"。TD-074 修过 19 处此类断言，但未形成门禁化，同类问题重新发生。
- 影响：外部文档与 UI 是用户第一印象（用户原则）。CLI/ Dashboard 的第一屏版本自述错误，直接损害"确定性可信"的核心卖点。

### F2 一次性 dispatch vs 工程工作流（严重度：高，本方案主攻方向）

- 现象：DevSquad 的价值交付以"提交任务→拿报告"为中心。真实工程师的高频价值时刻是：PR 打开时、CI 失败时、commit 前后、发布前。这些时刻当前只有一个内部种子——本仓 CI 的 PR 4 字段评论（V4.6.0 W2 P2-b），它证明了可行性，但只服务本仓，外部用户拿不到。
- 证据：W2 的 `gh pr comment` 协议、judge 隔离、回放缓存全部就绪且经过 J7 真实验证（project memory 2026-10-12）；`pre-commit` 能力 V4.2.1 已落地（ROADMAP P2-4）；CLI 生命周期命令 spec/plan/build/test/review/ship 已存在（cli.py:366-372）——**零件全齐，缺的是面向外部仓库的分发包装**。
- 影响：219 个模块的检查能力被锁在"主动调用"形态里。被动触发（PR/push 事件）才是工程落地的形态。

### F3 信号蒸发——无跨 run 缺陷台账（严重度：高，已有上游验证的低成本解）

- 现象：review 发现（BREAK/VULN）、疑似缺陷、失败分类（FailureClass）都是 run 内产物。run 结束后无持久化工单，无"发现→立案→修复→回归→关闭"生命周期。TECH_DEBT.md 管 TODO 标记，不管 AI 发现。
- 上游对照：TraeMultiAgentSkill v2.14 已实现 defects.json 跨 run 台账 + DEF-NNN 状态机 + 登记闸（发现未立案 → finalize FAIL），与本仓 FailureClass/审计链同构（详见 10-20 跟踪文档 §3.1/§3.2）。
- 影响：AI 发现的质量信号不积累，跨 run 无记忆。这是"AI 团队"与"真人团队"行为差距最大的一处——真人团队的 bug 会进 Jira，DevSquad 的 finding 进不了任何地方。

### F4 功能深度不均——219 模块中的投机面（严重度：中，需审计而非扩张）

- 现象：V4.2-V4.4 吸收的借鉴型功能（impeccable 命令词表、live browser 模式、meta-skill 六层、taste-dials 系）各自带 27-61 项测试，anti-ghost 证明它们被调用。但"被测试调用"≠"被用户需要"。无任何消费者统计可证明其真实使用。
- 影响：维护面持续扩大（每版本都要带着它们过全部门禁），而 785 个 MINOR 测试质量项还在治理中。按用户"防 feature bloat"原则，扩张前应先审计存量。

### F5 落地证明缺位——dogfooding 有实绩、无证据链（严重度：中）

- 现象：本仓是最完整的 DevSquad 用户（PR 评论、债务批次、跟踪纪律都是方法论运行证据），但这些证据散在 docs/ 与 memory 中，未形成对外可引用的"DevSquad on DevSquad"自证报告。
- 影响：外部用户无法低成本判断"这套东西真的能用在真实工程吗"——这恰是本工具最需要回答的问题。

---

## 4. 已加入 vs 待加入功能通盘表

### 4.1 已加入（按价值簇，非逐条全列）

| 价值簇 | 内容 | 价值判定 |
|---|---|---|
| 编排核心 | 7 角色、意图三级降级、同步/异步 workers、Scratchpad 跨会话搜索、五轴共识、会话恢复、i18n 三语 | 核心，保持 |
| 确定性质量层 | review_checkers 两阶段门禁、review_taxonomy 十类、failure_taxonomy、四层规则链、--preview、FileBundler、git-guardrails 三级分类 | **护城河**，保持并扩大消费面 |
| 工程管理 | RiskRegister(PMP)、RequirementTracer、TodoDriftMonitor、PonytailDebtCollector、ErrorBudgetTracker、DoraMetrics、GapAnalyzer、ViewpointRegistry(TOGAF) | 能力在，**消费浅**（多数仅 dispatch 内部调用，未接入 spec/ship 生命周期命令）→ P3-E2 |
| 生命周期 CLI | init/spec/plan/build/test/review/ship/status/demo | SDLC 面就位，review --changeset/--diff-file 已支持 PR 审查输入 → P1 分发包装的底座 |
| 测试基建（V4.6） | LLM 回放缓存、judge 隔离、PR 4 字段评论、exit 0/1/2 契约 | **已验证的分发协议** → P1-R1 直接复用 |
| 子技能（8） | dispatch/intent/review/security/test/retrospective/prototype/teach | teach/prototype 属借鉴型 → P3-E1 审计对象 |
| 集成面 | REST API、MCP(RBAC)、Dashboard(6-Tab/live)、ConnectorFramework(GitHub 三模式)、Docker/Helm | MCP 是"其他用户"最宽通道，文档不足 → P1-R4 |

### 4.2 待加入 / 在途项（全部登记于案）

| 项 | 来源 | 当前状态 | 本方案处置 |
|---|---|---|---|
| 跨 run 缺陷台账 + feature_gate 锚定 | 上游 v2.14（10-20 跟踪文档裁定候选） | 待用户裁定 | **纳入 P2** |
| SU 五条安全红线 checklist | 上游 v2.9（储备） | 储备 | 维持储备，P2 台账涉及持久化文件时调用 |
| 非 eval 受限表达式求值器 | 上游 v2.13（储备） | 储备 | 维持储备（无真实 DSL 需求不立项） |
| v2.12 浏览器测试闭环 | 上游 v2.12 | 已裁定不吸收 | 维持不吸收 |
| TD-071 host/api 性能基线 | TECH_DEBT | OPEN（环境阻断，诚实 stub） | **纳入 P0-W3**（可用环境真实测量后关账） |
| 785 项 MINOR 测试质量 | TECH_DEBT 持续治理 | 0 项可机械转换，需逐个语义判断 | 维持持续治理，不设新承诺 |
| Docker/Helm/Prometheus 真实环境检查 | PROJECT_STATUS §9 | 待可用环境 | 与 TD-071 同环境窗口执行 |
| Dynamic Workflows 6 模式库 | ROADMAP P3-1 | 已裁决不做（YAGNI/Non-Goals 冲突） | **维持不做** |
| Loop Engineering 作为默认内核 | VISION.md 长期愿景 | 部分（LoopKernel/回退策略/SmartConfirmation 已有，未成默认） | P3-E4 评估，不承诺 |
| 过时版本串清除 + 状态文档刷新 | **本次评审新发现（F1）** | 未登记 | **P0-W1/W2** |

### 4.3 与用户原则的对齐检查

- **Simplicity First**：P1/P2 均为"包装既有能力"或"吸收已验证设计"，无新造轮子。
- **优先整合现有工具**：GitHub Action 打包的是既有门禁；台账复用上游踩坑记录（转移丢失/ID 复用两类缺陷上游已修）。
- **防 feature bloat**：本方案含明确的减法动作（P3-E1 消费者审计）。
- **版本纪律**（2026-09-24 用户明令）：默认 PATCH；P1 立项 V4.8.0 MINOR 需用户显式批准。

---

## 5. 建议方案（分批）

### 5.1 P0 卫生批（PATCH 级，目标：下个发布窗口前）

| 项 | 内容 | 验收 |
|---|---|---|
| P0-W1 | 清除 6 处过时版本串（cli.py:341 / cli_metrics.py:217 / cli_visual.py:3 / dashboard/components.py:505 / workflow_engine_mixins.py:213 / benchmark_ponytail_smart.py:384）；并把"用户可见面禁止过时版本串"纳入 check_version_consistency 的负向扫描 | 新增负向测试：人为植入 `DevSquad V0.0` → 门禁变红 |
| P0-W2 | PROJECT_STATUS.md 刷新至 V4.7.1 现实（版本/发布状态/PyPI 链接）；RELEASE_CHECKLIST.md 增加"发布时必须刷新状态文档"步骤 | 文档声明与 PyPI 实测一致（采集命令附文档） |
| P0-W3 | TD-071：在可用环境完成 host/api 性能基线真实测量，关闭最后一项 stub | snapshot_id 无 `_stub` 标记；性能门禁全绿 |
| P0-W4 | 两份上游跟踪文档入库（2026-10-12 修改 + 2026-10-20 新增），维持"万事留痕" | git log 可见；main 干净 |

### 5.2 P1 价值主张批——"DevSquad 进入工程师工作流"（建议 V4.8.0，MINOR 需批准）

**一句话**：不新增检查能力，把已有确定性资产送到工程师的真实工作时刻。

| 项 | 内容 | 价值假设与验收 |
|---|---|---|
| P1-R1 devsquad-gate GitHub Action | 打包 review 确定性侧（review_checkers + review_taxonomy + 规则链 + TestQualityGuard）+ `--preview` 定价 + V4.6.0 的 4 字段 PR 评论协议 + judge 三态，输出为外部仓库可安装的 Action（`uses: lulin70/devsquad/.github/workflows/...` 或独立 action repo） | 假设：被动触发（PR 事件）的采纳成本远低于主动 dispatch。验收：①在 1 个外部真实仓库试装并跑通；②e2e：PR 打开→评论出现→幂等更新；③失败注入→Action fail-closed 非零退出；④发布前按铁律做模拟真实用户测试 |
| P1-R2 persona 五分钟通道 | 三条分流路径各配一条最短引导：TRAE/IDE 用户（host 委托，零 key）→ 技能列表即用；CLI 用户 → `init` 向导按后端分流（key/演示）；仓库维护者 → R1 Action 一行接入。落点：QUICKSTART 重构 + `init` 向导分流逻辑 | 验收：三个 persona 各一条模拟真实用户 e2e（从安装到看到第一份产出）；每条路径起点命令唯一且文档与实现一致（config consistency 扩展覆盖） |
| P1-R3 dogfooding 自证链 | "DevSquad on DevSquad" 季度报告：从自身门禁与审计链自动采集（金字塔比例/门禁绿数/PR 评论覆盖/债务进出），发布为对外价值证据；数字全部可复现（附采集命令） | 验收：首期报告产出，任一数字可用文档命令复现；无不可复现断言（TD-074 教训） |
| P1-R4 MCP 通道文档强化 | MCP server 已含 RBAC 与 fail-closed（mcp_server.py:236-406），补齐"Cursor/其他 IDE 经 MCP 使用"的安装与工具清单文档 | 验收：外部 IDE 按文档可完成连接（e2e 或截图证据） |

### 5.3 P2 工程闭环批——跨 run 缺陷台账（建议 V4.9.0 候选）

吸收上游 v2.14（设计细节见 10-20 跟踪文档 §3.1/§3.2，此处只列落点）：

| 项 | 内容 |
|---|---|
| defects.json 全局台账 | `defect add/update/close/reopen/audit/list`；DEF-NNN；工单必须挂真实信号（review finding / suspected_bug / FailureClass 记录），禁止凭空立案 |
| 状态机 | open →（登记修复 commit）→ fixed →（回归用例全 PASS）→ closed；closed→regressed→open（reopen 强制 reason）；上游踩过的两类缺陷（转移丢失/ID 复用）直接补齐实现 |
| 登记闸 | 台账启用后，任何 finding 未立案 → finalize/review gate=FAIL（fail-closed） |
| feature_gate 锚定 | 覆盖矩阵从执行记录现算（不信任自报）+ 清单 SHA256 锚定（防"移动球门"）；与审计链同源 |

验收：状态机全转移覆盖测试（含负向：无信号立案被拒、未立案发现打红 gate）；e2e 全生命周期链路；与 FailureClass 的映射测试（发现分类→台账信号类型）。

### 5.4 P3 评估批（先审计，后决定，不承诺实施）

| 项 | 内容 | 前置条件 |
|---|---|---|
| P3-E1 存量消费者审计 | 对借鉴型模块（teach/prototype/live-browser/meta-skill-layering/impeccable 词表/taste-dials）逐项回答"谁在什么场景用"；产出保留/冻结/移除三态清单 | 用户认可"审计先于扩张" |
| P3-E2 既有模块深度整合 | RiskRegister/RequirementTracer/DORA → 接入 spec/ship 生命周期命令的输出（让生命周期 CLI 有工程管理深度） | E1 完成后按裁定 |
| P3-E4 Loop-as-default 评估 | 评估"Plan→Dev→Verify→Fix 作为默认内核"距 VISION 的差距与成本 | P1/P2 稳定后 |

### 5.5 不做清单（Non-Goals，维护既有裁定的严肃性）

- 不做黑盒 Web/浏览器自动化/系统反向理解（上游 v2.9/v2.12 方向，场景与重依赖双重不符）。
- 不自建 LLM、不做去中心化、不做实时聊天循环（VISION.md §5 既有承诺，维持）。
- 不做使用遥测（隐私立场；价值度量改用 R3 自证报告 + 外部试点 + issue/PR 反馈）。
- 不在 P1/P2 期间新增借鉴型大功能模块（扩张冻结至 E1 审计完成）。

### 5.6 风险与权衡

| 风险 | 缓解 |
|---|---|
| R1 Action 打包带来跨仓库维护负担（GitHub API 变更/限流） | 评论协议保持 4 字段极简 + continue-on-error 边界（W2 已验证）；Action 输出协议带版本号 |
| R2 台账状态机复杂度失控 | 封闭状态集 + 每个转移强制字段；上游实现级教训直接复用；负向测试先行 |
| R3 P0 与 P1 并行造成发布窗口混乱 | 严格分批：P0 独立 PATCH 入库；P1 走 PR + 权威 CI + 发布前 e2e 铁律 |

---

## 6. 裁定请求（决策点）

| # | 决策 | 建议默认 |
|---|---|---|
| D1 | P0 卫生批是否立即执行（含两份跟踪文档 commit 入库） | 建议批准，独立 PATCH 批次 |
| D2 | P1 是否立项为 **V4.8.0 MINOR**（版本纪律需显式批准） | 建议批准；R1-R4 范围可裁减 |
| D3 | P2 缺陷台账是否排入 V4.9.0 | 建议批准（上游已验证，吸收成本低） |
| D4 | 是否认可"E1 消费者审计先于任何功能扩张"的原则 | 建议认可 |

## 7. 维护

- 本文档为 2026-10-20 评审快照。裁定后由对应批次 PRD/设计文档接管细节；本文 §4 通盘表在每次 MINOR 发布时同步。
