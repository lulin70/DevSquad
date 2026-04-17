# P2-b: Skillify 技能自动生成系统 - 设计文档

**版本**: v1.0
**日期**: 2026-04-15
**状态**: 草案待评审
**基于**: v3-upgrade-proposal.md §2.5

---

## 1. 背景与动机

### 1.1 现状分析

当前 MultiAgentSkill 已具备：
- ✅ **SkillRegistry**: 技能注册/发现/版本管理（手动注册）
- ✅ **Coordinator + Workers**: 多 Agent 协作执行框架
- ✅ **PermissionGuard**: 操作权限控制
- ✅ **ContextCompressor**: 上下文压缩管理
- ✅ **完整执行历史**: WorkerResult + AuditEntry 记录每次操作

**关键差距**: 系统缺乏从成功执行中**自动提取可复用模式**的能力。每次复杂任务完成后，成功的操作序列只是被记录在日志中，无法自动转化为新的 Skill，导致重复劳动。

### 1.2 目标

构建 **Skillify 技能自动生成系统**，实现：

```
用户完成复杂任务 → 执行历史记录 → 模式识别与提取 → Skill草案生成
→ 质量验证 → 用户确认 → 发布到 SkillRegistry → 下次自动匹配复用
```

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **模式驱动** | 从真实成功案例中提取，非人工臆造 |
| **增量进化** | 新 Skill 基于已有 Skill 组合或扩展 |
| **质量门控** | 自动评分 + 用户确认双保险 |
| **可追溯** | 每个 Skill 可追溯其来源的执行记录 |
| **非侵入式** | 不影响正常协作流程，异步后台分析 |

---

## 2. 核心架构设计

### 2.1 数据流架构

```
┌──────────────────────────────────────────────────────┐
│                   Skillifier                          │
│                                                      │
│  ┌───────────┐    ┌───────────┐    ┌──────────────┐ │
│  │ Pattern   │───▶│  Skill    │───▶│   Skill      │ │
│  │ Extractor │    │ Generator │    │  Validator   │ │
│  └───────────┘    └───────────┘    └──────┬───────┘ │
│       ▲                                       │       │
│       │                                       ▼       │
│  ┌────┴──────┐                         ┌──────────┐  │
│  │ Execution │                         │  Skill    │  │
│  │ History   │                         │ Publisher │  │
│  │ (Input)   │                         └────┬─────┘  │
│  └───────────┘                              │        │
│                                             ▼        │
│                                    ┌──────────────────┐│
│                                    │  SkillRegistry   ││
│                                    │  (Existing System)││
│                                    └──────────────────┘│
└──────────────────────────────────────────────────────┘
```

### 2.2 核心数据模型

#### 2.2.1 ExecutionRecord — 执行记录

```python
@dataclass
class ExecutionRecord:
    record_id: str                           # 唯一ID
    task_description: str                    # 任务描述
    start_time: datetime                     # 开始时间
    end_time: datetime                       # 结束时间
    duration_seconds: float                  # 执行时长
    success: bool                            # 是否成功
    worker_id: str                           # 执行Worker
    role_id: str                             # 角色ID
    steps: List[ExecutionStep]              # 执行步骤列表
    results: List[WorkerResult]             # 结果列表
    artifacts: List[str]                    # 产出物路径
    metadata: Dict[str, Any]               # 额外元数据

@dataclass
class ExecutionStep:
    step_order: int                          # 步骤序号
    action_type: ActionType                # 操作类型 (from PermissionGuard)
    target: str                             # 操作目标
    description: str                        # 步骤描述
    outcome: str                             # 结果 (success/error/skipped)
    duration_ms: int                        # 耗时
    input_data: Optional[str] = None        # 输入数据摘要
    output_data: Optional[str] = None       # 输出数据摘要
```

#### 2.2.2 SuccessPattern — 成功模式

