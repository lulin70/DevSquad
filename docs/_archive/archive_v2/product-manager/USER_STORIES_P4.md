# Phase 4: MemoryBridge 记忆桥接系统 - 用户故事 (USER_STORIES)

**版本**: v1.0
**日期**: 2026-04-16
**作者**: PM (产品经理角色)
**基于设计文档**: [v3-phase4-memorybridge-design.md](../architecture/v3-phase4-memorybridge-design.md)

---

## Epic 概览

| Epic ID | 名称 | 用户价值 | 优先级 | 故事数 |
|---------|------|---------|--------|-------|
| E1 | **记忆召回** | 任务执行前自动获取相关历史经验，避免重复犯错 | P0 | 3 |
| E2 | **经验捕获** | 执行过程中的洞察自动沉淀为持久记忆 | P0 | 2 |
| E3 | **知识管理** | 领域知识的增删改查 + 搜索 | P1 | 2 |
| E4 | **反馈闭环** | 用户反馈自动记录并影响后续决策 | P1 | 2 |
| E5 | **模式持久化** | Skillifier 学到的成功模式跨会话保留 | P2 | 2 |
| E6 | **生命周期** | 记忆的遗忘、压缩、清理自动化 | P2 | 2 |

**总计: 13 个用户故事 | 预计验收标准: ~58 AC**

---

## E1: 记忆召回

### US-4.01: 作为 Coordinator，我希望在规划任务时能召回相关历史经验

**背景**: 当前每次任务都从零开始。如果之前解决过类似问题（如"微服务拆分策略"），历史经验应该被自动注入到任务上下文中。

**验收标准 (AC)**:
- AC-01: `recall(MemoryQuery("微服务架构"))` 返回相关知识/案例，耗时 < 50ms
- AC-02: 返回结果按 `relevance_score` 降序排列
- AC-03: 返回结果包含 `memory_type` / `title` / `content` / `domain` 字段
- AC-04: 无匹配结果时返回空列表（不报错）
- AC-05: 支持按 `domain` 过滤（如只看"架构设计"领域）

**边界场景**:
- B1: 查询文本为空字符串 → 返回空列表
- B2: 记忆库完全为空 → 返回空列表，不崩溃
- B3: 包含中英文混合查询 → 正确分词和匹配

---

### US-4.02: 作为 Worker，我希望执行过程中能按需检索补充知识

**背景**: Worker 在执行过程中可能遇到不熟悉的技术点，需要从知识库快速查找参考资料。

**验收标准 (AC)**:
- AC-01: `search_knowledge(["缓存一致性", "Redis"])` 返回匹配条目
- AC-02: 支持多关键词 AND 逻辑（所有关键词都需匹配）
- AC-03: 单关键词搜索也能工作
- AC-04: 搜索结果限制默认 `limit=5`，可配置
- AC-05: 结果包含完整 `content` 字段供 Worker 参考

---

### US-4.03: 作为系统，我希望记忆检索使用倒排索引保证性能

**背景**: 随着记忆条目增长（数百~数千），线性扫描不可接受。需要索引加速。

**验收标准 (AC)**:
- AC-01: 500 条记忆的搜索耗时 < 20ms
- AC-02: 写入新记忆后索引自动更新（增量或触发重建）
- AC-03: 删除记忆后索引同步清理
- AC-04: 索引支持中文分词（基础版：按字符/词组切分）
- AC-05: TF-IDF 相关度评分合理（精确匹配 > 部分匹配 > 无关）

---

## E2: 经验捕获

### US-4.04: 作为系统，我希望 Worker 完成任务后自动捕获关键发现

**背景**: Scratchpad 中记录了 FINDING 类型的条目（如"发现 N+1 查询问题"）。这些高价值发现应自动进入记忆库。

**验收标准 (AC)**:
- AC-01: `capture_execution(record, scratchpad_entries)` 将 confidence > 0.7 的 FINDING 转为 episodic 记忆
- AC-02: 生成的记忆包含：task_description / finding_content / worker_id / timestamp
- AC-03: 自动打标签（从 task_description 提取关键词）
- AC-04: 返回新创建的记忆 ID
- AC-05: 同一任务的多个 FINDING 生成多条独立记忆

**边界场景**:
- B1: scratchpad 无 FINDING 类型条目 → 不写入，返回空
- B2: scratchpad 为空 → 不报错
- B3: FINDING 的 content 超长（>5000字）→ 自动截断并标记

---

### US-4.05: 作为系统，我希望错误和异常也能转化为学习机会

**背景**: 执行失败时的上下文（错误信息、触发条件）是宝贵的学习素材，应生成分析案例存入记忆库。

**验收标准 (AC)**:
- AC-01: `learn_from_mistake(error_context)` 生成 AnalysisCase 并写入
- AC-02: AnalysisCase 包含 problem/context/solutions 字段
- AC-03: 错误类型作为 domain 分类依据
- AC-04: 相似错误不重复生成（去重逻辑）
- AC-05: 生成的分析案例 status="completed"

---

## E3: 知识管理

### US-4.06: 作为开发者，我希望可以手动增删改查知识库条目

**背景**: 除了自动捕获，开发者也需要手动维护核心知识（如团队规范、架构决策记录）。

**验收标准 (AC)**:
- AC-01: `write_knowledge(KnowledgeItem)` 创建新条目，返回 ID
- AC-02: `read_knowledge(domain="架构设计")` 返回该域所有条目
- AC-03: `read_knowledge()` 不带参数返回全部
- AC-04: 更新操作通过 write 相同 ID 覆盖实现
- AC-05: 删除操作从文件系统和索引同时移除

---

