# Phase 4: MemoryBridge 记忆桥接系统 - 测试计划 (TEST_PLAN)

**版本**: v1.0
**日期**: 2026-04-16
**作者**: Tester (测试专家角色)
**基于**: [v3-phase4-memorybridge-design.md](../architecture/v3-phase4-memorybridge-design.md) + [USER_STORIES_P4.md](./USER_STORIES_P4.md)
**预估总用例数**: ~96

---

## 1. 测试策略概述

### 1.1 测试分层

```
┌─────────────────────────────────────────────┐
│              L3: E2E 端到端                   │ ~8 cases
│  写入→索引→搜索→遗忘→压缩 完整生命周期       │
├─────────────────────────────────────────────┤
│              L2: Integration 集成测试          │ ~10 cases
│  Coordinator/Skillifier 集成                 │
├─────────────────────────────────────────────┤
│              L1: Unit 单元测试                │ ~78 cases
│  T1~T8 各组件独立验证                         │
└─────────────────────────────────────────────┘
```

### 1.2 测试特殊考虑

| 方面 | 策略 |
|------|------|
| **文件 I/O** | 使用临时目录（tmpdir），测试后清理 |
| **并发安全** | 多线程读写同一记忆库 |
| **中文支持** | 查询/内容包含中英文混合 |
| **时间依赖** | 用 mock 时间或宽松断言 |
| **JSON 完整性** | 读写后验证 JSON 可解析 |

---

## 2. L1 单元测试详细设计

### T1: 数据模型验证 (~10 cases)

覆盖: MemoryType / MemoryItem / MemoryQuery / MemoryConfig / MemoryStats

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T1.01 | MemoryType 枚举完整性 | 6 种类型都有值 | P0 |
| T1.02 | MemoryItem 基本字段 | id/type/title/content/domain/tags 正确 | P0 |
| T1.03 | MemoryItem age_days 计算 | 返回正确天数差 | P1 |
| T1.04 | MemoryQuery 默认值 | limit=5, min_relevance=0.3 | P0 |
| T1.05 | MemoryConfig default | enabled=True, auto_capture=True | P0 |
| T1.06 | MemoryConfig lightweight | auto_capture=False, max=100 | P1 |
| T1.07 | MemoryConfig full | 大容量配置值正确 | P1 |
| T1.08 | MemoryRecallResult 结构 | memories/total_found/query_time_ms/hit_types | P1 |
| T1.09 | MemoryStats 字段完整 | total/by_type/oldest/newest/storage_size | P2 |
| T1.10 | 序列化/反序列化 | dataclass → dict → dataclass 往返一致 | P2 |

---

### T2: MemoryWriter (~8 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T2.01 | write_knowledge 创建新条目 | 文件存在，返回非空 ID | P0 |
| T2.02 | write_knowledge 内容正确 | JSON 包含所有字段 | P0 |
| T2.03 | write_episodic 创建 | episodic 记忆写入成功 | P0 |
| T2.04 | write_feedback 创建 | feedback JSON 格式正确 | P0 |
| T2.05 | write_pattern 创建 | pattern 写入 persisted_patterns/ | P1 |
| T2.06 | write_analysis 创建 | analysis case 含 whys/solutions | P1 |
| T2.07 | batch_write 批量 | N 条全部写入，返回成功计数 | P1 |
| T2.08 | 覆盖写入同 ID | 后写覆盖先写 | P2 |

---

### T3: MemoryReader (~8 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T3.01 | read_knowledge 全部 | 返回所有知识条目 | P0 |
| T3.02 | read_knowledge 按域过滤 | 只返回指定 domain 的条目 | P0 |
| T3.03 | read_knowledge 空库 | 返回空列表 | P0 |
| T3.04 | read_episodic 带 limit | 返回数量 <= limit | P1 |
| T3.05 | read_episodic 按 since 过滤 | 只返回指定时间后的 | P1 |
| T3.06 | read_feedback 按 type 过滤 | 只返回匹配 type 的 | P1 |
| T3.07 | read_patterns 按 category | 分类过滤正确 | P1 |
| T3.08 | read_analysis_cases 按 status | status 过滤正确 | P2 |

---