```python
@dataclass
class SuccessPattern:
    pattern_id: str                          # 模式ID
    name: str                                # 模式名称
    description: str                         # 描述
    source_records: List[str]               # 来源执行记录ID列表
    steps_template: List[PatternStep]       # 步骤模板(泛化后)
    trigger_keywords: List[str]             # 触发关键词
    applicable_roles: List[str]             # 适用角色
    frequency: int                          # 出现频次
    confidence: float                       # 置信度 [0.0-1.0]
    avg_success_rate: float                 # 平均成功率
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class PatternStep:
    action_type: ActionType                # 操作类型
    target_pattern: str                      # 目标模式(泛化,如 "*.py")
    description_template: str                # 描述模板
    is_required: bool = True                # 是否必需步骤
    estimated_risk: float = 0.0             # 预估风险分
```

#### 2.2.3 SkillProposal — 技能提案

```python
@dataclass
class SkillProposal:
    proposal_id: str                         # 提案ID
    name: str                                # Skill名称
    slug: str                                # URL友好标识
    version: str = "1.0.0"                   # 版本
    description: str                         # 描述
    category: str = "auto-generated"         # 分类
    trigger_conditions: List[str]           # 触发条件
    steps: List[SkillStepDef]              # 步骤定义
    required_roles: List[str]              # 需要的角色
    input_schema: Dict[str, Any]           # 输入Schema
    output_schema: Dict[str, Any]          # 输出Schema
    acceptance_criteria: List[str]         # 验收标准
    source_pattern: Optional[str] = None   # 来源模式ID
    quality_score: float = 0.0             # 质量评分 [0-100]
    validation_result: Optional[ValidationResult] = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    published_at: Optional[datetime] = None

class ProposalStatus(Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"

@dataclass
class ValidationResult:
    score: float                             # 总分 [0-100]
    completeness: float                      # 完整性 [0-100]
    specificity: float                       # 特异性 [0-100]
    repeatability: float                     # 可重复性 [0-100]
    safety: float                            # 安全性 [0-100]
    issues: List[str] = field(default_factory=list)  # 问题列表
    suggestions: List[str] = field(default_factory=list)  # 改进建议
```

### 2.3 核心组件：Skillifier

```python
class Skillifier:
    """技能自动生成器"""

    def __init__(self,
                 skill_registry: Optional['SkillRegistry'] = None,
                 min_pattern_occurrences: int = 2,
                 min_confidence: float = 0.6,
                 auto_analyze: bool = True):

    def record_execution(self, record: ExecutionRecord) -> None:
        """记录一次执行"""

    def analyze_history(self, since: datetime = None,
                       until: datetime = None) -> List[SuccessPattern]:
        """分析历史执行记录，提取成功模式"""

    def generate_skill(self, pattern: SuccessPattern) -> SkillProposal:
        """从模式生成Skill提案"""

    def validate_skill(self, proposal: SkillProposal) -> ValidationResult:
        """验证Skill质量"""

    def approve_and_publish(self, proposal_id: str,
                           approver: str = "system") -> bool:
        """批准并发布Skill到Registry"""

    def suggest_skills_for_task(self, task_description: str) -> List[SkillProposal]:
        """为给定任务推荐已有或新生成的Skill"""

    def get_pattern_library(self) -> List[SuccessPattern]:
        """获取所有已发现的模式"""

    def export_patterns(self) -> str:
        """导出模式库(JSON)"""

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
```

---

## 3. 模式提取算法

### 3.1 核心算法流程

```
ExecutionHistory (N条记录)
       ↓
  ┌─────────────────────┐
  │ 1. 过滤            │ ← 只保留 success=True 的记录
  │    (成功记录)       │
  └────────┬────────────┘
           ↓
  ┌─────────────────────┐
  │ 2. 步骤序列化       │ ← 将每条记录的steps转为特征向量
  │    (向量化)         │
  └────────┬────────────┘
           ↓
  ┌─────────────────────┐
  │ 3. 序列聚类         │ ← 相似步骤序列归为一类
  │    (聚类分组)       │
  └────────┬────────────┘
           ↓
  ┌─────────────────────┐
  │ 4. 模式泛化         │ ← 将具体值替换为通配符模式
  │    (抽象化)         │
  └────────┬────────────┘
           ↓
  ┌─────────────────────┐
  │ 5. 频率+置信度计算   │ ← 统计出现频率、成功率、置信度
  │    (评分排序)       │
  └────────┬────────────┘
           ↓
  ┌─────────────────────┐
  │ 6. 过滤输出         │ ← freq >= N 且 confidence >= T
  │    (阈值过滤)       │
  └─────────────────────┘
           ↓
     SuccessPattern[]
```

