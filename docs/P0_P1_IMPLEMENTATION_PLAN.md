# P0-P1 实施计划文档

> **版本**: V4.0.0 → V4.0.1 (PATCH 递增，无新功能)
> **创建时间**: 2026-07-11
> **基于评估**: [TECH_DEBT_ASSESSMENT_V4.0.md](./TECH_DEBT_ASSESSMENT_V4.0.md)

---

## 范围调整说明

基于代码探索，对评估报告中的 P0-P1 做如下诚实调整：

| 任务 | 原计划 | 调整后 | 原因 |
|------|--------|--------|------|
| P0.2 | dispatcher_base.py 测试 | 改为 dispatcher mixins 测试 | dispatcher_base.py 仅 128 行抽象声明，无实现逻辑 |
| P0.3 | CI 安装 Pillow/Streamlit | 仅验证 | CI test.yml L38 已安装 `streamlit Pillow` |
| P1.3 | workflow_engine_base.py 测试 | 聚焦缺口补充 | 已有 4 个测试文件覆盖部分逻辑 |

---

## P0 — 立即执行

### P0.1: dispatch_steps.py 测试补充

**目标模块**: `scripts/collaboration/dispatch_steps.py` (~1030 行)
**目标类**: `PostDispatchPipeline`
**当前测试**: 仅 4 处间接引用，无专属测试文件
**目标**: 创建 `tests/test_dispatch_steps.py`，40-50 测试

**测试范围**:
- `execute()` 方法 (L154-L369): 主执行入口，协调步骤 8-23
- `_collect_worker_results()` (L375-L399): 结果收集
- `_build_step_timings()` (L405-L414): 步骤时间统计
- `_build_lifecycle_trace()` (L416-L447): 生命周期追踪
- 各 mixin 步骤的集成测试

**验证标准**:
- 新增 40+ 测试全部通过
- ruff check + format 通过
- mypy 0 errors
- 覆盖率提升 ~2%

### P0.2: dispatcher mixins 测试补充

**目标模块**: dispatcher mixins（有实际逻辑的）
- `dispatcher_utils_mixin.py` — 角色分析、报告格式化
- `dispatcher_status_mixin.py` — 性能统计、回归检测
- `dispatcher_error_mixin.py` — 错误处理
- `dispatcher_audit_mixin.py` — 审计日志

**目标**: 创建 `tests/test_dispatcher_mixins.py`，30-40 测试
**验证标准**: 新增测试全部通过，覆盖率提升 ~1.5%

### P0.3: CI Pillow/Streamlit 验证

**现状**: CI test.yml L38 已安装 `streamlit Pillow`
**行动**: 确认 `pip install -e ".[dev]"` 包含这两个依赖，验证 7 个 Pillow skip 在 CI 中不再触发
**验证标准**: CI run 中 skip 数减少

---

## P1 — 短期执行

### P1.1: 批量修复 55 个 no-any-return

**已识别**: 55 个 `# type: ignore[no-any-return]`，分布在 30 个文件中

**重灾区**:
| 模块 | 数量 | 模式 |
|------|------|------|
| memory_serializer.py | 9 | 委托 writer 返回 Any |
| dispatcher_utils_mixin.py | 4 | 委托 report_formatter |
| performance_monitor.py | 4 | psutil 返回 |
| memory_query.py | 4 | 委托 reader |
| enhanced_worker.py | 3 | 委托 briefing/cache |

**修复策略**:
1. **委托模式** (占 70%): 为被委托方法添加精确返回类型，移除 ignore
2. **psutil/json 返回** (占 20%): 添加 cast() 或明确返回类型
3. **复杂动态类型** (占 10%): 保留 ignore 但添加注释说明

**验证标准**: 移除 40+ 个 no-any-return，mypy 0 errors

### P1.2: 拆分 4 个 God Class

**目标文件**:
| 模块 | 行数 | 职责域 | 拆分方向 |
|------|------|--------|----------|
| mce_adapter.py | ~560 | 分类/存储/检索/规则 | 提取 RuleMatcher + MemoryRetriever |
| redis_cache.py | ~537 | 连接/CRUD/TTL/统计 | 提取 CacheStatistics + ConnectionManager |
| warmup_manager.py | ~581 | 预热/缓存/调度/元数据 | 提取 WarmupScheduler + WarmupCache |
| worker.py | ~638 | 执行/消息/状态/缓存 | 提取 ScratchpadHandler + WorkerState |

**原则**:
- 提取子类/辅助类，不改变公开 API
- 保持向后兼容（原类作为 facade）
- 每个拆分后单独运行测试验证
- 利用已有测试作为安全网

**验证标准**:
- 所有现有测试通过
- ruff + mypy 通过
- God Class 候选从 4 降至 0-1

### P1.3: workflow_engine_base.py 缺口补充

**现状**: 已有 4 个测试文件覆盖部分逻辑
**缺口**: workflow_engine_base.py 的核心方法（create_workflow, execute_step, get_status 等）
**目标**: 补充 20-30 测试
**验证标准**: 覆盖率提升 ~1%

### P1.4: 真实 LLM 性能基准刷新

**条件**: 需要 API key
**行动**: 如有 key，运行 `benchmark_real_llm.py`，更新 MATURITY_ASSESSMENT
**降级**: 无 key 则跳过，标注"待实测"

---

## 版本管理

- **当前版本**: 4.0.0
- **目标版本**: 4.0.1 (PATCH 递增，修复/重构/优化无新功能)
- **更新位置**: _version.py, pyproject.toml, README (EN/CN/JP), SKILL.md, skill-manifest.yaml, CHANGELOG

## 验证清单

- [ ] ruff check . --ignore=E501 通过
- [ ] ruff format --check . 通过
- [ ] mypy scripts/ 通过 (0 errors)
- [ ] pytest tests/ 全部通过 (0 failures)
- [ ] CI run 全绿 (security + test + lint + build + e2e)
- [ ] 版本号所有位置一致
- [ ] 文档更新 (CHANGELOG, PROJECT_STATUS)
