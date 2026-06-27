# 协作系统 (Collaboration System) 用户故事与场景文档

## 更新履历

| 版本 | 日期 | 更新人 | 更新内容 | 审核状态 |
|------|------|--------|----------|----------|
| v1.0.0 | 2026-04-15 | 产品经理 | 初始版本：基于 Phase 1 协作系统编写完整用户故事和场景 | 待审核 |

---

## 一、产品概述

### 1.1 产品定位
DevSquad 协作系统是一个基于 **Coordinator + Scratchpad + Worker** 模式的多 Agent 协作框架，灵感来源于 Claude Code 的 Coordinator 架构。它让多个 AI 角色像真实团队一样协作完成复杂任务。

### 1.2 核心价值主张
- **信息透明**: 所有 Worker 通过共享 Scratchpad 实时交换发现、决策、冲突
- **角色分工**: 每个 Worker 扮演特定角色（架构师、测试者、PM 等），各司其职
- **共识决策**: 权重投票机制确保重要决策经过充分讨论
- **可追溯**: 完整的执行历史和协作报告，每一步都有据可查

### 1.3 目标用户
| 用户类型 | 描述 | 核心诉求 |
|---------|------|---------|
| 项目负责人 | 需要协调多个 AI 角色完成复杂项目 | 一键启动多角色协作，自动生成报告 |
| AI 应用开发者 | 将协作系统集成到自己的工作流中 | API 简洁清晰，易于集成 |
| 质量保障人员 | 需要验证协作系统的可靠性 | 全面的测试覆盖，明确的验收标准 |

---

## 二、用户画像

### 2.1 用户画像 A: 李明 —项目负责人
- **背景**: 负责 SaaS 产品开发的技术负责人
- **痛点**: 单个 AI 角色无法覆盖所有专业领域（架构+测试+产品），需要多角色协同
- **期望**: 输入一个任务描述，自动分配给合适的角色，拿到完整的分析报告
- **典型场景**: "设计一个电商系统的认证模块" → 自动分配给架构师/测试者/PM → 收到完整报告

### 2.2 用户画像 B: 张华 —AI 工程师
- **背景**: 正在构建基于 LLM 的自动化工具链
- **痛点**: 需要可靠的多 Agent 协作基础设施，不想从零实现
- **期望**: 清晰的 API 接口，完善的错误处理，可扩展的架构
- **典型场景**: 在自己的 Python 项目中 `from collaboration import Coordinator` 直接使用

### 2.3 用户画像 C: 王芳 —质量保障专家
- **背景**: 负责 AI 系统的质量验证
- **痛点**: 多 Agent 系统的交互复杂，难以全面测试
- **期望**: 明确的用户场景定义，完整的测试用例，清晰的边界条件
- **典型场景**: 基于用户故事设计测试计划，验证系统的健壮性

---

## 三、用户故事 (User Stories)

### Epic 1: Scratchpad 共享黑板

#### US-1.1: 作为 Worker，我希望在 Scratchpad 上写入我的发现
- **优先级**: P0 (必须有)
- **用户故事**: 作为一名架构师 Worker，我在分析代码时发现了 N+1 查询问题，我希望将这个发现写入共享黑板，让其他角色也能看到。
- **验收标准 (AC)**:
  - [ ] AC-1.1.1: 可以创建包含 worker_id、role_id、content、confidence 的条目
  - [ ] AC-1.1.2: 条目自动获得唯一 entry_id 和时间戳
  - [ ] AC-1.1.3: 条目支持标签(tags)用于分类检索
  - [ ] AC-1.1.4: 写入后可以通过 entry_id 检索到该条目
- **场景示例**:
  ```
  场景: 架构师写入性能发现
    Given 一个空的 Scratchpad
    And 架构师 Worker "arch-1"
    When 写入一条 FINDING 类型的条目，内容为"数据库查询存在N+1问题"，置信度0.9
    Then 返回有效的 entry_id
    And 条目的 worker_id 为 "arch-1"
    And 条目的 confidence 为 0.9
  ```