### T4: MemoryIndexer (~14 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T4.01 | build_index 基础 | 索引构建后 _index_built=True | P0 |
| T4.02 | build_index 倒排索引内容 | word → {id} 映射正确 | P0 |
| T4.03 | add_to_index 增量 | 新条目出现在索引中 | P0 |
| T4.04 | remove_from_index | 删除后不再被搜到 | P0 |
| T4.05 | search 精确匹配 | 完全匹配关键词得分最高 | P0 |
| T4.06 | search 部分匹配 | 部分匹配得分低于精确 | P0 |
| T4.07 | search 无结果 | 不相关查询返回空列表 | P0 |
| T4.08 | search 按 type_filter | 只返回指定类型的结果 | P1 |
| T4.09 | search 按 domain_filter | 域过滤正确 | P1 |
| T4.10 | search limit 限制 | 返回数量 <= limit | P1 |
| T4.11 | keyword_search 多关键词 AND | 所有关键词都需命中 | P1 |
| T4.12 | keyword_search 单关键词 | 单词也能工作 | P2 |
| T4.13 | _tokenize 中文分词 | 中文字符被正确切分 | P1 |
| T4.14 | _compute_relevance TF-IDF | 相关文档得分 > 不相关文档 | P1 |

---

### T5: MemoryBridge 核心 (~14 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T5.01 | recall 基本查询 | 返回 MemoryRecallResult | P0 |
| T5.02 | recall 耗时 < 50ms | query_time_ms < 50 | P0 |
| T5.03 | recall 空库 | total_found=0, memories=[] | P0 |
| T5.04 | capture_execution FINDING→episodic | 高置信度 FINDING 转为 episodic | P0 |
| T5.05 | capture_execution 低置信度跳过 | confidence<0.7 的不写入 | P0 |
| T5.06 | capture_execution 空 scratchpad | 不报错，返回 None | P1 |
| T5.07 | record_feedback 基本 | feedback 文件创建成功 | P0 |
| T5.08 | persist_pattern 高质量(score>=70) | 写入成功 | P1 |
| T5.09 | persist_pattern 低质量跳过 | score<70 不写入 | P1 |
| T5.10 | learn_from_mistake 生成分析案例 | AnalysisCase 创建 | P1 |
| T5.11 | search_knowledge 关键词搜索 | 返回匹配的 KnowledgeItem 列表 | P0 |
| T5.12 | get_statistics 结构完整 | 各字段有值 | P1 |
| T5.13 | get_recent_history 返回最近 N 条 | 数量 <= n，按时间降序 | P1 |
| T5.14 | print_diagnostics 输出非空 | 包含统计信息行 | P2 |

---

### T6: 生命周期管理 (~8 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T6.01 | forgetting_weight 新记忆(7天内) | weight ≈ 1.0 | P0 |
| T6.02 | forgetting_weight 成熟记忆(30天) | 0.5 < weight < 1.0 | P0 |
| T6.03 | forgetting_weight 陈旧记忆(60天) | 0.3 < weight < 0.6 | P0 |
| T6.04 | forgetting_weight 高频访问衰减慢 | access_count 高则权重更高 | P1 |
| T6.05 | compress_old_memories 60天+压缩 | content 变短，标记 compressed=True | P1 |
| T6.06 | compress_old_memories 新记忆不动 | 7 天内的不受影响 | P1 |
| T6.07 | cleanup_expired_memories 90天+删除 | 超过 retention_days 的被清理 | P2 |
| T6.08 | 生命周期配置开关 | compress_old=False 时不执行压缩 | P2 |

---

### T7: 存储抽象层 (~6 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T7.01 | JsonMemoryStore save+load | 写入后可读取相同数据 | P0 |
| T7.02 | JsonMemoryStore list_all | 返回已保存的所有条目 | P0 |
| T7.03 | JsonMemoryStore delete | 删除后 list_all 不再包含 | P1 |
| T7.04 | CompositeMemoryStore 路由 | KNOWLEDGE→Json, EPISODIC→SQLite | P0 |
| T7.05 | CompositeMemoryStore 未知类型 | 抛出合理异常或回退 | P2 |
| T7.06 | 存储目录自动创建 | base_dir 不存在时自动创建 | P1 |

---

### T8: 边界情况 (~10 cases)

| ID | 用例名称 | 验证点 | 优先级 |
|----|---------|--------|--------|
| T8.01 | 空字符串查询 | 返回空结果 | P0 |
| T8.02 | 特殊字符查询（<>/"'/\） | 不崩溃 | P1 |
| T8.03 | 超长 content (>100KB) | 正常存储和读取 | P1 |
| T8.04 | 并发 write 安全 | 20 线程同时写入无数据损坏 | P0 |
| T8.05 | 并发 read/write 安全 | 同时读写不崩溃 | P0 |
| T8.06 | 损坏的 JSON 文件 | 读取时跳过或报错而非崩溃 | P1 |
| T8.07 | 权限不足的目录 | 给出清晰错误信息 | P2 |
| T8.08 | 磁盘满模拟 | 写入失败时优雅降级 | P2 |
| T8.09 | Unicode 内容（emoji） | 存取不丢失 | P1 |
| T8.10 | 极大量记忆(5000+) 性能 | 操作在合理时间内完成 | P2 |

---

## L2 集成测试设计 (~10 cases)

### IT1: Coordinator 集成 (6 cases)

