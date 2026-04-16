# Phase 3: WarmupManager 启动优化 - 测试计划 (TEST_PLAN)

**版本**: v1.0
**日期**: 2026-04-16
**作者**: Tester (测试专家角色)
**基于**: [v3-phase3-warmup-design.md](../architecture/v3-phase3-warmup-design.md) + [USER_STORIES_P3.md](./USER_STORIES_P3.md)
**预估总用例数**: ~95

---

## 1. 测试策略概述

### 1.1 测试分层

```
┌─────────────────────────────────────────────┐
│              L3: E2E 端到端                   │ ~8 cases
│  完整预热流程 + 集成场景                       │
├─────────────────────────────────────────────┤
│              L2: Integration 集成测试          │ ~12 cases
│  与 Coordinator / PromptRegistry 集成         │
├─────────────────────────────────────────────┤
│              L1: Unit 单元测试                │ ~75 cases
│  T1~T8 各组件独立验证                         │
└─────────────────────────────────────────────┘
```

### 1.2 测试原则

| 原则 | 说明 |
|------|------|
| **隔离性** | 每个测试用例前后 reset WarmupManager 单例 |
| **可重复性** | 不依赖执行顺序，任意顺序运行结果一致 |
| **快速反馈** | 单元测试每个 < 50ms，全量 < 5s |
| **真实模拟** | 用真实 ThreadPoolExecutor 而非 mock（L2/L3） |
| **边界覆盖** | 重点覆盖空值/超时/并发/异常路径 |

---

## 2. L1 单元测试详细设计

### T1: 数据模型验证 (~12 cases)

覆盖: WarmupConfig / CacheEntry / WarmupTask / WarmupResult / WarmupReport / WarmupMetrics

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T1.01 | Config default 值正确性 | enabled=True, eager_timeout=200, async_workers=4, cache_max_size=200 | P0 |
| T1.02 | Config fast 模式最小化 | async_workers=0 或最小值, eager_only=True | P0 |
| T1.03 | Config full 模式最大化 | 更长超时, 更多 workers, 全部 preload | P0 |
| T1.04 | CacheEntry 创建与基本属性 | key/value/timestamp 正确设置 | P0 |
| T1.05 | CacheEntry is_expired TTL 过期 | created_at + ttl < now → True | P0 |
| T1.06 | CacheEntry is_expired 未过期 | created_at + ttl > now → False | P0 |
| T1.07 | CacheEntry age_seconds 计算 | 返回正确的秒数差 | P1 |
| T1.08 | WarmupTask 所有字段赋值 | task_id/name/priority/layer/deps/executor/timeout/retry | P1 |
| T1.09 | WarmupResult SUCCESS 状态创建 | status=SUCCESS, error=None | P1 |
| T1.10 | WarmupResult ERROR 状态创建 | status=ERROR, error 非空 | P1 |
| T1.11 | WarmupReport 统计字段一致性 | completed+failed+cached == total_tasks | P1 |
| T1.12 | WarmupMetrics hit_rate 计算边界 | 0 hits → 0%, all hits → 100% | P2 |

---

### T2: WarmupManager 核心逻辑 (~18 cases)