#### US-1.2: 作为 Worker，我希望按条件读取 Scratchpad 上的相关条目
- **优先级**: P0 (必须有)
- **用户故事**: 作为测试者 Worker，我想查看架构师最近写的关于"性能"相关的发现，以便我针对性地设计测试用例。
- **验收标准 (AC)**:
  - [ ] AC-1.2.1: 支持关键词全文搜索(query)
  - [ ] AC-1.2.2: 支持按类型过滤(FINDING/DECISION/CONFLICT/QUESTION等)
  - [ ] AC-1.2.3: 支持按状态过滤(ACTIVE/RESOLVED/SUPERSEDED)
  - [ ] AC-1.2.4: 支持按 Worker 过滤
  - [ ] AC-1.2.5: 支持按标签过滤
  - [ ] AC-1.2.6: 支持限制返回数量(limit)
  - [ ] AC-1.2.7: 支持按时间范围过滤(since)
- **场景示例**:
  ```
  场景: 测试者搜索性能相关问题
    Given Scratchpad 中有 10 条不同类型的条目
    And 其中 3 条包含"性能"关键词
    When 按 query="性能" 搜索
    Then 返回恰好 3 条匹配结果
    And 结果按时间倒序排列
  ```

#### US-1.3: 作为 Worker，我希望标记已解决的问题
- **优先级**: P0 (必须有)
- **用户故事**: 作为开发者 Worker，我看到架构师标记了一个"N+1查询"问题，我修复了它并添加了缓存层，希望将这个问题标记为已解决。
- **验收标准 (AC)**:
  - [ ] AC-1.3.1: 可以通过 entry_id 将条目标记为 RESOLVED
  - [ ] AC-1.3.2: 解决时可以附加解决方案说明
  - [ ] AC-1.3.3: 已解决的条目内容会追加 [RESOLVED] 标记
  - [ ] AC-1.3.4: 版本号自增
- **场景示例**:
  ```
  场景: 开发者解决问题
    Given 存在一个 ACTIVE 状态的 FINDING 条目，entry_id 为 "entry-abc123"
    When 调用 resolve("entry-abc123", resolution="已添加Redis缓存")
    Then 该条目状态变为 RESOLVED
    And 内容末尾附加 "[RESOLVED] 已添加Redis缓存"
  ```

#### US-1.4: 作为 Worker，我希望查看活跃的冲突列表
- **优先级**: P1 (应该有)
- **用户故事**: 作为 PM Worker，我想快速看到当前有哪些未解决的冲突，以便组织讨论。
- **验收标准 (AC)**:
  - [ ] AC-1.4.1: get_conflicts() 返回所有 CONFLICT 类型且状态为 ACTIVE 的条目
  - [ ] AC-1.4.2: 无冲突时返回空列表
- **场景示例**:
  ```
  场景: PM 查看冲突列表
    Given Scratchpad 中有 2 个 CONFLICT 类型的 ACTIVE 条目
    And 有 1 个已 RESOLVED 的 CONFLICT 条目
    When 调用 get_conflicts()
    Then 返回 2 个活跃冲突
    And 不包含已解决的冲突
  ```

#### US-1.5: 作为系统使用者，我希望获取 Scratchpad 的统计摘要
- **优先级**: P1 (应该有)
- **用户故事**: 作为项目负责人，我想了解 Scratchpad 上目前有多少条目、各类型分布如何、哪些 Worker 最活跃。
- **验收标准 (AC)**:
  - [ ] AC-1.5.1: get_stats() 返回总条目数、按类型统计、按状态统计、按 Worker 统计
  - [ ] AC-1.5.2: get_summary() 返回人类可读的 Markdown 格式摘要
  - [ ] AC-1.5.3: 摘要包含关键发现、决策、冲突的分类展示
- **场景示例**:
  ```
  场景: 获取统计摘要
    Given Scratchpad 中有 15 个 FINDING, 3 个 DECISION, 2 个 CONFLICT
    When 调用 get_summary()
    Then 返回 Markdown 格式文本
    And 包含 "Key Findings (15)" 章节
    And 包含 "Active Conflicts (2)" 章节
  ```

#### US-1.6: 作为系统使用者，我希望 Scratchpad 能持久化数据
- **优先级**: P1 (应该有)
- **用户故事**: 作为项目负责人，如果协作过程中断，我不希望丢失已经产生的发现和决策。
- **验收标准 (AC)**:
  - [ ] AC-1.6.1: 提供 persist_dir 参数启用持久化
  - [ ] AC-1.6.2: 数据以 JSONL 格式追加写入文件
  - [ ] AC-1.6.3: 重启后可以从文件恢复数据
  - [ ] AC-1.6.4: 持久化失败不影响内存操作