| ID | 用例名称 | 验证点 | 对应 US |
|----|---------|--------|--------|
| IT1.01 | 任务前召回注入上下文 | plan_task_with_memory 注入历史经验 | US-4.01 |
| IT1.02 | 无记忆时正常降级 | 空记忆库不影响任务规划 | US-4.01 |
| IT1.03 | 执行后自动捕获 | execute_plan 后调用 capture_execution | US-4.04 |
| IT1.04 | 错误时学习 | 异常触发 learn_from_mistake | US-4.05 |
| IT1.05 | 多轮任务记忆累积 | 第 2 轮比第 1 轮召回更多 | US-4.01 |
| IT1.06 | 统计面板反映增长 | get_statistics 显示数量增加 | US-4.07 |

### IT2: Skillifier 集成 (4 cases)

| ID | 用例名称 | 验证点 | 对应 US |
|----|---------|--------|--------|
| IT2.01 | 高质量模式持久化 | score=82 的模式被保存 | US-4.10 |
| IT2.02 | 低质量模式不持久化 | score=50 的模式不保存 | US-4.10 |
| IT2.03 | 启动时加载已有模式 | read_patterns 返回之前保存的 | US-4.11 |
| IT2.04 | 模式用于技能建议 | suggest_skills 使用已加载模式 | US-4.11 |

---

## L3 端到端测试设计 (~8 cases)

| ID | 场景 | 步骤 | 验收 | 对应旅程 |
|----|------|------|------|---------|
| E2E.01 | 首次使用积累旅程 | 空库→执行→捕获→反馈→统计 | 记忆从 0 增长 | 旅程 A |
| E2E.02 | 第二次使用生效旅程 | 有记忆→召回→加速执行→追加记忆 | hit rate > 0 | 旅程 B |
| E2E.03 | 完整生命周期 | 写入→索引→搜索→压缩→清理 | 全流程无错误 | — |
| E2E.04 | 反馈闭环 | 反馈→关联→权重变化→排名提升 | 正向反馈有效 | US-4.09 |
| E2E.05 | 高并发压力 | 30 线程同时读写搜索 | 无死锁/数据错 | T8.04/.05 |
| E2E.06 | 大规模记忆性能 | 1000 条记忆的搜索 < 50ms | 性能达标 | US-4.03 |
| E2E.07 | 中英文混合查询 | "Redis缓存一致性" 搜索 | 中文正确分词匹配 | US-4.01 B3 |
| E2E.08 | diagnostics 完整性 | print_diagnostics() 包含所有预期行 | 格式完整 | US-4.07 |

---

## 3. 测试优先级矩阵

| 优先级 | L1 Unit | L2 Integration | L3 E2E | 合计 |
|--------|---------|----------------|--------|------|
| **P0 (必须)** | ~38 | ~8 | ~4 | **~50** |
| **P1 (重要)** | ~30 | ~2 | ~3 | **~35** |
| **P2 (可选)** | ~10 | 0 | ~1 | **~11** |
| **合计** | **~78** | **~10** | **~8** | **~96** |

---

## 4. 性能验收标准

| 指标 | 目标值 | 测量方法 | 对应用例 |
|------|--------|---------|---------|
| recall() 延迟 (< 500 items) | < 50ms | perf_counter 包裹 | T5.02 |
| index search 延迟 (500 items) | < 20ms | perf_counter 包裹 | T4.03 |
| write_knowledge 延迟 | < 10ms | perf_counter 包裹 | T2.01 |
| batch_write (100 items) | < 200ms | perf_counter 包裹 | T2.07 |
| 全量索引重建 (500 items) | < 500ms | perf_counter 包裹 | T4.01 |
| 并发安全性 | 0 数据损坏 | 多线程 + 断言检查 | T8.04/.05 |
| 内存稳定性 | 无持续增长 | tracemalloc | T8.06 |

---

## 5. Mock/Fixture 策略

| 组件 | 策略 | 原因 |
|------|------|------|
| 文件系统 | tempfile.mkdtemp() | 隔离测试环境，自动清理 |
| 时间 | 固定或自由漂移 | 遗忘曲线测试需控制时间 |
| ScratchpadEntry | 真实对象 | capture_execution 需要真实结构 |
| ExecutionRecord | 真实对象 | 同上 |
| SQLite | :memory: 或临时文件 | 测试用内存数据库加速 |

---

## 6. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 中文分词质量影响搜索精度 | 中 | 中 | 提供基础版 + 可选 jieba |
| JSON 文件并发写入冲突 | 低 | 高 | 文件锁 + 写时复制 |
| 索引与数据不一致 | 中 | 中 | 每次 search 前可选 re-index |
| 临时目录清理失败 | 低 | 低 | try/finally 保证清理 |
