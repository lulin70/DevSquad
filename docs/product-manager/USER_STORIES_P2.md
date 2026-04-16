# Phase 2: PermissionGuard 权限守卫 — 用户故事与场景

**版本**: v1.0
**日期**: 2026-04-15
**作者**: 产品经理 (PM Role)
**基于**: v3-phase2-permission-design.md

---

## 用户画像

### 用户A: 项目管理员
- 管理多个 AI Agent 协作项目
- 关注系统安全性和操作可审计性
- 需要灵活配置权限策略

### 用户B: 开发者/使用者
- 使用 TraeMultiAgentSkill 执行开发任务
- 希望正常工作流不被过度打断
- 偶尔需要执行敏感操作（如 git push）

### 用户C: 安全审计员
- 定期审查系统操作日志
- 关注异常操作和潜在风险
- 需要完整的决策追溯链

---

## Epic 1: 4级权限分级

### US-1.1: 作为管理员，我希望在 PLAN 模式下所有写操作被拦截
**优先级**: P0 | **复杂度**: 中 | **风险**: 低

**用户故事**:
> 当我开启 **PLAN（计划）模式**时，我希望系统能完全禁止任何文件创建、修改、删除、Shell执行和网络请求，只允许只读操作。这样我可以在不产生实际变更的情况下预览 Agent 的行为。

**验收标准 (AC)**:
- [ ] PLAN 模式下 `FILE_CREATE` → `DecisionOutcome.DENIED`
- [ ] PLAN 模式下 `FILE_MODIFY` → `DecisionOutcome.DENIED`
- [ ] PLAN 模式下 `FILE_DELETE` → `DecisionOutcome.DENIED`
- [ ] PLAN 模式下 `SHELL_EXECUTE` → `DecisionOutcome.DENIED`
- [ ] PLAN 模式下 `FILE_READ` → `DecisionOutcome.ALLOWED`
- [ ] 切换到其他级别后，之前被拒绝的操作可以重新提交

**场景**:
```
场景 1.1.1: PLAN模式下的代码修改尝试
  Given 当前权限级别为 PLAN
  When 架构师Worker 尝试修改 src/main.py
  Then 返回 DecisionOutcome.DENIED, reason 包含 "PLAN模式禁止写操作"
  And 审计日志记录该拒绝事件

场景 1.1.2: PLAN模式下的读取操作放行
  Given 当前权限级别为 PLAN
  When 测试专家Worker 读取 test_config.json
  Then 返回 DecisionOutcome.ALLOWED
```

---

### US-1.2: 作为开发者，我希望 DEFAULT 模式对危险操作要求确认
**优先级**: P0 | **复杂度**: 中 | **风险**: 低

**用户故事**:
> 在默认的 **DEFAULT 模式**下，我希望普通操作（读文件、创建 .py/.md 文件）能自动通过，但危险操作（删除文件、sudo命令、修改凭据文件）必须提示我确认后再执行。

**验收标准 (AC)**:
- [ ] 创建 `.py` / `.md` 文件 → `ALLOWED` 或 `PROMPT`（取决于规则）
- [ ] 修改 `.env` 或 `credentials` 文件 → `PROMPT`（需确认）
- [ ] 执行 `rm -rf` 命令 → `PROMPT`（需确认）
- [ ] 执行 `sudo` 命令 → `PROMPT`（需确认）
- [ ] 普通文件读取 → `ALLOWED`

**场景**:
```
场景 1.2.1: 默认模式下创建Python文件
  Given 当前权限级别为 DEFAULT
  When 开发者Worker 创建新文件 utils/helper.py
  Then 返回 ALLOWED（匹配规则 R002）

场景 1.2.2: 默认模式下修改环境变量文件
  Given 当前权限级别为 DEFAULT
  When Worker 尝试修改 .env 文件
  Then 返回 PROMPT, requires_confirmation=True
  And reason 包含 "高风险" 或 "需确认"

场景 1.2.3: 默认模式下执行rm命令
  Given 当前权限级别为 DEFAULT
  When Worker 尝试执行 shell: rm -rf dist/
  Then 返回 PROMPT, risk_score >= 0.9
```

---

### US-1.3: 作为高级用户，我希望 AUTO 模式用AI智能判断安全性
**优先级**: P1 | **复杂度**: 高 | **风险**: 中