### 3.2 步骤相似度计算

```python
def step_similarity(a: ExecutionStep, b: ExecutionStep) -> float:
    """两条步骤的相似度 [0.0, 1.0]"""
    if a.action_type != b.action_type:
        return 0.0

    score = 0.0
    # 操作类型相同: +0.4
    score += 0.4

    # 目标路径相似(扩展名匹配): +0.3
    if _extension_match(a.target, b.target):
        score += 0.3
    elif _directory_match(a.target, b.target):
        score += 0.15

    # 描述语义重叠: +0.2
    desc_overlap = _word_overlap(a.description, b.description)
    score += 0.2 * desc_overlap

    # 结果一致性: +0.1
    if a.outcome == b.outcome == "success":
        score += 0.1

    return min(1.0, score)


def sequence_similarity(seq_a: List[ExecutionStep],
                       seq_b: List[ExecutionStep]) -> float:
    """两条步骤序列的相似度 [0.0, 1.0](编辑距离加权)"""
    # 使用动态规划计算最优对齐的相似度
    ...
```

### 3.3 模式泛化规则

| 具体值 | 泛化规则 | 示例 |
|--------|---------|------|
| 具体文件名 | `*.{ext}` | `utils/helper.py` → `*.py` |
| 具体目录 | `{dir}/**` | `src/core/engine.py` → `**/*.py` |
| 时间戳/随机ID | `{timestamp}` / `{id}` | `report_20260415.md` → `*.md` |
| 具体数值 | `{value}` | `port=8080` → `port={value}` |
| 项目特定路径 | `{project_path}` | `/Users/lin/project/` → `{project_path}` |

---

## 4. Skill生成策略

### 4.1 从模式到Skill的映射

```
SuccessPattern                    →    SkillProposal
─────────────────────────────────────────────────
pattern.name                     →    proposal.name
pattern.steps_template           →    proposal.steps
pattern.applicable_roles         →    proposal.required_roles
pattern.trigger_keywords         →    proposal.trigger_conditions
pattern.avg_success_rate        →    quality_score的一部分
pattern.source_records           →    元数据(可追溯)
```

### 4.2 自动填充字段

| 字段 | 生成策略 |
|------|---------|
| **slug** | name → kebab-case |
| **version** | 默认 "1.0.0" |
| **description** | 从步骤模板和触发条件自动生成 |
| **input_schema** | 分析步骤中需要的输入参数 |
| **output_schema** | 分析步骤中产生的产出物类型 |
| **acceptance_criteria** | 从成功记录的结果中提取 |
| **category** | 基于主要操作类型分类(code-review/test/deploy/refactor...) |

### 4.3 Skill 分类体系

```python
class SkillCategory(Enum):
    CODE_GENERATION = "code-generation"       # 代码生成
    CODE_REVIEW = "code-review"               # 代码审查
    TESTING = "testing"                         # 测试相关
    DEPLOYMENT = "deployment"                   # 部署发布
    REFACTORING = "refactoring"               # 重构优化
    DOCUMENTATION = "documentation"           # 文档生成
    ANALYSIS = "analysis"                       # 分析诊断
    INTEGRATION = "integration"               # 集成配置
    SECURITY = "security"                     # 安全检查
    PERFORMANCE = "performance"               # 性能优化
    AUTO_GENERATED = "auto-generated"         # 自动生成
```

---

## 5. 质量验证体系

### 5.1 五维评估模型

| 维度 | 权重 | 评估方法 | 满分标准 |
|------|------|---------|---------|
| **完整性** | 25% | 步骤覆盖度、Schema完整 | 所有步骤有定义，I/O Schema完整 |
| **特异性** | 20% | 触发条件精确度 | 不与其他Skill过度重叠 |
| **可重复性** | 20% | 历史成功率、频次 | >= 3次成功执行，成功率>=80% |
| **安全性** | 20% | 包含的高风险操作比例 | 无BYPASS级操作，PROMPT<30% |
| **实用性** | 15% | 步骤数合理性、耗时 | 3-15步，总耗时<30min |

