# 协作系统 (Collaboration System) 测试用例

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v1.0.0 | 2026-04-15 | 测试专家 | 初始版本：98 个测试用例覆盖全部用户故事 | 待审核 |

---

## 用例统计

| 类别 | 数量 | 覆盖范围 |
|------|------|---------|
| T1: Scratchpad 基础 CRUD | 8 | US-1.1~1.3 |
| T2: Scratchpad 查询过滤 | 7 | US-1.2 |
| T3: Scratchpad 统计与持久化 | 6 | US-1.5~1.7 |
| T4: Worker 创建与执行 | 6 | US-2.1~2.2 |
| T5: Worker 交互(问题/冲突/通知/投票) | 5 | US-2.3~2.5 |
| T6: Consensus 提案与投票 | 6 | US-3.1~3.2 |
| T7: Consensus 共识判定 | 6 | US-3.3~3.4 |
| T8: Coordinator 规划与创建 | 5 | US-4.1~4.2 |
| T9: Coordinator 执行与收集 | 5 | US-4.3~4.4 |
| T10: Coordinator 冲突解决与报告 | 4 | US-4.5 |
| T11: BatchScheduler | 3 | US-5.1 |
| BT: 边界与异常 | 19 | E-01~E-08 |
| IT: 集成测试 | 12 | 模块间交互 |
| E2E: 用户旅程 | 8 | 旅程 A/B/C + 变体 |
| **合计** | ****100**** | |

---

## Phase 1: 单元测试用例

### T1: Scratchpad 基础 CRUD (US-1.1~1.3)

| 用例ID | 标题 | 前置条件 | 步骤 | 预期结果 | 对应AC |
|--------|------|---------|------|---------|-------|
| T1.1 | 写入基本条目 | 空 Scratchpad | write(ScratchpadEntry(worker_id="w1", role_id="arch", content="发现N+1问题")) | 返回 entry_id，条目可读回 | AC-1.1.1~4 |
| T1.2 | 自动生成 ID 和时间戳 | 空 Scratchpad | 写入不指定 entry_id 的条目 | entry_id 以 "entry-" 开头，timestamp 为当前时间 | AC-1.1.2 |
| T1.3 | 条目带标签和置信度 | 空 Scratchpad | 写入 tags=["perf","db"], confidence=0.9 | 属性正确保存和读取 | AC-1.1.3 |
| T1.4 | 按 ID 读取单条 | 有 N 条记录 | read() 后检查返回列表包含目标 ID | 精确匹配 | AC-1.1.4 |
| T1.5 | 标记已解决 | 存在 ACTIVE 条目 | resolve(entry_id, "已修复") | status=RESOLVED，内容追加 [RESOLVED] | AC-1.3.1~3 |
| T1.6 | 解决时版本号递增 | version=1 的条目 | resolve() 后检查 version | version == 2 | AC-1.3.4 |
| T1.7 | 解决不存在的 ID | 空 Scratchpad | resolve("nonexistent") | 不抛异常，静默忽略 | AC-边界 |
| T1.8 | 序列化/反序列化 round-trip | 已有条目 | to_dict() → from_dict() → 比较 | 所有字段一致 | 数据完整性 |

### T2: Scratchpad 查询过滤 (US-1.2)

| 用例ID | 标题 | 前置条件 | 步骤 | 预期结果 | 对应AC |
|--------|------|---------|------|---------|-------|
| T2.1 | 关键词全文搜索 | 10 条混合类型条目(3条含"性能") | read(query="性能") | 返回恰好 3 条 | AC-1.2.1 |
| T2.2 | 按 EntryType 过滤 | FINDING×5, DECISION×3, CONFLICT×2 | read(entry_type=FINDING) | 仅返回 5 条 FINDING | AC-1.2.2 |
| T2.3 | 按 EntryStatus 过滤 | ACTIVE×8, RESOLVED×2 | read(status=RESOLVED) | 仅返回 2 条 | AC-1.2.3 |
| T2.4 | 按 worker_id 过滤 | w1 写 3 条, w2 写 2 条 | read(worker_id="w1") | 仅返回 w1 的 3 条 | AC-1.2.4 |
| T2.5 | 按标签过滤 | tags 含 "security" 的 2 条 | read(tags=["security"]) | 返回 2 条 | AC-1.2.5 |
| T2.6 | 限制返回数量 | 100 条记录 | read(limit=10) | 返回最多 10 条 | AC-1.2.6 |
| T2.7 | 组合过滤：type+status+query | 多种混合数据 | read(entry_type=FINDING, status=ACTIVE, query="API") | 同时满足所有条件 | AC-组合 |