**用户故事**:
> 在 **AUTO（自动）模式**下，我希望系统能根据操作的上下文（目标路径、操作类型、历史模式）自动判断是否安全。对于明显安全的操作直接放行，对于可疑操作才提示确认。这样可以在安全和效率之间取得平衡。

**验收标准 (AC)**:
- [ ] `auto_classify()` 返回 [0.0, 1.0] 范围的风险评分
- [ ] 低风险操作（score < 0.3）→ `ALLOWED`
- [ ] 中风险操作（0.3 ≤ score < 0.7）→ `PROMPT`
- [ ] 高风险操作（score ≥ 0.7）→ `PROMPT` 或 `DENIED`
- [ ] 白名单中的操作始终 `ALLOWED`
- [ ] 分类结果包含评估维度说明

**场景**:
```
场景 1.3.1: AUTO模式下的安全操作自动放行
  Given 当前权限级别为 AUTO
  And 白名单包含 "pip list", "python -m pytest"
  When Worker 执行 pip list
  Then 返回 ALLOWED, confidence > 0.9

场景 1.3.2: AUTO模式下的可疑操作触发确认
  Given 当前权限级别为 AUTO
  When Worker 尝试 curl http://unknown-api.example.com/data
  Then auto_classify() 返回 risk_score > 0.5
  And 返回 PROMPT, requires_confirmation=True

场景 1.3.3: AUTO模式的5维度评分可见
  Given 一个 ProposedAction
  When 调用 auto_classify(action)
  Then 返回值在 [0.0, 1.0] 区间内
  And 可查看各维度得分明细
```

---

### US-1.4: 作为受信用户，我希望 BYPASS 模式完全跳过检查
**优先级**: P1 | **复杂度**: 低 | **风险**: 高

**用户故事**:
> 在特定的高信任场景（如 CI/CD 环境、本地全权开发会话），我希望 **BYPASS 模式**能让所有操作直接通过，不做任何检查。但这个模式应该有明确的启用条件，防止误用。

**验收标准 (AC)**:
- [ ] BYPASS 模式下所有操作 → `ALLOWED`
- [ ] 审计日志仍然记录（标记为 BYPASS 绕过）
- [ ] 启用 BYPASS 需要显式调用 `set_level(BYPASS)`
- [ ] 不支持通过规则配置自动切换到 BYPASS

**场景**:
```
场景 1.4.1: BYPASS模式全部放行
  Given 当前权限级别为 BYPASS
  When Worker 执行任意操作（包括 rm -rf, sudo）
  Then 返回 ALLOWED
  And 审计日志记录该操作，标记 guard_level=BYPASS

场景 1.4.2: BYPASS模式仍有审计追踪
  Given 当前权限级别为 BYPASS
  When 连续执行10个不同类型操作
  Then get_audit_log() 能返回全部10条记录
  And 每条记录的 guard_level = BYPASS
```

---

## Epic 2: 规则引擎

### US-2.1: 作为管理员，我希望使用默认规则集即可覆盖常见场景
**优先级**: P0 | **复杂度**: 低 | **风险**: 低

**用户故事**:
> 我希望系统自带一套经过验证的 **30条默认规则**，覆盖文件读写、Shell命令、网络请求、Git操作等常见操作类型。这样开箱即用，无需手动配置就能获得基本的安全保护。

**验收标准 (AC)**:
- [ ] 默认加载 30 条规则
- [ ] 覆盖 8 种 ActionType
- [ ] 每条规则有唯一的 rule_id
- [ ] 规则按 action_type + pattern 组织
- [ ] 敏感操作（.env/credentials/rm/sudo）分配最高风险分

**场景**:
```
场景 2.1.1: 默认规则数量验证
  Given 新建 PermissionGuard()
  Then 加载了 30 条默认规则
  And 覆盖 FILE_READ, FILE_CREATE, FILE_MODIFY, FILE_DELETE,
      SHELL_EXECUTE, NETWORK_REQUEST, GIT_OPERATION, ENVIRONMENT

场景 2.1.2: 敏感文件规则存在
  Given 默认规则集
  When 查找匹配 ".env" 的 FILE_MODIFY 规则
  Then 存在 rule_id="R009", required_level=BYPASS, risk_boost=0.8
```

---

### US-2.2: 作为管理员，我希望动态添加和移除自定义规则
**优先级**: P0 | **复杂度**: 低 | **风险**: 低