### 5.2 质量分级

| 分数范围 | 等级 | 处理方式 |
|---------|------|---------|
| 85-100 | A (优秀) | 自动发布 |
| 70-84 | B (良好) | 推荐发布，需快速审核 |
| 55-69 | C (合格) | 需人工改进后发布 |
| <55 | D (不合格) | 返回重新生成或丢弃 |

### 5.3 自动拒绝规则

以下情况自动标记为 D（不合格）：
- 步骤数为 0 或 > 20
- 包含 BYPASS 级别操作
- 触发条件过于宽泛（< 3个关键词）
- 来源记录全部来自同一任务（可能过拟合）
- 平均单步耗时 > 5 分钟

---

## 6. 与协作系统集成

### 6.1 数据采集点

```
Coordinator.execute_plan()
    ├── Worker.execute() × N
    │   ├── 产生 ExecutionRecord
    │   ├── 写入 Scratchpad
    │   └── PermissionGuard.check() → AuditEntry
    │
    └── 收集结果
        ├── Skillifier.record_execution(record)
        └── 后台异步: analyze_history() → 发现新模式
```

### 6.2 触发时机

| 事件 | 动作 |
|------|------|
| 任务完成(success) | 记录 ExecutionRecord |
| 累计 >= 5 条新记录 | 触发 analyze_history() |
| 发现新 pattern(confidence >= 0.6) | 自动生成 SkillProposal |
| Proposal 质量分数 >= 70 | 进入 REVIEWING 状态通知用户 |
| 用户确认 | 发布到 SkillRegistry |

### 6.3 Skill推荐集成

当 Coordinator.plan_task() 时：
1. 先查询 SkillRegistry 匹配已有 Skill
2. 再调用 Skillifier.suggest_skills_for_task()
3. 合并推荐结果，优先使用高质量 Skill

---

## 7. 文件结构

```
scripts/collaboration/
├── skillifier.py              ← 核心: Skillifier + 数据模型
├── skillifier_test.py         ← 测试套件
├── __init__.py                ← 更新导出
└── ...

docs/
├── architecture/
│   └── v3-phase2-skillify-design.md  ← 本文档
├── product-manager/
│   └── USER_STORIES_P2b.md          ← PM: 用户故事
└── test-expert/
    ├── TEST_PLAN_P2b.md             ← Tester: 测试计划
    ├── TEST_CASES_P2b.md            ← Tester: 测试用例
    └── TEST_REPORT_P2b.md           ← Tester: 测试报告
```

---

## 8. 验收标准

| 编号 | 标准 | 验证方式 |
|------|------|---------|
| AC-01 | 能从 ExecutionRecord 列表中提取 SuccessPattern | 单元测试 |
| AC-02 | 模式泛化正确处理文件路径/目录/时间戳 | 泛化测试 |
| AC-03 | 序列相似度计算合理(相同序列≈1.0, 完全不同≈0) | 相似度测试 |
| AC-04 | 生成的 SkillProposal 结构完整 | 生成测试 |
| AC-05 | 五维质量评分各维度返回 [0,100] | 验证测试 |
| AC-06 | 质量分级(A/B/C/D)边界正确 | 分级测试 |
| AC-07 | 自动拒绝规则生效 | 拒绝测试 |
| AC-08 | approve_and_publish 成功写入 Registry | 集成测试 |
| AC-09 | suggest_skills_for_task 返回相关推荐 | 推荐测试 |
| AC-10 | export/import 模式库 roundtrip | 序列化测试 |

---

## 9. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 模式过拟合(过于特化) | 中 | 低 | 最少3次不同任务的记录才生成模式 |
| 生成低质量 Skill | 中 | 中 | 五维验证 + 质量门槛 |
| 性能开销(大量历史分析) | 低 | 中 | 异步后台执行 + 增量分析 |
| 与现有 Skill 冲突 | 低 | 低 | slug 唯一性检查 + 版本管理 |
