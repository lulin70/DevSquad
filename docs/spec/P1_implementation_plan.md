# P1 实施计划文档

> **文档类型**: 实施计划 (DevSquad 文档先行)
> **创建日期**: 2026-07-13
> **版本**: v4.0.9 → v4.0.10 (PATCH)
> **状态**: 实施中
> **依据**: [V4.0.9_P1_P2_Improvement_Assessment.md](../audits/V4.0.9_P1_P2_Improvement_Assessment.md)

---

## 一、实施范围

P1 四项改进，按依赖和难度排序：

| 序号 | 任务 | 预估 | 依赖 |
|------|------|------|------|
| P1-D | 覆盖率阈值 60→75 | 0.5h | 无 |
| P1-C | ue_test_heuristic_mixin LLM 路径测试 | 1h | 无 |
| P1-A | redis_cache.py 专用测试 | 3h | 安装 fakeredis |
| P1-B | Loop Engineering 端到端闭环测试 | 2h | 无 |

---

## 二、P1-D: 覆盖率阈值提升

### 方案
- 文件: `pyproject.toml`
- 修改: `fail_under = 60` → `fail_under = 75`
- 理由: 实际覆盖率 80.03%，阈值 60% 过低无法防止退化

### 验证
- `python -m pytest tests/ --cov=scripts/collaboration --cov-branch -q` 确认覆盖率 ≥75%

---

## 三、P1-C: ue_test_heuristic_mixin LLM 路径测试

### 现状
- 文件: `scripts/collaboration/ue_test_heuristic_mixin.py` (236 行)
- 覆盖率: 65% — 未覆盖 L36, L85-97, L110-135
- 未覆盖的是 `_assess_with_llm` 和 `_parse_llm_usability_response` 方法

### 测试设计
1. **test_assess_usability_with_llm_backend**: 提供 mock llm_backend，验证走 LLM 路径
2. **test_assess_usability_without_llm_falls_back_to_rules**: 无 llm_backend 时走规则路径
3. **test_assess_with_llm_falls_back_on_error**: LLM 异常时回退到规则评估
4. **test_parse_llm_usability_response_valid_json**: 解析合法 JSON 响应
5. **test_parse_llm_usability_response_invalid_json_falls_back**: 非法 JSON 回退到规则
6. **test_parse_llm_usability_response_partial_data**: 部分字段缺失的容错
7. **test_build_usability_prompt_contains_heuristics**: prompt 包含 10 项启发式

### 文件
- 新增测试到: `tests/test_ue_test_framework.py` (已有 47 测试)
- 使用 unittest.mock.Mock 模拟 llm_backend.generate() 返回值

---

## 四、P1-A: redis_cache.py 专用测试

### 现状
- 文件: `scripts/collaboration/redis_cache.py` (730 行)
- 覆盖率: **0%** — 无专用测试文件
- 依赖: `redis.asyncio` (未安装), `fakeredis` (未安装)

### 方案
1. **安装 fakeredis**: `pip install fakeredis` + 加入 pyproject.toml `[dev]` 依赖
2. **新建**: `tests/test_redis_cache.py`
3. **不安装 redis 包** — fakeredis 提供 `FakeAsyncRedis` 替代 `redis.asyncio`

### 测试设计 (RedisCacheBackend)
1. **test_init_defaults**: 默认参数初始化
2. **test_init_with_env_vars**: REDIS_URL/CACHE_PREFIX/CACHE_TTL 环境变量
3. **test_prefixed_key**: 前缀添加/移除
4. **test_set_and_get**: 基本 set/get 往返
5. **test_get_miss**: 不存在的 key 返回 None
6. **test_delete**: 删除存在的 key
7. **test_delete_miss**: 删除不存在的 key 返回 False
8. **test_clear**: 清空所有带前缀的 key
9. **test_mset_and_mget**: 批量操作
10. **test_mget_empty_keys**: 空列表返回空
11. **test_mset_empty_mapping**: 空映射返回 True
12. **test_stats**: 统计信息包含必要字段
13. **test_stats_hit_rate**: 命中率计算
14. **test_health_check**: 健康检查返回状态
15. **test_health_check_throttled**: 频繁检查被跳过
16. **test_scan_keys**: 按模式扫描 key
17. **test_close**: 关闭连接
18. **test_enable_compression**: 启用 gzip 压缩
19. **test_retry_on_failure**: 重试机制（mock 连接失败）
20. **test_reconnect**: 自动重连