- **场景示例**:
  ```
  场景: 数据持久化与恢复
    Given 创建 Scratchpad 时指定 persist_dir="/tmp/test_sp"
    And 写入 5 条条目
    When 销毁并重新创建 Scratchpad(同一 persist_dir)
    Then 自动加载之前的 5 条条目
    And 总条目数仍为 5
  ```

#### US-1.7: 作为系统使用者，我希望 Scratchpad 能处理大量数据
- **优先级**: P2 (可以有)
- **用户故事**: 在长时间运行的大型项目中，Scratchpad 可能积累上千条记录。当达到容量上限时，应自动淘汰旧数据。
- **验收标准 (AC)**:
  - [ ] AC-1.7.1: 默认上限 1000 条
  - [ ] AC-1.7.2: 达到上限时触发 LRU 淘汰
  - [ ] AC-1.7.3: 优先淘汰已 RESOLVED 的旧条目
  - [ ] AC-1.7.4: 没有已解决条目时淘汰最旧的条目
- **场景示例**:
  ```
  场景: 容量满时自动淘汰
    Given Scratchpad 最大容量为 1000
    And 当前已有 999 条 RESOLVED 条目 和 1 条 ACTIVE 条目
    When 写入第 1001 条新条目
    Then 自动淘汰最旧的 RESOLVED 条目
    And 总条目数为 1000
  ```

---

### Epic 2: Worker 工作者

#### US-2.1: 作为系统使用者，我希望创建具有特定角色的 Worker
- **优先级**: P0 (必须有)
- **用户故事**: 作为项目负责人，我需要创建一个扮演"架构师"角色的 Worker，让它按照架构师的思维方式来分析任务。
- **验收标准 (AC)**:
  - [ ] AC-2.1.1: 创建时指定 worker_id、role_id、role_prompt、scratchpad
  - [ ] AC-2.1.2: Worker 正确保存所有初始化参数
  - [ ] AC-2.1.3: WorkerFactory 可批量创建多个 Worker
- **场景示例**:
  ```
  场景: 创建单个 Worker
    Given 一个 Scratchpad 实例
    When 创建 Worker(worker_id="w1", role_id="architect", role_prompt="你是资深架构师...", scratchpad=sp)
    Then Worker 的 worker_id 为 "w1"
    And Worker 的 role_id 为 "architect"
    And Worker 关联到正确的 Scratchpad
  ```

#### US-2.2: 作为 Worker，我希望执行任务并输出结果
- **优先级**: P0 (必须有)
- **用户故事**: 作为架构师 Worker，我收到一个"设计用户认证模块"的任务，我需要分析任务上下文并输出我的发现。
- **验收标准 (AC)**:
  - [ ] AC-2.2.1: execute() 方法接收 TaskDefinition 并返回 WorkerResult
  - [ ] AC-2.2.2: 成功时 success=True，包含 output 和 duration_seconds
  - [ ] AC-2.2.3: 失败时 success=False，包含 error 信息
  - [ ] AC-2.2.4: 执行过程中自动将发现写入 Scratchpad
  - [ ] AC-2.2.5: 执行前会读取 Scratchpad 上的相关发现作为上下文
- **场景示例**:
  ```
  场景: 成功执行任务
    Given 架构师 Worker "w1"
    And 任务描述为 "设计用户认证模块的架构"
    When 执行该任务
    Then 返回 WorkerResult(success=True)
    And result.worker_id == "w1"
    And result.duration_seconds > 0
    And Scratchpad 上新增至少 1 条 FINDING
  ```

#### US-2.3: 作为 Worker，我希望向其他角色提问
- **优先级**: P0 (必须有)
- **用户故事**: 作为 UI 设计师 Worker，我不确定某个 API 是否需要版本控制，希望向产品经理提问并获得回复。
- **验收标准 (AC)**:
  - [ ] AC-2.3.1: write_question() 创建 QUESTION 类型条目
  - [ ] AC-2.3.2: 同时生成 TaskNotification 发送给指定角色
  - [ ] AC-2.3.3: 通知包含问题摘要和详情
  - [ ] AC-2.3.4: 对方可以通过 get_pending_notifications() 获取通知
