# P2-b: Skillify 技能自动生成 — 用户故事与场景

**版本**: v1.0
**日期**: 2026-04-15
**作者**: 产品经理 (PM Role)
**基于**: v3-phase2-skillify-design.md

---

## 用户画像

### 用户A: 高级使用者
- 经常使用系统完成复杂多步骤任务
- 希望重复性工作能自动转化为可复用 Skill
- 关注新 Skill 的质量和安全性

### 用户B: 平台管理员
- 管理团队共享的 Skill 库
- 需要审核自动生成的 Skill
- 关注 Skill 的可追溯性和来源

### 用户C: 新手用户
- 不熟悉所有可用功能
- 希望系统能推荐合适的 Skill
- 依赖高质量 Skill 提升工作效率

---

## Epic 1: 执行记录采集

### US-1.1: 作为系统，我希望每次任务执行完成后自动记录 ExecutionRecord
**优先级**: P0 | **复杂度**: 低

**验收标准 (AC)**:
- [ ] Coordinator 完成任务后自动调用 `record_execution()`
- [ ] ExecutionRecord 包含 task_description, worker_id, steps, success
- [ ] 每个步骤包含 action_type, target, outcome, duration_ms
- [ ] 失败的任务也被记录（success=False）

**场景**:
```
场景 1.1.1: 成功任务记录
  Given Worker 成功完成 "设计用户认证系统" 任务(5步)
  When 任务完成
  Then ExecutionRecord.success == True
  And len(steps) == 5
  And 每步 outcome == "success"

场景 1.1.2: 失败任务记录
  Given Worker 执行任务时第3步失败
  When 任务结束
  Then ExecutionRecord.success == False
  And steps[2].outcome == "error"
```

---

### US-1.2: 作为用户，我希望能手动添加执行记录
**优先级**: P1 | **复杂度**: 低

**验收标准 (AC)**:
- [ ] `record_execution()` 支持手动传入 ExecutionRecord
- [ ] 手动记录和自动记录存储在同一库中

---

## Epic 2: 模式提取与分析

### US-2.1: 作为系统，我希望从历史记录中自动提取成功模式
**优先级**: P0 | **复杂度**: 中

**用户故事**:
> 当系统中积累了足够的成功执行记录（>=5条）时，我希望系统能自动分析这些记录，识别出重复出现的操作模式。这样我就能发现哪些任务流程是可以标准化和复用的。

**验收标准 (AC)**:
- [ ] `analyze_history()` 返回 SuccessPattern 列表
- [ ] 每个 Pattern 有 pattern_id, name, steps_template
- [ ] Pattern 包含 trigger_keywords 和 confidence
- [ ] 只从 success=True 的记录中提取模式
- [ ] frequency >= 2 的模式才会被提取

**场景**:
```
场景 2.1.1: 基本模式提取
  Given 10条成功的"Python项目初始化"执行记录(每条4-6步)
  When 调用 analyze_history()
  Then 返回 >= 1 个 SuccessPattern
  And pattern.name 包含 "python" 或 "init"
  And pattern.frequency >= 3

场景 2.1.2: 不同任务不混淆
  Given 5条"代码审查" + 5条"部署上线"的混合记录
  When analyze_history()
  Then 返回至少2个不同类别的Pattern
  And 各Pattern.trigger_keywords 明显不同
```

---

### US-2.2: 作为系统，我希望模式泛化正确处理具体值
**优先级**: P0 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] 具体文件名 → `*.{ext}` 泛化
- [ ] 具体目录 → `{dir}/**` 泛化
- [ ] 时间戳/随机ID → 占位符泛化
- [ ] 步骤描述中的具体值保留模板变量

**场景**:
```
场景 2.2.1: 文件名泛化
  Given 记录中 target="src/utils/helper.py"
  When 模式提取泛化后
  Then target_pattern="*.py" 或 "**/*.py"

场景 2.2.2: 目录结构保留
  Given 记录中 target="src/core/engine.py"
  When 泛化
  Then target_pattern 仍包含目录层级信息

场景 2.2.3: 时间戳替换
  Given 记录中 target="report_20260415_143022.md"
  When 泛化
  Then target_pattern 包含通配符或占位符
```