### T3: Scratchpad 统计、摘要、容量、持久化 (US-1.5~1.7)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T3.1 | get_stats 完整性 | 写入多种类型条目后调用 | 包含 total_entries/by_type/by_status/by_worker/write_count/read_count | AC-1.5.1 |
| T3.2 | get_summary Markdown 格式 | 有 findings+decisions+conflicts | 返回含 #/## 标题的 Markdown 文本 | AC-1.5.2~3 |
| T3.3 | get_conflicts 仅返回活跃冲突 | ACTIVE CONFLICT×2, RESOLVED CONFLICT×1 | 返回 2 个 | AC-1.4.1~2 |
| T3.4 | JSONL 持久化写入 | 创建带 persist_dir 的 SP，写 5 条 | 文件存在且含 5 行 JSON | AC-1.6.1~2 |
| T3.5 | JSONL 持久化恢复 | 销毁后重建同 persist_dir 的 SP | 自动加载 5 条，总数正确 | AC-1.6.3 |
| T3.6 | LRU 淘汰优先 RESOLVED | 写满 1000 条(含 RESOLVED)，再写 1 条 | 最旧 RESOLVED 被淘汰 | AC-1.7.1~4 |

### T4: Worker 创建与执行 (US-2.1~2.2)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T4.1 | 创建基本 Worker | Worker("w1", "arch", prompt, sp) | 属性正确 | AC-2.1.1~3 |
| T4.2 | Factory 批量创建 | WorkerFactory.create_batch(3 configs, sp) | 返回 3 个不同 Worker | AC-2.1.3 |
| T4.3 | execute 成功 | w.execute(TaskDefinition(desc="设计认证")) | success=True, duration>0, scratchpad 新增 FINDING | AC-2.2.1~5 |
| T4.4 | execute 上下文感知 | 先在 SP 写相关发现，再 execute | _do_work 输出中包含相关发现引用 | AC-2.2.5 |
| T4.5 | execute 异常处理 | Worker 的 _do_work 抛出异常 | success=False, error 非空 | AC-2.2.3 |
| T4.6 | Factory.create 单个 | WorkerFactory.create(cfg, sp) | 等价于 Worker(...) | AC-2.1 |

### T5: Worker 交互操作 (US-2.3~2.5)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T5.1 | write_finding | w.write_finding(ScratchpadEntry(FINDING)) | SP 新增 1 FINDING，_entries_written_count++ | — |
| T5.2 | write_question + 通知 | w.write_question("?", to_roles=["pm"]) | SP 新增 QUESTION，notification outbox 含 1 条 | AC-2.3.1~4 |
| T5.3 | write_conflict | w.write_conflict("冲突内容", target_id, "原因") | SP 新增 CONFLICT，tags 含 target_id | AC-2.4.1~3 |
| T5.4 | vote_on_proposal 权重 | arch Worker 投票 | Vote.weight == 1.5 | AC-2.5.1~3 |
| T5.5 | get_pending_notifications | 发送 2 条通知后获取 | 返回 2 条，outbox 清空 | AC-2.3.4 |

### T6: Consensus 提案与投票 (US-3.1~3.2)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T6.1 | create_proposal 基本属性 | ce.create_proposal("topic", "p1", "content") | proposal_id 以 "prop-" 开头, status="open" | AC-3.1.1~4 |
| T6.2 | cast_vote 正常 | open 提案 + Vote(decision=True) | votes 列表新增 1 条 | AC-3.2.1~3 |
| T6.3 | cast_vote 重复投票 | 同一提案投 3 次 | votes 列表有 3 条 | AC-3.2.3 |
| T6.4 | cast_vote 已关闭提案 | closed 提案 + cast_vote | 抛出 ValueError | AC-3.2.2 |
| T6.5 | create_proposal 带 options | options=["A","B","C"] | proposal.options == ["A","B","C"] | AC-3.1.4 |
| T6.6 | get_record 查询 | 达成共识后查询 | 返回正确的 ConsensusRecord | — |

### T7: Consensus 共识判定 (US-3.3~3.4)