- **场景示例**:
  ```
  场景: Worker 间问答交互
    Given 架构师 Worker "w1" 和 PM Worker "w2"
    When w1 调用 write_question("这个API是否需要版本控制？", to_roles=["product-manager"])
    Then Scratchpad 新增 1 条 QUESTION 类型条目
    And w2.get_pending_notifications() 包含 1 条 question 类型通知
    And 通知的 to_workers 包含 "product-manager"
  ```

#### US-2.4: 作为 Worker，我希望报告发现的冲突
- **优先级**: P1 (应该有)
- **用户故事**: 作为安全专家 Worker，我发现架构师提出的方案存在安全隐患，需要将此作为冲突记录下来。
- **验收标准 (AC)**:
  - [ ] AC-2.4.1: write_conflict() 创建 CONFLICT 类型条目
  - [ ] AC-2.4.2: 冲突条目关联被冲突的目标条目 ID
  - [ ] AC-2.4.3: 冲突条目包含冲突原因说明
- **场景示例**:
  ```
  场景: 报告冲突
    Given 安全专家 Worker "sec-1"
    And 架构师的某条建议 entry_id 为 "entry-xyz"
    When sec-1 调用 write_conflict("方案A存在SQL注入风险", conflicting_entry_id="entry-xyz", reason="未使用参数化查询")
    Then 新增 CONFLICT 类型条目
    And 条目 tags 包含 "entry-xyz"
  ```

#### US-2.5: 作为 Worker，我希望参与投票决策
- **优先级**: P1 (应该有)
- **用户故事**: 作为架构师 Worker，PM 提出了一个技术方案提案，我希望根据我的专业知识投出赞成或反对票。
- **验收标准 (AC)**:
  - [ ] AC-2.5.1: vote_on_proposal() 生成带权重的 Vote 对象
  - [ ] AC-2.5.2: 投票权重根据 ROLE_WEIGHTS 配置自动确定
  - [ ] AC-2.5.3: 架构师权重 1.5x，PM 权重 1.2x，其他 1.0x
  - [ ] AC-2.5.4: 支持 veto（weight < 0）触发升级
- **场景示例**:
  ```
  场景: 架构师投出加权票
    Given 架构师 Worker "arch-1"
    When arch-1 调用 vote_on_proposal("prop-001", decision=True, reason="技术可行")
    Then Vote.weight == 1.5 (架构师权重)
    And Vote.decision == True
    And Vote.voter_role == "architect"
  ```

---

### Epic 3: Consensus 共识引擎

#### US-3.1: 作为 Coordinator，我希望发起决策提案
- **优先级**: P0 (必须有)
- **用户故事**: 当多个 Worker 对同一个问题有不同意见时，Coordinator 需要发起一个正式的投票提案来达成共识。
- **验收标准 (AC)**:
  - [ ] AC-3.1.1: create_proposal() 生成唯一的 proposal_id
  - [ ] AC-3.1.2: 提案包含 topic、proposer_id、proposal_content
  - [ ] AC-3.1.3: 提案初始状态为 "open"
  - [ ] AC-3.1.4: 可以设置可选选项(options)和截止时间(deadline)
- **场景示例**:
  ```
  场景: 发起投票提案
    Given ConsensusEngine 实例
    When create_proposal(topic="是否采用微服务架构", proposer_id="coord-1", content="...")
    Then 返回 DecisionProposal
    And proposal.proposal_id 以 "prop-" 开头
    And proposal.status == "open"
  ```

#### US-3.2: 作为 Worker，我希望对提案进行投票
- **优先级**: P0 (必须有)
- **用户故事**: 各个 Worker 根据自己的专业判断对提案进行投票。
- **验收标准 (AC)**:
  - [ ] AC-3.2.1: cast_vote() 向指定提案添加投票
  - [ ] AC-3.2.2: 非 open 状态的提案拒绝接受新投票
  - [ ] AC-3.2.3: 同一 Worker 可多次投票（模拟多轮讨论）
- **场景示例**:
  ```
  场景: 多人投票
    Given 提案 "prop-001" 处于 open 状态
    When 架构师投赞成票(weight=1.5) 和 PM 投赞成票(weight=1.2)
    Then 提案的 votes 列表包含 2 个 Vote
    And 提案状态仍为 open
  ```