---

### US-2.3: 作为用户，我希望能看到模式库统计信息
**优先级**: P1 | **复杂度**: 低

**验收标准 (AC)**:
- [ ] `get_statistics()` 返回总记录数、总模式数、平均置信度
- [ ] `get_pattern_library()` 返回所有已发现模式
- [ ] `export_patterns()` 输出 JSON 格式

---

## Epic 3: Skill 自动生成

### US-3.1: 作为系统，我希望从模式自动生成 SkillProposal
**优先级**: P0 | **复杂度**: 高

**用户故事**:
> 当系统发现一个高置信度的成功模式后，我希望它能自动生成一份完整的 Skill 提案，包含名称、描述、触发条件、步骤定义、输入输出 Schema 和验收标准。这样我可以快速评审并决定是否发布。

**验收标准 (AC)**:
- [ ] `generate_skill(pattern)` 返回 SkillProposal
- [ ] Proposal 包含 name, slug, version, description
- [ ] Proposal.steps 从 pattern.steps_template 映射而来
- [ ] Proposal.trigger_conditions 来自 pattern.trigger_keywords
- [ ] Proposal.quality_score 有初始值（基于模式置信度）
- [ ] Proposal.status == DRAFT

**场景**:
```
场景 3.1.1: 基本生成
  Given 一个 frequency=5, confidence=0.85 的 SuccessPattern
  When generate_skill(pattern)
  Then 返回 SkillProposal
  And proposal.name != ""
  And len(proposal.steps) == len(pattern.steps_template)
  And proposal.status == ProposalStatus.DRAFT

场景 3.1.2: slug 自动生成
  Given pattern.name = "Python Project Initialization"
  When 生成 proposal
  Then proposal.slug == "python-project-initialization"
```

---

### US-3.2: 作为系统，我希望生成的 Skill 能自动分类
**优先级**: P1 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] 主要操作是文件创建/修改 → category = "code-generation"
- [ ] 包含测试相关关键词 → category = "testing"
- [ ] 包含部署/发布关键词 → category = "deployment"
- [ ] 无法明确分类 → category = "auto-generated"

---

## Epic 4: 质量验证

### US-4.1: 作为系统，我希望对生成的 Skill 进行五维质量评分
**优先级**: P0 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] `validate_skill(proposal)` 返回 ValidationResult
- [ ] 结果包含 score (0-100), completeness, specificity, repeatability, safety
- [ ] 结果包含 issues 列表和 suggestions 列表
- [ ] 五维分数都在 [0, 100] 区间内

**场景**:
```
场景 4.1.1: 完美Skill高分
  Given 一个步骤完整(10步)、无高风险操作、3次以上成功复现的Proposal
  When validate_skill()
  Then result.score >= 80
  And result.safety >= 90

场景 4.1.2: 缺陷Skill低分
  Given 一个只有1步、或包含BYPASS操作的Proposal
  When validate_skill()
  Then result.score < 55
  And issues 包含相关问题说明
```

---

### US-4.2: 作为系统，我希望质量分级(A/B/C/D)正确
**优先级**: P0 | **复杂度**: 低

**验收标准 (AC)**:
- [ ] score >= 85 → A (优秀)
- [ ] 70 <= score < 85 → B (良好)
- [ ] 55 <= score < 70 → C (合格)
- [ ] score < 55 → D (不合格)

---

### US-4.3: 作为系统，我希望自动拒绝明显不合格的Skill
**优先级**: P0 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] 步骤数 = 0 或 > 20 → 自动 D
- [ ] 包含 BYPASS 操作 → 自动 D 或 safety 极低
- [ ] 触发条件 < 3 个关键词 → completeness 扣分
- [ ] 所有来源记录来自同一任务 → repeatability 扣分

---

## Epic 5: 发布与集成

### US-5.1: 作为用户，我希望批准后 Skill 能发布到 Registry
**优先级**: P0 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] `approve_and_publish(proposal_id)` 将 Skill 写入 Registry
- [ ] 发布后 proposal.status == PUBLISHED
- [ ] 发布后 proposal.published_at 有时间戳
- [ ] 已发布的 Skill 可通过 Registry.query() 发现