覆盖: 单例模式 / 任务注册 / warmup 执行 / 基本缓存操作

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T2.01 | instance() 单例一致性 | 两次调用返回同一对象 (`is` 判断) | P0 |
| T2.02 | instance() 线程安全 | 10 线程并发 instance() 只创建 1 个对象 | P0 |
| T2.03 | reset() 后重新创建 | reset → 新 instance 是不同对象 | P0 |
| T2.04 | register_task() 基本注册 | 注册后 tasks dict 包含该 task | P0 |
| T2.05 | register_task() 重复注册覆盖 | 同 task_id 后注册的覆盖先注册的 | P1 |
| T2.06 | register_task() 批量注册 | 注册多个任务后数量正确 | P1 |
| T2.07 | warmup() 无任务时返回空报告 | tasks 为空时 report.total_tasks=0 | P1 |
| T2.08 | warmup() 只执行指定层 | layers=[EAGER] 不触发 ASYNC 任务 | P0 |
| T2.09 | get() 缓存命中 | 先 set 再 get 返回同一值 | P0 |
| T2.10 | get() 缓存未命中返回默认值 | 未 set 的 key 返回 default | P0 |
| T2.11 | get() 缓存过期返回默认值 | TTL 过期的条目返回 None/default | P0 |
| T2.12 | get_or_load() 首次加载 | 首次调用执行 loader 并缓存 | P0 |
| T2.13 | get_or_load() 二次命中 | 二次调用不执行 loader（访问计数检查） | P0 |
| T2.14 | is_ready() 已完成任务 | warmup 后 is_ready(task_id)=True | P1 |
| T2.15 | is_ready() 未完成任务 | 未 warmup 时 is_ready=False | P1 |
| T2.16 | is_fully_warmed() 全部完成 | 所有任务完成后返回 True | P1 |
| T2.17 | is_fully_warmed() 部分完成 | 部分 ASYNC 进行中时返回 False | P1 |
| T2.18 | get_report() 结构完整性 | 包含所有必需字段和任务结果 | P2 |

---

### T3: L1 Eager 预热 (~8 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T3.01 | eager 成功执行单个任务 | executor 被调用, 结果写入缓存, status=SUCCESS | P0 |
| T3.02 | eager 多任务按依赖排序 | 依赖的任务先执行 | P0 |
| T3.03 | eager 任务抛出异常 | status=ERROR, error 信息保留, 不影响后续任务 | P0 |
| T3.04 | eager 无依赖任务并行可能性 | 无依赖的多个任务都执行 | P1 |
| T3.05 | eager 空任务列表 | 返回空 results 列表 | P1 |
| T3.06 | eager 耗时记录准确性 | duration_ms 在合理范围内（>0 且 < timeout） | P1 |
| T3.07 | eager 结果写入缓存 | get(task_id) 可获取 executor 返回值 | P1 |
| T3.08 | eager 全部失败时的报告 |全部 ERROR, completed=0 | P2 |

---

### T4: L2 Async 预热 (~10 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T4.01 | async 立即返回不阻塞 | warmup_async() 耗时 < 10ms | P0 |
| T4.02 | async 后台任务最终完成 | 等待后 is_fully_warmed()=True | P0 |
| T4.03 | async 任务成功写入缓存 | 异步完成后 get(key) 可获取值 | P0 |
| T4.04 | async 依赖关系遵守 | 被依赖任务先于依赖者完成 | P0 |
| T4.05 | async 任务超时标记 TIMEOUT | executor sleep > timeout → TIMEOUT | P0 |
| T4.06 | async 任务异常不崩溃主线程 | 抛 Exception → 主线程正常 | P0 |
| T4.07 | async 幂等性 | 两次 warmup_async() 只执行一批 | P1 |
| T4.08 | async 多线程并发安全 | 多个 ASYNC 任务同时写缓存无冲突 | P1 |
| T4.09 | async 自定义 worker 数 | config.async_workers=2 时只有 2 线程 | P1 |
| T4.10 | async shutdown 中断 | shutdown() 后异步任务停止 | P2 |

---

### T5: 缓存管理 (~14 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T5.01 | 基本 set/get | 存取一致 | P0 |
| T5.02 | TTL 过期自动清除 | 等 TTL 后 get 返回 None | P0 |
| T5.03 | TTL=0 永不过期 | 设置 ttl=0 后永不过期 | P0 |
| T5.04 | LRU 淘汰最久未访问 | 超过 max_size 后淘汰 last_accessed 最小的 | P0 |
| T5.05 | LRU 淘汰后访问计数更新 | 被淘汰的条目不再可用 | P1 |
| T5.06 | TTL 淘汰优先于 LRU | 有过期条目时先清过期再清空间 | P1 |
| T5.07 | max_size=0 禁用缓存 | set 后立即 get 返回 None | P1 |
| T5.08 | invalidate 单个 key | 该 key 不可用, 其余不受影响 | P0 |
| T5.09 | invalidate_all 清空 | 全部不可用 | P0 |
| T5.10 | invalidate 不存在的 key | 不报错（no-op） | P1 |
| T5.11 | access_count 递增 | 每次 get 都 +1 | P2 |
| T5.12 | 并发读写安全性 | 多线程同时 get/set 无数据损坏 | P0 |
| T5.13 | 缓存容量精确控制 | 达到 max_size 时恰好触发淘汰 | P1 |
| T5.14 | 大量缓存条目性能 | 500 条 set+get 总耗时 < 100ms | P2 |