#### US-3.3: 作为系统使用者，我希望系统能自动判定共识结果
- **优先级**: P0 (必须有)
- **用户故事**: 当所有角色都投票完毕后，系统应根据权重和规则自动判定是否通过。
- **验收标准 (AC)**:
  - [ ] AC-3.3.1: reach_consensus() 返回 ConsensusRecord
  - [ ] AC-3.3.2: 权重占比 > 51% → APPROVED (简单多数)
  - [ ] AC-3.3.3: 权重占比 > 67% → APPROVED (绝对多数)
  - [ ] AC-3.3.3: 存在否决票(weight < 0) → ESCALATED (升级人工)
  - [ ] AC-3.3.4: 赞成率 40%-60% 且未达门槛 → SPLIT (意见分裂)
  - [ ] AC-3.3.5: 零投票 → TIMEOUT
  - [ ] AC-3.3.6: 达成共识后提案状态变为 "closed"
- **场景示例**:
  ```
  场景: 权重多数通过
    Given 提案收到 2 票赞成(权重 1.5+1.2=2.7), 0 票反对
    When reach_consensus()
    Then outcome == DecisionOutcome.APPROVED
    And votes_for == 2
    And total_weight_for == 2.7
  ```

#### US-3.4: 作为安全关注者，我希望否决权能正确触发升级
- **优先级**: P1 (应该有)
- **用户故事**: 当安全问题被提出时，即使大多数人都同意，安全专家的一票否决也应该触发升级流程。
- **验收标准 (AC)**:
  - [ ] AC-3.4.1: weight < 0 的投票被视为否决(veto)
  - [ ] AC-3.4.2: 任何否决票都导致 outcome = ESCALATED
  - [ ] AC-3.4.3: escalation_reason 记录否决详情
- **场景示例**:
  ```
  场景: 否决权触发升级
    Given 提案收到 1 票赞成(weight=1.0) 和 1 票否决(weight=-1.0, reason="安全风险")
    When reach_consensus()
    Then outcome == DecisionOutcome.ESCALATED
    And escalation_reason 包含 "Veto"
    And final_decision 包含反对权重信息
  ```

---

### Epic 4: Coordinator 协调者

#### US-4.1: 作为项目负责人，我希望一键规划多角色协作任务
- **优先级**: P0 (必须有)
- **用户故事**: 我输入任务描述和需要的角色列表，系统自动生成执行计划，将任务分配给每个角色。
- **验收标准 (AC)**:
  - [ ] AC-4.1.1: plan_task() 根据 role 列表生成 ExecutionPlan
  - [ ] AC-4.1.2: 多角色默认采用 PARALLEL 并行模式
  - [ ] AC-4.1.3: plan.total_tasks == len(available_roles)
  - [ ] AC-4.1.4: 每个 TaskDefinition 都携带正确的 role_id 和 stage_id
- **场景示例**:
  ```
  场景: 规划 3 角色并行任务
    Given Coordinator 实例
    When plan_task("设计电商系统", [{"role_id":"architect"}, {"role_id":"tester"}, {"role_id":"pm"}])
    Then 返回 ExecutionPlan
    And plan.total_tasks == 3
    And plan.batches[0].mode == BatchMode.PARALLEL
  ```

#### US-4.2: 作为项目负责人，我希望自动创建对应的 Workers
- **优先级**: P0 (必须有)
- **用户故事**: 规划完成后，系统应为每个角色自动创建一个 Worker 实例。
- **验收标准 (AC)**:
  - [ ] AC-4.2.1: spawn_workers() 为每个任务创建 Worker
  - [ ] AC-4.2.2: Worker 数量等于计划中的任务数
  - [ ] AC-4.2.3: 所有 Worker 共享同一个 Scratchpad
  - [ ] AC-4.2.4: 如果提供了 PromptRegistry，Worker 自动加载对应角色的 prompt
- **场景示例**:
  ```
  场景: 批量创建 Workers
    Given ExecutionPlan 包含 3 个任务(architect, tester, pm)
    When spawn_workers(plan)
    Then 返回 3 个 Worker 实例
    And coord.workers 字典包含 3 个条目
    And 所有 Worker 的 scratchpad 是同一个对象
  ```