**用户故事**:
> 我希望能在运行时动态添加新规则或移除现有规则，而不需要重启系统。这样我可以根据项目的特殊安全需求定制权限策略。

**验收标准 (AC)**:
- [ ] `add_rule(rule)` 成功添加到规则列表
- [ ] `remove_rule(rule_id)` 成功移除指定规则
- [ ] 移除后该规则不再影响后续 check()
- [ ] 添加重复 rule_id 时抛出异常或覆盖
- [ ] 支持批量导入规则（import_rules）

**场景**:
```
场景 2.2.1: 添加自定义规则
  Given PermissionGuard 含30条默认规则
  When 添加规则: 禁止在 /etc/ 下创建文件, required_level=BYPASS
  Then 规则总数变为31
  And 对 /etc/config.conf 的 FILE_CREATE 操作返回 DENIED/PROMPT

场景 2.2.2: 移除规则
  Given PermissionGuard 含30条默认规则
  When 移除 rule_id="R009" (.env修改规则)
  Then 规则总数变为29
  And 对 .env 的 FILE_MODIFY 回退到通用规则 R011

场景 2.2.3: 导入导出规则
  Given 一组自定义规则
  When export_rules() → JSON
  And 在新实例中 import_rules(JSON)
  Then 两边规则集一致
```

---

### US-2.3: 作为开发者，我希望规则支持多种匹配模式
**优先级**: P1 | **复杂度**: 中 | **风险**: 低

**用户故事**:
> 我希望规则的 `pattern` 字段支持 **glob 模式**（通配符）、**前缀匹配** 和 **正则表达式** 三种方式，这样可以精确描述各种目标路径和命令模式。

**验收标准 (AC)**:
- [ ] glob 模式: `"*.py"` 匹配所有 .py 文件
- [ ] glob 模式: `"src/**/*.py"` 匹配 src 目录递归
- [ ] 前缀匹配: `"git "` 匹配以 git 开头的命令
- [ ] 正则模式: `r"rm\s+-.*f"` 匹配 rm -f 变体
- [ ] 多条规则匹配时取最严格的结果

**场景**:
```
场景 2.3.1: Glob通配符匹配
  Given 规则 pattern="*.py", action_type=FILE_MODIFY
  When 检查 target="utils/helper.py"
  Then 规则匹配成功

场景 2.3.2: 前缀匹配Shell命令
  Given 规则 pattern="git ", action_type=SHELL_EXECUTE
  When 检查 target="git status"
  Then 规则匹配成功

场景 2.3.3: 正则表达式匹配
  Given 规则 pattern=r"rm\s+-.+", action_type=SHELL_EXECUTE
  When 检查 target="rm -rf /tmp/cache"
  Then 规则匹配成功
```

---

## Epic 3: 审计日志

### US-3.1: 作为安全审计员，我希望每次权限决策都有完整记录
**优先级**: P0 | **复杂度**: 低 | **风险**: 低

**用户故事**:
> 我希望系统的每一次 `check()` 调用都生成一条 **审计日志**，记录操作内容、决策结果、命中规则、耗时等完整信息。这样事后我可以完整回溯任何一次权限判断的过程和原因。

**验收标准 (AC)**:
- [ ] 每次 check() 生成一条 AuditEntry
- [ ] 包含: entry_id, action详情, decision结果, matched_rule, reason
- [ ] 包含: 当时的 guard_level, timestamp, duration_ms
- [ ] 日志持久化在内存中（可扩展到磁盘）
- [ ] 支持按时间/类型/结果/Worker 过滤查询

**场景**:
```
场景 3.1.1: 单次操作产生审计日志
  Given PermissionGuard 启用了 audit_log=True
  When check(ProposedAction(FILE_DELETE, "important_data.json"))
  Then get_audit_log() 包含该条目
  And 条目的 decision.outcome != None
  And 条目的 duration_ms >= 0

场景 3.1.2: 审计日志过滤查询
  Given 已执行50次check操作
  When get_audit_log(outcome=DENIED)
  Then 仅返回被拒绝的操作记录
  When get_audit_log(action_type=SHELL_EXECUTE)
  Then 仅返回Shell操作记录
```

---

### US-3.2: 作为管理员，我希望看到安全统计报告
**优先级**: P1 | **复杂度**: 中 | **风险**: 低

