# Phase 2: PermissionGuard 权限守卫 — 测试计划

**版本**: v1.0
**日期**: 2026-04-15
**作者**: 测试专家 (Tester Role)
**基于**: USER_STORIES_P2.md (13用户故事/60AC) + v3-phase2-permission-design.md

---

## 1. 测试策略

### 1.1 测试金字塔

```
        ╱╲
       ╱E2E╲         ~10%  (用户旅程、端到端集成)
      ╱─────╲
     ╱Integration╲   ~20%  (Guard+Coordinator, Guard+Consensus)
    ╱───────────╲
   ╱   Unit Tests  ╲ ~70%  (规则匹配、级别行为、分类器、审计日志)
  ╱───────────────╲
```

### 1.2 测试分层

| 层级 | 范围 | 用例数 | 覆盖目标 |
|------|------|--------|---------|
| **L1 单元测试** | PermissionGuard 核心方法 | ~85 | 每个public method ≥3条用例 |
| **L2 集成测试** | Guard + Coordinator/Worker | ~15 | 关键集成路径全覆盖 |
| **L3 E2E测试** | 完整用户旅程 | ~8 | 3个旅程全部通过 |
| **总计** | | **~108** | |

---

## 2. 测试环境

- Python 3.9+
- 无外部依赖（纯标准库 + dataclasses/enum/threading）
- 并发测试需要 threading 模块
- 时间相关测试需要 freezetime 或 mock

---

## 3. 准入准出标准

### 3.1 准入条件
- [ ] 设计文档已评审通过
- [ ] 用户故事已确认（13故事/60AC）
- [ ] 代码实现完成，可导入无报错
- [ ] 默认30条规则已加载验证

### 3.2 准出条件
- [ ] 全部测试用例通过（目标 108/108）
- [ ] 代码覆盖率 > 90%（核心模块）
- [ ] 无 P0/P1 缺陷遗留
- [ ] 性能基准达标（单次 check < 5ms, 1000规则 < 50ms）
- [ ] 安全边界场景全部通过

---

## 4. 测试执行计划

### Phase 1: 单元测试 (~85用例)

#### T1: 数据模型验证 (10用例)

| ID | 用例名称 | 对应AC | 优先级 |
|----|---------|--------|--------|
| T1.01 | ProposedAction 创建和字段默认值 | US-5.1 | P0 |
| T1.02 | ProposedAction 序列化 roundtrip | - | P1 |
| T1.03 | PermissionRule 创建和校验 | US-2.1 | P0 |
| T1.04 | PermissionDecision 创建和属性 | - | P0 |
| T1.05 | DecisionOutcome 枚举完整性 | - | P0 |
| T1.06 | ActionType 枚举覆盖8种类型 | - | P0 |
| T1.07 | PermissionLevel 4级枚举 | US-1.1~1.4 | P0 |
| T1.08 | AuditEntry 完整性和时间戳 | US-3.1 | P0 |
| T1.09 | 空字段默认值合理性 | US-5.1 | P0 |
| T1.10 | 特殊字符在数据模型中不丢失 | BS-01 | P1 |

#### T2: 4级行为测试 (16用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| T2.01 | PLAN模式 FILE_CREATE → DENIED | US-1.1 | P0 |
| T2.02 | PLAN模式 FILE_MODIFY → DENIED | US-1.1 | P0 |
| T2.03 | PLAN模式 FILE_DELETE → DENIED | US-1.1 | P0 |
| T2.04 | PLAN模式 SHELL_EXECUTE → DENIED | US-1.1 | P0 |
| T2.05 | PLAN模式 FILE_READ → ALLOWED | US-1.1 | P0 |
| T2.06 | PLAN模式 NETWORK_REQUEST → DENIED | US-1.1 | P0 |
| T2.07 | DEFAULT模式 .py创建 → ALLOWED/AUTO | US-1.2 | P0 |
| T2.08 | DEFAULT模式 .env修改 → PROMPT | US-1.2 | P0 |
| T2.09 | DEFAULT模式 credentials修改 → PROMPT | US-1.2 | P0 |
| T2.10 | DEFAULT模式 rm命令 → PROMPT | US-1.2 | P0 |
| T2.11 | DEFAULT模式 sudo命令 → PROMPT | US-1.2 | P0 |
| T2.12 | DEFAULT模式 正常读取 → ALLOWED | US-1.2 | P0 |
| T2.13 | AUTO模式 安全操作 → ALLOWED | US-1.3 | P1 |
| T2.14 | AUTO模式 可疑操作 → PROMPT | US-1.3 | P1 |
| T2.15 | BYPASS模式 全部 → ALLOWED | US-1.4 | P1 |
| T2.16 | BYPASS模式审计仍记录 | US-1.4 | P1 |

