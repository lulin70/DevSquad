# 协作系统 (Collaboration System) 测试计划

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v1.0.0 | 2026-04-15 | 测试专家 | 初始版本：基于 USER_STORIES.md 编写完整测试策略 | 待审核 |

---

## 一、测试概述

### 1.1 测试范围
本测试计划覆盖 **DevSquad v3.0 Phase 1** 的协作系统全部 5 个核心模块：
- Scratchpad（共享黑板）
- Worker（工作者）
- ConsensusEngine（共识引擎）
- Coordinator（协调者）
- BatchScheduler（批处理调度器）

### 1.2 测试依据
- [USER_STORIES.md](../product-manager/USER_STORIES.md) — 22 个用户故事 + 验收标准
- [v3-upgrade-proposal.md](../architecture/v3-upgrade-proposal.md) — 架构设计文档
- 源代码: `scripts/collaboration/` 全部模块

### 1.3 测试策略

采用 **测试金字塔** 策略：

```
        /\
       /  \     E2E 集成测试 (10%)
      /────\    ── 完整协作流程、用户旅程
     /  🟢  \   目标: 覆盖所有用户旅程
    /────────\  
   /  单元测试  \  (70%)
  /────────────\ ── 每个类/方法的独立功能
 /   🔵🔵🔵🔵🔵  \ 目标: 覆盖所有 AC 验收标准
/────────────────\
  集成测试 (20%)
 ── 模块间交互
 目标: 覆盖跨模块场景
```

| 层级 | 测试数量 | 覆盖目标 | 执行频率 |
|------|---------|---------|---------|
| 单元测试 | ~50 | 每个 AC 至少 1 个用例 | 每次 CI |
| 集成测试 | ~15 | 模块间接口和交互 | 每次 CI |
| E2E 测试 | ~8 | 用户旅程端到端 | 每次发布前 |

---

## 二、测试环境

### 2.1 环境要求

| 项目 | 要求 |
|------|------|
| Python | >= 3.8 |
| OS | macOS / Linux |
| 依赖 | 仅标准库 (无第三方依赖) |
| 磁盘空间 | > 10MB (用于持久化测试) |

### 2.2 测试数据

使用以下预设数据集进行一致性测试：

```python
# 标准角色配置
STANDARD_ROLES = [
    {"role_id": "architect"},
    {"role_id": "product-manager"},
    {"role_id": "tester"},
    {"role_id": "ui-designer"},
    {"role_id": "solo-coder"},
]

# 标准 Worker 配置
WORKER_CONFIGS = [
    {"worker_id": "w-arch", "role_id": "architect", "role_prompt": "你是资深架构师..."},
    {"worker_id": "w-pm", "role_id": "product-manager", "role_prompt": "你是产品经理..."},
    {"worker_id": "w-test", "role_id": "tester", "role_prompt": "你是测试专家..."},
]

# 标准任务描述
TASK_DESCRIPTION = "为一个在线教育平台设计完整的用户认证和权限管理系统"
```

---

## 三、测试维度与覆盖矩阵

### 3.1 功能测试覆盖矩阵

| Epic | US编号 | AC 数量 | 功能测试用例数 | 边界测试用例数 | 异常测试用例数 |
|------|--------|---------|---------------|---------------|---------------|
| E1:Scratchpad | US-1.1~1.7 | 24 | 18 | 6 | 5 |
| E2:Worker | US-2.1~2.5 | 16 | 12 | 4 | 4 |
| E3:Consensus | US-3.1~3.4 | 14 | 12 | 4 | 4 |
| E4:Coordinator | US-4.1~4.5 | 19 | 14 | 4 | 5 |
| E5:BatchScheduler | US-5.1 | 3 | 3 | 2 | 1 |
| **合计** | **22** | **76** | **59** | **20** | **19** |

### 3.2 非功能测试

| 维度 | 测试项 | 方法 | 通过标准 |
|------|-------|------|---------|
| 性能 | 1000 条写入耗时 | 计时 | < 1s |
| 性能 | 全文搜索 1000 条 | 计时 | < 50ms |
| 并发 | 多线程同时写入 | threading | 无数据丢失 |
| 容量 | LRU 淘汰正确性 | 写入超限 | 优先淘汰 RESOLVED |
| 持久化 | JSONL 写入/读取 | 文件 I/O | 数据完整可恢复 |
| 内存 | 大量对象创建/销毁 | gc | 无内存泄漏迹象 |

---

## 四、测试执行计划

### 4.1 阶段划分