**用户故事**:
> 我希望系统能生成一份 **安全报告**，汇总总检查次数、通过率/拒绝率/确认率、平均风险分数、最常见的被拒操作等关键指标。这让我快速了解系统的安全状态。

**验收标准 (AC)**:
- [ ] `get_security_report()` 返回结构化统计数据
- [ ] 包含: total_checks, allowed/denied/prompted/escalated 计数
- [ ] 包含: avg_risk_score, top_denied_actions 排行
- [ ] 报告数据来自审计日志

**场景**:
```
场景 3.2.1: 安全报告完整性
  Given 已执行多种类型的操作
  When 调用 get_security_report()
  Then 返回字典包含以下key:
    total_checks, allowed, denied, prompted, escalated,
    avg_risk_score, top_denied_actions
  And allowed + denied + prompted + escalated == total_checks
```

---

## Epic 4: 与协作系统集成

### US-4.1: 作为协调器，我希望 Worker 执行前自动进行权限检查
**优先级**: P0 | **复杂度**: 中 | **风险**: 中

**用户故事**:
> 当 Coordinator 调度 Worker 执行任务时，我希望每个 Worker 的每个操作都能 **自动经过 PermissionGuard 检查**，无需 Worker 自行处理权限逻辑。这样权限控制是统一的、强制的、不可绕过的。

**验收标准 (AC)**:
- [ ] Worker.execute_with_guard(task, guard) 自动包装权限检查
- [ ] ALLOWED 的操作正常执行
- [ ] DENIED 的操作跳过并记录错误
- [ ] PROMPT 的操作暂停等待回调
- [ ] ESCALATED 的操作写入 Scratchpad 冲突

**场景**:
```
场景 4.1.1: Worker 通过 Guard 执行任务
  Given Coordinator 配置了 PermissionGuard(DEFAULT)
  And 分配了一个任务给架构师Worker
  When Worker 尝试创建文件 + 读取文件 + 修改文件
  Then 每个操作都经过 guard.check()
  And 结果符合各操作的权限规则

场景 4.1.2: 被拒绝的操作不影响其他操作
  Given Worker 要执行5个操作
  When 第3个操作被 DENIED
  Then 第1、2、4、5个操作正常处理
  And 第3个操作的失败原因记录在 WorkerResult.errors 中
```

---

### US-4.2: 作为协调器，我希望 ESCALATED 操作触发共识流程
**优先级**: P2 | **复杂度**: 高 | **风险**: 中

**用户故事**:
> 当某个操作超出了当前权限级别的处理能力（ESCALATED），我希望系统能 **自动将此问题升级为共识投票**，让多个 Worker 讨论后决定是否临时放行此操作。这体现了多 Agent 协作的优势——集体智慧优于单一判断。

**验收标准 (AC)**:
- [ ] ESCALATED 决策 → Scratchpad 写入 CONFLICT 条目
- [ ] Coordinator.detect_escalations() 发现待处理的升级
- [ ] 发起 ConsensusEngine 投票
- [ ] 共识通过 → 临时放行；未通过 → 保持拒绝

**场景**:
```
场景 4.2.1: ESCALATED触发共识
  Given PermissionGuard 返回 ESCALATED 决策
  When Coordinator 处理该决策
  Then Scratchpad 出现一条 CONFLICT 类型条目
  And 内容包含操作详情和风险评分
  And resolve_conflicts() 会发现该冲突并发起投票
```

---

## Epic 5: 边界与异常

### US-5.1: 作为系统，我希望正确处理空输入和非法输入
**优先级**: P0 | **复杂度**: 低 | **风险**: 低

**验收标准 (AC)**:
- [ ] 空 ProposedAction → 合理的默认决策（DENIED 或 ALLOWED 取决于设计）
- [ ] 空目标字符串 → 不崩溃，返回明确错误
- [ ] 未知的 ActionType → 使用兜底规则
- [ ] None 值字段 → 有合理默认值

**场景**:
```
场景 5.1.1: 空操作检查
  When check(ProposedAction(action_type=FILE_READ, target=""))
  Then 返回有效 PermissionDecision, 不抛异常

场景 5.1.2: 全空字段
  When check(ProposedAction())
  Then 返回有效 PermissionDecision, outcome=DENIED 或有明确reason
```

---

