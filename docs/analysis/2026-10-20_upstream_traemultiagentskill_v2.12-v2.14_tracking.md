# 上游 TraeMultiAgentSkill 更新分析（v2.12 → v2.14）

> 文档类型：上游跟踪分析 | 日期：2026-10-20 | 分析基线：DevSquad V4.7.1（2026-10-15 已发布 PyPI + GitHub Release，main 干净）
> 上游仓库：[weiransoft/TraeMultiAgentSkill](https://github.com/weiransoft/TraeMultiAgentSkill)（无 release/tag，以 commit + CHANGELOG 演进）
> DevSquad 对齐基线：**v2.8.4 协议**（HostLLMBridge v2 的 7 字段 fail-closed marker、prompt_file、subagent_type 映射、fuse、资源上限、跨版本隔离、v1 强制回退）
> 本文独立完整，不依赖会话上下文。数据来源：
> ① `gh api 'repos/weiransoft/TraeMultiAgentSkill/commits?since=2026-10-13T00:00:00Z'`（13 commits，2026-10-20 采集）
> ② 上游 CHANGELOG.md 全文（raw 接口，2026-10-20 采集，v2.12–v2.14 三节逐字通读）
> 上一轮跟踪：[2026-10-12_upstream_traemultiagentskill_v2.11_tracking.md](2026-10-12_upstream_traemultiagentskill_v2.11_tracking.md)（覆盖 v2.8.4 → v2.11.0）

---

## 1. 结论速览

1. **协议兼容面：零破坏。** v2.12–v2.14 全部 13 个 commit 的 message 经关键词扫描（marker/host/bridge/protocol/contract/fail-closed），零命中；CHANGELOG 三节通读，无任何 marker 协议、7 字段契约、prompt_file、subagent_type、fuse、资源上限的变更条目。DevSquad HostLLMBridge v2 兼容性维持。注意概念区分：v2.12 的"三宿主"指浏览器执行宿主（agent-browser / chrome-devtools / trae-internal 降级链），与宿主 LLM 委托协议无关。
2. **上游三版本是一条递进链**：浏览器测试闭环（v2.12）→ 数据校验闭环（v2.13）→ 功能覆盖与缺陷台账（v2.14），全部挂在"黑盒 Web 系统"垂直能力包上。场景与浏览器宿主依赖同 v2.9 判定，**整体实现不跟进**。
3. **但 v2.13/v2.14 的确定性内核与门禁方法论与本仓高度同构**，2 项建议吸收（若裁定）、2 项确认无需动作：
   - ① 跨 run 缺陷台账状态机 + 登记闸（v2.14，借鉴价值最高）
   - ② feature_gate 现算覆盖矩阵 + 清单 SHA256 锚定（v2.14，与①自然搭配）
   - ③ 非 eval 受限表达式求值器（v2.13，储备参考，不立项）
   - ④ "声明必执行"反静默跳过 + env_failure 诚实降级（v2.13，与本仓 pass|fail|tool_missing 三态同款，无需动作）
4. **建议动作**：①+② 合并为 1 个 P3 backlog 候选，待用户裁定后立项；维持事件驱动跟踪节奏（详见 §5）。

---

## 2. 上游版本明细（v2.11.0 之后）

| 版本 | 日期 | commit | 关键内容 | 对 DevSquad 的相关性 |
|---|---|---|---|---|
| v2.12.0 | 2026-10-14 | 83bf76a1 | 浏览器端页面功能与视觉测试闭环。三阶段 prompt（planner：OP-\* 操作点 + DT-\* 六类数据集 P/B/N/E/A/T + TC-\* 用例，缺类须书面理由；四角色评审复用 v2.10 共识收敛；三宿主执行 + 六条铁律 + 六类阻碍协议）+ 纯标准库 `browser_test_recorder.py`（9 子命令，schema 强制，finalize 做 summary 数字与逐条记录一致性核对 + P0 100% 门禁，20 单测）+ 7 个 CLI flags + 互斥校验扩展 + 三 manifest 同步；断点回填 v2.11 BREAK 清单（双向闭环） | 低。场景（黑盒 Web 浏览器测试）与浏览器宿主依赖同 v2.9 判定；recorder 的"汇总数字与逐条记录一致性核对"门禁模式与本仓 anti-ghost 同源，仅方法论层面 |
| v2.13.0 | 2026-10-15 | 3796d49e（docs b0244401） | 数据校验闭环。`data_rules.py`（自研 tokenizer + 递归下降求值器，**非 eval**，白名单文法；UNIQ/INV/CONS/SM/REF 五类规则；主键对齐行级 diff）+ `db_probe.py`（复用 ReadOnlyGuard 唯一语句通道：仅 SELECT/SHOW/EXPLAIN、拒多语句、参数化；驱动缺失诚实降级 env_failure，无硬依赖引入）+ recorder 三新子命令（db-snapshot/dc-check/rule）+ "声明必执行"反静默跳过 + finalize **data_gate**；11 新用例含真实 SQLite 全链路 4 场景 | 中。求值器与只读守卫有独立方法论价值（§3.3）；"声明必执行 + env_failure → BLOCKED"与本仓 verify_prometheus_e2e.py 的 pass\|fail\|tool_missing 三态同款 |
| v2.14.0 | 2026-10-16 | f28da009（docs a2a38586） | 功能覆盖驱动测试与缺陷台账。FUNC-\* 每页功能清单（kind 五类 interactive/form/display/nav/branch，evidence 强制文件:行号，interactive/form 禁豁免，display/nav 豁免须书面 waive_reason）+ **feature_gate**（finalize 从执行记录现算 FUNC×PASS 矩阵，不信任自报；清单 SHA256 锚定防篡改）+ **defects.json 跨 run 缺陷台账**（信号-工单模型，open→fixed→closed 状态机 + regressed 回炉，DEF-NNN 扫 history 防 ID 复用）+ **登记闸**（suspected_bug 无工单 → finalize FAIL）+ finalize 四门禁（P0/data_gate/feature_gate/登记闸）；19 用例，三版全量回归 50 passed | **高**。缺陷状态机与本仓 FailureClass/TECH_DEBT 管理同构；现算覆盖矩阵与 anti-ghost 原理同源；SHA256 锚定与本仓审计链同源（§3.1/§3.2） |
| （非发版） | 2026-10-18 | 2fa329e8 等 5 个 | 公众号进化史素材（v2.9–v2.14 六篇合辑 + SVG/PNG 贴图），纯文档/营销 | 无 |

> 计数出入记录（诚实留痕）：上游 CHANGELOG 中 v2.14 用例分项计数 7+3+7+1=18，与总量 19 差 1；三版回归 50=20+11+19 自洽。不影响功能结论，仅记录核查发现。

## 3. 可借鉴点详析

### 3.1 跨 run 缺陷台账状态机（v2.14，借鉴价值最高）

上游把"缺陷"从一次性产物升级为**跨 run 生命周期对象**：

- **信号-工单模型**：执行期 `error --suspected-bug` 是信号；`defect add` 才是正式工单，且 `bug_ref` 强制关联真实信号的 error_seq——禁止凭空立案。
- **状态机**：open →（update --commit 登记修复 commit + 摘要）→ fixed →（回归 run 关联用例全 PASS 核对）→ closed；closed → regressed → open（reopen 强制 reason，并清空 fix/regression 字段）。每个转移都有强制字段，防"口头关闭"。
- **登记闸**：台账启用后，任何 suspected_bug 信号未登记 DEF-\* 工单 → finalize gate=FAIL。**信号不许蒸发**。
- **防 ID 复用**：DEF-NNN 分配既扫台账现存条目，也扫 history 中的 add 记录，已删工单 ID 不回收。

与本仓的亲缘关系：`failure_taxonomy.py` 的 FailureClass 是运行时失败的封闭分类学；TECH_DEBT 台账管已知欠账。上游补齐了两者之间的**生命周期维度**——发现（信号）→ 立案（工单）→ 修复（commit）→ 回归（全 PASS）→ 关闭，与"audit finding 必须先复现"铁律同源：发现必须收敛到可追踪对象，且"发现了没立案"本身就是 gate FAIL。

潜在落点（若立项）：review/test 子技能的跨 run 产物。本仓 Scratchpad/WorkflowTrace 是 run 内状态；缺一个跨 run 的缺陷台账 + finalize 门禁交叉核对。属 P3 backlog 候选。

### 3.2 feature_gate 现算覆盖矩阵 + 清单 SHA256 锚定（v2.14）

- **现算而非自报**：finalize 从执行记录现算 FUNC × PASS 断言关联矩阵，不信任执行侧自报覆盖。interactive/form 任一未覆盖 → 整体 FAIL。
- **豁免留痕**：display/nav 可豁免，但必须书面 waive_reason，summary 渲染 waived 溯源与缺口清单（归属页面 + kind）。
- **防"移动球门"**：功能清单原件的 SHA256 写入 run 元数据；执行期篡改清单即 FAIL。

与本仓的亲缘关系：与 AntiGhostChecker（模块必须激活而非仅存在）原理同源——**声明 ≠ 覆盖，必须拿执行记录现算**；SHA256 锚定与 WorkflowTrace 审计链同源；豁免须书面理由 = fail-closed 的例外必须留痕。若做 §3.1 缺陷台账，覆盖矩阵现算 + 清单哈希锚定是自然搭配，建议同批。

### 3.3 非 eval 受限表达式求值器 + 只读快照守卫（v2.13，储备参考）

- `data_rules.py`：自研 tokenizer + 递归下降解析器，白名单文法（字段引用/字面量/比较/四则/`len()`/聚合 count/sum/min/max/exists），明确不用 eval。若未来本仓四层规则链外扩"用户可写规则表达式"类 DSL，这是现成的安全设计参考。**现阶段无落点，储备。**
- `db_probe.py`：ReadOnlyGuard 唯一语句通道（仅 SELECT/SHOW/EXPLAIN、多语句拒绝、参数化传参）+ env_failure 诚实降级（断言 BLOCKED 而非谎报 FAIL/PASS）。与本仓 `verify_prometheus_e2e.py` 的 pass|fail|tool_missing 三态同款——再次确认本仓纪律自洽，无需动作。

### 3.4 无需动作项（避免重复建设）

- **v2.12 三宿主浏览器执行闭环**：场景（无源码黑盒 Web）+ 浏览器宿主依赖，同 v2.9"不建议跟进"判定；其四角色用例评审复用的正是 v2.10 共识收敛，本仓 consensus（并行投票 + 共识门 fail-closed）已覆盖且更强。
- **"声明必执行"反静默跳过（v2.13）**：本仓各 gate 已是 fail-closed，模式一致，无新意。
- **finalize 多门禁收敛（v2.14）**：本仓质量门禁链（金字塔/静态链/config consistency）同构，无需对齐。
- 旁证：v2.14 Fixed 段修了 planner prompt 引用路径漂移（`scripts/data/` → `scripts/data_test/`）等文档-实现漂移问题，处置方式与本仓 config consistency 门禁同思路，相互印证。

## 4. 协议兼容性核查记录

核查方式（2026-10-20）：

- `gh api 'commits?since=2026-10-13T00:00:00Z'`（13 commits）全量 message 关键词扫描：marker / host / bridge / protocol / contract / fail-closed → **零命中**。
- CHANGELOG.md v2.12–v2.14 三节逐字通读 → 无 marker 协议、7 字段契约、prompt_file、subagent_type、fuse、资源上限的任何变更条目。
- 新能力仍走"宿主 LLM 派发 + 提示词契约回填"既有通道；确定性内核（recorder / data_test）为纯 Python 标准库或可选驱动，不触碰协议面。
- 概念区分：v2.12"三宿主"= 浏览器执行宿主降级链，非 HostLLMBridge 宿主 LLM 委托。

结论：**DevSquad HostLLMBridge v2 与上游 v2.14.0 仍兼容**。下次真实监听方联调（若 TRAE IDE 升级触发）前再复查一次即可。

## 5. 跟踪策略建议

- 维持**事件驱动**：季度例行或用户提及上游时执行同类扫描，更新本文档"版本明细"表。
- 上游 2026-10-18 起 commit 全部为公众号传播素材，表明其处于 v2.14 后的传播期；v2.15 出现前无跟踪紧迫性。
- 若上游出现 marker 协议 BREAKING：先在本地 TRAE IDE 真实联调复现 → 更新 `DEVSQUAD_HOST_BRIDGE_VERSION` fail-closed flag → 补 e2e 证据（复用 V4.5.12 框架）。

## 6. 裁定记录

- 2026-10-12：v2.8.4→v2.11.0 跟踪完成（见上一轮文档）；其中 BREAK/VULN 分类学借鉴已通过 V4.7.0 W1 `review_taxonomy.py` 落地（PR #34/#35）。
- 2026-10-20：用户指示执行 v2.12–v2.14 扫描，本文档即产出。吸收建议**待用户裁定**：
  - 建议吸收（合并为 1 个 P3 backlog 候选）：缺陷台账状态机 + 登记闸（§3.1）；feature_gate 现算覆盖矩阵 + SHA256 锚定（§3.2）。
  - 储备不立项：非 eval 受限求值器（§3.3）。
  - 不吸收：v2.12 浏览器闭环、"声明必执行"反静默跳过、finalize 多门禁收敛（§3.4）。