#### US-4.3: 作为项目负责人，我希望一键执行完整协作流程
- **优先级**: P0 (必须有)
- **用户故事**: 点击"执行"，所有 Worker 开始工作，完成后收集结果。
- **验收标准 (AC)**:
  - [ ] AC-4.3.1: execute_plan() 依次执行所有 batch
  - [ ] AC-4.3.2: PARALLEL batch 中所有任务并发执行
  - [ ] AC-4.3.3: SERIAL batch 中任务串行执行
  - [ ] AC-4.3.4: 返回 ScheduleResult，包含成功/失败统计
  - [ ] AC-4.3.5: 记录执行耗时
- **场景示例**:
  ```
  场景: 执行 5 角色协作
    Given 已规划并创建了 5 个 Worker
    When execute_plan(plan)
    Then result.completed_tasks == 5
    And result.success == True
    And result.duration_seconds > 0
  ```

#### US-4.4: 作为项目负责人，我希望收集完整的协作结果
- **优先级**: P0 (必须有)
- **用户故事**: 执行完成后，我想看到一个汇总：有多少发现、多少决策、多少冲突、Worker 间发了什么消息。
- **验收标准 (AC)**:
  - [ ] AC-4.4.1: collect_results() 返回结构化的结果字典
  - [ ] AC-4.4.2: 包含 scratchpad 摘要和统计数据
  - [ ] AC-4.4.3: 包含 findings_count / decisions_count / conflicts_count
  - [ ] AC-4.4.4: 包含所有 Worker 的 pending notifications
- **场景示例**:
  ```
  场景: 收集结果
    Given 5 个 Worker 已完成执行，产生了若干发现和消息
    When collect_results()
    Then 返回字典包含 "coordinator_id", "scratchpad", "findings_count" 等键
    And findings_count >= 5 (每个 Worker 至少产生 1 条)
  ```

#### US-4.5: 作为项目负责人，我希望自动解决冲突并生成报告
- **优先级**: P1 (应该有)
- **用户故事**: 如果 Worker 之间产生了冲突，系统应尝试通过共识机制解决，最终生成一份完整的协作报告。
- **验收标准 (AC)**:
  - [ ] AC-4.5.1: resolve_conflicts() 对每个冲突发起投票
  - [ ] AC-4.5.2: 冲突解决后将对应条目标记为 RESOLVED
  - [ ] AC-4.5.3: generate_report() 输出 Markdown 格式的完整报告
  - [ ] AC-4.5.4: 报告包含参与者、耗时、发现/决策/冲突统计、消息记录、共识记录
- **场景示例**:
  ```
  场景: 生成协作报告
    Given 完整的协作流程已执行
    When generate_report()
    Then 返回字符串长度 > 200
    And 包含 "协作报告" 标题
    And 包含 "Worker"、"Scratchpad"、"共识" 等章节
  ```

---

### Epic 5: BatchScheduler 批处理调度器

#### US-5.1: 作为系统使用者，我希望支持并行和串行两种调度模式
- **优先级**: P1 (应该有)
- **用户故事**: 有些任务可以同时做（如分析和评审），有些必须顺序做（如先设计再开发再测试）。调度器应支持这两种模式。
- **验收标准 (AC)**:
  - [ ] AC-5.1.1: BatchMode.PARALLEL 表示并行执行
  - [ ] AC-5.1.2: BatchMode.SERIAL 表示串行执行
  - [ ] AC-5.1.3: schedule() 接受多个 TaskBatch，按依赖关系排序执行
- **场景示例**:
  ```
  场景: 混合模式调度
    Given Batch 1: PARALLEL, 2 个任务(架构分析 + UI 设计)
    And Batch 2: SERIAL, 1 个任务(开发实现, 依赖 Batch 1)
    When schedule([batch1, batch2], workers)
    Then 先并行执行 Batch 1 的 2 个任务
    再串行执行 Batch 2 的 1 个任务
  ```

---

## 四、边界场景与非功能需求

### 4.1 异常场景

| 编号 | 场景 | 期望行为 |
|------|------|---------|
| E-01 | Scratchpad 写入空内容条目 | 正常写入，content 为空字符串 |
| E-02 | 查询不存在的 entry_id | read 返回空列表，resolve 静默忽略 |
| E-03 | Worker 执行抛出异常 | 返回 WorkerResult(success=False, error=异常信息) |
| E-04 | 对已关闭的提案投票 | 抛出 ValueError |
| E-05 | 持久化目录无写权限 | 静默失败，内存操作正常 |
| E-06 | Scratchpad 容量为 0 或负数 | 使用默认值 1000 |
| E-07 | 创建 Worker 时 scratchpad 为 None | 抛出 TypeError |
| E-08 | 并发写入同一条目 | 版本号递增，最后写入胜出(LWW) |