---

### T6: 依赖解析 (~6 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T6.01 | 无依赖线性排序 | 输入顺序保持或按 priority 排序 | P0 |
| T6.02 | 简单链式依赖 A→B→C | A最先, C最后 | P0 |
| T6.03 | 菱形依赖 A→{B,C}→D | B,C在D之前, B,C之间任意 | P0 |
| T6.04 | 循环依赖 A→B→A | 抛出 ValueError 含循环信息 | P0 |
| T6.05 | 自依赖 A→A | 抛出 ValueError | P1 |
| T6.06 | 空列表输入 | 返回空列表 | P1 |

---

### T7: 性能与 Metrics (~8 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T7.01 | get_metrics() 返回结构完整 | 所有字段非 None 且类型正确 | P0 |
| T7.02 | startup_time_ms 合理性 | > 0 且 < 10000 (10s 上限) | P0 |
| T7.03 | cache_hit_rate 计算正确 | 手动设置 hits/misses 后验证公式 | P0 |
| T7.04 | print_diagnostics() 输出非空 | 包含关键指标行 | P1 |
| T7.05 | print_diagnostics() 格式化 | 包含 ✅❌ 图标和毫秒数 | P1 |
| T7.06 | benchmark() 返回统计量 | mean/min/max/p50/p95 都存在 | P0 |
| T7.07 | benchmark() 多次迭代一致性 | iterations=3 时有 3 个数据点 | P1 |
| T7.08 | benchmark() 每次冷启动 | 每次 iteration 前都 invalidate_all | P1 |

---

### T8: 边界情况与降级 (~9 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T8.01 | disabled 配置跳过预热 | enabled=False 时 warmup() 空操作 | P0 |
| T8.02 | executor 超时处理 | 任务执行超过 timeout_ms 标记 TIMEOUT | P0 |
| T8.03 | 空任务列表 warmup | 报告显示 0 任务 | P1 |
| T8.04 | 重复 register 同一 task_id | 后者覆盖前者 | P1 |
| T8.05 | shutdown 后 get 行为 | 返回 default, 不崩溃 | P0 |
| T8.06 | shutdown 后重新 warmup | 可恢复（重新创建 executor） | P1 |
| T8.07 | 环境变量 WARMUP_MODE 解析 | FAST/FULL/DEFAULT/DISABLED 正确映射 | P1 |
| T8.08 | 非法环境变量值回退 DEFAULT | WARMUP_MODE=UNKNOWN → DEFAULT | P2 |
| T8.09 | 极大 timeout 值不溢出 | timeout_ms=999999 正常工作 | P2 |

---

## 3. L2 集成测试设计 (~12 cases)

### IT1: Coordinator 集成 (6 cases)

| ID | 用例名称 | 验证点 | 对应 US |
|----|---------|--------|--------|
| IT1.01 | 预热后快速创建 Coordinator | 创建耗时 < 50ms | US-3.06 |
| IT1.02 | 预热后 Coordinator.plan_task 正常 | 返回有效 ExecutionPlan | US-3.06 |
| IT1.03 | 未预热时 Coordinator 创建走 LAZY | 能工作但较慢 (< 200ms) | US-3.06 |
| IT1.04 | 预热 Scratchpad 复用 | 多次创建共享缓存 | US-3.07 |
| IT1.05 | invalidate 后 Coordinator 重建 | 加载最新资源 | US-3.13 |
| IT1.06 | 连续创建 100 次 Coordinator | 无内存泄漏（内存稳定） | US-3.06 B3 |

### IT2: PromptRegistry 集成 (4 cases)