**场景**:
```
场景 5.1.1: 正常发布流程
  Given 一个 status=APPROVED 的 Proposal
  When approve_and_publish(proposal_id)
  Then 返回 True
  And Registry 中可查询到该 Skill
  And Skill.version == "1.0.0"

场景 5.1.2: 重复发布检测
  Given 同名 Skill 已存在于 Registry
  When 再次 approve_and_publish
  Then 版本号递增为 "1.1.0" 或返回冲突提示
```

---

### US-5.2: 作为用户，我希望能为新任务推荐合适的 Skill
**优先级**: P1 | **复杂度**: 中

**验收标准 (AC)**:
- [ ] `suggest_skills_for_task("设计API接口")` 返回匹配列表
- [ ] 返回结果按相关性排序
- [ ] 无匹配时返回空列表而非报错

**场景**:
```
场景 5.2.1: 关键词匹配
  Given Registry中有 "api-design" 和 "code-review" 两个Skill
  When suggest_skills_for_task("帮我设计RESTful API")
  Then "api-design" 排在第一位
  And "code-review" 可能也在列表中(相关性较低)
```

---

## 边界场景清单

| # | 场景 | 预期行为 |
|---|------|---------|
| BS-01 | 空历史记录 analyze | 返回空列表，不崩溃 |
| BS-02 | 单条记录无法形成模式 | 返回空列表 |
| BS-03 | 所有记录都是失败的 | 不生成任何Pattern |
| BS-04 | 极长步骤序列(50+步) | 正常处理，可能被验证拒绝 |
| BS-05 | 特殊字符在target路径 | 泛化和匹配正常工作 |
| BS-06 | 并发 analyze_history 调用 | 线程安全，结果一致 |
| BS-07 | 循环依赖(A→B→A) | 检测到循环，打破依赖 |

---

## 用户旅程示例

### 旅程A: 首次 Skill 发现
```
1. 用户使用系统完成了 8 次"Python项目初始化"(每次都成功)
2. 系统后台累计到第5次成功时触发 analyze_history()
3. 发现一个 pattern: frequency=5, confidence=0.88
4. 自动生成 SkillProposal: "Python Project Setup"
5. validate_score = 92 (A级)
6. 系统通知用户: "发现可复用技能「Python Project Setup」"
7. 用户查看详情后点击确认
8. Skill 发布到 Registry
9. 下次用户说"新建一个Python项目" → 自动匹配该 Skill ✅
```

### 旅程B: 质量改进循环
```
1. 系统生成一个 SkillProposal "Quick Deploy", score=58 (C级)
2. validate_result.issues = ["步骤过于简略(仅2步)", "缺少回滚方案"]
3. 用户选择"改进而非丢弃"
4. 系统建议: 增加预检查步骤、增加健康验证步骤
5. 改进后重新验证 score=76 (B级)
6. 用户批准发布
```

---

## 验收标准总表

| ID | 故事 | 优先级 | AC数量 | 状态 |
|-----|------|--------|--------|------|
| US-1.1 | 自动记录执行 | P0 | 5 | ⬜ |
| US-1.2 | 手动添加记录 | P1 | 2 | ⬜ |
| US-2.1 | 模式提取 | P0 | 5 | ⬜ |
| US-2.2 | 模式泛化 | P0 | 4 | ⬜ |
| US-2.3 | 统计信息 | P1 | 3 | ⬜ |
| US-3.1 | Skill自动生成 | P0 | 6 | ⬜ |
| US-3.2 | 自动分类 | P1 | 4 | ⬜ |
| US-4.1 | 五维质量评分 | P0 | 5 | ⬜ |
| US-4.2 | 质量分级 | P0 | 4 | ⬜ |
| US-4.3 | 自动拒绝规则 | P0 | 4 | ⬜ |
| US-5.1 | 发布到Registry | P0 | 5 | ⬜ |
| US-5.2 | 任务推荐Skill | P1 | 3 | ⬜ |
| **合计** | | | **54** | |
