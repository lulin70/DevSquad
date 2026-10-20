# 上游 TraeMultiAgentSkill 更新分析（v2.8.4 → v2.11.0）

> 文档类型：上游跟踪分析 | 日期：2026-10-12 | 分析基线：DevSquad V4.6.0（PR #29 待合并）
> 上游仓库：[weiransoft/TraeMultiAgentSkill](https://github.com/weiransoft/TraeMultiAgentSkill)（45 stars，无 release/tag，以 commit + CHANGELOG 演进）
> DevSquad 对齐基线：**v2.8.4 协议**（2026-07-23；HostLLMBridge v2 的 7 字段 fail-closed marker、prompt_file、subagent_type 映射、fuse、资源上限、跨版本隔离、v1 强制回退——V4.5.12 与 TRAE IDE 3.3.95 真实联调覆盖）
> 本文独立完整，不依赖会话上下文。数据来源：上游 CHANGELOG.md 与 commit 历史（`gh api repos/weiransoft/TraeMultiAgentSkill/...`，2026-10-12 采集）。

---

## 1. 结论速览

1. **协议兼容面：零破坏，无需紧急跟进。** v2.9.0–v2.11.0 全部是上层能力扩展（新 prompt 模板 / 新 CLI flags / 新模块包），CHANGELOG 中无任何 marker 协议、host bridge 契约、marker 字段口径的变更。DevSquad 的 HostLLMBridge v2 不受影响。
2. **上游重心已从"多角色编排协议"转向"垂直能力包"**：v2.9 起连续三个版本都在做黑盒系统理解（SU/SFD）与方案/页面级质量闭环（proposal-review / business-flow），与 DevSquad 的 CLI/MCP 编排器定位渐行渐远。**不建议跟进 SU/SFD**（场景不同 + Playwright/DB 驱动重依赖）。
3. **三个可借鉴点**，按价值排序：①BREAK/VULN 分类学（与本仓 FailureClass 分类学同构，编号化方法论值得移植到 review 子技能）；②SU 五条安全红线（未来只读内省类能力的现成 checklist）；③互斥 flag 统一前置校验（v2.11 重构，DevSquad CLI 已有类似校验，模式一致，无需动作）。
4. **建议动作**：立 1 个 backlog 项（BREAK/VULN 分类学借鉴）；每季度或收到用户信号时再扫一次上游（本仓无自动上游跟踪门禁）。

---

## 2. 上游版本明细（v2.8.4 之后）

| 版本 | 日期 | 主题 | 关键内容 | 对 DevSquad 的相关性 |
|---|---|---|---|---|
| v2.9.0 | 2026-09-28 | SU 系统理解 | 黑盒遗留 Web 系统只读反向理解：Playwright 自动登录（会话维持、`--storage-state` 旁路）+ 图式 BFS 页面遍历（url_key 去重、动作三级分级 T1/T2/T3、网络层拦截非 GET）+ MySQL/PostgreSQL 只读内省（隐式 FK 三重预筛）+ Redis SCAN 采集 + UI↔API↔DB 三角关联；产出 10 节文档 + understanding.json + Mermaid；SQLite WAL 断点续跑；18 模块 + 400+ 测试 | 低。场景（无源码黑盒 Web）与本仓（有源码编排器）不同；重依赖（playwright/pymysql/psycopg2/redis）与本仓轻依赖原则冲突 |
| v2.9.1 | 2026-09-30 | SFD 专家详说 | SU 第三阶段：五专家子代理分节撰写《系统功能详说文档》（8 节大纲 + assemble 装配 + (seq,ref) 双键锚点漂移检测 + 凭据四判据扫描） | 低。依赖 SU 产物 |
| v2.9.2 | 2026-09-30 | D1 修复 | `understanding.json` 的 `meta.run_status` 渲染收口即终态（`run_status_override` + 终态白名单校验，非法值 ValueError） | 无直接关系。但"状态收口必须投影终态、白名单校验"与本仓 fail-closed 纪律一致 |
| （非发版） | 2026-09-30 | dynamic-workflows v2.6 | 动态工作流模块与测试入仓（Phase 4-10 融合产物） | 未在 CHANGELOG 立节，成熟度存疑，观察 |
| （非发版） | 2026-10-11 | vue-dual-stack-migration | 双栈迁移模式 + 角色提示词扩充（patterns 目录） | 低。Vue 专项 |
| v2.10.0 | 2026-10-12 | proposal-review | 方案撰写全流程：业界调研（真实 WebSearch）→ 方案撰写 → **四角色交叉评审**（架构师/产品/测试/独立开发）→ 共识收敛 → 迭代修改 | 中。与 DevSquad consensus 机制重叠度高，借鉴价值有限；其"四角色 = 我们 7 角色子集" |
| v2.11.0 | 2026-10-12 | business-flow-analysis | 页面级业务质量闭环：SU 页面盘点 → 流转路径 → **5 类逻辑断点（BREAK-1~5）+ 5 类业务线漏洞（VULN-1~5）** → 欠缺页面清单（GAP-001~N）→ GAP-DESIGN 9 段式设计（含"与现有页面的衔接点★强制精准到代码位置"）→ 多角色评审 → 开发 → UI/UX 测试；6 个 CLI flags + 特殊模式互斥统一前置校验 | **方法论高**（见 §3.1）；实现不强求 |

## 3. 可借鉴点详析

### 3.1 BREAK/VULN 分类学（v2.11，借鉴价值最高）

上游把"页面级业务质量问题"编号化为两个封闭集合：

| 集合 | 编号 | 含义 |
|---|---|---|
| 逻辑断点 | BREAK-1~5 | 入口断裂 / 出口断裂 / 前置条件缺失 / 数据衔接断裂 / 业务闭环断裂 |
| 业务线漏洞 | VULN-1~5 | 数据泄漏 / 状态不一致 / 操作不可达 / 边界缺失 / 导航不一致 |

与本仓的亲缘关系：`failure_taxonomy.py` 的 `FailureClass`（product_failed / environment_blocked）是**运行时失败**的分类学；BREAK/VULN 是**设计产物质量**的分类学。两者同构——封闭编号集合 + 每类明确定义 + 结论必须挂证据（上游强制"每个分析必须有 SU 采集产物或代码证据，禁止凭空推断"，与本仓"audit finding 必须先复现"铁律同源）。

潜在落点（若立项）：review 子技能的确定性规则侧——四层规则优先级链（V4.5.0 设计）目前匹配的是代码模式；可新增"页面/路由级断点检查"类目，用 BREAK/VULN 编号输出发现。属 P3 backlog，不在当前批次。

### 3.2 SU 五条安全红线（v2.9，作为未来 checklist 储备）

凭据不落盘明文（统一 redact 管线 + 日志全程脱敏）；DB 会话只读 + SQL 语句白名单；Redis 命令只读白名单；浏览器网络层拦截全部非 GET 与白名单外域；危险按钮零点击只记录。与本仓既有纪律（key 不明文、fail-closed、诚实降级"绝不以假数据冒充"）完全一致——未来若做任何"读取用户环境"的能力（如 Dashboard 读本地配置、e2e 读 CI 环境），直接复用此清单做威胁建模。

### 3.3 无需动作项（避免重复建设）

- proposal-review 四角色评审：DevSquad consensus（并行投票 + 共识门 fail-closed）已覆盖且更强。
- 互斥 flag 前置统一校验：本仓 CLI 已有同类校验；上游只是补齐，无新意。
- 诚实降级声明（依赖缺失时显式声明未采集）：本仓 `verify_prometheus_e2e.py` 的 `pass|fail|tool_missing` 三态已是同款。

## 4. 协议兼容性核查记录

核查方式：通读上游 v2.9.0–v2.11.0 三段 CHANGELOG 全文 + 扫描 commit 历史（2026-10-12 03:05 UTC 最新提交）。

- 无任何条目提及 marker 字段、7 字段契约、prompt_file、subagent_type、fuse、资源上限的变更。
- 新能力全部通过"宿主 LLM 派发子代理 + 提示词契约回填"的既有通道构建（如 SFD 的五位专家派发），即上游也在沿用 v2.8.4 协议面。
- 结论：**DevSquad HostLLMBridge v2 与上游 v2.11.0 仍兼容**；下次真实监听方联调（若 TRAE IDE 升级触发）前再复查一次即可。

## 5. 跟踪策略建议

- 本仓无上游自动跟踪门禁（上游无 release/tag，`gh api` 轮询 CHANGELOG 是唯一低成本手段）。建议维持**事件驱动**：季度例行或用户提及上游时执行一次本档同类扫描，更新本档"版本明细"表。
- 若上游未来出现 marker 协议变更（BREAKING），处置路径：先在本地 TRAE IDE 真实联调环境复现 → 更新 `DEVSQUAD_HOST_BRIDGE_VERSION` fail-closed flag → 补 e2e 证据（V4.5.12 框架就位，直接复用）。

## 6. 裁定记录

- 2026-10-12：用户指示"沉淀为分析文档"，本文档即产出。BREAK/VULN 借鉴立项与否待用户裁定（建议：backlog P3）。
- 2026-10-20：BREAK/VULN 借鉴已落地（V4.7.0 W1 `review_taxonomy.py`，PR #34/#35）。v2.12–v2.14 跟踪扫描完成，产出 [2026-10-20_upstream_traemultiagentskill_v2.12-v2.14_tracking.md](2026-10-20_upstream_traemultiagentskill_v2.12-v2.14_tracking.md)。
