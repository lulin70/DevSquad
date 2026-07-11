# P2-4 测试计划：无测试模块补充

**版本**: v4.0.3 → v4.0.4
**目标**: 整体覆盖率从 72.58% 提升至 ≥80%（需新增 ~1363 语句覆盖）
**预估工作量**: 12-16h
**风险**: 低（纯测试补充，不修改源码）

## 1. 当前覆盖率基线

- 总语句数: 26644
- 已覆盖: 19952
- 未覆盖: 6692
- 当前覆盖率: 72.58%
- 目标覆盖率: 80%（需覆盖 21315 语句，新增 1363）

## 2. 模块清单与优先级

### 第一梯队（核心模块，纯 Python 可测，高 ROI）

| # | 模块 | 语句数 | missing | 当前覆盖率 | 预估测试数 | 覆盖率提升 |
|---|------|--------|---------|-----------|-----------|-----------|
| 1 | async_coordinator.py | 322 | 322 | 0% | 30-40 | +1.2% |
| 2 | feedback_control_loop.py | 183 | 130 | 29% | 20-25 | +0.5% |
| 3 | enhanced_worker.py | 287 | 147 | 49% | 20-25 | +0.6% |
| 4 | rule_collector.py | 398 | 223 | 44% | 25-35 | +0.8% |
| 5 | adaptive_role_selector.py | 109 | 60 | 45% | 10-15 | +0.2% |

**第一梯队小计**: missing 882，预估覆盖率提升 +3.3%

### 第二梯队（重要模块，中 ROI）

| # | 模块 | 语句数 | missing | 当前覆盖率 | 预估测试数 | 覆盖率提升 |
|---|------|--------|---------|-----------|-----------|-----------|
| 6 | async_llm_backend.py | 311 | 159 | 49% | 15-20 | +0.6% |
| 7 | cache_interface.py | 158 | 91 | 42% | 10-15 | +0.3% |
| 8 | code_map_generator.py | 167 | 97 | 42% | 10-15 | +0.4% |
| 9 | dual_layer_context.py | 88 | 52 | 41% | 8-10 | +0.2% |
| 10 | prometheus_metrics.py | 135 | 69 | 49% | 8-10 | +0.3% |
| 11 | dispatch_performance.py | 85 | 43 | 49% | 8-10 | +0.2% |
| 12 | dispatch_steps_consensus_mixin.py | 61 | 31 | 49% | 5-8 | +0.1% |

**第二梯队小计**: missing 542，预估覆盖率提升 +2.1%

### 第三梯队（CLI 和 Dashboard，低 ROI）

| # | 模块 | 语句数 | missing | 当前覆盖率 | 预估测试数 | 覆盖率提升 |
|---|------|--------|---------|-----------|-----------|-----------|
| 13 | cli.py | 230 | 136 | 41% | 10-15 | +0.5% |
| 14 | cli_dispatch.py | 168 | 85 | 49% | 8-10 | +0.3% |
| 15 | dispatch_views.py | 97 | 81 | 16% | 8-10 | +0.3% |
| 16 | auth_views.py | 49 | 38 | 22% | 5-8 | +0.1% |

**第三梯队小计**: missing 340，预估覆盖率提升 +1.2%

### 排除模块（需要外部环境或工具脚本）

| 模块 | missing | 排除原因 |
|------|---------|---------|
| redis_cache.py | 360 | 需要 Redis 环境 |
| multi_level_cache.py | 285 | 依赖 redis_cache |
| language_parsers.py | 149 | 工具模块，非核心流程 |
| mce_adapter.py | 181 | 依赖 CarryMem 外部库（已有测试但覆盖率低） |
| llm_retry_async.py | 98 | 已有测试，需增强 |
| dispatcher_async_mixin.py | 46 | 依赖 async_coordinator |
| benchmark_*.py | 307 | benchmark 脚本 |
| generate_benchmark_report.py | 177 | 工具脚本 |
| check_version_consistency.py | 81 | 工具脚本 |
| _find_missing_hints.py | 35 | 工具脚本 |

## 3. 执行策略

### 阶段一：第一梯队（预估 6-8h，覆盖率 +3.3% → ~75.9%）

按以下顺序逐一补充：
1. **async_coordinator.py** — AsyncCoordinator/AsyncWorkerWrapper，核心异步协调器
2. **feedback_control_loop.py** — FeedbackControlLoop，V3.6.1 核心特性
3. **enhanced_worker.py** — EnhancedWorker，P2-1 刚改过
4. **rule_collector.py** — RuleCollector，规则收集管线
5. **adaptive_role_selector.py** — AdaptiveRoleSelector，自适应角色选择

### 阶段二：第二梯队（预估 4-6h，覆盖率 +2.1% → ~78%）

6. **async_llm_backend.py** — AsyncLLMBackend
7. **cache_interface.py** — CacheInterface
8. **code_map_generator.py** — CodeMapGenerator
9. **dual_layer_context.py** — DualLayerContext
10. **prometheus_metrics.py** — PrometheusMetrics
11. **dispatch_performance.py** — DispatchPerformance
12. **dispatch_steps_consensus_mixin.py** — PostDispatchConsensusMixin

### 阶段三：第三梯队（预估 2-3h，覆盖率 +1.2% → ~79.2%）

13. **cli.py** — CLI 主入口
14. **cli_dispatch.py** — CLI dispatch 子命令
15. **dispatch_views.py** — Dashboard dispatch 视图
16. **auth_views.py** — Dashboard auth 视图

### 阶段四：验证 + 版本 + Git

- 运行全量 pytest --cov 确认覆盖率 ≥80%
- ruff check + mypy 0 errors
- 版本 4.0.3 → 4.0.4（9 个文件同步）
- CHANGELOG.md + CHANGELOG-CN.md 更新
- git commit + push

## 4. 测试规范

- 使用真实组件而非 Mock（遵循用户测试哲学）
- 异步测试使用 pytest-asyncio（asyncio_mode = "auto"）
- 每个模块的测试文件命名: `tests/test_<module_name>.py`
- 测试覆盖: 正常路径 + 边界条件 + 错误处理
- 不使用 skip（遵循用户测试哲学）

## 5. 决策点

### 决策点 6: P2-4 执行范围
- **选项 A**: 只做第一梯队（5 模块，+3.3%，覆盖率 ~75.9%）
- **选项 B**: 第一+第二梯队（12 模块，+5.4%，覆盖率 ~78%）—— 推荐
- **选项 C**: 全部三个梯队（16 模块，+6.6%，覆盖率 ~79.2%）
- **选项 D**: 全部三个梯队 + 增强已有低覆盖模块（达到 80%+）

**PM 决策**: 待定

## 6. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 4.0.4 | 2026-07-11 | P2-4 无测试模块补充 |