| 用例ID | 标题 | 投票配置 | 预期 outcome | 对应AC |
|--------|------|---------|-------------|-------|
| T7.1 | 简单多数通过 | arch+(1.5), pm+(1.2) vs 反对(0) | APPROVED (权重比 100%) | AC-3.3.2 |
| T7.2 | 否决权触发升级 | arch+(1.0), sec-(-1.0 veto) | ESCALATED | AC-3.3.3, AC-3.4.1~3 |
| T7.3 | 意见分裂 |赞成50% vs 反对50% | SPLIT | AC-3.3.4 |
| T7.4 | 零投票超时 | 无任何投票 | TIMEOUT | AC-3.3.5 |
| T7.5 | 绝对多数通过 | 4 票赞成(总权 4.7) vs 1 票反对(1.0) | APPROVED (82% > 67%) | AC-3.3.2 |
| T7.6 | 共识后状态关闭 | reach_consensus() 后 | proposal.status == "closed" | AC-3.3.6 |

### T8: Coordinator 规划与创建 (US-4.1~4.2)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T8.1 | plan_task 3 角色并行 | coord.plan_task("task", [arch,tester,pm]) | plan.total_tasks==3, batches[0].mode==PARALLEL | AC-4.1.1~4 |
| T8.2 | plan_task 带 stage_id | stage_id="stage2" | 每个 TaskDefinition.stage_id=="stage2" | AC-4.1.4 |
| T8.3 | spawn_workers 3 个 | spawn_workers(plan) | 3 个 Worker，共享同一 SP | AC-4.2.1~3 |
| T8.4 | spawn_workers 单角色 | 1 个角色的 plan | 1 个 Worker，estimated_parallelism==0 | AC-4.1.3 |
| T8.5 | workers 字典一致性 | spawn_workers 后检查 coord.workers | len(coord.workers) == 任务数 | AC-4.2.2 |

### T9: Coordinator 执行与收集 (US-4.3~4.4)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T9.1 | execute_plan 全部成功 | 3 Workers 执行 | completed_tasks==3, success=True | AC-4.3.1~5 |
| T9.2 | execute_plan 产生发现 | 执行后检查 SP | 每个 Worker 至少写 1 条 FINDING | AC-4.3.4 |
| T9.3 | collect_results 结构 | 执行后 collect_results() | 含 coordinator_id/scratchpad/findings_count 等 | AC-4.4.1~4 |
| T9.4 | collect_results notifications | 某 Worker 发送了通知 | notifications 列表非空 | AC-4.4.4 |
| T9.5 | execute_plan 耗时 | 执行前记录时间 | result.duration_seconds > 0 | AC-4.3.5 |

### T10: Coordinator 冲突解决与报告 (US-4.5)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T10.1 | resolve_conflicts 无冲突 | SP 中无 CONFLICT | 返回空列表 | — |
| T10.2 | resolve_conflicts 有冲突 | SP 中有 2 个 ACTIVE CONFLICT | 返回 2 条 ConsensusRecord | AC-4.5.1~2 |
| T10.3 | generate_report 格式 | 完整流程后 generate_report() | 含 "协作报告"/Worker/Scratchpad/共识 章节 | AC-4.5.3~4 |
| T10.4 | generate_report 长度 | 5 角色完整流程 | report 长度 > 200 字符 | AC-4.5.4 |

### T11: BatchScheduler (US-5.1)

| 用例ID | 标题 | 步骤 | 预期结果 | 对应AC |
|--------|------|------|---------|-------|
| T11.1 | PARALLEL batch | PARALLEL batch 含 2 任务 | total_tasks==2 | AC-5.1.1~2 |
| T11.2 | SERIAL batch | SERIAL batch 含 2 任务 | 串行执行 | AC-5.1.2 |
| T11.3 | schedule 多 batch | [PARALLEL batch, SERIAL batch] | 按顺序执行 | AC-5.1.3 |

---

## Phase 2: 边界与异常测试