#### T3: 规则引擎 (18用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| T3.01 | 默认加载30条规则 | US-2.1 | P0 |
| T3.02 | 规则覆盖8种ActionType | US-2.1 | P0 |
| T3.03 | add_rule 成功添加 | US-2.2 | P0 |
| T3.04 | remove_rule 成功移除 | US-2.2 | P0 |
| T3.05 | 移除后不再影响check | US-2.2 | P0 |
| T3.06 | import_rules / export_rules roundtrip | US-2.2 | P1 |
| T3.07 | Glob *.py 匹配 | US-2.3 | P1 |
| T3.08 | Glob src/**/*.py 递归匹配 | US-2.3 | P1 |
| T3.09 | 前缀 "git " 匹配Shell命令 | US-2.3 | P1 |
| T3.10 | 正则 rm\s+-.*f 匹配 | US-2.3 | P1 |
| T3.11 | 多规则匹配取最严格 | US-2.3 | P1 |
| T3.12 | 无匹配规则时的兜底行为 | US-2.1 | P0 |
| T3.13 | 敏感文件(.env)高风险分 | US-1.2 | P0 |
| T3.14 | credentials 文件最高风险 | US-1.2 | P0 |
| T3.15 | rm/sudo 命令极高风险 | US-1.2 | P0 |
| T3.16 | PyPI网络请求低风险 | US-2.1 | P1 |
| T3.17 | Git只读操作低风险 | US-2.1 | P1 |
| T3.18 | 禁用规则(enabled=False)跳过 | US-2.2 | P2 |

#### T4: AI自动分类器 (12用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| T4.01 | 返回值范围 [0.0, 1.0] | US-1.3 | P0 |
| T4.02 | 低风险操作 score < 0.3 | US-1.3 | P1 |
| T4.03 | 中风险操作 0.3 ≤ score < 0.7 | US-1.3 | P1 |
| T4.04 | 高风险操作 score ≥ 0.7 | US-1.3 | P1 |
| T4.05 | 目标敏感度维度评估 | US-1.3 | P1 |
| T4.06 | 操作破坏性维度评估 | US-1.3 | P1 |
| T4.07 | 白名单操作直接放行 | US-1.3 | P1 |
| T4.08 | 白名单添加/查询 | US-1.3 | P2 |
| T4.09 | 上下文合理性加分 | US-1.3 | P2 |
| T4.10 | 来源可信度影响评分 | US-1.3 | P2 |
| T4.11 | 空内容分类器返回默认值 | US-5.1 | P0 |
| T4.12 | 特殊字符不影响分类 | BS-01 | P1 |

#### T5: 审计日志 (14用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| T5.01 | check() 产生审计条目 | US-3.1 | P0 |
| T5.02 | 条目包含完整字段 | US-3.1 | P0 |
| T5.03 | duration_ms ≥ 0 | US-3.1 | P0 |
| T5.04 | 按 outcome 过滤 | US-3.1 | P0 |
| T5.05 | 按 action_type 过滤 | US-3.1 | P1 |
| T5.06 | 按 since/until 时间过滤 | US-3.1 | P1 |
| T5.07 | 按 worker_id 过滤 | US-3.1 | P1 |
| T5.08 | limit 参数限制返回数量 | US-3.1 | P1 |
| T5.09 | audit_log=False 时无记录 | US-3.1 | P2 |
| T5.10 | get_security_report() 结构 | US-3.2 | P1 |
| T5.11 | 报告数值一致性(总和=total) | US-3.2 | P1 |
| T5.12 | top_denied_actions 排序正确 | US-3.2 | P2 |
| T5.13 | 连续多次调用日志递增 | US-3.1 | P0 |
| T5.14 | 日志顺序按时间排列 | US-3.1 | P1 |