### US-5.2: 作为系统，我希望高并发下权限检查线程安全
**优先级**: P1 | **复杂度**: 中 | **风险**: 中

**验收标准 (AC)**:
- [ ] 多线程同时调用 check() 不崩溃
- [ ] 审计日志不丢失、不乱序
- [ ] 动态 add_rule/remove_rule 线程安全

**场景**:
```
场景 5.2.1: 并发检查
  Given 10个线程同时调用 check() 各100次
  Then 所有调用正常返回
  And 审计日志总数 == 1000
  And 无数据竞争异常
```

---

## 边界场景清单

| # | 场景 | 预期行为 | 优先级 |
|---|------|---------|--------|
| BS-01 | 目标路径含 Unicode/中文 | 正常匹配和检查 | P1 |
| BS-02 | 超长路径 (>1000字符) | 不截断，完整处理 | P1 |
| BS-03 | 特殊字符路径 (`..`, `\0`) | 识别为可疑，提高风险分 | P0 |
| BS-04 | 同一操作连续快速提交 | 每次独立检查，均记录日志 | P1 |
| BS-05 | 规则循环依赖 | 无死锁，取首次匹配 | P2 |
| BS-06 | 1000+ 条规则时的性能 | check() < 50ms | P1 |
| BS-07 | 切换级别后已缓存结果失效 | 重新评估 | P1 |
| BS-08 | 审计日志达到容量上限 | 自动轮转/FIFO淘汰 | P2 |

---

## 用户旅程示例

### 旅程A: 安全的开发工作流
```
1. 用户启动协作任务 → Coordinator 创建 PermissionGuard(DEFAULT)
2. 架构师Worker 读取需求文档 → ALLOWED ✅
3. 架构师Worker 创建 design.md → ALLOWED (R003) ✅
4. UI设计师Worker 创建 styles.css → PROMPT (R005) → 用户确认 → 继续
5. 测试专家Worker 执行 pytest → ALLOWED (R018) ✅
6. 开发者Worker 修改 .env → PROMPT (R009) → 用户确认 → 继续
7. 开发者Worker git push → PROMPT (R028) → 用户确认 → 完成
8. 用户查看安全报告 → 8次检查, 3次确认, 0次拒绝 ✅
```

### 旅程B: PLAN模式预览
```
1. 用户设置 PermissionGuard(PLAN)
2. 提交一个完整的多角色协作任务
3. 所有Worker的所有写操作都被 DENIED
4. 但所有读操作正常 ALLOWED
5. 用户查看审计日志 → 看到20次DENIED记录
6. 用户了解哪些操作会被执行 → 切换回 DEFAULT 模式
7. 这次有了充分预期
```

### 旅程C: 安全事件调查
```
1. 安全审计员调用 get_security_report()
2. 发现昨晚有3次 DENIED 操作
3. 查看 get_audit_log(outcome=DENIED)
4. 发现某Worker尝试 rm -rf 项目目录
5. 查看 decision.reason 和 matched_rule
6. 确认是误操作（非恶意），更新培训材料
```

---

## 验收标准总表

| ID | 故事 | 优先级 | AC数量 | 状态 |
|-----|------|--------|--------|------|
| US-1.1 | PLAN模式禁止写操作 | P0 | 6 | ⬜ |
| US-1.2 | DEFAULT模式危险操作确认 | P0 | 5 | ⬜ |
| US-1.3 | AUTO模式AI智能判断 | P1 | 6 | ⬜ |
| US-1.4 | BYPASS模式跳过检查 | P1 | 4 | ⬜ |
| US-2.1 | 30条默认规则覆盖 | P0 | 5 | ⬜ |
| US-2.2 | 动态增删规则 | P0 | 5 | ⬜ |
| US-2.3 | 多种匹配模式 | P1 | 5 | ⬜ |
| US-3.1 | 完整审计日志 | P0 | 6 | ⬜ |
| US-3.2 | 安全统计报告 | P1 | 2 | ⬜ |
| US-4.1 | Worker自动权限检查 | P0 | 5 | ⬜ |
| US-4.2 | ESCALATED触发共识 | P2 | 4 | ⬜ |
| US-5.1 | 异常输入处理 | P0 | 4 | ⬜ |
| US-5.2 | 线程安全 | P1 | 3 | ⬜ |
| **合计** | | | **60** | |