### US-4.07: 作为系统，我希望有统一的记忆统计面板

**背景**: 了解记忆库健康状态：各类型数量、增长趋势、存储占用。

**验收标准 (AC)**:
- AC-01: `get_statistics()` 返回 MemoryStats 对象
- AC-02: 统计包含：total_memories / by_type_counts / oldest/newest / storage_size_kb
- AC-03: 统计包含：index_status（是否已构建）/ last_index_time
- AC-04: `print_diagnostics()` 输出人类可读的面板
- AC-05: 统计数据实时准确（与实际文件数一致）

---

## E4: 反馈闭环

### US-4.08: 作为用户，我希望我的反馈被正确记录并可追溯

**背景**: 用户在交互中提出的建议/投诉应被结构化记录，而非丢失。

**验收标准 (AC)**:
- AC-01: `record_feedback(UserFeedback(...))` 写入 JSON 文件
- AC-02: feedback 包含 type/content/rating/context/timestamp
- AC-03: 支持 suggestion/complaint/bug 三种类型
- AC-04: 可通过 `read_feedback(type="suggestion")` 过滤查询
- AC-05: 同一用户的多次反馈按时间排序

---

### US-4.09: 作为系统，我希望高频正向反馈能提升相关知识的权重

**背景**: 如果某类知识持续获得用户好评，应在召回时获得更高排名。

**验收标准 (AC)**:
- AC-01: 正向反馈（rating >= 4 或 type=suggestion）关联到相关 memory_id
- AC-02: 关联后该 memory 的 access_count 或 metadata.positive_feedbacks 增加
- AC-03: recall 时正相关度得分有加权加成（+10%）
- AC-04: 无关联目标的反馈不影响任何记忆权重
- AC-05: 权重影响在下次索引重建后生效

---

## E5: 模式持久化

### US-4.10: 作为系统，我希望 Skillifier 的高质量技能模式能跨会话保留

**背景**: Skillifier 在会话内学到的成功模式，当前随进程结束而消失。Phase 4 应将其持久化。

**验收标准 (AC)**:
- AC-01: `persist_pattern(SuccessPattern)` 写入 persisted_patterns/
- AC-02: 文件名格式: pattern_{timestamp}_{slug}.json
- AC-03: 只持久化 quality_score >= 70（grade A/B）的模式
- AC-04: 低质量模式（< 70）不写入但记录原因
- AC-05: 已存在的同名模式覆盖更新

---

### US-4.11: 作为 Coordinator，我希望启动时可加载已持久化的技能模式

**背景**: 新会话开始时，之前学到的成功模式应可供参考或直接复用。

**验收标准 (AC)**:
- AC-01: `read_patterns()` 返回所有已持久化的模式
- AC-02: `read_patterns(category="code-generation")` 按类别过滤
- AC-03: 加载后的模式可用于 suggest_skills_for_task() 输入
- AC-04: 无已持久化模式时返回空列表
- AC-05: 模式的 trigger_keywords 可用于记忆搜索匹配

---

## E6: 生命周期

### US-4.12: 作为系统，我希望陈旧记忆自动压缩以节省空间

**背景**: 60 天前的详细情景记忆价值降低，应压缩为摘要。

**验收标准 (AC)**:
- AC-01: 60 天以上的 episodic 记忆自动压缩（content → 摘要）
- AC-02: 压缩后标记 metadata.compressed=True
- AC-03: 原始长度记录在 metadata.original_length
- AC-04: 90 天以上的记忆可选归档或删除
- AC-05: 压缩操作可通过配置开关控制

---

### US-4.13: 作为系统，我希望记忆遵循遗忘曲线衰减访问权重

**背景**: 长时间未访问的记忆即使内容相关，也不应与新记忆同等排名。

**验收标准 (AC)**:
- AC-01: 7 天内记忆权重 = 1.0
- AC-02: 30 天记忆权重 ≈ 0.8（受访问频率调节）
- AC-03: 60 天记忆权重 ≈ 0.5
- AC-04: 90+ 天记忆权重 ≈ 0.3
- AC-05: 高频访问的记忆衰减更慢（access_count 调节因子）

---

## 总结

### 验收标准矩阵

| Epic | 故事数 | AC 数量 | 核心指标 |
|------|--------|---------|---------|
| E1 记忆召回 | 3 | 15 | recall < 50ms, index < 20ms |
| E2 经验捕获 | 2 | 10 | auto-capture FINDING → episodic |
| E3 知识管理 | 2 | 10 | CRUD + statistics |
| E4 反馈闭环 | 2 | 10 | feedback → weight adjustment |
| E5 模式持久化 | 2 | 10 | skill pattern cross-session |
| E6 生命周期 | 2 | 10 | forgetting curve + compression |
| **合计** | **13** | **~65** | **hit rate > 60%, latency < 50ms** |

### 用户旅程示例

#### 旅程 A: 首次使用 + 学习积累
```
1. 用户首次运行任务（记忆库为空）
   → recall() 返回空，正常执行
2. Worker 发现重要问题，写入 Scratchpad FINDING
   → capture_execution() 自动保存为 episodic 记忆
3. Skillifier 学到成功模式 (score=82)
   → persist_pattern() 保存到 persisted_patterns/
4. 用户给出正面反馈
   → record_feedback() 保存 + 提升相关权重
```

#### 旅程 B: 第二次类似任务（记忆生效）
```
1. 用户提交类似任务
   → recall() 返回上次的相关经验和模式
2. Coordinator 将历史经验注入任务描述
   → Worker 基于已有经验更快完成任务
3. 执行中发现新的细节
   → 新记忆追加，旧记忆 access_count++
4. get_statistics() 显示记忆库健康成长
```