#### T6: 边界与异常 (15用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| T6.01 | 空 ProposedAction 不崩溃 | US-5.1 | P0 |
| T6.02 | 空目标字符串处理 | US-5.1 | P0 |
| T6.03 | None 字段有默认值 | US-5.1 | P0 |
| T6.04 | 超长路径(>1000字符) | BS-02 | P1 |
| T6.05 | 路径遍历(..)检测 | BS-03 | P0 |
| T6.06 | Unicode中文路径 | BS-01 | P1 |
| T6.07 | 同一操作连续提交独立检查 | BS-04 | P1 |
| T6.08 | 切换级别后重新评估 | BS-07 | P1 |
| T6.09 | set_level() 立即生效 | US-1.1~1.4 | P0 |
| T6.10 | 重复add_rule处理 | US-2.2 | P1 |
| T6.11 | 移除不存在的rule_id | US-2.2 | P1 |
| T6.12 | 空规则集初始化 | US-2.1 | P1 |
| T6.13 | risk_score 边界值 0.0 和 1.0 | US-1.3 | P1 |
| T6.14 | 特殊字符XML/JSON注入安全 | BS-01 | P1 |
| T6.15 | 极大规则数量性能 | BS-06 | P2 |

### Phase 2: 集成测试 (~15用例)

#### IT1: Guard + Worker 集成 (8用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| IT1.01 | Worker.execute_with_guard 基本流程 | US-4.1 | P0 |
| IT1.02 | ALLOWED 操作正常执行 | US-4.1 | P0 |
| IT1.03 | DENIED 操作跳过并记录错误 | US-4.1 | P0 |
| IT1.04 | PROMPT 操作暂停等待回调 | US-4.1 | P1 |
| IT1.05 | 被拒操作不影响其他操作 | US-4.1 | P1 |
| IT1.06 | 多Worker共享同一Guard实例 | US-4.1 | P1 |
| IT1.07 | WorkerResult 包含权限决策信息 | US-4.1 | P1 |
| IT1.08 | Guard未配置时降级处理 | US-4.1 | P2 |

#### IT2: Guard + Consensus 联动 (4用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| IT2.01 | ESCALATED → Scratchpad CONFLICT | US-4.2 | P2 |
| IT2.02 | Coordinator 发现升级请求 | US-4.2 | P2 |
| IT2.03 | 共识通过 → 临时放行 | US-4.2 | P2 |
| IT2.04 | 共识未通过 → 保持拒绝 | US-4.2 | P2 |

#### IT3: Guard + Coordinator 集成 (3用例)

| ID | 用例名称 | 对应US | 优先级 |
|----|---------|--------|--------|
| IT3.01 | Coordinator 构造时注入Guard | US-4.1 | P0 |
| IT3.02 | execute_plan 全流程权限检查 | US-4.1 | P0 |
| IT3.03 | generate_report 包含安全摘要 | US-3.2 | P1 |

### Phase 3: E2E测试 (~8用例)

| ID | 用例名称 | 对应旅程 | 优先级 |
|----|---------|---------|--------|
| E2E-1 | 旅程A: 安全开发工作流 | 旅程A | P0 |
| E2E-2 | 旅程B: PLAN模式预览 | 旅程B | P1 |
| E2E-3 | 旅程C: 安全事件调查 | 旅程C | P1 |
| E2E-4 | 大规模100次操作压力测试 | - | P1 |
| E2E-5 | 完整协作流(5角色+权限) | 扩展 | P1 |
| E2E-6 | 动态规则热更新场景 | US-2.2 | P2 |
| E2E-7 | 级别动态切换场景 | US-1.1~1.4 | P2 |
| E2E-8 | 全量审计报告导出验证 | US-3.2 | P2 |

---

## 5. 风险预估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| auto_classify 逻辑复杂导致测试不稳定 | 中 | 低 | 使用固定seed/mock，确定性断言 |
| 并发测试在CI环境中失败 | 低 | 中 | 重试机制 + 超时保护 |
| 规则匹配边界case遗漏 | 中 | 中 | 增加模糊测试用例 |

---

## 6. 缺陷分级

| 级别 | 定义 | 示例 |
|------|------|------|
| **P0-致命** | 安全绕过、数据丢失 | BYPASS外的级别允许了rm -rf |
| **P1-严重** | 功能错误、核心逻辑缺陷 | 规则完全不匹配、审计丢失 |
| **P2-一般** | 边界问题、体验问题 | 错误信息不够清晰 |
| **P3-轻微** | 文档、格式、命名 | 注释缺失、变量名不规范 |