### 4.2 性能需求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 单次写入延迟 | < 1ms | 内存操作 |
| 单次查询延迟 | < 5ms | 全文扫描 1000 条以内 |
| 10 Worker 并发执行 | < 500ms | 不含实际 AI 推理时间 |
| Scratchpad 容量 | 1000 条默认 | 可配置 |
| JSONL 持久化吞吐 | > 1000 条/秒 | 追加写入 |

### 4.3 安全需求

| 需求 | 说明 |
|------|------|
| 数据隔离 | 不同 Coordinator 实例的 Scratchpad 互相隔离 |
| 线程安全 | Scratchpad 的读写操作使用 RLock 保护 |
| 输入校验 | 关键参数有类型检查 |

---

## 五、用户旅程 (User Journey)

### 旅程 A: 完整的多角色协作（主流程）

```
项目负责人李明
  │
  ├─ 1. 创建 Coordinator
  │     coord = Coordinator()
  │
  ├─ 2. 规划任务（5 个角色）
  │     plan = coord.plan_task("设计在线教育平台认证系统",
  │       [architect, pm, tester, ui-designer, solo-coder])
  │
  ├─ 3. 创建 Workers
  │     workers = coord.spawn_workers(plan)
  │     → 5 个 Worker 就绪，共享 Scratchpad
  │
  ├─ 4. 执行计划
  │     result = coord.execute_plan(plan)
  │     → 每个 Worker 分析任务，写入发现到 Scratchpad
  │     → Worker 间可能产生问题和通知
  │
  ├─ 5. 收集结果
  │     collection = coord.collect_results()
  │     → 看到 5+ 条发现，可能有冲突和消息
  │
  ├─ 6. 解决冲突（如有）
  │     resolutions = coord.resolve_conflicts()
  │     → 对每个冲突发起投票，自动/升级解决
  │
  └─ 7. 生成报告
        report = coord.generate_report()
        → 完整的 Markdown 协作报告
```

### 旅程 B: 仅使用 Scratchpad 进行信息交换（轻量场景）

```
开发者张华
  │
  ├─ 1. 创建 Scratchpad
  │     sp = Scratchpad(persist_dir="./data/collab")
  │
  ├─ 2. Worker A 写入发现
  │     sp.write(ScratchpadEntry(..., content="发现API响应慢"))
  │
  ├─ 3. Worker B 读取并补充
  │     findings = sp.read(query="API")
  │     sp.write(ScratchpadEntry(..., content="建议添加缓存层",
  │       references=[Reference(SUPPORTS, entry_id_a, "...")]))
  │
  └─ 4. 标记解决
        sp.resolve(entry_id_a, resolution="已添加 Redis 缓存")
```

### 旅程 C: 仅使用共识引擎进行决策（独立场景）

```
团队决策
  │
  ├─ 1. 创建提案
  │     prop = ce.create_proposal("是否升级到 Python 3.12?", "tech-lead", "理由...")
  │
  ├─ 2. 各角色投票
  │     ce.cast_vote(prop.id, Vote(arch=True, w=1.5))
  │     ce.cast_vote(prop.id, Vote(pm=True, w=1.2))
  │     ce.cast_vote(prop.id, Vote(dev=False, w=1.0))
  │
  └─ 3. 判定结果
        record = ce.reach_consensus(prop.id)
        → APPROVED (2.7 vs 1.0, 权重比 73% > 51%)
```

---

## 六、验收标准总表

| Epic | 用户故事数 | P0 | P1 | P2 | 合计 |
|------|----------|----|----|----|-----|
| Epic 1: Scratchpad | 7 | 4 | 2 | 1 | 7 |
| Epic 2: Worker | 5 | 3 | 2 | 0 | 5 |
| Epic 3: Consensus | 4 | 3 | 1 | 0 | 4 |
| Epic 4: Coordinator | 5 | 4 | 1 | 0 | 5 |
| Epic 5: BatchScheduler | 1 | 0 | 1 | 0 | 1 |
| **合计** | **22** | **14** | **7** | **1** | **22** |