| 用例ID | 标题 | 步骤 | 预期结果 | 对应场景 |
|--------|------|------|---------|---------|
| BT.1 | 空内容条目写入 | content="" | 正常写入 | E-01 |
| BT.2 | 查询不存在 ID | read(query="不可能存在的字符串xyz") | 返回 [] | E-02 |
| BT.3 | Worker execute 异常 | _do_work 手动抛 Exception | success=False, error 非空 | E-03 |
| BT.4 | 已关闭提案投票 | closed 提案 cast_vote | ValueError | E-04 |
| BT.5 | 特殊字符内容 | content='<script>alert("xss")</script>' | 正常存储和检索 | 安全 |
| BT.6 | 超长内容(10KB) | content="A"*10000 | 正常存储 | 边界 |
| BT.7 | 超多标签 | tags=[f"tag{i}" for i in range(100)] | 正常存储 | 边界 |
| BT.8 | confidence 边界值 | confidence=0.0 和 1.0 | 正常存储 | 边界 |
| BT.9 | limit=0 | read(limit=0) | 返回 [] | 边界 |
| BT.10 | limit 超过总量 | read(limit=9999) | 返回全部 | 边界 |
| BT.11 | 空角色规划 | available_roles=[] | plan.total_tasks==0 | E-边界 |
| BT.12 | 单角色协作 | 1 个角色 | 正常执行 | E-边界 |
| BT.13 | 大规模角色(20个) | 20 个角色 | plan+spawn+execute 正常 | 压力 |
| BT.14 | 全部投反对票 | 所有人 decision=False | REJECTED | E-边界 |
| BT.15 | 全部否决(weight<0) | 所有人 weight=-1.0 | ESCALATED | E-边界 |
| BT.16 | 混合投票(有赞成有否决) | 2 赞成 + 1 否决 | ESCALATED | E-边界 |
| BT.17 | 高置信度 finding | confidence=1.0 | 统计正确 | 边界 |
| BT.18 | 低置信度 question | confidence=0.01 | 正常存储 | 边界 |
| BT.19 | export_json 完整性 | 多种类型条目后 export | 有效 JSON，所有条目都在 | 数据 |

---

## Phase 3: 集成测试

| 用例ID | 标题 | 步骤 | 验证点 |
|--------|------|------|-------|
| IT.1 | W→SP→W 信息流 | W1 写 FINDING → W2 读到 | Worker 间通过 Scratchpad 共享信息 |
| IT.2 | W→W 问答闭环 | W1 write_question → W2 收到 notification | TaskNotification 协议工作正常 |
| IT.3 | Coord→Workers→SP 完整链路 | plan→spawn→execute→collect | 端到端数据流完整 |
| IT.4 | Coord→Consensus→SP 冲突解决 | W1 写 conflict → coord.resolve → SP resolved | 共识引擎集成正确 |
| IT.5 | 持久化跨实例恢复 | 实例 A 写入 → 销毁 → 实例 B 恢复 | 数据持久化可靠 |
| IT.6 | 持久化并发安全 | 两个实例同一 persist_dir | 无数据损坏 |
| IT.7 | Worker 上下文感知执行 | SP 预填相关发现 → Worker execute | Worker 能读到上下文 |
| IT.8 | 多 Worker 并行写入 | 5 Worker 同时 write | 无丢失，版本号正确 |
| IT.9 | Reference 关联 | Entry A 引用 Entry B | from_dict/to_dict 往返保留引用 |
| IT.10 | Notification XML 格式 | to_xml() 输出 | 符合 XML TaskNotification schema |
| IT.11 | get_summary 按 role 过滤 | get_summary(for_role="architect") | 仅显示相关内容 |
| IT.12 | clear 后重新使用 | sp.clear() → 写入新数据 | 状态完全重置 |

---

## Phase 4: E2E 用户旅程测试

| 用例ID | 旅程 | 场景描述 | 验证点 |
|--------|------|---------|-------|
| E2E-1 | 旅程A | 5 角色(arch/pm/tester/ui/coder)完整协作 | plan→spawn→execute→collect→resolve→report 全链路 |
| E2E-2 | 旅程B | 轻量 Scratchpad 交换 | write→read→resolve 三步流程 |
| E2E-3 | 旅程C | 独立共识决策 | create_proposal→vote×3→reach_consensus |
| E2E-4 | 含冲突变体 | 旅程A + Worker 写入 CONFLICT | resolve_conflicts 正确触发 |
| E2E-5 | 否决票变体 | 旅程C + security 投否决 | ESCALATED 结果 |
| E2E-6 | 持久化恢复变体 | 旅程A + persist_dir + 重启恢复 | 数据完整 |
| E2E-7 | 压力变体 | 20 角色 × 每人写 10 条 = 200 条 | 性能可接受 |
| E2E-8 | 错误恢复变体 | 旅程A + 1 个 Worker 故意报错 | 其他 Worker 正常完成 |