```
Phase 1: 单元测试 (预计 ~60 个用例)
  ├─ T1. Scratchpad 单元测试 (18 用例)
  │   ├─ T1.1 基础 CRUD (write/read/resolve) — 8 用例
  │   ├─ T1.2 查询过滤 (query/type/status/worker/tags/limit/since) — 7 用例
  │   └─ T1.3 统计与摘要 (get_stats/get_summary/export) — 3 用例
  │
  ├─ T2. Worker 单元测试 (12 用例)
  │   ├─ T2.1 创建与属性 (3 用例)
  │   ├─ T2.2 任务执行 execute() (3 用例)
  │   ├─ T2.3 Scratchpad 交互 (write_finding/write_question/write_conflict) — 4 用例
  │   └─ T2.4 通知与投票 (2 用例)
  │
  ├─ T3. Consensus 单元测试 (12 用例)
  │   ├─ T3.1 提案生命周期 (create/open/close) — 3 用例
  │   ├─ T3.2 投票机制 (cast_vote/权重/重复投票) — 4 用例
  │   └─ T3.3 共识判定 (APPROVED/REJECTED/SPLIT/ESCALATED/TIMEOUT) — 5 用例
  │
  ├─ T4. Coordinator 单元测试 (14 用例)
  │   ├─ T4.1 任务规划 plan_task() (3 用例)
  │   ├─ T4.2 Worker 创建 spawn_workers() (3 用例)
  │   ├─ T4.3 执行引擎 execute_plan() (3 用例)
  │   └─ T4.4 结果收集与报告 (collect_results/generate_report/resolve_conflicts) — 5 用例
  │
  └─ T5. BatchScheduler 单元测试 (3 用例)

Phase 2: 集成测试 (预计 ~15 个用例)
  ├─ IT1. Worker ↔ Scratchpad 数据流 (4 用例)
  ├─ IT2. Coordinator → Workers → Scratchpad 完整链路 (4 用例)
  ├─ IT3. Coordinator → Consensus → Scratchpad 冲突解决 (3 用例)
  └─ IT4. 持久化集成 (JSONL 写入/恢复/并发安全) (4 用例)

Phase 3: 边界与异常测试 (预计 ~19 个用例)
  ├─ BT1. Scratchpad 边界 (空查询/容量满/特殊字符/超大内容) — 5 用例
  ├─ BT2. Worker 异常 (execute 抛异常/空 prompt/无效 task) — 4 用例
  ├─ BT3. Consensus 异常 (已关闭提案/零投票/全否决) — 4 用例
  ├─ BT4. Coordinator 边界 (零角色/单角色/大量角色) — 4 用例
  └─ BT5. 并发安全 (多线程写入同一条目) — 2 用例

Phase 4: E2E 用户旅程测试 (预计 ~8 个用例)
  ├─ E2E-1: 旅程 A — 完整 5 角色协作 (1 用例)
  ├─ E2E-2: 旅程 B — 轻量 Scratchpad 信息交换 (1 用例)
  ├─ E2E-3: 旅程 C — 独立共识决策 (1 用例)
  ├─ E2E-4: 含冲突的协作流程 (1 用例)
  ├─ E2E-5: 含否决票的共识流程 (1 用例)
  ├─ E2E-6: 持久化恢复后的完整流程 (1 用例)
  ├─ E2E-7: 大规模数据压力测试 (1 用例)
  └─ E2E-8: 错误恢复能力测试 (1 用例)
```

### 4.2 缺陷分级标准

| 等级 | 定义 | 示例 | 响应时间 |
|------|------|------|---------|
| P0-Critical | 核心功能不可用 | import 失败、核心方法崩溃 | 立即修复 |
| P1-Major | 主要功能异常 | 共识结果错误、数据丢失 | 当日修复 |
| P2-Minor | 次要功能缺陷 | 统计数字偏差、格式问题 | 3 日内修复 |
| P3-Trivial | 优化建议 | 日志不够详细、命名不规范 | 下迭代 |

---

## 五、风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 并发竞态条件 | 数据不一致 | 中 | 使用 RLock 保护，增加并发测试 |
| 持久化文件损坏 | 数据丢失 | 低 | JSONL 追加模式，失败静默跳过 |
| 内存溢出(大量条目) | 系统崩溃 | 低 | LRU 淘汰 + 容量上限 |
| 循环依赖导入 | 模块加载失败 | 已解决 | Phase 1 已修复 __init__.py 导入链 |

---

## 六、准入/准出标准

### 6.1 准入条件
- [x] USER_STORIES.md 已完成并审核通过
- [x] 代码编译/导入无错误 (`python3 -c "from collaboration import *"`)
- [x] 现有 e2e_test.py 20/20 通过

### 6.2 准出条件
- [ ] 所有 P0 用例通过率 100%
- [ ] 所有 P1 用例通过率 >= 95%
- [ ] 总体通过率 >= 90%
- [ ] 发现的所有 P0/P1 缺陷已修复并验证
- [ ] 测试报告已完成