| ID | 用例名称 | 验证点 | 对应 US |
|----|---------|--------|--------|
| IT2.01 | 缓存的 Registry 可查询角色 | get_role_prompt("architect") 非空 | US-3.04 |
| IT2.02 | Registry 单例多次 get 一致 | `is` 判断相同 | US-3.07 |
| IT2.03 | Registry 失败时降级 | 文件删除后标记 ERROR + LAZY 恢复 | US-3.12 |
| IT2.04 | Top3 角色预加载内容完整 | PM/Architect/SoloCoder prompt 非空 | US-3.04 |

### IT3: PermissionGuard 集成 (2 cases)

| ID | 用例名称 | 验证点 | 对应 US |
|----|---------|--------|--------|
| IT3.01 | 规则预编译后首次 check < 10ms | 性能达标 | US-3.06 |

---

## 4. L3 端到端测试设计 (~8 cases)

### E2E 完整流程

| ID | 场景 | 步骤 | 验收 | 对应旅程 |
|----|------|------|------|---------|
| E2E.01 | Web 服务启动旅程 | import → warmup → create Coordinator → 执行任务 | 全程 < 500ms | 旅程 A |
| E2E.02 | CLI Fast 模式旅程 | WARMUP_MODE=FAST → import → 执行 | import < 20ms | 旅程 B |
| E2E.03 | 完整预热-使用-失效-重热循环 | warmup → use → invalidate → warmup → use | 每轮功能正常 | US-3.13 |
| E2E.04 | 异步预热竞态条件 | warmup_async → 立即 get(未完成key) → 等待 → get(已完成) | 最终一致 | US-3.05 |
| E2E.05 | 高并发压力测试 | 20 线程同时 get/set/warmup | 无死锁/数据错误 | E1 B2 |
| E2E.06 | 内存稳定性长时间运行 | 1000 次 warmup+invalidate 循环 | 内存不持续增长 | E3 |
| E2E.07 | benchmark 回归基线 | benchmark(10) p95 < 阈值 | 性能回归检测 | US-3.11 |
| E2E.08 | diagnostics 输出完整性 | print_diagnostics() 包含所有预期行 | 格式正确 | US-3.10 |

---

## 5. 测试优先级矩阵

| 优先级 | L1 Unit | L2 Integration | L3 E2E | 合计 |
|--------|---------|----------------|--------|------|
| **P0 (必须)** | ~42 | ~10 | ~5 | **~57** |
| **P1 (重要)** | ~25 | ~2 | ~2 | **~29** |
| **P2 (可选)** | ~8 | 0 | ~1 | **~9** |
| **合计** | **~75** | **~12** | **~8** | **~95** |

---

## 6. 性能验收标准

| 指标 | 目标值 | 测量方法 | 对应用例 |
|------|--------|---------|---------|
| import collaboration (L1 only) | < 100ms | time.perf_counter() | E2E.02 |
| L2 Async 全部完成 | < 500ms | warmup + wait | T4.02 |
| 预热后首次 Coordinator() | < 50ms | perf_counter | IT1.01 |
| 首次 PermissionGuard.check() | < 10ms | perf_counter | IT3.01 |
| 缓存命中率（典型流） | > 85% | metrics.hit_rate | T7.03 |
| benchmark(5) p95 | < 1200ms | benchmark() | E2E.07 |
| 全量单元测试执行时间 | < 10s | pytest --timeout | — |

---

## 7. Mock 策略

| 组件 | Mock 方式 | 原因 |
|------|----------|------|
| 文件系统 I/O (PromptRegistry) | 真实文件 | 测试真实加载行为 |
| ThreadPoolExecutor | 真实线程 | 测试并发安全性 |
| time.sleep / time.time | 允许真实使用 | 测试基于时间的逻辑 |
| 外部网络请求 | 不涉及 | 本模块无网络调用 |
| logging 输出 | 允许输出 | 诊断信息需要可见 |

---

## 8. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 测试间状态污染 | 高 | 高 | 每个 test_ 函数前后调用 reset() |
| 时间相关测试 flaky | 中 | 中 | 用宽松阈值（±50%）而非精确匹配 |
| 多线程测试不确定性行为 | 低 | 高 | 使用 Event/Barrier 同步 |
| 平台差异（Win/Mac/Linux） | 低 | 中 | 路径分隔符用 pathlib |