### 测试设计 (SyncRedisCacheWrapper)
21. **test_sync_wrapper_get_set**: 同步包装器基本操作
22. **test_sync_wrapper_delete**: 同步删除
23. **test_sync_wrapper_clear**: 同步清空
24. **test_sync_wrapper_health_check**: 同步健康检查
25. **test_sync_wrapper_close**: 同步关闭

### Mock 策略
- 使用 `fakeredis.aioredis.FakeRedis` 替代真实 Redis
- 通过 `monkeypatch` 替换 `redis.asyncio` 模块
- 不 mock RedisCacheBackend 本身（测试真实逻辑）

---

## 五、P1-B: Loop Engineering 端到端闭环测试

### 现状
- `test_loop_engineering.py` 已有 36 个测试（数据模型+各阶段单元测试）
- `TestLoopKernel` 有 3 个集成测试但未验证完整自迭代闭环
- `FeedbackControlLoop` 已通过 `dispatch_steps_feedback_mixin.py` 集成

### 测试设计
1. **test_loop_full_cycle_iteration**: 验证完整的 Discovery→Handoff→Verify→Persist→Schedule 闭环
2. **test_loop_feedback_feeds_into_next_sense**: 验证 Feedback 结果反馈到下一轮 Discovery
3. **test_loop_terminates_on_quality_gate**: quality_gate 达标时终止
4. **test_loop_terminates_on_max_iterations**: 达到 max_iterations 时终止
5. **test_loop_stop_manual**: 手动 stop() 后终止
6. **test_loop_fix_on_verification_failure**: 验证失败时进入 FIX 而非 STOP
7. **test_loop_human_checkpoint**: 达到 human_checkpoint_every 时暂停
8. **test_feedback_control_loop_integration**: FeedbackControlLoop 与 dispatcher 的集成

### 文件
- 新增测试到: `tests/test_loop_engineering.py` (已有 36 测试)
- 新增 `TestLoopEndToEnd` 类

---

## 六、验证计划

### 单元测试验证
```bash
# P1-D 验证
python -m pytest tests/ --cov=scripts/collaboration --cov-branch --cov-report=term-missing -q

# P1-C 验证
python -m pytest tests/test_ue_test_framework.py -v --cov=scripts/collaboration/ue_test_heuristic_mixin

# P1-A 验证
python -m pytest tests/test_redis_cache.py -v --cov=scripts/collaboration/redis_cache

# P1-B 验证
python -m pytest tests/test_loop_engineering.py -v
```

### 全套回归验证
```bash
# 全套测试 (排除 smoke/e2e)
python -m pytest tests/ --timeout=60 --tb=line -q --ignore=tests/smoke --ignore=tests/e2e

# ruff check
ruff check .

# 覆盖率确认 ≥75%
python -m pytest tests/ --cov=scripts/collaboration --cov-branch --cov-fail-under=75 -q
```

---

## 七、版本规划

- 当前版本: v4.0.9
- 完成后版本: v4.0.10 (PATCH — 测试补充，无新功能)
- 版本更新位置: VERSION, pyproject.toml, scripts/collaboration/_version.py, Dockerfile, skill-manifest.yaml, SKILL.md, README.md, CHANGELOG.md, CHANGELOG-CN.md

---

*文档创建: 2026-07-13 | DevSquad 文档先行 | 版本: v4.0.9*
